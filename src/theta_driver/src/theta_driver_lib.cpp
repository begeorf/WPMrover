#include "theta_driver/theta_driver_lib.hpp"
#include <opencv2/imgproc.hpp>
#include <opencv2/imgcodecs.hpp>

namespace {
theta_driver::gst_src gsrc;
}

namespace theta_driver {

gboolean gst_bus_callback(GstBus* bus, GstMessage* message, gpointer data) {
    (void)bus;
    (void)data;
    GError* err;
    gchar* dbg;
    switch (GST_MESSAGE_TYPE(message)) {
        case GST_MESSAGE_ERROR:
            gst_message_parse_error(message, &err, &dbg);
            g_print("Error: %s\n", err->message);
            g_error_free(err);
            g_free(dbg);
            g_main_loop_quit(gsrc.loop);
            break;
        default:
            break;
    }

    return TRUE;
}

void uvc_streaming_callback(uvc_frame_t* frame, void* ptr) {
    struct gst_src* src = (struct gst_src*)ptr;
    GstBuffer* buffer;
    GstFlowReturn ret;
    GstMapInfo map;

    // Capture precise system wall-time at UVC arrival
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    uint64_t capture_time_ns = (uint64_t)ts.tv_sec * 1000000000ULL + ts.tv_nsec;

    buffer = gst_buffer_new_allocate(NULL, frame->data_bytes, NULL);
    
    // Set standard PTS for GStreamer pipeline clocking
    GST_BUFFER_PTS(buffer) = frame->sequence * src->dwFrameInterval * 100;
    // Store real-world wall clock time in DTS where nvv4l2decoder won't wipe it out
    GST_BUFFER_DTS(buffer) = capture_time_ns;
    GST_BUFFER_DURATION(buffer) = src->dwFrameInterval * 100;
    GST_BUFFER_OFFSET(buffer) = frame->sequence;
    src->framecount++;

    gst_buffer_map(buffer, &map, GST_MAP_WRITE);
    memcpy(map.data, frame->data, frame->data_bytes);
    gst_buffer_unmap(buffer, &map);

    g_signal_emit_by_name(src->appsrc, "push-buffer", buffer, &ret);
    gst_buffer_unref(buffer);
    if (ret != GST_FLOW_OK) {
        fprintf(stderr, "g_signal_emit_by_name push-buffer error");
    }
    return;
}

GstFlowReturn new_sample_callback(GstAppSink* sink, gpointer data) {
    ThetaDriver* driver = static_cast<ThetaDriver*>(data);
    
    rclcpp::Time now = driver->get_clock()->now();
    bool needs_lowres = true;
    if (driver->target_framerate_ < 30.0) {
        double elapsed = (now - driver->last_publish_time_).seconds();
        if (elapsed < (1.0 / driver->target_framerate_)) {
            needs_lowres = false;
        }
    }

    bool needs_snapshot = false;
    if (driver->enable_snapshots_ && (driver->snapshot_pub_.getNumSubscribers() > 0 || !driver->snapshot_save_dir_.empty())) {
        if (driver->use_automatic_snapshots_) {
            double elapsed_snapshot = (now - driver->last_snapshot_time_).seconds();
            if (elapsed_snapshot >= (1.0 / driver->snapshot_target_framerate_)) {
                needs_snapshot = true;
            }
        }
        if (driver->force_snapshot_) {
            needs_snapshot = true;
        }
    }

    if (!needs_lowres && !needs_snapshot) {
        GstSample* drop_sample = gst_app_sink_pull_sample(sink);
        if (drop_sample) gst_sample_unref(drop_sample);
        return GST_FLOW_OK;
    }

    GstSample* sample = gst_app_sink_pull_sample(sink);
    if (sample == NULL) {
        return GST_FLOW_EOS;
    }

    GstBuffer* buffer = gst_sample_get_buffer(sample);
    
    // Read wall-clock timestamp preserved across decoder from DTS
    uint64_t capture_time_ns = GST_BUFFER_DTS(buffer);

    // Fallback if decoder cleared DTS: use current system time
    if (capture_time_ns == GST_CLOCK_TIME_NONE || capture_time_ns == 0) {
        capture_time_ns = driver->get_clock()->now().nanoseconds();
    }

    GstBuffer* app_buffer = gst_buffer_copy_deep(buffer);
    GstMapInfo map;
    gst_buffer_map(app_buffer, &map, GST_MAP_WRITE);

    // Pass map and exact capture timestamp to publisher
    driver->publishImage(map, capture_time_ns);

    gst_sample_unref(sample);
    gst_buffer_unmap(app_buffer, &map);
    gst_buffer_unref(app_buffer);
    return GST_FLOW_OK;
}

void ThetaDriver::publishImage(GstMapInfo map, uint64_t capture_time_ns) {
    int full_width = use4k_ ? 3840 : 1920;
    int full_height = use4k_ ? 1920 : 960;
    
    // Convert capture nanoseconds into a ROS Time object
    rclcpp::Time capture_stamp(capture_time_ns, RCL_ROS_TIME);
    rclcpp::Time system_now = this->get_clock()->now();

    cv::Mat full_frame(full_height, full_width, CV_8UC3, map.data);

    auto make_camera_info = [&](int width, int height) {
        auto info = std::make_unique<sensor_msgs::msg::CameraInfo>();
        info->header.stamp = capture_stamp; // Use hardware capture stamp
        info->header.frame_id = camera_frame_;
        info->width = width;
        info->height = height;
        info->distortion_model = "plumb_bob"; 

        double fx = width / 0.5;
        double fy = height / 0.5;
        double cx = width / 2.0;
        double cy = height / 2.0;

        info->k[0] = fx;  info->k[2] = cx;
        info->k[4] = fy;  info->k[5] = cy;
        info->k[8] = 1.0;

        info->p[0] = fx;  info->p[2] = cx;
        info->p[5] = fy;  info->p[6] = cy;
        info->p[10] = 1.0;

        return info;
    };

    // 1. Handle Lazy Snapshot Publishing (Full Resolution Layer)
    if (enable_snapshots_ && (snapshot_pub_.getNumSubscribers() > 0 || snapshot_info_pub_->get_subscription_count() > 0 || !snapshot_save_dir_.empty())) {
        double elapsed_snapshot = (capture_stamp - last_snapshot_time_).seconds();
        bool forced = force_snapshot_.exchange(false);
        if (forced || (use_automatic_snapshots_ && elapsed_snapshot >= (1.0 / snapshot_target_framerate_))) {

            snapshot_count_++;
            double pipeline_delay_ms = (system_now.seconds() - capture_stamp.seconds()) * 1000.0;
            
            // RCLCPP_INFO(get_logger(), 
            //             "[Snapshot #%lu] Captured: %.4f s | Written: %.4f s | Pipeline Latency: %.2f ms", 
            //             snapshot_count_, capture_stamp.seconds(), system_now.seconds(), pipeline_delay_ms);

            // Only publish to ROS if there are actual subscribers
            if (snapshot_pub_.getNumSubscribers() > 0 || snapshot_info_pub_->get_subscription_count() > 0) {
                auto snapshot_msg = std::make_unique<sensor_msgs::msg::Image>();
                snapshot_msg->header.stamp = capture_stamp; // True physical capture timestamp
                snapshot_msg->header.frame_id = camera_frame_;
                snapshot_msg->width = full_width;
                snapshot_msg->height = full_height;
                snapshot_msg->encoding = "rgb8";
                snapshot_msg->is_bigendian = false;
                snapshot_msg->step = full_width * 3;

                size_t full_size = snapshot_msg->step * snapshot_msg->height;
                snapshot_msg->data.resize(full_size);
                memcpy(snapshot_msg->data.data(), full_frame.data, full_size);

                snapshot_pub_.publish(*snapshot_msg);
                snapshot_info_pub_->publish(*make_camera_info(full_width, full_height));
            }

            // Save to disk asynchronously in a background thread
            if (!snapshot_save_dir_.empty()) {
                std::string filename = snapshot_save_dir_ + "/snapshot_" + std::to_string(capture_stamp.nanoseconds()) + ".jpg";
                
                // Clone the matrix (cheap reference copy with deep data) for background thread
                cv::Mat frame_to_save = full_frame.clone();

                // Spawn an asynchronous worker thread to write disk file without blocking callback
                std::thread([frame_to_save, filename, this, count = snapshot_count_]() {
                    cv::Mat bgr_frame;
                    cv::cvtColor(frame_to_save, bgr_frame, cv::COLOR_RGB2BGR);
                    cv::imwrite(filename, bgr_frame);
                    // RCLCPP_INFO(get_logger(), "[Snapshot #%lu] Disk write completed: %s", count, filename.c_str());
                }).detach();
            }

            // RCLCPP_INFO(get_logger(), "[Snapshot #%lu] Finished saving & publishing.", snapshot_count_);

            last_snapshot_time_ = capture_stamp;
        }
    }

    // 2. Handle Throttled Downscaled Stream Publishing
    double elapsed_lowres = (capture_stamp - last_publish_time_).seconds();
    if (target_framerate_ >= 30.0 || elapsed_lowres >= (1.0 / target_framerate_)) {
        cv::Mat final_frame;
        if (downscale_factor_ > 1) {
            int new_width = full_width / downscale_factor_;
            int new_height = full_height / downscale_factor_;
            cv::resize(full_frame, final_frame, cv::Size(new_width, new_height), 0, 0, cv::INTER_NEAREST);
        } else {
            final_frame = full_frame;
        }

        auto image = std::make_unique<sensor_msgs::msg::Image>();
        image->header.stamp = capture_stamp; // True physical capture timestamp
        image->header.frame_id = camera_frame_;
        image->width = final_frame.cols;
        image->height = final_frame.rows;
        image->encoding = "rgb8";
        image->is_bigendian = false;
        image->step = final_frame.cols * 3;

        size_t size = image->step * image->height;
        image->data.resize(size);
        memcpy(image->data.data(), final_frame.data, size);
        
        image_pub_.publish(*image);
        info_pub_->publish(*make_camera_info(final_frame.cols, final_frame.rows));
        last_publish_time_ = capture_stamp;
    }
}

ThetaDriver::ThetaDriver(const rclcpp::NodeOptions& options)
    : Node("theta_driver", options), 
      last_publish_time_(0, 0, RCL_ROS_TIME),
      last_snapshot_time_(0, 0, RCL_ROS_TIME) {
    RCLCPP_INFO(get_logger(), "Initializing");
    onInit();
}

ThetaDriver::~ThetaDriver() {
    if (streaming_) {
        gst_element_set_state(gsrc.pipeline, GST_STATE_NULL);
        g_source_remove(gsrc.bus_watch_id);
        uvc_stop_streaming(devh_);
        uvc_close(devh_);
        uvc_exit(ctx_);
    }
}

void ThetaDriver::onInit() {
    image_pub_ = image_transport::create_publisher(this, "image_raw", rmw_qos_profile_default);
    snapshot_pub_ = image_transport::create_publisher(this, "image_snapshot", rmw_qos_profile_default);

    info_pub_ = this->create_publisher<sensor_msgs::msg::CameraInfo>("camera_info", 10);
    snapshot_info_pub_ = this->create_publisher<sensor_msgs::msg::CameraInfo>("image_snapshot/camera_info", 10);

    declare_parameter<bool>("enable_snapshots", false);
    get_parameter("enable_snapshots", enable_snapshots_);
    declare_parameter<bool>("use_automatic_snapshots", true);
    get_parameter("use_automatic_snapshots", use_automatic_snapshots_);
    declare_parameter<bool>("use_distance_snapshots", false);
    get_parameter("use_distance_snapshots", use_distance_snapshots_);
    declare_parameter<bool>("use4k", false);
    get_parameter("use4k", use4k_);
    declare_parameter<int>("downscale_factor", 1);
    get_parameter("downscale_factor", downscale_factor_);
    declare_parameter<double>("target_framerate", 30.0);
    get_parameter("target_framerate", target_framerate_);
    declare_parameter<double>("snapshot_target_framerate", 1.0);
    get_parameter("snapshot_target_framerate", snapshot_target_framerate_);
    declare_parameter<std::string>("serial", "");
    get_parameter("serial", serial_);
    declare_parameter<std::string>("camera_frame", camera_frame_);
    get_parameter("camera_frame", camera_frame_);
    declare_parameter<std::string>("snapshot_save_dir", "");
    get_parameter("snapshot_save_dir", snapshot_save_dir_);

    // Pipeline tuned to force max-buffers=1 and drop leaky frames (Eliminates camera lag)
    pipeline_ =
        "appsrc name=ap max-buffers=2 leaky=2 ! "
        "h264parse ! "
        "nvv4l2decoder ! video/x-raw(memory:NVMM) ! "
        "nvvidconv ! video/x-raw,format=BGRx ! "
        "videoconvert ! video/x-raw,format=RGB ! "
        "appsink name=appsink emit-signals=true max-buffers=1 drop=true";
    declare_parameter<std::string>("pipeline", pipeline_);
    get_parameter("pipeline", pipeline_);

    trigger_snapshot_srv_ = create_service<std_srvs::srv::Trigger>(
        "trigger_snapshot",
        std::bind(&ThetaDriver::handleTriggerSnapshot, this, std::placeholders::_1, std::placeholders::_2));

    // --- CONFIGURATION PRINTS ---
    RCLCPP_INFO(get_logger(), "===============================================");
    RCLCPP_INFO(get_logger(), "  Theta 360 Camera Driver Configuration ");
    RCLCPP_INFO(get_logger(), "===============================================");
    RCLCPP_INFO_STREAM(get_logger(), " * Enable Snapshots   : " << (enable_snapshots_ ? "True" : "False"));
    RCLCPP_INFO_STREAM(get_logger(), " * Automatic Snapshots: " << (use_automatic_snapshots_ ? "True" : "False"));
    RCLCPP_INFO_STREAM(get_logger(), " * Distance Snapshots : " << (use_distance_snapshots_ ? "True" : "False"));
    RCLCPP_INFO_STREAM(get_logger(), " * Resolution Mode    : " << (use4k_ ? "4K (3840x1920)" : "FHD (1920x960)"));
    RCLCPP_INFO_STREAM(get_logger(), " * Downscale Factor   : " << downscale_factor_ 
                                     << " (Output: " << (use4k_ ? 3840 : 1920) / downscale_factor_ << "x" 
                                     << (use4k_ ? 1920 : 960) / downscale_factor_ << ")");
    RCLCPP_INFO_STREAM(get_logger(), " * Target Framerate   : " << target_framerate_ << " FPS");
    RCLCPP_INFO_STREAM(get_logger(), " * Snapshot Max Rate  : " << snapshot_target_framerate_ << " FPS (Lazy)");
    RCLCPP_INFO_STREAM(get_logger(), " * Camera Frame ID    : " << camera_frame_);
    RCLCPP_INFO_STREAM(get_logger(), " * Target Serial      : " << (serial_.empty() ? "First available device" : serial_));
    RCLCPP_INFO_STREAM(get_logger(), " * Snapshot Save Dir  : " << (snapshot_save_dir_.empty() ? "Disabled" : snapshot_save_dir_));
    RCLCPP_INFO(get_logger(), "===============================================");

    rclcpp::Rate rate(1);
    while (rclcpp::ok()) {
        bool ok = init();
        if (ok) {
            break;
        }
        else {
            RCLCPP_ERROR(get_logger(), "Initialization failed");
        }
        rate.sleep();
        RCLCPP_WARN(get_logger(), "retry");
    }
}

void ThetaDriver::handleTriggerSnapshot(
    const std::shared_ptr<std_srvs::srv::Trigger::Request> /*request*/,
    std::shared_ptr<std_srvs::srv::Trigger::Response> response) {
    if (!enable_snapshots_ || !use_distance_snapshots_) {
        response->success = false;
        response->message = "Distance-based snapshots are disabled (enable_snapshots/use_distance_snapshots)";
        return;
    }

    // Capture happens asynchronously on the next GStreamer sample; this only confirms the
    // request was accepted, not that the frame has been written to disk yet.
    force_snapshot_ = true;
    response->success = true;
    response->message = "Snapshot request accepted";
}

bool ThetaDriver::open() {
    uvc_error_t res;
    uvc_device_t** devlist;

    res = uvc_init(&ctx_, NULL);
    if (res != UVC_SUCCESS) {
        RCLCPP_ERROR_STREAM(get_logger(), "uvc_init failed");
        return false;
    }

    res = thetauvc_find_devices(ctx_, &devlist);
    if (res != UVC_SUCCESS) {
        uvc_perror(res, "find_thetauvc_device error");
        uvc_exit(ctx_);
        return false;
    }

    unsigned int idx = 0;
    while (devlist[idx] != NULL) {
        uvc_device_descriptor_t* desc;

        if (uvc_get_device_descriptor(devlist[idx], &desc) == UVC_SUCCESS) {
            RCLCPP_INFO_STREAM(get_logger(), "index: " << idx);
            if (desc->product) {
                RCLCPP_INFO_STREAM(get_logger(), "product: " << desc->product);
            }
            if (desc->serialNumber) {
                RCLCPP_INFO_STREAM(get_logger(), "serial: " << desc->serialNumber);
            }
            if (serial_.empty() || serial_ == std::string(desc->serialNumber)) {
                uvc_device_t* dev;
                thetauvc_find_device(ctx_, &dev, idx);
                uvc_open(dev, &devh_);
                uvc_free_device_descriptor(desc);
                uvc_free_device_list(devlist, 1);

                if (use4k_) {
                    thetauvc_get_stream_ctrl_format_size(devh_, THETAUVC_MODE_UHD_2997, &ctrl_);
                }
                else {
                    thetauvc_get_stream_ctrl_format_size(devh_, THETAUVC_MODE_FHD_2997, &ctrl_);
                }
                return true;
            }
            else {
                uvc_free_device_descriptor(desc);
            }
        }
        idx++;
    }
    return false;
}

bool ThetaDriver::init() {
    streaming_ = false;
    if (!gst_is_initialized()) {
        gst_init(0, 0);
    }

    GError* error = NULL;
    gsrc.framecount = 0;
    gsrc.loop = g_main_loop_new(NULL, TRUE);
    gsrc.timer = g_timer_new();
    gsrc.pipeline = gst_parse_launch(pipeline_.c_str(), &error);
    if (gsrc.pipeline == NULL) {
        RCLCPP_FATAL_STREAM(get_logger(), error->message);
        g_error_free(error);
        return false;
    }
    gst_pipeline_set_clock(GST_PIPELINE(gsrc.pipeline), gst_system_clock_obtain());
    gsrc.appsrc = gst_bin_get_by_name(GST_BIN(gsrc.pipeline), "ap");

    GstCaps* caps = gst_caps_new_simple("video/x-h264",
                                        "framerate", GST_TYPE_FRACTION, 30000, 1001,
                                        "stream-format", G_TYPE_STRING, "byte-stream",
                                        "profile", G_TYPE_STRING, "constrained-baseline", NULL);
    gst_app_src_set_caps(GST_APP_SRC(gsrc.appsrc), caps);

    GstBus* bus = gst_pipeline_get_bus(GST_PIPELINE(gsrc.pipeline));
    gsrc.bus_watch_id = gst_bus_add_watch(bus, gst_bus_callback, NULL);
    gst_object_unref(bus);

    GstElement* appsink = gst_bin_get_by_name(GST_BIN(gsrc.pipeline), "appsink");
    if (appsink == NULL) {
        g_print("appsink is NULL\n");
    } else {
        g_object_set(G_OBJECT(appsink), "drop", TRUE, "max-buffers", 1, "sync", FALSE, NULL);
    }
    g_signal_connect(appsink, "new-sample", G_CALLBACK(new_sample_callback), this);
    gst_object_unref(appsink);

    bool ok = open();
    if (!ok) {
        RCLCPP_FATAL(get_logger(), "Device open error");
        return false;
    }

    gsrc.dwFrameInterval = ctrl_.dwFrameInterval;
    gsrc.dwClockFrequency = ctrl_.dwClockFrequency;
    if (gst_element_set_state(gsrc.pipeline, GST_STATE_PLAYING) == GST_STATE_CHANGE_FAILURE) {
        RCLCPP_FATAL(get_logger(), "Could not start streaming");
        return false;
    }

    RCLCPP_INFO_STREAM(get_logger(), "Start streaming");
    uvc_error_t res = uvc_start_streaming(devh_, &ctrl_, uvc_streaming_callback, &gsrc, 0);
    if (res != UVC_SUCCESS) {
        RCLCPP_ERROR(get_logger(), "uvc_start_streaming: failed");
    }
    else {
        streaming_ = true;
    }
    return res == UVC_SUCCESS;
}

} // namespace theta_driver

#include "rclcpp_components/register_node_macro.hpp"
RCLCPP_COMPONENTS_REGISTER_NODE(theta_driver::ThetaDriver)