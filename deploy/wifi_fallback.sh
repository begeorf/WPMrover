 #!/bin/bash
# wifi_fallback.sh — Smart WiFi/Hotspot Manager for MAX-Brain
#
# Runs as a long-running systemd service (Type=simple).
#
# Phase 1 (BOOT):    Disable hotspot, scan for WiFi, wait up to 60s.
# Phase 2 (MONITOR): Check WiFi health every 30s. If WiFi drops, attempt
#                     reconnect; if that fails, activate hotspot and idle.
#
# Designed for Jetson boards with no RTC — install fake-hwclock for sane
# timestamps. The script also logs uptime in every line as a fallback.

set -u

# --- CONFIGURATION -----------------------------------------------------------
HOTSPOT_NAME=""         # disabled
SCAN_WAIT=30            # Max seconds to wait for WiFi at boot
SCAN_INTERVAL=3         # Seconds between checks during boot scan
MONITOR_INTERVAL=30     # Seconds between health checks after connection
STABLE_WAIT=4           # Seconds to verify connection + IP stability
SCAN_READY_WAIT=15      # Max seconds to wait for scan results to appear

# Ordered list of approved WiFi networks. ONLY these will be tried — no other
# saved profiles will be attempted. Add or reorder entries as needed.
PREFERRED_NETWORKS=("guestwireless" "TP-Link_6408" "MWireless") #network 1 is the WPM guest network

# Number of connection attempts per preferred network before moving to the next.
PREFERRED_RETRIES=(3 3)
# -----------------------------------------------------------------------------

# --- LOGGING -----------------------------------------------------------------
# Every log line: [<uptime>s] [<LEVEL>] [<PHASE>] <message>
# Phases: BOOT, SCAN, CONNECT, MONITOR, RECONNECT, FALLBACK, SYSTEM
_uptime() { cut -d' ' -f1 /proc/uptime; }

log_info()  { echo "[$(  _uptime)s] [INFO]  [$1] ${*:2}"; }
log_warn()  { echo "[$( _uptime)s] [WARN]  [$1] ${*:2}"; }
log_error() { echo "[$(_uptime)s] [ERROR] [$1] ${*:2}"; }

# Snapshot of full network state — call at every decision point
log_network_state() {
    local phase="$1"
    log_info "$phase" "---- Network State Snapshot ----"

    # WiFi radio
    local radio
    radio=$(nmcli radio wifi 2>&1)
    log_info "$phase" "WiFi radio: $radio"

    # WiFi device + state
    local wifi_dev wifi_state
    wifi_dev=$(nmcli -t -f DEVICE,TYPE device status 2>/dev/null \
               | grep ':wifi$' | head -1 | cut -d: -f1)
    if [[ -n "$wifi_dev" ]]; then
        wifi_state=$(nmcli -t -f DEVICE,STATE device status 2>/dev/null \
                     | grep "^${wifi_dev}:" | cut -d: -f2-)
        log_info "$phase" "WiFi device: $wifi_dev  state: $wifi_state"
    else
        log_warn "$phase" "No WiFi device found"
    fi

    # Active connections (all types)
    local active
    active=$(nmcli -t -f NAME,TYPE,DEVICE connection show --active 2>&1)
    if [[ -n "$active" ]]; then
        while IFS= read -r line; do
            log_info "$phase" "  active: $line"
        done <<< "$active"
    else
        log_info "$phase" "  active: (none)"
    fi

    # Visible WiFi networks (top 10 by signal strength)
    local visible
    visible=$(nmcli -t -f SSID,SIGNAL,SECURITY dev wifi list 2>/dev/null \
              | sort -t: -k2 -rn | head -10)
    if [[ -n "$visible" ]]; then
        log_info "$phase" "Visible networks (SSID:SIGNAL:SECURITY):"
        while IFS= read -r line; do
            log_info "$phase" "  wifi: $line"
        done <<< "$visible"
    else
        log_info "$phase" "Visible networks: (none)"
    fi

    # IP addresses on WiFi interface
    if [[ -n "$wifi_dev" ]]; then
        local ip
        ip=$(ip -4 addr show "$wifi_dev" 2>/dev/null \
             | grep -oP 'inet \K[\d.]+/[\d]+' || true)
        log_info "$phase" "WiFi IPv4: ${ip:-(none)}"
    fi

    log_info "$phase" "---- End Snapshot ----"
}

# --- HELPERS -----------------------------------------------------------------

# Return the name of the active WiFi client connection (excludes hotspot).
get_wifi_connection() {
    nmcli -t -f NAME,TYPE connection show --active 2>/dev/null \
        | grep ':802-11-wireless' \
        | head -n 1 \
        | cut -d: -f1
}

# Return 0 if the WiFi interface has a routable IPv4 address.
has_wifi_ip() {
    local wifi_dev
    wifi_dev=$(nmcli -t -f DEVICE,TYPE device status 2>/dev/null \
               | grep ':wifi$' | head -1 | cut -d: -f1)
    [[ -n "$wifi_dev" ]] \
        && ip -4 addr show "$wifi_dev" 2>/dev/null | grep -q 'inet '
}

# Actively try to bring up preferred WiFi connections in priority order.
# Only PREFERRED_NETWORKS are attempted — no other saved profiles are tried.
# Each network is retried PREFERRED_RETRIES[i] times before moving on.
#
# If a profile is already activating (NM auto-connect in progress), we wait
# for it rather than issuing a new `connection up` — which would send a
# `new-activation` signal to NM, tearing down the in-progress attempt and
# restarting from scratch (confirmed bug: see NM journal reason 'new-activation').
try_known_wifi() {
    local phase="$1"
    local i
    for (( i=0; i<${#PREFERRED_NETWORKS[@]}; i++ )); do
        local profile="${PREFERRED_NETWORKS[$i]}"
        local retries="${PREFERRED_RETRIES[$i]:-1}"
        local attempt nmcli_out

        # Check if NM is already activating this profile — if so, wait for it
        # instead of restarting it with a new connection-activate request.
        local cur_state
        cur_state=$(nmcli -t -f NAME,STATE connection show --active 2>/dev/null \
                    | grep "^${profile}:" | cut -d: -f2 || true)
        if [[ "$cur_state" == "activating" ]]; then
            log_info "$phase" "Profile '$profile' is already activating — waiting up to 30s for NM to complete"
            local w
            for (( w=0; w<30; w+=2 )); do
                sleep 2
                cur_state=$(nmcli -t -f NAME,STATE connection show --active 2>/dev/null \
                            | grep "^${profile}:" | cut -d: -f2 || true)
                if [[ "$cur_state" == "activated" ]]; then
                    log_info "$phase" "Profile '$profile' activated by NM auto-connect"
                    return 0
                elif [[ -z "$cur_state" ]]; then
                    log_warn "$phase" "Profile '$profile' auto-connect dropped — will retry explicitly"
                    break
                fi
            done
        fi

        for (( attempt=1; attempt<=retries; attempt++ )); do
            log_info "$phase" "Trying '$profile' (attempt ${attempt}/${retries})..."
            nmcli_out=$(nmcli --wait 30 connection up id "$profile" 2>&1)
            if [[ $? -eq 0 ]]; then
                log_info "$phase" "Activated '$profile' successfully"
                return 0
            else
                log_warn "$phase" "Profile '$profile' attempt ${attempt} failed: $nmcli_out"
            fi
        done
    done
    return 1
}

# Bring up the hotspot and log the result.
activate_hotspot() {
    local phase="$1"
    nmcli connection modify id "$HOTSPOT_NAME" connection.autoconnect yes 2>/dev/null
    log_info "$phase" "Hotspot autoconnect re-enabled"

    if nmcli connection up id "$HOTSPOT_NAME" 2>/dev/null; then
        log_info "$phase" "Hotspot '$HOTSPOT_NAME' is now active"
    else
        log_error "$phase" "Failed to bring up hotspot '$HOTSPOT_NAME'"
    fi
    log_network_state "$phase"
}

# --- SAFETY ------------------------------------------------------------------
# Always re-enable hotspot autoconnect on exit so a crash never strands the
# robot without any connectivity.
cleanup() {
    log_warn "SYSTEM" "Script exiting (signal or error) — re-enabling hotspot autoconnect"
}
trap cleanup EXIT

# =============================================================================
# PHASE 1: BOOT
# =============================================================================
log_info "BOOT" "========== Smart Network Manager Started =========="
log_info "BOOT" "Config: SCAN_WAIT=${SCAN_WAIT}s  STABLE_WAIT=${STABLE_WAIT}s  MONITOR_INTERVAL=${MONITOR_INTERVAL}s"

# 1a. Wait for NetworkManager
log_info "BOOT" "Waiting for NetworkManager to be ready..."
nm_wait=0
while ! nmcli general status &>/dev/null; do
    sleep 2
    nm_wait=$((nm_wait + 2))
    if (( nm_wait % 10 == 0 )); then
        log_warn "BOOT" "Still waiting for NetworkManager (${nm_wait}s)..."
    fi
done
log_info "BOOT" "NetworkManager is ready (waited ${nm_wait}s)"

# 1b. Log initial state before any changes
log_network_state "BOOT"

# 1c. Enable WiFi radio and trigger an explicit scan
nmcli radio wifi on
log_info "BOOT" "WiFi radio enabled"
nmcli dev wifi rescan 2>/dev/null || true
sleep 2

# =============================================================================
# PHASE 1b: SCAN — wait for external networks to appear
# =============================================================================
log_info "SCAN" "Waiting for WiFi scan results (up to ${SCAN_READY_WAIT}s)..."
scan_found=false
for (( w=0; w<SCAN_READY_WAIT; w+=2 )); do
    # Count visible SSIDs, excluding our own hotspot (remnant can linger at signal 0)
    scan_count=$(nmcli -t -f SSID dev wifi list 2>/dev/null \
                 | grep '[^[:space:]]' \
                 | grep -cv "^${HOTSPOT_NAME}$" || true)
    if (( scan_count > 0 )); then
        log_info "SCAN" "Scan complete: $scan_count external network(s) visible after ${w}s"
        scan_found=true
        break
    fi
    nmcli dev wifi rescan 2>/dev/null || true
    sleep 2
done
if [[ "$scan_found" != "true" ]]; then
    log_warn "SCAN" "No external networks found after ${SCAN_READY_WAIT}s — continuing anyway"
fi
log_network_state "SCAN"

# =============================================================================
# PHASE 1c: CONNECT — wait for a known WiFi network
# =============================================================================
log_info "CONNECT" "Waiting for a known WiFi connection (up to ${SCAN_WAIT}s)..."
connected=false

# First, actively try to bring up a saved WiFi profile.
# NM autoconnect is unreliable on Jetson after AP mode teardown.
try_known_wifi "CONNECT"

for (( i=0; i<SCAN_WAIT; i+=SCAN_INTERVAL )); do
    wifi_con=$(get_wifi_connection)

    if [[ -n "$wifi_con" ]]; then
        # Reject connections to non-preferred networks (e.g. open public WiFi)
        approved=false
        for net in "${PREFERRED_NETWORKS[@]}"; do
            [[ "$wifi_con" == "$net" ]] && approved=true && break
        done
        if [[ "$approved" == "false" ]]; then
            log_warn "CONNECT" "Connected to non-preferred network '$wifi_con' — disconnecting and retrying"
            nmcli connection down id "$wifi_con" 2>/dev/null || true
            sleep 2
            try_known_wifi "CONNECT"
            continue
        fi

        log_info "CONNECT" "Detected association to '$wifi_con' — verifying stability and IP (${STABLE_WAIT}s)..."
        sleep "$STABLE_WAIT"

        wifi_verify=$(get_wifi_connection)
        if [[ "$wifi_verify" == "$wifi_con" ]] && has_wifi_ip; then
            log_info "CONNECT" "SUCCESS: Connected to '$wifi_con' with valid IP"
            log_network_state "CONNECT"
            # Save clock now as a guard against hard power-off before NTP syncs.
            # A second save will happen in MONITOR once NTP is confirmed.
            fake-hwclock save && log_info "CONNECT" "fake-hwclock saved (pre-NTP)" || log_warn "CONNECT" "fake-hwclock save failed"
            connected=true
            break
        elif [[ "$wifi_verify" == "$wifi_con" ]]; then
            log_warn "CONNECT" "Associated to '$wifi_con' but no IP address yet (DHCP may be slow)"
        else
            log_warn "CONNECT" "Association to '$wifi_con' dropped during stability check"
            log_network_state "CONNECT"
        fi
    else
        log_info "CONNECT" "No known WiFi yet (${i}/${SCAN_WAIT}s elapsed)"
        # Rescan and retry known profiles periodically
        nmcli dev wifi rescan 2>/dev/null || true
        sleep 2
        try_known_wifi "CONNECT"
    fi

    sleep "$SCAN_INTERVAL"
done

if [[ "$connected" != "true" ]]; then
    log_warn "FALLBACK" "No stable WiFi connection after ${SCAN_WAIT}s — entering continuous retry mode"
    log_network_state "FALLBACK"

    # Continually scan and try preferred networks indefinitely
    while true; do
        log_info "RECONNECT" "Retrying preferred WiFi networks..."
        nmcli dev wifi rescan 2>/dev/null || true
        sleep 3
        if try_known_wifi "RECONNECT"; then
            log_info "RECONNECT" "Successfully reconnected!"
            break
        fi
        sleep "$MONITOR_INTERVAL"
    done
fi

# =============================================================================
# PHASE 2: MONITOR — check WiFi health periodically
# =============================================================================
log_info "MONITOR" "Entering WiFi health monitor (check every ${MONITOR_INTERVAL}s, logging only)..."

ntp_clock_saved=false

while true; do
    sleep "$MONITOR_INTERVAL"

    # Save NTP-accurate clock once NTP sync is confirmed (one-time).
    if [[ "$ntp_clock_saved" == "false" ]] && timedatectl | grep -q 'synchronized: yes'; then
        fake-hwclock save && log_info "MONITOR" "fake-hwclock saved (NTP-confirmed)" || log_warn "MONITOR" "fake-hwclock save (NTP) failed"
        ntp_clock_saved=true
    fi

    wifi_con=$(get_wifi_connection)

    if [[ -n "$wifi_con" ]]; then
        approved=false
        for net in "${PREFERRED_NETWORKS[@]}"; do
            [[ "$wifi_con" == "$net" ]] && approved=true && break
        done
        if [[ "$approved" == "false" ]]; then
            log_warn "MONITOR" "Connected to non-preferred network '$wifi_con' — disconnecting"
            nmcli connection down id "$wifi_con" 2>/dev/null || true
        elif has_wifi_ip; then
            log_info "MONITOR" "WiFi healthy: '$wifi_con'"
        else
            log_warn "MONITOR" "WiFi '$wifi_con' associated but no IP — possible DHCP issue"
            log_network_state "MONITOR"
        fi
    else
        log_warn "MONITOR" "WiFi connection lost"
        log_network_state "MONITOR"
    fi
done


