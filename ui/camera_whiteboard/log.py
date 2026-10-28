"""日志。

打包成无控制台程序后 `sys.stdout` 是 None，直接 print 会抛异常。
所有输出统一走这里：同时写文件（.run/app.log）和标准输出（如果有）。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

_LOG_PATH: Path | None = None


def set_log_path(path: Path | None) -> None:
    global _LOG_PATH
    _LOG_PATH = path
    if path is not None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and path.stat().st_size > 1_000_000:
                path.write_text("", encoding="utf-8")  # 超过 1MB 清一次
        except OSError:
            pass


def log(message: str) -> None:
    stamp = time.strftime("%H:%M:%S") + f".{int(time.time() * 1000) % 1000:03d}"
    line = f"[{stamp}] {message}"
    try:
        if sys.stdout is not None:
            print(line, flush=True)
    except Exception:  # noqa: BLE001
        pass
    if _LOG_PATH is None:
        return
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def log_path() -> Path | None:
    return _LOG_PATH
