#!/usr/bin/env python3
import math
from typing import Optional

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy, DurabilityPolicy
from sensor_msgs.msg import LaserScan, PointCloud2


class SimpleCloudToScan(Node):
    def __init__(self) -> None:
        super().__init__("simple_cloud_to_scan")

        # =========================================================================
        # ROBOSENSE AIRY HARDWARE PARAMETERS
        # =========================================================================
        # target_frame: Base frame used for height filtering.
        self.declare_parameter("target_frame", "base_link")
        
        # Slicing Height: Because the Airy points 90 degrees straight up, 
        # narrow this window tightly around the sensor height to isolate a flat 2D slice.
        self.declare_parameter("min_height", -0.05) 
        self.declare_parameter("max_height", 0.05)  
        
        # Outer bounds: Keep range_min just outside the physical edge of the Rover chassis.
        self.declare_parameter("range_min", 0.3)   
        self.declare_parameter("range_max", 30.0)  # Max solid distance mapping range
        
        # Scan frequency: RoboSense Airy runs at a stable 10Hz (0.1s frame period)
        self.declare_parameter("scan_time", 0.1)   
        
        # Angular resolution: RS Airy has a native horizontal resolution of 0.4 degrees
        # 0.4 * (math.pi / 180.0) = ~0.00698132 radians
        self.declare_parameter("angle_increment", 0.00698132)

        self.target_frame = self.get_parameter("target_frame").get_parameter_value().string_value
        self.min_height = self.get_parameter("min_height").get_parameter_value().double_value
        self.max_height = self.get_parameter("max_height").get_parameter_value().double_value
        self.range_min = self.get_parameter("range_min").get_parameter_value().double_value
        self.range_max = self.get_parameter("range_max").get_parameter_value().double_value
        self.scan_time = self.get_parameter("scan_time").get_parameter_value().double_value
        self.angle_increment = self.get_parameter("angle_increment").get_parameter_value().double_value
        
        # 360-degree horizontal sweep
        self.angle_min = -math.pi
        self.angle_max = math.pi

        # Diagnostic counters
        self._msgs_received = 0
        self._scans_published = 0
        self._skipped_empty_cloud = 0
        self._skipped_height_filter = 0
        self._skipped_range_filter = 0

        # ROS 2 Best Effort QoS (matches the rslidar_sdk driver stream output)
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE, 
            history=HistoryPolicy.KEEP_LAST, 
            depth=5,
            durability=DurabilityPolicy.VOLATILE
        )

        # SUBSCRIBER: Maps directly to the active topic published by rslidar_sdk
        self.subscription = self.create_subscription(
            PointCloud2,
            "rslidar_points",  # Fixed topic match to the RS Airy driver output stream
            self.listener_callback,
            sensor_qos,
        )

        # PUBLISHER: Emits standard 2D laser arrays for slam_toolbox / Nav2
        self.publisher = self.create_publisher(LaserScan, "scan", sensor_qos)

        # Performance summary every 30 seconds
        self.create_timer(30.0, self._log_stats)

        self.get_logger().info(
            f"RS Airy Cloud-to-Scan Node Active. "
            f"Slice Windows: [{self.min_height}m to {self.max_height}m] "
            f"Horizontal Resolution: 0.4 deg "
            f"Tracking Frame: {self.target_frame}"
        )

    def _log_stats(self) -> None:
        self.get_logger().info(
            f"[RS Airy Stats/30s] Rx_Clouds={self._msgs_received} "
            f"Tx_Scans={self._scans_published} "
            f"Filtered_Out: Empty={self._skipped_empty_cloud} "
            f"Height_Blinded={self._skipped_height_filter} "
            f"Range_Blinded={self._skipped_range_filter}"
        )
        self._msgs_received = 0
        self._scans_published = 0
        self._skipped_empty_cloud = 0
        self._skipped_height_filter = 0
        self._skipped_range_filter = 0

    def listener_callback(self, msg: PointCloud2) -> None:
        self._msgs_received += 1

        if msg.width == 0 or msg.height == 0:
            self._skipped_empty_cloud += 1
            return

        # 1. Direct parsing via byte array structure buffer
        # RS Airy encodes standard floating arrays for spatial structures
        dtype_list = [("x", np.float32), ("y", np.float32), ("z", np.float32)]

        if msg.point_step > 12:
            dtype_list.append(("padding", "V", msg.point_step - 12))

        raw_data = np.frombuffer(msg.data, dtype=dtype_list)

        x = raw_data["x"]
        y = raw_data["y"]
        z = raw_data["z"]

        # 2. Slice out a flat horizontal window to extract a 2D line
        height_mask = (z > self.min_height) & (z < self.max_height)
        x = x[height_mask]
        y = y[height_mask]

        if x.size == 0:
            self._skipped_height_filter += 1
            return

        # 3. Vectorized Range/Angle calculations
        ranges = np.hypot(x, y)
        angles = np.arctan2(y, x)

        # 4. Filter range limits
        range_mask = (ranges > self.range_min) & (ranges < self.range_max)
        ranges = ranges[range_mask]
        angles = angles[range_mask]

        if ranges.size == 0:
            self._skipped_range_filter += 1
            return

        # 5. Binning array setup
        num_readings = round((self.angle_max - self.angle_min) / self.angle_increment)
        scan_ranges = np.full(num_readings, float("inf"), dtype=np.float32)

        # 6. Map calculated angles into exact bucket indices
        indices = ((angles - self.angle_min) / self.angle_increment).astype(int)

        idx_mask = (indices >= 0) & (indices < num_readings)
        indices = indices[idx_mask]
        ranges = ranges[idx_mask]

        # Use fast numpy vectorized array minimization
        np.minimum.at(scan_ranges, indices, ranges)

        # 7. Package and Emit LaserScan
        scan = LaserScan()
        scan.header = msg.header
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


def main(args: Optional[list] = None) -> None:
    rclpy.init(args=args)
    node = SimpleCloudToScan()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()