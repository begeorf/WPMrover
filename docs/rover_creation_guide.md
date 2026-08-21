# Rover Developer Setup Guide

## Automation

### Creating Shell and service files
create all the .sh, .service files

make all the .sh files executable:
`sudo chmod +x /[path to file]/[file name]`

### Adding wifi networks
use this terminal command
```
nmcli connection add \
  type wifi \
  con-name "YOUR_WIFI_NAME" \
  ssid "YOUR_WIFI_NAME" \
  wifi-sec.key-mgmt wpa-psk \
  wifi-sec.psk "YOUR_WIFI_PASSWORD"
```
```
nmcli connection add \
  type wifi \
  con-name "HoustonRouter" \
  ssid "TP-Link_1C90" \
  wifi-sec.key-mgmt wpa-psk \
  wifi-sec.psk "84795120"
```
```
nmcli connection add \
  type wifi \
  con-name "WPMGuest" \
  ssid "" \
  wifi-sec.key-mgmt wpa-psk \
  wifi-sec.psk "84795120"
```

### Adding network for lidar

## Step by step each action I take
### 1. Connecting to Wifi
- boot
- login: password = 'rover'
- check linux distro
  - the distro is ubuntu 24.04
```
lsb_release -a
# or 
cat /etc/os-release
```
- find mac address `ip link show`
  - look for the value under wlP1p0 or smt like that
  - DC Rover MAC Address: `B4-6B-FC-37-22-29`
  - Houston Rover MAC Address: `34:e1:2d:98:b9:7b`
- add to network if needed
- workaround to get firefox
- download .tar version of firefox for arm64 to a thumb drive
- on the orin, need to adjust the date and time first
  - `sudo timedatectl set-timezone America/Detroit`
  - `sudo date -s "YYYY-MM-DD HH:MM:SS"`
- once date is synced, run `tar -xvf /media/rover/[usb stick name]/[firefox*.tar.xz]`
  - for example: `tar -xvf /media/rover/USB\ DISK/firefox-154.0.tar.xz`
- launch firefox `~/firefox/firefox &`
- make date and time sync on boot
```
sudo date -s "YYYY-MM-DD HH:MM:SS"
sudo apt update && sudo apt install -y fake-hwclock
sudo fake-hwclock save
sudo systemctl enable --now systemd-timesyncd
sudo timedatectl set-ntp true
sudo timedatectl set-timezone America/Detroit
```
- verify they sync on boot
```
timedatectl status
# this should be the current time

sudo systemctl restart systemd-timesyncd

sudo systemctl restart NetworkManager

timedatectl status
               Local time: Thu 2026-08-20 10:39:19 EDT
           Universal time: Thu 2026-08-20 14:39:19 UTC
                 RTC time: Thu 2026-08-20 14:39:20
                Time zone: America/Detroit (EDT, -0400)
System clock synchronized: yes
              NTP service: active
          RTC in local TZ: no
rover@rover:~/rover_workspace$ 
```
- Add lidar network
```sudo nmcli con add type ethernet con-name "lidar" ip4 192.168.1.102/24 gw4 "" ipv4.method manual```
- Connect to a network


- Connect to MWireless
  - useful website: https://documentation.its.umich.edu/content/wifi-manually-configuring-your-ubuntu-linux-device-mwireless1
  - the file at `/etc/ssl/certs/USERTrust_RSA_Certification_Authority.pem` already exists
- Save IP address and network for SSHing in the future
  - In the WiFi settings menu GUI, click the gear icon on the network you want to view
  - Under the "Details" tab, find the value lised as `IPv4 Address
    - Houston, MGuest, `35.0.28.71`
    - Houston, MWireless, `35.3.34.131`
    - DC, MWireless, `35.3.94.23`


- Copy repo
  - ssh in
  - `sudo apt update && sudo apt install tree`
  - `cd ~/rover_workspace`
  - `mkdir tmp && cd tmp`
  - git clone all the stuff
  - Compare diff of old and new
    - ignore .pyc files
    - copy over any .pt version of cv models
    - make the models, small, nano directories
    - everythign above here is both rovers, everything below is HOUSTON only
    - compile them
      - 

Everything above this line is done on both rovers
---
Everythign below the line is only done on the Houston Rover
- Compile YOLO models
  ```
  # 1. Install pip package manager
  sudo apt update && sudo apt install -y python3-pip

  # 2. Install Ultralytics and version-matched core dependencies
  pip3 install ultralytics "numpy<2" "opencv-python<4.10" --break-system-packages

  # 3. Add local binary path to PATH and reload shell configuration
  echo 'export PATH=$PATH:~/.local/bin' >> ~/.bashrc
  source ~/.bashrc

  # 4. Install ONNX parsing and slimming tools
  pip3 install "onnx~=1.21.0" onnxslim "onnxruntime~=1.24.2" --break-system-packages

  # 5. Install TensorRT runtime bindings
  pip3 install tensorrt --break-system-packages

  # 6. Install NVIDIA ModelOpt for FP16 auto-casting during export
  pip3 install "nvidia-modelopt[onnx]>=0.44" --break-system-packages

  # 7. Navigate to your model directory and perform the export on nano model
  cd ~/rover_workspace/WPMrover/src/perception/models/nano/
  yolo export model=ConcreteModel1_YOLO_nano.pt format=engine device=0 quantize=True

  # 8. Navigate to your model directory and perform the export on small model
  cd ~/rover_workspace/WPMrover/src/perception/models/small/
  yolo export model=ConcreteModel1_YOLO_small.pt format=engine device=0 quantize=True
  ```
- Build workspace
  - first get the zed camera SDK
  - At the time of writing, the zed ros wrapper only supports up to v5.3
  - check jetpack version on Orin
    `apt-cache show nvidia-jetpack`
    - download the one that matches this on zed website
  - [personal compuater terminal] Get the SDK intstaller onto the Rover's computer 
  ```
  cd ~/Downloads
  scp ZED_SDK_Tegra_L4T38.4_v5.3.1.zstd.run rover@35.3.34.131:~/
  ```
  - [Rover terminal] Run the SDK
  ```
  cd ~/
  chmod +x ZED_SDK_Tegra_L4T38.2_v5.3.1.zstd.run 
  ./ZED_SDK_Tegra_L4T38.2_v5.3.1.zstd.run 
  ```
  - There will be a bunch of dialogue boxes
  ```
  WARNING : possibly unsupported Linux 4 Tegra version, Continue  [Y/n] ? y

  To continue you have to accept the EULA. Accept  [Y/n] ? y

  [sudo] password for rover: rover

  Install samples (recommended) [Y/n] ? n

  Do you want to auto-install dependencies (recommended) ? following packet will be installed via the package manager : libjpeg-turbo8 libturbojpeg libusb-1.0-0 libusb-1.0-0-dev libopenblas-dev libarchive-dev libv4l-0 curl unzip zlib1g mesa-utils udev libpng-dev python3-dev python3-pip python3-setuptools qtbase5-dev qtchooser qt5-qmake qtbase5-dev-tools libqt5opengl5 libqt5svg5 [Y/n] ? YES

  Do you want to install the Python API (recommended) [Y/n] ? y

  Please specify your python executable: python3

  Do you want to download and optimize the NEURAL Depth models now? These will be required at runtime and will be processed then if not done now, which will extend startup time on first use. [Y/n] ? y

  Do you want to run the ZED Diagnostic to download all AI models [Y/n] ?n

  ```
  - follow the prompts and download newest CUDA Version if necessary (Houston Rover has CUDA 13.2 now)
  - clone zed interfaces
    - `git clone https://github.com/stereolabs/zed-ros2-interfaces.git`
  - installl dependencies
  ```
  cd ~/rover_workspace/WPMrover
  rosdep update
  rosdep install --from-paths src --ignore-src -r -y

  # Clean and rebuild the workspace
  colcon build --symlink-install
  ```
  - install nympy c headers
  `sudo apt update && sudo apt install -y python3-numpy python3-dev`
  - install cv bridge library
  `sudo apt update && sudo apt install -y ros-$ROS_DISTRO-cv-bridge`
    - add to cmake lists.txt in theta driver
    ```
    ament_target_dependencies(theta_driver_lib
      ${dependencies}
      image_transport
      OpenCV
      Boost
      cv_bridge
    )
    ```
    - change header file name of equirect_to_cloud_node.cpp
    ```
    # from
    #include <cv_bridge/cv_bridge.h>
    # to
    #include <cv_bridge/cv_bridge.hpp>
    ```
  - build the workspace
  ```colcon build --symlink-install```
  - Make zzzsnapshots directory
  - Forward the port `8765`
  - organize directory structure
  ```
  cd ~/rover_workspace
  rm -rf build install log src
  mv WPMrover/{*,.*} . 2>/dev/null || true
  rmdir WPMrover
  ```
  - rebuild
  `rm -rf build install log` `colcon build --symlink-install`

- Install tailscale
```
curl -fsSL https://tailscale.com/install.sh | sh
```
- Activate: `sudo tailscale up`
- Houston tailscale IP: `100.97.144.107`
  

