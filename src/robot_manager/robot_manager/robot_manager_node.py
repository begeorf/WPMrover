#!/usr/bin/env python3

import enum
import json
import os
import signal
import subprocess
import threading
import time
from typing import IO, Dict, List, Optional  # List used in _kill_descendants

import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from rclpy.node import Node
from std_msgs.msg import Int32, String
from std_srvs.srv import Trigger


class ManagerState(enum.Enum):
    """Lifecycle states for the robot_manager state machine."""

    IDLE = "IDLE"
    NAV_STARTING = "NAV_STARTING"
    NAV_RUNNING = "NAV_RUNNING"
    MAP_STARTING = "MAP_STARTING"
    MAP_RUNNING = "MAP_RUNNING"
    STOPPING = "STOPPING"


class RobotManagerNode(Node):
    """Pipeline orchestration and health monitor for MAX-Brain.

    Boots to IDLE. Accepts Foxglove service calls to start navigation or 3D mapping
    pipelines, enforces mutual exclusion, and reports system state via /diagnostics
    and /robot_manager/status.

    Health monitoring uses count_publishers() graph queries — no topic subscriptions
    on high-bandwidth streams. One subscription to /diagnostics collects driver-level
    health at ~1 Hz. State transitions require both grace period elapsed AND key
    topic publishers present.
    """

    _NAV_GRACE_SEC = 45.0
    _MAP_GRACE_SEC = 15.0

    def __init__(self) -> None:
        # Node must be initialized first before accessing self.get_logger()
        super().__init__("robot_manager")
        self.get_logger().info("[DEBUG] Initializing RobotManagerNode...")

        self.declare_parameter("yolo_engine_path", "")
        self.declare_parameter("pcd_save_dir", "~/maps/pointlio")
        self.declare_parameter("health_check_hz", 1.0)
        self.declare_parameter("status_publish_hz", 2.0)

        # State
        self._state = ManagerState.IDLE
        self._state_lock = threading.Lock()
        self._pipeline_proc: Optional[subprocess.Popen] = None
        self._pipeline_pgid: Optional[int] = None
        self._pipeline_log: Optional[IO] = None
        self._state_entry_time: float = time.monotonic()
        self._start_time: float = time.monotonic()
        self._last_error: str = ""

        # Cached diagnostics from /diagnostics subscriber (driver-level health)
        self._driver_diagnostics: Dict[str, str] = {}
        self._driver_diag_lock = threading.Lock()

        # Single lightweight subscription — /diagnostics only (~1 Hz, small text payload)
        self.create_subscription(DiagnosticArray, "/diagnostics", self._external_diag_cb, 10)

        # Publishers
        self._status_pub = self.create_publisher(String, "/robot_manager/status", 10)
        self._pipeline_state_pub = self.create_publisher(Int32, "/robot_manager/pipeline_state", 10)
        self._diag_pub = self.create_publisher(DiagnosticArray, "/diagnostics", 10)

        # Services
        self.get_logger().info("[DEBUG] Creating ROS 2 services...")
        self.create_service(Trigger, "/robot_manager/start_navigation", self._start_navigation_cb)
        self.create_service(Trigger, "/robot_manager/start_mapping", self._start_mapping_cb)
        self.create_service(Trigger, "/robot_manager/stop_pipeline", self._stop_pipeline_cb)
        self.create_service(Trigger, "/robot_manager/enable_dev", self._start_development_cb)

        # Timers
        health_hz: float = self.get_parameter("health_check_hz").value
        status_hz: float = self.get_parameter("status_publish_hz").value
        self.create_timer(1.0 / health_hz, self._health_check_loop)
        self.create_timer(1.0 / status_hz, self._publish_status)
        self.create_timer(1.0 / status_hz, self._watchdog_loop)

        self.get_logger().info("robot_manager started — state: IDLE")
        self.get_logger().info("[DEBUG] Node initialization complete.")

    # --- Subscriber callbacks ---

    def _external_diag_cb(self, msg: DiagnosticArray) -> None:
        """Cache driver-level diagnostics from /diagnostics, excluding our own entries."""
        with self._driver_diag_lock:
            for status in msg.status:
                # Skip our own published entries to prevent feedback loop
                if not status.name.startswith("robot_manager/"):
                    self._driver_diagnostics[status.name] = status.message

    # --- Service callbacks ---
    def _start_development_cb(
        self, _req: Trigger.Request, res: Trigger.Response
        ) -> Trigger.Response:
        """Trigger developer support mode systemd service."""
        self.get_logger().info("[DEBUG] /robot_manager/enable_dev service called.")

        try:
            # -S tells sudo to read the password from standard input (stdin)
            cmd = ["sudo", "-S", "/usr/local/bin/dev_mode_start.sh"]
            
            result = subprocess.run(
                cmd,
                input=f"rover\n",  # Append newline to simulate pressing Enter
                capture_output=True,
                text=True,
                timeout=10.0,
            )

            if result.returncode == 0:
                res.success = True
                res.message = "Developer support mode successfully triggered."
                self.get_logger().info(res.message)
            else:
                res.success = False
                res.message = f"Failed to start dev mode service (code {result.returncode}): {result.stderr.strip()}"
                self.get_logger().error(res.message)

        except subprocess.TimeoutExpired:
            res.success = False
            res.message = "Timed out waiting for developer mode service to start."
            self.get_logger().error(res.message)
        except Exception as exc:
            res.success = False
            res.message = f"Exception while triggering dev mode: {exc}"
            self.get_logger().error(res.message)

        return res

    def _start_navigation_cb(
        self, _req: Trigger.Request, res: Trigger.Response
    ) -> Trigger.Response:
        """Start the navigation pipeline if currently IDLE."""
        self.get_logger().info("[DEBUG] /robot_manager/start_navigation service called.")
        with self._state_lock:
            self.get_logger().info(f"[DEBUG] _start_navigation_cb: Current state = {self._state.value}")
            if self._state != ManagerState.IDLE:
                res.success = False
                res.message = f"Cannot start navigation: current state is {self._state.value}"
                self.get_logger().info(f"[DEBUG] _start_navigation_cb: Rejecting call — {res.message}")
                return res

            yolo_path: str = self.get_parameter("yolo_engine_path").value
            self.get_logger().info(f"[DEBUG] _start_navigation_cb: yolo_engine_path parameter = '{yolo_path}'")
            if not yolo_path:
                res.success = False
                res.message = "Cannot start navigation: yolo_engine_path parameter is not set"
                self.get_logger().info(f"[DEBUG] _start_navigation_cb: Rejecting call — {res.message}")
                return res
            if not os.path.isfile(yolo_path):
                res.success = False
                res.message = f"Cannot start navigation: engine file not found: {yolo_path}"
                self.get_logger().info(f"[DEBUG] _start_navigation_cb: Rejecting call — {res.message}")
                return res

            log_path = "/tmp/max_bringup.log" #TODO: change to correct file path
            self.get_logger().info(f"[DEBUG] _start_navigation_cb: Attempting to spawn process, logging to {log_path}")

            try:
                self._pipeline_log = open(log_path, "w")  # noqa: WPS515
                self._pipeline_proc = subprocess.Popen(
                    [
                        "ros2",
                        "launch",
                        "bringup",
                        "rover_bringup.launch.py",
                        f"yolo_engine_path:={yolo_path}",
                    ],
                    start_new_session=True,
                    stdout=self._pipeline_log,
                    stderr=self._pipeline_log,
                )
                self._pipeline_pgid = os.getpgid(self._pipeline_proc.pid)
                self.get_logger().info(f"[DEBUG] _start_navigation_cb: Process spawned successfully (PID={self._pipeline_proc.pid}, PGID={self._pipeline_pgid})")
            except Exception as exc:
                self._close_pipeline_log()
                self.get_logger().warning(f"Failed to spawn navigation pipeline: {exc}")
                res.success = False
                res.message = f"Failed to spawn pipeline: {exc}"
                self.get_logger().info(f"[DEBUG] _start_navigation_cb: Exception caught during spawn — {res.message}")
                return res

            self._transition_to(ManagerState.NAV_STARTING)
            res.success = True
            res.message = "Navigation pipeline starting"
            self.get_logger().info(
                f"Navigation pipeline started (pid={self._pipeline_proc.pid})"
                f" — log: {log_path}"
                f" — {self._NAV_GRACE_SEC}s grace period"
            )
            self.get_logger().info(f"[DEBUG] _start_navigation_cb: Returning success response — {res.message}")
            return res

    def _start_mapping_cb(self, _req: Trigger.Request, res: Trigger.Response) -> Trigger.Response:
        """Start the 3D mapping pipeline if currently IDLE."""
        self.get_logger().info("[DEBUG] /robot_manager/start_mapping service called.")
        with self._state_lock:
            self.get_logger().info(f"[DEBUG] _start_mapping_cb: Current state = {self._state.value}")
            if self._state != ManagerState.IDLE:
                res.success = False
                res.message = f"Cannot start mapping: current state is {self._state.value}"
                self.get_logger().info(f"[DEBUG] _start_mapping_cb: Rejecting call — {res.message}")
                return res

            pcd_save_dir: str = os.path.expanduser(self.get_parameter("pcd_save_dir").value)
            self.get_logger().info(f"[DEBUG] _start_mapping_cb: pcd_save_dir parameter = '{pcd_save_dir}'")
            log_path = "/tmp/pointlio.log"
            self.get_logger().info(f"[DEBUG] _start_mapping_cb: Attempting to spawn process, logging to {log_path}")

            try:
                self._pipeline_log = open(log_path, "w")  # noqa: WPS515
                self._pipeline_proc = subprocess.Popen(
                    [
                        # TODO: change this once pointlio is implemented
                        "ros2",
                        "launch",
                        "pointlio",
                        "mapping_3d.launch.py",
                        f"pcd_save_dir:={pcd_save_dir}",
                    ],
                    start_new_session=True,
                    stdout=self._pipeline_log,
                    stderr=self._pipeline_log,
                )
                self._pipeline_pgid = os.getpgid(self._pipeline_proc.pid)
                self.get_logger().info(f"[DEBUG] _start_mapping_cb: Process spawned successfully (PID={self._pipeline_proc.pid}, PGID={self._pipeline_pgid})")
            except Exception as exc:
                self._close_pipeline_log()
                self.get_logger().warning(f"Failed to spawn mapping pipeline: {exc}")
                res.success = False
                res.message = f"Failed to spawn pipeline: {exc}"
                self.get_logger().info(f"[DEBUG] _start_mapping_cb: Exception caught during spawn — {res.message}")
                return res

            self._transition_to(ManagerState.MAP_STARTING)
            res.success = True
            res.message = "Mapping pipeline starting"
            self.get_logger().info(
                f"Mapping pipeline started (pid={self._pipeline_proc.pid})"
                f" — log: {log_path}"
                f" — {self._MAP_GRACE_SEC}s grace period"
            )
            self.get_logger().info(f"[DEBUG] _start_mapping_cb: Returning success response — {res.message}")
            return res

    def _stop_pipeline_cb(self, _req: Trigger.Request, res: Trigger.Response) -> Trigger.Response:
        """Stop the active pipeline and return to IDLE."""
        self.get_logger().info("[DEBUG] /robot_manager/stop_pipeline service called.")
        with self._state_lock:
            self.get_logger().info(f"[DEBUG] _stop_pipeline_cb: Current state = {self._state.value}")
            if self._state == ManagerState.IDLE:
                res.success = False
                res.message = "No pipeline is running"
                self.get_logger().info(f"[DEBUG] _stop_pipeline_cb: Rejecting call — {res.message}")
                return res
            if self._state == ManagerState.STOPPING:
                res.success = False
                res.message = "Pipeline is already stopping"
                self.get_logger().info(f"[DEBUG] _stop_pipeline_cb: Rejecting call — {res.message}")
                return res

            self.get_logger().info("[DEBUG] _stop_pipeline_cb: Calling _kill_pipeline()...")
            self._kill_pipeline()
            self._transition_to(ManagerState.STOPPING)
            res.success = True
            res.message = "Pipeline stop requested"
            self.get_logger().info("Pipeline stop requested — state: STOPPING")

        # Publish immediately so Foxglove sees STOPPING before the process exits
        indicator = Int32()
        indicator.data = 3
        self._pipeline_state_pub.publish(indicator)
        self.get_logger().info(f"[DEBUG] _stop_pipeline_cb: Returning success response — {res.message}")
        return res

    # --- Timer callbacks ---

    def _health_check_loop(self) -> None:
        """Drive state transitions. Runs at health_check_hz.

        Transitions require both the grace period elapsed AND all required topic
        publishers present. Publisher checks use count_publishers() — no subscriptions,
        no DDS message traffic.
        """
        with self._state_lock:
            elapsed = time.monotonic() - self._state_entry_time

            if self._state == ManagerState.NAV_STARTING:
                if elapsed >= self._NAV_GRACE_SEC and self._nav_publishers_ready():
                    self._transition_to(ManagerState.NAV_RUNNING)
                    self.get_logger().info("Navigation is running")

            elif self._state == ManagerState.MAP_STARTING:
                if elapsed >= self._MAP_GRACE_SEC and self._map_publishers_ready():
                    self._transition_to(ManagerState.MAP_RUNNING)
                    self.get_logger().info("Mapping is running")

            elif self._state == ManagerState.STOPPING:
                if self._pipeline_proc is None or self._pipeline_proc.poll() is not None:
                    self._pipeline_proc = None
                    self._pipeline_pgid = None
                    self._close_pipeline_log()
                    self._transition_to(ManagerState.IDLE)
                    self.get_logger().info("Pipeline stopped — state: IDLE")

        self._publish_diagnostics()

    def _publish_status(self) -> None:
        """Publish JSON status blob at status_publish_hz."""
        with self._state_lock:
            state = self._state
            pid = self._pipeline_proc.pid if self._pipeline_proc else None

        with self._driver_diag_lock:
            driver_diag = dict(self._driver_diagnostics)

        status = {
            "state": state.value,
            "pipeline_pid": pid,
            "uptime_sec": int(time.monotonic() - self._start_time),
            "last_error": self._last_error,
            # Publisher presence — graph queries, zero DDS traffic
            "topics": self._topic_publisher_snapshot(),
            # Driver-level health from /diagnostics subscriber
            "driver_diagnostics": driver_diag,
        }

        msg = String()
        msg.data = json.dumps(status)
        self._status_pub.publish(msg)

        indicator = Int32()
        indicator.data = self._state_to_indicator(state)
        self._pipeline_state_pub.publish(indicator)

    def _watchdog_loop(self) -> None:
        """Detect unexpected pipeline crashes and revert to IDLE."""
        with self._state_lock:
            if self._state in (ManagerState.IDLE, ManagerState.STOPPING):
                return
            if self._pipeline_proc is not None and self._pipeline_proc.poll() is not None:
                code = self._pipeline_proc.returncode
                self._last_error = f"Pipeline exited unexpectedly (code {code})"
                self.get_logger().warning(self._last_error)
                self._pipeline_proc = None
                self._pipeline_pgid = None
                self._close_pipeline_log()
                self._transition_to(ManagerState.IDLE)

    # --- Helpers ---

    def _nav_publishers_ready(self) -> bool:
        """Return True when all nav pipeline topics have active publishers.

        Uses count_publishers() — local graph query, no DDS traffic.
        Lidar and map are the minimum required for functional navigation.
        """
        return self.count_publishers("/rslidar_points") > 0 and self.count_publishers("/map") > 0

    def _map_publishers_ready(self) -> bool:
        """Return True when all mapping pipeline topics have active publishers.

        Uses count_publishers() — local graph query, no DDS traffic.
        """
        return (
            self.count_publishers("/lidar_points") > 0
            and self.count_publishers("/imu/filtered") > 0
            # and self.count_publishers("/registered_scan") > 0
        )

    def _topic_publisher_snapshot(self) -> Dict[str, bool]:
        """Return publisher-present flag for all monitored topics.

        All checks are count_publishers() graph queries — no subscriptions,
        no message deserialization, no DDS traffic.
        """
        topics = (
            "/lidar_points", # TODO: change topic name to match rs airy lidar
            "/imu/filtered", # TODO: change topic name to match rs ekf node
            "/odom",
            "/map",
            "/camera/color/image_raw",
            "/yolo/internal_state",
            # "/registered_scan",
        )
        return {t: self.count_publishers(t) > 0 for t in topics}

    def _transition_to(self, new_state: ManagerState) -> None:
        """Update state and record entry time. Must be called under _state_lock."""
        self._state = new_state
        self._state_entry_time = time.monotonic()

    def _state_to_indicator(self, state: ManagerState) -> int:
        """Map manager state to indicator value published on /robot_manager/pipeline_state.

        Returns:
            0 = IDLE (gray), 1 = STARTING (yellow), 2 = RUNNING (green), 3 = STOPPING (red).
        """
        if state == ManagerState.IDLE:
            return 0
        if state in (ManagerState.NAV_STARTING, ManagerState.MAP_STARTING):
            return 1
        if state in (ManagerState.NAV_RUNNING, ManagerState.MAP_RUNNING):
            return 2
        return 3  # STOPPING

    def _kill_pipeline(self) -> None:
        """Terminate the pipeline and all descendant processes.

        ros2 launch spawns each ROS node in its own session, so killing only the
        launch process group leaves node subprocesses alive. This method walks
        /proc to find every process descended from the launch PID and sends
        SIGTERM to each one before killing the launch process group itself.
        Must be called under _state_lock.
        """
        if self._pipeline_proc is not None:
            self._kill_descendants(self._pipeline_proc.pid)

        if self._pipeline_pgid is not None:
            try:
                os.killpg(self._pipeline_pgid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except Exception as exc:
                self.get_logger().warning(f"Failed to kill pipeline process group: {exc}")

    def _kill_descendants(self, root_pid: int) -> None:
        """Send SIGTERM to all processes descended from root_pid via /proc.

        Args:
            root_pid: PID of the root process whose descendants to terminate.
        """
        try:
            # Build a parent→children map from /proc
            children: Dict[int, List[int]] = {}
            for entry in os.scandir("/proc"):
                if not entry.name.isdigit():
                    continue
                try:
                    stat = open(f"/proc/{entry.name}/stat").read().split()
                    pid, ppid = int(stat[0]), int(stat[3])
                    children.setdefault(ppid, []).append(pid)
                except OSError:
                    pass

            # BFS from root_pid, kill leaves first (reverse BFS order)
            visited, queue = [], [root_pid]
            while queue:
                pid = queue.pop()
                visited.append(pid)
                queue.extend(children.get(pid, []))

            for pid in reversed(visited):
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                except Exception as exc:
                    self.get_logger().warning(f"Failed to SIGTERM pid {pid}: {exc}")
        except Exception as exc:
            self.get_logger().warning(f"Descendant kill failed: {exc}")

    def _close_pipeline_log(self) -> None:
        """Close the open pipeline log file handle if any."""
        if self._pipeline_log is not None:
            try:
                self._pipeline_log.close()
            except Exception as exc:
                self.get_logger().warning(f"Failed to close pipeline log: {exc}")
            self._pipeline_log = None

    def _publish_diagnostics(self) -> None:
        """Publish a rich DiagnosticArray to /diagnostics.

        Entries are visible in Foxglove's Diagnostics panel with color-coded
        OK/WARN levels and expandable key-value details. Topic checks use
        count_publishers() — no subscriptions, no DDS message traffic.
        """
        with self._state_lock:
            state = self._state
            pid = self._pipeline_proc.pid if self._pipeline_proc else None
            elapsed = int(time.monotonic() - self._state_entry_time)

        active = state not in (ManagerState.IDLE, ManagerState.STOPPING)
        nav_active = state in (ManagerState.NAV_STARTING, ManagerState.NAV_RUNNING)
        map_active = state in (ManagerState.MAP_STARTING, ManagerState.MAP_RUNNING)

        array = DiagnosticArray()
        array.header.stamp = self.get_clock().now().to_msg()

        def _kv(key: str, value: str) -> KeyValue:
            k = KeyValue()
            k.key = key
            k.value = value
            return k

        # --- State ---
        s = DiagnosticStatus()
        s.name = "robot_manager/state"
        s.level = DiagnosticStatus.OK
        s.message = state.value
        s.values.append(_kv("elapsed_sec", str(elapsed)))
        s.values.append(_kv("uptime_sec", str(int(time.monotonic() - self._start_time))))
        array.status.append(s)

        # --- Pipeline process ---
        s = DiagnosticStatus()
        s.name = "robot_manager/pipeline"
        if pid is not None:
            s.level = DiagnosticStatus.WARN if self._last_error else DiagnosticStatus.OK
            s.message = "running" if active else "stopping"
            s.values.append(_kv("pid", str(pid)))
        else:
            s.level = DiagnosticStatus.WARN if self._last_error else DiagnosticStatus.OK
            s.message = "last error: " + self._last_error if self._last_error else "idle"
        if self._last_error:
            s.values.append(_kv("last_error", self._last_error))
        array.status.append(s)

        # --- Topic publisher checks ---
        # Each entry: OK (green) = publisher present or not required,
        #             WARN (yellow) = required by active pipeline but missing.
        topic_cfg = [
            ("/rslidar_points", "lidar", nav_active or map_active),
            ("/map", "map", nav_active),
            ("/imu/filtered", "imu", map_active),
            ("/registered_scan", "registered_scan", map_active),
            ("/camera/zed_node/rgb/color/image", "camera", nav_active),
            ("/yolo/internal_state", "yolo", nav_active),
            ("/odom", "odom", nav_active),
        ]

        for topic, short_name, required in topic_cfg:
            has_pub = self.count_publishers(topic) > 0
            s = DiagnosticStatus()
            s.name = f"robot_manager/{short_name}"
            s.values.append(_kv("topic", topic))
            s.values.append(_kv("publishers", "1" if has_pub else "0"))

            if not active:
                s.level = DiagnosticStatus.OK
                s.message = "idle"
            elif has_pub:
                s.level = DiagnosticStatus.OK
                s.message = "OK"
            elif required:
                s.level = DiagnosticStatus.WARN
                s.message = "no publisher"
            else:
                s.level = DiagnosticStatus.OK
                s.message = "not required"

            array.status.append(s)

        self._diag_pub.publish(array)


def main(args=None) -> None:
    """Entry point for the robot_manager node."""
    rclpy.init(args=args)
    node = RobotManagerNode()
    try:
        node.get_logger().info("[DEBUG] Starting rclpy.spin...")
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.get_logger().info("[DEBUG] Shutting down RobotManagerNode...")
        node._kill_pipeline()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()