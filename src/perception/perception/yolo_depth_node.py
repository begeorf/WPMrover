#!/usr/bin/env python3
import ast  # Added to safely parse string representations of lists
from collections import defaultdict, deque
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import rclpy
import torch
from cv_bridge import CvBridge

# Foxglove Imports
from foxglove_msgs.msg import Color, ImageAnnotations, Point2, PointsAnnotation, TextAnnotation
from message_filters import ApproximateTimeSynchronizer, Subscriber
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image, CompressedImage
from ultralytics import YOLO
from vision_msgs.msg import Detection3D, Detection3DArray, ObjectHypothesisWithPose, ObjectHypothesis


class YoloDepthNode(Node):
    """ROS2 node that fuses RealSense RGB and depth images to produce 3D object detections.

    Runs YOLOv8 TensorRT inference on the colour stream, estimates per-detection depth
    using a robust ROI-median strategy, back-projects detections into 3D camera space,
    and publishes vision_msgs/Detection3DArray together with optional Foxglove image
    annotations. Temporal smoothing is applied to both depth and 3D position estimates
    to reduce jitter.
    """

    def __init__(self) -> None:
        super().__init__("yolo_depth_node")

        # --- Parameters ---
        self.declare_parameter("debug_view", False)
        # engine_path: required — must be set at launch; no default since the compiled engine
        # is deployment-specific (architecture and TensorRT version dependent).
        self.declare_parameter("engine_path", "")
        self.declare_parameter("device", "cuda:0")
        self.declare_parameter("confidence_threshold", 0.5)
        self.declare_parameter("depth_buffer_size", 5)
        self.declare_parameter("max_depth_change_ratio", 0.15)
        self.declare_parameter("position_history_size", 3)
        self.declare_parameter("roi_size", 15)
        self.declare_parameter("min_depth_samples", 5)
        self.declare_parameter("depth_percentile", 25)
        self.declare_parameter("object_key_grid_size", 50)
        self.declare_parameter("classes", "[0]") # Default to person

        self.debug_view = self.get_parameter("debug_view").get_parameter_value().bool_value
        self.device = self.get_parameter("device").get_parameter_value().string_value
        self.confidence_threshold = (
            self.get_parameter("confidence_threshold").get_parameter_value().double_value
        )

        # --- Temporal Smoothing Parameters ---
        self.depth_buffer_size = (
            self.get_parameter("depth_buffer_size").get_parameter_value().integer_value
        )
        self.max_depth_change_ratio = (
            self.get_parameter("max_depth_change_ratio").get_parameter_value().double_value
        )
        self.roi_size = self.get_parameter("roi_size").get_parameter_value().integer_value
        self.min_depth_samples = (
            self.get_parameter("min_depth_samples").get_parameter_value().integer_value
        )
        self.depth_percentile = (
            self.get_parameter("depth_percentile").get_parameter_value().integer_value
        )
        self.object_key_grid_size = (
            self.get_parameter("object_key_grid_size").get_parameter_value().integer_value
        )
        self.depth_history = defaultdict(lambda: deque(maxlen=self.depth_buffer_size))
        self.position_history = defaultdict(
            lambda: deque(
                maxlen=self.get_parameter("position_history_size")
                .get_parameter_value()
                .integer_value
            )
        )
        self.last_seen = {}
        
        # --- FPS PROFILING ---
        self.frame_count = 0
        self.start_time = None

        # --- ROS Setup ---
        self.bridge = CvBridge()
        self.intrinsics_matrix = None
        self.fx = self.fy = self.cx = self.cy = 0.0

        # ZED Camera Info Topic Fix
        self.sub_info = self.create_subscription(
            CameraInfo, "/camera/zed_node/rgb/color/rect/image/camera_info", self.info_callback, qos_profile_sensor_data
        )

        # Change these to match your ZED 2i topics:
        self.rgb_sub = Subscriber(self, CompressedImage, "/camera/zed_node/rgb/color/rect/image/compressed", qos_profile=qos_profile_sensor_data)
        self.depth_sub = Subscriber(self, Image, "/camera/zed_node/depth/depth_registered", qos_profile=qos_profile_sensor_data)
        
        # FIX: Increased slop from 0.1 to 0.3 to prevent dropping mismatched frames
        self.sync = ApproximateTimeSynchronizer(
            [self.rgb_sub, self.depth_sub], queue_size=10, slop=0.3
        )
        self.sync.registerCallback(self.image_cb)

        # Internal State (For Object Mapper)
        self.det_pub = self.create_publisher(Detection3DArray, "/yolo/internal_state", 10)
        
        # FIX: Changed path to match ZED's namespace environment structure
        # self.annot_pub = self.create_publisher(ImageAnnotations, "/camera/zed_node/rgb/color/rect/image/annotations", 10)
        self.annot_pub = self.create_publisher(ImageAnnotations, "/yolo/image_annotations", 10)

        # --- YOLO Setup ---
        engine_path_str = self.get_parameter("engine_path").get_parameter_value().string_value
        if not engine_path_str:
            raise RuntimeError(
                "Parameter 'engine_path' must be set at launch to the compiled .engine file path."
            )
        engine_path = Path(engine_path_str)

        if engine_path.exists():
            self.get_logger().info(f"Loading optimized TensorRT Engine from: {engine_path}")
            self.model = YOLO(str(engine_path))
        else:
            self.get_logger().warn(
                f"Engine not found at {engine_path}. Using standard .pt (Slower)"
            )
            self.model = YOLO("yolov8n.pt")
            if torch.cuda.is_available():
                self.model.to(self.device)

        self.names = self.model.names

        # Dynamic Classes Mapping
        self.target_classes = set()
        raw_classes = self.get_parameter("classes").get_parameter_value().string_value
        try:
            parsed_list = ast.literal_eval(raw_classes)
            if isinstance(parsed_list, list):
                self.target_classes = set(int(x) for x in parsed_list)
            else:
                self.target_classes = {int(parsed_list)}
        except Exception as e:
            self.get_logger().error(f"Failed to parse 'classes' parameter: {e}")
            self.target_classes = {0}

        self.get_logger().info(f"Yolo Depth Node Started. Filtered Classes: {self.target_classes}")

    def info_callback(self, msg: CameraInfo) -> None:
        """Cache camera intrinsic parameters on first receipt."""
        if self.intrinsics_matrix is None:
            self.fx = msg.k[0]
            self.fy = msg.k[4]
            self.cx = msg.k[2]
            self.cy = msg.k[5]
            self.intrinsics_matrix = True
            # for debugging 
            # self.get_logger().info(f"🎉 SUCCESS: Camera intrinsics cached! fx: {self.fx}, fy: {self.fy}")

    def get_improved_depth(
        self,
        depth_frame_mm: np.ndarray,
        cx_pixel: int,
        cy_pixel: int,
        bbox: tuple,
    ) -> Optional[float]:
        """Estimate robust object depth using an ROI median with outlier rejection."""
        x1, y1, x2, y2 = bbox

        roi = depth_frame_mm[
            max(cy_pixel - self.roi_size, 0) : min(
                cy_pixel + self.roi_size, depth_frame_mm.shape[0]
            ),
            max(cx_pixel - self.roi_size, 0) : min(
                cx_pixel + self.roi_size, depth_frame_mm.shape[1]
            ),
        ]

        valid_depths_mm = roi[roi > 0]
        if valid_depths_mm.size < self.min_depth_samples:
            return None

        valid_depths_m = valid_depths_mm.astype(np.float32) / 1000.0

        mean_depth = np.mean(valid_depths_m)
        std_depth = np.std(valid_depths_m)

        if std_depth > 0:
            filtered_depths = valid_depths_m[np.abs(valid_depths_m - mean_depth) < 2 * std_depth]
        else:
            filtered_depths = valid_depths_m

        if filtered_depths.size < 3:
            return None
        return float(np.percentile(filtered_depths, self.depth_percentile))

    def smooth_depth_temporal(
        self, object_key: str, raw_depth: float, current_time: float
    ) -> float:
        """Apply exponential weighted averaging and rate-limiting to raw depth estimates."""
        self.last_seen[object_key] = current_time
        self.depth_history[object_key].append(raw_depth)
        history = list(self.depth_history[object_key])

        if len(history) == 1:
            return raw_depth

        weights = np.exp(np.linspace(-1, 0, len(history)))
        weights /= weights.sum()
        smoothed_depth = float(np.average(history, weights=weights))

        if len(history) > 1:
            prev_depth = history[-2]
            max_change = self.max_depth_change_ratio * prev_depth
            depth_change = smoothed_depth - prev_depth
            if abs(depth_change) > max_change:
                smoothed_depth = prev_depth + np.sign(depth_change) * max_change
        return smoothed_depth

    def smooth_position_temporal(self, object_key: str, position: np.ndarray) -> np.ndarray:
        """Apply a sliding window mean to 3D object position estimates."""
        self.position_history[object_key].append(position)
        history = np.array(list(self.position_history[object_key]))
        if len(history) == 1:
            return position
        return np.mean(history, axis=0)

    def cleanup_old_objects(self, current_time: float, timeout: float = 2.0) -> None:
        """Remove tracking history for objects not seen within the timeout window."""
        objects_to_remove = [k for k, v in self.last_seen.items() if current_time - v > timeout]
        for key in objects_to_remove:
            if key in self.depth_history:
                del self.depth_history[key]
            if key in self.position_history:
                del self.position_history[key]
            del self.last_seen[key]

    def image_cb(self, rgb_msg: CompressedImage, depth_msg: Image) -> None:
        """Run YOLO inference and publish 3D detections with optional Foxglove annotations."""

        # --- CALCULATE REAL-WORLD THROUGHPUT ---
        if self.start_time is None:
            self.start_time = self.get_clock().now()
        
        self.frame_count += 1
        elapsed_time = (self.get_clock().now() - self.start_time).nanoseconds / 1e9
        
        if elapsed_time >= 5.0:
            fps = self.frame_count / elapsed_time
            self.get_logger().info(f"📊 PERFORMANCE PROFILER: Processing at {fps:.2f} FPS over the last {elapsed_time:.1f}s")
            self.frame_count = 0
            self.start_time = self.get_clock().now()

        # LOG MARKER 1: The callback triggered! (Both messages arrived and matched timestamps)
        # self.get_logger().info("🎯 CALLBACK TRIGGERED: Received synchronized RGB and Depth frames!", throttle_duration_sec=2.0)

        if not self.intrinsics_matrix:
            # for debugging
            # self.get_logger().warn("⚠️ DROPPING FRAME: Waiting for CameraInfo /intrinsics...", throttle_duration_sec=2.0)
            return

        # if (
        #     not self.debug_view
        #     and self.det_pub.get_subscription_count() == 0
        #     and self.annot_pub.get_subscription_count() == 0
        # ):
        #     self.get_logger().warn("No publishers or subscribers, Returning...", throttle_duration_sec=5.0)
        #     return

        current_time = rgb_msg.header.stamp.sec + rgb_msg.header.stamp.nanosec * 1e-9

        try:
            rgb_arr = self.bridge.compressed_imgmsg_to_cv2(rgb_msg, "bgr8")
            depth_arr_mm = self.bridge.imgmsg_to_cv2(depth_msg, "passthrough")
            # LOG MARKER 2: ROS to OpenCV conversion was successful
            # self.get_logger().info(f"📸 Images decoded successfully. RGB Shape: {rgb_arr.shape}, Depth Dtype: {depth_arr_mm.dtype}", throttle_duration_sec=5.0)
        except Exception as e:
            # self.get_logger().error(f"❌ Image conversion failed: {e}", throttle_duration_sec=5.0)
            # self.get_logger().warn(f"Image conversion failed: {e}", throttle_duration_sec=5.0)
            return

        # LOG MARKER 3: Sending to GPU for TensorRT inference
        # self.get_logger().info("🧠 Running YOLO TensorRT inference...", throttle_duration_sec=5.0)
        results = self.model(
            rgb_arr, verbose=False, device=self.device, conf=self.confidence_threshold
        )[0]

        # --- SSH DEBUG PRINT ---
        if len(results.boxes) > 0:
            self.get_logger().info(f"YOLO detected {len(results.boxes)} objects! Class IDs: {[int(b.cls[0]) for b in results.boxes]}")
            pass
        else:
            self.get_logger().info("YOLO running but found 0 objects in this frame.", throttle_duration_sec=2.0)

        det_msg = Detection3DArray()
        det_msg.header = rgb_msg.header

        should_publish_foxglove = (not self.debug_view) and (
            self.annot_pub.get_subscription_count() > 0
        )
        annot_msg = ImageAnnotations() if should_publish_foxglove else None

        red_color = Color(r=1.0, g=0.0, b=0.0, a=1.0)
        white_color = Color(r=1.0, g=1.0, b=1.0, a=1.0)
        red_bg = Color(r=1.0, g=0.0, b=0.0, a=0.5)

        for box in results.boxes:
            cls_id = int(box.cls[0])

            if cls_id not in self.target_classes:
                continue

            conf = float(box.conf)
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            label = self.names[cls_id]

            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            raw_depth = self.get_improved_depth(depth_arr_mm, cx, cy, (x1, y1, x2, y2))

            if raw_depth is None:
                continue

            object_key = (
                f"{label}_{cx // self.object_key_grid_size}_{cy // self.object_key_grid_size}"
            )
            smoothed_depth = self.smooth_depth_temporal(object_key, raw_depth, current_time)

            x_cam = (cx - self.cx) * smoothed_depth / self.fx
            y_cam = (cy - self.cy) * smoothed_depth / self.fy
            raw_pos = np.array([x_cam, y_cam, smoothed_depth])

            smooth_pos = self.smooth_position_temporal(object_key, raw_pos)

            w_pixels = x2 - x1
            h_pixels = y2 - y1
            real_w = (w_pixels * smoothed_depth) / self.fx
            real_h = (h_pixels * smoothed_depth) / self.fy

            det = Detection3D()
            det.header = rgb_msg.header
            # old ros2 jazzy version det.results.append(ObjectHypothesisWithPose(id=label, score=conf))
            # updated humble version of hypothesis making 
            hyp_pose = ObjectHypothesisWithPose()
            hyp_pose.hypothesis.class_id = str(label)
            hyp_pose.hypothesis.score = float(conf)
            det.results.append(hyp_pose)
            det.bbox.center.position.x = float(smooth_pos[0])
            det.bbox.center.position.y = float(smooth_pos[1])
            det.bbox.center.position.z = float(smooth_pos[2])
            det.bbox.size.x = real_w
            det.bbox.size.y = real_h
            det.bbox.size.z = real_w

            det_msg.detections.append(det)

            if should_publish_foxglove:
                rect = PointsAnnotation()
                rect.timestamp = rgb_msg.header.stamp
                rect.type = PointsAnnotation.LINE_LOOP
                rect.thickness = 3.0
                rect.outline_color = red_color
                rect.fill_color = Color(r=0.0, g=0.0, b=0.0, a=0.0)
                rect.points = [
                    Point2(x=float(x1), y=float(y1)),
                    Point2(x=float(x2), y=float(y1)),
                    Point2(x=float(x2), y=float(y2)),
                    Point2(x=float(x1), y=float(y2)),
                ]
                annot_msg.points.append(rect)

                txt = TextAnnotation()
                txt.timestamp = rgb_msg.header.stamp
                txt.position = Point2(x=float(x1), y=float(y1) - 10)
                txt.text = f"{label} ({smoothed_depth:.1f} m)"
                txt.font_size = 18.0
                txt.text_color = white_color
                txt.background_color = red_bg
                annot_msg.texts.append(txt)

            if self.debug_view:
                cv2.rectangle(rgb_arr, (x1, y1), (x2, y2), (0, 255, 0), 2)
                text = f"{label} raw:{raw_depth:.2f}m | smooth:{smoothed_depth:.2f}m"
                cv2.putText(
                    rgb_arr, text, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1
                )

        self.det_pub.publish(det_msg)

        if should_publish_foxglove:
            self.annot_pub.publish(annot_msg)

        if self.debug_view:
            cv2.imshow("YOLO 3D - Moving Average", rgb_arr)
            cv2.waitKey(1)

        self.cleanup_old_objects(current_time)


def main(args: Optional[list] = None) -> None:
    rclpy.init(args=args)
    node = YoloDepthNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()