#!/usr/bin/env python3
import sys
import os
import math

# ROS 2 Bag Reader API Libraries
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

# Import specific message types we want to parse
from sensor_msgs.msg import Imu
from nav_msgs.msg import Odometry

def quaternion_to_yaw(w, x, y, z):
    """Converts orientation quaternions directly to a continuous Radian heading."""
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)

def analyze_bag(bag_path):
    serialization_format = 'cdr'
    storage_options = rosbag2_py.StorageOptions(uri=bag_path, storage_id='sqlite3') 
    converter_options = rosbag2_py.ConverterOptions(
        input_serialization_format=serialization_format,
        output_serialization_format=serialization_format
    )
    
    reader = rosbag2_py.SequentialReader()
    try:
        reader.open(storage_options, converter_options)
    except Exception as e:
        print(f"Error opening bag: {e}")
        return
    
    topic_types = {topic.name: topic.type for topic in reader.get_all_topics_and_types()}

    # State tracking variables for time deltas
    last_imu_data_stamp = None
    last_imu_raw_stamp = None
    
    # Accumulated integration results
    accumulated_imu_data_rad = 0.0
    accumulated_imu_raw_rad = 0.0
    initial_timestamp = None
    
    # Unwrapping markers for Quaternion tracks
    last_ekf_yaw = None
    unwrapped_ekf_yaw = 0.0
    
    last_wheel_yaw = None
    unwrapped_wheel_yaw = 0.0
    
    csv_data = []
    print(f"Reading data packets from sqlite3 rosbag: {bag_path}")
    
    while reader.has_next():
        (topic, data, t) = reader.read_next()
        
        if initial_timestamp is None:
            initial_timestamp = t
            
        elapsed_seconds = (t - initial_timestamp) * 1e-9
        
        if topic not in topic_types:
            continue
            
        msg_type = get_message(topic_types[topic])
        msg = deserialize_message(data, msg_type)
        
        # 1. PROCESS IMU/DATA (INTEGRATION METHOD)
        if topic == "/imu/data":
            current_stamp = msg.header.stamp.sec + (msg.header.stamp.nanosec * 1e-9)
            vel_z = msg.angular_velocity.z
            
            if last_imu_data_stamp is not None:
                dt = current_stamp - last_imu_data_stamp
                if 0 < dt < 1.0:
                    accumulated_imu_data_rad += vel_z * dt
                    csv_data.append({
                        'time': elapsed_seconds,
                        'source': 'IMU_Data',
                        'degrees': math.degrees(accumulated_imu_data_rad)
                    })
            last_imu_data_stamp = current_stamp
            
        # 2. PROCESS IMU_RAW (INTEGRATION METHOD)
        elif topic == "/imu_raw":
            current_stamp = msg.header.stamp.sec + (msg.header.stamp.nanosec * 1e-9)
            vel_z = msg.angular_velocity.z
            
            if last_imu_raw_stamp is not None:
                dt = current_stamp - last_imu_raw_stamp
                if 0 < dt < 1.0:
                    accumulated_imu_raw_rad += vel_z * dt
                    csv_data.append({
                        'time': elapsed_seconds,
                        'source': 'IMU_Raw',
                        'degrees': math.degrees(accumulated_imu_raw_rad)
                    })
            last_imu_raw_stamp = current_stamp
            
        # 3. PROCESS FUSED EKF ODOMETRY DATA
        elif topic == "/odometry/filtered":
            q = msg.pose.pose.orientation
            current_raw_yaw = quaternion_to_yaw(q.w, q.x, q.y, q.z)
            
            if last_ekf_yaw is not None:
                delta_yaw = current_raw_yaw - last_ekf_yaw
                if delta_yaw > math.pi:    delta_yaw -= 2.0 * math.pi
                elif delta_yaw < -math.pi: delta_yaw += 2.0 * math.pi
                unwrapped_ekf_yaw += delta_yaw
            else:
                unwrapped_ekf_yaw = current_raw_yaw
                
            csv_data.append({
                'time': elapsed_seconds,
                'source': 'EKF_Odom',
                'degrees': math.degrees(unwrapped_ekf_yaw)
            })
            last_ekf_yaw = current_raw_yaw

        # 4. PROCESS RAW WHEEL ODOMETRY
        elif topic == "/odometry/wheels":
            q = msg.pose.pose.orientation
            current_raw_yaw = quaternion_to_yaw(q.w, q.x, q.y, q.z)
            
            if last_wheel_yaw is not None:
                delta_yaw = current_raw_yaw - last_wheel_yaw
                if delta_yaw > math.pi:    delta_yaw -= 2.0 * math.pi
                elif delta_yaw < -math.pi: delta_yaw += 2.0 * math.pi
                unwrapped_wheel_yaw += delta_yaw
            else:
                unwrapped_wheel_yaw = current_raw_yaw
                
            csv_data.append({
                'time': elapsed_seconds,
                'source': 'Raw_Wheel',
                'degrees': math.degrees(unwrapped_wheel_yaw)
            })
            last_wheel_yaw = current_raw_yaw

    if not csv_data:
        print("\nError: No valid messages processed.")
        return

    # Extract final points safely
    imu_data_final = [d['degrees'] for d in csv_data if d['source'] == 'IMU_Data']
    imu_raw_final = [d['degrees'] for d in csv_data if d['source'] == 'IMU_Raw']
    ekf_final = [d['degrees'] for d in csv_data if d['source'] == 'EKF_Odom']
    wheel_final = [d['degrees'] for d in csv_data if d['source'] == 'Raw_Wheel']

    final_imu_data = imu_data_final[-1] if imu_data_final else 0.0
    final_imu_raw = imu_raw_final[-1] if imu_raw_final else 0.0
    final_ekf = ekf_final[-1] if ekf_final else 0.0
    final_wheel = wheel_final[-1] if wheel_final else 0.0

    print(f"\n--- SPIN LOG PROCESSING COMPLETE ---")
    print(f"Final Integrated /imu/data:          {final_imu_data:.2f}°")
    print(f"Final Integrated /imu_raw:           {final_imu_raw:.2f}°")
    print(f"Final Raw Wheel Odometry:            {final_wheel:.2f}°")
    print(f"Final Unwrapped EKF Filter Odom:     {final_ekf:.2f}°")
    print(f"------------------------------------")

    # ----------------------------------------------------
    # DETAILED ERROR REPORTING SECTION
    # ----------------------------------------------------
    try:
        print("\n[Input Required]")
        user_input = input("Enter the physical ground truth rotation in DEGREES (e.g. 360, 1080): ")
        ground_truth = float(user_input)
    except ValueError:
        print("Invalid input. Bypassing calculations.")
        ground_truth = None

    if ground_truth is not None:
        denominator = ground_truth if ground_truth != 0 else 1.0
        
        print(f"\n====================================================================")
        print(f"            GROUND TRUTH ERROR REPORT (Target: {ground_truth:.1f}°)")
        print(f"====================================================================")
        
        # 1. /imu/data
        if imu_data_final:
            err = final_imu_data - ground_truth
            pct = (abs(err) / abs(denominator)) * 100.0
            print(f"Integrated /imu/data:     Error: {err:+.2f}°  |  Pct Error: {pct:.2f}%")
            
        # 2. /imu_raw
        if imu_raw_final:
            err = final_imu_raw - ground_truth
            pct = (abs(err) / abs(denominator)) * 100.0
            print(f"Integrated /imu_raw:      Error: {err:+.2f}°  |  Pct Error: {pct:.2f}%")
            
        # 3. Raw Wheels
        if wheel_final:
            err = final_wheel - ground_truth
            pct = (abs(err) / abs(denominator)) * 100.0
            print(f"Raw Wheel Odometry:       Error: {err:+.2f}°  |  Pct Error: {pct:.2f}%")
            
        # 4. Fused EKF
        if ekf_final:
            err = final_ekf - ground_truth
            pct = (abs(err) / abs(denominator)) * 100.0
            print(f"Fused EKF State:          Error: {err:+.2f}°  |  Pct Error: {pct:.2f}%")
        print(f"====================================================================")

    # ----------------------------------------------------
    # CSV DATA DUMP
    # ----------------------------------------------------
    output_csv = "spin_test_results.csv"
    try:
        with open(output_csv, 'w') as f:
            f.write("elapsed_time_sec,sensor_source,accumulated_degrees\n")
            for row in csv_data:
                f.write(f"{row['time']:.4f},{row['source']},{row['degrees']:.2f}\n")
        print(f"\nDetailed timeline trace exported to: {output_csv}")
    except Exception as e:
        print(f"Failed to write CSV: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_spins.py rosbag2_xxx/")
        sys.exit(1)
        
    analyze_bag(sys.argv[1])