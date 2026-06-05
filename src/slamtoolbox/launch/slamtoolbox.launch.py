import os
from pathlib import Path
from ament_index_python.packages import get_package_share_directory, get_package_share_path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node, ComposableNodeContainer
from launch_ros.descriptions import ComposableNode

def generate_launch_description():
    # ==========================================
    # 1. PACKAGE PATHS & PARAMETER DEFINITIONS
    # ==========================================
    slam_toolbox_pkg = get_package_share_directory("slamtoolbox")
    driver_share = get_package_share_directory('roverrobotics_driver')
    # zed_wrapper_pkg = get_package_share_directory('zed_wrapper')
    rslidar_pkg = get_package_share_directory('rslidar_sdk')
    zero_description_pkg = get_package_share_directory('rover_description')
    
    # Configuration Files
    slam_config_file = os.path.join(slam_toolbox_pkg, "config", "slamtoolbox_params.yaml")
    hardware_config = os.path.join(driver_share, 'config', 'zero_config.yaml')
    
    # Locate and read the true URDF description from roverrobotics_description
    rover_path = get_package_share_path('roverrobotics_description')
    default_model_path = os.path.join(rover_path, 'urdf', 'rover_4wd.urdf')
    with open(default_model_path, 'r') as infp:
        robot_desc = infp.read()
    
    rslidar_launch_path = os.path.join(rslidar_pkg, "launch", "start.py")
    zero_static_launch_path = os.path.join(zero_description_pkg, "")

    # Include rslidar driver launch
    rslidar_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(rslidar_launch_path), launch_arguments={}.items()
    )

    # Include Zero static transforms launch
    zero_static_transforms_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(zero_static_launch_path), launch_arguments={}.items()
    )

    ld = LaunchDescription()

    # ==========================================
    # 2. CORE ROVER PLATFORM NODES
    # ==========================================
    robot_driver = Node(
        package='roverrobotics_driver',
        name='roverrobotics_driver',
        executable='roverrobotics_driver',
        parameters=[hardware_config, {
            'port': '/dev/rover-control',
            'baud_rate': 115200,
            'robot_type': 'zero2',
            'odom_frame': 'odom',
            'base_frame': 'base_footprint'
        }],
        output='screen',
        respawn=True,
        respawn_delay=1
    )

    joint_state_publisher_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        output='screen'
    )

    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_desc}],
        output='screen'
    )

    # ==========================================
    # 3. PERCEPTION PIPELINE (LiDAR Stream Processing)
    # ==========================================
    rslidar_node = Node(
        package='rslidar_sdk',
        executable='rslidar_sdk_node',
        name='rslidar_sdk_node',
        output='screen',
        parameters=[{
            'use_lidar_clock': False,
            'lidar_type': 'RSAIRY',
            'msop_port': 6699,
            'difop_port': 7788
        }]
    )

    pointcloud_to_laserscan_node = Node(
        package='pointcloud_to_laserscan',
        executable='pointcloud_to_laserscan_node',
        name='pointcloud_to_laserscan',
        output='screen',
        remappings=[
            ('cloud_in', '/rslidar_points'),
            ('scan', '/scan')
        ],
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
            'use_sim_time': False,
            'qos_reliability': 2  # FIXED: Switched from 1 (Reliable) to 2 (Best Effort) to match SLAM Engine & RViz
        }]
    )

    # BNO055 IMU Sensor Node
    bno055_node = Node(
        package='bno055',
        executable='bno055',
        name='bno055',
        output='screen',
        parameters=[{'uart_port': '/dev/ttyUSB0', 'frame_id': 'bno055'}]
    )

    # ==========================================
    # 4. COMPOSABLE CAMERA CONTAINER
    # ==========================================
    zed_container = ComposableNodeContainer(
        name='zed_container',
        namespace='camera',
        package='rclcpp_components',
        executable='component_container_isolated', # FIXED: Switched to isolated container to resolve class lookup failure
        composable_node_descriptions=[
            ComposableNode(
                package='zed_components',
                plugin='stereolabs::ZedCamera',
                name='zed_node',
                parameters=[
                    os.path.join(zed_wrapper_pkg, 'config', 'common_stereo.yaml'),
                    os.path.join(zed_wrapper_pkg, 'config', 'zed2i.yaml'),
                    {
                        'pos_tracking.pos_tracking_enabled': True,
                        'pos_tracking.publish_tf': False,       
                        'pos_tracking.publish_map_tf': False,   
                        'video.img_downsample_factor': 2.0,     
                        'depth.depth_mode': 'PERFORMANCE'       
                    }
                ]
            )
        ],
        output='screen'
    )

    # ==========================================
    # 5. STATIC SENSOR COORDINATE LIFTS
    # ==========================================
    footprint_to_link_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='footprint_to_link',
        arguments=['--x', '0.0', '--y', '0.0', '--z', '0.1', '--roll', '0.0', '--pitch', '0.0', '--yaw', '0.0', '--frame-id', 'base_footprint', '--child-frame-id', 'base_link']
    )

    lidar_static_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='base_link_to_laser',
        arguments=['--x', '0.15', '--y', '0.0', '--z', '0.4', '--roll', '0.0', '--pitch', '0.0', '--yaw', '0.0', '--frame-id', 'base_link', '--child-frame-id', 'rslidar']
    )

    imu_static_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='base_link_to_imu',
        arguments=['--x', '0.0', '--y', '0.0', '--z', '0.05', '--roll', '0.0', '--pitch', '0.0', '--yaw', '0.0', '--frame-id', 'base_link', '--child-frame-id', 'bno055']
    )

    camera_static_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='base_link_to_camera_pivot',
        arguments=['--x', '0.2', '--y', '0.0', '--z', '0.3', '--roll', '0.0', '--pitch', '0.0', '--yaw', '0.0', '--frame-id', 'base_link', '--child-frame-id', 'camera_camera_link']
    )

    # ==========================================
    # 6. MAPPING ENGINE & VISUALIZATION (SLAM Toolbox)
    # ==========================================
    slam_toolbox_node = Node(
        package="slam_toolbox",
        executable="async_slam_toolbox_node",
        name="slam_toolbox",
        output='screen',
        parameters=[slam_config_file],
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen'
    )

    # ==========================================
    # 7. ACTION PIPELINE REGISTRATION
    # ==========================================
    ld.add_action(robot_driver)
    ld.add_action(joint_state_publisher_node)
    ld.add_action(robot_state_publisher_node)
    ld.add_action(rslidar_node)
    ld.add_action(pointcloud_to_laserscan_node)
    ld.add_action(bno055_node)
    ld.add_action(zed_container)
    ld.add_action(footprint_to_link_tf)
    ld.add_action(lidar_static_tf)
    ld.add_action(imu_static_tf)
    ld.add_action(camera_static_tf)
    ld.add_action(slam_toolbox_node)
    ld.add_action(rviz_node)
   
    return ld