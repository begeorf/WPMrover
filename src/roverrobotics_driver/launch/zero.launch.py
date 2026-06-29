import os

from ament_index_python.packages import get_package_share_directory
from ament_index_python.packages import get_package_share_path
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():

    # Paths
    rover_path = get_package_share_path('roverrobotics_description')
    default_model_path = os.path.join(rover_path, 'urdf', 'rover_4wd.urdf')
    driver_share = get_package_share_directory('roverrobotics_driver')
    hardware_config = os.path.join(driver_share, 'config', 'zero_config.yaml')

    # Read URDF into memory for robot_state_publisher
    with open(default_model_path, 'r') as infp:
        robot_desc = infp.read()

    # PS4 controller launch
    controller_launch_path = os.path.join(driver_share, 'launch', 'ps4_controller.launch.py')
    ps4_controller_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(controller_launch_path))

    # EKF (robot_localization) — sole publisher of odom -> base_footprint
    ekf_launch_path = os.path.join(driver_share, 'launch', 'robot_localizer.launch.py')
    robot_localizer_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(ekf_launch_path))

    # Accessories (LiDAR, IMU, ZED camera)
    accessories_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(driver_share, 'launch', 'accessories.launch.py')))

    # Rover chassis driver — publishes /odometry/wheels topic only (publish_tf: false in config)
    robot_driver = Node(
        package='roverrobotics_driver',
        name='roverrobotics_driver',
        executable='roverrobotics_driver',
        parameters=[hardware_config],
        output='screen',
        respawn=True,
        respawn_delay=1
    )

    joint_state_publisher_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher'
    )

    # URDF publisher — publishes static TFs for base_footprint -> base_link -> sensors
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_desc}]
    )

    ld = LaunchDescription()
    ld.add_action(robot_driver)
    ld.add_action(accessories_launch)
    ld.add_action(joint_state_publisher_node)
    ld.add_action(robot_state_publisher_node)
    ld.add_action(robot_localizer_launch)
    ld.add_action(ps4_controller_launch)

    return ld