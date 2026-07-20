import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    # Locate configuration file path
    config_path = os.path.join(
        get_package_share_directory('theta_driver'),
        'config',
        'theta_params.yaml'
    )

    # Launch the driver component as a standalone node
    theta_driver_node = Node(
        package='theta_driver',
        executable='theta_driver_node', # Make sure this matches your CMake entry point name
        name='theta_driver',
        output='screen',
        parameters=[config_path]
    )

    return LaunchDescription([theta_driver_node])