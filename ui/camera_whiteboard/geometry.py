"""屏幕几何与坐标换算。纯函数，便于无界面测试。

约定（见 specs/windows11/canvas-coordinate.md）：
- 画布坐标 = 虚拟桌面坐标（可能为负），所以"在哪画就落在哪"，不需要额外偏移规则。
- 悬浮层窗口覆盖整个虚拟桌面；窗口内坐标 + 窗口原点 = 画布坐标。
"""

from __future__ import annotations

Rect = tuple[int, int, int, int]  # x, y, w, h


def union_rect(rects: list[Rect]) -> Rect:
    """多显示器时的虚拟桌面外接矩形。"""
    if not rects:
        return (0, 0, 0, 0)
    left = min(r[0] for r in rects)
    top = min(r[1] for r in rects)
    right = max(r[0] + r[2] for r in rects)
    bottom = max(r[1] + r[3] for r in rects)
    return (left, top, right - left, bottom - top)


def widget_to_canvas(x: float, y: float, origin: tuple[int, int]) -> tuple[float, float]:
    """悬浮层窗口坐标 -> 画布坐标。"""
    return (x + origin[0], y + origin[1])


def canvas_to_widget(x: float, y: float, origin: tuple[int, int]) -> tuple[float, float]:
    """画布坐标 -> 悬浮层窗口坐标。"""
    return (x - origin[0], y - origin[1])


def clamp_viewport(rect: Rect, min_size: int = 64) -> Rect:
    """视口最小尺寸保护，避免除零。"""
    x, y, w, h = rect
    return (x, y, max(min_size, w), max(min_size, h))
