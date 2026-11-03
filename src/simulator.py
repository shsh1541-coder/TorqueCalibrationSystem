"""
Automatic calibration sequence engine (Qt independent).

The engine walks through the sequence of section 4:

    Preloading x N  ->  Series 1 (all points)  ->  ...  ->  Series n

It is driven by ``advance(real_dt)`` which the GUI calls from a 50 ms QTimer in
the main thread. Each call converts real time into simulated time
(``speed_factor``) and processes the virtual device samples that fall into that
time. Because the work per call is tiny, the GUI never blocks and there are no
threads, locks or race conditions - which also guarantees that a measurement
can never be stored twice.

Listeners receive callbacks (``on_sample``, ``on_capture`` ...) so the same
engine is used by the GUI, by the database recorder and by the tests.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

from .config import CalibrationSettings, EquipmentInfo, SimulationSettings
from .data_source import PHASE_CAPTURED, PHASE_ZERO, TorqueDataSource

# Engine states
STATE_IDLE = "IDLE"
STATE_RUNNING = "RUNNING"
STATE_PAUSED = "PAUSED"
STATE_WAITING = "WAITING"          # manual mode: waiting for NEXT MEASUREMENT
STATE_STOPPED = "STOPPED"
STATE_COMPLETED = "COMPLETED"

KIND_PRELOAD = "preload"
KIND_MEASURE = "measure"


@dataclass(frozen=True)
class Step:
    index: int            # position in the whole sequence (0-based)
    kind: str             # preload | measure
    target: float         # N·m
    cycle: int = 0        # preload cycle (1-based) for preload steps
    series: int = 0       # series (1-based) for measurement steps
    point_index: int = 0  # point index (0-based) for measurement steps

    @property
    def label(self) -> str:
        if self.kind == KIND_PRELOAD:
            return f"Preload {self.cycle}  @ {self.target:.2f} N·m"
        return f"Series {self.series} / Point {self.point_index + 1}  @ {self.target:.2f} N·m"


@dataclass
class Measurement:
    series: int
    point_index: int
    target: float
    value: float
    timestamp: str


@dataclass
class PreloadRecord:
    cycle: int
    target: float
    peak: float
    timestamp: str


class EngineListener:
    """No-op base class; override what you need."""

    def on_state_changed(self, state: str) -> None: ...
    def on_step_started(self, step: Step) -> None: ...
    def on_sample(self, step: Optional[Step], t_total: float, t_step: float,
                  torque: float, phase: str) -> None: ...
    def on_phase_changed(self, step: Step, phase: str) -> None: ...
    def on_preload_captured(self, record: PreloadRecord) -> None: ...
    def on_measurement_captured(self, step: Step, m: Measurement) -> None: ...
    def on_step_finished(self, step: Step) -> None: ...
    def on_preloading_completed(self) -> None: ...
    def on_series_completed(self, series: int) -> None: ...
    def on_completed(self) -> None: ...
    def on_log(self, phase: str, message: str) -> None: ...


def build_steps(settings: CalibrationSettings, equipment: EquipmentInfo) -> List[Step]:
    steps: List[Step] = []
    preload_target = settings.effective_preload_torque(equipment.capacity)
    for c in range(settings.preload_cycles):
        steps.append(Step(len(steps), KIND_PRELOAD, preload_target, cycle=c + 1))
    for s in range(settings.n_series):
        for i, p in enumerate(settings.points):
            steps.append(Step(len(steps), KIND_MEASURE, float(p), series=s + 1, point_index=i))
    return steps


def now_iso() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


class CalibrationEngine:
    MAX_SAMPLES_PER_ADVANCE = 400   # protects against huge catch-up after a stall

    def __init__(self, source: TorqueDataSource, equipment: EquipmentInfo,
                 settings: CalibrationSettings, sim: SimulationSettings):
        self.source = source
        self.equipment = equipment
        self.settings = settings
        self.sim = sim
        self.listeners: List[EngineListener] = []
        self.manual_mode = False
        self._clock: Callable[[], str] = now_iso
        self.reset()

    # ------------------------------------------------------------------ setup
    def add_listener(self, listener: EngineListener) -> None:
        if listener not in self.listeners:
            self.listeners.append(listener)

    def remove_listener(self, listener: EngineListener) -> None:
        if listener in self.listeners:
            self.listeners.remove(listener)

    def configure(self, equipment: EquipmentInfo, settings: CalibrationSettings,
                  sim: SimulationSettings) -> None:
        if self.state in (STATE_RUNNING, STATE_PAUSED, STATE_WAITING):
            raise RuntimeError("Cannot change settings while a calibration is in progress.")
        self.equipment, self.settings, self.sim = equipment, settings, sim
        if hasattr(self.source, "sim"):
            self.source.sim = sim
        if hasattr(self.source, "resolution"):
            self.source.resolution = settings.resolution
        self.reset()

    def reset(self) -> None:
        self.steps: List[Step] = build_steps(self.settings, self.equipment)
        self.state = STATE_IDLE
        self.step_idx = 0
        self.current: Optional[Step] = None
        self.preloads: Dict[int, PreloadRecord] = {}
        self.measurements: Dict[Tuple[int, int], Measurement] = {}
        self.t_total = 0.0
        self._acc = 0.0
        self._gap_left = 0.0
        self._last_phase: Optional[str] = None
        self._captured_this_step = False
        self._preload_done_emitted = False
        if hasattr(self.source, "abort_application"):
            self.source.abort_application()

    # ------------------------------------------------------------- properties
    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def n_measurements_total(self) -> int:
        return self.settings.n_series * len(self.settings.points)

    @property
    def n_measurements_done(self) -> int:
        return len(self.measurements)

    @property
    def is_active(self) -> bool:
        return self.state in (STATE_RUNNING, STATE_PAUSED, STATE_WAITING)

    @property
    def is_complete(self) -> bool:
        return self.state == STATE_COMPLETED and self.n_measurements_done == self.n_measurements_total

    def next_step(self) -> Optional[Step]:
        return self.steps[self.step_idx] if self.step_idx < len(self.steps) else None

    # ---------------------------------------------------------------- control
    def start(self) -> None:
        if self.is_active:
            return
        if self.state in (STATE_COMPLETED, STATE_STOPPED):
            self.reset()
        if not self.source.connect():
            raise RuntimeError(f"Cannot connect to data source: {self.source.name}")
        self.source.reset_run()
        self._log("SYSTEM", f"Calibration started ({self.source.name}).")
        self._set_state(STATE_RUNNING)
        self._gap_left = 0.0

    def restore(self, preloads: List[PreloadRecord], measurements: List[Measurement]) -> None:
        """Restore a partially completed run (crash recovery). Engine goes PAUSED."""
        self.reset()
        for p in preloads:
            self.preloads[p.cycle] = p
        for m in measurements:
            self.measurements[(m.series, m.point_index)] = m
        idx = 0
        for st in self.steps:
            done = (st.cycle in self.preloads) if st.kind == KIND_PRELOAD else \
                ((st.series, st.point_index) in self.measurements)
            if not done:
                break
            idx += 1
        self.step_idx = idx
        self._preload_done_emitted = idx >= self.settings.preload_cycles
        self.source.connect()
        self.source.reset_run()
        if idx >= len(self.steps):
            self._set_state(STATE_COMPLETED)
        else:
            self._log("SYSTEM", f"Recovered run: resuming at step {idx + 1}/{len(self.steps)}.")
            self._set_state(STATE_PAUSED)

    def pause(self) -> None:
        if self.state in (STATE_RUNNING, STATE_WAITING):
            self._resume_to = self.state
            self._log("SYSTEM", "Paused.")
            self._set_state(STATE_PAUSED)

    def resume(self) -> None:
        if self.state == STATE_PAUSED:
            target = getattr(self, "_resume_to", STATE_RUNNING)
            self._log("SYSTEM", "Resumed.")
            self._set_state(target)

    def stop(self) -> None:
        if self.is_active:
            self.source.abort_application()
            self.current = None
            self._log("SYSTEM", "Calibration stopped by operator.")
            self._set_state(STATE_STOPPED)

    def set_manual(self, manual: bool) -> None:
        self.manual_mode = bool(manual)
        self._log("SYSTEM", f"Mode: {'MANUAL' if manual else 'AUTO'}.")
        if not manual and self.state == STATE_WAITING:
            self._set_state(STATE_RUNNING)

    def next_measurement(self) -> bool:
        if self.state == STATE_WAITING:
            self._set_state(STATE_RUNNING)
            self._gap_left = 0.0
            return True
        return False

    # ------------------------------------------------------------ simulation
    def advance(self, real_dt: float) -> int:
        """Advance by ``real_dt`` seconds of wall-clock time. Returns samples processed."""
        if self.state != STATE_RUNNING:
            return 0
        interval = self.sim.sampling_interval_ms / 1000.0
        self._acc += max(0.0, real_dt) * self.sim.speed_factor
        n = 0
        while self._acc >= interval - 1e-12 and self.state == STATE_RUNNING:
            self._acc -= interval
            self._process_sample(interval)
            n += 1
            if n >= self.MAX_SAMPLES_PER_ADVANCE:
                self._acc = 0.0
                break
        return n

    def run_to_completion(self, max_samples: int = 10_000_000) -> int:
        """Process samples without real time (tests / batch). Respects manual mode."""
        interval = self.sim.sampling_interval_ms / 1000.0
        n = 0
        while self.state == STATE_RUNNING and n < max_samples:
            self._process_sample(interval)
            n += 1
        return n

    def _process_sample(self, dt: float) -> None:
        self.t_total += dt
        if self.current is None:
            if self._gap_left > 0:
                self._gap_left -= dt
                self._emit_sample(None, 0.0, self.source.idle_sample(dt), PHASE_ZERO)
                return
            st = self.next_step()
            if st is None:
                self._finish()
                return
            self._begin_step(st)
            return

        sample = self.source.read_sample(dt)
        if sample.phase != self._last_phase:
            self._last_phase = sample.phase
            for l in self.listeners:
                l.on_phase_changed(self.current, sample.phase)
        self._emit_sample(self.current, sample.t, sample.torque, sample.phase)

        if sample.captured is not None and not self._captured_this_step:
            self._captured_this_step = True
            self._record_capture(self.current, sample.captured)

        if self.source.application_done:
            self._end_step()

    def _begin_step(self, st: Step) -> None:
        self.current = st
        self._captured_this_step = False
        self._last_phase = None
        self.source.begin_application(st.target)
        if st.kind == KIND_PRELOAD:
            self._log("PRELOAD", f"Preload cycle {st.cycle}/{self.settings.preload_cycles} "
                                 f"started, target {st.target:.2f} N·m.")
        else:
            self._log("MEASURE", f"Series {st.series}/{self.settings.n_series}, point "
                                 f"{st.point_index + 1}/{len(self.settings.points)} started, "
                                 f"target {st.target:.2f} N·m.")
        for l in self.listeners:
            l.on_step_started(st)

    def _record_capture(self, st: Step, value: float) -> None:
        ts = self._clock()
        if st.kind == KIND_PRELOAD:
            if st.cycle in self.preloads:
                return  # duplicate guard
            rec = PreloadRecord(st.cycle, st.target, value, ts)
            self.preloads[st.cycle] = rec
            self._log("PRELOAD", f"Preload {st.cycle} peak {value:.2f} N·m.")
            for l in self.listeners:
                l.on_preload_captured(rec)
        else:
            key = (st.series, st.point_index)
            if key in self.measurements:
                return  # duplicate guard
            m = Measurement(st.series, st.point_index, st.target, value, ts)
            self.measurements[key] = m
            self._log("CAPTURE", f"MEASUREMENT CAPTURED  S{st.series} P{st.point_index + 1}: "
                                 f"{value:.2f} N·m (target {st.target:.2f}).")
            for l in self.listeners:
                l.on_measurement_captured(st, m)

    def _end_step(self) -> None:
        st = self.current
        self.current = None
        self.step_idx += 1
        for l in self.listeners:
            l.on_step_finished(st)
        if st.kind == KIND_PRELOAD and st.cycle == self.settings.preload_cycles \
                and not self._preload_done_emitted:
            self._preload_done_emitted = True
            self._log("PRELOAD", "PRELOADING COMPLETED")
            for l in self.listeners:
                l.on_preloading_completed()
        if st.kind == KIND_MEASURE and st.point_index == len(self.settings.points) - 1:
            self._log("MEASURE", f"Series {st.series} completed.")
            for l in self.listeners:
                l.on_series_completed(st.series)
        if self.step_idx >= len(self.steps):
            self._finish()
            return
        self._gap_left = self.sim.inter_step_delay
        if self.manual_mode:
            self._set_state(STATE_WAITING)

    def _finish(self) -> None:
        self.current = None
        self._log("SYSTEM", f"CALIBRATION COMPLETED - {self.n_measurements_done}/"
                            f"{self.n_measurements_total} measurements.")
        self._set_state(STATE_COMPLETED)
        for l in self.listeners:
            l.on_completed()

    # ---------------------------------------------------------------- helpers
    def _emit_sample(self, st, t_step, torque, phase):
        for l in self.listeners:
            l.on_sample(st, self.t_total, t_step, torque, phase)

    def _set_state(self, state: str) -> None:
        if state != self.state:
            self.state = state
            for l in self.listeners:
                l.on_state_changed(state)

    def _log(self, phase: str, message: str) -> None:
        for l in self.listeners:
            l.on_log(phase, message)

    # ------------------------------------------------------------ estimation
    def estimated_duration(self) -> float:
        """Estimated wall-clock duration (s) of a complete run with current settings."""
        sim_t = 0.0
        src = type(self.source)
        zero = getattr(src, "ZERO_TIME", 0.25)
        frac = getattr(src, "APPROACH_FRACTION", 0.88)
        arate = getattr(src, "APPROACH_RATE", 0.3)
        rrate = getattr(src, "RELEASE_RATE", 2.0)
        r = self.sim.ramp_speed
        for st in self.steps:
            v = st.target
            sim_t += zero + frac * v / r + (1 - frac) * v / (r * arate) + self.sim.hold_time \
                + v / (r * rrate) + self.sim.inter_step_delay
        return sim_t / self.sim.speed_factor


def wall_clock() -> float:
    return time.monotonic()
