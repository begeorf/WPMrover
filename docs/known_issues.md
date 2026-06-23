# Known Issues - Rover Zero

**Rules:**
- Headings: `## ISSUE-NNN: short title` — do not change this format.
- Status values: `open` | `resolved` | `workaround_in_place` | `needs_more_info`
- Never delete entries — mark resolved issues `**Status:** resolved` and leave them in place.
- ISSUE numbers are assigned monotonically and never reused.
- To add a new issue during a robot session, run `/record_issue` in Claude Code.

---

## ISSUE-001: TF Fighting Conflict Between ZED Camera and Wheel Encoders During Recording

* **Status:** resolved
* **Root Cause:** A resource conflict was discovered where both the ZED launch configuration and the SLAM launch configuration were simultaneously trying to access the raw LiDAR data stream, leading to dropped packets. An initial attempt to fix this by preventing the SLAM launcher from accessing the LiDAR data directly caused a downstream break in RViz's frame rendering.
* **Resolution:** Created a dedicated, standalone post-processing launch file (`playback_slam.launch.py`) designed specifically for visualizing data and running SLAM calculations natively over a recorded `rosbag` stream.

## ISSUE-002: Vertical Frame and Lidar Point Cloud Jitter During Post-Visualization Replays

* **Status:** open / postponed
* **Description:** While replaying test data, the coordinate frames and the LiDAR point cloud display rapid vertical jumping/vibrating artifacts. The issue stems from a 3D transform orientation mismatch: the ZED camera tracks microscopic lens movements in full 3D space (fluctuating pitch, roll, and Z-height), which rigidly conflicts with the flat 2D projection constraints expected by the robot base and the 2D SLAM pipeline.
* **Workaround / Fix:** This issue remains unresolved/unintegrated long-term as priorities have shifted to implementing Nav2.

## ISSUE-003: Severe Yaw Drift and Map Divergence with Robot Localizer Pipeline

* **Status:** open
* **Description:** When running the new `robot_localization` data pipeline during playback, the robot completely loses track of its orientation. The LiDAR data shifts wildly in the yaw (rotational) direction rather than locking onto fixed features. Because the raw odometry frames from the bag were remapped to prevent authority fights, `slam_toolbox` is starved of an accurate baseline transform chain (`odom -> base_footprint`), causing incoming laser scans to paint obstacle walls haphazardly all over the map.
* **Workaround / Fix:** Needs investigation into how the robot localizer's state estimation transforms are being exposed or regenerated during bag playback when historical TFs are hidden.