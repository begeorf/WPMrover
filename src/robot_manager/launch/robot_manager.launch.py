from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    yolo_engine_path_arg = DeclareLaunchArgument(
        name="yolo_engine_path",
        default_value="/home/rover/rover_workspace/src/perception/models/small/ConcreteModel1_YOLO_small.engine",
        description="Absolute path to YOLO TensorRT engine file — required for start_navigation",
    )
    pcd_save_dir_arg = DeclareLaunchArgument(
        name="pcd_save_dir",
        default_value="~/maps/pointlio",
        description="Directory for Point-LIO PCD output",
    )

    robot_manager_node = Node(
        package="robot_manager",
        executable="robot_manager_node",
        name="robot_manager",
        output="screen",
        parameters=[
            {
                "yolo_engine_path": LaunchConfiguration("yolo_engine_path"),
                "pcd_save_dir": LaunchConfiguration("pcd_save_dir"),
            }
        ],
    )

    foxglove_bridge_node = Node(
            package="foxglove_bridge",
            executable="foxglove_bridge",  # Note: executable is 'foxglove_bridge', not 'foxglove_bridge_node'
            name="foxglove_bridge",
            parameters=[{
                "port": 8765,
                "address": "0.0.0.0",
                "send_buffer_limit": 10000000,
                "use_sim_time": False,
            }]
        )

    return LaunchDescription([
        yolo_engine_path_arg,
        pcd_save_dir_arg,
        robot_manager_node,
        foxglove_bridge_node
    ])
