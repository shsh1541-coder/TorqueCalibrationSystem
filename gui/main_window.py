"""Main window: layout, control logic and connection of all modules."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QElapsedTimer, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QMainWindow, QMessageBox, QPushButton, QScrollArea, QSplitter,
                               QVBoxLayout, QWidget)

from src import paths
from src.calibration import calculate, partial_row, values_matrix
from src.certificate_excel import generate_excel
from src.certificate_pdf import generate_pdf
from src.config import (APP_SUBTITLE, APP_TITLE, APP_VERSION, SPEED_PRESENTATION,
                        SPEED_PRESETS, CalibrationSettings, EquipmentInfo, SimulationSettings)
from src.data_source import (PHASE_APPLIED, PHASE_APPROACHING, PHASE_CAPTURED,
                             PHASE_INCREASING, PHASE_RELEASING, PHASE_ZERO,
                             SimulatedTorqueSource)
from src.database import (STATUS_ABORTED, STATUS_COMPLETED, STATUS_STOPPED, Database,
                          DatabaseRecorder)
from src.report_data import CertificateData, build_from_db, build_from_engine
from src.simulator import (KIND_PRELOAD, STATE_COMPLETED, STATE_IDLE, STATE_PAUSED,
                           STATE_RUNNING, STATE_STOPPED, STATE_WAITING, CalibrationEngine,
                           EngineListener)
from . import theme
from .certificate_preview import CertificatePreview
from .dashboard import (Card, DigitalDisplay, EquipmentPanel, EventLog, ProgressPanel,
                        ResultsTable)
from .dialogs import HistoryDialog, ResultReviewDialog, SettingsDialog
from .realtime_graph import RealtimeGraph
from .torque_gauge import TorqueGauge

TICK_MS = 50

PHASE_KO = {PHASE_ZERO: "Zero 영점", PHASE_INCREASING: "Torque Increasing 증가",
            PHASE_APPROACHING: "Approaching Target 목표 접근", PHASE_APPLIED: "Torque Applied 유지",
            PHASE_CAPTURED: "Measurement Captured 확정", PHASE_RELEASING: "Torque Released 해제"}


class _Bridge(EngineListener):
    """Forwards engine callbacks to the window (same thread - QTimer driven)."""

    def __init__(self, win: "MainWindow"):
        self.w = win

    def on_state_changed(self, state):
        self.w.on_engine_state(state)

    def on_step_started(self, step):
        self.w.on_step_started(step)

    def on_sample(self, step, t_total, t_step, torque, phase):
        self.w.last_sample = (step, t_total, t_step, torque, phase)
        self.w.graph.add_sample(step is not None, t_total, t_step, torque, phase)

    def on_phase_changed(self, step, phase):
        self.w.progress.lbl_phase.setText(PHASE_KO.get(phase, phase))

    def on_preload_captured(self, record):
        self.w.on_capture(record.peak, preload=True)

    def on_measurement_captured(self, step, m):
        self.w.on_measurement(step, m)

    def on_step_finished(self, step):
        self.w.graph.finish_trace()
        self.w.table.highlight(None, None)

    def on_preloading_completed(self):
        self.w.progress.set_banner("PRELOADING COMPLETED  사전부하 완료", theme.GREEN)
        self.w.banner_hold = 1.0

    def on_completed(self):
        self.w.on_completed()

    def on_log(self, phase, message):
        self.w.event_log.append(phase, message)


class CompletionOverlay(QFrame):
    """Large completion message shown over the dashboard (presentation friendly)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet("QFrame { background-color: rgba(8, 20, 38, 225); border: 2px solid "
                           f"{theme.GREEN}; border-radius: 14px; }}"
                           "QLabel { background: transparent; border: none; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 30, 40, 30)
        self.l1 = QLabel("CALIBRATION COMPLETED")
        self.l2 = QLabel("")
        self.l3 = QLabel("")
        for l, px, col in ((self.l1, 40, theme.GREEN), (self.l2, 26, "#ffffff"),
                           (self.l3, 26, theme.CYAN)):
            l.setAlignment(Qt.AlignCenter)
            l.setFont(theme.ui_font(px, bold=True))
            l.setStyleSheet(f"color: {col};")
            lay.addWidget(l)
        hint = QLabel("click to close")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(f"color: {theme.TEXT_DIM};")
        lay.addWidget(hint)
        self.hide()

    def show_message(self, done: int, total: int, cert_ready: bool):
        self.l2.setText(f"{done} / {total} Measurements Completed")
        self.l3.setText("Certificate Ready" if cert_ready else "Ready for Certificate Generation")
        self.reposition()
        self.show()
        self.raise_()
        QTimer.singleShot(12000, self.hide)

    def reposition(self):
        p = self.parentWidget()
        if p is None:
            return
        w, h = min(760, int(p.width() * 0.8)), 260
        self.setGeometry((p.width() - w) // 2, (p.height() - h) // 2, w, h)

    def mousePressEvent(self, _e):
        self.hide()


class MainWindow(QMainWindow):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.equipment = EquipmentInfo.from_dict(db.load_app_setting("equipment"))
        self.settings = CalibrationSettings.from_dict(db.load_app_setting("settings"))
        self.sim = SimulationSettings.from_dict(db.load_app_setting("simulation"))
        self.source = SimulatedTorqueSource(self.sim, self.settings.resolution)
        self.engine = CalibrationEngine(self.source, self.equipment, self.settings, self.sim)
        self.bridge = _Bridge(self)
        self.engine.add_listener(self.bridge)
        self.recorder: Optional[DatabaseRecorder] = None
        self.cal_id: Optional[int] = None
        self.cert_data: Optional[CertificateData] = None
        self.cert_pdf: Optional[Path] = None
        self.viewing_record: Optional[int] = None   # history record shown (not a live run)
        self.last_sample = None
        self.banner_hold = 0.0
        self.presentation = False
        self.current_target: Optional[float] = None

        self.setWindowTitle(f"{APP_TITLE} - {APP_SUBTITLE}  [SIMULATION MODE]  v{APP_VERSION}")
        self.resize(1600, 960)
        self.setMinimumSize(1200, 760)
        self._build_ui()
        self.equipment_panel.set_equipment(self.equipment, self.settings)
        self._reconfigure_views()

        self.timer = QTimer(self)
        self.timer.setInterval(TICK_MS)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self._tick)
        self.elapsed = QElapsedTimer()
        self.clock = QTimer(self)
        self.clock.timeout.connect(self._update_clock)
        self.clock.start(1000)
        self._update_clock()
        self.sc_full = QShortcut(QKeySequence("F11"), self)
        self.sc_full.activated.connect(self._toggle_fullscreen)
        self.sc_esc = QShortcut(QKeySequence("Esc"), self)
        self.sc_esc.activated.connect(lambda: self.isFullScreen() and self.showNormal())
        self._update_buttons()
        QTimer.singleShot(300, self._check_recovery)

    # =================================================================== UI
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self._header())

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(12, 10, 12, 8)
        bl.setSpacing(8)
        self.h_split = QSplitter(Qt.Horizontal)
        self.h_split.setChildrenCollapsible(False)

        # ---- left column
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(8)
        self.equipment_panel = EquipmentPanel()
        ll.addWidget(self.equipment_panel)
        cfg = Card("CALIBRATION SETTINGS  교정 설정")
        self.cfg_summary = QLabel()
        self.cfg_summary.setWordWrap(True)
        self.cfg_summary.setStyleSheet(f"color: {theme.TEXT}; background: transparent;")
        cfg.vbox.addWidget(self.cfg_summary)
        row = QHBoxLayout()
        self.btn_settings = QPushButton("설정 Settings")
        self.btn_settings.clicked.connect(self._open_settings)
        self.btn_history = QPushButton("이력 History")
        self.btn_history.clicked.connect(self._open_history)
        self.btn_review = QPushButton("결과 검토 Review")
        self.btn_review.clicked.connect(self._open_review)
        for b in (self.btn_settings, self.btn_history, self.btn_review):
            row.addWidget(b)
        cfg.vbox.addLayout(row)
        ll.addWidget(cfg)
        self.event_log = EventLog()
        ll.addWidget(self.event_log, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(left)
        scroll.setMinimumWidth(330)
        self.left_panel = scroll
        self.h_split.addWidget(scroll)

        # ---- right column
        self.v_split = QSplitter(Qt.Vertical)
        self.v_split.setChildrenCollapsible(False)
        top = QWidget()
        tl = QHBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(8)
        self.display = DigitalDisplay()
        gauge_card = Card("TORQUE GAUGE  토크 게이지")
        self.gauge = TorqueGauge(maximum=self.equipment.capacity)
        gauge_card.vbox.addWidget(self.gauge, 1)
        self.progress = ProgressPanel()
        tl.addWidget(self.display, 5)
        tl.addWidget(gauge_card, 3)
        tl.addWidget(self.progress, 3)
        self.v_split.addWidget(top)
        graph_card = Card()
        self.graph = RealtimeGraph()
        graph_card.vbox.setContentsMargins(4, 4, 4, 4)
        graph_card.vbox.addWidget(self.graph)
        self.v_split.addWidget(graph_card)
        table_card = Card("MEASUREMENT RESULTS  측정 결과  (N·m)")
        self.table = ResultsTable()
        table_card.vbox.addWidget(self.table)
        self.v_split.addWidget(table_card)
        self.v_split.setStretchFactor(0, 4)
        self.v_split.setStretchFactor(1, 5)
        self.v_split.setStretchFactor(2, 3)
        self.v_split.setSizes([330, 380, 230])
        self.h_split.addWidget(self.v_split)
        self.h_split.setStretchFactor(0, 0)
        self.h_split.setStretchFactor(1, 1)
        self.h_split.setSizes([360, 1240])
        bl.addWidget(self.h_split, 1)
        bl.addWidget(self._controls())
        v.addWidget(body, 1)
        self.overlay = CompletionOverlay(root)

        sb = self.statusBar()
        self.sb_source = QLabel(f"Data source: {self.source.name}")
        self.sb_eta = QLabel("")
        self.sb_out = QLabel(f"Output: {paths.output_root()}")
        sb.addWidget(self.sb_source)
        sb.addWidget(QLabel("  |  "))
        sb.addWidget(self.sb_eta)
        sb.addPermanentWidget(self.sb_out)

    def _header(self):
        h = QFrame()
        h.setObjectName("HeaderBar")
        h.setFixedHeight(68)
        lay = QHBoxLayout(h)
        lay.setContentsMargins(20, 6, 20, 6)
        led = QLabel("●")
        led.setStyleSheet(f"color: {theme.ACCENT}; font-size: 26px; background: transparent;")
        lay.addWidget(led)
        tv = QVBoxLayout()
        tv.setSpacing(0)
        t = QLabel(APP_TITLE)
        t.setObjectName("AppTitle")
        s = QLabel(APP_SUBTITLE)
        s.setObjectName("AppSubtitle")
        tv.addWidget(t)
        tv.addWidget(s)
        lay.addLayout(tv)
        lay.addStretch(1)
        self.state_led = QLabel("●  READY")
        self.state_led.setStyleSheet(f"color: {theme.TEXT_DIM}; font-weight: 700; "
                                     "background: transparent;")
        lay.addWidget(self.state_led)
        lay.addSpacing(18)
        self.clock_label = QLabel()
        self.clock_label.setObjectName("Clock")
        lay.addWidget(self.clock_label)
        lay.addSpacing(18)
        badge = QLabel("SIMULATION MODE")
        badge.setObjectName("SimBadge")
        badge.setToolTip("가상 토크측정기 신호를 사용합니다. 실제 계측기와 연결되어 있지 않습니다.")
        lay.addWidget(badge)
        return h

    def _controls(self):
        box = QFrame()
        box.setObjectName("Card")
        g = QVBoxLayout(box)
        g.setContentsMargins(10, 8, 10, 8)
        g.setSpacing(6)
        r1 = QHBoxLayout()
        r2 = QHBoxLayout()

        def btn(text, slot, name=None, row=r1, checkable=False):
            b = QPushButton(text)
            if name:
                b.setObjectName(name)
            b.setCheckable(checkable)
            b.setMinimumHeight(38)
            b.clicked.connect(slot)
            row.addWidget(b)
            return b

        self.b_start = btn("▶  START CALIBRATION", self._on_start, "Primary")
        self.b_pause = btn("⏸  PAUSE", self._on_pause)
        self.b_resume = btn("▶  RESUME", self._on_resume)
        self.b_stop = btn("■  STOP", self._on_stop, "Danger")
        self.b_reset = btn("↺  RESET", self._on_reset)
        self.b_next = btn("⏭  NEXT MEASUREMENT", self._on_next)
        self.b_mode = btn("MODE: AUTO", self._on_mode, checkable=True)
        r1.addSpacing(10)
        r1.addWidget(QLabel("Speed:"))
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(list(SPEED_PRESETS.keys()))
        self.speed_combo.setCurrentText(self.sim.preset)
        self.speed_combo.currentTextChanged.connect(self._on_speed)
        self.speed_combo.setMinimumHeight(36)
        r1.addWidget(self.speed_combo)
        self.b_present = btn("★  PRESENTATION MODE", self._on_presentation, checkable=True)

        self.b_generate = btn("GENERATE CERTIFICATE", self._on_generate, "Success", row=r2)
        self.b_pdf = btn("EXPORT PDF", self._on_export_pdf, row=r2)
        self.b_xlsx = btn("EXPORT EXCEL", self._on_export_excel, row=r2)
        self.b_open = btn("OPEN CERTIFICATE", self._on_open_certificate, row=r2)
        self.b_folder = btn("OPEN OUTPUT FOLDER", self._open_output_folder, row=r2)
        r2.addStretch(1)
        note = QLabel("All values are simulated  —  모든 측정값은 시뮬레이션 데이터입니다")
        note.setStyleSheet(f"color: {theme.AMBER}; background: transparent;")
        r2.addWidget(note)
        g.addLayout(r1)
        g.addLayout(r2)
        return box

    # ============================================================ helpers
    def _reconfigure_views(self):
        s, e = self.settings, self.equipment
        self.table.configure(s.points, s.n_series, s.coverage_k)
        self.gauge.set_maximum(max(e.capacity, max(s.points)))
        self.gauge.set_target(None)
        self.gauge.set_value(0)
        self.display.set_current(0.0)
        self.display.set_target(None)
        self.progress.meas_bar.setRange(0, s.n_series * len(s.points))
        self.progress.meas_bar.setValue(0)
        self.progress.step_bar.setRange(0, s.preload_cycles + s.n_series * len(s.points))
        self.progress.step_bar.setValue(0)
        for l in (self.progress.lbl_series, self.progress.lbl_point, self.progress.lbl_preload,
                  self.progress.lbl_phase):
            l.setText("-")
        self._update_summary()

    def _update_summary(self):
        s, m = self.settings, self.sim
        pts = ", ".join(f"{p:g}" for p in s.points)
        rule = "Simple" if s.decision_rule == "simple" else "Guarded (w = U)"
        self.cfg_summary.setText(
            f"Points: {pts} N·m<br>Series: {s.n_series} &nbsp;|&nbsp; Preloading: "
            f"{s.preload_cycles}× {s.effective_preload_torque(self.equipment.capacity):g} "
            f"N·m<br>Tolerance: ±{s.tolerance_pct:g} % (demo) &nbsp;|&nbsp; Rule: {rule}"
            f"<br>U: k = {s.coverage_k:g}, ref {s.ref_expanded_u_pct:g} %, r = {s.resolution:g}"
            f"<br>Simulation: ±{m.random_error_pct:g} % random, noise {m.noise_level:g} "
            f"N·m, {m.sampling_interval_ms} ms")
        self.cfg_summary.setTextFormat(Qt.RichText)
        self.sb_eta.setText(f"Speed: {m.preset}  |  Estimated run time: "
                            f"{self.engine.estimated_duration():.0f} s")
        self.progress.lbl_speed.setText(f"{m.preset} ({m.speed_factor:g}×)")
        self.progress.lbl_mode.setText("MANUAL" if self.engine.manual_mode else "AUTO")

    def _update_clock(self):
        self.clock_label.setText(datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))

    def _save_app_settings(self):
        self.db.save_app_setting("equipment", self.equipment.to_dict())
        self.db.save_app_setting("settings", self.settings.to_dict())
        self.db.save_app_setting("simulation", self.sim.to_dict())

    def _error(self, title: str, exc: Exception):
        QMessageBox.critical(self, title, f"{type(exc).__name__}: {exc}")

    def _set_recorder(self, cal_id: Optional[int]):
        if self.recorder:
            self.engine.remove_listener(self.recorder)
        self.recorder = None
        self.cal_id = cal_id
        if cal_id is not None:
            self.recorder = DatabaseRecorder(self.db, cal_id)
            self.engine.add_listener(self.recorder)

    def _complete_for_certificate(self) -> bool:
        if self.viewing_record is not None:
            rec = self.db.get_calibration(self.viewing_record)
            return rec is not None and rec.status == STATUS_COMPLETED
        return self.engine.is_complete and self.cal_id is not None

    def _update_buttons(self):
        st = self.engine.state
        active = st in (STATE_RUNNING, STATE_PAUSED, STATE_WAITING)
        self.b_start.setEnabled(st in (STATE_IDLE, STATE_STOPPED, STATE_COMPLETED))
        self.b_pause.setEnabled(st in (STATE_RUNNING, STATE_WAITING))
        self.b_resume.setEnabled(st == STATE_PAUSED)
        self.b_stop.setEnabled(active)
        self.b_reset.setEnabled(st != STATE_RUNNING and st != STATE_WAITING)
        self.b_next.setEnabled(st == STATE_WAITING)
        complete = self._complete_for_certificate()
        self.b_generate.setEnabled(complete)
        self.b_pdf.setEnabled(complete)
        self.b_xlsx.setEnabled(complete)
        self.b_open.setEnabled(self.cert_pdf is not None and self.cert_pdf.exists())
        self.btn_review.setEnabled(complete)
        self.btn_settings.setEnabled(not active)
        self.btn_history.setEnabled(not active)
        self.equipment_panel.set_editable(not active)
        colors = {STATE_IDLE: theme.TEXT_DIM, STATE_RUNNING: theme.GREEN, STATE_PAUSED: theme.AMBER,
                  STATE_WAITING: theme.CYAN, STATE_STOPPED: theme.RED, STATE_COMPLETED: theme.GREEN}
        label = {STATE_IDLE: "READY", STATE_WAITING: "WAITING (MANUAL)"}.get(st, st)
        if self.viewing_record is not None and st == STATE_IDLE:
            label = f"VIEWING RECORD #{self.viewing_record}"
        self.state_led.setText(f"●  {label}")
        self.state_led.setStyleSheet(f"color: {colors.get(st, theme.TEXT_DIM)}; font-weight: 700;"
                                     " background: transparent;")

    # ============================================================ engine cb
    def on_engine_state(self, state):
        if state == STATE_PAUSED:
            self.progress.set_banner("PAUSED  일시 정지", theme.AMBER)
        elif state == STATE_WAITING:
            self.progress.set_banner("WAITING  —  press NEXT MEASUREMENT", theme.CYAN)
        elif state == STATE_STOPPED:
            self.progress.set_banner("STOPPED  교정 중지", theme.RED)
            self.timer.stop()
        self._update_buttons()

    def on_step_started(self, step):
        s = self.settings
        self.current_target = step.target
        self.graph.start_trace(step.label, step.target, step.kind)
        self.display.set_target(step.target)
        self.gauge.set_target(step.target)
        self.progress.step_bar.setValue(step.index)
        if step.kind == KIND_PRELOAD:
            self.progress.set_banner(f"PRELOADING  사전부하   Cycle {step.cycle} / "
                                     f"{s.preload_cycles}", theme.AMBER)
            self.progress.lbl_preload.setText(f"{step.cycle} / {s.preload_cycles}")
            self.progress.lbl_series.setText("-")
            self.progress.lbl_point.setText("-")
        else:
            self.progress.set_banner(
                f"MEASUREMENT IN PROGRESS   Series {step.series} / {s.n_series}  ·  "
                f"Point {step.point_index + 1} / {len(s.points)}", theme.ACCENT)
            self.progress.lbl_preload.setText(f"{s.preload_cycles} / {s.preload_cycles} ✓")
            self.progress.lbl_series.setText(f"{step.series} / {s.n_series}")
            self.progress.lbl_point.setText(f"{step.point_index + 1} / {len(s.points)}")
            self.table.highlight(step.series, step.point_index)

    def on_capture(self, value: float, preload: bool):
        if self.last_sample:
            _, tt, ts, _, _ = self.last_sample
            self.graph.mark_capture(tt, ts, value)
        label = "PRELOAD PEAK" if preload else "MEASUREMENT CAPTURED"
        self.progress.set_banner(f"{label}   {value:.2f} N·m", theme.GREEN)

    def on_measurement(self, step, m):
        self.on_capture(m.value, preload=False)
        self.table.set_value(m.series, m.point_index, m.value)
        row = values_matrix(self.engine.measurements, self.settings)[m.point_index]
        mean, rel = partial_row(row, self.settings.points[m.point_index])
        self.table.set_partial(m.point_index, mean, rel)
        self.progress.meas_bar.setValue(self.engine.n_measurements_done)

    def on_completed(self):
        self.timer.stop()
        self.progress.step_bar.setValue(self.progress.step_bar.maximum())
        self.display.set_target(None)
        self.gauge.set_target(None)
        self.current_target = None
        try:
            result = calculate(self.engine.measurements, self.settings)
        except Exception as exc:  # pragma: no cover
            self._error("계산 오류", exc)
            return
        for i, p in enumerate(result.points):
            self.table.set_final(i, p.mean, p.rel_error_pct, p.U, p.decision(result.decision_rule))
        if self.cal_id is not None:
            self.db.save_results(self.cal_id, result.to_dict(), result.overall)
            self.db.set_status(self.cal_id, STATUS_COMPLETED)
        done, total = self.engine.n_measurements_done, self.engine.n_measurements_total
        self.progress.set_banner(f"CALIBRATION COMPLETED   {done} / {total}   "
                                 f"Result: {result.overall}", theme.GREEN)
        self.cert_data, self.cert_pdf = None, None
        cert_ready = False
        if self.presentation:
            cert_ready = self._generate_certificate(show_preview=False, also_excel=True)
        self._update_buttons()
        self.overlay.show_message(done, total, cert_ready)

    # ============================================================== timer
    def _tick(self):
        dt = self.elapsed.restart() / 1000.0
        dt = min(max(dt, 0.0), 0.5)
        try:
            self.engine.advance(dt)
        except Exception as exc:
            self.timer.stop()
            self.engine.pause()
            self._error("시뮬레이션 오류", exc)
            return
        if self.last_sample:
            step, _, _, torque, phase = self.last_sample
            tgt = self.current_target
            reached = (step is not None and tgt is not None and
                       phase in (PHASE_APPLIED, PHASE_CAPTURED) and
                       abs(torque - tgt) <= max(0.01 * tgt, 0.1))
            self.display.set_current(torque, reached)
            self.gauge.set_value(torque)
            self.gauge.set_reached(reached)
        self.graph.refresh()

    # ============================================================ controls
    def _on_start(self):
        if self.engine.state not in (STATE_IDLE, STATE_STOPPED, STATE_COMPLETED):
            return
        self.equipment_panel.read_into(self.equipment, self.settings)
        errs = self.settings.validate() + self.sim.validate()
        if max(self.settings.points) > self.equipment.capacity:
            errs.append("교정점이 최대용량(Capacity)을 초과합니다.")
        if errs:
            QMessageBox.warning(self, "설정 오류", "\n".join(errs))
            return
        try:
            self.engine.configure(self.equipment, self.settings, self.sim)
            self.viewing_record = None
            self.cert_data, self.cert_pdf = None, None
            self.overlay.hide()
            self.graph.clear()
            self.event_log.clear()
            self._reconfigure_views()
            self._save_app_settings()
            cal_id = self.db.create_calibration(self.equipment, self.settings, self.sim)
            self._set_recorder(cal_id)
            self.engine.set_manual(self.b_mode.isChecked())
            self.engine.start()
        except Exception as exc:
            self._error("시작 오류", exc)
            return
        self.event_log.append("SYSTEM", f"Calibration record #{self.cal_id} created.")
        self.elapsed.start()
        self.timer.start()
        self._update_buttons()

    def _on_pause(self):
        self.engine.pause()

    def _on_resume(self):
        self.engine.resume()
        self.elapsed.start()
        if not self.timer.isActive():
            self.timer.start()
        if self.engine.state == STATE_RUNNING and self.current_target is not None:
            self.progress.set_banner("MEASUREMENT IN PROGRESS", theme.ACCENT)

    def _on_stop(self):
        if QMessageBox.question(self, "STOP", "현재 교정 시퀀스를 종료할까요?\n"
                                "측정된 데이터는 이력(History)에 STOPPED 상태로 남습니다.") \
                != QMessageBox.Yes:
            return
        self.engine.stop()
        if self.cal_id is not None:
            self.db.set_status(self.cal_id, STATUS_STOPPED)
        self.table.highlight(None, None)
        self.display.set_current(0.0)
        self.gauge.set_value(0)
        self.last_sample = None
        self._update_buttons()

    def _on_reset(self):
        has_data = bool(self.engine.measurements or self.engine.preloads) or \
            self.viewing_record is not None
        if has_data and QMessageBox.question(
                self, "RESET", "측정 데이터 화면을 초기화할까요?\n(저장된 이력은 유지됩니다)") \
                != QMessageBox.Yes:
            return
        if self.engine.state == STATE_PAUSED and self.cal_id is not None:
            self.db.set_status(self.cal_id, STATUS_STOPPED)
        self.timer.stop()
        self.engine.reset()
        self._set_recorder(None)
        self.viewing_record = None
        self.cert_data, self.cert_pdf = None, None
        self.last_sample = None
        self.current_target = None
        self.graph.clear()
        self.overlay.hide()
        self._reconfigure_views()
        self.progress.set_banner("READY  대기", theme.TEXT_DIM)
        self.event_log.append("SYSTEM", "Reset - data cleared.")
        self._update_buttons()

    def _on_next(self):
        if self.engine.next_measurement():
            self.elapsed.start()

    def _on_mode(self, checked):
        self.b_mode.setText("MODE: MANUAL" if checked else "MODE: AUTO")
        self.engine.set_manual(checked)
        self.progress.lbl_mode.setText("MANUAL" if checked else "AUTO")
        self._update_buttons()

    def _on_speed(self, name):
        try:
            self.sim.apply_preset(name)   # timing only - results unaffected
        except ValueError:
            return
        self.db.save_app_setting("simulation", self.sim.to_dict())
        self._update_summary()

    def _on_presentation(self, checked):
        self.presentation = checked
        self.left_panel.setVisible(not checked)
        self.progress.set_presentation(checked)
        if checked:
            if self.speed_combo.currentText() != SPEED_PRESENTATION:
                self.speed_combo.setCurrentText(SPEED_PRESENTATION)
            if self.b_mode.isChecked():
                self.b_mode.setChecked(False)
                self._on_mode(False)
            self.v_split.setSizes([420, 420, 200])
            self.event_log.append("SYSTEM", "Presentation Mode ON - full sequence + certificate "
                                            f"in approx. {self.engine.estimated_duration():.0f} s.")
        else:
            self.v_split.setSizes([330, 380, 230])
        self.b_present.setText("★  PRESENTATION MODE: ON" if checked else
                               "★  PRESENTATION MODE")

    def _toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    # =========================================================== certificate
    def _certificate_data(self) -> CertificateData:
        if self.viewing_record is not None:
            return build_from_db(self.db, self.viewing_record)
        cert_no = self.db.assign_cert_no(self.cal_id)
        return build_from_engine(self.engine, cert_no, self.cal_id, self.db.get_events(self.cal_id))

    def _generate_certificate(self, show_preview=True, also_excel=False) -> bool:
        if not self._complete_for_certificate():
            QMessageBox.information(self, "알림", "측정이 완료된 후에만 성적서를 발행할 수 있습니다.")
            return False
        try:
            data = self._certificate_data()
            out = paths.certificates_dir()
            pdf = generate_pdf(data, out / f"{paths.safe_filename(data.cert_no)}.pdf")
            self.db.add_certificate(data.calibration_id, data.cert_no, "PDF", str(pdf))
            if also_excel:
                xl = generate_excel(data, out / f"{paths.safe_filename(data.cert_no)}.xlsx")
                self.db.add_certificate(data.calibration_id, data.cert_no, "XLSX", str(xl))
            self.cert_data, self.cert_pdf = data, pdf
            self.event_log.append("CERT", f"Certificate {data.cert_no} generated: {pdf.name}")
            if self.cal_id is not None:
                self.db.add_event(self.cal_id, "CERT", f"Certificate {data.cert_no} generated.")
        except Exception as exc:
            self._error("성적서 생성 오류", exc)
            return False
        self._update_buttons()
        if show_preview:
            self._on_open_certificate()
        return True

    def _on_generate(self):
        self._generate_certificate(show_preview=True)

    def _export(self, kind: str):
        if not self._complete_for_certificate():
            return
        try:
            data = self.cert_data or self._certificate_data()
            self.cert_data = data
            ext, flt = (".pdf", "PDF (*.pdf)") if kind == "PDF" else (".xlsx", "Excel (*.xlsx)")
            default = paths.certificates_dir() / f"{paths.safe_filename(data.cert_no)}{ext}"
            fn, _ = QFileDialog.getSaveFileName(self, f"Export {kind}", str(default), flt)
            if not fn:
                return
            path = Path(fn)
            if path.suffix.lower() != ext:
                path = path.with_suffix(ext)
            if kind == "PDF":
                generate_pdf(data, path)
                self.cert_pdf = path
            else:
                generate_excel(data, path)
            self.db.add_certificate(data.calibration_id, data.cert_no, kind, str(path))
            self.event_log.append("CERT", f"{kind} exported: {path}")
        except PermissionError as exc:
            QMessageBox.critical(self, "저장 오류", f"파일을 저장할 수 없습니다 (다른 프로그램에서 "
                                                  f"열려 있는지 확인하세요).\n{exc}")
            return
        except Exception as exc:
            self._error("내보내기 오류", exc)
            return
        self._update_buttons()
        box = QMessageBox(self)
        box.setWindowTitle("Export")
        box.setText(f"{kind} 성적서를 저장했습니다.\n{path}")
        open_btn = box.addButton("열기 (Open)", QMessageBox.AcceptRole)
        box.addButton("확인", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _on_export_pdf(self):
        self._export("PDF")

    def _on_export_excel(self):
        self._export("XLSX")

    def _on_open_certificate(self):
        if not (self.cert_pdf and self.cert_pdf.exists()):
            QMessageBox.information(self, "알림", "먼저 GENERATE CERTIFICATE로 성적서를 생성하세요.")
            return
        dlg = CertificatePreview(self.cert_pdf, parent=self, on_export_pdf=self._on_export_pdf,
                                 on_export_excel=self._on_export_excel)
        dlg.exec()

    def _open_output_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.certificates_dir())))

    # ============================================================== dialogs
    def _open_settings(self):
        self.equipment_panel.read_into(self.equipment, self.settings)
        dlg = SettingsDialog(self.settings, self.sim, self)
        if dlg.exec():
            self.settings, new_sim = dlg.settings, dlg.sim
            # keep the same SimulationSettings object shared with the source
            for k, v in new_sim.to_dict().items():
                setattr(self.sim, k, v)
            self.speed_combo.blockSignals(True)
            self.speed_combo.setCurrentText(self.sim.preset)
            self.speed_combo.blockSignals(False)
            if self.engine.state in (STATE_IDLE, STATE_STOPPED, STATE_COMPLETED):
                self.engine.configure(self.equipment, self.settings, self.sim)
                self.viewing_record = None
                self.graph.clear()
                self._reconfigure_views()
            self._save_app_settings()
            self._update_summary()
            self._update_buttons()

    def _open_review(self):
        try:
            data = self.cert_data or self._certificate_data()
        except Exception as exc:
            self._error("결과 검토 오류", exc)
            return
        ResultReviewDialog(data.result, data.settings, self).exec()

    def _open_history(self):
        dlg = HistoryDialog(self.db, self)
        if not dlg.exec() or dlg.selected_id is None:
            return
        cal_id = dlg.selected_id
        if dlg.action == "load":
            self._load_record(cal_id)
        else:
            try:
                data = build_from_db(self.db, cal_id)
                ext = ".pdf" if dlg.action == "pdf" else ".xlsx"
                default = paths.certificates_dir() / f"{paths.safe_filename(data.cert_no)}{ext}"
                fn, _ = QFileDialog.getSaveFileName(self, "Save certificate", str(default),
                                                    "PDF (*.pdf)" if ext == ".pdf" else
                                                    "Excel (*.xlsx)")
                if not fn:
                    return
                path = Path(fn).with_suffix(ext)
                (generate_pdf if ext == ".pdf" else generate_excel)(data, path)
                self.db.add_certificate(cal_id, data.cert_no, ext[1:].upper(), str(path))
                QMessageBox.information(self, "완료", f"성적서를 재생성했습니다.\n{path}")
            except Exception as exc:
                self._error("재생성 오류", exc)

    def _load_record(self, cal_id: int):
        rec = self.db.get_calibration(cal_id)
        if rec is None:
            return
        self.timer.stop()
        self.engine.reset()
        self._set_recorder(None)
        self.equipment, self.settings = rec.equipment, rec.settings
        for k, v in rec.sim.to_dict().items():
            setattr(self.sim, k, v)
        self.engine.configure(self.equipment, self.settings, self.sim)
        self.equipment_panel.set_equipment(self.equipment, self.settings)
        self.graph.clear()
        self._reconfigure_views()
        self.viewing_record = cal_id
        self.cert_data, self.cert_pdf = None, None
        meas = self.db.get_measurements(cal_id)
        for m in meas:
            self.table.set_value(m.series, m.point_index, m.value)
        mm = {(m.series, m.point_index): m for m in meas}
        if rec.status == STATUS_COMPLETED:
            res = calculate(mm, self.settings)
            for i, p in enumerate(res.points):
                self.table.set_final(i, p.mean, p.rel_error_pct, p.U, p.decision(res.decision_rule))
            self.progress.set_banner(f"RECORD #{cal_id}  {rec.cert_no or ''}  {res.overall}",
                                     theme.GREEN)
        else:
            self.progress.set_banner(f"RECORD #{cal_id}  ({rec.status})", theme.AMBER)
        self.progress.meas_bar.setValue(len(meas))
        self.graph.load_traces([{"x": i + 1, "value": m.value} for i, m in enumerate(meas)])
        self.event_log.clear()
        for ev in self.db.get_events(cal_id):
            self.event_log.text.appendPlainText(f"{ev['timestamp'][11:19]} [{ev['phase']:<7}] "
                                                f"{ev['message']}")
        self._update_buttons()

    # ============================================================ recovery
    def _check_recovery(self):
        rec = self.db.find_unfinished()
        if rec is None:
            return
        n = self.db.count_measurements(rec.id)
        np_ = len(self.db.get_preloads(rec.id))
        ans = QMessageBox.question(
            self, "데이터 복구 (Recovery)",
            f"이전 교정 #{rec.id} 이(가) 완료되지 않은 채 종료되었습니다.\n"
            f"저장된 데이터: 사전부하 {np_}회, 측정값 {n}개\n\n"
            "중단된 지점부터 이어서 진행할까요?\n(아니오: 기록을 ABORTED 로 보관)")
        if ans != QMessageBox.Yes:
            self.db.set_status(rec.id, STATUS_ABORTED)
            return
        try:
            self.equipment, self.settings = rec.equipment, rec.settings
            for k, v in rec.sim.to_dict().items():
                setattr(self.sim, k, v)
            self.engine.configure(self.equipment, self.settings, self.sim)
            self.equipment_panel.set_equipment(self.equipment, self.settings)
            self._reconfigure_views()
            self._set_recorder(rec.id)
            meas = self.db.get_measurements(rec.id)
            self.engine.restore(self.db.get_preloads(rec.id), meas)
            for m in meas:
                self.table.set_value(m.series, m.point_index, m.value)
            self.progress.meas_bar.setValue(len(meas))
            self.progress.step_bar.setValue(self.engine.step_idx)
            if self.engine.state == STATE_COMPLETED:
                self.on_completed()
            else:
                self.progress.set_banner("RECOVERED  —  press RESUME", theme.AMBER)
        except Exception as exc:
            self._error("복구 오류", exc)
        self._update_buttons()

    # =============================================================== events
    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if hasattr(self, "overlay") and self.overlay.isVisible():
            self.overlay.reposition()

    def closeEvent(self, ev):
        if self.engine.is_active:
            ans = QMessageBox.question(
                self, "종료 확인", "교정이 진행 중입니다. 종료할까요?\n"
                "측정된 데이터는 저장되어 있으며 다음 실행 시 복구할 수 있습니다.")
            if ans != QMessageBox.Yes:
                ev.ignore()
                return
        self.timer.stop()
        self.clock.stop()
        try:
            self.source.disconnect()
            self.db.close()
        except Exception:
            pass
        ev.accept()
