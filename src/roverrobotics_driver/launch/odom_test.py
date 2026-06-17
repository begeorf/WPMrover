#!/usr/bin/env python3

import sys
import time
import rclpy
from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult

def create_pose(navigator, x, y, yaw_deg):
    """Helper function to build a PoseStamped destination."""
    pose = PoseStamped()
    pose.header.frame_id = 'map'
    pose.header.stamp = navigator.get_clock().now().to_msg()
    pose.pose.position.x = float(x)
    pose.pose.position.y = float(y)
    
    # Convert Yaw Degrees to Quaternion Orientation
    import math
    yaw_rad = math.radians(yaw_deg)
    pose.pose.orientation.z = math.sin(yaw_rad / 2.0)
    pose.pose.orientation.w = math.cos(yaw_rad / 2.0)
    return pose

def execute_pattern(navigator, pattern_poses):
    """Iterates through a list of poses, commanding the robot to each step."""
    for i, target_pose in enumerate(pattern_poses):
        print(f"\n[Odom Test] Sending Waypoint {i+1}/{len(pattern_poses)}...")
        navigator.goToPose(target_pose)

        # Monitor progress until the robot reaches the destination
        while not navigator.isTaskComplete():
            feedback = navigator.getFeedback()
            if feedback and i % 5 == 0:
                print(f"Distance remaining: {feedback.distance_remaining:.2f} meters.")
            time.sleep(0.5)

        # Evaluate the arrival state
        result = navigator.getResult()
        if result == TaskResult.SUCCEEDED:
            print(f"[Odom Test] Waypoint {i+1} Reached Successfully!")
            time.sleep(1.5)  # Let the robot stabilize at the checkpoint
        elif result == TaskResult.CANCELED:
            print("[Odom Test] Task was canceled! Exiting.")
            sys.exit(1)
        elif result == TaskResult.FAILED:
            print("[Odom Test] Planning/Execution failed to waypoint. Exiting.")
            sys.exit(1)

def main():
    rclpy.init()
    navigator = BasicNavigator()

    # Define test parameters
    # Adjust these numbers depending on your room size!
    SQUARE_SIDE_METERS = 2.0  
    STRAIGHT_LINE_METERS = .605

    print("Waiting for Nav2 Lifecycle Servers to become active...")
    # BYPASS: Manually check the action server instead of waiting for AMCL lifecycle node
    # This checks if the core Nav2 navigation action engine is listening
    action_client = navigator.nav_to_pose_client
    print("Waiting for /navigate_to_pose action server to respond...")
    
    server_ready = False
    for retry in range(10):
        if action_client.wait_for_server(timeout_sec=1.0):
            server_ready = True
            break
            
    if not server_ready:
        print("\n[ERROR] Nav2 action server is not running yet.")
        print("Please verify your main terminal says 'Managed nodes are active' before running this script.")
        sys.exit(1)
        
    print("Nav2 Action Server Detected! Navigation stack is ready.")
    print("\nPlease select your pattern:")
    print("1: Straight Line Path (Out and Back)")
    print("2: Square Loop Path (Odom Drift Benchmark)")
    
    choice = input("Enter pattern choice (1 or 2): ").strip()

    waypoints = []

    if choice == '1':
        print(f"Configuring Straight Line Test: {STRAIGHT_LINE_METERS} meters.")
        # Step 1: Move forward straight
        waypoints.append(create_pose(navigator, STRAIGHT_LINE_METERS, 0.0, 0.0))
        # Step 2: Return back to origins
        # waypoints.append(create_pose(navigator, 0.0, 0.0, 0.0))

    elif choice == '2':
        print(f"Configuring Square Loop Test: {SQUARE_SIDE_METERS}x{SQUARE_SIDE_METERS} meters.")
        # Corner 1: Drive forward on X axis
        waypoints.append(create_pose(navigator, SQUARE_SIDE_METERS, 0.0, 90.0))
        # Corner 2: Move left on Y axis
        waypoints.append(create_pose(navigator, SQUARE_SIDE_METERS, SQUARE_SIDE_METERS, 180.0))
        # Corner 3: Drive backward parallel to start
        waypoints.append(create_pose(navigator, 0.0, SQUARE_SIDE_METERS, 270.0))
        # Corner 4: Return exactly to origin spot (0,0)
        waypoints.append(create_pose(navigator, 0.0, 0.0, 0.0))
    else:
        print("Invalid option. Exiting.")
        sys.exit(1)

    print("\nStarting execution pattern. Watch your robot!")
    execute_pattern(navigator, waypoints)
    
    print("\n[Odom Test] Pattern Finished! Check your physical markings.")
    rclpy.shutdown()

if __name__ == '__main__':
    main()