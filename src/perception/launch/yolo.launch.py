import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    engine_path_arg = DeclareLaunchArgument(
        'engine_path',
        default_value='/home/rover/rover_workspace/src/perception/models/nano/ConcreteModel1_YOLO_nano.engine',
        # default_value='/home/rover/rover_workspace/src/perception/models/nano/ConcreteModel1_YOLO_small.engine',
        description='Absolute path to the compiled YOLO TensorRT .engine file'
    )

    classes_arg = DeclareLaunchArgument(
        'classes',
        default_value="'[1]'",  # Detect Cracking
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
            'classes': LaunchConfiguration('classes'),
            'debug_view': False,
            'confidence_threshold': 0.35,
        }]
    )

    return LaunchDescription([
        engine_path_arg, 
        classes_arg,
        yolo_node
    ])