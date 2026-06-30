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