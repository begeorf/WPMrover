#!/usr/bin/env python3
import math
from typing import Optional

import rclpy
from rclpy.node import Node

from std_srvs.srv import Trigger
from tf2_ros import TransformException
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener
from visualization_msgs.msg import Marker, MarkerArray


class SnapshotManager(Node):
    def __init__(self) -> None:
        super().__init__("snapshot_manager")

        self.get_logger().info("==========================================")
        self.get_logger().info("Initializing SnapshotManager Node...")
        self.get_logger().info("==========================================")

        # --- PARAMETERS ---
        self.declare_parameter("snapshot_density_distance", 1.0)
        self.declare_parameter("pose_check_frequency", 5.0)
        self.declare_parameter("map_frame", "map")
        self.declare_parameter("base_frame", "base_link")
        self.declare_parameter("publish_markers", True)
        self.declare_parameter("trigger_service_name", "/trigger_snapshot")

        self.snapshot_density_distance = (
            self.get_parameter("snapshot_density_distance").get_parameter_value().double_value
        )
        self.pose_check_frequency = (
            self.get_parameter("pose_check_frequency").get_parameter_value().double_value
        )
        self.map_frame = self.get_parameter("map_frame").get_parameter_value().string_value
        self.base_frame = self.get_parameter("base_frame").get_parameter_value().string_value
        self.publish_markers = (
            self.get_parameter("publish_markers").get_parameter_value().bool_value
        )
        trigger_service_name = (
            self.get_parameter("trigger_service_name").get_parameter_value().string_value
        )

        self.get_logger().info(
            f"Loaded Param - snapshot_density_distance: {self.snapshot_density_distance}"
        )
        self.get_logger().info(f"Loaded Param - pose_check_frequency: {self.pose_check_frequency}")
        self.get_logger().info(f"Loaded Param - map_frame: {self.map_frame}")
        self.get_logger().info(f"Loaded Param - base_frame: {self.base_frame}")
        self.get_logger().info(f"Loaded Param - publish_markers: {self.publish_markers}")
        self.get_logger().info(f"Loaded Param - trigger_service_name: {trigger_service_name}")

        # --- STATE ---
        self.snapshot_points = []  # list of (x, y)
        self.pending_point = None  # point awaiting service confirmation

        # --- ROS SETUP ---
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.trigger_client = self.create_client(Trigger, trigger_service_name)

        if self.publish_markers:
            self.marker_pub = self.create_publisher(MarkerArray, "/snapshot_markers", 10)

        # --- TIMERS ---
        self.create_timer(1.0 / self.pose_check_frequency, self.check_pose)

        self.get_logger().info("SnapshotManager Node initialized and timers running.")

    def check_pose(self) -> None:
        """Look up the robot pose in the map frame and trigger a snapshot if it is far
        enough from every previously accepted snapshot location."""
        if self.pending_point is not None:
            # Still waiting on a prior trigger call to resolve; avoid double-triggering.
            return

        try:
            transform = self.tf_buffer.lookup_transform(
                self.map_frame, self.base_frame, rclpy.time.Time()
            )
        except TransformException as e:
            self.get_logger().warn(f"TF lookup failed: {e}", throttle_duration_sec=5.0)
            return

        x = transform.transform.translation.x
        y = transform.transform.translation.y

        nearest_dist = self.nearest_distance(x, y)
        if nearest_dist is not None and nearest_dist <= self.snapshot_density_distance:
            return

        self.request_snapshot(x, y)

    def nearest_distance(self, x: float, y: float) -> Optional[float]:
        if not self.snapshot_points:
            return None
        return min(math.hypot(px - x, py - y) for px, py in self.snapshot_points)

    def request_snapshot(self, x: float, y: float) -> None:
        if not self.trigger_client.service_is_ready():
            self.get_logger().warn(
                "trigger_snapshot service not available", throttle_duration_sec=5.0
            )
            return

        self.pending_point = (x, y)
        future = self.trigger_client.call_async(Trigger.Request())
        future.add_done_callback(lambda f: self.handle_trigger_response(f, x, y))

    def handle_trigger_response(self, future, x: float, y: float) -> None:
        self.pending_point = None
        try:
            response = future.result()
        except Exception as e:
            self.get_logger().warn(f"trigger_snapshot call failed: {e}")
            return

        if not response.success:
            self.get_logger().warn(f"Snapshot request rejected: {response.message}")
            return

        self.snapshot_points.append((x, y))
        self.get_logger().info(f"Snapshot accepted at ({x:.2f}, {y:.2f})")
        if self.publish_markers:
            self.publish_visualization()

    def publish_visualization(self) -> None:
        marker_array = MarkerArray()
        cube_size = 0.2  # 20cm
        for i, (x, y) in enumerate(self.snapshot_points):
            marker = Marker()
            marker.header.frame_id = self.map_frame
            marker.header.stamp = self.get_clock().now().to_msg()
            marker.ns = "snapshots"
            marker.id = i
            marker.type = Marker.CUBE
            marker.action = Marker.ADD
            marker.pose.position.x = x
            marker.pose.position.y = y
            marker.pose.orientation.w = 1.0
            marker.scale.x = cube_size
            marker.scale.y = cube_size
            marker.scale.z = cube_size
            marker.color.r = 1.0
            marker.color.g = 0.0
            marker.color.b = 0.0
            marker.color.a = 0.9
            marker_array.markers.append(marker)

            text_marker = Marker()
            text_marker.header = marker.header
            text_marker.ns = "snapshot_labels"
            text_marker.id = i + 10000
            text_marker.type = Marker.TEXT_VIEW_FACING
            text_marker.action = Marker.ADD
            text_marker.text = str(i + 1)
            text_marker.pose.position.x = x
            text_marker.pose.position.y = y
            text_marker.pose.position.z = cube_size / 2 + 0.2
            text_marker.pose.orientation.w = 1.0
            text_marker.scale.z = 0.2
            text_marker.color.r = 1.0
            text_marker.color.g = 1.0
            text_marker.color.b = 1.0
            text_marker.color.a = 1.0
            marker_array.markers.append(text_marker)

        self.marker_pub.publish(marker_array)


def main(args: Optional[list] = None) -> None:
    rclpy.init(args=args)
    node = SnapshotManager()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
