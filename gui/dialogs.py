"""Settings, result review and history dialogs."""
from __future__ import annotations

import copy
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox,
                               QDoubleSpinBox, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QSpinBox, QTableWidget,
                               QTableWidgetItem, QTabWidget, QTextBrowser, QVBoxLayout, QWidget)

from src.calibration import CalibrationResult
from src.config import (DECISION_GUARD, DECISION_RULE_TEXT, DECISION_SIMPLE, SPEED_PRESETS,
                        TOLERANCE_NOTE, CalibrationSettings, SimulationSettings)
from src.uncertainty import assumptions_text
from . import theme


def _d(lo, hi, dec, val, suffix="", step=None):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(dec)
    s.setValue(val)
    if suffix:
        s.setSuffix(suffix)
    if step:
        s.setSingleStep(step)
    return s


def _i(lo, hi, val, suffix=""):
    s = QSpinBox()
    s.setRange(lo, hi)
    s.setValue(val)
    if suffix:
        s.setSuffix(suffix)
    return s


class SettingsDialog(QDialog):
    """Calibration settings (교정 설정), uncertainty inputs and simulation settings."""

    def __init__(self, settings: CalibrationSettings, sim: SimulationSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calibration Settings  교정 설정")
        self.setMinimumWidth(620)
        self.settings = copy.deepcopy(settings)
        self.sim = copy.deepcopy(sim)
        tabs = QTabWidget()
        tabs.addTab(self._cal_tab(), "교정 설정 (Calibration)")
        tabs.addTab(self._unc_tab(), "불확도 (Uncertainty)")
        tabs.addTab(self._sim_tab(), "시뮬레이션 (Simulation)")
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel |
                              QDialogButtonBox.RestoreDefaults)
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        bb.button(QDialogButtonBox.RestoreDefaults).clicked.connect(self._defaults)
        lay = QVBoxLayout(self)
        lay.addWidget(tabs)
        lay.addWidget(bb)

    # ------------------------------------------------------------------ tabs
    def _cal_tab(self):
        s = self.settings
        w = QWidget()
        f = QFormLayout(w)
        self.points = QLineEdit(", ".join(f"{p:g}" for p in s.points))
        self.points.setToolTip("Comma separated, e.g. 20, 40, 60, 80, 100")
        self.n_series = _i(2, 5, s.n_series)
        self.preload_cycles = _i(0, 5, s.preload_cycles)
        self.preload_torque = _d(0, 100000, 1, s.preload_torque or 0, " N·m")
        self.preload_torque.setSpecialValueText("= Capacity")
        self.tolerance = _d(0.01, 100, 2, s.tolerance_pct, " %", 0.5)
        self.rule = QComboBox()
        self.rule.addItem("단순 상대오차 판정 (Simple)", DECISION_SIMPLE)
        self.rule.addItem("불확도 고려 판정 (Guard band w = U)", DECISION_GUARD)
        self.rule.setCurrentIndex(0 if s.decision_rule == DECISION_SIMPLE else 1)
        self.rule_text = QLabel()
        self.rule_text.setWordWrap(True)
        self.rule_text.setStyleSheet(f"color: {theme.TEXT_DIM};")
        self.rule.currentIndexChanged.connect(
            lambda _: self.rule_text.setText(DECISION_RULE_TEXT.get(self.rule.currentData(), "")))
        self.rule_text.setText(DECISION_RULE_TEXT.get(self.rule.currentData(), ""))
        self.performed = QLineEdit(s.performed_by)
        self.reviewed = QLineEdit(s.reviewed_by)
        f.addRow("Calibration Points (N·m)", self.points)
        f.addRow("Number of Series", self.n_series)
        f.addRow("Preloading Cycles 사전부하", self.preload_cycles)
        f.addRow("Preload Torque", self.preload_torque)
        f.addRow("Tolerance 허용오차 (±)", self.tolerance)
        f.addRow("Decision Rule 판정 규칙", self.rule)
        f.addRow("", self.rule_text)
        note = QLabel(TOLERANCE_NOTE)
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {theme.AMBER};")
        f.addRow("", note)
        f.addRow("Performed by", self.performed)
        f.addRow("Reviewed by", self.reviewed)
        return w

    def _unc_tab(self):
        s = self.settings
        w = QWidget()
        f = QFormLayout(w)
        self.ref_name = QLineEdit(s.reference_instrument)
        self.ref_u = _d(0, 10, 3, s.ref_expanded_u_pct, " %", 0.01)
        self.ref_k = _d(1, 5, 2, s.ref_k)
        self.resolution = _d(0.0001, 10, 4, s.resolution, " N·m", 0.01)
        self.add_u = _d(0, 10, 3, s.additional_u_pct, " %", 0.01)
        self.k = _d(1, 5, 2, s.coverage_k)
        f.addRow("Reference Instrument", self.ref_name)
        f.addRow("Reference U (of reading)", self.ref_u)
        f.addRow("Reference k", self.ref_k)
        f.addRow("Resolution r", self.resolution)
        f.addRow("Additional std. u (of reading)", self.add_u)
        f.addRow("Coverage factor k (U = k·uc)", self.k)
        txt = QLabel("\n".join("• " + a for a in assumptions_text(s)))
        txt.setWordWrap(True)
        txt.setStyleSheet(f"color: {theme.TEXT_DIM};")
        f.addRow("Assumptions", txt)
        return w

    def _sim_tab(self):
        m = self.sim
        w = QWidget()
        f = QFormLayout(w)
        self.preset = QComboBox()
        self.preset.addItems(list(SPEED_PRESETS.keys()))
        self.preset.setCurrentText(m.preset)
        self.rand = _d(0, 10, 3, m.random_error_pct, " %", 0.05)
        self.bias = _d(0, 10, 3, m.systematic_error_pct, " %", 0.05)
        self.noise = _d(0, 5, 3, m.noise_level, " N·m", 0.01)
        self.interval = _i(10, 500, m.sampling_interval_ms, " ms")
        self.ramp = _d(1, 1000, 1, m.ramp_speed, " N·m/s")
        self.hold = _d(0.1, 30, 2, m.hold_time, " s", 0.1)
        self.gap = _d(0, 30, 2, m.inter_step_delay, " s", 0.1)
        self.speed = _d(0.1, 20, 2, m.speed_factor, " ×", 0.1)
        self.seed = QLineEdit("" if m.seed is None else str(m.seed))
        self.seed.setPlaceholderText("empty = different values every run")
        self.preset.currentTextChanged.connect(self._apply_preset)
        f.addRow("Simulation Speed preset", self.preset)
        f.addRow("Random Error Range (±, of target)", self.rand)
        f.addRow("Systematic bias (max ±)", self.bias)
        f.addRow("Noise Level (σ)", self.noise)
        f.addRow("Sampling Interval", self.interval)
        f.addRow("Torque Ramp Speed", self.ramp)
        f.addRow("Measurement Hold Time", self.hold)
        f.addRow("Delay between applications", self.gap)
        f.addRow("Simulation Speed factor", self.speed)
        f.addRow("Random seed (optional)", self.seed)
        note = QLabel("Speed settings change timing only. Captured values are generated "
                      "independently of timing, so the results are not affected.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {theme.TEXT_DIM};")
        f.addRow("", note)
        return w

    def _apply_preset(self, name):
        p = SPEED_PRESETS.get(name)
        if not p:
            return
        self.ramp.setValue(p["ramp_speed"])
        self.hold.setValue(p["hold_time"])
        self.gap.setValue(p["inter_step_delay"])
        self.speed.setValue(p["speed_factor"])

    def _defaults(self):
        d, m = CalibrationSettings(), SimulationSettings()
        self.points.setText(", ".join(f"{p:g}" for p in d.points))
        self.n_series.setValue(d.n_series)
        self.preload_cycles.setValue(d.preload_cycles)
        self.preload_torque.setValue(0)
        self.tolerance.setValue(d.tolerance_pct)
        self.rule.setCurrentIndex(0)
        self.ref_u.setValue(d.ref_expanded_u_pct)
        self.ref_k.setValue(d.ref_k)
        self.resolution.setValue(d.resolution)
        self.add_u.setValue(d.additional_u_pct)
        self.k.setValue(d.coverage_k)
        self.ref_name.setText(d.reference_instrument)
        self.preset.setCurrentText(m.preset)
        self._apply_preset(m.preset)
        self.rand.setValue(m.random_error_pct)
        self.bias.setValue(m.systematic_error_pct)
        self.noise.setValue(m.noise_level)
        self.interval.setValue(m.sampling_interval_ms)
        self.seed.setText("")

    def _accept(self):
        s, m = self.settings, self.sim
        try:
            pts = [float(x) for x in self.points.text().replace(";", ",").split(",") if x.strip()]
        except ValueError:
            QMessageBox.warning(self, "입력 오류", "교정점은 숫자를 쉼표로 구분해 입력하세요.")
            return
        s.points = pts
        s.n_series = self.n_series.value()
        s.preload_cycles = self.preload_cycles.value()
        s.preload_torque = self.preload_torque.value() or None
        s.tolerance_pct = self.tolerance.value()
        s.decision_rule = self.rule.currentData()
        s.performed_by = self.performed.text().strip() or "Student"
        s.reviewed_by = self.reviewed.text().strip() or "Instructor"
        s.reference_instrument = self.ref_name.text().strip()
        s.ref_expanded_u_pct = self.ref_u.value()
        s.ref_k = self.ref_k.value()
        s.resolution = self.resolution.value()
        s.additional_u_pct = self.add_u.value()
        s.coverage_k = self.k.value()
        m.preset = self.preset.currentText()
        m.random_error_pct = self.rand.value()
        m.systematic_error_pct = self.bias.value()
        m.noise_level = self.noise.value()
        m.sampling_interval_ms = self.interval.value()
        m.ramp_speed = self.ramp.value()
        m.hold_time = self.hold.value()
        m.inter_step_delay = self.gap.value()
        m.speed_factor = self.speed.value()
        seed = self.seed.text().strip()
        try:
            m.seed = int(seed) if seed else None
        except ValueError:
            QMessageBox.warning(self, "입력 오류", "Random seed는 정수여야 합니다.")
            return
        errs = s.validate() + m.validate()
        if errs:
            QMessageBox.warning(self, "입력 오류", "\n".join(errs))
            return
        self.accept()


# ---------------------------------------------------------------------------
class ResultReviewDialog(QDialog):
    """Calibration Result Review: full calculation table + uncertainty budget."""

    def __init__(self, result: CalibrationResult, settings: CalibrationSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calibration Result Review  교정 결과 검토")
        self.resize(1100, 640)
        lay = QVBoxLayout(self)
        n = settings.n_series
        heads = ["Nominal"] + [f"S{i + 1}" for i in range(n)] + \
                ["Mean", "Error\n(N·m)", "Rel. Error\n(%)", "Correction\n(N·m)", "s",
                 "uA", "uref", "ures", "uadd", "uc", f"U (k={settings.coverage_k:g})",
                 "Simple", "Guarded"]
        t = QTableWidget(len(result.points), len(heads))
        t.setHorizontalHeaderLabels(heads)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for r, p in enumerate(result.points):
            b = p.budget
            vals = [f"{p.nominal:.2f}"] + [f"{v:.2f}" for v in p.values] + [
                f"{p.mean:.3f}", f"{p.error:+.3f}", f"{p.rel_error_pct:+.3f}",
                f"{p.correction:+.3f}", f"{p.std_dev:.4f}"] + \
                [f"{c.u:.4f}" for c in b.components] + \
                [f"{b.uc:.4f}", f"{b.U:.3f}", p.decision_simple, p.decision_guard]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setTextAlignment(Qt.AlignCenter)
                t.setItem(r, c, it)
        lay.addWidget(QLabel("<b>Calculation results</b>  (Mean, Indication Error, Relative "
                             "Error, Correction, Repeatability, Uncertainty)"))
        lay.addWidget(t, 2)
        info = QTextBrowser()
        rule = DECISION_RULE_TEXT[result.decision_rule]
        col = {"PASS": theme.GREEN, "FAIL": theme.RED}.get(result.overall, theme.AMBER)
        html = [f"<h3 style='color:{col}'>Overall conformity: {result.overall}</h3>",
                f"<p><b>Decision rule:</b> {rule}</p>",
                f"<p><b>Tolerance:</b> ±{settings.tolerance_pct:g} % "
                f"&nbsp;<i>({TOLERANCE_NOTE})</i></p>",
                "<p><b>Uncertainty model:</b> uc = √(uA² + uref² + ures² + "
                "uadd²), U = k·uc</p><ul>"]
        html += [f"<li>{a}</li>" for a in assumptions_text(settings)]
        html.append("</ul>")
        info.setHtml("".join(html))
        lay.addWidget(info, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        bb.accepted.connect(self.accept)
        bb.button(QDialogButtonBox.Close).clicked.connect(self.accept)
        lay.addWidget(bb)


# ---------------------------------------------------------------------------
class HistoryDialog(QDialog):
    """Measurement history (측정 이력 조회)."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.selected_id: Optional[int] = None
        self.action: Optional[str] = None
        self.setWindowTitle("Calibration History  측정 이력")
        self.resize(980, 520)
        lay = QVBoxLayout(self)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["ID", "Certificate No.", "Created", "Status",
                                              "Model", "Serial No.", "Measurements", "Result"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.doubleClicked.connect(lambda _: self._done("load"))
        lay.addWidget(self.table)
        row = QHBoxLayout()
        self.btn_load = QPushButton("결과 불러오기 (Load)")
        self.btn_pdf = QPushButton("PDF 재생성")
        self.btn_xlsx = QPushButton("Excel 재생성")
        self.btn_del = QPushButton("삭제 (Delete)")
        self.btn_del.setObjectName("Danger")
        close = QPushButton("닫기")
        for b, a in ((self.btn_load, "load"), (self.btn_pdf, "pdf"), (self.btn_xlsx, "xlsx")):
            b.clicked.connect(lambda _=False, a=a: self._done(a))
            row.addWidget(b)
        self.btn_del.clicked.connect(self._delete)
        row.addWidget(self.btn_del)
        row.addStretch(1)
        close.clicked.connect(self.reject)
        row.addWidget(close)
        lay.addLayout(row)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self._fill()

    def _fill(self):
        recs = self.db.list_calibrations()
        self.table.setRowCount(len(recs))
        self._recs = recs
        for r, rec in enumerate(recs):
            n = self.db.count_measurements(rec.id)
            total = rec.settings.n_series * len(rec.settings.points)
            vals = [str(rec.id), rec.cert_no or "-", rec.created_at.replace("T", " "), rec.status,
                    rec.equipment.model, rec.equipment.serial_number, f"{n} / {total}",
                    rec.overall or "-"]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, c, it)
        self._update_buttons()

    def _current(self):
        rows = self.table.selectionModel().selectedRows()
        return self._recs[rows[0].row()] if rows else None

    def _update_buttons(self):
        rec = self._current()
        done = rec is not None and rec.status == "COMPLETED"
        self.btn_load.setEnabled(rec is not None)
        self.btn_pdf.setEnabled(done)
        self.btn_xlsx.setEnabled(done)
        self.btn_del.setEnabled(rec is not None and rec.status != "IN_PROGRESS")

    def _done(self, action):
        rec = self._current()
        if rec is None:
            return
        if action in ("pdf", "xlsx") and rec.status != "COMPLETED":
            QMessageBox.information(self, "알림", "완료된 교정만 성적서를 재생성할 수 있습니다.")
            return
        self.selected_id, self.action = rec.id, action
        self.accept()

    def _delete(self):
        rec = self._current()
        if rec is None:
            return
        if QMessageBox.question(self, "삭제 확인", f"교정 기록 #{rec.id} 을(를) 삭제할까요?") \
                == QMessageBox.Yes:
            self.db.delete_calibration(rec.id)
            self._fill()
