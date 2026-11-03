"""Circular analog torque gauge drawn with QPainter (0 ~ capacity N·m)."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QConicalGradient, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget

from . import theme


class TorqueGauge(QWidget):
    START_ANGLE = 225.0   # degrees, Qt convention (0 = 3 o'clock, counter-clockwise)
    SPAN = 270.0

    def __init__(self, parent=None, maximum: float = 100.0):
        super().__init__(parent)
        self._max = maximum
        self._value = 0.0
        self._target = None
        self._reached = False
        self.setMinimumSize(180, 180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    # ---------------------------------------------------------------- api
    def set_maximum(self, maximum: float):
        self._max = max(1e-6, float(maximum))
        self.update()

    def set_value(self, value: float):
        self._value = max(0.0, float(value))
        self.update()

    def set_target(self, target):
        self._target = None if target is None else float(target)
        self.update()

    def set_reached(self, reached: bool):
        if reached != self._reached:
            self._reached = reached
            self.update()

    # -------------------------------------------------------------- paint
    def _angle(self, v: float) -> float:
        frac = min(max(v / self._max, 0.0), 1.05)
        return self.START_ANGLE - frac * self.SPAN

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height())
        cx, cy = self.width() / 2.0, self.height() / 2.0 + side * 0.04
        radius = side * 0.44
        rect = QRectF(cx - radius, cy - radius, 2 * radius, 2 * radius)
        thick = max(6.0, radius * 0.11)

        # Track
        pen = QPen(QColor(theme.GAUGE_TRACK), thick, Qt.SolidLine, Qt.FlatCap)
        p.setPen(pen)
        p.drawArc(rect, int(self.START_ANGLE * 16), int(-self.SPAN * 16))

        # Value arc (gradient blue -> cyan, green when target reached)
        frac = min(max(self._value / self._max, 0.0), 1.0)
        if frac > 0:
            if self._reached:
                color = QColor(theme.GREEN)
                pen = QPen(color, thick, Qt.SolidLine, Qt.FlatCap)
            else:
                grad = QConicalGradient(QPointF(cx, cy), self.START_ANGLE)
                grad.setColorAt(0.0, QColor(theme.ACCENT))
                grad.setColorAt(0.75, QColor(theme.CYAN))
                pen = QPen(QBrush(grad), thick, Qt.SolidLine, Qt.FlatCap)
            p.setPen(pen)
            p.drawArc(rect, int(self.START_ANGLE * 16), int(-self.SPAN * frac * 16))

        # Ticks and labels
        major = 10
        p.setFont(theme.ui_font(max(9, int(radius * 0.09))))
        for i in range(major * 5 + 1):
            v = self._max * i / (major * 5)
            a = math.radians(self._angle(v))
            is_major = i % 5 == 0
            r1 = radius - thick * 0.9
            r2 = r1 - (radius * (0.10 if is_major else 0.05))
            p.setPen(QPen(QColor(theme.TEXT if is_major else theme.TEXT_DIM),
                          2.0 if is_major else 1.0))
            p.drawLine(QPointF(cx + r1 * math.cos(a), cy - r1 * math.sin(a)),
                       QPointF(cx + r2 * math.cos(a), cy - r2 * math.sin(a)))
            if is_major:
                rl = r2 - radius * 0.11
                txt = f"{v:g}"
                p.setPen(QColor(theme.TEXT_DIM))
                p.drawText(QRectF(cx + rl * math.cos(a) - 22, cy - rl * math.sin(a) - 9, 44, 18),
                           Qt.AlignCenter, txt)

        # Target marker
        if self._target is not None and self._target > 0:
            a = math.radians(self._angle(self._target))
            r_out, r_in = radius + thick * 0.75, radius - thick * 0.75
            p.setPen(QPen(QColor(theme.AMBER), 3.0))
            p.drawLine(QPointF(cx + r_in * math.cos(a), cy - r_in * math.sin(a)),
                       QPointF(cx + r_out * math.cos(a), cy - r_out * math.sin(a)))

        # Needle
        a = math.radians(self._angle(self._value))
        ln = radius * 0.72
        tip = QPointF(cx + ln * math.cos(a), cy - ln * math.sin(a))
        w = radius * 0.035
        left = QPointF(cx + w * math.cos(a + math.pi / 2), cy - w * math.sin(a + math.pi / 2))
        right = QPointF(cx + w * math.cos(a - math.pi / 2), cy - w * math.sin(a - math.pi / 2))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.GREEN if self._reached else theme.TEXT))
        p.drawPolygon(QPolygonF([left, tip, right]))
        p.setBrush(QColor(theme.PANEL_BORDER))
        p.drawEllipse(QPointF(cx, cy), radius * 0.07, radius * 0.07)

        # Center readout
        p.setFont(theme.digit_font(max(12, int(radius * 0.17)), bold=True))
        p.setPen(QColor(theme.GREEN if self._reached else theme.TEXT))
        p.drawText(QRectF(cx - radius, cy + radius * 0.22, 2 * radius, radius * 0.25),
                   Qt.AlignCenter, f"{self._value:6.2f}")
        p.setFont(theme.ui_font(max(9, int(radius * 0.085))))
        p.setPen(QColor(theme.TEXT_DIM))
        p.drawText(QRectF(cx - radius, cy + radius * 0.46, 2 * radius, radius * 0.16),
                   Qt.AlignCenter, "N·m")
        p.end()
