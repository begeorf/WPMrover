#!/usr/bin/env python3
"""Alternative SLAM launch file (used by navigation_launch.py).

Prerequisites: zero.launch.py must be running (provides rover driver,
EKF, URDF publisher, accessories, and PS4 controller).

This file only adds pointcloud_to_laserscan and async_slam_toolbox_node.
The EKF is launched by zero.launch.py — do NOT duplicate it here.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():

    use_sim_time = LaunchConfiguration('use_sim_time')
    slam_params_file = LaunchConfiguration('slam_params_file')

    declare_use_sim_time_argument = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description='Use simulation/Gazebo clock')
    declare_slam_params_file_cmd = DeclareLaunchArgument(
        'slam_params_file',
        default_value=os.path.join(get_package_share_directory("roverrobotics_driver"),
                                   'config/slam_configs', 'mapper_params_online_async.yaml'),
        description='Full path to the ROS2 parameters file to use for the slam_toolbox node')

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
            'range_max': 50.0,
            'use_inf': True,
            'use_sim_time': use_sim_time,
            'qos_reliability': 2
        }],
        remappings=[
            ('cloud_in', '/rslidar_points'),
            ('scan', '/scan')
        ]
    )

    start_async_slam_toolbox_node = Node(
        parameters=[
          slam_params_file,
          {'use_sim_time': use_sim_time}
        ],
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen')

    ld = LaunchDescription()
    ld.add_action(declare_use_sim_time_argument)
    ld.add_action(pointcloud_to_laserscan_node)
    ld.add_action(declare_slam_params_file_cmd)
    ld.add_action(start_async_slam_toolbox_node)

    return ld

