#!/usr/bin/env python3
import os
import cv2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

import torch
import numpy as np
import pytorch360convert


class CubemapConverterNode(Node):

    def __init__(self):
        super().__init__('cubemap_converter_node')

        self.bridge = CvBridge()

        # Paths for side-by-side demo comparison
        workspace_dir = os.path.expanduser('~/rover_workspace')
        self.orig_output_path = os.path.join(workspace_dir, 'original_snapshot.png')
        self.cube_output_path = os.path.join(workspace_dir, 'cubemap_output.png')

        # Subscription: Listening on /image_snapshot
        self.sub = self.create_subscription(
            Image,
            '/image_snapshot',
            self.image_callback,
            10
        )

        # Publisher: Sending processed cubemap image
        self.pub = self.create_publisher(
            Image,
            '/cubemap_snapshot',
            10
        )

        self.get_logger().info('Cubemap Converter Node Initialized.')
        self.get_logger().info(f'Saving raw image to: {self.orig_output_path}')
        self.get_logger().info(f'Saving processed image to: {self.cube_output_path}')

    def image_callback(self, msg: Image):
        try:
            # 1. Convert ROS Image message to OpenCV BGR format
            cv_img = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

            # 2. Save the original equirectangular image to the workspace
            cv2.imwrite(self.orig_output_path, cv_img)

            # 3. Convert BGR to RGB with positive memory strides
            rgb_img = np.ascontiguousarray(cv_img[:, :, ::-1])
            tensor_img = torch.from_numpy(rgb_img).permute(2, 0, 1).float() / 255.0

            # 4. Perform Equirectangular to Cubemap conversion
            cubemap_tensor = pytorch360convert.e2c(
                tensor_img,
                face_w=256,
                mode='bilinear',
                cube_format='dice'
            )

            # 5. Convert PyTorch tensor back to OpenCV numpy array (BGR)
            cubemap_np = (cubemap_tensor.permute(1, 2, 0).cpu().numpy() * 255.0).astype(np.uint8)
            cubemap_bgr = np.ascontiguousarray(cubemap_np[:, :, ::-1])

            # 6. Save the cubemap image to the workspace
            cv2.imwrite(self.cube_output_path, cubemap_bgr)

            # 7. Convert back to ROS Image message and publish
            out_msg = self.bridge.cv2_to_imgmsg(cubemap_bgr, encoding='bgr8')
            out_msg.header = msg.header
            self.pub.publish(out_msg)

            self.get_logger().info('Saved both original_snapshot.png and cubemap_output.png!')

        except Exception as e:
            self.get_logger().error(f'Failed to convert image: {str(e)}')


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