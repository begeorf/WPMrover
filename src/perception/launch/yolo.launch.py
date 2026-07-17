import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    engine_path_arg = DeclareLaunchArgument(
        'engine_path',
        default_value='/home/rover/rover_workspace/yolo11n.engine',
        description='Absolute path to the compiled YOLO TensorRT .engine file'
    )

    classes_arg = DeclareLaunchArgument(
        'classes',
        default_value='[0, 56, 57]',  # Detect persons, chairs, sofas
        description='List of COCO class IDs to filter'
    )

    yolo_node = Node(
        package='perception',
        executable='yolo_depth_node',
        name='yolo_depth_node',
        output='screen',
        emulate_tty=True,
        parameters=[{
            'engine_path': LaunchConfiguration('engine_path'),
            'debug_view': False,
            'confidence_threshold': 0.5,
        }]
    )

    return LaunchDescription([
        engine_path_arg,
        yolo_node
    ])