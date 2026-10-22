#!/usr/bin/env python3
"""cuVSLAM stereo odometry node (exploration phase, sim first).

Subscribes to a rectified stereo pair + camera_info (the Isaac ZED subgraph on /{drone}/sensors/
front_stereo/...), runs PyCuVSLAM stereo visual odometry (no IMU yet) and publishes
nav_msgs/Odometry in a body-aligned (FLU) frame anchored at the first tracked pose.

This is the exploration precursor of the roadmap's "cuVSLAM connector" (l1_bridge): the same node
later runs on the Jetson with realsense2_camera topics instead of the sim topics.

Frames:
  cuVSLAM world/rig frames are optical (X right, Y down, Z forward). We re-express the rig pose in an
  FLU-aligned world (X forward, Y left, Z up) by conjugating with the fixed optical->body rotation, so
  the output looks like a normal ROS odometry. The translation offset between camera and body
  (0.12 m forward, -0.02 m down in the sim mount) is NOT applied; evo's SE(3) alignment absorbs it
  for scoring. Nothing here is fed to PX4.

Only standard ROS 2 + numpy + scipy are used (no cv_bridge): images are decoded from the raw buffer.
"""
import json
import time

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from message_filters import Subscriber, ApproximateTimeSynchronizer
from sensor_msgs.msg import Image, CameraInfo
from nav_msgs.msg import Odometry, Path
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String
from scipy.spatial.transform import Rotation as R

import cuvslam
try:
    import cv2
except ImportError:  # debug image still works without cv2 (no circles)
    cv2 = None

# body (FLU) from optical (RDF): x_b = z_o, y_b = -x_o, z_b = -y_o
R_BODY_FROM_OPT = np.array([[0.0, 0.0, 1.0],
                            [-1.0, 0.0, 0.0],
                            [0.0, -1.0, 0.0]])


def image_to_numpy(msg: Image) -> np.ndarray:
    """Decode a sensor_msgs/Image into a uint8 HxW (mono) or HxWx3 (rgb) array."""
    enc = msg.encoding.lower()
    buf = np.frombuffer(msg.data, dtype=np.uint8)
    if enc in ("mono8", "8uc1"):
        return buf.reshape(msg.height, msg.step)[:, :msg.width]
    if enc in ("rgb8", "bgr8"):
        img = buf.reshape(msg.height, msg.step)[:, :msg.width * 3].reshape(msg.height, msg.width, 3)
        return img[:, :, ::-1] if enc == "bgr8" else img
    if enc in ("rgba8", "bgra8"):
        img = buf.reshape(msg.height, msg.step)[:, :msg.width * 4].reshape(msg.height, msg.width, 4)
        img = img[:, :, :3]
        return img[:, :, ::-1] if enc == "bgra8" else np.ascontiguousarray(img)
    raise ValueError(f"unsupported image encoding '{msg.encoding}'")


def camera_from_info(info: CameraInfo) -> cuvslam.Camera:
    cam = cuvslam.Camera()
    k = info.k
    cam.focal = [float(k[0]), float(k[4])]
    cam.principal = [float(k[2]), float(k[5])]
    cam.size = [int(info.width), int(info.height)]
    cam.distortion = cuvslam.Distortion(cuvslam.Distortion.Model.Pinhole)  # rectified input
    cam.rig_from_camera = cuvslam.Pose(rotation=[0.0, 0.0, 0.0, 1.0], translation=[0.0, 0.0, 0.0])
    return cam


def baseline_from_right_info(info: CameraInfo) -> float:
    """ROS stereo convention: right P[0,3] = -fx * baseline."""
    fx = float(info.p[0])
    tx = float(info.p[3])
    if fx <= 0.0:
        raise ValueError("right camera_info has fx <= 0")
    return -tx / fx


class CuvslamStereoNode(Node):
    def __init__(self):
        super().__init__("cuvslam_stereo_node")
        self.declare_parameter("drone", "drone_1")
        self.declare_parameter("stereo_ns", "sensors/front_stereo")
        self.declare_parameter("baseline_override_m", 0.0)   # >0 overrides the camera_info baseline
        self.declare_parameter("sync_slop_s", 0.001)
        self.declare_parameter("odom_frame", "")
        self.declare_parameter("child_frame", "")
        self.declare_parameter("status_period_s", 1.0)
        self.declare_parameter("publish_debug_image", True)   # left image with tracked features drawn
        self.declare_parameter("path_max_poses", 6000)        # nav_msgs/Path for the 3D panel

        drone = self.get_parameter("drone").value
        ns = self.get_parameter("stereo_ns").value
        base = f"/{drone}/{ns}"
        self.odom_frame = self.get_parameter("odom_frame").value or f"{drone}/cuvslam_odom"
        self.child_frame = self.get_parameter("child_frame").value or f"{drone}/cuvslam_base"
        self.baseline_override = float(self.get_parameter("baseline_override_m").value)

        sensor_qos = QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT,
                                history=HistoryPolicy.KEEP_LAST)
        self.left_info = None
        self.right_info = None
        self.create_subscription(CameraInfo, f"{base}/left/camera_info", self._left_info_cb, sensor_qos)
        self.create_subscription(CameraInfo, f"{base}/right/camera_info", self._right_info_cb, sensor_qos)
        self.sub_l = Subscriber(self, Image, f"{base}/left/image_rect", qos_profile=sensor_qos)
        self.sub_r = Subscriber(self, Image, f"{base}/right/image_rect", qos_profile=sensor_qos)
        self.sync = ApproximateTimeSynchronizer(
            [self.sub_l, self.sub_r], queue_size=10,
            slop=float(self.get_parameter("sync_slop_s").value))
        self.sync.registerCallback(self._stereo_cb)

        self.pub_odom = self.create_publisher(Odometry, f"/{drone}/cuvslam/odometry", 10)
        self.pub_status = self.create_publisher(String, f"/{drone}/cuvslam/status", 10)
        self.pub_path = self.create_publisher(Path, f"/{drone}/cuvslam/path", 5)
        self.pub_debug = self.create_publisher(Image, f"/{drone}/cuvslam/debug_image", 5)
        self.debug_on = bool(self.get_parameter("publish_debug_image").value)
        self.path = Path(); self.path.header.frame_id = self.odom_frame
        self.path_max = int(self.get_parameter("path_max_poses").value)
        self.create_timer(float(self.get_parameter("status_period_s").value), self._status_tick)

        self.tracker = None
        self.baseline = None
        self.n_frames = 0
        self.n_tracked = 0
        self.n_lost = 0
        self.last_ts_ns = None
        self.lat_ms = []           # per-frame track() wall time
        self.win_frames = 0        # frames in the current status window
        self.win_t0 = time.monotonic()
        self.get_logger().info(f"waiting for {base}/{{left,right}}/{{image_rect,camera_info}}")

    # --- camera info -------------------------------------------------------
    def _left_info_cb(self, msg):
        if self.left_info is None:
            self.left_info = msg
            self._try_init()

    def _right_info_cb(self, msg):
        if self.right_info is None:
            self.right_info = msg
            self._try_init()

    def _try_init(self):
        if self.tracker is not None or self.left_info is None or self.right_info is None:
            return
        try:
            b = self.baseline_override if self.baseline_override > 0.0 else baseline_from_right_info(self.right_info)
        except ValueError as e:
            self.get_logger().error(f"cannot derive baseline: {e}; set baseline_override_m")
            return
        left = camera_from_info(self.left_info)
        right = camera_from_info(self.right_info)
        # right camera sits +baseline along the optical X axis of the left (rig) camera
        right.rig_from_camera = cuvslam.Pose(rotation=[0.0, 0.0, 0.0, 1.0], translation=[float(b), 0.0, 0.0])
        rig = cuvslam.Rig()
        rig.cameras = [left, right]
        cfg = cuvslam.Tracker.OdometryConfig(
            async_sba=False,
            rectified_stereo_camera=True,
            odometry_mode=cuvslam.Tracker.OdometryMode.Multicamera,
        )
        self.tracker = cuvslam.Tracker(rig, cfg)
        self.baseline = b
        self.get_logger().info(
            f"tracker ready: {left.size[0]}x{left.size[1]} fx={left.focal[0]:.1f} "
            f"cx,cy={left.principal[0]:.1f},{left.principal[1]:.1f} baseline={b:.4f} m "
            f"frames {self.left_info.header.frame_id}/{self.right_info.header.frame_id}")

    # --- stereo frames -----------------------------------------------------
    def _stereo_cb(self, left_msg: Image, right_msg: Image):
        if self.tracker is None:
            return
        ts_ns = left_msg.header.stamp.sec * 1_000_000_000 + left_msg.header.stamp.nanosec
        if self.last_ts_ns is not None and ts_ns <= self.last_ts_ns:
            return  # cuVSLAM requires strictly increasing timestamps
        try:
            imgs = [image_to_numpy(left_msg), image_to_numpy(right_msg)]
        except ValueError as e:
            self.get_logger().error(str(e), throttle_duration_sec=5.0)
            return
        t0 = time.monotonic()
        try:
            est, _ = self.tracker.track(ts_ns, imgs)
        except ValueError as e:
            self.get_logger().warn(f"track() rejected frame: {e}", throttle_duration_sec=5.0)
            return
        self.lat_ms.append((time.monotonic() - t0) * 1e3)
        self.last_ts_ns = ts_ns
        self.n_frames += 1
        self.win_frames += 1
        if est.world_from_rig is None:
            self.n_lost += 1
            return
        self.n_tracked += 1
        pose = est.world_from_rig.pose
        t_o = np.asarray(pose.translation, dtype=float)
        q_o = np.asarray(pose.rotation, dtype=float)          # xyzw, world_opt <- rig_opt
        # conjugate into an FLU-aligned world: T_b = C * T_o * C^-1, C = (R_BODY_FROM_OPT, 0)
        R_o = R.from_quat(q_o).as_matrix()
        R_b = R_BODY_FROM_OPT @ R_o @ R_BODY_FROM_OPT.T
        t_b = R_BODY_FROM_OPT @ t_o
        q_b = R.from_matrix(R_b).as_quat()

        od = Odometry()
        od.header.stamp = left_msg.header.stamp
        od.header.frame_id = self.odom_frame
        od.child_frame_id = self.child_frame
        od.pose.pose.position.x, od.pose.pose.position.y, od.pose.pose.position.z = map(float, t_b)
        od.pose.pose.orientation.x, od.pose.pose.orientation.y, od.pose.pose.orientation.z, od.pose.pose.orientation.w = map(float, q_b)
        # covariance from cuVSLAM is not exposed in this first version; leave unknown (0)
        self.pub_odom.publish(od)

        ps = PoseStamped(); ps.header = od.header; ps.pose = od.pose.pose
        self.path.poses.append(ps)
        if len(self.path.poses) > self.path_max:
            del self.path.poses[: len(self.path.poses) - self.path_max]
        self.path.header.stamp = od.header.stamp
        self.pub_path.publish(self.path)

        if self.debug_on:
            self._publish_debug(left_msg, imgs[0])

    # --- debug image: tracked features on the left frame ---------------------
    def _publish_debug(self, left_msg: Image, left_img: np.ndarray):
        try:
            obs = self.tracker.get_last_observations(0)
        except Exception:
            obs = []
        img = np.ascontiguousarray(left_img if left_img.ndim == 3 else np.stack([left_img] * 3, axis=-1)).copy()
        if cv2 is not None:
            for o in obs:
                c = ((o.id * 17) % 256, (o.id * 31) % 256, (o.id * 47) % 256)
                cv2.circle(img, (int(o.u), int(o.v)), 3, c, -1)
            cv2.putText(img, f"features {len(obs)}  frame {self.n_frames}  lost {self.n_lost}",
                        (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1, cv2.LINE_AA)
        else:
            for o in obs:
                u, v = int(o.u), int(o.v)
                img[max(v-1,0):v+2, max(u-1,0):u+2] = (0, 255, 0)
        m = Image(); m.header = left_msg.header; m.height, m.width = img.shape[:2]
        m.encoding = "rgb8"; m.is_bigendian = 0; m.step = m.width * 3; m.data = img.tobytes()
        self.pub_debug.publish(m)

    # --- status ------------------------------------------------------------
    def _status_tick(self):
        now = time.monotonic()
        dt = now - self.win_t0
        rate = self.win_frames / dt if dt > 0 else 0.0
        lat = self.lat_ms[-100:]
        msg = {
            "ready": self.tracker is not None,
            "baseline_m": self.baseline,
            "frames": self.n_frames,
            "tracked": self.n_tracked,
            "lost": self.n_lost,
            "rate_hz": round(rate, 1),
            "track_ms_p50": round(float(np.median(lat)), 1) if lat else None,
            "track_ms_p99": round(float(np.percentile(lat, 99)), 1) if lat else None,
        }
        self.pub_status.publish(String(data=json.dumps(msg)))
        self.win_frames = 0
        self.win_t0 = now


def main():
    rclpy.init()
    node = CuvslamStereoNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
