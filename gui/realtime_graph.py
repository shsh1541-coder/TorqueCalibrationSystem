"""Real-time torque graph (PyQtGraph) with review of previous applications."""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.data_source import PHASE_RELEASING
from . import theme

VIEW_LIVE = "live"
VIEW_TIMELINE = "timeline"


class _Trace:
    __slots__ = ("label", "target", "t", "y", "rel", "capture", "kind")

    def __init__(self, label: str, target: float, kind: str):
        self.label, self.target, self.kind = label, target, kind
        self.t: List[float] = []
        self.y: List[float] = []
        self.rel: List[bool] = []
        self.capture: Optional[tuple] = None


def _split(t, y, rel):
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    rel = np.asarray(rel, dtype=bool)
    if t.size == 0:
        return t, y, y
    rel_ext = rel.copy()
    rel_ext[:-1] |= rel[1:]          # include the last loading point -> continuous curve
    y_rise = np.where(~rel, y, np.nan)
    y_rel = np.where(rel_ext, y, np.nan)
    return t, y_rise, y_rel


class RealtimeGraph(QWidget):
    MAX_TIMELINE_POINTS = 20000

    def __init__(self, parent=None):
        super().__init__(parent)
        pg.setConfigOptions(antialias=True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        top = QHBoxLayout()
        self.title = QLabel("REAL-TIME TORQUE GRAPH  실시간 토크 그래프")
        self.title.setObjectName("CardTitle")
        top.addWidget(self.title)
        top.addStretch(1)
        top.addWidget(QLabel("View:"))
        self.view_combo = QComboBox()
        self.view_combo.setMinimumWidth(260)
        self.view_combo.currentIndexChanged.connect(self._on_view_changed)
        top.addWidget(self.view_combo)
        lay.addLayout(top)

        self.plot = pg.PlotWidget(background=theme.GRAPH_BG)
        self.plot.showGrid(x=True, y=True, alpha=0.18)
        self.plot.setLabel("bottom", "Time (s)", color=theme.TEXT_DIM)
        self.plot.setLabel("left", "Torque (N·m)", color=theme.TEXT_DIM)
        for ax in ("left", "bottom"):
            a = self.plot.getAxis(ax)
            a.setPen(pg.mkPen(theme.PANEL_BORDER))
            a.setTextPen(pg.mkPen(theme.TEXT_DIM))
        self.plot.setMouseEnabled(x=True, y=False)
        self.legend = self.plot.addLegend(offset=(10, 10), labelTextColor=theme.TEXT_DIM)
        self.rise = self.plot.plot([], [], pen=pg.mkPen(theme.ACCENT, width=2.4),
                                   name="Torque Increasing", connect="finite")
        self.release = self.plot.plot([], [], pen=pg.mkPen(theme.AMBER, width=2.4),
                                      name="Torque Releasing", connect="finite")
        self.target_curve = self.plot.plot([], [], pen=pg.mkPen(theme.TEXT_DIM, width=1.5,
                                                                   style=Qt.DashLine),
                                           name="Target Torque")
        self.capture_pts = pg.ScatterPlotItem(size=14, symbol="star", pen=pg.mkPen("#ffffff", width=1),
                                              brush=pg.mkBrush(theme.GREEN),
                                              name="Measurement Capture Point")
        self.plot.addItem(self.capture_pts)
        self.current_dot = pg.ScatterPlotItem(size=9, pen=None, brush=pg.mkBrush(theme.CYAN))
        self.plot.addItem(self.current_dot)
        lay.addWidget(self.plot, 1)
        self.clear()

    # ---------------------------------------------------------------- data
    def clear(self):
        self.traces: List[_Trace] = []
        self.current: Optional[_Trace] = None
        self.tl_t: List[float] = []
        self.tl_y: List[float] = []
        self.tl_rel: List[bool] = []
        self.tl_caps: List[tuple] = []
        self._dirty = True
        self.view_combo.blockSignals(True)
        self.view_combo.clear()
        self.view_combo.addItem("LIVE  현재 측정", VIEW_LIVE)
        self.view_combo.addItem("FULL TIMELINE  전체 타임라인", VIEW_TIMELINE)
        self.view_combo.blockSignals(False)
        self.view_combo.setCurrentIndex(0)
        self.refresh(force=True)

    def start_trace(self, label: str, target: float, kind: str):
        self.current = _Trace(label, target, kind)
        self._dirty = True

    def add_sample(self, in_step: bool, t_total: float, t_step: float, torque: float, phase: str):
        rel = phase == PHASE_RELEASING
        if in_step and self.current is not None:
            self.current.t.append(t_step)
            self.current.y.append(torque)
            self.current.rel.append(rel)
        if len(self.tl_t) < self.MAX_TIMELINE_POINTS:
            self.tl_t.append(t_total)
            self.tl_y.append(torque)
            self.tl_rel.append(rel)
        self._dirty = True

    def mark_capture(self, t_total: float, t_step: float, value: float):
        if self.current is not None:
            self.current.capture = (t_step, value)
        self.tl_caps.append((t_total, value))
        self._dirty = True

    def finish_trace(self):
        if self.current is None:
            return
        self.traces.append(self.current)
        idx = len(self.traces) - 1
        self.view_combo.addItem(f"#{idx + 1:02d}  {self.current.label}", idx)
        self.current = None
        self._dirty = True

    def load_traces(self, traces: List[Dict]):
        """Show static capture points for a record loaded from history (no raw curves stored)."""
        self.clear()
        for tr in traces:
            self.tl_caps.append((tr["x"], tr["value"]))
        self._dirty = True
        self.refresh(force=True)

    # -------------------------------------------------------------- render
    def _on_view_changed(self, _i):
        self._dirty = True
        self.refresh(force=True)

    def refresh(self, force: bool = False):
        if not (self._dirty or force):
            return
        self._dirty = False
        view = self.view_combo.currentData()
        if view == VIEW_TIMELINE:
            t, yr, yl = _split(self.tl_t, self.tl_y, self.tl_rel)
            self.rise.setData(t, yr, connect="finite")
            self.release.setData(t, yl, connect="finite")
            self.target_curve.setData([], [])
            if self.tl_caps:
                xs, ys = zip(*self.tl_caps)
                self.capture_pts.setData(list(xs), list(ys))
            else:
                self.capture_pts.setData([], [])
            self.current_dot.setData([self.tl_t[-1]] if self.tl_t else [],
                                     [self.tl_y[-1]] if self.tl_y else [])
            self.plot.enableAutoRange(axis="x")
            self.plot.setYRange(0, self._ymax(max(self.tl_y) if self.tl_y else 0), padding=0)
            return
        trace = self.current if view == VIEW_LIVE else \
            (self.traces[view] if isinstance(view, int) and view < len(self.traces) else None)
        if view == VIEW_LIVE and trace is None and self.traces:
            trace = self.traces[-1]       # keep the last curve visible between steps
        if trace is None:
            for c in (self.rise, self.release, self.target_curve):
                c.setData([], [])
            self.capture_pts.setData([], [])
            self.current_dot.setData([], [])
            return
        t, yr, yl = _split(trace.t, trace.y, trace.rel)
        self.rise.setData(t, yr, connect="finite")
        self.release.setData(t, yl, connect="finite")
        x_end = max(float(t[-1]) if t.size else 1.0, 1.0)
        self.target_curve.setData([0, x_end * 1.05], [trace.target, trace.target])
        if trace.capture:
            self.capture_pts.setData([trace.capture[0]], [trace.capture[1]])
        else:
            self.capture_pts.setData([], [])
        if trace is self.current and trace.t:
            self.current_dot.setData([trace.t[-1]], [trace.y[-1]])
        else:
            self.current_dot.setData([], [])
        self.plot.setXRange(0, x_end * 1.05, padding=0)
        self.plot.setYRange(0, self._ymax(max(trace.target, max(trace.y) if trace.y else 0)),
                            padding=0)

    @staticmethod
    def _ymax(v: float) -> float:
        return max(10.0, v * 1.15)
