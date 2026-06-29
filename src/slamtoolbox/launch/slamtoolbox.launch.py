import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, TimerAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """SLAM launch file.

    Prerequisites: zero.launch.py must be running (provides rover driver,
    EKF, URDF publisher, accessories, and PS4 controller).

    This file only adds:
      1. pointcloud_to_laserscan — converts 3D LiDAR to 2D /scan
      2. async_slam_toolbox_node — SLAM (publishes map -> odom)
    """

    use_sim_time = LaunchConfiguration('use_sim_time')

    declare_use_sim_time_argument = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description='Use simulation/Gazebo clock')

    slam_toolbox_pkg = get_package_share_directory("slamtoolbox")
    slam_config_file = os.path.join(slam_toolbox_pkg, "config", "slamtoolbox_params.yaml")

    # Convert 3D point cloud to 2D laser scan for SLAM Toolbox
    pointcloud_to_laserscan_node = Node(
        package='pointcloud_to_laserscan',
        executable='pointcloud_to_laserscan_node',
        name='pointcloud_to_laserscan',
        output='screen',
        parameters=[{
            'target_frame': 'base_footprint',
            'transform_tolerance': 0.05,
            'min_height': 0.15,
            'max_height': 1.00,
            'angle_min': -3.14159,
            'angle_max': 3.14159,
            'angle_increment': 0.0087,
            'scan_time': 0.1,
            'range_min': 0.20,
            'range_max': 8.0,
            'use_inf': True,
            'use_sim_time': use_sim_time,
            'qos_reliability': 2,
        }],
        remappings=[
            ('cloud_in', '/rslidar_points'),
            ('scan', '/scan')
        ],
    )

    # SLAM Toolbox — publishes map -> odom
    slam_toolbox_node = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[
            slam_config_file,
            {'use_sim_time': use_sim_time}
        ],
    )

    ld = LaunchDescription()
    ld.add_action(declare_use_sim_time_argument)

    # Delay pointcloud_to_laserscan slightly to let TF tree stabilize
    delayed_pointcloud_to_laserscan = TimerAction(
        period=2.0,
        actions=[pointcloud_to_laserscan_node]
    )
    ld.add_action(delayed_pointcloud_to_laserscan)
    ld.add_action(slam_toolbox_node)

    return ld