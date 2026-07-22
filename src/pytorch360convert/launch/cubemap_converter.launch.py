import os
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='pytorch360convert',
            executable='cubemap_converter_node',
            name='cubemap_converter_node',
            output='screen',
            # Re-map topics here if needed in the future
            remappings=[
                # ('/image_snapshot', '/my_camera/image_raw'),
            ],
            parameters=[
                # Future parameters like face_w can be passed here
            ]
        )
    ])