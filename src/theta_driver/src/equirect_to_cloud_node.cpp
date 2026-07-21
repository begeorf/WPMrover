#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <sensor_msgs/msg/point_cloud2.hpp>
#include <sensor_msgs/point_cloud2_iterator.hpp>
#include <cv_bridge/cv_bridge.h>
#include <opencv2/opencv.hpp>
#include <cmath>
#include <vector>

class EquirectToPointCloudNode : public rclcpp::Node {
public:
  EquirectToPointCloudNode() : Node("equirect_to_pointcloud_node") {
    this->declare_parameter<double>("radius", 5.0);
    this->declare_parameter<int>("downsample_factor", 2);

    radius_ = this->get_parameter("radius").as_double();
    downsample_factor_ = this->get_parameter("downsample_factor").as_int();

    sub_image_ = this->create_subscription<sensor_msgs::msg::Image>(
      "/image_raw", 10,
      std::bind(&EquirectToPointCloudNode::imageCallback, this, std::placeholders::_1));

    pub_cloud_ = this->create_publisher<sensor_msgs::msg::PointCloud2>("/image_sphere_cloud", 10);

    RCLCPP_INFO(this->get_logger(), "C++ Equirectangular to PointCloud Node initialized.");
  }

private:
  struct PrecomputedPoint {
    float x, y, z;
  };

  void precomputeLUT(int width, int height) {
    RCLCPP_INFO(this->get_logger(), "Precomputing spherical LUT for %dx%d resolution...", width, height);
    
    lut_.resize(width * height);
    lut_width_ = width;
    lut_height_ = height;

    for (int v = 0; v < height; ++v) {
      double norm_v = (v + 0.5) / height;
      double phi = (0.5 - norm_v) * M_PI; // Latitude [-pi/2, pi/2]

      for (int u = 0; u < width; ++u) {
        double norm_u = (u + 0.5) / width;
        // Inverted sign (-2.0) fixes horizontal mirroring issue
        double theta = -(norm_u - 0.5) * (2.0 * M_PI); // Longitude [-pi, pi]

        int idx = v * width + u;
        lut_[idx].x = static_cast<float>(radius_ * std::cos(phi) * std::cos(theta));
        lut_[idx].y = static_cast<float>(radius_ * std::cos(phi) * std::sin(theta));
        lut_[idx].z = static_cast<float>(radius_ * std::sin(phi));
      }
    }
  }

  void imageCallback(const sensor_msgs::msg::Image::SharedPtr msg) {
    cv_bridge::CvImagePtr cv_ptr;
    try {
      cv_ptr = cv_bridge::toCvCopy(msg, sensor_msgs::image_encodings::BGR8);
    } catch (const cv_bridge::Exception& e) {
      RCLCPP_ERROR(this->get_logger(), "cv_bridge exception: %s", e.what());
      return;
    }

    cv::Mat image = cv_ptr->image;
    if (downsample_factor_ > 1) {
      cv::resize(image, image, cv::Size(image.cols / downsample_factor_, image.rows / downsample_factor_), 0, 0, cv::INTER_LINEAR);
    }

    int width = image.cols;
    int height = image.rows;

    if (lut_width_ != width || lut_height_ != height) {
      precomputeLUT(width, height);
    }

    // Prepare PointCloud2 Message
    auto cloud_msg = std::make_unique<sensor_msgs::msg::PointCloud2>();
    cloud_msg->header = msg->header;
    cloud_msg->height = 1;
    cloud_msg->width = width * height;
    cloud_msg->is_dense = true;
    cloud_msg->is_bigendian = false;

    sensor_msgs::PointCloud2Modifier modifier(*cloud_msg);
    modifier.setPointCloud2FieldsByString(2, "xyz", "rgb");
    modifier.resize(width * height);

    sensor_msgs::PointCloud2Iterator<float> iter_x(*cloud_msg, "x");
    sensor_msgs::PointCloud2Iterator<float> iter_y(*cloud_msg, "y");
    sensor_msgs::PointCloud2Iterator<float> iter_z(*cloud_msg, "z");
    sensor_msgs::PointCloud2Iterator<uint8_t> iter_rgb(*cloud_msg, "rgb");

    for (int v = 0; v < height; ++v) {
      const cv::Vec3b* row_ptr = image.ptr<cv::Vec3b>(v);
      for (int u = 0; u < width; ++u, ++iter_x, ++iter_y, ++iter_z, ++iter_rgb) {
        int idx = v * width + u;
        
        // Coordinates from Look-Up Table
        *iter_x = lut_[idx].x;
        *iter_y = lut_[idx].y;
        *iter_z = lut_[idx].z;

        // BGR from OpenCV to RGB packed bytes
        const auto& pixel = row_ptr[u];
        iter_rgb[0] = pixel[0]; // B
        iter_rgb[1] = pixel[1]; // G
        iter_rgb[2] = pixel[2]; // R
      }
    }

    pub_cloud_->publish(std::move(cloud_msg));
  }

  double radius_;
  int downsample_factor_;
  int lut_width_{0};
  int lut_height_{0};
  std::vector<PrecomputedPoint> lut_;

  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr sub_image_;
  rclcpp::Publisher<sensor_msgs::msg::PointCloud2>::SharedPtr pub_cloud_;
};

int main(int argc, char** argv) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<EquirectToPointCloudNode>());
  rclcpp::shutdown();
  return 0;
}