#!/bin/bash
# this file is located at /home/rover/start_rover.sh
# Clean startup script for systemd boot service

LOG_FILE="/tmp/robot_startup.log"
YOLO_ENGINE="/home/rover/rover_workspace/src/perception/models/small/ConcreteModel1_YOLO_small.engine"

echo "=== [$(date)] Robot Startup Initiated ===" > "$LOG_FILE"

# 1. Source ROS 2 and Workspace Environments
source /opt/ros/humble/setup.bash
source /home/rover/rover_workspace/install/setup.bash

export PYTHONUNBUFFERED=1
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# 2. Kill any stale processes or lock files from previous runs
pkill -9 -f "ros2|launch|component_container|zed|bno055|rslidar|roverrobotics|foxglove" 2>/dev/null || true
fuser -k 8765/tcp 2>/dev/null || true

# 3. Launch Orchestrator in IDLE mode
# (Orchestrator brings up Foxglove Bridge + Hardware + robot_manager)
stdbuf -oL -eL ros2 launch rover_orchestrator orchestrator_launch.py \
    yolo_engine_path:="$YOLO_ENGINE" >> "$LOG_FILE" 2>&1