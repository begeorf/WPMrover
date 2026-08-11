# [rover_name] Robot Deployment: Automation Documentation

## 1. System Overview
This system provides a fully automated startup sequence for the Roverrobotics Rover Zero robot. It handles:

- **Smart Networking:** Automatically connects to any known WiFi (Home, Office, Hotspot). 
<!-- If all fail, it creates its own fallback Hotspot (**MAX-Hotspot**) so you are never locked out. -->
- **Field Management:** Includes a command-line tool (`add-wifi`) to safely add new networks on-site without losing connection.
- **Robust Application Launch:** Starts the entire ROS 2 stack (SLAM, Navigation, AI, Camera) automatically.
- **Crash Recovery:** Automatic service restarts on failure via systemd `Restart=on-failure`.

---

## 2. File Architecture

These are the 6 critical files that orchestrate the system.

| File Path | Role | Description |
|----------|------|-------------|
| `/usr/local/bin/wifi_fallback.sh` | Network Manager | Scans for any known WiFi network. If none connect within 45s, it launches the fallback Hotspot (MAX-Hotspot). |
| `/usr/local/bin/add-wifi` | Field Tool | A custom command to add new WiFi credentials. It scans first to verify the network exists before adding, preventing typos and connection drops. |
| `/home/rover/robot_env_loader.sh` | Env Setup | Loads ROS 2 Humble, CycloneDDS, and CUDA library paths. Sources the MAX-Brain-v1.0 workspace install. |
| `/usr/local/bin/start_robot_system.sh` | Orchestrator | The main script. Loads env, starts the Foxglove Bridge, and triggers the ROS launch. |
| `/etc/systemd/system/robot-app.service` | Service Def | Controls the orchestrator. Runs on boot and automatically restarts the application if it crashes. |
| `/home/unitree/MAX-Brain-v1.0/src/bringup/max_bringup/launch/max_bringup.launch.py` | ROS Launch | The "Brain." Launches Nav2, SLAM, camera, and AI in a timed sequence. |

---

## 3. The Startup Sequence

### Power On
Linux Kernel loads.

### T+45s (Network)
`wifi-fallback.service` runs.

- **Check:** Is any known WiFi reachable?
- **Priority:** Connects to the network with the highest `autoconnect-priority`.
- **Failure:** If no connection after 45s, create Hotspot:
  - SSID: `MAX-Hotspot`
  - Password: `MAX-Hotspot`

### T+60s (Application)
`robot-app.service` starts.

- Loads environment variables (`robot_env_loader.sh`)
- Starts Foxglove Bridge (Docker)
- Executes ROS 2 Launch

### T+70s (ROS Nodes)
- **0s:** Nav2 & SLAM
- **+5s:** RealSense Camera
- **+20s:** YOLO Depth Node
- **+30s:** Object Mapper
- **+40s:** Voxel Filter (LiDAR downsampler for visualization)

---

## 4. Operator's Guide (Cheat Sheet)

### A. Managing WiFi in the Field

When you arrive at a new location:

1. Connect your laptop to:
   - SSID: `MAX-Hotspot`
2. SSH into the robot:
   ```bash
   ssh unitree@192.168.123.161
   ```

   or

   ```bash
   ssh unitree@ubuntu.local
   ```

3. Run the tool:
   ```bash
   sudo add-wifi
   ```

4. Follow prompts (Scan → Enter Password → Reboot)

---

### B. Start / Stop Services

Stop the Robot App:
```bash
sudo systemctl stop robot-app.service
```

Start the Robot App:
```bash
sudo systemctl start robot-app.service
```

Restart the Robot App:
```bash
sudo systemctl restart robot-app.service
```

---

### C. Debugging Logs

Main Application Log (ROS/Python Errors):
```bash
tail -f /tmp/robot_startup.log
```

Network Manager Log (WiFi/Hotspot Switching):
```bash
sudo journalctl -u wifi-fallback.service -f
```

---

## 5. Technical Notes for Developers

### YOLO Node Launch

The YOLO node (`object_detection/yolo_depth_node`) requires `LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1` on aarch64 targets. This is handled directly in `max_bringup.launch.py` via the `additional_env` argument on the `Node()` action — no workaround scripts are needed.

The YOLO TensorRT engine is expected at `/home/unitree/yolov8n.engine`. This path is passed as the `yolo_engine_path` launch argument by `start_robot_system.sh`.

---

### Internal Network ("Conn1")

The robot has an internal ethernet connection named **Conn1** used for communication with the legs.

Notes:
- The system may report "Connected to Conn1" even without internet.
- External WiFi networks are prioritized.
- Default `autoconnect-priority` is **100** for networks added via `add-wifi`.



