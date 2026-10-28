"""启动白板界面的入口脚本。

    .venv\\Scripts\\python.exe scripts\\run_ui.py
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.camera_whiteboard.app import main  # noqa: E402


def _args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Camera Whiteboard")
    ap.add_argument("--seconds", type=float, default=0.0,
                    help="若干秒后自动退出（0 表示一直运行），用于冒烟测试")
    return ap.parse_args()


if __name__ == "__main__":
    raise SystemExit(main(_args().seconds))
