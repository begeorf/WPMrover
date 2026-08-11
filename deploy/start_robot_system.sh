#!/bin/bash
# Rover Zero Main Robot Orchestrator
# Loads the Humble environment and launches orchestrator_launch.py.

# --- CONFIGURATION ---
LOG_FILE="/tmp/robot_startup.log"
LAUNCH_FILE="/home/rover/rover_workspace/src/rover_orchestrator/launch/orchestrator_launch.py"
YOLO_ENGINE="/home/rover/rover_workspace/src/perception/models/small/ConcreteModel1_YOLO_small.engine"
ENV_LOADER="/home/rover/rover_workspace/robot_env_loader.sh"
# ---------------------

# Redirect standard output and error to log file while outputting to stdout
exec > >(tee -a ${LOG_FILE}) 2>&1
``
echo "--- [$(date)] Rover System Startup Initiated ---"

# 1. Load the ROS 2 Humble Environment & CUDA Paths
if [ -f "$ENV_LOADER" ]; then
    source "$ENV_LOADER"
    echo "Environment loaded successfully."
else
    echo "ERROR: Environment loader not found at $ENV_LOADER"
    exit 1
fi

# 2. Launch Main ROS 2 Orchestrator (Foxglove Bridge runs natively inside this launch file)
echo "Launching orchestrator: $LAUNCH_FILE"
echo "  yolo_engine_path: $YOLO_ENGINE"

exec ros2 launch "$LAUNCH_FILE" yolo_engine_path:=$YOLO_ENGINE
