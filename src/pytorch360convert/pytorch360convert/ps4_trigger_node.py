#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from std_msgs.msg import Empty


class PS4TriggerNode(Node):

    def __init__(self):
        super().__init__('ps4_trigger_node')

        self.declare_parameter('circle_button_idx', 2)
        self.circle_button_idx = self.get_parameter('circle_button_idx').value

        self.prev_button_state = 0

        # ROS 2 Publisher to trigger capture on the driver topic
        self.trigger_pub = self.create_publisher(
            Empty,
            '/camera/trigger_snap',
            10
        )
        
        # ROS 2 Joy Subscriber
        self.joy_sub = self.create_subscription(
            Joy,
            '/joy',
            self.joy_callback,
            10
        )

        self.get_logger().info('====================================================')
        self.get_logger().info(' [INIT] PS4 Trigger Node Initialized')
        self.get_logger().info(' [INIT] Listening on: /joy')
        self.get_logger().info(' [INIT] Triggering topic: /camera/trigger_snap')
        self.get_logger().info(f' [INIT] Target Button: Circle (Index {self.circle_button_idx})')
        self.get_logger().info('====================================================')

    def joy_callback(self, msg: Joy):
        if len(msg.buttons) <= self.circle_button_idx:
            return

        current_button_state = msg.buttons[self.circle_button_idx]

        # Rising edge detection (Unpressed -> Pressed)
        if current_button_state == 1 and self.prev_button_state == 0:
            self.get_logger().info('[INPUT] Circle Button Pressed! Publishing snapshot trigger...')
            self.trigger_pub.publish(Empty())

        self.prev_button_state = current_button_state


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