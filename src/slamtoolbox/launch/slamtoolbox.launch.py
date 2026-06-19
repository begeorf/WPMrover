import os
from pathlib import Path
from ament_index_python.packages import get_package_share_directory, get_package_share_path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node, ComposableNodeContainer
from launch_ros.descriptions import ComposableNode


def generate_launch_description():
    # ==========================================
    # 1. PACKAGE PATHS & PARAMETER DEFINITIONS
    # ==========================================
    slam_toolbox_pkg = get_package_share_directory("slamtoolbox")
    rslidar_pkg = get_package_share_directory('rslidar_sdk')
    # zed_wrapper_pkg = get_package_share_directory('zed_wrapper')
    zero_description_pkg = get_package_share_directory('roverrobotics_description')

    # === MODIFICATION 1: Get driver package directory and define controller launch path ===
    rover_driver_pkg = get_package_share_directory('roverrobotics_driver')
    controller_launch_path = os.path.join(rover_driver_pkg, 'launch', 'ps4_controller.launch.py') # Match your actual launch filename if different
    ps4_controller_launch = IncludeLaunchDescription(PythonLaunchDescriptionSource(controller_launch_path))
    
    # Configuration Files
    slam_config_file = os.path.join(slam_toolbox_pkg, "config", "slamtoolbox_params.yaml")
    
    # Locate and read the true URDF description from roverrobotics_description
    rover_path = get_package_share_path('roverrobotics_description')
    default_model_path = os.path.join(rover_path, 'urdf', 'rover_4wd.urdf')
    with open(default_model_path, 'r') as infp:
        robot_desc = infp.read()
    
    rslidar_launch_path = os.path.join(rslidar_pkg, "launch", "start.py")
    # zero_static_launch_path = os.path.join(zero_description_pkg, "")

    # Include rslidar driver launch
    rslidar_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(rslidar_launch_path), launch_arguments={}.items()
    )

    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_desc,
            'use_sim_time': False
        }]
    )

    # NEED write odometry/wheels to odom package

    # use tf2 transform from odom to base link
    # test before slam: move with controller
    # odom should stay the same but base link should move

    rover_driver_node = Node(
        package='roverrobotics_driver',
        executable='roverrobotics_driver', # verify this name matches your package executable if it differs
        name='roverrobotics_driver',
        output='screen',
        parameters=[{
            'use_sim_time': False,
            'robot_type': 'zero2',                # Sets the controller mapping (usually 'pro' or '4wd')
            'device_port': '/dev/rover',         # Maps to your physical USB-to-Serial port rule
            'comm_type': 'serial',               # Tells the driver to stream over serial protocol
            'odom_frame': 'odom',
            'base_link_frame': 'base_footprint',
            # these are intended to fix the tf fighting issues
            'publish_tf': True,                  # <-- ADD THIS LINE: Stops driver from fighting ZED over TF
            'publish_odom': True
        }]
    )

    pointcloud_to_laserscan_node = Node(
        package='pointcloud_to_laserscan',
        executable='pointcloud_to_laserscan_node',
        name='pointcloud_to_laserscan',
        output='screen',
        parameters=[{
            'target_frame': 'base_footprint',
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
            'use_sim_time': False, #this should be set to true when looking at data in post, false when collecting data
            'qos_reliability': 2 # 1 = Reliable QoS profile to match slam_toolbox, 2 = best effort
        }],
        remappings=[
            ('cloud_in', '/rslidar_points'),
            ('scan', '/scan')
        ],
        # ros_args=['--param', 'qos_reliability:=reliable']
    )

    # SLAM toolbox node
    slam_toolbox_node = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[slam_config_file],
    )

    ld = LaunchDescription()

    ld.add_action(slam_toolbox_node)
    # ld.add_action(robot_state_publisher_node)
    # ld.add_action(rover_driver_node)

    # === MODIFICATION 2: Add the controller launch action to the tree ===
    ld.add_action(ps4_controller_launch)

    # delayed_lidar_driver = TimerAction(
    #     period=5.0,
    #     actions=[rslidar_launch],
    # )
    # ld.add_action(delayed_lidar_driver)

    delayed_pointcloud_to_laserscan = TimerAction(
        period=10.0,
        actions=[pointcloud_to_laserscan_node]
    )
    ld.add_action(delayed_pointcloud_to_laserscan)

    return ld

if __name__ == "__main__": 
    generate_launch_description()
