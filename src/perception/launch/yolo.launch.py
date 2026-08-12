import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    snapshot_manager_config_path = os.path.join(
        get_package_share_directory('perception'),
        'config',
        'snapshot_manager_params.yaml'
    )

    engine_path_arg = DeclareLaunchArgument(
        'engine_path',
        # default_value='/home/rover/rover_workspace/src/perception/models/nano/ConcreteModel1_YOLO_nano.engine',
        default_value='/home/rover/rover_workspace/src/perception/models/small/ConcreteModel1_YOLO_small.engine',
        description='Absolute path to the compiled YOLO TensorRT .engine file'
    )

    classes_arg = DeclareLaunchArgument(
        'classes',
        default_value="'[1]'",  # Detect Cracking
        description='List of COCO class IDs to filter'
    )

     # --- Object Mapper Node Arguments ---
    map_save_path_arg = DeclareLaunchArgument(
        'map_save_path',
        default_value='semantic_map.json',
        description='Path to save/load the persisted JSON semantic map'
    )

    match_dist_thresh_arg = DeclareLaunchArgument(
        'match_dist_thresh',
        default_value='0.5',
        description='Distance threshold in meters for data association matching'
    )

    save_interval_arg = DeclareLaunchArgument(
        'save_interval',
        default_value='5.0',
        description='Interval in seconds between atomic map JSON disk writes'
    )

    # --- Snapshot Manager Node Arguments ---
    snapshot_density_distance_arg = DeclareLaunchArgument(
        'snapshot_density_distance',
        default_value='1.0',
        description='Minimum distance in meters to the nearest existing snapshot before a new one is triggered'
    )

    yolo_node = Node(
        package='perception',
        executable='yolo_depth_node',
        name='yolo_depth_node',
        output='screen',
        emulate_tty=True,
        parameters=[{
            'engine_path': LaunchConfiguration('engine_path'),
            'classes': LaunchConfiguration('classes'),
            'debug_view': False,
            'confidence_threshold': 0.35,
        }]
    )

    object_mapper_node = Node(
        package='perception',
        executable='object_mapper_node',
        name='object_mapper_node',
        output='screen',
        emulate_tty=True,
        parameters=[{
            'debug_view': False,
            'map_save_path': LaunchConfiguration('map_save_path'),
            'match_dist_thresh': LaunchConfiguration('match_dist_thresh'),
            'save_interval': LaunchConfiguration('save_interval'),
            'position_alpha': 0.8,
        }]
    )

    snapshot_manager_node = Node(
        package='perception',
        executable='snapshot_manager_node',
        name='snapshot_manager',
        output='screen',
        emulate_tty=True,
        parameters=[
            snapshot_manager_config_path,
            {'snapshot_density_distance': LaunchConfiguration('snapshot_density_distance')},
        ]
    )

    return LaunchDescription([
        engine_path_arg,
        classes_arg,
        map_save_path_arg,
        match_dist_thresh_arg,
        save_interval_arg,
        snapshot_density_distance_arg,
        yolo_node,
        object_mapper_node,
        snapshot_manager_node,
    ])