#!/usr/bin/env python3
import os
import time
import threading
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
        self.is_busy = False
        self.last_snap_time = 0.0

        self.workspace_dir = os.path.expanduser('~/rover_workspace')

        # Publisher for raw equirectangular image
        self.image_pub = self.create_publisher(Image, '/camera/image_raw', 10)

        # Subscriber for PS4 Circle Button (Instant Fire)
        self.trigger_sub = self.create_subscription(
            Empty,
            '/camera/trigger_snap',
            self.trigger_callback,
            10
        )

        # Subscriber for PS4 X Button (Download to SSD)
        self.offload_sub = self.create_subscription(
            Empty,
            '/camera/trigger_offload',
            self.offload_callback,
            10
        )

        # Initialize persistent libgphoto2 session
        self.gp_camera = None
        self.gp_context = None
        self._init_camera_session()
        self._configure_hardware_auto_mode()

        self.get_logger().info('====================================================')
        self.get_logger().info(' [INIT] Theta Driver Node (Non-Blocking + Enhanced Debug)')
        self.get_logger().info(' [INIT] Circle (Snap)    : /camera/trigger_snap')
        self.get_logger().info(' [INIT] Cross X (Offload): /camera/trigger_offload')
        self.get_logger().info(' [INIT] Publisher        : /camera/image_raw (rgb8)')
        self.get_logger().info('====================================================')

    def _init_camera_session(self):
        try:
            self.gp_context = gp.Context()
            self.gp_camera = gp.Camera()
            self.gp_camera.init(self.gp_context)
            self.get_logger().info('✅ [GPHOTO2] Persistent session connected successfully!')
        except gp.GPhoto2Error as e:
            self.get_logger().error(f'❌ [GPHOTO2 INIT ERROR] Connection failed: {e}')

    def _configure_hardware_auto_mode(self):
        if not self.gp_camera:
            return
        try:
            config = self.gp_camera.get_config(self.gp_context)

            try:
                exp_widget = config.get_child_by_name('expprogram')
                try:
                    auto_exp = exp_widget.get_choice(2)
                except Exception:
                    auto_exp = 'Auto'
                exp_widget.set_value(auto_exp)
            except Exception:
                pass

            try:
                wb_widget = config.get_child_by_name('whitebalance')
                try:
                    auto_wb = wb_widget.get_choice(0)
                except Exception:
                    auto_wb = 'Automatic'
                wb_widget.set_value(auto_wb)
            except Exception:
                pass

            self.gp_camera.set_config(config, self.gp_context)
            self.get_logger().info('⚙️ [CONFIG] Auto Exposure & Auto White Balance active')
        except gp.GPhoto2Error as e:
            self.get_logger().warn(f'⚠️ [CONFIG WARN] Could not apply config: {e}')

    def trigger_callback(self, msg: Empty):
        current_time = time.time()
        
        # Debounce/Cooldown guard (3.0s)
        if current_time - self.last_snap_time < 3.0:
            remaining = 3.0 - (current_time - self.last_snap_time)
            self.get_logger().warn(f'⏱️ [COOLDOWN ACTIVE] Camera busy stitching! Wait {remaining:.1f}s...')
            return

        if self.is_busy:
            self.get_logger().warn('⚠️ [REJECTED] Node is busy with another USB operation!')
            return

        if not self.gp_camera:
            self.get_logger().error('❌ [ERROR] Camera session lost. Reconnecting...')
            self._init_camera_session()
            if not self.gp_camera:
                return

        self.is_busy = True
        self.last_snap_time = current_time
        t0 = time.perf_counter()

        try:
            self.get_logger().info('🔴 [CIRCLE PRESSED] Triggering camera shutter...')
            self.gp_camera.trigger_capture(self.gp_context)
            elapsed = (time.perf_counter() - t0) * 1000

            self.get_logger().info('====================================================')
            self.get_logger().info('📸 [SHUTTER FIRED] Snapshot capturing to internal storage...')
            self.get_logger().info(f'⚡ Trigger overhead: {elapsed:.2f} ms')
            self.get_logger().info('⏳ [WAITING FOR STITCHING] Monitoring camera internal status...')
            self.get_logger().info('====================================================')

            # Launch a background thread to monitor when the camera finishes stitching/writing
            threading.Thread(target=self._wait_for_capture_complete, daemon=True).start()

        except Exception as e:
            self.get_logger().error(f'❌ [CAPTURE ERROR] Shutter trigger failed: {e}')
            if self.gp_camera:
                try:
                    self.gp_camera.exit(self.gp_context)
                except Exception:
                    pass
                self.gp_camera = None
            self.is_busy = False

    def _wait_for_capture_complete(self):
        """Polls camera events to confirm when processing and writing to storage finishes."""
        t_start = time.perf_counter()
        try:
            while True:
                event_type, event_data = self.gp_camera.wait_for_event(1000, self.gp_context)
                
                if event_type == gp.GP_EVENT_FILE_ADDED:
                    file_path = os.path.join(event_data.folder, event_data.name)
                    elapsed = time.perf_counter() - t_start
                    self.get_logger().info('====================================================')
                    self.get_logger().info(f'✅ [CAPTURE COMPLETE] Image processed & saved!')
                    self.get_logger().info(f'📁 File Location : {file_path}')
                    self.get_logger().info(f'⏱️ Total Time    : {elapsed:.2f} seconds')
                    self.get_logger().info('====================================================')
                    break
                
                elif event_type == gp.GP_EVENT_TIMEOUT:
                    # If 5 seconds pass without event, camera finished without explicit event
                    if time.perf_counter() - t_start > 5.0:
                        self.get_logger().info('ℹ️ [STATUS] Camera finished writing to storage.')
                        break
        except Exception as e:
            self.get_logger().warn(f'⚠️ [MONITOR WARN] Event polling ended: {e}')
        finally:
            self.is_busy = False

    def offload_callback(self, msg: Empty):
        self.get_logger().info('🔵 [X BUTTON PRESSED] Received offload trigger!')

        if self.is_busy:
            self.get_logger().warn('⚠️ [REJECTED] Camera is busy capturing or transferring!')
            return

        if not self.gp_camera:
            self.get_logger().error('❌ [ERROR] Camera session lost. Cannot offload.')
            return

        self.is_busy = True
        self.get_logger().info('📥 [OFFLOAD STARTED] Transferring files from camera storage to SSD...')

        try:
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            offload_dir = os.path.join(self.workspace_dir, f'theta_captures_{timestamp}')
            os.makedirs(offload_dir, exist_ok=True)

            self.get_logger().info('🔍 Scanning camera internal storage for files...')
            all_files = self._list_files_recursive('/')

            if not all_files:
                self.get_logger().info('ℹ️ [OFFLOAD EMPTY] No images found on camera storage.')
                return

            self.get_logger().info(f'📦 Found {len(all_files)} file(s). Downloading to: {offload_dir}')

            for idx, (folder, name) in enumerate(all_files, start=1):
                t0 = time.perf_counter()
                target_path = os.path.join(offload_dir, name)

                camera_file = gp.CameraFile()
                self.gp_camera.file_get(
                    folder,
                    name,
                    gp.GP_FILE_TYPE_NORMAL,
                    camera_file,
                    self.gp_context
                )
                camera_file.save(target_path)
                dl_time = time.perf_counter() - t0

                file_size_mb = os.path.getsize(target_path) / (1024 * 1024)
                self.get_logger().info(
                    f'   ├── [{idx}/{len(all_files)}] Saved {name} '
                    f'({file_size_mb:.2f} MB) in {dl_time:.3f}s'
                )

                # Publish the latest transferred image to ROS
                if idx == len(all_files):
                    self._publish_image_to_ros(target_path)

            self.get_logger().info('====================================================')
            self.get_logger().info(f'✅ [OFFLOAD COMPLETE] All {len(all_files)} file(s) saved to {offload_dir}')
            self.get_logger().info('====================================================')

        except Exception as e:
            self.get_logger().error(f'❌ [OFFLOAD ERROR] Download failed: {e}')
        finally:
            self.is_busy = False

    def _list_files_recursive(self, folder='/'):
        files = []
        try:
            for name, _ in self.gp_camera.folder_list_files(folder, self.gp_context):
                if name.lower().endswith(('.jpg', '.jpeg', '.png')):
                    files.append((folder, name))
            for name, _ in self.gp_camera.folder_list_folders(folder, self.gp_context):
                subfolder = os.path.join(folder, name)
                files.extend(self._list_files_recursive(subfolder))
        except gp.GPhoto2Error as e:
            self.get_logger().warn(f'⚠️ Folder listing warning ({folder}): {e}')
        return files

    def _publish_image_to_ros(self, file_path):
        bgr_img = cv2.imread(file_path)
        if bgr_img is None:
            return

        rgb_img = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2RGB)
        ros_msg = self.bridge.cv2_to_imgmsg(rgb_img, encoding='rgb8')
        ros_msg.header.stamp = self.get_clock().now().to_msg()
        ros_msg.header.frame_id = 'theta_camera'

        self.image_pub.publish(ros_msg)
        self.get_logger().info(f'📢 Published {os.path.basename(file_path)} to /camera/image_raw')

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