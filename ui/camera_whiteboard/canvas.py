"""笔迹模型。纯 Python，不依赖 Qt，便于无界面环境测试。

规则来源：specs/windows11/canvas-coordinate.md
- 笔迹存画布坐标（浮点），与屏幕、窗口位置无关
- 线宽存画布单位，缩放只在渲染时乘系数
- 视口外的采样点直接丢弃，不插值、不裁剪
- 视口移动不删除已存笔画
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

Rect = tuple[float, float, float, float]  # vx, vy, vw, vh
Color = tuple[int, int, int, int]  # RGBA 0-255

PEN = "pen"
ERASER = "eraser"


@dataclass
class Stroke:
    color: Color = (0, 0, 0, 255)
    width: float = 4.0
    tool: str = PEN
    points: list[tuple[float, float]] = field(default_factory=list)

    def add(self, x: float, y: float) -> None:
        self.points.append((x, y))

    @property
    def is_empty(self) -> bool:
        return not self.points

    def bounds(self) -> tuple[float, float, float, float] | None:
        if not self.points:
            return None
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return min(xs), min(ys), max(xs), max(ys)


def _point_segment_distance(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    """点到线段的距离，用于橡皮命中判定（只看采样点会漏掉长笔画的中间段）。"""
    dx = bx - ax
    dy = by - ay
    if dx == 0.0 and dy == 0.0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


class Canvas:
    """一块无限画布 + 一个视口。视口决定哪一块内容会被送出。"""

    def __init__(self, viewport: Rect = (0.0, 0.0, 1280.0, 960.0)) -> None:
        self._viewport: Rect = tuple(viewport)  # type: ignore[assignment]
        self._strokes: list[Stroke] = []
        self._active: Stroke | None = None
        self._actions: list[tuple[str, object]] = []
        self._revision = 0

    def _touch(self) -> None:
        """内容发生变化时递增，供发布器判断是否需要重新渲染。"""
        self._revision += 1

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def active_stroke(self) -> Stroke | None:
        """正在画、还没落笔的笔画（发布器也要把它渲染进去）。"""
        return self._active

    # ---- 视口 ----

    @property
    def viewport(self) -> Rect:
        return self._viewport

    def set_viewport(self, vx: float, vy: float, vw: float, vh: float) -> None:
        if vw <= 0 or vh <= 0:
            raise ValueError("Viewport width and height must be positive")
        self._viewport = (float(vx), float(vy), float(vw), float(vh))
        self._touch()
        # 按定义：移动视口不删除已存笔画

    def contains(self, x: float, y: float) -> bool:
        vx, vy, vw, vh = self._viewport
        return vx <= x <= vx + vw and vy <= y <= vy + vh

    # ---- 笔画 ----

    @property
    def strokes(self) -> tuple[Stroke, ...]:
        return tuple(self._strokes)

    @property
    def stroke_count(self) -> int:
        return len(self._strokes)

    def begin_stroke(
        self,
        x: float,
        y: float,
        *,
        color: Color = (0, 0, 0, 255),
        width: float = 4.0,
        tool: str = PEN,
    ) -> bool:
        """起点在视口外则不开笔（越界直接丢弃）。橡皮不建笔画，直接擦。"""
        if not self.contains(x, y):
            return False
        if tool == ERASER:
            self.erase_at(x, y, width)
            return True
        self._active = Stroke(color=color, width=float(width), tool=PEN, points=[(float(x), float(y))])
        self._touch()
        return True

    def add_point(self, x: float, y: float) -> bool:
        if self._active is None:
            return False
        if not self.contains(x, y):
            return False
        self._active.add(float(x), float(y))
        self._touch()
        return True

    def end_stroke(self) -> bool:
        if self._active is None:
            return False
        stroke = self._active
        self._active = None
        if stroke.is_empty:
            return False
        self._strokes.append(stroke)
        self._actions.append(("add", stroke))
        self._touch()
        return True

    # ---- 橡皮 ----

    def erase_at(self, x: float, y: float, radius: float) -> int:
        """整笔擦除：笔画路径（含线段中间部分）进入半径即删掉整条笔画。"""
        if radius <= 0:
            return 0
        hit: list[tuple[int, Stroke]] = []
        for index in range(len(self._strokes) - 1, -1, -1):
            stroke = self._strokes[index]
            if self._stroke_hit(stroke, x, y, radius):
                hit.append((index, stroke))
        if not hit:
            return 0
        removed = []
        for index, stroke in hit:  # 从后往前删，索引不失效
            self._strokes.pop(index)
            removed.append((index, stroke))
        self._actions.append(("erase", removed))
        self._touch()
        return len(removed)

    @staticmethod
    def _stroke_hit(stroke: Stroke, x: float, y: float, radius: float) -> bool:
        points = stroke.points
        if not points:
            return False
        if len(points) == 1:
            return math.hypot(points[0][0] - x, points[0][1] - y) <= radius
        for i in range(len(points) - 1):
            ax, ay = points[i]
            bx, by = points[i + 1]
            if _point_segment_distance(x, y, ax, ay, bx, by) <= radius:
                return True
        return False

    # ---- 撤销 / 清空 ----

    def undo(self) -> bool:
        if not self._actions:
            return False
        kind, payload = self._actions.pop()
        if kind == "add":
            stroke = payload  # type: ignore[assignment]
            if self._strokes and self._strokes[-1] is stroke:
                self._strokes.pop()
            else:
                self._strokes = [s for s in self._strokes if s is not stroke]
            self._touch()
            return True
        if kind == "erase":
            for index, stroke in sorted(payload, key=lambda item: item[0]):  # type: ignore[union-attr]
                self._strokes.insert(index, stroke)
            self._touch()
            return True
        if kind == "clear":
            self._strokes = list(payload)  # type: ignore[arg-type]
            self._touch()
            return True
        return False

    def can_undo(self) -> bool:
        return bool(self._actions)

    def clear(self) -> bool:
        if not self._strokes:
            return False
        self._actions.append(("clear", list(self._strokes)))
        self._strokes = []
        self._touch()
        return True
