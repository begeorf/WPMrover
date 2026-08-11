#!/usr/bin/env python3
import json
import math
import os
import sys
from typing import Optional

# Pre-flight debug print (triggers upon script load/import)
print("[DEBUG OBJECT_MAPPER] Script file loaded successfully!", file=sys.stderr)

import rclpy
import tf2_geometry_msgs

# OUTPUT MESSAGES
from foxglove_msgs.msg import Color, CubePrimitive, SceneEntity, SceneUpdate, TextPrimitive
from geometry_msgs.msg import PointStamped, Vector3
from rclpy.node import Node

# TF2 Imports
from tf2_ros import TransformException
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener
from vision_msgs.msg import Detection3DArray
from visualization_msgs.msg import Marker, MarkerArray


class ObjectMapper(Node):
    def __init__(self) -> None:
        super().__init__("object_mapper")

        self.get_logger().info("==========================================")
        self.get_logger().info("Initializing ObjectMapper Node...")
        self.get_logger().info("==========================================")

        # --- PARAMETERS ---
        self.declare_parameter("debug_view", False)
        self.declare_parameter("map_save_path", "semantic_map.json")
        self.declare_parameter("match_dist_thresh", 0.5)
        self.declare_parameter("save_interval", 5.0)
        self.declare_parameter("position_alpha", 0.8)

        self.debug_view = self.get_parameter("debug_view").get_parameter_value().bool_value
        self.map_file = self.get_parameter("map_save_path").get_parameter_value().string_value
        self.match_dist_thresh = (
            self.get_parameter("match_dist_thresh").get_parameter_value().double_value
        )
        self.save_interval = self.get_parameter("save_interval").get_parameter_value().double_value
        self.position_alpha = (
            self.get_parameter("position_alpha").get_parameter_value().double_value
        )

        self.get_logger().info(f"Loaded Param - debug_view: {self.debug_view}")
        self.get_logger().info(f"Loaded Param - map_save_path: {self.map_file}")
        self.get_logger().info(f"Loaded Param - match_dist_thresh: {self.match_dist_thresh}")

        # --- STATE ---
        self.objects = []
        self.next_obj_id = 0
        self.load_map()  # Load existing data from JSON

        # --- 1Hz BUFFER (The Mailbox) ---
        self.latest_msg = None

        # --- ROS SETUP ---
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # NOTE: Updated to use FAST callback
        self.sub = self.create_subscription(
            Detection3DArray, "/yolo/internal_state", self.fast_callback, 10
        )
        self.get_logger().info("Subscribed to: /yolo/internal_state")

        # --- PUBLISHERS ---
        self.scene_pub = self.create_publisher(SceneUpdate, "/visual_scene", 10)

        if self.debug_view:
            self.marker_pub = self.create_publisher(MarkerArray, "/visual_markers", 10)
            self.get_logger().info("MODE: DEBUG VIEW (Publishing /visual_markers + JSON Saving)")
        else:
            self.get_logger().info("MODE: FOXGLOVE OPTIMIZED (SceneUpdate Only)")

        # --- TIMERS ---
        # 1. Visualization Timer (Keep independent to ensure markers don't flicker)
        self.create_timer(1.0, self.publish_visualization)

        # 2. Storage Timer
        self.create_timer(self.save_interval, self.save_map)

        # 3. Processing Timer (The new 1Hz Logic Loop)
        self.create_timer(1.0, self.slow_processing_loop)

        self.get_logger().info("ObjectMapper Node initialized and timers running.")

    def load_map(self) -> None:
        """Load previously saved objects from the JSON map file if it exists."""
        if os.path.exists(self.map_file):
            try:
                with open(self.map_file, "r") as f:
                    self.objects = json.load(f)

                max_id = -1
                for obj in self.objects:
                    if obj["id"] > max_id:
                        max_id = obj["id"]
                self.next_obj_id = max_id + 1

                self.get_logger().info(f"Loaded {len(self.objects)} objects from disk.")
            except Exception as e:
                self.get_logger().warn(f"Failed to load map: {e}")

    def save_map(self) -> None:
        """Persist the current object list to JSON using an atomic write."""
        tmp_path = self.map_file + ".tmp"
        try:
            with open(tmp_path, "w") as f:
                json.dump(self.objects, f, indent=4)
            os.replace(tmp_path, self.map_file)
        except Exception as e:
            self.get_logger().error(f"Failed to save map: {e}")

    def fast_callback(self, msg: Detection3DArray) -> None:
        """Buffer the latest detection message for processing at 1 Hz."""
        self.latest_msg = msg

    def slow_processing_loop(self) -> None:
        """Process buffered detections at 1 Hz: transform to map frame and update object list."""
        # 1. Check mailbox
        if self.latest_msg is None:
            return

        # Take the message and clear the mailbox
        msg = self.latest_msg
        self.latest_msg = None

        if not msg.detections:
            return

        try:
            # Transform from Camera Frame -> Map Frame
            # We use rclpy.time.Time() to get the latest available transform
            transform = self.tf_buffer.lookup_transform(
                "map", msg.header.frame_id, rclpy.time.Time()
            )
        except TransformException as e:
            self.get_logger().warn(f"TF lookup failed: {e}", throttle_duration_sec=5.0)
            return

        for det in msg.detections:
            # Extract label accounting for ROS 2 Humble vision_msgs changes
            if hasattr(det.results[0], "hypothesis"):
                label = det.results[0].hypothesis.class_id
            else:
                label = str(det.results[0].id)

            # 1. Transform Point to Map Frame
            point_camera = PointStamped()
            point_camera.point = det.bbox.center.position

            try:
                point_map = tf2_geometry_msgs.do_transform_point(point_camera, transform)
            except Exception as e:
                self.get_logger().warn(f"Failed to transform detection: {e}")
                continue

            x, y, z = point_map.point.x, point_map.point.y, point_map.point.z

            # Dimensions
            sx = det.bbox.size.z if det.bbox.size.z > 0.05 else 0.1
            sy = det.bbox.size.x
            sz = det.bbox.size.y

            # 2. Data Association (Your Original Logic)
            match_found = False
            for obj in self.objects:
                dx = obj["x"] - x
                dy = obj["y"] - y
                dist = math.sqrt(dx * dx + dy * dy)

                if obj["label"] == label and dist < self.match_dist_thresh:
                    # Update Position (Weighted Average)
                    alpha = self.position_alpha
                    obj["x"] = alpha * obj["x"] + (1.0 - alpha) * x
                    obj["y"] = alpha * obj["y"] + (1.0 - alpha) * y
                    obj["z"] = alpha * obj["z"] + (1.0 - alpha) * z

                    # Update dimensions (Max hold)
                    obj["sx"] = max(obj.get("sx", 0.1), sx)
                    obj["sy"] = max(obj.get("sy", 0.1), sy)
                    obj["sz"] = max(obj.get("sz", 0.1), sz)

                    match_found = True
                    break

            # 3. Create New Object
            if not match_found:
                new_obj = {
                    "id": self.next_obj_id,
                    "label": label,
                    "x": x,
                    "y": y,
                    "z": z,
                    "sx": sx,
                    "sy": sy,
                    "sz": sz,
                }
                self.objects.append(new_obj)
                self.next_obj_id += 1
                if self.debug_view:
                    self.get_logger().info(f"Registered new {label} at ({x:.2f}, {y:.2f})")

    def publish_visualization(self) -> None:
        """Publish Foxglove SceneUpdate and optional RViz MarkerArray for all tracked objects.

        When debug_view is enabled, also publishes a MarkerArray to /visual_markers.
        """
        if not self.objects:
            return

        # --- 1. FOXGLOVE SCENE UPDATE (Always Published) ---
        scene_msg = SceneUpdate()
        green_color = Color(r=0.0, g=1.0, b=0.0, a=0.6)
        white_color = Color(r=1.0, g=1.0, b=1.0, a=1.0)

        for obj in self.objects:
            entity = SceneEntity()
            entity.frame_id = "map"
            entity.timestamp = self.get_clock().now().to_msg()
            # Convert Integer ID to String for Foxglove
            entity.id = str(obj["id"])
            entity.lifetime.sec = 2
            entity.frame_locked = True

            # Cube
            cube = CubePrimitive()
            cube.pose.position.x = obj["x"]
            cube.pose.position.y = obj["y"]
            cube.pose.position.z = obj["z"]
            cube.size = Vector3(
                x=float(obj.get("sx", 0.1)),
                y=float(obj.get("sy", 0.1)),
                z=float(obj.get("sz", 0.1)),
            )
            cube.color = green_color
            entity.cubes.append(cube)

            # Text
            text = TextPrimitive()
            text.billboard = True
            text.pose.position.x = obj["x"]
            text.pose.position.y = obj["y"]
            text.pose.position.z = obj["z"] + float(obj.get("sz", 0.1)) / 2 + 0.2
            text.text = obj["label"]
            text.font_size = 20.0
            text.scale_invariant = True
            text.color = white_color
            entity.texts.append(text)

            scene_msg.entities.append(entity)

        self.scene_pub.publish(scene_msg)

        # --- 2. RVIZ MARKER ARRAY (Only if Debug View) ---
        if self.debug_view:
            marker_array = MarkerArray()

            for obj in self.objects:
                # Shape Marker
                marker = Marker()
                marker.header.frame_id = "map"
                marker.header.stamp = self.get_clock().now().to_msg()
                marker.ns = "objects"
                marker.id = obj["id"]
                marker.type = Marker.CUBE
                marker.action = Marker.ADD
                marker.pose.position.x = obj["x"]
                marker.pose.position.y = obj["y"]
                marker.pose.position.z = obj["z"]
                marker.pose.orientation.w = 1.0
                marker.scale.x = obj.get("sx", 0.1)
                marker.scale.y = obj.get("sy", 0.1)
                marker.scale.z = obj.get("sz", 0.1)
                marker.color.r = 0.0
                marker.color.g = 1.0
                marker.color.b = 0.0
                marker.color.a = 0.6
                marker.lifetime = rclpy.duration.Duration(seconds=2.0).to_msg()
                marker_array.markers.append(marker)

                # Text Marker
                text_marker = Marker()
                text_marker.header = marker.header
                text_marker.ns = "text"
                text_marker.id = obj["id"] + 10000
                text_marker.type = Marker.TEXT_VIEW_FACING
                text_marker.action = Marker.ADD
                text_marker.text = obj["label"]
                text_marker.pose.position.x = obj["x"]
                text_marker.pose.position.y = obj["y"]
                text_marker.pose.position.z = obj["z"] + (marker.scale.z / 2) + 0.2
                text_marker.scale.z = 0.2
                text_marker.color.r = 1.0
                text_marker.color.g = 0.0
                text_marker.color.b = 0.0
                text_marker.color.a = 1.0
                text_marker.lifetime = marker.lifetime
                marker_array.markers.append(text_marker)

            self.marker_pub.publish(marker_array)


def main(args: Optional[list] = None) -> None:
    print("[DEBUG MAIN] main() entrypoint reached!", file=sys.stderr)
    rclpy.init(args=args)
    node = ObjectMapper()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.save_map()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()