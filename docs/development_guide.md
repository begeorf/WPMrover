# [rover_name] Robot Deployment: Development Documentation

## 1. System Overview
This system provides automated remote access for developers. It runs on top of the automation system, see `automation_guide.md`. It requires:

- **Connection:** Rover and Asus Device must be connected to the same network, and the network must have internet. 
<!-- If all fail, it creates its own fallback Hotspot (**MAX-Hotspot**) so you are never locked out. -->
- **Robot in IDLE mode:** The robot will launch into IDLE mode. A user will press a button in foxglove to put the robot in dev mode
- **Charging:** Rover must be placed on the charger while in developer mode to prevent it from running out of battery and dying.

---

## 2. File Architecture

These are the`[TODO: number of files]` critical files that orchestrate the system.

| File Path | Role | Description |
|----------|------|-------------|
| `/usr/local/bin/wifi_fallback.sh` | Network Manager | Scans for any known WiFi network. If none connect within 45s, it launches the fallback Hotspot (MAX-Hotspot). |
| `/usr/local/bin/add-wifi` | Field Tool | A custom command to add new WiFi credentials. It scans first to verify the network exists before adding, preventing typos and connection drops. |
| `/home/rover/robot_env_loader.sh` | Env Setup | Loads ROS 2 Humble, CycloneDDS, and CUDA library paths. Sources the MAX-Brain-v1.0 workspace install. |
| `/usr/local/bin/start_robot_system.sh` | Orchestrator | The main script. Loads env, starts the Foxglove Bridge, and triggers the ROS launch. |
| `/etc/systemd/system/robot-app.service` | Service Def | Controls the orchestrator. Runs on boot and automatically restarts the application if it crashes. |
| `/home/unitree/MAX-Brain-v1.0/src/bringup/max_bringup/launch/max_bringup.launch.py` | ROS Launch | The "Brain." Launches Nav2, SLAM, camera, and AI in a timed sequence. |
`/etc/systemd/system/robot_dev_mode_start.service` | Service Def | Executes the `dev_mode_start.sh`  as root. |
`/usr/local/bin/dev_mode_start.sh` | Developer mode manager | Puts Tailscale up, allowing a devleoper to remotely SSH into the rover. |
---

## 3. The Startup Sequence

### T+0s IDLE Mode
Rover must be in IDLE mode with a foxglove connection to begin the processes.

### T+`[time]`s (User Input)
User presses the `[TODO: button name]` button
- Service callback: `[TOOD: callback name]` runs in the background

### T+`[time]`s (Dev mode Service file)
`rover_dev_mode_start.service` runs.
- Runs `dev_mode_start.sh` as `root`.

### T+70s (DEV mode )
- Robot becomes Accessable with its Tailscale IP address

---

## 4. Operator's Guide (Cheat Sheet)

### A. Foxglove automated developer mode

- Follow the steps in `automation_guide.md` to put the robot into IDLE mode.
- Press the button in foxglove to put the robot in developer mode.


---

### B. Developer mode from terminal commands
- Access the rover terminal either via SSH or with keyboard and mouse
- Put the robot in developer mode:
```bash
sudo systemctl start robot_dev_mode_start.service
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



