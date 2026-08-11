import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction, LogInfo
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():

    # --------------------------------------------------------------------------
    # 1. Package Share Directories
    # --------------------------------------------------------------------------
    roverrobotics_share = get_package_share_directory('roverrobotics_driver')
    theta_share = get_package_share_directory('theta_driver')
    perception_share = get_package_share_directory('perception')

    # --------------------------------------------------------------------------
    # 2. Launch File Paths
    # --------------------------------------------------------------------------
    zero_launch_path = os.path.join(
        roverrobotics_share, 'launch', 'zero.launch.py'
    )
    nav_launch_path = os.path.join(
        roverrobotics_share, 'launch', 'navigation_launch.py'
    )
    theta_launch_path = os.path.join(
        theta_share, 'launch', 'theta.launch.py'
    )
    yolo_launch_path = os.path.join(
        perception_share, 'launch', 'yolo.launch.py'
    )

    # --------------------------------------------------------------------------
    # 3. Subsystem Descriptions with Staggered Delays (5s increments)
    # --------------------------------------------------------------------------

    # T = 0s: Base Robot Hardware Driver
    stage_1_zero_driver = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(zero_launch_path)
    )

    # T = 5s: Navigation Stack
    stage_2_navigation = TimerAction(
        period=5.0,
        actions=[
            LogInfo(msg="[Orchestrator] T+5s: Launching Navigation Stack..."),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(nav_launch_path)
            ),
        ],
    )

    # T = 10s: Theta 360 Camera Driver
    stage_3_theta_camera = TimerAction(
        period=10.0,
        actions=[
            LogInfo(
                msg="[Orchestrator] T+10s: Launching Theta Camera Driver..."
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(theta_launch_path)
            ),
        ],
    )

    # T = 15s: YOLO Perception Node
    stage_4_yolo_perception = TimerAction(
        period=15.0,
        actions=[
            LogInfo(
                msg="[Orchestrator] T+15s: Launching YOLO Perception Pipeline..."
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(yolo_launch_path)
            ),
        ],
    )

    # --------------------------------------------------------------------------
    # 4. Return Launch Description
    # --------------------------------------------------------------------------
    return LaunchDescription([
        LogInfo(msg="[Orchestrator] Starting Rover Master Staggered Bringup..."),
        stage_1_zero_driver,
        stage_2_navigation,
        stage_3_theta_camera,
        stage_4_yolo_perception,
    ])