#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, PointCloud2, PointField
from cv_bridge import CvBridge
import numpy as np
import cv2


class EquirectToPointCloud(Node):

    def __init__(self):
        super().__init__("equirect_to_pointcloud_node")

        # Declare parameters
        self.declare_parameter("radius", 5.0)  # Sphere radius in meters
        self.declare_parameter(
            "downsample_factor", 4
        )  # Downsample image to preserve FPS

        self.radius = self.get_parameter("radius").value
        self.downsample_factor = self.get_parameter("downsample_factor").value

        self.bridge = CvBridge()
        self.lut_u, self.lut_v = None, None
        self.xyz_sphere = None
        self.grid_shape = (0, 0)

        # Subscribers and Publishers
        self.sub_image = self.create_subscription(
            Image, "/image_raw", self.image_callback, 10
        )
        self.pub_cloud = self.create_publisher(
            PointCloud2, "/image_sphere_cloud", 10
        )

        self.get_logger().info("Equirectangular to PointCloud Node Started.")

    def precompute_spherical_lut(self, width, height):
        """Precomputes 3D Cartesian coordinates (X, Y, Z) for the given sphere dimensions."""
        self.get_logger().info(
            f"Precomputing Look-Up Table for resolution {width}x{height}..."
        )

        # Generate pixel grid centers
        u = (np.arange(width) + 0.5) / width
        v = (np.arange(height) + 0.5) / height

        # Convert 2D pixel coordinates to spherical angles (Theta, Phi)
        # Longitude theta: [-pi, pi], Latitude phi: [pi/2, -pi/2]
        theta = -(u - 0.5) * (2.0 * np.pi)
        phi = (0.5 - v) * np.pi

        theta_grid, phi_grid = np.meshgrid(theta, phi)

        # Convert spherical coordinates to Cartesian 3D coordinates (Forward = +X, Left = +Y, Up = +Z)
        R = self.radius
        x = R * np.cos(phi_grid) * np.cos(theta_grid)
        y = R * np.cos(phi_grid) * np.sin(theta_grid)
        z = R * np.sin(phi_grid)

        # Stack into (N, 3) matrix
        self.xyz_sphere = np.column_stack(
            (x.ravel(), y.ravel(), z.ravel())
        ).astype(np.float32)
        self.grid_shape = (height, width)

    def image_callback(self, msg: Image):
        # Convert ROS Image to OpenCV BGR
        try:
            cv_img = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as e:
            self.get_logger().error(f"Failed to convert ROS Image: {e}")
            return

        # Downsample image for efficient rendering performance
        if self.downsample_factor > 1:
            h, w = cv_img.shape[:2]
            cv_img = cv2.resize(
                cv_img,
                (w // self.downsample_factor, h // self.downsample_factor),
                interpolation=cv2.INTER_NEAREST,
            )

        h, w, _ = cv_img.shape

        # Recompute coordinate matrix if image size changes
        if self.xyz_sphere is None or self.grid_shape != (h, w):
            self.precompute_spherical_lut(w, h)

        # Convert BGR to RGB
        cv_img_rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        rgb_flat = cv_img_rgb.reshape(-1, 3).astype(np.uint32)

        # Pack RGB into 32-bit float bitwise pattern expected by PointCloud2
        # Bit layout: 0x00RRGGBB
        packed_rgb = (
            (rgb_flat[:, 0] << 16) | (rgb_flat[:, 1] << 8) | rgb_flat[:, 2]
        )
        rgb_floats = packed_rgb.view(np.float32).reshape(-1, 1)

        # Combine XYZ coordinates with packed RGB floats
        cloud_data = np.hstack((self.xyz_sphere, rgb_floats))

        # Build PointCloud2 message
        cloud_msg = PointCloud2()
        cloud_msg.header = msg.header
        cloud_msg.height = 1
        cloud_msg.width = cloud_data.shape[0]
        cloud_msg.is_dense = True
        cloud_msg.is_bigendian = False

        # Define fields: x, y, z, rgb
        cloud_msg.fields = [
            PointField(
                name="x", offset=0, datatype=PointField.FLOAT32, count=1
            ),
            PointField(
                name="y", offset=4, datatype=PointField.FLOAT32, count=1
            ),
            PointField(
                name="z", offset=8, datatype=PointField.FLOAT32, count=1
            ),
            PointField(
                name="rgb", offset=12, datatype=PointField.FLOAT32, count=1
            ),
        ]

        cloud_msg.point_step = 16  # 4 floats * 4 bytes
        cloud_msg.row_step = cloud_msg.point_step * cloud_msg.width
        cloud_msg.data = cloud_data.tobytes()

        self.pub_cloud.publish(cloud_msg)


def main(args=None):
    rclpy.init(args=args)
    node = EquirectToPointCloud()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()