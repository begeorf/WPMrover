#!/usr/bin/env python3
import os
import time
import cv2
import gphoto2 as gp

import rclpy
from rclpy.node import Node
from std_msgs.msg import Empty
from sensor_msgs.msg import Image
from cv_bridge import CvBridge


class ThetaDriverNode(Node):

    def __init__(self):
        super().__init__('theta_driver_node')

        self.bridge = CvBridge()
        self.is_capturing = False

        self.workspace_dir = os.path.expanduser('~/rover_workspace')
        self.save_path = os.path.join(self.workspace_dir, 'original_snapshot.png')

        # Publisher for raw equirectangular image
        self.image_pub = self.create_publisher(Image, '/camera/image_raw', 10)

        # Subscriber for PS4 trigger
        self.trigger_sub = self.create_subscription(
            Empty,
            '/camera/trigger_snap',
            self.trigger_callback,
            10
        )

        # Initialize persistent libgphoto2 session
        self.gp_camera = None
        self.gp_context = None
        self._init_camera_session()
        self._configure_hardware_auto_mode()

        self.get_logger().info('====================================================')
        self.get_logger().info(' [INIT] Theta Driver Node (Full Auto + Correct RGB)')
        self.get_logger().info(' [INIT] Subscribed to: /camera/trigger_snap')
        self.get_logger().info(' [INIT] Output Publisher: /camera/image_raw (rgb8)')
        self.get_logger().info(f' [INIT] Output Path: {self.save_path}')
        self.get_logger().info('====================================================')

    def _init_camera_session(self):
        try:
            self.gp_context = gp.Context()
            self.gp_camera = gp.Camera()
            self.gp_camera.init(self.gp_context)
            self.get_logger().info('✅ [GPHOTO2] Persistent camera session established successfully!')
        except gp.GPhoto2Error as e:
            self.get_logger().error(f'❌ [GPHOTO2 INIT ERROR] Failed to connect to camera: {e}')

    def _configure_hardware_auto_mode(self):
        """Forces hardware exposure and white balance back to full Auto in camera NVRAM."""
        if not self.gp_camera:
            return
        try:
            config = self.gp_camera.get_config(self.gp_context)

            # 1. Reset Exposure Program to Auto
            try:
                exp_widget = config.get_child_by_name('expprogram')
                try:
                    auto_exp = exp_widget.get_choice(2)
                except Exception:
                    auto_exp = 'Auto'
                exp_widget.set_value(auto_exp)
                self.get_logger().info(f'⚙️ [CONFIG] Exposure Program -> {auto_exp}')
            except Exception as e:
                self.get_logger().warn(f'⚠️ [CONFIG] Could not set Exposure Program: {e}')

            # 2. Force White Balance back to Automatic
            try:
                wb_widget = config.get_child_by_name('whitebalance')
                try:
                    auto_wb = wb_widget.get_choice(0)
                except Exception:
                    auto_wb = 'Automatic'
                wb_widget.set_value(auto_wb)
                self.get_logger().info(f'🎨 [CONFIG] White Balance -> {auto_wb}')
            except Exception as e:
                self.get_logger().warn(f'⚠️ [CONFIG] Could not set White Balance: {e}')

            # Push config back to camera
            self.gp_camera.set_config(config, self.gp_context)

        except gp.GPhoto2Error as e:
            self.get_logger().warn(f'⚠️ [CONFIG WARN] Could not apply auto mode hardware settings: {e}')

    def trigger_callback(self, msg: Empty):
        if self.is_capturing:
            self.get_logger().warn('[BUSY] Capture requested, but camera is currently processing!')
            return

        if not self.gp_camera:
            self.get_logger().error('❌ [ERROR] Camera session not available. Attempting reconnect...')
            self._init_camera_session()
            self._configure_hardware_auto_mode()
            if not self.gp_camera:
                return

        self.is_capturing = True
        self.get_logger().info('📸 [TRIGGER RECEIVED] Firing trigger & fetching snapshot...')

        try:
            self.capture_and_publish()
        except Exception as e:
            self.get_logger().error(f'❌ [EXCEPTION] Capture failed: {str(e)}')
            # Reset camera session on failure
            if self.gp_camera:
                self.gp_camera.exit(self.gp_context)
                self.gp_camera = None
        finally:
            self.is_capturing = False

    def capture_and_publish(self):
        t_start = time.perf_counter()

        # Step 1: Trigger capture (Wait for internal exposure & stitching)
        t0 = time.perf_counter()
        file_path = self.gp_camera.capture(gp.GP_CAPTURE_IMAGE, self.gp_context)
        trigger_time = time.perf_counter() - t0

        # Step 2: Download directly to disk
        t0 = time.perf_counter()
        camera_file = gp.CameraFile()
        self.gp_camera.file_get(
            file_path.folder,
            file_path.name,
            gp.GP_FILE_TYPE_NORMAL,
            camera_file,
            self.gp_context
        )
        camera_file.save(self.save_path)
        download_time = time.perf_counter() - t0

        file_size_mb = os.path.getsize(self.save_path) / (1024 * 1024)

        # Step 3: Load into OpenCV & Convert BGR -> RGB
        t0 = time.perf_counter()
        bgr_img = cv2.imread(self.save_path)
        if bgr_img is None:
            self.get_logger().error(f'❌ [CV ERROR] Could not read file at {self.save_path}')
            return

        # Convert OpenCV BGR array to standard RGB array
        rgb_img = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2RGB)
        load_time_ms = (time.perf_counter() - t0) * 1000

        # Step 4: Publish RGB Image to ROS
        t0 = time.perf_counter()
        ros_msg = self.bridge.cv2_to_imgmsg(rgb_img, encoding='rgb8')
        ros_msg.header.stamp = self.get_clock().now().to_msg()
        ros_msg.header.frame_id = 'theta_camera'

        self.image_pub.publish(ros_msg)
        pub_time_ms = (time.perf_counter() - t0) * 1000

        total_time = time.perf_counter() - t_start

        # Performance breakdown
        h, w, _ = rgb_img.shape
        self.get_logger().info('====================================================')
        self.get_logger().info('📊 [PERSISTENT DRIVER BENCHMARK]')
        self.get_logger().info(f'   ├── 1. Trigger & Stitching        : {trigger_time:.3f}s')
        self.get_logger().info(f'   ├── 2. Transfer File ({file_size_mb:.2f} MB) : {download_time:.3f}s')
        self.get_logger().info(f'   ├── 3. OpenCV Load & BGR->RGB    : {load_time_ms:.2f} ms')
        self.get_logger().info(f'   ├── 4. ROS Image Publish (rgb8)   : {pub_time_ms:.2f} ms')
        self.get_logger().info(f'   └── 🏆 TOTAL CYCLE TIME           : {total_time:.3f}s')
        self.get_logger().info('====================================================')

    def destroy_node(self):
        if self.gp_camera:
            self.gp_camera.exit(self.gp_context)
            self.get_logger().info('Closed camera session.')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ThetaDriverNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()