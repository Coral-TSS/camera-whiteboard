"""输出画面的版式：白板面板放在哪、多大。

输出帧固定 1280x960（4:3）。白板是一块带边框的白色面板，浮在摄像头画面上。
锚点共 13 个：九宫格 9 个 + 三分法 4 个交点。
"""

from __future__ import annotations

from PySide6.QtCore import QRect

# 键 -> (中文名, 水平位置, 垂直位置)
# 位置取值："left"/"center"/"right"/"top"/"middle"/"bottom"/"t1"/"t2"
ANCHORS: dict[str, tuple[str, str, str]] = {
    "tl": ("Top left", "left", "top"),
    "tc": ("Top center", "center", "top"),
    "tr": ("Top right", "right", "top"),
    "cl": ("Middle left", "left", "middle"),
    "c": ("Center", "center", "middle"),
    "cr": ("Middle right", "right", "middle"),
    "bl": ("Bottom left", "left", "bottom"),
    "bc": ("Bottom center", "center", "bottom"),
    "br": ("Bottom right", "right", "bottom"),
    "t1l": ("Thirds top left", "t1", "t1"),
    "t1r": ("Thirds top right", "t2", "t1"),
    "t2l": ("Thirds bottom left", "t1", "t2"),
    "t2r": ("Thirds bottom right", "t2", "t2"),
}

# 画布大小预设：控制的是**白板窗口占屏幕宽度的比例**，
# 输出画面里的面板大小直接由窗口大小换算，不再单独设一个比例
SIZES: dict[str, tuple[str, float]] = {
    "s": ("Small", 0.35),
    "m": ("Medium", 0.50),
    "l": ("Large", 0.70),
}

# 面板宽度占输出宽度的允许范围（太窄看不清、太宽挡脸）
MIN_RATIO = 0.20
MAX_RATIO = 0.90

ASPECT = 3 / 4  # 面板保持 4:3，与白板纸面一致
MARGIN_RATIO = 0.03  # 相对最终视频帧的边距，不用内缩掩盖客户端裁切

# 默认放左上：本机窗口是以左上角为锚点缩放的，输出面板也这样才"统一"
DEFAULT_ANCHOR = "tl"
DEFAULT_SIZE = "m"
DEFAULT_RATIO = 0.50


def clamp_ratio(ratio: float) -> float:
    return max(MIN_RATIO, min(MAX_RATIO, float(ratio)))


def panel_size(ratio: float = DEFAULT_RATIO, out_w: int = 1280, out_h: int = 960) -> tuple[int, int]:
    """面板的像素尺寸（4:3）。位置与尺寸分离，便于"左上角固定、只长宽"。"""
    ratio = clamp_ratio(ratio)
    width = int(out_w * ratio)
    height = int(round(width * 0.75))
    if height > out_h:
        height = out_h
        width = int(round(height / 0.75))
    return width, height


def panel_rect(anchor: str = DEFAULT_ANCHOR, ratio: float = DEFAULT_RATIO,
               out_w: int = 1280, out_h: int = 960) -> QRect:
    """算出白板面板在输出帧里的矩形。ratio = 面板宽度 / 输出宽度。"""
    _, hpos, vpos = ANCHORS.get(anchor, ANCHORS[DEFAULT_ANCHOR])
    ratio = clamp_ratio(ratio)

    panel_w = int(out_w * ratio)
    panel_h = int(round(panel_w * 0.75))  # 4:3
    if panel_h > out_h:
        panel_h = out_h
        panel_w = int(round(panel_h / 0.75))

    margin_x = int(out_w * MARGIN_RATIO)
    margin_y = int(out_h * MARGIN_RATIO)

    if hpos == "left":
        x = margin_x
    elif hpos == "right":
        x = out_w - margin_x - panel_w
    elif hpos == "t1":
        x = int(out_w / 3) - panel_w // 2
    elif hpos == "t2":
        x = int(out_w * 2 / 3) - panel_w // 2
    else:
        x = (out_w - panel_w) // 2

    if vpos == "top":
        y = margin_y
    elif vpos == "bottom":
        y = out_h - margin_y - panel_h
    elif vpos == "t1":
        y = int(out_h / 3) - panel_h // 2
    elif vpos == "t2":
        y = int(out_h * 2 / 3) - panel_h // 2
    else:
        y = (out_h - panel_h) // 2

    # 夹进"安全区"：会议客户端会裁掉画面边缘，贴边的部分对面看不到
    min_x, max_x = margin_x, out_w - margin_x - panel_w
    if max_x < min_x:                 # 面板太大，安全区放不下就退回整帧
        min_x, max_x = 0, out_w - panel_w
    min_y, max_y = margin_y, out_h - margin_y - panel_h
    if max_y < min_y:
        min_y, max_y = 0, out_h - panel_h
    x = max(min_x, min(x, max_x))
    y = max(min_y, min(y, max_y))
    return QRect(x, y, panel_w, panel_h)


def anchor_label(anchor: str) -> str:
    from .i18n import anchor as tr_anchor

    return tr_anchor(anchor)
