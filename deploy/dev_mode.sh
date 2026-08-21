#!/usr/bin/env bash
set -euo pipefail

echo "=== Enabling Developer Support Mode ==="

# 1. Bring up Tailscale with Tailscale SSH enabled
echo "[+] Starting Tailscale..."
sudo tailscale up --ssh

# 2. Prevent system sleep, suspend, and hibernation
echo "[+] Disabling system sleep and suspend targets..."
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target

# 3. Disable Wi-Fi power management (if Wi-Fi is used)
if command -v nmcli &> /dev/null; then
    echo "[+] Disabling Wi-Fi power saving..."
    sudo nmcli radio wifi on
    # Disables powersave on active wifi connection
    WIFI_CONN=$(nmcli -t -f UUID,TYPE connection show --active | grep 802-11-wireless | cut -d: -f1 || true)
    if [ -n "$WIFI_CONN" ]; then
        sudo nmcli connection modify "$WIFI_CONN" 802-11-wireless.powersave 2
    fi
fi

# 4. Prevent USB/Network device autosuspend (NVIDIA Jetson specific)
if [ -f /sys/module/usbcore/parameters/autosuspend ]; then
    echo "[+] Disabling USB autosuspend..."
    echo -1 | sudo tee /sys/module/usbcore/parameters/autosuspend > /dev/null
fi

echo ""
echo "=== Developer Mode ACTIVE ==="
echo "Tailscale IP:"
tailscale ip -4
echo "Hostname: $(hostname)"