import os
from ament_index_python.packages import get_package_share_directory, get_package_share_path
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    slam_toolbox_pkg = get_package_share_directory("slam_toolbox")
    
    # Locate your robot's URDF description so robot_state_publisher can map frames
    rover_path = get_package_share_path('roverrobotics_description')
    default_model_path = os.path.join(rover_path, 'urdf', 'rover_4wd.urdf')
    with open(default_model_path, 'r') as infp:
        robot_desc = infp.read()

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')

    # 1. Robot State Publisher to handle the URDF structure matching the bag clock
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_desc,
            'use_sim_time': use_sim_time
        }]
    )

    # 2. Convert raw recorded point clouds into laser scans on the fly
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
            'use_sim_time': use_sim_time,
            'qos_reliability': 2 # Matches your reliable bag file /rslidar_points recording
        }],
        remappings=[
            ('cloud_in', '/rslidar_points'),
            ('scan', '/scan')
        ]
    )

    # 3. Live SLAM Node listening to the playback data
    slam_toolbox_node = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[
            {'use_sim_time': use_sim_time},
            {'odom_frame': 'odom'},
            {'base_frame': 'base_link'}, 
            {'map_frame': 'map'},
            {'scan_topic': '/scan'},
            {'scan_queue_size': 10},
            {'qos_overrides./scan.subscriber.reliability': 'best_effort'}
        ],
    )

    # 4. Static transforms bridging the gaps not captured dynamically
    base_footprint_bridge = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='base_footprint_to_base_link',
        arguments=['0', '0', '0', '0', '0', '0', 'base_footprint', 'base_link'],
        parameters=[{'use_sim_time': use_sim_time}]
    )

    baselink_to_rslidar_bridge = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='baselink_to_rslidar',
        arguments=['0.000', '0.044', '0.268', '0.000', '0.384', '0.000', 'base_link', 'rslidar'],
        parameters=[{'use_sim_time': use_sim_time}]
    )

    # 5. RViz2 Node
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen'
    )

    # Bridge the gap because the bag only has odom -> camera_camera_link
    camera_to_baselink_bridge = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='camera_to_base_link',
        # Adjust these offsets if your camera isn't at the physical center
        arguments=['0', '0', '0', '0', '0', '0', 'camera_camera_link', 'base_footprint'],
        parameters=[{'use_sim_time': use_sim_time}]
    )

    ld = LaunchDescription()
    ld.add_action(robot_state_publisher_node)
    ld.add_action(pointcloud_to_laserscan_node)
    ld.add_action(slam_toolbox_node)
    ld.add_action(base_footprint_bridge)
    ld.add_action(baselink_to_rslidar_bridge)
    # ld.add_action(camera_to_baselink_bridge)
    ld.add_action(rviz_node)

    return ld