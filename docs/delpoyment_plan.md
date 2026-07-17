# Rover Zero 3 Autonomous Inspection Robot - Deployment Plan


**Company:** Walter P Moore


**Start Date:** May 11th | **Finish Date:** August 7th


## Project Overview
This document outlines the deployment and development plan for transforming the [Rover Zero 3](https://roverrobotics.com/products/4wd-rover-zero-unmanned-ground-vehicle?srsltid=AfmBOoqNb-cTH6PLr3lSvbTj5OcZ1Nz4kVjkthFVi45RrsCuU8j71Tde) into a fully autonomous inspection robot. This guide serves as both a technical roadmap and a tracking document.


**Visual Deployment Map:** Before diving into the technical milestones, we strongly encourage you to take a look at the project's high-level architecture and visual deployment plan here:
🔗 **[Rover Deployment Plan - Mural Board](https://app.mural.co/t/walterpmoore8943/m/walterpmoore8943/1777499592001/6e513c8c5d9d240c0a9fc8d2c950f6d322477fda)**


**Instructions:** Suggested workflow is to follow the milestones sequentially (modify this doc if you prefer another workflow). As you complete the tasks in each component, fill out the corresponding `Tests & Results` section and answer the `Evaluation Metrics & Questions`.


---


  ## Milestone 1: Hardware Setup


  ### Tasks
  - [ ] **NVIDIA Jetson Orin NX Installation:**
    - Mount the Jetson Orin NX.
    - Complete wiring and power distribution.
    - Install Ubuntu 24.04. (you may need usb wifi dongle)
  - [ ] **Sensor Installations:**
    - **Robosense Airy lidar:** Install, wire power, and configure network. Ping `192.168.1.200` and verify the reception of UDP packets.
    - **IMU:** Install physically, connect, and verify raw data reception.
    - **ZED 2i Stereo Camera:** Design/install mounting brackets, complete connections, and verify data stream.


  ### Tests & Results
  **Date Completed:** `[In Progress]`


  **Notes/Issues:**
- `[2026-05-11]`: Robot driving with PS4 controller verified.
- `[2026-05-12]`: Designed Jetson Orin NX mount and laser-cut a flat test template to verify geometry. Planned peripheral cabling.
- `[2026-05-13]`:
  - Finalized and printed Orin NX/IMU mounting bracket (V1).
    - *Known Issue #1:* Failed to account for a section of the chassis sticking up above the height of the bolt hole.
    - *Known Issue #2:* Tolerance conflict discovered with the lidar/camera bracket.
    - *Fix:* Updated CAD for Orin NX/IMU mounting bracket to address the tolerance issue. Planned to manually modify V1 print to clear obstacles until V2 print.
  - Brainstormed camera and lidar placements with Mark; started design on lidar/camera bracket (~40% complete)
- `[2026-05-14]`:
  - Redesigned Orin/IMU bracket to eliminate issues permanently in CAD (awaiting confirmation that hardware works before printing V2).
  - Printed two test versions of the lidar/camera bracket, both fit well with no tolerance issues.
  - Designed a localized bracket for the lidar (similar to Hossein's halo design).
- `[2026-05-15]`:
  - Printed the dedicated lidar bracket. No issues.
  - Finalized the lidar/camera bracket in CAD after checking wheel clearances (current lidar angle is set to 22 degrees) and sent it to the printer.
- `[2026-05-18]`:
  - Test-fit the heat-set inserts on Orin/IMU bracket V1.
  - Printed Orin/IMU bracket V2.
    - Mounted the Orin/IMU V2 bracket onto the robot. Noted a minor tolerance issue with the Orin being close to the space above a bolt making it inconvenient to screw in.
    - *Hardware spec:* Use M5x16mm bolts for the chassis mounts.
    - *Hardware Spec:* Use M2.5x4mm heat-set inserts and M2.5x6mm bolts for the Orin and IMU mounts, with washers on the IMU mount.
- `[2026-05-19]`:
  - Printed lidar/camera mount V1
     - Identified a tolerance issue between the bolts on the dedicated lidar bracket and the lidar/camera mount from the V1 print.
     - Reprinted the dedicated lidar bracket, resolved.
     - *Hardware spec:* Use M3x8mm bolts for the Zed 2i.
     - *Hardware spec:* Use M3x16mm bolts for the lidar.
     - *Hardware spec:* Bolt order for lidar mount: *Bolt head -> Washer -> lidar/camera mount -> dedicated lidar bracket -> Washer -> Lock washer -> Nut*.
     - *Hardware spec:* Use M5x16mm bolts for the chassis mounts
  - Mounted lidar/camera assembly, no issues
  - Connected the Jetson to the RoboSense Airy lidar; raw data verification was fully successful.
  - **Assembly & Hardware Stack Status:**
    - *Pending:* Extensive cable management is still required due to the large volume of peripheral routing.
- `[2026-06-16]`: Mounted a new version of the payload
  - Corrected the previous versions so everything faces the front
  - Peripherals are closer together, leaving more room for future peripherals and excess cables
 
### Evaluation Metrics & Questions
1. **Battery Life:** What is the tested battery life with the Orin NX and all sensors running simultaneously?
   - *Result:* `[Enter time in hours/minutes]`
2. **Power Consumption:** What is the average power drawn by the Robosense Airy lidar during operation?
   - *Result:* `[Enter Watts]`
3. **Compute Power Modes:** Can the system reliably run the Orin NX in MAX power mode, or does it need to be constrained to 25W or 15W to prevent voltage drops/overheating?
   - *Result:* `[Enter observations]`


---


## 💻 Milestone 2: Driver Installations


### Tasks
- [ ] **ROS2 Humble Installation:** Install on the Orin NX following the [official documentation](https://docs.ros.org/en/jazzy/Installation.html).
- [ ] **RoverRobotics SDK:** Install and configure the [RoverRobotics ROS2 SDK](https://github.com/RoverRobotics/roverrobotics_ros2/tree/main). Ensure compatibility with ROS2 Humble.
- [ ] **lidar Driver:** Install the [RoboSense ROS2 driver](https://github.com/RoboSense-lidar/rslidar_sdk). ~~*Note: May require modifications to compile/run smoothly on Jazzy.*~~
- [ ] **IMU Driver:** Find, install, and configure the appropriate ROS2 Humble driver for the IMU.
- [ ] **ZED 2i Driver:** Install the ZED SDK and the ROS2 wrapper for Humble. [ZED 2i ROS2 Wrapper] (https://github.com/stereolabs/zed-ros2-wrapper)


### Tests & Results
* **Date Completed:** `[2026-05-26]`


**Notes/Issues:**
- `[2026-05-20]`: Got Chromium working on the Orin
  - Had to manually reset the system date/time to install packages (I suspect this is also the culprit for the wifi driver thing).
    - This might be a necessary step for doing anything if I can't figure out how to make the time wifi synced.
  - *Reset system time*: `[sudo date -s YYYY-MM-DD HH:MM:SS]`
  - *Launch Chromium from terminal:* `[flatpak run chromium.Chromium &]`


- `[2026-05-20]`: System date and time WiFi-synced on boot.
- `[2026-05-20]`: Robosense lidar driver downloaded to Orin
- `[2026-05-20]`: BNO-055 driver downloaded to Orin
- `[2026-05-22]`: Zed SDK and Camera driver installed to Orin, camera synced to Orin and I could see output in Rviz
  - *to build*: `colcon build --symlink-install --cmake-agrs -DCMAKE_BUILD_TYPE=Release`
  - *source*: `source install/setup.bash`
  - *to run*: `ros2 launch zed_wrapper zed_camera.launch.py camera_model:='zed2i'`
  - *rviz*: (new terminal, source) `ros2 run rviz2 rviz2`
- `[2026-05-22]`: rslidar_sdk configured, lidar output confrimed in Rviz
  - *to build*: `colcon build --symlink-install --packages-select --rslidar_sdk`
  - *source*: `source install/setup.bash`
  - *to run*: `ros2 launch rslidar_sdk start.py`
- `[2026-05-22]`: First lidar frequency test had a steady state frequency of around 9Hz, second test was around 5Hz.
     - after running `pkill -f rslidar` this was fixed. So for whatever reason ^C'ing the launch command doesn't kill one of the background processes.
       - New issue: gracefully kill all background processes.
       - note: killing rslidar with pkill also stops rviz


### Evaluation Metrics & Questions
1. **lidar Data Specs:** What is the data size per frame and per second published by the lidar in ROS2?
   - *Result:* `1.38MB/frame, 11.8 MB/s`
   - These results were achieved using a very quick test. For more accurate data, I will do multiple trials of longer tests.
2. **Publishing Frequencies:**
   - IMU Frequency: `~47Hz` check default setting in config file
   - ZED 2i Frequency: `~29Hz` make this 15hz 15 fps
   - lidar Frequency: `~9Hz`
     
3. **ROS2 Interfaces:** List topic names and message types for the IMU, lidar, and ZED 2i outputs.
  - *Nodes running with Zed Active:*
    - `/clicked_point [geometry_msgs/msg/PointStamped]`
    - `/diagnostics [diagnostic_msgs/msg/DiagnosticArray]`
    - `/parameter_events [rcl_interfaces/msg/ParameterEvent]`
    - `/rosout [rcl_interfaces/msg/Log]`
    - `/rslidar_points [sensor_msgs/msg/PointCloud2]`
    - `/tf [tf2_msgs/msg/TFMessage]`
    - `/tf_static [tf2_msgs/msg/TFMessage]`
    - `/zed/joint_states [sensor_msgs/msg/JointState]`
    - `/zed/zed_description [std_msgs/msg/String]`
    - `/zed/zed_node/depth/camera_info [sensor_msgs/msg/CameraInfo]`
    - `/zed/zed_node/depth/depth_registered [sensor_msgs/msg/Image]`
    - `/zed/zed_node/depth/depth_registered/camera_info [sensor_msgs/msg/CameraInfo]`
    - `/zed/zed_node/depth/depth_registered/compressedDepth [sensor_msgs/msg/CompressedImage]`
    - `/zed/zed_node/imu/data [sensor_msgs/msg/Imu]`
    - `/zed/zed_node/odom [nav_msgs/msg/Odometry]`
    - `/zed/zed_node/point_cloud/cloud_registered [sensor_msgs/msg/PointCloud2]`
    - `/zed/zed_node/pose [geometry_msgs/msg/PoseStamped]`
    - `/zed/zed_node/pose/status [zed_msgs/msg/PosTrackStatus]`
    - `/zed/zed_node/rgb/color/rect/camera_info [sensor_msgs/msg/CameraInfo]`
    - `/zed/zed_node/rgb/color/rect/image [sensor_msgs/msg/Image]`
    - `/zed/zed_node/rgb/color/rect/image/camera_info [sensor_msgs/msg/CameraInfo]`
    - `/zed/zed_node/rgb/color/rect/image/compressed [sensor_msgs/msg/CompressedImage]`
    - `/zed/zed_node/rgb/color/rect/image/theora [theora_image_transport/msg/Packet]`
    - `/zed/zed_node/status/health [zed_msgs/msg/HealthStatusStamped]`
    - `/zed/zed_node/status/heartbeat [zed_msgs/msg/Heartbeat]`
  - *Nodes running with LiDAR Active:*
    - `/clicked_point [geometry_msgs/msg/PointStamped]`
    - `/goal_pose [geometry_msgs/msg/PoseStamped]`
    - `/initialpose [geometry_msgs/msg/PoseWithCovarianceStamped]`
    - `/parameter_events [rcl_interfaces/msg/ParameterEvent]`
    - `/rosout [rcl_interfaces/msg/Log]`
    - `/rslidar_points [sensor_msgs/msg/PointCloud2]`
    - `/tf [tf2_msgs/msg/TFMessage]`
    - `/tf_static [tf2_msgs/msg/TFMessage]`
  - *Nodes running with IMU Active:*
    - `/calib_status [std_msgs/msg/String]`
    - `/cmd_vel [geometry_msgs/msg/Twist]`
    - `/grav [geometry_msgs/msg/Vector3]`
    - `/imu/data [sensor_msgs/msg/Imu]`
    - `/imu_raw [sensor_msgs/msg/Imu]`
    - `/joint_states [sensor_msgs/msg/JointState]`
    - `/mag [sensor_msgs/msg/MagneticField]`
    - `/odometry/wheels [nav_msgs/msg/Odometry]`
    - `/parameter_events [rcl_interfaces/msg/ParameterEvent]`
    - `/robot_description [std_msgs/msg/String]`
    - `/robot_info [std_msgs/msg/Float32MultiArray]`
    - `/robot_status [std_msgs/msg/Float32MultiArray]`
    - `/rosout [rcl_interfaces/msg/Log]`
    - `/rover_zero2/battery_status [sensor_msgs/msg/BatteryState]`
    - `/soft_estop/reset [std_msgs/msg/Bool]`
    - `/soft_estop/trigger [std_msgs/msg/Bool]`
    - `/temp [sensor_msgs/msg/Temperature]`
    - `/tf [tf2_msgs/msg/TFMessage]`
    - `/tf_static [tf2_msgs/msg/TFMessage]`
    - `/trim_event [std_msgs/msg/Float32]`
  - *Nodes running with zero launch file active*
    - `/calib_status [std_msgs/msg/String]`
    - `/camera/camera_description [std_msgs/msg/String]`
    - `/camera/joint_states [sensor_msgs/msg/JointState]`
    - `/camera/zed_node/depth/camera_info [sensor_msgs/msg/CameraInfo]`
    - `/camera/zed_node/depth/depth_registered [sensor_msgs/msg/Image]`
    - `/camera/zed_node/depth/depth_registered/camera_info [sensor_msgs/msg/CameraInfo]`
    - `/camera/zed_node/depth/depth_registered/compressedDepth [sensor_msgs/msg/CompressedImage]`
    - `/camera/zed_node/imu/data [sensor_msgs/msg/Imu]`
    - `/camera/zed_node/odom [nav_msgs/msg/Odometry]`
    - `/camera/zed_node/point_cloud/cloud_registered [sensor_msgs/msg/PointCloud2]`
    - `/camera/zed_node/pose [geometry_msgs/msg/PoseStamped]`
    - `/camera/zed_node/pose/status [zed_msgs/msg/PosTrackStatus]`
    - `/camera/zed_node/rgb/color/rect/camera_info [sensor_msgs/msg/CameraInfo]`
    - `/camera/zed_node/rgb/color/rect/image [sensor_msgs/msg/Image]`
    - `/camera/zed_node/rgb/color/rect/image/camera_info [sensor_msgs/msg/CameraInfo]`
    - `/camera/zed_node/rgb/color/rect/image/compressed [sensor_msgs/msg/CompressedImage]`
    - `/camera/zed_node/rgb/color/rect/image/theora [theora_image_transport/msg/Packet]`
    - `/camera/zed_node/status/health [zed_msgs/msg/HealthStatusStamped]`
    - `/camera/zed_node/status/heartbeat [zed_msgs/msg/Heartbeat]`
    - `/clicked_point [geometry_msgs/msg/PointStamped]`
    - `/cmd_vel [geometry_msgs/msg/Twist]`
    - `/diagnostics [diagnostic_msgs/msg/DiagnosticArray]`
    - `/goal_pose [geometry_msgs/msg/PoseStamped]`
    - `/grav [geometry_msgs/msg/Vector3]`
    - `/imu/data [sensor_msgs/msg/Imu]`
    - `/imu_raw [sensor_msgs/msg/Imu]`
    - `/initialpose [geometry_msgs/msg/PoseWithCovarianceStamped]`
    - `/joint_states [sensor_msgs/msg/JointState]`
    - `/mag [sensor_msgs/msg/MagneticField]`
    - `/map [nav_msgs/msg/OccupancyGrid]`
    - `/map_updates [map_msgs/msg/OccupancyGridUpdate]`
    - `/odometry/wheels [nav_msgs/msg/Odometry]`
    - `/parameter_events [rcl_interfaces/msg/ParameterEvent]`
    - `/robot_description [std_msgs/msg/String]`
    - `/robot_info [std_msgs/msg/Float32MultiArray]`
    - `/robot_status [std_msgs/msg/Float32MultiArray]`
    - `/rosout [rcl_interfaces/msg/Log]`
    - `/rover_zero2/battery_status [sensor_msgs/msg/BatteryState]`
    - `/rslidar_points [sensor_msgs/msg/PointCloud2]`
    - `/scan [sensor_msgs/msg/LaserScan]`
    - `/soft_estop/reset [std_msgs/msg/Bool]`
    - `/soft_estop/trigger [std_msgs/msg/Bool]`
    - `/temp [sensor_msgs/msg/Temperature]`
    - `/tf [tf2_msgs/msg/TFMessage]`
    - `/tf_static [tf2_msgs/msg/TFMessage]`
    - `/trim_event [std_msgs/msg/Float32]`






---


## Milestone 3: Autonomy Requirements


### Tasks
- [ ] **URDF & TF Tree:** Complete the Unified Robot Description Format (URDF) for the Rover. Accurately model the base footprint and add links/joints for the lidar, IMU, and ZED 2i. Include precise extrinsic and intrinsic values.
- [ ] **Rover Control API:** Figure out the rover control API. Test motor commands (`cmd_vel`), odometry feedback, and verify full ROS2 support for chassis control.
  - figure out if it uses `ros_control` or something else
- [ ] **Sensor Pipeline Modifications:** The current autonomy pipeline is integrated with the Robosense Airy but expects a RealSense D435i camera. Identify and implement the necessary modifications to transition the pipeline to the ZED 2i stereo camera.
  - install slam toolbox and nav2
  - need node converts 3d lidar to `laser_scan`
    - check lidar QoS settings too
    src go2 driver go2 driver
  - need odometry to base_link
    - look at slam_launch.py
    - look at sportmode to odom in unitree thing (in go2 driver)
  - install tf2 package
    - then run `ros2 run tf2_tools view_frames`


### Tests & Results
* **Date Completed:** `[YYYY-MM-DD]`
* **Notes/Issues:** > *(Document TF tree anomalies, API quirks, or ZED vs RealSense integration challenges)*
- `[2026-05-26]`: Tested motors with `cmd_vel`.
     - To launch: `ros2 launch roverrobotics_driver zero.launch.py`
     - Publish cmd_vel: `ros2 topic pub -r 20 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.2, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"`
       - Note: Linear positive x commands drive the robot backwards, angular positve z spins the robot CCW
     - Publish Odom: `ros2 topic echo /odometry/wheels`
     - Battery Percentage: `ros2 topic echo /rover_zero2/battery_status | grep percentage:`
       - Battery percentage only shows up in 3.33% intervals
- `[2026-05-26]`: According to Robosense docs, the airy's center is at the exact center of the base
  - This uses a right-handed Z up X forward coordinate system
- `[2026-05-26]`: According to StereoLabs docs, the Zed's center is at the center of the left lens.
  - The coordinate system can be customized; I will choose a right-handed Z up X forward system.
- `[2026-05-26]`: The IMU's current position means it has a right-handed Z up X right coordinate system. I don't want to re mount it so I'll rotate the axes in the congif files.
- `[2026-06-01]`: URDF file configured with launch file, might need further editing of zed reference frames
- `[2026-06-01]`: Customized `pointcloud_to_laserscan` and got output on `/scan` topic
- `[2026-06-15]`: How to visualize data in post: `ros2 bag`
  - `ros2 bag record -o test_folder`
  - puts all topic data in test folder, after you're finished close the terminal
    - where to run this command `~/workspace/`
    - this command also creates the folder that the data is saved to
  - `ros2 bag play test_folder`
  - plays back robot data as if it was happening in real time
  - `[06/17/2026]` Gemini says to not record all the packages
    - which packages to record...
- `[2026-06-16]`: Updated URDF to reflect new payload design
- `[2026-06-17]` PS4 Congroller with SlamToolBox
  - Integrated `ps4_controller.launch.py` into `slamtoolbox.launch.py`
  - Robot is not moving W.R.T. map frame... not sure what's wrong
- `[2026-06-18]`:
  - When testing SLAM yesterday, I noticed an issue with Lidar "bouncing", due to 2 different sources of odom fighting over the transform to it's frame
  - When testing SLAM yesterday, I noticed an issue with the /scan topic data being lower than "map" (map is linked to `base_link` and `points_to_laserscan` is linked to `base_footprint`)
    - I 'fixed' both of these sort of by accident, I changed a bunch of parameters a bunch of times and when I went to record a txt output of the frames it decided to work. This may have caused the issues below...
  - When testing the SLAM today after fixing the above, I noticed another issue: Lidar packets are being dropped due to the queue being full and the lidar is no longer centered on the map frame (it moves wrt the robot)
    - I'm not sure if this is caused because the tf tree is somehow broken with my accidental fix of the earlier odom issue
    - The lidar moving wrt the robot may also be caused by the fact that I was moving it by hand (so if it was using wheel encoder odometry this might be fixed)
  - Issue: need to modify the QoS settings to `BEST_EFFORT`, currently it's set to `RELIABLE`.




### Evaluation Metrics & Questions
1. **TF Verification:** Are all static transforms broadcasting at the correct rate? Is there any latency or drift between `base_link` and the sensor frames?
   - *Result:* `[Enter observations]`
2. **Control Latency:** What is the measured delay between sending a `Twist` message to the Rover API and the physical wheels moving?
   - *Result:* `[Enter ms]`
3. **Camera Pipeline Gap:** What specific parameter or node changes were required to swap the D435i for the ZED 2i (e.g., depth image encoding, topic remapping, field of view adjustments)?
   - *Result:* `[Describe modifications]`


---


## Milestone 4: SLAM
**Date Completed:** `[In Progress]`


### Tasks
- [ ] **SLAM:** Deploy the SLAM module (slamtoolbox, pointlio) utilizing the Robosense lidar and IMU.


### Tests & Results
- How to visualize data in post: `ros2 bag`
  - `[06-15-2026]` Meeting with Hossein
  - `ros2 bag record -o test_folder`
  - puts all topic data in test folder, after you're finished close the terminal
    - where to run this command `~/workspace/`
    - this command also creates the folder that the data is saved to
  - How to play back:
    - `ros2 param set /async_slam_toolbox_node use_sim_time True`
    - `ros2 launch slamtoolbox slamtoolbox.launch.py --ros-args -p use_sim_time:=True`
    - `ros2 bag play test_folder --clock`
    - this is currently incorrect
  - plays back robot data as if it was happening in real time
  - `[06/17/2026]` Gemini says to not record all the packages
    - which packages to record...




**Notes/Issues:**
- `[2026-06-08]`: Tested SLAM
  - To launch: `ros2 launch roverrobotics_driver slam_launch.py`
  - Map looks right based on the rover sitting on the desk, need to find a way of recording what the robot sees while driving.
- How to launch in SLAM mode:
  - first do `ros2 launch slamtoolbox slamtoolbox.launch.py`
  - then do `ros2 launch roverrobotics_driver navigation_launch.py slam:=True`
  - then do `ros2 action send_goal /explore_with_behavior nav2_msgs/action/ExploreWithBehavior "{}"`
- `[2026-06-10]`: Battery life test (Max power mode)
  - launched Zero Driver, Navigation (which runs SLAM), and motors at 0.5m/s
  - Battery life: `01:53:10`
- `[2026-06-17]` PS4 Congroller with SlamToolBox
  - Integrated `ps4_controller.launch.py` into `slamtoolbox.launch.py`
  - Robot is not moving W.R.T. map frame... not sure what's wrong
  - Fixed by changing config parameters
- `[2026-06-18]` Issue with Orin Dropping lidar packets
  - Solved: Previously both the zero launcher and the slam launcher were requesting the lidar data, changed the slam launcher so it doesn't use lidar data directly
- `[2026-06-19]` When fixing the above issue, this broke the visualization in post with slam
  - fixed by creating a dedicated slam post processing visualization node
- `[2026-07-07]` Fixed robot localization issues, slam works well now




### Evaluation Metrics & Questions
1. **SLAM Accuracy:** During a closed-loop drive in the lab, what is the estimated odometry drift upon returning to the origin?
   - *Result:* `[Enter drift in cm/degrees]`


---


## Milestones 5: Navigation
**Date Completed:** `[YYYY-MM-DD]`


### Tasks
- [ ] **Navigation:** Deploy the Nav2 stack. Tune costmaps and local planners for the Rover's kinematics.
  - test sending goals and sending waypoints (3 waypoints mabye)
  - increase complexity of goals and pathplanning
  - test dynamic obstable avoidance (do something where robot has to go around an obstacle)
    - test by sending a command straight to cmd_vel
    - publish goal to /goal_pose
      - message type shoudl be geometry_msgs/msg/PoseStamped
      - try navigate to pose action


### Tests & Results
**Date Completed:** `[YYYY-MM-DD]`


**Notes/Issues:**
- `[2026-06-08]`: Nav2 launch files
  - To launch: `ros2 launch roverrobotics_driver navigation_launch.py`
  - `navigation_launch.py` also launches `nav2_backend.py` and `slam_launch.py`
  - Setting a goal pose in rviz makes the robot try to drive to there
    - currently there is some placeholder costmap
  - How to launch in SLAM mode:
    - first do `ros2 launch slamtoolbox slamtoolbox.launch.py`
    - then do `ros2 launch roverrobotics_driver navigation_launch.py slam:=True`
    - then do `ros2 action send_goal /explore_with_behavior nav2_msgs/action/ExploreWithBehavior "{}"`
- `[2026-06-08]` Issue: Mounted hardware facing wrong direction
  - I placed the lidar and cameara mounted facing the back of the rover
- `[2026-06-09]` Navigation test: set goal pose 1m in front of robot
  - Result: robot moved 66cm forward
- `[2026-06-09]` Navigation test: set goal pose 1m behind robot and 180 turn
  - Result: Robot turned by ~30 degrees and moved backwards ~30cm
  - Interpretation: Need to run more tests to figure out the behavior when the robot's goal pose has a different orientation than the starting one
- `[2026-07-07]` Fixed robot localization issues, Nav2 works well now
  - Robot navigates to goals and avoids obstacles


### Evaluation Metrics & Questions
1. **Navigation Reliability:** Out of 10 autonomous point-to-point navigation commands with dynamic obstacles, how many were successfully reached without manual intervention?
   - *Result:* `[Enter success rate 10/10]`


---


## Milestone 6: 360 Camera
**Date Completed:** `[In Progress]`


### Tasks
- [ ] **Mounting** Mount the 360 Camera on the Rover Zero
- [ ] **Driver** Install the theta driver here: https://github.com/stella-cv/theta_driver?tab=readme-ov-file
- [ ] **URDF/TF** Update the URDF File for the exact position of the Z1 is available and publish transforms from base link to it

- add depth and cv to 360 camera
  - need calibration between lidar and camera
  - first try manual splicing between lidar and 360 camera




### Tests & Results

**Notes/Issues:**
- `[2026-06-30]` Installed `theta_driver` on orin
- `[2026-07-08]` 360 camera installed on rover
  - How to wake up camera from sleep mode: `gphoto2 --set-config=d80e=0`
  - Disable sleep timer: `gphoto2 --set-config=d803=0`
  - Disable auto power off timer: `gphoto2 --set-config=d81b=0`
  - Check values: `gphoto2 --get-config=[value]`
  - Both data and power can flow over the USB cable; infinate battery life
  - Need to compress images before sending to foxglove


### Evaluation Metrics & Questions
1. **360 Data Specs:** What is the data size per frame and per second published by the lidar in ROS2?
   - *Result:* `data speeds`
2. **Publishing Frequencies:**
    - **Z1 pubishing frequency**
      - `[~19hz]`
    - check if changing resolution 
     
3. **ROS2 Interfaces:** List topic names and message types for the IMU, lidar, and ZED 2i outputs.
    - *Nodes running with theta Active:*
      - `/clicked_point [geometry_msgs/msg/PointStamped]`
      - `/goal_pose [geometry_msgs/msg/PoseStamped]`
      - `/image_raw [sensor_msgs/msg/Image]`
      - `/initialpose [geometry_msgs/msg/PoseWithCovarianceStamped]`
      - `/move_base_simple/goal [geometry_msgs/msg/PoseStamped]`
      - `/parameter_events [rcl_interfaces/msg/ParameterEvent]`
      - `/rosout [rcl_interfaces/msg/Log]`


---


## Milestone 6: PointLio
**Date Completed:** `[In Progress]`


### Tasks
- [ ] **Pointlio** Deploy the pointlio package, configure sensors into pipeline


### Tests & Results
- Hossein pointlio library
  - https://git.walterpmoore.com/ai/robotics/unitree-robotics/-/tree/main/src/slam/pointlio?ref_type=heads
  - only focus on pointlio after slamtoolbox and nav2
    - pointlio is super sensitive
  - need to read pointlio first




**Notes/Issues:**




### Evaluation Metrics & Questions
1. **SLAM Accuracy:** During a closed-loop drive in the lab, what is the estimated odometry drift upon returning to the origin?
   - *Result:* `[Enter drift in cm/degrees]`


---


## Milestones 7: Computer Vision


### Tasks
- [ ] **Computer Vision Module:** Integrate our YOLOv11 (or latest stable) model for structural crack detection. Utilize the Orin NX GPU for inference.
- prerequisites for CV
  - data size
  - frequency
  - depth quality (is it accurate with reality and aligned with rbg)
  - check which topic is somethign like `depth_aligned_to_color` some unified topic
- where to download YOLO
  - Install via pytorch
  - pytorch version is heavyweight (not good for orin)
  - convert from pytorch to tensorRT
  - build TensorRT version on GPU
- Stage 1 is to run yolo v11 small and nano size
  - do object detection on depth camera
  - test throughput; how many FPS can we get throught the CV model
  - compare small vs nano model
  - don't use segmentation models; object detection only w/ bounding box
- https://docs.ultralytics.com/
YOLO Object Detection & Segmentation | Ultralytics Docs
Discover Ultralytics YOLO - the latest in real-time object detection and image segmentation. Learn about its features and maximize its potential in your projects.
- this has guides/tutorials
- Frank and Gorkem very knowledgable about CV
- Next tasks: use pixels close to the center of the bounding box, take the median depth and use that to find the depth
### Tests & Results
**Date Completed:** `[YYYY-MM-DD]`
**Notes/Issues:**
### Evaluation Metrics & Questions
1. **Computer Vision Performance:** What is the average inference FPS for the YOLO crack detection model running on the Orin NX?
   - *Result:* `[Enter FPS]`

---

## Milestones 8: User Interface
### Tasks
- [ ] **User Interface:** Set up Foxglove Studio dashboards for real-time visualization of the robot's state, maps, and camera feeds.
- UI panels; 
  - camera images with bounding box
  - costmap from above
  - 3d model of robot for better visual appearance
    - Make it dynamic for something visually cool
  - 3d view with lidar points (again compress/throttle/downfilter)
    - create a new topic for 2fps
    - use throttle library
      - hossein unsure if it voxelizes
  - Need to test foxglove on ipad
  - Leave this for now:
    - Final task: automate everything
      - start button: launches all launch files
      - stop button: ^C everything


### Tests & Results
**Date Completed:** `[YYYY-MM-DD]`


**Notes/Issues:**
- `[2026-06-24]` iPad delivered; passcode is 153426
- `[2026-06-29]` Foxglove connection to the robot established
  - On Orin, run `ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:=8765`
  - Create the port under the `ports` tab of the VS Code terminal.
  - Then, while SSH'd in, click `Open connection` in foxglove app. Type in `ws://localhost:8765` into the box and click connect.

### Evaluation Metrics & Questions
1. **UI Telemetry:** What is the total network bandwidth consumed when Foxglove is streaming the full UI dashboard (including point clouds and compressed images)?
   - *Result:* `[Enter Mbps]`


---


## Milestones 9: Exploration


### Tasks
- [ ] **Exploration:** Implement autonomous frontier exploration.




### Tests & Results
**Date Completed:** `[YYYY-MM-DD]`


**Notes/Issues:**




### Evaluation Metrics & Questions








---


## Milestone X: Test and Improvements


### Tasks
- [ ] **Lab Tests:** Iterative testing within the controlled lab environment. Ensure safe operation, obstacle avoidance, and system stability.
- [ ] **Field Tests:** Deploy the robot in a real-world inspection scenario (e.g., a parking garage or active site). Monitor suspension, real-world lighting impacts on the ZED 2i, and lidar performance in varied environments.


### Tests & Results
* **Date Completed:** `[YYYY-MM-DD]`
* **Lab Test Summary:** > *(Summarize lab performance, hardware durability, and software stability)*
* **Field Test Summary:** > *(Summarize field performance, environmental challenges, and crack detection accuracy in the wild)*


### Final Evaluation Metrics & Questions
1. **System Uptime:** What was the longest continuous autonomous run without a software crash or hardware fault?
   - *Result:* `[Enter duration]`
2. **Improvement Roadmap:** Based on the field tests, list the top 3 hardware or software improvements needed for V2 of the deployment.
   1. `[Improvement 1]`
   2. `[Improvement 2]`
   3. `[Improvement 3]`






