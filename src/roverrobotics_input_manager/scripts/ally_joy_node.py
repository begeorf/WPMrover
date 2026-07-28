#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from geometry_msgs.msg import Twist


class AllyJoyNode(Node):
    """ROS 2 Node tailored for ROG Ally X (or standard Xbox controllers) using 
    Josh Newans' Foxglove Joystick Panel in Gamepad Mode.
    
    Converts /joy messages sent by Foxglove into geometry_msgs/Twist on /cmd_vel.
    """

    def __init__(self) -> None:
        super().__init__("ally_joy_node")

        # --- Parameters ---
        self.declare_parameter("joy_topic", "/joy")
        self.declare_parameter("cmd_vel_topic", "/cmd_vel")

        # Standard Web Gamepad API Axis Mappings
        # Axis 1 = Left Stick Vertical (Forward / Backward)
        # Axis 0 = Left Stick Horizontal (Left / Right strafe for holonomic drive)
        # Axis 2 = Right Stick Horizontal (Yaw Rotation)
        self.declare_parameter("axis_linear_x", 1)      
        self.declare_parameter("axis_linear_y", 0)      
        self.declare_parameter("axis_angular_z", 2)     

        # Gamepad Web API Inversion Flags 
        # (Standard Web Gamepad API sends Up as -1.0, so linear_x needs inversion)
        self.declare_parameter("invert_linear_x", False)
        self.declare_parameter("invert_linear_y", False)
        self.declare_parameter("invert_angular_z", False)

        # Speed Multipliers (m/s and rad/s)
        self.declare_parameter("scale_linear_x", 0.8)   # Normal Max Forward/Backward Speed
        self.declare_parameter("scale_linear_y", 0.0)   # Non-zero for Omni/Holonomic drive
        self.declare_parameter("scale_angular_z", 1.8)  # Max Rotation Speed

        # Safety & Comfort
        self.declare_parameter("deadzone", 0.15)        # Ignore stick drift < 8%
        self.declare_parameter("timeout_sec", 0.5)      # Auto-stop robot if Foxglove drops connection

        # Buttons (Standard Xbox/Gamepad mapping)
        # Button 5 = Right Bumper (RB)
        self.declare_parameter("enable_button", -1)     # Set to button ID for deadman's switch (-1 = disabled)
        self.declare_parameter("turbo_button", 5)       # RB button index for speed boost
        self.declare_parameter("turbo_scale", 1.5)      # Speed multiplier when holding turbo button

        # Load Parameters
        joy_topic = self.get_parameter("joy_topic").value
        cmd_vel_topic = self.get_parameter("cmd_vel_topic").value

        self.axis_linear_x = self.get_parameter("axis_linear_x").value
        self.axis_linear_y = self.get_parameter("axis_linear_y").value
        self.axis_angular_z = self.get_parameter("axis_angular_z").value

        self.invert_linear_x = -1.0 if self.get_parameter("invert_linear_x").value else 1.0
        self.invert_linear_y = -1.0 if self.get_parameter("invert_linear_y").value else 1.0
        self.invert_angular_z = -1.0 if self.get_parameter("invert_angular_z").value else 1.0

        self.scale_linear_x = self.get_parameter("scale_linear_x").value
        self.scale_linear_y = self.get_parameter("scale_linear_y").value
        self.scale_angular_z = self.get_parameter("scale_angular_z").value

        self.deadzone = self.get_parameter("deadzone").value
        self.timeout_sec = self.get_parameter("timeout_sec").value

        self.enable_button = self.get_parameter("enable_button").value
        self.turbo_button = self.get_parameter("turbo_button").value
        self.turbo_scale = self.get_parameter("turbo_scale").value

        # --- Publishers & Subscribers ---
        self.sub_joy = self.create_subscription(
            Joy, joy_topic, self.joy_callback, 10
        )
        self.pub_cmd_vel = self.create_publisher(Twist, cmd_vel_topic, 10)

        # Watchdog Timer
        self.last_joy_time = self.get_clock().now()
        # self.timer = self.create_timer(0.1, self.watchdog_callback)  # 10Hz check

        self.get_logger().info(
            f"🎮 Ally Joy Node active in GAMEPAD MODE.\n"
            f"   Subscribed to: {joy_topic}\n"
            f"   Publishing to: {cmd_vel_topic}"
        )

    def apply_deadzone(self, value: float) -> float:
        """Zero out small stick drifts within the configured deadzone."""
        if abs(value) < self.deadzone:
            return 0.0
        return value

    def joy_callback(self, msg: Joy) -> None:
        """Parse Foxglove Joy inputs and convert them to Twist messages."""
        self.last_joy_time = self.get_clock().now()

        # Check enable button (Deadman's switch)
        if self.enable_button >= 0:
            if self.enable_button >= len(msg.buttons) or msg.buttons[self.enable_button] == 0:
                self.stop_robot()
                return

        # Check Turbo Multiplier
        multiplier = 1.0
        if self.turbo_button >= 0 and self.turbo_button < len(msg.buttons):
            if msg.buttons[self.turbo_button] == 1:
                multiplier = self.turbo_scale

        twist = Twist()

        # Parse Forward / Backward (Axis 1)
        if self.axis_linear_x < len(msg.axes):
            raw_x = msg.axes[self.axis_linear_x]
            twist.linear.x = (
                self.apply_deadzone(raw_x) * self.invert_linear_x * self.scale_linear_x * multiplier
            )

        # Parse Left / Right Strafe (Axis 0)
        if self.axis_linear_y < len(msg.axes) and self.scale_linear_y != 0.0:
            raw_y = msg.axes[self.axis_linear_y]
            twist.linear.y = (
                self.apply_deadzone(raw_y) * self.invert_linear_y * self.scale_linear_y * multiplier
            )

        # Parse Turning / Yaw (Axis 2)
        if self.axis_angular_z < len(msg.axes):
            raw_z = msg.axes[self.axis_angular_z]
            twist.angular.z = (
                self.apply_deadzone(raw_z) * self.invert_angular_z * self.scale_angular_z * multiplier
            )

        self.pub_cmd_vel.publish(twist)

    def watchdog_callback(self) -> None:
        """Bring robot to an immediate halt if Foxglove drops connection or stops publishing."""
        time_since_last_msg = (self.get_clock().now() - self.last_joy_time).nanoseconds / 1e9
        if time_since_last_msg > self.timeout_sec:
            stop_cmd = Twist()
            self.cmd_pub.publish(stop_cmd)

    def stop_robot(self) -> None:
        """Publish zero velocity to halt the robot."""
        twist = Twist()
        self.pub_cmd_vel.publish(twist)


def main(args=None):
    rclpy.init(args=args)
    node = AllyJoyNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop_robot()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()