"""读取 config/app.json（设备名、媒体源 CLSID）。

路径解析要兼顾源码运行和打包运行：
- 源码：仓库根/config/app.json
- 打包：从 exe 所在目录向上找 config/app.json（产物在仓库内时命中仓库配置）
- 也支持环境变量 CWB_CONFIG 显式指定
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CLSID = "{2B28F238-082E-4FE4-8142-3141306593D0}"
DEFAULT_DEVICE_NAME = "Camera Whiteboard"


@dataclass
class AppConfig:
    media_source_clsid: str = DEFAULT_CLSID
    device_name: str = DEFAULT_DEVICE_NAME
    source: str = "defaults"
    language: str = "en"

    @property
    def is_default(self) -> bool:
        return self.source == "defaults"


def config_path() -> Path | None:
    env = os.environ.get("CWB_CONFIG")
    if env:
        p = Path(env)
        return p if p.exists() else None

    if getattr(sys, "frozen", False):
        start = Path(sys.executable).resolve().parent
    else:
        start = Path(__file__).resolve().parents[2]

    for base in [start, *start.parents]:
        candidate = base / "config" / "app.json"
        if candidate.exists():
            return candidate
    return None


def load_config() -> AppConfig:
    path = config_path()
    if path is None:
        return AppConfig()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return AppConfig()
    return AppConfig(
        media_source_clsid=str(data.get("mediaSourceClsid") or DEFAULT_CLSID),
        device_name=str(data.get("deviceName") or DEFAULT_DEVICE_NAME),
        source=str(path),
        language=str(data.get("language") or "en"),
    )
