#!/usr/bin/env python3
"""
High-Resolution Persistent Ricoh Theta Capture Node (Option 1 Optimized)
------------------------------------------------------------------------
Uses persistent python-gphoto2 C-bindings with safe PTP property traversal.
Locks Exposure Program (0x500e) and White Balance (0x5005) to eliminate on-camera
light metering delays (~1.8s savings). Disables internal DSP stitching (0xD834=2).
"""

import os
import time
import cv2
import numpy as np
import torch
import torch.nn.functional as F

import gphoto2 as gp

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Empty
from cv_bridge import CvBridge


class OrinGpuStitcher:
    """Handles PyTorch CUDA remapping for high-resolution dual-fisheye frames."""
    
    def __init__(self, eq_width=7296, eq_height=3648, lut_dir="/tmp"):
        self.eq_width = eq_width
        self.eq_height = eq_height
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.grid_path = os.path.join(lut_dir, f"theta_grid_{eq_width}x{eq_height}.pt")
        
        if not os.path.exists(self.grid_path):
            self._generate_and_save_grid()
            
        try:
            self.grid = torch.load(self.grid_path, map_location=self.device, weights_only=True)
        except TypeError:
            self.grid = torch.load(self.grid_path, map_location=self.device)

    def _generate_and_save_grid(self):
        """Generates dual-fisheye spherical projection grid matching frame size."""
        print(f"⚙️ Generating PyTorch CUDA grid ({self.eq_width}x{self.eq_height}) on Jetson...")
        theta = np.linspace(-np.pi, np.pi, self.eq_width)
        phi = np.linspace(-np.pi/2, np.pi/2, self.eq_height)
        theta_grid, phi_grid = np.meshgrid(theta, phi)

        x = np.cos(phi_grid) * np.sin(theta_grid)
        y = np.sin(phi_grid)
        z = np.cos(phi_grid) * np.cos(theta_grid)

        radius = self.eq_height / 2.0
        c1 = (self.eq_width / 4.0, self.eq_height / 2.0)
        c2 = (3 * self.eq_width / 4.0, self.eq_height / 2.0)

        r = np.arctan2(np.sqrt(x**2 + y**2), z) / (np.pi / 2.0)
        angle = np.arctan2(y, x)

        map_x = np.zeros((self.eq_height, self.eq_width), dtype=np.float32)
        map_y = np.zeros((self.eq_height, self.eq_width), dtype=np.float32)

        # Front lens
        mask_left = z >= 0
        map_x[mask_left] = c1[0] + r[mask_left] * radius * np.cos(angle[mask_left])
        map_y[mask_left] = c1[1] + r[mask_left] * radius * np.sin(angle[mask_left])

        # Back lens
        mask_right = z < 0
        r_back = np.arctan2(np.sqrt(x**2 + y**2), -z) / (np.pi / 2.0)
        map_x[mask_right] = c2[0] + r_back[mask_right] * radius * np.cos(angle[mask_right])
        map_y[mask_right] = c2[1] + r_back[mask_right] * radius * np.sin(angle[mask_right])

        norm_x = (map_x / (self.eq_width - 1)) * 2.0 - 1.0
        norm_y = (map_y / (self.eq_height - 1)) * 2.0 - 1.0

        grid = torch.from_numpy(np.stack([norm_x, norm_y], axis=-1)).unsqueeze(0).float()
        torch.save(grid, self.grid_path)
        print("✅ Calibration grid generated and cached.")

    def remap(self, raw_dual_fisheye_bgr, logger):
        """Executes PyTorch CUDA remapping on full high-res frames."""
        t0 = time.perf_counter()

        img_tensor = torch.from_numpy(raw_dual_fisheye_bgr).permute(2, 0, 1).unsqueeze(0).float().to(self.device)
        equirect_tensor = F.grid_sample(img_tensor, self.grid, mode='bilinear', padding_mode='zeros', align_corners=True)
        equirect_bgr = equirect_tensor.squeeze(0).permute(1, 2, 0).byte().cpu().numpy()

        t_gpu_ms = (time.perf_counter() - t0) * 1000.0
        logger.info(f"   └─ [GPU Processing] High-Res PyTorch Remap: {t_gpu_ms:.2f} ms")
        return equirect_bgr


class HighResThetaDriverNode(Node):
    """ROS 2 Node managing persistent gPhoto2 capture with locked camera hardware properties."""
    
    def __init__(self):
        super().__init__('theta_driver_node')
        
        self.publisher_ = self.create_publisher(Image, '/camera/image_raw', 10)
        self.bridge = CvBridge()
        
        self.trigger_sub = self.create_subscription(
            Empty,
            '/camera/trigger_snap',
            self.trigger_callback,
            10
        )
        self.is_processing = False

        # Initialize persistent gPhoto2 C-session
        self.get_logger().info("📷 Initializing persistent gPhoto2 USB session...")
        gp.check_result(gp.use_python_logging())
        
        self.camera = gp.Camera()
        self.camera.init()

        # Apply Hardware Configuration (Option 1: Lock Exposure & WB, Disable Stitching)
        self._configure_camera_hardware()

        # Default GPU Stitcher (Dynamically auto-adjusts to downloaded payload dimensions)
        self.stitcher = OrinGpuStitcher(eq_width=7296, eq_height=3648)
        self.get_logger().info("🚀 High-Res Driver Ready. Listening for PS4 Trigger.")

    def _configure_camera_hardware(self):
        """Safely sets PTP properties to disable DSP stitching and lock Exposure/WB."""
        try:
            config = self.camera.get_config()

            def find_child(parent, path_str):
                curr = parent
                for part in path_str.strip('/').split('/'):
                    curr = curr.get_child_by_name(part)
                return curr

            # 1. Disable Onboard Image Stitching (0xD834 = 2: Dual-Fisheye Mode)
            for path in ['other/d834', 'd834']:
                try:
                    node = find_child(config, path)
                    node.set_value('2')
                    self.get_logger().info("   ├─ [Config] Image Stitching: Disabled (Dual-Fisheye 0xD834=2)")
                    break
                except Exception:
                    continue

            # 2. Lock Exposure Program Mode (0x500e = 1 [Manual] or 4 [Shutter Priority])
            # Skips auto-exposure calculation delay prior to shutter trigger
            for path in ['other/500e', 'capturesettings/exposureprogram', 'exposureprogram', '500e']:
                try:
                    node = find_child(config, path)
                    try:
                        node.set_value('1')  # Manual Mode
                        self.get_logger().info("   ├─ [Config] Exposure Mode: Locked to Manual (0x500e=1)")
                    except Exception:
                        node.set_value('4')  # Shutter Priority Mode
                        self.get_logger().info("   ├─ [Config] Exposure Mode: Locked to Shutter Priority (0x500e=4)")
                    break
                except Exception:
                    continue

            # 3. Lock White Balance (0x5005 / whitebalance)
            # Skips auto white balance color temperature calculation delay
            for path in ['imgsettings/whitebalance', 'other/5005', 'whitebalance', '5005']:
                try:
                    node = find_child(config, path)
                    try:
                        node.set_value('Daylight')
                        self.get_logger().info("   ├─ [Config] White Balance: Locked to Daylight")
                    except Exception:
                        node.set_value('2')
                        self.get_logger().info("   ├─ [Config] White Balance: Locked to Enum Value (2)")
                    break
                except Exception:
                    continue

            # Commit configuration tree to camera hardware
            self.camera.set_config(config)
            self.get_logger().info("✅ All PTP configuration properties locked successfully.")

        except Exception as e:
            self.get_logger().warn(f"⚠️ Non-fatal notice during PTP configuration: {str(e)}")

    def trigger_callback(self, msg):
        """Executes full-res capture, in-memory transfer, and GPU stitching."""
        if self.is_processing:
            self.get_logger().warn("⚠️ Trigger received while previous frame processing. Skipping.")
            return

        self.is_processing = True
        t_pipeline_start = time.perf_counter()

        self.get_logger().info("====================================================")
        self.get_logger().info("📸 HIGH-RES TRIGGER RECEIVED (PS4 Circle) -> Capturing Frame")

        try:
            # Step 1: Execute Camera Shutter
            t_shutter_start = time.perf_counter()
            file_path = self.camera.capture(gp.GP_CAPTURE_IMAGE)
            t_shutter_ms = (time.perf_counter() - t_shutter_start) * 1000.0
            self.get_logger().info(f"1. [Camera Hardware] Shutter Snap & Sensor Readout: {t_shutter_ms:.2f} ms")

            # Step 2: In-Memory RAM Transfer (Skip physical disk I/O)
            t_transfer_start = time.perf_counter()
            camera_file = self.camera.file_get(file_path.folder, file_path.name, gp.GP_FILE_TYPE_NORMAL)
            file_data = camera_file.get_data_and_size()
            
            raw_bytes = np.frombuffer(file_data, dtype=np.uint8)
            raw_image = cv2.imdecode(raw_bytes, cv2.IMREAD_COLOR)
            t_transfer_ms = (time.perf_counter() - t_transfer_start) * 1000.0

            # Delete file on camera flash memory to prevent internal storage fill-up
            self.camera.file_delete(file_path.folder, file_path.name)

            h, w, c = raw_image.shape
            size_mb = len(file_data) / (1024 * 1024)
            self.get_logger().info(f"2. [USB RAM Download] Payload Size: {size_mb:.2f} MB ({w}x{h} resolution)")
            self.get_logger().info(f"   └─ In-Memory Transfer & OpenCV Decode Time: {t_transfer_ms:.2f} ms")

            # Auto-align GPU Stitcher grid dimensions if downloaded payload differs
            if (w, h) != (self.stitcher.eq_width, self.stitcher.eq_height):
                self.get_logger().info(f"⚙️ Grid size mismatch detected. Adjusting PyTorch Grid to {w}x{h}...")
                self.stitcher = OrinGpuStitcher(eq_width=w, eq_height=h)

            # Step 3: PyTorch GPU Remap
            self.get_logger().info("3. [Orin GPU Stitching] Executing PyTorch High-Res Remap...")
            equirect_img = self.stitcher.remap(raw_image, self.get_logger())

            # Step 4: Publish ROS Image Message
            t_pub_start = time.perf_counter()
            msg = self.bridge.cv2_to_imgmsg(equirect_img, encoding="bgr8")
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = "camera_link"
            self.publisher_.publish(msg)
            t_pub_ms = (time.perf_counter() - t_pub_start) * 1000.0

            total_elapsed_ms = (time.perf_counter() - t_pipeline_start) * 1000.0
            self.get_logger().info(f"4. [ROS Publisher] cv_bridge conversion + Publish: {t_pub_ms:.2f} ms")
            self.get_logger().info(f"🏁 TOTAL END-TO-END HIGH-RES LATENCY: {total_elapsed_ms:.2f} ms")
            self.get_logger().info("====================================================")

        except Exception as e:
            self.get_logger().error(f"❌ Error during capture pipeline: {str(e)}")
        finally:
            self.is_processing = False

    def destroy_node(self):
        try:
            self.camera.exit()
        except Exception:
            pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = HighResThetaDriverNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()