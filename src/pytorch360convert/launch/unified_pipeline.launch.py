from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        # 1. Standard Linux Joy Driver
        Node(
            package='joy_linux',
            executable='joy_linux_node',
            name='joy_linux_node',
            output='screen',
            parameters=[{'deadzone': 0.05}]
        ),
        # 2. PS4 Controller Trigger Mapper
        Node(
            package='pytorch360convert',
            executable='ps4_trigger_node',
            name='ps4_trigger_node',
            output='screen'
        ),
        # 3. Theta Camera Hardware Driver
        Node(
            package='pytorch360convert',
            executable='theta_driver_node',
            name='theta_driver_node',
            output='screen'
        ),
        # 4. PyTorch CUDA Cubemap Converter
        Node(
            package='pytorch360convert',
            executable='cubemap_converter_node',
            name='cubemap_converter_node',
            output='screen'
        ),
    ])