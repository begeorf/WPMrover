#!/usr/bin/env python3
import time
import cv2
import torch

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

# Replace or import your actual PyTorch360 convert library here
# from pytorch360convert import e2c


class CubemapConverterNode(Node):

    def __init__(self):
        super().__init__('cubemap_converter_node')

        self.bridge = CvBridge()
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'

        # Subscribes to raw image feed from camera driver
        self.image_sub = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.image_callback,
            10
        )

        # Output publisher for converted cubemap
        self.cubemap_pub = self.create_publisher(Image, '/camera/cubemap', 10)

        self.get_logger().info('====================================================')
        self.get_logger().info(' [INIT] Cubemap Converter Node Initialized')
        self.get_logger().info(f' [INIT] PyTorch Device: {self.device}')
        self.get_logger().info(' [INIT] Subscribed to: /camera/image_raw')
        self.get_logger().info(' [INIT] Output Topic: /camera/cubemap')
        self.get_logger().info('====================================================')

    def image_callback(self, msg: Image):
        t_start = time.perf_counter()
        self.get_logger().info('>>> [CONVERTER] Received image from /camera/image_raw. Processing on CUDA...')

        try:
            cv_img = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            
            # --- GPU Cubemap Conversion Execution ---
            # (Insert your PyTorch 360 projection logic here)
            # Example placeholder keeping image format intact:
            tensor_img = torch.from_numpy(cv_img).to(self.device)
            
            # Simulated Output
            out_msg = self.bridge.cv2_to_imgmsg(cv_img, encoding='bgr8')
            out_msg.header = msg.header
            self.cubemap_pub.publish(out_msg)

            duration_ms = (time.perf_counter() - t_start) * 1000
            self.get_logger().info(f'✅ [CONVERTER DONE] Cubemap generated & published! (Took {duration_ms:.2f} ms)')

        except Exception as e:
            self.get_logger().error(f'❌ [CONVERTER ERROR] Conversion failed: {str(e)}')


def main(args=None):
    rclpy.init(args=args)
    node = CubemapConverterNode()
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