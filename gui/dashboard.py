"""Dashboard widgets: equipment panel, digital display, progress panel, results table, log."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractItemView, QDoubleSpinBox, QFormLayout, QFrame,
                               QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QPlainTextEdit, QProgressBar, QSizePolicy, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget, QComboBox)

from src.config import CalibrationSettings, EquipmentInfo
from . import theme


class Card(QFrame):
    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.vbox = QVBoxLayout(self)
        self.vbox.setContentsMargins(14, 10, 14, 12)
        self.vbox.setSpacing(6)
        if title:
            lab = QLabel(title)
            lab.setObjectName("CardTitle")
            self.vbox.addWidget(lab)


def _dspin(lo, hi, dec, val, suffix=""):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(dec)
    s.setValue(val)
    if suffix:
        s.setSuffix(suffix)
    s.setKeyboardTracking(False)
    return s


# ---------------------------------------------------------------------------
class EquipmentPanel(Card):
    """Editable equipment information (장비 정보) + environmental conditions."""

    def __init__(self, parent=None):
        super().__init__("EQUIPMENT INFORMATION  장비 정보", parent)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setSpacing(6)
        self.equipment = QLineEdit()
        self.manufacturer = QLineEdit()
        self.model = QLineEdit()
        self.serial = QLineEdit()
        self.capacity = _dspin(1, 100000, 1, 100, " N·m")
        self.range_min = _dspin(0, 100000, 1, 20, " N·m")
        self.range_max = _dspin(0, 100000, 1, 100, " N·m")
        self.direction = QComboBox()
        self.direction.setEditable(True)
        self.direction.addItems(["Clockwise (CW)", "Counter-clockwise (CCW)"])
        self.customer = QLineEdit()
        rng = QWidget()
        rl = QHBoxLayout(rng)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(self.range_min)
        rl.addWidget(QLabel("~"))
        rl.addWidget(self.range_max)
        form.addRow("Equipment", self.equipment)
        form.addRow("Manufacturer", self.manufacturer)
        form.addRow("Model", self.model)
        form.addRow("Serial Number", self.serial)
        form.addRow("Capacity", self.capacity)
        form.addRow("Calibration Range", rng)
        form.addRow("Direction", self.direction)
        form.addRow("Customer", self.customer)
        self.vbox.addLayout(form)

        env_title = QLabel("ENVIRONMENT  환경조건")
        env_title.setObjectName("CardTitle")
        self.vbox.addSpacing(6)
        self.vbox.addWidget(env_title)
        form2 = QFormLayout()
        self.temperature = _dspin(-20, 80, 1, 23.0, " °C")
        self.humidity = _dspin(0, 100, 0, 50, " %RH")
        form2.addRow("Temperature", self.temperature)
        form2.addRow("Relative Humidity", self.humidity)
        self.vbox.addLayout(form2)
        self._editables = [self.equipment, self.manufacturer, self.model, self.serial,
                           self.capacity, self.range_min, self.range_max, self.direction,
                           self.customer, self.temperature, self.humidity]

    def set_equipment(self, e: EquipmentInfo, s: CalibrationSettings):
        self.equipment.setText(e.equipment)
        self.manufacturer.setText(e.manufacturer)
        self.model.setText(e.model)
        self.serial.setText(e.serial_number)
        self.capacity.setValue(e.capacity)
        self.range_min.setValue(e.range_min)
        self.range_max.setValue(e.range_max)
        self.direction.setCurrentText(e.direction)
        self.customer.setText(e.customer)
        self.temperature.setValue(s.temperature)
        self.humidity.setValue(s.humidity)

    def read_into(self, e: EquipmentInfo, s: CalibrationSettings):
        e.equipment = self.equipment.text().strip() or "Torque Wrench"
        e.manufacturer = self.manufacturer.text().strip()
        e.model = self.model.text().strip()
        e.serial_number = self.serial.text().strip()
        e.capacity = self.capacity.value()
        e.range_min = self.range_min.value()
        e.range_max = self.range_max.value()
        e.direction = self.direction.currentText().strip()
        e.customer = self.customer.text().strip()
        s.temperature = self.temperature.value()
        s.humidity = self.humidity.value()

    def set_editable(self, editable: bool):
        for w in self._editables:
            w.setEnabled(editable)


# ---------------------------------------------------------------------------
class DigitalDisplay(Card):
    """Large digital readout: CURRENT TORQUE and TARGET TORQUE."""

    def __init__(self, parent=None):
        super().__init__("", parent)
        self.vbox.setSpacing(2)
        self.cur_title = QLabel("CURRENT TORQUE  현재 토크")
        self.cur_title.setObjectName("BigLabel")
        self.cur_value = QLabel("0.00")
        self.cur_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.cur_unit = QLabel("N·m")
        self.cur_unit.setObjectName("BigLabel")
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.cur_value)
        row.addSpacing(8)
        row.addWidget(self.cur_unit, 0, Qt.AlignBottom)
        self.tgt_title = QLabel("TARGET TORQUE  목표 토크")
        self.tgt_title.setObjectName("BigLabel")
        self.tgt_value = QLabel("--.--")
        self.tgt_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        for lab in (self.cur_value, self.tgt_value):
            lab.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            lab.setMinimumWidth(10)
        self._last_size = None
        self.tgt_unit = QLabel("N·m")
        self.tgt_unit.setObjectName("BigLabel")
        row2 = QHBoxLayout()
        row2.addStretch(1)
        row2.addWidget(self.tgt_value)
        row2.addSpacing(8)
        row2.addWidget(self.tgt_unit, 0, Qt.AlignBottom)
        self.vbox.addWidget(self.cur_title)
        self.vbox.addLayout(row, 3)
        self.vbox.addWidget(self.tgt_title)
        self.vbox.addLayout(row2, 2)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._reached = False
        self._apply_colors()
        self._rescale()

    def set_current(self, value: float, reached: bool = False):
        self.cur_value.setText(f"{value:7.2f}")
        if reached != self._reached:
            self._reached = reached
            self._apply_colors()

    def set_target(self, target: Optional[float]):
        self.tgt_value.setText("--.--" if target is None else f"{target:7.2f}")

    def _apply_colors(self):
        col = theme.GREEN if self._reached else "#ffffff"
        self.cur_value.setStyleSheet(f"color: {col}; background: transparent;")
        self.tgt_value.setStyleSheet(f"color: {theme.CYAN}; background: transparent;")

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._rescale()

    def _rescale(self):
        h, w = self.height(), self.width()
        if self._last_size == (w, h):
            return
        self._last_size = (w, h)
        big = int(max(28, min(h * 0.34, w * 0.20)))
        mid = int(max(18, min(h * 0.17, w * 0.11)))
        lab = int(max(10, min(h * 0.055, 18)))
        self.cur_value.setFont(theme.digit_font(big))
        self.tgt_value.setFont(theme.digit_font(mid))
        for l in (self.cur_title, self.tgt_title, self.cur_unit, self.tgt_unit):
            l.setFont(theme.ui_font(lab, bold=True))


# ---------------------------------------------------------------------------
class ProgressPanel(Card):
    """Sequence state: banner, series / point / cycle, progress bars."""

    def __init__(self, parent=None):
        super().__init__("SEQUENCE STATUS  진행 상태", parent)
        self.banner = QLabel("READY")
        self.banner.setObjectName("StatusBanner")
        self.banner.setAlignment(Qt.AlignCenter)
        self.banner.setMinimumHeight(46)
        self.vbox.addWidget(self.banner)
        grid = QGridLayout()
        grid.setVerticalSpacing(4)
        self.lbl_mode = self._pair(grid, 0, "Mode")
        self.lbl_phase = self._pair(grid, 1, "Signal Phase")
        self.lbl_series = self._pair(grid, 2, "Series 시리즈")
        self.lbl_point = self._pair(grid, 3, "Point 교정점")
        self.lbl_preload = self._pair(grid, 4, "Preload 사전부하")
        self.lbl_speed = self._pair(grid, 5, "Speed")
        self.vbox.addLayout(grid)
        self.meas_bar = QProgressBar()
        self.meas_bar.setFormat("Measurements  %v / %m")
        self.step_bar = QProgressBar()
        self.step_bar.setFormat("Sequence  %v / %m  (%p%)")
        self.vbox.addWidget(self.meas_bar)
        self.vbox.addWidget(self.step_bar)
        self.vbox.addStretch(1)
        self.set_banner("READY  대기", theme.TEXT_DIM)
        self._big = False

    def _pair(self, grid, row, name):
        k = QLabel(name)
        k.setStyleSheet(f"color: {theme.TEXT_DIM}; background: transparent;")
        v = QLabel("-")
        v.setStyleSheet("font-weight: 700; background: transparent;")
        v.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(k, row, 0)
        grid.addWidget(v, row, 1)
        return v

    def set_banner(self, text: str, color: str):
        self.banner.setText(text)
        self.banner.setStyleSheet(
            f"color: {color}; border: 1px solid {color}; background-color: #0f1a2d;"
            f"border-radius: 6px; font-weight: 700; letter-spacing: 2px; padding: 6px;")

    def set_presentation(self, big: bool):
        self._big = big
        px = 30 if big else 16
        self.banner.setFont(theme.ui_font(px, bold=True))
        self.banner.setMinimumHeight(90 if big else 46)
        for l in (self.lbl_series, self.lbl_point, self.lbl_preload):
            l.setFont(theme.ui_font(24 if big else 13, bold=True))


# ---------------------------------------------------------------------------
class ResultsTable(QTableWidget):
    """Target | Series 1..n | Average | Error (%) | U (k=2) | Result."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._hl = None
        self.points: List[float] = []
        self.n_series = 3
        self.k = 2.0

    def configure(self, points: List[float], n_series: int, k: float = 2.0):
        self.points, self.n_series, self.k = list(points), n_series, k
        heads = ["Target (N·m)"] + [f"Series {i + 1}" for i in range(n_series)] + \
                ["Average", "Error (%)", f"U (k={k:g})", "Result 판정"]
        self.clear()
        self.setColumnCount(len(heads))
        self.setRowCount(len(points))
        self.setHorizontalHeaderLabels(heads)
        for r, p in enumerate(points):
            self._set(r, 0, f"{p:.2f}", bold=True)
            for c in range(1, len(heads)):
                self._set(r, c, "-")
        self._hl = None

    def _set(self, r, c, text, bold=False, color=None):
        it = QTableWidgetItem(text)
        it.setTextAlignment(Qt.AlignCenter)
        f = it.font()
        f.setBold(bold)
        it.setFont(f)
        if color:
            it.setForeground(QBrush(QColor(color)))
        self.setItem(r, c, it)
        return it

    def set_value(self, series: int, point_index: int, value: float):
        self._set(point_index, series, f"{value:.2f}", bold=True)

    def set_partial(self, point_index: int, mean, rel):
        if mean is None:
            return
        self._set(point_index, self.n_series + 1, f"{mean:.2f}", color=theme.TEXT_DIM)
        self._set(point_index, self.n_series + 2, f"{rel:+.2f}", color=theme.TEXT_DIM)

    def set_final(self, point_index: int, mean, rel, U, decision):
        self._set(point_index, self.n_series + 1, f"{mean:.2f}", bold=True)
        self._set(point_index, self.n_series + 2, f"{rel:+.2f}", bold=True)
        self._set(point_index, self.n_series + 3, f"{U:.3f}")
        col = {"PASS": theme.GREEN, "FAIL": theme.RED}.get(decision, theme.AMBER)
        self._set(point_index, self.n_series + 4, decision, bold=True, color=col)

    def highlight(self, series: Optional[int], point_index: Optional[int]):
        if self._hl:
            r, c = self._hl
            it = self.item(r, c)
            if it:
                it.setBackground(QBrush())
        self._hl = None
        if series is None or point_index is None:
            return
        it = self.item(point_index, series)
        if it is None:
            it = self._set(point_index, series, "▶")
        if it.text() == "-":
            it.setText("▶")
        it.setBackground(QBrush(QColor("#1f4f9a")))
        self._hl = (point_index, series)


# ---------------------------------------------------------------------------
class EventLog(Card):
    MAX_LINES = 2000

    def __init__(self, parent=None):
        super().__init__("EVENT LOG  측정 이벤트", parent)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(self.MAX_LINES)
        self.text.setFont(theme.digit_font(11, bold=False))
        self.vbox.addWidget(self.text)

    def append(self, phase: str, message: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.text.appendPlainText(f"{ts} [{phase:<7}] {message}")

    def clear(self):
        self.text.clear()
