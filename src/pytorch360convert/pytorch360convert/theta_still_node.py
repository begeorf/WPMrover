#!/usr/bin/env python3
import os
import time
import subprocess
import cv2

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy, Image
from cv_bridge import CvBridge


class ThetaStillNode(Node):

    def __init__(self):
        super().__init__('theta_still_node')

        self.bridge = CvBridge()

        # Workspace path for output high-res snapshot
        self.workspace_dir = os.path.expanduser('~/rover_workspace')
        self.save_path = os.path.join(self.workspace_dir, 'original_snapshot.png')

        # Button index configuration for PS4 Controller (Index 2 = Circle Button)
        self.declare_parameter('circle_button_idx', 2)
        self.circle_button_idx = self.get_parameter('circle_button_idx').value

        # Debounce/State tracking flags
        self.prev_button_state = 0
        self.is_capturing = False

        # Subscriber to Joy topic from joy_linux_node
        self.joy_sub = self.create_subscription(
            Joy,
            '/joy',
            self.joy_callback,
            10
        )

        # Publisher to send saved image to cubemap converter node
        self.image_pub = self.create_publisher(
            Image,
            '/image_snapshot',
            10
        )

        self.get_logger().info('====================================================')
        self.get_logger().info(' [INIT] Theta Still Node Initialized Successfully!')
        self.get_logger().info(' [INIT] Listening on topic: /joy')
        self.get_logger().info(' [INIT] Output image topic: /image_snapshot')
        self.get_logger().info(f' [INIT] Target save path: {self.save_path}')
        self.get_logger().info(f' [INIT] Configured Button Index: {self.circle_button_idx} (Circle Button)')
        self.get_logger().info(' [INIT] Waiting for PS4 controller input...')
        self.get_logger().info('====================================================')

    def joy_callback(self, msg: Joy):
        if len(msg.buttons) <= self.circle_button_idx:
            self.get_logger().warn(
                f'[JOYSTICK WARN] Received Joy message with only {len(msg.buttons)} buttons, '
                f'but target button index is {self.circle_button_idx}.'
            )
            return

        current_button_state = msg.buttons[self.circle_button_idx]

        # Detect Rising Edge: Button transition from 0 (unpressed) -> 1 (pressed)
        if current_button_state == 1 and self.prev_button_state == 0:
            self.get_logger().info('----------------------------------------------------')
            self.get_logger().info(f'[BUTTON EVENT] Circle button (index {self.circle_button_idx}) PRESSED!')
            
            if not self.is_capturing:
                self.get_logger().info('[BUTTON EVENT] Camera is idle. Initializing capture sequence...')
                self.take_picture()
            else:
                self.get_logger().warn('[BUTTON EVENT BUSY] Capture requested, but camera is currently busy taking a photo!')
            self.get_logger().info('----------------------------------------------------')

        self.prev_button_state = current_button_state

    def take_picture(self):
        self.is_capturing = True
        total_start_time = time.perf_counter()
        
        self.get_logger().info('📸 [CAPTURE START] Launching benchmark capture pipeline...')

        try:
            # Clean up old file to prevent stale checks
            if os.path.exists(self.save_path):
                os.remove(self.save_path)

            # -----------------------------------------------------------------
            # SUB-PHASE 1A: Trigger Camera Shutter / Internal Capture
            # -----------------------------------------------------------------
            cmd_capture = ['gphoto2', '--capture-image']
            self.get_logger().info(f'[GPHOTO2 CAPTURE] Executing: {" ".join(cmd_capture)}')
            
            t0 = time.perf_counter()
            result_cap = subprocess.run(cmd_capture, capture_output=True, text=True)
            capture_duration = time.perf_counter() - t0

            if result_cap.returncode != 0:
                self.get_logger().error(f'❌ [CAPTURE ERROR] gphoto2 trigger failed after {capture_duration:.2f}s!')
                if result_cap.stderr.strip():
                    self.get_logger().error(f'[GPHOTO2 STDERR] {result_cap.stderr.strip()}')
                self.is_capturing = False
                return

            self.get_logger().info(f'⏱️ [TIMER] Sub-Phase 1A (Shutter/Camera Storage): {capture_duration:.3f}s')

            # -----------------------------------------------------------------
            # SUB-PHASE 1B: USB Download to Host PC
            # -----------------------------------------------------------------
            cmd_download = [
                'gphoto2',
                '--get-file=1',
                '--filename', self.save_path,
                '--force-overwrite'
            ]
            self.get_logger().info(f'[GPHOTO2 DOWNLOAD] Executing: {" ".join(cmd_download)}')

            t0 = time.perf_counter()
            result_down = subprocess.run(cmd_download, capture_output=True, text=True)
            download_duration = time.perf_counter() - t0

            if result_down.returncode != 0:
                self.get_logger().error(f'❌ [DOWNLOAD ERROR] gphoto2 transfer failed after {download_duration:.2f}s!')
                if result_down.stderr.strip():
                    self.get_logger().error(f'[GPHOTO2 STDERR] {result_down.stderr.strip()}')
                self.is_capturing = False
                return

            self.get_logger().info(f'⏱️ [TIMER] Sub-Phase 1B (USB File Download): {download_duration:.3f}s')

            gphoto_total_duration = capture_duration + download_duration

            # -----------------------------------------------------------------
            # PHASE 2: Disk File Verification
            # -----------------------------------------------------------------
            t0 = time.perf_counter()
            if not os.path.exists(self.save_path):
                self.get_logger().error(f'❌ [FILE ERROR] Expected image file does not exist at {self.save_path}')
                self.is_capturing = False
                return

            file_size_mb = os.path.getsize(self.save_path) / (1024 * 1024)
            file_check_duration = time.perf_counter() - t0

            self.get_logger().info(
                f'⏱️ [TIMER] Phase 2 (File Check): {file_check_duration*1000:.2f} ms '
                f'| File: {self.save_path} ({file_size_mb:.2f} MB)'
            )

            # -----------------------------------------------------------------
            # PHASE 3: OpenCV Image Read
            # -----------------------------------------------------------------
            t0 = time.perf_counter()
            cv_img = cv2.imread(self.save_path)
            cv_load_duration = time.perf_counter() - t0

            if cv_img is None:
                self.get_logger().error(f'❌ [IMAGE LOAD ERROR] OpenCV failed to read image file at {self.save_path}')
                self.is_capturing = False
                return

            h, w, c = cv_img.shape
            self.get_logger().info(
                f'⏱️ [TIMER] Phase 3 (OpenCV Load): {cv_load_duration*1000:.2f} ms '
                f'| Resolution: {w}x{h} ({c} channels)'
            )

            # -----------------------------------------------------------------
            # PHASE 4: ROS Message Conversion & Publishing
            # -----------------------------------------------------------------
            t0 = time.perf_counter()
            ros_msg = self.bridge.cv2_to_imgmsg(cv_img, encoding='bgr8')
            ros_msg.header.stamp = self.get_clock().now().to_msg()
            ros_msg.header.frame_id = 'theta_camera'

            self.image_pub.publish(ros_msg)
            publish_duration = time.perf_counter() - t0

            self.get_logger().info(
                f'⏱️ [TIMER] Phase 4 (ROS Publish to /image_snapshot): {publish_duration*1000:.2f} ms'
            )

            # -----------------------------------------------------------------
            # TOTAL PIPELINE TIME & SUMMARY
            # -----------------------------------------------------------------
            total_duration = time.perf_counter() - total_start_time
            self.get_logger().info('====================================================')
            self.get_logger().info('📊 [SUMMARY] DETAILED CAPTURE & DOWNLOAD BENCHMARK')
            self.get_logger().info(f'   ├── 1A. Camera Trigger/Shutter: {capture_duration:.3f}s ({(capture_duration/total_duration)*100:.1f}%)')
            self.get_logger().info(f'   ├── 1B. USB File Download     : {download_duration:.3f}s ({(download_duration/total_duration)*100:.1f}%)')
            self.get_logger().info(f'   ├──  1. Total gphoto2 Time    : {gphoto_total_duration:.3f}s ({(gphoto_total_duration/total_duration)*100:.1f}%)')
            self.get_logger().info(f'   ├──  2. File Check            : {file_check_duration*1000:.2f} ms')
            self.get_logger().info(f'   ├──  3. OpenCV Disk Load      : {cv_load_duration*1000:.2f} ms')
            self.get_logger().info(f'   ├──  4. ROS Image Publish     : {publish_duration*1000:.2f} ms')
            self.get_logger().info(f'   └── 🏆 TOTAL PIPELINE TIME    : {total_duration:.3f}s ({total_duration*1000:.1f} ms)')
            self.get_logger().info('====================================================')

        except Exception as e:
            self.get_logger().error(f'❌ [EXCEPTION] Unexpected error during capture pipeline: {str(e)}')
        finally:
            self.is_capturing = False
            self.get_logger().info('[STATE RESET] Camera node state reset to IDLE.\n')


def main(args=None):
    rclpy.init(args=args)
    node = ThetaStillNode()
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