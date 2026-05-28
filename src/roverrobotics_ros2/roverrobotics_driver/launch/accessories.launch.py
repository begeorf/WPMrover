#!/usr/bin/env python3

import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.actions import DeclareLaunchArgument
from launch.actions import LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from math import pi
import yaml

def generate_launch_description():
    ld = LaunchDescription()

    # Locate package directories
    driver_share = get_package_share_directory('roverrobotics_driver')
    zed_share = get_package_share_directory('zed_wrapper')
    rslidar_share = get_package_share_directory('rslidar_sdk') # Find RoboSense Share

    accessories_config_path = Path(driver_share, 'config/accessories.yaml')
    zed_config_path = Path(zed_share, 'config/zed2i.yaml')

     # Read the config file
    with open(accessories_config_path, 'r') as f:
        accessories_config = yaml.load(f, Loader=yaml.FullLoader)

    
   # 1. RoboSense Airy 3D Lidar Setup (Replaced 2D RPLidar)
    if accessories_config.get('rslidar', {}).get('ros__parameters', {}).get('active', False):
        rslidar_launch = IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(rslidar_share, 'launch', 'start.py')
            )
        )
        ld.add_action(rslidar_launch)
    
    # BNO055 IMU Setup
    if accessories_config.get('bno055', {}).get('ros__parameters', {}).get('active', False):
        bno055_node = Node(
            package = 'bno055',
            name = 'bno055',
            executable = 'bno055',
            parameters = [accessories_config_path],
            remappings=[
                ('/imu', '/imu/data')
            ])
        
        # Add BNO055 IMU to launch description
        ld.add_action(bno055_node)

    # 3. ZED 2i Stereo Camera Setup
    if accessories_config.get('zed2i', {}).get('ros__parameters', {}).get('active', False):
        zed_launch = IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(zed_share, 'launch', 'zed_camera.launch.py')
            ),
            launch_arguments={
                'camera_model': 'zed2i',
                'camera_name': 'camera',
                'config_path': str(zed_config_path)
            }.items()
        )
        ld.add_action(zed_launch)

    return ld

