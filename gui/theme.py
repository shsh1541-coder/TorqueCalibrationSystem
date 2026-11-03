"""Colour palette, fonts and stylesheet loading (dark industrial theme)."""
from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase

from src.paths import resource_path

BG = "#0d1626"            # navy background
BG_ALT = "#111d31"
PANEL = "#16223a"         # cards
PANEL_BORDER = "#26385a"
CHARCOAL = "#1b2230"
TEXT = "#e6edf7"
TEXT_DIM = "#8ea0bd"
ACCENT = "#2f81f7"        # blue accent
CYAN = "#3cc8ff"
GREEN = "#2ecc71"         # status / target reached
AMBER = "#f5a623"
RED = "#ff5c5c"
GAUGE_TRACK = "#243552"
GRAPH_BG = "#0b1322"

UI_FONT_FAMILIES = ["TorqueCal Sans KR", "Segoe UI", "Apple SD Gothic Neo", "Malgun Gothic",
                    "Helvetica Neue", "Arial"]
DIGIT_FONT_FAMILIES = ["Consolas", "Menlo", "SF Mono", "DejaVu Sans Mono", "Courier New"]


def load_app_fonts() -> None:
    """Register the bundled Korean font so Hangul renders identically on Mac/Windows."""
    fdir = resource_path("fonts")
    if fdir.is_dir():
        for f in fdir.glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(f))


def ui_font(px: int, bold: bool = False) -> QFont:
    f = QFont()
    f.setFamilies(UI_FONT_FAMILIES)
    f.setPixelSize(max(1, int(px)))
    f.setBold(bold)
    return f


def digit_font(px: int, bold: bool = True) -> QFont:
    f = QFont()
    f.setFamilies(DIGIT_FONT_FAMILIES)
    f.setStyleHint(QFont.Monospace)
    f.setPixelSize(max(1, int(px)))
    f.setBold(bold)
    return f


def stylesheet() -> str:
    path = resource_path("styles", "dark.qss")
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""
