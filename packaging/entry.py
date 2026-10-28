"""打包入口。PyInstaller 从这里开始分析依赖。

与 scripts/run_ui.py 的区别：这里直接 import 包，让 PyInstaller 把 ui 包一起收进去，
不依赖运行时的 sys.path 拼接。
"""

import sys

def _seconds() -> float:
    if "--seconds" in sys.argv:
        try:
            return float(sys.argv[sys.argv.index("--seconds") + 1])
        except (IndexError, ValueError):
            return 0.0
    return 0.0


if __name__ == "__main__":
    if "--check-bundle" in sys.argv:
        from ui.camera_whiteboard.bundlecheck import check_bundle

        report_index = sys.argv.index("--check-bundle") + 1
        if report_index >= len(sys.argv):
            raise SystemExit(2)
        raise SystemExit(check_bundle(sys.argv[report_index]))

    # 只有标准库 + ctypes：先把虚拟摄像头挂上去，再加载 Qt，
    # 这样用户双击后能很快在会议里看到「摄像头1」
    from ui.camera_whiteboard.bootstrap import claim_single_instance, start_virtual_camera

    if not claim_single_instance():
        from ui.camera_whiteboard.log import log, set_log_path
        from ui.camera_whiteboard.paths import log_path

        set_log_path(log_path())
        log("Another instance is already running; exiting to avoid camera conflicts.")
        raise SystemExit(0)

    vcam, _ = start_virtual_camera()

    from ui.camera_whiteboard.app import main

    raise SystemExit(main(_seconds(), vcam=vcam))
