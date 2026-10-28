"""运行期路径解析（只用标准库）。

单独拆出来，是为了让"启动虚拟摄像头"能在导入 PySide6/cv2 之前就跑起来——
用户双击后越快能在会议里看到「摄像头1」越好。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _start_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def run_dir() -> Path:
    """共享帧/日志所在目录，与媒体源 DLL 的搜索顺序保持一致。"""
    env = os.environ.get("CWB_FRAME_FILE")
    if env:
        return Path(env).parent

    start = _start_dir()
    for base in ([] if getattr(sys, "frozen", False) else [start, *start.parents]):
        if (base / ".run").is_dir():
            return base / ".run"

    programdata = os.environ.get("ProgramData", r"C:\ProgramData")
    return Path(programdata) / "CameraWhiteboard"


def frames_path() -> Path:
    env = os.environ.get("CWB_FRAME_FILE")
    if env:
        return Path(env)
    return run_dir() / "frames.bin"


def log_path() -> Path:
    return run_dir() / "app.log"
