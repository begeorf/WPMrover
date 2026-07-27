#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from std_msgs.msg import Empty


class PS4TriggerNode(Node):

    def __init__(self):
        super().__init__('ps4_trigger_node')

        # Button index mapping for DS4 controller (Linux joy driver)
        self.CIRCLE_INDEX = 2  # Circle Button
        self.CROSS_INDEX = 1   # X (Cross) Button

        self.last_circle_state = 0
        self.last_cross_state = 0

        # Publishers
        self.snap_pub = self.create_publisher(Empty, '/camera/trigger_snap', 10)
        self.offload_pub = self.create_publisher(Empty, '/camera/trigger_offload', 10)

        # Subscriber
        self.joy_sub = self.create_subscription(Joy, '/joy', self.joy_callback, 10)

        self.get_logger().info('====================================================')
        self.get_logger().info(' [INIT] PS4 Trigger Node Initialized')
        self.get_logger().info(' [INIT] Listening on: /joy')
        self.get_logger().info(' [INIT] Circle (Index 2) -> /camera/trigger_snap')
        self.get_logger().info(' [INIT] Cross X (Index 0) -> /camera/trigger_offload')
        self.get_logger().info('====================================================')

    def joy_callback(self, msg: Joy):
        if len(msg.buttons) <= max(self.CIRCLE_INDEX, self.CROSS_INDEX):
            return

        # Circle Button Press Detection (Rising Edge)
        circle_state = msg.buttons[self.CIRCLE_INDEX]
        if circle_state == 1 and self.last_circle_state == 0:
            self.get_logger().info('[INPUT] Circle Pressed -> Publishing snapshot trigger')
            self.snap_pub.publish(Empty())
        self.last_circle_state = circle_state

        # Cross (X) Button Press Detection (Rising Edge)
        cross_state = msg.buttons[self.CROSS_INDEX]
        if cross_state == 1 and self.last_cross_state == 0:
            self.get_logger().info('[INPUT] X Pressed -> Publishing offload trigger')
            self.offload_pub.publish(Empty())
        self.last_cross_state = cross_state


def main(args=None):
    rclpy.init(args=args)
    node = PS4TriggerNode()
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