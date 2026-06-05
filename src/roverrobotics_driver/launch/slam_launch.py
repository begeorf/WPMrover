#!/usr/bin/env python3

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.actions import DeclareLaunchArgument
from launch.actions import LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    
    # Slam toolbox launch setup
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


    rl_launch_path = os.path.join(get_package_share_directory("roverrobotics_driver"), 'launch', 'robot_localizer.launch.py')
    robot_localizer_launch = IncludeLaunchDescription(PythonLaunchDescriptionSource(rl_launch_path),
        launch_arguments={'use_sim_time': use_sim_time}.items())
    
    # NEW: PointCloud to LaserScan Slicer node
    pointcloud_to_laserscan_node = Node(
        package='pointcloud_to_laserscan',
        executable='pointcloud_to_laserscan_node',
        name='pointcloud_to_laserscan',
        output='screen',
        parameters=[{
            'target_frame': 'base_link',
            'transform_tolerance': 0.05,
            'min_height': 0.10,
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

    # Add sim time arg
    ld.add_action(declare_use_sim_time_argument)
    
    # Add localization to launch description
    ld.add_action(robot_localizer_launch)

    # Run the data converter stream
    ld.add_action(pointcloud_to_laserscan_node)

    # Add slam setup to launch description
    ld.add_action(declare_slam_params_file_cmd)
    ld.add_action(start_async_slam_toolbox_node)
    
    return ld

