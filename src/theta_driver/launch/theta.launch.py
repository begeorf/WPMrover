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

    # PointCloud Converter Node
    equirect_cloud_node = Node(
        package='theta_driver',
        executable='equirect_to_cloud_node',
        name='equirect_to_cloud',
        output='screen',
        parameters=[{
            'radius': 5.0,
            'downsample_factor': 2
        }]
    )

    ld = LaunchDescription()
    ld.add_action(theta_driver_node)
    # ld.add_action(equirect_cloud_node)

    return ld