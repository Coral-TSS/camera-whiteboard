"""画笔预设：颜色、笔宽、工具。

键名只做标识，界面上显示的名字由 i18n 决定（中/英）。
"""

from __future__ import annotations

PALETTE: list[tuple[str, tuple[int, int, int, int]]] = [
    ("red", (255, 60, 60, 255)),
    ("yellow", (255, 210, 60, 255)),
    ("green", (70, 220, 120, 255)),
    ("blue", (80, 170, 255, 255)),
    ("black", (30, 30, 34, 255)),
]

WIDTHS: list[tuple[str, float]] = [("thin", 4.0), ("medium", 8.0), ("thick", 16.0)]

TOOLS: list[tuple[str, str]] = [("pen", "pen"), ("eraser", "eraser")]
