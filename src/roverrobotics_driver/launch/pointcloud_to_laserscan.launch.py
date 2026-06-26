import math
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    
    # Custom parameter tuning for the RoboSense Airy on the Rover chassis
    updated_params = {
        # CRITICAL: Projecting the data onto base_link automatically flattens 
        # out your lidar's physical 22-degree forward tilt!
        "target_frame": "base_footprint",
        
        "transform_tolerance": 0.3,
        
        # Slicing Window (in meters relative to base_link):
        # Your lidar sits at z = 0.195m. The top of your rover chassis is roughly at z = 0.125m.
        # This narrow window captures obstacles safely above the frame but below the sky.
        "min_height": 0.15,  
        "max_height": 50.0,  
        
        # Full 360 field of view coverage
        "angle_min": -math.pi,  # -3.14159
        "angle_max": math.pi,   # 3.14159
        
        # RS Airy Horizontal Resolution: ~0.2 degrees at 10Hz
        # 0.2 * (math.pi / 180.0) = ~0.00349065 rad
        "angle_increment": 0.00349065,
        
        # Lidar rotation frequency (10Hz = 0.1s spin cycle)
        "scan_time": 0.1,
        
        # Minimum range must clear your chassis outer box boundaries (approx 0.25m from center)
        "range_min": 0.3,  
        # change max range to be accurate (max range according to website is 60m)
        "range_max": 60.0,  # Reliable structural range for indoor/outdoor mapping
        
        "use_inf": True,
        "inf_epsilon": 1.0,
        "concurrency_level": 1,
    }

    return LaunchDescription([
        Node(
            package="pointcloud_to_laserscan",
            executable="pointcloud_to_laserscan_node",
            name="pointcloud_to_laserscan",
            output="screen",
            emulate_tty=True,
            arguments=[
                "--ros-args",
                "--log-level",
                "INFO",
            ],
            # REMAPPINGS CONFIGURATION:
            # Matches your config.yaml output topic and standardizes it to /scan for SLAM Toolbox
            remappings=[
                ("cloud_in", "/rslidar_points"),
                ("scan", "/scan")
            ],
            parameters=[updated_params],
        )
    ])