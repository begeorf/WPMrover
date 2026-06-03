import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    """
    Launch file for SLAM Toolbox with GO2 robot, Hesai LiDAR, and required transforms
    """

    # Get package directories
    slam_toolbox_pkg = get_package_share_directory("slamtoolbox")
    hesai_lidar_driver_pkg = get_package_share_directory("hesai_lidar_driver")
    go2_description_pkg = get_package_share_directory("go2_description")

    # SLAM Toolbox configuration file
    slam_config_file = os.path.join(slam_toolbox_pkg, "config", "slamtoolbox_params.yaml")

    # Launch file paths
    hesai_launch_path = os.path.join(hesai_lidar_driver_pkg, "launch", "start.py")
    go2static_launch_path = os.path.join(go2_description_pkg, "launch", "go2static.launch.py")

    # Include Hesai LiDAR driver launch
    hesai_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(hesai_launch_path), launch_arguments={}.items()
    )

    # Include GO2 static transforms launch
    go2_static_transforms_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(go2static_launch_path), launch_arguments={}.items()
    )

    # GO2 driver sync — joints only (publish_odom=False avoids conflict with sport_to_odom)
    go2_driver_sync_node = Node(
        package="go2_driver",
        executable="go2_driver_sync",
        name="go2_driver_sync",
        output="screen",
        parameters=[
            {
                "publish_odom": False,
                "publish_pointcloud": False,
                "joint_publish_hz": 20.0,
                "use_sim_time": False,
            }
        ],
    )

    # GO2 Sport to Odometry node
    sport_to_odom_node = Node(
        package="go2_driver",
        executable="sport_to_odom",
        name="sport_to_odom",
        output="screen",
        parameters=[
            {
                "use_sim_time": False,
            }
        ],
    )

    pointcloud_to_laserscan_node = Node(
        package="go2_driver",
        executable="pointcloud_to_laserscan",
        name="pointcloud_to_laserscan",
        output="screen",
        parameters=[
            {
                "use_sim_time": False,
            }
        ],
    )

    # SLAM Toolbox node (async SLAM)
    slam_toolbox_node = Node(
        package="slam_toolbox",
        executable="async_slam_toolbox_node",
        name="slam_toolbox",
        output="screen",
        parameters=[slam_config_file],
    )

    # Create launch description
    ld = LaunchDescription()

    # Add all launch files and nodes

    ld.add_action(slam_toolbox_node)

    delayed_go2static = TimerAction(
        period=7.0,  # was 7.0
        actions=[go2_static_transforms_launch, go2_driver_sync_node],
    )
    ld.add_action(delayed_go2static)

    delayed_lidar_driver = TimerAction(
        period=14.0,  # was 14.0
        actions=[hesai_launch],
    )
    ld.add_action(delayed_lidar_driver)

    delayed_odom = TimerAction(
        period=20.0,  # was 20.0
        actions=[sport_to_odom_node],
    )
    ld.add_action(delayed_odom)

    delayed_pointcloud_to_laserscan = TimerAction(
        period=27.0,  # was 27.0
        actions=[pointcloud_to_laserscan_node],
    )
    ld.add_action(delayed_pointcloud_to_laserscan)
    return ld


if __name__ == "__main__":
    generate_launch_description()


