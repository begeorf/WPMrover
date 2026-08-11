#!/usr/bin/env python3

import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable  # <-- Added SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.actions import DeclareLaunchArgument
from launch.actions import LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch.actions import TimerAction
from math import pi
import yaml

def generate_launch_description():
    ld = LaunchDescription()

    # --- CUDA Environment Configuration ---
    # Enforces CUDA 12.6 paths for ZED SDK and GPU-accelerated nodes
    cuda_path = '/usr/local/cuda-12.6'
    ld.add_action(SetEnvironmentVariable('CUDA_HOME', cuda_path))
    ld.add_action(SetEnvironmentVariable(
        'PATH', 
        f"{cuda_path}/bin:" + os.environ.get('PATH', '')
    ))
    # Includes Jetson GPU driver paths (/usr/lib/aarch64-linux-gnu/nvidia) for libsl_zed.so
    ld.add_action(SetEnvironmentVariable(
        'LD_LIBRARY_PATH', 
        f"{cuda_path}/lib64:/usr/lib/aarch64-linux-gnu/nvidia:" + os.environ.get('LD_LIBRARY_PATH', '')
    ))

    # Locate package directories
    driver_share = get_package_share_directory('roverrobotics_driver')
    zed_wrapper_share = get_package_share_directory('zed_wrapper')
    rslidar_share = get_package_share_directory('rslidar_sdk') # Find RoboSense Share

    zed_config_common = os.path.join(zed_wrapper_share, 'config', 'common_stereo.yaml')
    zed_config_camera = os.path.join(zed_wrapper_share, 'config', 'zed2i.yaml')

    accessories_config_path = Path(driver_share, 'config/accessories.yaml')

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
    
    # 2. BNO055 IMU Setup
    if accessories_config.get('bno055', {}).get('ros__parameters', {}).get('active', False):
        bno055_node = Node(
            package = 'bno055',
            name = 'bno055',
            executable = 'bno055',
            parameters = [accessories_config_path],
            remappings=[
                ('/imu', '/imu/data')
            ],
            respawn = True,
            respawn_delay = 2.0
        )
        
        # Add BNO055 IMU to launch description
        bno055_delayed_launch = TimerAction(
            period = 3.0,
            actions = [bno055_node]
        )
        ld.add_action(bno055_delayed_launch)

    # 3. ZED 2i Stereo Camera Setup (Minimal Compute Profile)
    if accessories_config.get('zed2i', {}).get('ros__parameters', {}).get('active', False):
        
        zed_launch = IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(zed_wrapper_share, 'launch', 'zed_camera.launch.py')
            ),
            launch_arguments={
                'camera_model': 'zed2i',
                'camera_name': 'camera',
                'publish_tf': 'false',      # don't publish odom -> camera_camera_link: would fight the EKF over odom
                'publish_map_tf': 'false',  # ignored once publish_tf is false, but kept explicit
                'publish_imu_tf': 'false',  # disables IMU TF generation from ZED
                'config_path': os.path.join(zed_wrapper_share, 'config'),
            }.items()
        )
        delayed_zed_launch = TimerAction(
            period=5.0,
            actions=[zed_launch]
        )
        ld.add_action(delayed_zed_launch)

    return ld