"""摄像头采集：独立线程抓帧，只保留最新一帧。

单独开线程的理由：`cap.read()` 是阻塞的（640x480 下约 33 ms 等下一帧），
放在 33 ms 的发布定时器里同步读会拖累节奏。

注意一个容易误判的现象：**光线很暗时摄像头会掉到 1 fps**——自动曝光把帧时间
拉到 1 秒，亮度接近 0。这看起来像线程/后端问题，其实是环境光。排查时先看
帧亮度，别急着怀疑代码。

后端选择（按优先级）：

1. **FfmpegCamera**：起一个 ffmpeg 子进程抓 DirectShow 的 MJPEG 流，
   能拿到 **1280x720@30fps**（设备真实能力）。OpenCV 的 DShow 后端不认
   `CAP_PROP_FOURCC`，只能协商到 YUY2，720p 会掉到 7.4fps，所以走 ffmpeg。
2. **OpenCVCamera**：没有 ffmpeg 时退回 640x480@30fps。

Media Foundation 在本机设备激活不可用（`E_INVALIDARG`，普通终端同样复现），故不使用。
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time

from PySide6.QtGui import QImage

# 低于这个平均亮度就认为"摄像头没画面"（关灯、镜头被挡、遮挡）。
# 8/255 已经很黑，正常昏暗室内也不会这么低。
DARK_THRESHOLD = 8.0
# 连续这么久的暗帧才判定，避免自动曝光调整瞬间误判
DARK_GRACE_SECONDS = 1.5


def is_dark_frame(frame, threshold: float = DARK_THRESHOLD) -> bool:
    """抽样估平均亮度（每 16 像素取一个，640x480 下约 1200 个样本，开销可忽略）。"""
    try:
        sample = frame[::16, ::16]
        return float(sample.mean()) < threshold
    except Exception:  # noqa: BLE001 - 采样失败就当不暗，别影响主流程
        return False


class OpenCVCamera:
    """DirectShow 采集，后台线程存最新帧。"""

    def __init__(self, width: int = 640, height: int = 480, fps: int = 30, index: int = 0) -> None:
        self.width = width
        self.height = height
        self.fps = fps
        self.index = index
        self._cap = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._open_ok = False
        self._lock = threading.Lock()
        self._latest: QImage | None = None
        self._frames = 0
        self._started_at = 0.0
        self._dark_since = 0.0
        self.brightness = -1.0
        self.last_error: str | None = None

    # ---- 生命周期 ----

    def open(self) -> bool:
        try:
            import cv2  # noqa: F401
        except ImportError:
            self.last_error = "opencv-python-headless is not installed"
            return False

        self._stop.clear()
        self._ready.clear()
        self._open_ok = False
        self._started_at = time.perf_counter()
        self._frames = 0

        # DirectShow 的 COM 对象是线程绑定的：必须在采集线程里创建 VideoCapture，
        # 否则 read() 会退化到每秒 1 帧。
        self._thread = threading.Thread(target=self._loop, name="camera", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=8.0)  # 冷启动（刚开机/刚插上）可能要好几百毫秒到几秒

        if not self._open_ok:
            self.last_error = self.last_error or "Camera startup timed out"
        return self._open_ok

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._open_ok = False
        with self._lock:
            self._latest = None

    @property
    def is_open(self) -> bool:
        return self._open_ok

    @property
    def measured_fps(self) -> float:
        elapsed = time.perf_counter() - self._started_at
        return self._frames / elapsed if elapsed > 0 else 0.0

    # ---- 取帧 ----

    def latest(self) -> QImage | None:
        with self._lock:
            return self._latest

    @property
    def is_dark(self) -> bool:
        """持续一段时间没有画面（关灯/遮挡），此时不该把黑帧送给对方。"""
        return self._dark_since > 0 and (time.perf_counter() - self._dark_since) > DARK_GRACE_SECONDS

    def latest_usable(self) -> QImage | None:
        return None if self.is_dark else self.latest()

    def _loop(self) -> None:
        import ctypes

        import cv2

        # 这个线程自己初始化 COM（MTA），并把 VideoCapture 建在这里
        ctypes.windll.ole32.CoInitializeEx(None, 0)
        cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            self.last_error = "Cannot open camera (possibly in use by another app)"
            self._ready.set()
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or self.width
        self.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or self.height
        self._cap = cap
        self._open_ok = True
        self._started_at = time.perf_counter()
        self._ready.set()

        try:
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    time.sleep(0.05)
                    continue
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w = rgb.shape[:2]
                image = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()
                self.brightness = float(frame[::16, ::16].mean())
                if self.brightness < DARK_THRESHOLD:
                    if self._dark_since == 0.0:
                        self._dark_since = time.perf_counter()
                else:
                    self._dark_since = 0.0
                with self._lock:
                    self._latest = image
                self._frames += 1
        finally:
            cap.release()
            self._cap = None
            ctypes.windll.ole32.CoUninitialize()


def ffmpeg_exe() -> str | None:
    """优先用 imageio-ffmpeg 自带的 ffmpeg（随包分发），其次找 PATH。"""
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        pass
    import shutil

    return shutil.which("ffmpeg")


_DEVICE_CACHE = "camera-device.txt"


def _cache_path():
    """设备名缓存放在 .run 下（打包后也能找到同一个目录）。"""
    from .paths import run_dir

    return run_dir() / _DEVICE_CACHE


def dshow_video_device(exe: str, use_cache: bool = True) -> str | None:
    """用 ffmpeg 列出 DirectShow 视频设备，取第一个的名字。

    枚举本身要 2-3 秒，缓存下来，下次启动直接读，省掉这段等待。
    """
    cache = _cache_path()
    if use_cache and cache is not None and cache.exists():
        name = cache.read_text(encoding="utf-8").strip()
        if name:
            return name
    try:
        out = subprocess.run(
            [exe, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
            capture_output=True, text=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for line in (out.stderr or "").splitlines():
        if "(video)" in line and '"' in line:
            name = line.split('"')[1]
            if cache is not None:
                try:
                    cache.write_text(name, encoding="utf-8")
                except OSError:
                    pass
            return name
    return None


class FfmpegCamera:
    """ffmpeg 子进程抓 MJPEG → JPEG 直通管道 → Python 解码。

    720p30 必须走 MJPEG（YUY2 在 USB 上带宽不够）。管道里传的是摄像头原生的
    JPEG 帧（`-c:v copy`），不重新编码，画质无损。
    """

    def __init__(self, width: int = 1280, height: int = 720, fps: int = 30) -> None:
        self.width = width
        self.height = height
        self.fps = fps
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._open_ok = False
        self._lock = threading.Lock()
        self._latest: QImage | None = None
        self._frames = 0
        self._started_at = 0.0
        self._dark_since = 0.0
        self.brightness = -1.0
        self.device = ""
        self.last_error: str | None = None

    # ---- 生命周期 ----

    def open(self) -> bool:
        exe = ffmpeg_exe()
        if not exe:
            self.last_error = "FFmpeg not found; install imageio-ffmpeg or reinstall the application"
            return False
        device = dshow_video_device(exe)
        if not device:
            # 缓存可能过期（换了摄像头），强制重新枚举一次
            device = dshow_video_device(exe, use_cache=False)
        if not device:
            self.last_error = "No DirectShow video camera found"
            return False
        self.device = device

        cmd = [
            exe, "-hide_banner", "-loglevel", "error",
            "-fflags", "nobuffer", "-probesize", "32", "-analyzeduration", "0",
            "-f", "dshow",
            "-video_size", f"{self.width}x{self.height}",
            "-framerate", str(self.fps),
            "-vcodec", "mjpeg",
            "-i", f"video={device}",
            "-c:v", "copy", "-f", "mjpeg", "pipe:1",
        ]
        try:
            self._proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                bufsize=0, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as exc:
            self.last_error = f"Could not start FFmpeg: {exc}"
            return False

        self._stop.clear()
        self._ready.clear()
        self._thread = threading.Thread(target=self._loop, name="camera-ffmpeg", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=8.0)
        if not self._open_ok:
            self.last_error = self.last_error or "FFmpeg produced no video; the camera may be in use"
            self.close()
        return self._open_ok

    def close(self) -> None:
        self._stop.set()
        proc = self._proc
        if proc is not None:
            # 让 ffmpeg 自己退出（stdin 送 q），别硬杀，避免驱动卡在只出黑帧的状态
            try:
                if proc.stdin:
                    proc.stdin.write(b"q")
                    proc.stdin.flush()
            except (OSError, ValueError):
                pass
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
            self._proc = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._open_ok = False
        with self._lock:
            self._latest = None

    @property
    def is_open(self) -> bool:
        return self._open_ok

    @property
    def measured_fps(self) -> float:
        elapsed = time.perf_counter() - self._started_at
        return self._frames / elapsed if elapsed > 0 else 0.0

    # ---- 取帧 ----

    def latest(self) -> QImage | None:
        with self._lock:
            return self._latest

    @property
    def is_dark(self) -> bool:
        return self._dark_since > 0 and (time.perf_counter() - self._dark_since) > DARK_GRACE_SECONDS

    def latest_usable(self) -> QImage | None:
        return None if self.is_dark else self.latest()

    def _loop(self) -> None:
        import cv2
        import numpy as np

        assert self._proc is not None and self._proc.stdout is not None
        stream = self._proc.stdout
        buf = b""
        while not self._stop.is_set():
            chunk = stream.read(65536)
            if not chunk:
                break  # ffmpeg 退出（摄像头被占用/拔掉）
            buf += chunk
            if len(buf) > 8_000_000:  # 防呆：找不到边界就丢掉，避免无限增长
                buf = buf[-2_000_000:]
            while True:
                start = buf.find(b"\xff\xd8")
                if start < 0:
                    break
                end = buf.find(b"\xff\xd9", start + 2)
                if end < 0:
                    break
                jpg = buf[start:end + 2]
                buf = buf[end + 2:]
                frame = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    continue
                if not self._open_ok:
                    h, w = frame.shape[:2]
                    self.width, self.height = w, h
                    self._open_ok = True
                    self._started_at = time.perf_counter()  # 从第一帧开始计，别把启动时间算进帧率
                    self._ready.set()
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w = rgb.shape[:2]
                image = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()
                self.brightness = float(frame[::16, ::16].mean())
                if self.brightness < DARK_THRESHOLD:
                    if self._dark_since == 0.0:
                        self._dark_since = time.perf_counter()
                else:
                    self._dark_since = 0.0
                with self._lock:
                    self._latest = image
                self._frames += 1
        self._ready.set()


def create_camera(prefer_ffmpeg: bool = True):
    """按优先级建摄像头。ffmpeg 优先（720p），失败退回 OpenCV（640x480）。"""
    if prefer_ffmpeg:
        cam = FfmpegCamera()
        if cam.open():
            return cam
        print(f"[camera] FFmpeg capture unavailable: {cam.last_error}", flush=True)
    cam2 = OpenCVCamera(640, 480, 30)
    if cam2.open():
        return cam2
    null = NullCamera()
    null.last_error = cam2.last_error or "Camera unavailable"
    return null


class NullCamera:
    """没有摄像头时的占位，方便界面统一处理。"""

    last_error = "Camera disabled"
    width = 0
    height = 0
    brightness = -1.0

    def open(self) -> bool:
        return False

    def close(self) -> None:
        pass

    @property
    def is_open(self) -> bool:
        return False

    @property
    def measured_fps(self) -> float:
        return 0.0

    def latest(self) -> QImage | None:
        return None

    def latest_usable(self) -> QImage | None:
        return None

    @property
    def is_dark(self) -> bool:
        return True
