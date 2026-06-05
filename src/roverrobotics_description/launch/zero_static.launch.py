import launch_ros.descriptions
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import Command, FindExecutable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    declared_arguments = [
        DeclareLaunchArgument("description_package", default_value="roverrobotics_description"),
        DeclareLaunchArgument("description_file", default_value="rover.urdf.xacro"),
        DeclareLaunchArgument("prefix", default_value=""),
        DeclareLaunchArgument("use_sim_time", default_value="false"),
        DeclareLaunchArgument("rviz", default_value="false"),
    ]

    description_package = LaunchConfiguration("description_package")
    description_file = LaunchConfiguration("description_file")
    prefix = LaunchConfiguration("prefix")
    use_sim_time = LaunchConfiguration("use_sim_time")
    rviz = LaunchConfiguration("rviz")

    robot_description_content = Command(
        [
            PathJoinSubstitution([FindExecutable(name="xacro")]),
            " ",
            PathJoinSubstitution([FindPackageShare(description_package), "urdf", description_file]),
            " ",
            "prefix:=",
            prefix,
        ]
    )
    robot_description = launch_ros.descriptions.ParameterValue(
        robot_description_content, value_type=str
    )

    rviz_config_path = PathJoinSubstitution(
        [FindPackageShare(description_package), "config", "go2_description.rviz"]
    )

    common_params = [{"robot_description": robot_description, "use_sim_time": use_sim_time}]

    robot_state_pub = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="screen",
        parameters=common_params + [{"publish_frequency": 100.0}],
    )

    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        output="screen",
        arguments=["-d", rviz_config_path],
        parameters=common_params,
        condition=IfCondition(rviz),
    )

    return LaunchDescription(declared_arguments + [robot_state_pub, rviz_node])
