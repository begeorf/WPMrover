# Known Issues - Rover Zero

**Rules:**
- Headings: `## ISSUE-NNN: short title` — do not change this format.
- Status values: `open` | `resolved` | `workaround_in_place` | `needs_more_info`
- Never delete entries — mark resolved issues `**Status:** resolved` and leave them in place.
- ISSUE numbers are assigned monotonically and never reused.
- To add a new issue during a robot session, run `/record_issue` in Claude Code.

---

## ISSUE-001: TF Fighting Conflict Between ZED Camera and Wheel Encoders During Recording

* **Status:** `resolved`
* **Root Cause:** A resource conflict was discovered where both the ZED launch configuration and the SLAM launch configuration were simultaneously trying to access the raw LiDAR data stream, leading to dropped packets. An initial attempt to fix this by preventing the SLAM launcher from accessing the LiDAR data directly caused a downstream break in RViz's frame rendering.
* **Resolution:** Created a dedicated, standalone post-processing launch file (`playback_slam.launch.py`) designed specifically for visualizing data and running SLAM calculations natively over a recorded `rosbag` stream.

## ISSUE-002: Vertical Frame and Lidar Point Cloud Jitter During Post-Visualization Replays

* **Status:** `open / postponed`
* **Description:** While replaying test data, the coordinate frames and the LiDAR point cloud display rapid vertical jumping/vibrating artifacts. The issue stems from a 3D transform orientation mismatch: the ZED camera tracks microscopic lens movements in full 3D space (fluctuating pitch, roll, and Z-height), which rigidly conflicts with the flat 2D projection constraints expected by the robot base and the 2D SLAM pipeline.
* **Workaround / Fix:** This issue remains unresolved/unintegrated long-term as priorities have shifted to implementing Nav2.

## ISSUE-003: Severe Yaw Drift and Map Divergence with Robot Localizer Pipeline

* **Status:** `open`
* **Description:** When running the new `robot_localization` data pipeline during playback, the robot completely loses track of its orientation. The LiDAR data shifts wildly in the yaw (rotational) direction rather than locking onto fixed features. Because the raw odometry frames from the bag were remapped to prevent authority fights, `slam_toolbox` is starved of an accurate baseline transform chain (`odom -> base_footprint`), causing incoming laser scans to paint obstacle walls haphazardly all over the map.
* **Workaround / Fix:** Needs investigation into how the robot localizer's state estimation transforms are being exposed or regenerated during bag playback when historical TFs are hidden.

## ISSUE-004: Odometry Distance Scaling Mismatch

* **Status:** `resolved`
* **Date Tracked:** `[2026-06-23]`

### Description
When executing paths via Nav2 or receiving direct `geometry_msgs/msg/Twist` velocity inputs, the physical robot traveled significantly less distance (~30%) than the software calculated. The `BasicNavigator` script logged a successful 1.0 meter arrival, but the physical Rover platform only progressed approximately 30 cm. Additionally, when testing a known rotation rate, the rover was underrotating based on the expected behavior

### Root Cause
The underlying base controller driver parameters held an uncalibrated, overly inflated value for the physical wheel diameter/radius and wheel base. Because the software believed the wheels were much larger than reality, it calculated that fewer raw encoder ticks were required to cross a meter, resulting in premature halting.

### Resolution
The base driver configuration parameters were updated to scale down the expected radius by the tracked error margin (~0.3x multiplier) to match the physical dimensions of the Rover Zero platform tires. Additionally, the wheelbase was adjusted based on the amonut that the rover was overrotating to make predictable rotations.

1. Modified `wheel_radius` in `src/roverrobotics_driver/library/libover/include/protocol_zero_2.hpp`.
2. Modified `wheel_base` in `src/roverrobotics_driver/library/libover/include/protocol_zero_2.hpp`.
3. Compile new binaries:
   ```bash
   rm -rf build/roverrobotics_driver install/roverrobotics_driver
   colcon build --packages-select roverrobotics_driver --symlink-install
4. Source new changes:
   ```bash
   source install/setup.bash

---

## ISSUE-005: Vertical Point Cloud Noise Forcing Local Costmap Failures

* **Status:** `resolved`
* **Date Tracke** `[2026-06-25]`
* **Root Cause:** The 3D LiDAR is structurally mounted at a forward-facing 22-degree angle. Because the `pointcloud_to_laserscan` target tracking frame was evaluated relative to `base_footprint` (the level floor plane), the downward diagonal tilt cast beams into the floor further away from the chassis. This wide vertical evaluation slice incorrectly captured ground data, treating the level floor as a giant obstacle barrier, which overloaded the message queues and corrupted the local navigation layer.
* **Resolution:** Tightened the horizontal slicing constraints inside the `pointcloud_to_laserscan` configuration parameters to prune away floor noise and restricted the maximum calculation distance to match the local costmap bounds:
  ```python
  'min_height': 0.15,
  'max_height': 0.60,
  'range_max': 3.0,

---

## ISSUE-006: Odometry Z-Axis Drifting Under Map Plane Floor Bounds

* **Status:** `workaround_in_place`
* **Date Tracked:** `[2026-06-25]`
* **Root Cause:** Minute physical pitching, chassis flexing, and temporary tire traction slippage cause sensor measurement anomalies. When tracking bounds are completely rigid (`0.0`), tiny physical dips calculate negative coordinates relative to the map origin, causing the costmap package to reject raytracing updates out of allocated memory array limits.
* **Workaround:** Provided a 40cm structural mathematical safety cushion by adjusting the local costmap voxel/obstacle settings to clear ground noise and tolerate slight suspension changes in `src/roverrobotics_driver/config/nav2_params.yaml`
  ```yaml
   local_costmap:
      local_costmap:
         ros_parameters:
            voxel_layer:
               origin_z: -0.4

---

## ISSUE-007: Cables Periodically Become Disconnected

* **Status:** `open`
* **Date Tracked:** `[2026-06-25]`
* **Root Cause:** Some cables are only loosely connected, causing friction from other cables and/or centripetal forces when the robot is turning to cause them to become disconnected. 

---

## ISSUE-008: TF Cache Time-Sync Lag and Dropped Sensor Messages
* **Status:** `open`
* **Date Tracked:** `[2026-06-25]`
* **Root Cause:** Hardware communication line drops throw off the clock alignment between the chassis internal encoder/LiDAR microcontrollers and the Jetson Orin system clock. Incoming sensor transforms are interpreted by `slam_toolbox` and `nav2` as arriving from the past, causing the message filters to discard them.
* **Error Messages:** 
   ```txt
   [async_slam_toolbox_node-1] [INFO]: Message Filter dropping message: frame 'base_footprint' at time [Timestamp] for reason 'the timestamp on the message is earlier than all the data in the transform cache'
   [planner_server-7] [INFO] [global_costmap.global_costmap]: Timed out waiting for transform from base_link to map to become available, tf error: Invalid frame ID "map" passed to canTransform argument target_frame - frame does not exist

---

## ISSUE-009: Nav2 Compute Bottleneck and Costmap Out-of-Bounds Failures at Charger
* **Status:** `workaround_in_place`
* **Date Tracked:** `[2026-06-25]`
* **Root Cause:** Launching the full autonomous navigation stack while docked inside the charging station causes immediate failures. The close proximity of walls/obstructions triggers aggressive, cyclic costmap resizing routines. This overhead, combined with local trajectory path planning calculations, saturates the Orin CPU. The control loop drops below real-time constraints, leading the Behavior Tree to assume a collision/stuck state and abort the navigation handles.
* **Error Messages:** 
   ```txt
   [planner_server-7] [WARN] [nav2_costmap_2d]: Robot is out of bounds of the costmap!
   [planner_server-7] [INFO] [global_costmap.global_costmap]: StaticLayer: Resizing costmap to...
   [controller_server-5] [WARN] [controller_server]: Control loop missed its desired rate of 10.0000Hz
   [bt_navigator-9] [WARN] [BehaviorTreeEngine]: Behavior Tree tick rate 100.00 was exceeded!
   [planner_server-7] [WARN] [planner_server]: GridBased: failed to create plan with tolerance 0.50.
   [bt_navigator-9] [ERROR] [bt_navigator_navigate_to_pose_rclcpp_node]: Failed to get result for follow_path in node halt!
* **Workaround:** Implemented a two-part mitigation strategy:
   1. No-Compute Taxiing Workflow: Modify operation procedures to spin up PS4 controller with `zero.launch.py`. Manually teleoperate (taxi) the rover using a controller out of the charging dock and onto the open floor/starting tape line before starting navigation servers.
   2. Throttling Planner Constraints: Eased real-time computing stress on the Orin CPU by adjusting the local controller frequency down from `10.0Hz` to `5.0Hz` in the Nav2 parameter configuration file:
   ```yaml
   controller_server:
      ros__parameters:
         controller_frequency: 5.0

fix odometry between odom and base_link
use only lidar odometry or wheel odometry
fix controller teleop issues
camera_camera_center comes off of base_link
where is camera_camera_link coming tf tree
create an xacro file to link 
global costmap isn't working in navigation
do foxglove now for visualization
   install foxglove in personal computer
      https://foxglove.dev/download
   need foxglove bridge in robot

### **ISSUE-010: Joystick Controls Behave as Accumulative Accelerators Instead of Direct Velocity Inputs**

* **Status**: `Resolved`
* **Symptoms:** Pushing the joystick analogue stick behaves like an accelerator pedal—the robot continuously "winds up" speed and, upon releasing the stick back to the center deadzone, continues to "coast" or drift forward with high latency instead of snapping to an immediate mechanical stop.
* **Root Cause:** A hidden background system daemon (`/usr/sbin/roverrobotics`) automatically executes a duplicate robot stack (`zero_teleop.launch.py`) on boot. While the operator's active terminal sends real-time joystick coordinates from the manual launcher, this background service concurrently bombards the `/cmd_vel` topic. This duplicate node collision over the exact same topic and serial port interface results in severe message lag, a command queuing bottleneck, and erratic "accelerating/coasting" control loop behavior.
* **Fix / Resolution:** Permanently stop and disable the conflicting background system service to ensure your manual launch file has exclusive, immediate control over the hardware:

```bash
# 1. Stop the active background process immediately
sudo systemctl stop roverrobotics.service

# 2. Permanently disable the service from starting up on boot
sudo systemctl disable roverrobotics.service
```

---
### **ISSUE-011: Robot Odom Only moving In a Straight lines in Foxglove**

* **Status**: `Resolved`
* **Symptoms:** No matter if the robot was being spun around or not, odom was only tracking the linear movement.
* **Root Cause:** Inside `localization_ekf.yaml`, the wheel odometry (`odom_0_config`) had the parameter for yaw velocity set to `false`. This means the ekf node was not listening to the rotations that the wheels were publishing.
* **Fix / Resolution:** Set parameter for yaw velocity in `odom_0_config` to `true`.

```yaml
odom0_config: [false, false, false,
               false, false, false,
               true,  true,  false,
               false, false, true,  # roll velo, pitch velo, yaw velo
               false, false, false]
```

---
### **ISSUE-012: Foxglove is laggy after having it open for some time**
* **Status**: `workaround_in_place`
* **Symptoms**: I originally launched the foxglove bridge for a test and the zero launcher. Then I parked the robot, closed the zero launcher but left the foxglove bridge open. The next time I went to launch the zero launcher the positional updates of the robot took several seconds to show up in foxglove. I'm not sure if this is because foxglove was open for too long
* **Root Cause**: My guesses are that it's either because foxglove bridge was open for too long or because it had multiple records of the same nodes being published.
* **Fix/Resolution**: When I restarted the foxglove bridge the problems went away, so it could be that foxglove needs to be closed after every instance of the zero launcher is closed or that foxglove develops a lot of lag over time.

---
### **ISSUE-013: Robot toses track of where it is when running slam**

* **Status**: `Resolved`
* **Symptoms:** After launching `zero.launch.py` and `slamtoolbox.launch.py`, the robot loses where it is WRT to the 'map' frame. This causes the map generated to have obstacles in the wrong spots.
* **Root Cause:** The robot doesn't know how far it's rotated when doing "tank turns" (where it spins in place). This means whenever it turns, it must readjust its position based on known obstacle locations. The SLAM node doesn't keep that many lidar frames stored for this purpose, so if the rotation is so far where there are no identifiable obstacles after the tank turn the robot will fail to relocalize itself. This is because the IMU had the wrong `frame_id` value.
* **Fix / Resolution:** In `/src/roverrobotics_driver/config/accessories.yaml`, I changed the `frame_id` parameter to be `bno055`, what the TF tree is expecting. In `localization_ekf.yaml`, I changed the IMU `operation_mode` parameter from `OxOC #NDOF` to `0x08 #IMU`. This disables the magnetic sensors, and switches the IMU from absolute orientation to relative orientation. I also removed `yaw_vel` from `odom0` (wheels) and removed `x_accel` and `y_accel` from `imu0`. So the wheels control `x_vel` and `y_vel` and the IMU controls `yaw_vel`. I also changed the `use_control` param to `true`, which enables the EKF to predict where it thinks the robot should be based on inputs. I also changed some of the odom and slam parameters to try to make localization easier (bigger buffers, more area scanned to realign off known obstacles, etc). To see all the changes I made, check the changes for commit `c0d8d19`.

---
### **ISSUE-014: Orin sometimes loses connection with the rover after docking**

* **Status**: `workaround_in_place`
* **Symptoms:** After finshing a test and parking the rover on its charger, the rover driver sometimes failes with the next launch.
```bash
[INFO] [roverrobotics_driver-1]: process started with pid [14941]
[roverrobotics_driver-1] [INFO] [1782924520.495260517] [roverrobotics_driver]: Starting Rover Driver node
[roverrobotics_driver-1] [INFO] [1782924520.495787963] [roverrobotics_driver]: Robot type is Rover zero2 over serial
[roverrobotics_driver-1] [INFO] [1782924520.495834685] [roverrobotics_driver]: Receiving velocity command from /cmd_vel
[roverrobotics_driver-1] [INFO] [1782924520.495850558] [roverrobotics_driver]: Estop state is currently inactive
[roverrobotics_driver-1] [INFO] [1782924520.495859742] [roverrobotics_driver]: Receiving Estop activation at /soft_estop/trigger
[roverrobotics_driver-1] [INFO] [1782924520.495866911] [roverrobotics_driver]: Receiving Estop deactivation at /soft_estop/reset
[roverrobotics_driver-1] [INFO] [1782924520.503369693] [roverrobotics_driver]: Publishing Robot status on /robot_status at 60.00hz
[roverrobotics_driver-1] [INFO] [1782924520.503451776] [roverrobotics_driver]: Robot is in closed loop mode.
[roverrobotics_driver-1] [INFO] [1782924520.503463841] [roverrobotics_driver]: PID is at P:0.0011 I:0.0000 D:0.0001
[roverrobotics_driver-1] [INFO] [1782924520.503477505] [roverrobotics_driver]: Connecting to robot at /dev/rover-control
[roverrobotics_driver-1] Warning: ~/robot.config file not found, persistent trim disabled
[roverrobotics_driver-1] errorerror[FATAL] [1782924520.503729420] [roverrobotics_driver]: Error when connecting to robot.
[roverrobotics_driver-1] [FATAL] [1782924520.503862802] [roverrobotics_driver]: Robot at /dev/rover-control is not available. Check that port is available and permissions allow access.
[INFO] [roverrobotics_driver-1]: process has finished cleanly [pid 14941]
```
* **Root Cause:** Unsure, it seems to happen less of if I drive the rover more slowly into its charger
* **Fix / Resolution:** When this happens, here is the troubleshooting steps:
   - Make sure the rover cable is plugged in; check both the connection of:
      - the Rover cable to the Splitter
      - the Splitter to the Orin 
   - Once it's plugged in, try some terminal commands
   - `ls -l /dev/rover-control`
      - this should output something like `lrwxrwxrwx 1 root root 7 Jul  1 13:12 /dev/rover-control -> ttyACM0`
      - The important thing is `/dev/rover-control -> ttyACM0`: this means the rover is connected
      - If the Orin sees the Rover, try `ros2 launch roverrobotics_driver zero.launch.py` again
   - If the rover isn't recognized, try 
      - `sudo udevadm control --reload-rule && sudo udevadm trigger`   
      - then try `ls -l /dev/rover-control` again
   - If this fails, reboot is needed
      - Turn rover power button off
      - Unplug Rover cable from Orin, wait `10s`
      - Turn on Rover power button, wait a bit (ssh in first before moving to next step)
      - Plug Rover cable into Orin
      - Try `ls -l /dev/rover-control` again, it should work
   - If this fails idk

---
### **ISSUE-015: Sensor Inaccuracies when Spinning**

* **Status**: `Resolved`
* **Symptoms:** After launching `zero.launch.py` and `slamtoolbox.launch.py`, the robot loses where it is WRT to the 'map' frame. This causes the map generated to have obstacles in the wrong spots (This is issue #13). When I conducted manual angular rotation tests to see how far the robot was spinning, I found that the IMU was overshooting how far the robot moved by about `3.3%`.
* **Root Cause:** Unknown
* **Fix / Resolution:** In `/src/bno055/bno055/sensor/SensorService.py`, I added a correcting factor to the angular velocity in the z direction, scaling it back by `0.968`. Here is the before and after of the message that gets published to `/imu/raw`

```
imu_raw_msg.angular_velocity.z = \ 
self.unpackBytesToFloat(buf[16], buf[17]) / self.param.gyr_factor.value
```
```
imu_raw_msg.angular_velocity.z = \ 
(self.unpackBytesToFloat(buf[16], buf[17]) / self.param.gyr_factor.value) * 0.968
```
Here is the before and after of the message that gets published to `/imu/data`.
```
imu_msg.angular_velocity.z = \
self.unpackBytesToFloat(buf[16], buf[17]) / self.param.gyr_factor.value
```
```
imu_msg.angular_velocity.z = \
(self.unpackBytesToFloat(buf[16], buf[17]) / self.param.gyr_factor.value) * 0.968
```
After implementing these changes, the IMU error was 0.18% for 1 test where the robot was rotated 1800 degrees CCW. This is honestly close enough to be a measurement error without extremely accurate starting and final positions measurements.