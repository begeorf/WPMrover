#!/usr/bin/env python3
import math
from typing import Optional

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy, DurabilityPolicy
from sensor_msgs.msg import LaserScan, PointCloud2

# TF2 Imports for transforming tilted data
from tf2_ros import TransformException
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener
import tf2_geometry_msgs 

class SimpleCloudToScan(Node):
    def __init__(self) -> None:
        super().__init__("simple_cloud_to_scan")

        # Target frame should be the flat base of the vehicle
        self.declare_parameter("target_frame", "base_footprint")
        
        # Slicing Window: Now relative to the ground/base_link!
        # If your LiDAR sits 30cm off the ground, a window of 0.2 to 0.4 
        # captures a clean slice 10cm above and below the sensor parallel to the earth.
        
        # chassis is 7.2mm from the ground, setting this to -0.5 makes the lidar not scan anything between 0mm and 1.2mm
        self.declare_parameter("min_height", -0.05)
        # change this to have a relevant max height, maybe about table height (depending if we want to go above/below tables)
        self.declare_parameter("max_height", 0.26)  
        
        self.declare_parameter("range_min", 0.4)   
        self.declare_parameter("range_max", 30.0)  
        self.declare_parameter("scan_time", 0.1)   
        self.declare_parameter("angle_increment", 0.00698132)

        self.target_frame = self.get_parameter("target_frame").get_parameter_value().string_value
        self.min_height = self.get_parameter("min_height").get_parameter_value().double_value
        self.max_height = self.get_parameter("max_height").get_parameter_value().double_value
        self.range_min = self.get_parameter("range_min").get_parameter_value().double_value
        self.range_max = self.get_parameter("range_max").get_parameter_value().double_value
        self.scan_time = self.get_parameter("scan_time").get_parameter_value().double_value
        self.angle_increment = self.get_parameter("angle_increment").get_parameter_value().double_value
        
        self.angle_min = -math.pi/4
        self.angle_max = math.pi/4  

        # Initialize TF Listener to dynamically read the LiDAR's tilt angle
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # Diagnostic counters
        self._msgs_received = 0
        self._scans_published = 0
        self._skipped_height_filter = 0

        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,    
            history=HistoryPolicy.KEEP_LAST,           
            depth=5,
            durability=DurabilityPolicy.VOLATILE       
        )

        self.subscription = self.create_subscription(
            PointCloud2,
            "rslidar_points",  
            self.listener_callback,
            sensor_qos,
        )

        self.publisher = self.create_publisher(LaserScan, "scan", sensor_qos)

    def listener_callback(self, msg: PointCloud2) -> None:
        self._msgs_received += 1
        if msg.width == 0 or msg.height == 0:
            return

        # Parse raw cloud bytes
        dtype_list = [("x", np.float32), ("y", np.float32), ("z", np.float32)]
        if msg.point_step > 12:
            dtype_list.append(("padding", "V", msg.point_step - 12))
        raw_data = np.frombuffer(msg.data, dtype=dtype_list)

        x = raw_data["x"]
        y = raw_data["y"]
        z = raw_data["z"]

        # --- DYNAMIC TF FLATTENING CORRECTION ---
        try:
            # Look up how the sensor frame (rslidar) is positioned relative to our flat floor frame (base_link)
            transform = self.tf_buffer.lookup_transform(
                self.target_frame,
                msg.header.frame_id,
                rclpy.time.Time()
            )
            
            # Extract translation offsets
            tx = transform.transform.translation.x
            ty = transform.transform.translation.y
            tz = transform.transform.translation.z
            
            # Extract rotation quaternion
            qx = transform.transform.rotation.x
            qy = transform.transform.rotation.y
            qz = transform.transform.rotation.z
            qw = transform.transform.rotation.w
            
            # Convert quaternion into a rotation matrix to mathematically un-tilt the cloud
            r11 = 1 - 2*(qy**2 + qz**2)
            r12 = 2*(qx*qy - qz*qw)
            r13 = 2*(qx*qz + qy*qw)
            r21 = 2*(qx*qy + qz*qw)
            r22 = 1 - 2*(qx**2 + qz**2)
            r23 = 2*(qy*qz - qx*qw)
            r31 = 2*(qx*qz - qy*qw)
            r32 = 2*(qy*qz + qx*qw)
            r33 = 1 - 2*(qx**2 + qy**2)
            
            # Project the tilted coordinates onto a mathematically flat ground plane
            x_flat = r11 * x + r12 * y + r13 * z + tx
            y_flat = r21 * x + r22 * y + r23 * z + ty
            z_flat = r31 * x + r32 * y + r33 * z + tz
            
        except TransformException as ex:
            self.get_logger().warning(f"Could not flatten cloud: {ex}", throttle_duration_sec=5.0)
            return

        # Slice the newly flattened data points
        height_mask = (z_flat > self.min_height) & (z_flat < self.max_height)
        x_eval = x_flat[height_mask]
        y_eval = y_flat[height_mask]

        if x_eval.size == 0:
            self._skipped_height_filter += 1
            return

        # Range and Angle calculations
        ranges = np.hypot(x_eval, y_eval)
        angles = np.arctan2(y_eval, x_eval)

        range_mask = (ranges > self.range_min) & (ranges < self.range_max)
        ranges = ranges[range_mask]
        angles = angles[range_mask]

        if ranges.size == 0:
            return

        # Binning
        num_readings = round((self.angle_max - self.angle_min) / self.angle_increment)
        scan_ranges = np.full(num_readings, float("inf"), dtype=np.float32)

        indices = ((angles - self.angle_min) / self.angle_increment).astype(int)
        idx_mask = (indices >= 0) & (indices < num_readings)
        indices = indices[idx_mask]
        ranges = ranges[idx_mask]

        np.minimum.at(scan_ranges, indices, ranges)

        # Build LaserScan
        scan = LaserScan()
        scan.header = msg.header
        scan.header.frame_id = self.target_frame  # Crucial: Output is now tracking base_link
        scan.angle_min = self.angle_min
        scan.angle_max = self.angle_max
        scan.angle_increment = self.angle_increment
        scan.time_increment = 0.0
        scan.scan_time = self.scan_time
        scan.range_min = self.range_min
        scan.range_max = self.range_max
        scan.ranges = scan_ranges.tolist()

        self.publisher.publish(scan)
        self._scans_published += 1

# Change your main function at the bottom of the file to this:
from rclpy.executors import MultiThreadedExecutor

def main(args: Optional[list] = None) -> None:
    rclpy.init(args=args)
    node = SimpleCloudToScan()
    
    # Use a MultiThreadedExecutor to safely process TF lookups and callbacks simultaneously
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()