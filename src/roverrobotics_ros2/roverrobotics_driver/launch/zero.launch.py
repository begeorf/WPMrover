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
    # ld.add_action(rviz_node)
   
    return ld
