#!/bin/bash
# deploy/install.sh — install Rover-Brain-v1.0 automation files onto a robot.
#
# Run as the 'unitree' user (not sudo). Uses sudo only for writes to
# /usr/local/bin/ and /etc/systemd/.
#
# Usage:
#   cp deploy/robot.conf.example deploy/robot.conf
#   nano deploy/robot.conf          # set ETH_INTERFACE, confirm WORKSPACE and YOLO_ENGINE
#   bash deploy/install.sh
#
# Idempotent: safe to re-run after git pull to update installed files.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF="$SCRIPT_DIR/robot.conf"
TEMPLATES="$SCRIPT_DIR/templates"

# ── 1. Load and validate robot.conf ──────────────────────────────────────────

if [ ! -f "$CONF" ]; then
    echo "ERROR: $CONF not found."
    echo "       Copy the example and fill in values:"
    echo "         cp $SCRIPT_DIR/robot.conf.example $CONF"
    echo "         nano $CONF"
    exit 1
fi

source "$CONF"

MISSING=0
for var in ETH_INTERFACE WORKSPACE YOLO_ENGINE; do
    if [ -z "${!var}" ]; then
        echo "ERROR: $var is not set in robot.conf"
        MISSING=1
    fi
done
[ $MISSING -ne 0 ] && exit 1

echo "=== MAX-Brain-v1.0 install.sh ==="
echo "  ETH_INTERFACE : $ETH_INTERFACE"
echo "  WORKSPACE     : $WORKSPACE"
echo "  YOLO_ENGINE   : $YOLO_ENGINE"
echo ""

# ── 2. Install fake-hwclock (reliable timestamps on Jetson without RTC) ──────

if ! dpkg -s fake-hwclock &>/dev/null; then
    echo "[pre] Installing fake-hwclock for reliable log timestamps..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq fake-hwclock
    echo "      fake-hwclock installed — system clock will persist across reboots"
else
    echo "[pre] fake-hwclock already installed"
fi

# ── 3. Prerequisite checks (warn, don't abort) ───────────────────────────────

WARNINGS=0

if [ ! -f "$WORKSPACE/install/setup.bash" ]; then
    echo "WARNING: $WORKSPACE/install/setup.bash not found."
    echo "         Run 'colcon build --parallel-workers 2' in $WORKSPACE first."
    WARNINGS=$((WARNINGS + 1))
fi

if [ ! -f "$YOLO_ENGINE" ]; then
    echo "WARNING: YOLO engine not found at $YOLO_ENGINE"
    echo "         robot_manager will boot fine, but start_navigation will be rejected"
    echo "         until the engine file exists."
    echo "         Generate with: yolo export model=yolov8n.pt format=engine device=0"
    WARNINGS=$((WARNINGS + 1))
fi

if ! docker image inspect foxglove-unitree &>/dev/null; then
    echo "WARNING: Docker image 'foxglove-unitree' not found."
    echo "         Build it before first boot (~90 min, once per robot):"
    echo "           bash $SCRIPT_DIR/docker/build_image.sh"
    WARNINGS=$((WARNINGS + 1))
fi

if ! nmcli connection show "MAX-Hotspot" &>/dev/null; then
    echo "WARNING: NetworkManager profile 'MAX-Hotspot' not found."
    echo "         The wifi-fallback service will fail to create a hotspot."
    echo "         Create it manually with nmcli or via the robot's WiFi settings."
    WARNINGS=$((WARNINGS + 1))
fi

[ $WARNINGS -gt 0 ] && echo ""

# ── 4. Install robot_env_loader.sh (inside workspace) ────────────────────────

echo "[1/5] Installing robot_env_loader.sh..."
sed \
    -e "s|__ETH_INTERFACE__|$ETH_INTERFACE|g" \
    -e "s|__WORKSPACE__|$WORKSPACE|g" \
    "$TEMPLATES/robot_env_loader.sh" \
    > "$WORKSPACE/robot_env_loader.sh"
chmod 755 "$WORKSPACE/robot_env_loader.sh"
echo "      -> $WORKSPACE/robot_env_loader.sh"

# ── 5. Install system scripts (sudo) ─────────────────────────────────────────

echo "[2/5] Installing system scripts to /usr/local/bin/..."

# start_robot_system.sh — needs placeholder substitution
sed \
    -e "s|__WORKSPACE__|$WORKSPACE|g" \
    -e "s|__YOLO_ENGINE__|$YOLO_ENGINE|g" \
    "$TEMPLATES/start_robot_system.sh" \
    | sudo tee /usr/local/bin/start_robot_system.sh > /dev/null
sudo chmod 755 /usr/local/bin/start_robot_system.sh
echo "      -> /usr/local/bin/start_robot_system.sh"

# verbatim copies
for script in wifi_fallback.sh add-wifi; do
    sudo cp "$TEMPLATES/$script" "/usr/local/bin/$script"
    sudo chmod 755 "/usr/local/bin/$script"
    echo "      -> /usr/local/bin/$script"
done

# ── 6. Install systemd service units (sudo) ──────────────────────────────────
# TODO: add wifi fallback to templates
echo "[3/5] Installing systemd service units..."
for unit in robot_startup.service wifi-fallback.service; do
    sudo cp "$TEMPLATES/$unit" "/etc/systemd/system/$unit"
    sudo chmod 644 "/etc/systemd/system/$unit"
    echo "      -> /etc/systemd/system/$unit"
done

# ── 7. Enable services ───────────────────────────────────────────────────────

echo "[4/5] Enabling services..."
sudo systemctl daemon-reload
sudo systemctl enable robot-app.service wifi-fallback.service
echo "      robot-app.service and wifi-fallback.service enabled"

# ── 8. Patch setup.sh ETH_INTERFACE ─────────────────────────────────────────

echo "[5/5] Patching setup.sh ETH_INTERFACE..."
SETUP_SH="$WORKSPACE/setup.sh"
if [ -f "$SETUP_SH" ]; then
    sed -i "s|^ETH_INTERFACE=.*|ETH_INTERFACE=\"$ETH_INTERFACE\"|" "$SETUP_SH"
    echo "      -> $SETUP_SH (ETH_INTERFACE set to $ETH_INTERFACE)"
else
    echo "      WARNING: $SETUP_SH not found — skipping"
fi

# ── Summary ──────────────────────────────────────────────────────────────────

echo ""
echo "=== Installation complete ==="
echo ""
echo "Files installed:"
echo "  $WORKSPACE/robot_env_loader.sh"
echo "  /usr/local/bin/start_robot_system.sh"
echo "  /usr/local/bin/wifi_fallback.sh"
echo "  /usr/local/bin/add-wifi"
echo "  /etc/systemd/system/robot-app.service"
echo "  /etc/systemd/system/wifi-fallback.service"
echo ""

if [ $WARNINGS -gt 0 ]; then
    echo "NOTE: $WARNINGS warning(s) above — review before rebooting."
    echo ""
fi

echo "Next steps:"
echo "  1. Verify services are enabled:"
echo "       systemctl is-enabled robot-app.service wifi-fallback.service"
echo "  2. Test without rebooting:"
echo "       sudo systemctl start robot-app.service"
echo "       tail -f /tmp/robot_startup.log"
echo "  3. To apply on next boot:"
echo "       sudo reboot"
echo ""
echo "To re-run after git pull (idempotent):"
echo "  bash $SCRIPT_DIR/install.sh"
echo ""
echo "To remove all installed files:"
echo "  bash $SCRIPT_DIR/uninstall.sh"



