how to make robot_startup.service run on boot; run this command in terminal
`sudo systemctl enable robot_startup.service`

how to start robot_startup.service manually
`sudo systemctl start robot_startup.service`

how to stop manually
`sudo systemctl stop robot_startup.service`

how to stop just the sh file
killall -9 ros2 launch_daemon python3
sudo pkill -9 -f "roverrobotics|bno055|theta_driver|joint_state_publisher"
sudo pkill -9 -f "component_container|zed_node|robot_state_publisher|rslidar|roverrobotics|bno055|foxglove|ros2|yolo|camera"