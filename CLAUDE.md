# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a ROS2 Humble (Ubuntu 22.04) colcon workspace that turns a **Rover Zero 3** ground vehicle (Walter P Moore) into an autonomous inspection robot running on an NVIDIA Jetson Orin NX. See [docs/delpoyment_plan.md](docs/delpoyment_plan.md) for the full milestone-by-milestone deployment log (hardware bring-up, driver installs, SLAM/Nav2 tuning, sensor specs, and dated field notes) and [docs/known_issues.md](docs/known_issues.md) for a running log of bugs, root causes, and fixes/workarounds.

Sensors: RoboSense Airy 3D LiDAR, BNO055 IMU, ZED 2i stereo camera, Ricoh Theta Z1 360 camera.

## Build / Run Commands

This is a standard colcon workspace — `src/` (packages), `build/`, `install/`, `log/` (all gitignored).

```bash
# Build everything
colcon build --symlink-install

# Build one package (much faster; do this when iterating on a single package)
colcon build --symlink-install --packages-select roverrobotics_driver

# Source after every build
source install/setup.bash
```

Common launches (all via `roverrobotics_driver`, run after sourcing):

```bash
ros2 launch roverrobotics_driver zero.launch.py                    # driver + URDF + accessories + EKF + PS4 controller
ros2 launch roverrobotics_driver slam_launch.py                    # pointcloud_to_laserscan + async_slam_toolbox_node (requires zero.launch.py already running)
ros2 launch roverrobotics_driver navigation_launch.py slam:=True    # Nav2 + slam_toolbox (mapping mode)
ros2 launch roverrobotics_driver navigation_launch.py map_file_name:=<name>  # Nav2 with a saved map (localization mode)
```

Bag record/playback (run from `~/rover_workspace`):

```bash
ros2 bag record -o test_folder
ros2 bag play test_folder --clock     # pair with use_sim_time:=True on slam/nav nodes
```

There is no test suite for the custom packages — verification is done by launching the stack and observing behavior in RViz/Foxglove, or by replaying a bag through `analyze_spins.py` (compares `/imu/data`, `/imu_raw`, wheel odometry, and EKF output against a known ground-truth rotation).

## Architecture

### Package layout (`src/`)
- **roverrobotics_driver** — the integration package; owns all launch files, the top-level configs (`config/*.yaml`), Nav2/slam_toolbox param files (`config/nav2_params.yaml`, `config/slam_configs/`), and the low-level chassis driver (`src/roverrobotics_ros2_driver.cpp`, wraps the vendor SDK under `library/`) that talks to the rover over `/dev/rover-control` and publishes wheel odometry + accepts `/cmd_vel`.
- **roverrobotics_description** — URDF/xacro for the chassis and sensor mounts, `display_*.launch.py` viewers.
- **roverrobotics_gazebo** — simulation launches/worlds (not currently the focus of this deployment).
- **roverrobotics_input_manager** — PS4/PS5 controller → `/cmd_vel` joystick mapping (`config/ps4_controller_config.yaml` / `ps5_controller_config*.yaml`, driven by `config/topics.yaml`).
- **bno055** — IMU driver (Python). `bno055/sensor/SensorService.py` is where raw IMU bytes are unpacked and published to `/imu_raw` and `/imu/data`; the angular-velocity correction factor lives here (see ISSUE-015 in known_issues.md).
- **rslidar_msg / rslidar_sdk** — RoboSense lidar message definitions and SDK/driver for the Airy 3D lidar; publishes `/rslidar_points`.
- **slamtoolbox** — vendored slam_toolbox with a project-specific `launch/slamtoolbox.launch.py` used by `navigation_launch.py`.
- **zed-ros2-wrapper** — Stereolabs ZED ROS2 wrapper (currently disabled in `accessories.launch.py` — commented out to stop it fighting wheel odometry over the `odom` transform; see TF ownership below).
- **theta_driver** — driver for the Ricoh Theta Z1 360 camera, publishes `/image_raw`.
- **libuvc-theta** (untracked, top-level) — vendored libuvc fork with Theta camera support, used by theta_driver.

### TF tree and odometry ownership (read this before touching localization)
This is the most fragile part of the system and the subject of most entries in `docs/known_issues.md`. The chain is:

```
map -> odom            published by slam_toolbox
odom -> base_footprint published by robot_localization (EKF), NOT by any individual sensor driver
base_footprint -> base_link -> chassis_link -> ... -> sensor links   published by robot_state_publisher (URDF)
```

- `robot_localizer.launch.py` starts the single `ekf_filter_node` (`config/localization_ekf.yaml`) that fuses wheel odometry (`/odometry/wheels`) and IMU (`/imu/data`) into `odom -> base_footprint`. This is included exactly once, from `zero.launch.py`.
- The rover chassis driver only publishes the `/odometry/wheels` topic, not TF (`publish_tf: false`) — it must never also broadcast `odom -> base_footprint` or it will fight the EKF.
- The ZED wrapper is launched with `publish_tf:=false` / `publish_map_tf:=false` for the same reason, and is currently disabled entirely in `accessories.launch.py`.
- The BNO055 `frame_id` must match what the TF tree expects (`bno055`) or SLAM re-localization after in-place rotations breaks (ISSUE-013).
- `slam_launch.py` deliberately does **not** re-launch the EKF — it assumes `zero.launch.py` is already running and only adds `pointcloud_to_laserscan` + `async_slam_toolbox_node`. Don't duplicate the EKF node across launch files.
- LiDAR is mounted at a fixed forward downward tilt; `pointcloud_to_laserscan` height/range filtering (`min_height`/`max_height`/`range_max`) is tuned to exclude floor returns at that angle — see ISSUE-005 before changing these.

### Config-driven accessories
`config/accessories.yaml` gates every sensor driver behind an `active: true/false` flag read by `accessories.launch.py` at launch-description-generation time (not a runtime param) — toggle a sensor on/off there rather than editing launch files. Per-robot hardware configs (wheel radius, wheel base, etc.) live in `config/<robot>_config.yaml` (e.g. `zero_config.yaml`); wheel geometry calibration errors show up as distance/rotation scaling bugs (see ISSUE-004).

### Known issues log
`docs/known_issues.md` is an append-only log (never delete entries, only update `Status:`) of numbered issues (`## ISSUE-NNN`). Check it before debugging TF, localization, or odometry problems — several past fixes (e.g. EKF yaw-velocity config, IMU frame_id, wheel radius/base calibration) are easy to accidentally revert. New entries are meant to be added via a `/record_issue` workflow.
