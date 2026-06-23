#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from tf2_msgs.msg import TFMessage
import math

class TFFlattener(Node):
    def __init__(self):
        super().__init__('tf_flattener')
        self.sub = self.create_subscription(TFMessage, '/tf_raw', self.callback, 10)
        self.pub = self.create_publisher(TFMessage, '/tf', 10)

    def callback(self, msg):
        out_msg = TFMessage()
        for transform in msg.transforms:
            # Fixed the nesting: frame_id lives inside the header object
            if transform.child_frame_id == 'camera_camera_link' or transform.header.frame_id == 'odom':
                # 1. Force the physical height to perfectly flat zero
                transform.transform.translation.z = 0.0
                
                # 2. Extract only the horizontal Yaw angle, discarding Pitch and Roll
                q = transform.transform.rotation
                siny_cosp = 2 * (q.w * q.z + q.x * q.y)
                cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
                yaw = math.atan2(siny_cosp, cosy_cosp)

                # 3. Re-encode back into a completely flat 2D quaternion
                transform.transform.rotation.x = 0.0
                transform.transform.rotation.y = 0.0
                transform.transform.rotation.z = math.sin(yaw / 2.0)
                transform.transform.rotation.w = math.cos(yaw / 2.0)
                
            out_msg.transforms.append(transform)
        self.pub.publish(out_msg)

def main():
    rclpy.init()
    node = TFFlattener()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()