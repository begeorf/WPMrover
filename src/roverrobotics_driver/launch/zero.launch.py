from pathlib import Path
import os

from ament_index_python.packages import get_package_share_directory
from ament_index_python.packages import get_package_share_path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
import xacro


def generate_launch_description():
    
    # model_arg = DeclareLaunchArgument(name='model', default_value=str(default_model_path),
    #                                   description='Absolute path to robot urdf file')
    # robot_description = ParameterValue(Command(['xacro ', LaunchConfiguration('model')]),
    #                                    value_type=str)
    # xacro_file = os.path.join(
    #     os.path.expanduser('~'), 
    #     'rover_workspace/src/rover_description/urdf/rover.urdf.xacro'
    # )
    # Pinpoint the static URDF file
    rover_path = get_package_share_path('roverrobotics_description')
    default_model_path = os.path.join(rover_path, 'urdf', 'rover_4wd.urdf')
    
    # READ the actual XML file content into memory so ROS can parse it
    with open(default_model_path, 'r') as infp:
        robot_desc = infp.read()
    
    # # 2. Compile the Xacro file to a URDF string entirely in memory
    # robot_description_xml = xacro.process_file(xacro_file).toxml()
   
    # hardware_config = Path(get_package_share_directory(
    #     'roverrobotics_driver'), 'config', 'zero_config.yaml')
    # assert hardware_config.is_file()
    driver_share = get_package_share_directory('roverrobotics_driver')
    hardware_config = os.path.join(driver_share, 'config', 'zero_config.yaml')

    controller_launch_path = os.path.join(driver_share, 'launch', 'ps4_controller.launch.py') # Match your actual launch filename if different
    ps4_controller_launch = IncludeLaunchDescription(PythonLaunchDescriptionSource(controller_launch_path))

    ld = LaunchDescription()

    robot_driver = Node(
        package = 'roverrobotics_driver',
        name = 'roverrobotics_driver',
        executable = 'roverrobotics_driver',
        parameters = [hardware_config],
        output='screen',
        respawn=True,
        respawn_delay=1
    )

    accessories_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([get_package_share_directory('roverrobotics_driver'), '/launch/accessories.launch.py']),
    )
   
    joint_state_publisher_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher'
    )

    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_desc}]
    )

    # 1. Bridge the Odometry tree to the robot base
    # (Maps camera_camera_center output back down to base_footprint)
    odom_to_footprint_bridge = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='camera_to_footprint',
        arguments=['0', '0', '-0.2', '0', '0', '0', 'camera_camera_center', 'base_footprint']
    )
    
    # === ADDED THIS NODE TO BRIDGE BASE_FOOTPRINT AND BASE_LINK ===
    base_footprint_bridge_node = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='base_footprint_to_base_link',
        arguments=['0', '0', '0', '0', '0', '0', 'base_footprint', 'base_link']
    )

    # # 3. Mount the Lidar to base_link (using your earlier measured translation/rotation offsets)
    # baselink_to_rslidar_bridge = Node(
    #     package='tf2_ros',
    #     executable='static_transform_publisher',
    #     name='baselink_to_rslidar',
    #     arguments=['0.000', '0.044', '0.268', '0.000', '0.384', '0.000', 'base_link', 'rslidar']
    # )

    # # 4. Mount the IMU to base_link
    # baselink_to_bno055_bridge = Node(
    #     package='tf2_ros',
    #     executable='static_transform_publisher',
    #     name='baselink_to_bno055',
    #     arguments=['0', '0', '0.05', '0', '0', '0', 'base_link', 'bno055']
    # )

    # # 5. Connect isolated camera_link frame to the main physical tree
    # baselink_to_cameralink_bridge = Node(
    #     package='tf2_ros',
    #     executable='static_transform_publisher',
    #     name='baselink_to_cameralink',
    #     arguments=['0.1', '0', '0.2', '0', '0', '0', 'base_link', 'camera_link']
    # )

    # RViz Visualizer Node
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen'
    )
    
    # ld.add_action(model_arg)
    ld.add_action(robot_driver)
    ld.add_action(accessories_launch)
    ld.add_action(joint_state_publisher_node)
    ld.add_action(robot_state_publisher_node)
    ld.add_action(base_footprint_bridge_node)
    ld.add_action(odom_to_footprint_bridge)
    # === MODIFICATION 2: Add the controller launch action to the tree ===
    ld.add_action(ps4_controller_launch)
    # ld.add_action(baselink_to_rslidar_bridge)
    # ld.add_action(baselink_to_bno055_bridge)
    # ld.add_action(baselink_to_cameralink_bridge)
    # ld.add_action(rviz_node)
   
    return ld
