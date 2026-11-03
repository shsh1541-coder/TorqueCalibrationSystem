"""Simulation, sequence and data-integrity tests (Qt independent)."""
import pytest

from src.config import (SPEED_FAST, SPEED_NORMAL, SPEED_PRESENTATION, CalibrationSettings,
                        EquipmentInfo, SimulationSettings)
from src.data_source import (PHASE_APPLIED, PHASE_APPROACHING, PHASE_CAPTURED, PHASE_INCREASING,
                             PHASE_RELEASING, PHASE_ZERO, HardwareTorqueSource,
                             SimulatedTorqueSource)
from src.database import STATUS_IN_PROGRESS, Database, DatabaseRecorder
from src.simulator import (KIND_MEASURE, KIND_PRELOAD, STATE_COMPLETED, STATE_PAUSED,
                           STATE_RUNNING, STATE_STOPPED, STATE_WAITING, CalibrationEngine,
                           EngineListener)


def make_engine(seed=1, preset=SPEED_NORMAL, **settings):
    sim = SimulationSettings(seed=seed)
    sim.apply_preset(preset)
    s = CalibrationSettings(**settings)
    return CalibrationEngine(SimulatedTorqueSource(sim, s.resolution), EquipmentInfo(), s, sim)


class Recorder(EngineListener):
    def __init__(self):
        self.steps, self.phases, self.samples, self.events = [], [], [], []
        self.preload_done = 0
        self.completed = 0

    def on_step_started(self, step):
        self.steps.append(step)

    def on_phase_changed(self, step, phase):
        self.phases.append((step.index, phase))

    def on_sample(self, step, t_total, t_step, torque, phase):
        self.samples.append((step.index if step else None, t_total, torque, phase))

    def on_preloading_completed(self):
        self.preload_done += 1

    def on_completed(self):
        self.completed += 1

    def on_log(self, phase, message):
        self.events.append((phase, message))


def test_sequence_3_preloads_and_15_measurements():
    e = make_engine()
    rec = Recorder()
    e.add_listener(rec)
    e.start()
    e.run_to_completion()
    assert e.state == STATE_COMPLETED
    assert len(rec.steps) == 18
    assert [s.kind for s in rec.steps[:3]] == [KIND_PRELOAD] * 3
    assert all(s.target == 100.0 for s in rec.steps[:3])
    order = [(s.series, s.target) for s in rec.steps[3:]]
    assert order == [(sr, p) for sr in (1, 2, 3) for p in (20.0, 40.0, 60.0, 80.0, 100.0)]
    assert len(e.preloads) == 3
    assert len(e.measurements) == 15
    assert rec.preload_done == 1 and rec.completed == 1
    assert any("PRELOADING COMPLETED" in m for _, m in rec.events)


def test_signal_phases_and_continuous_ramp():
    e = make_engine()
    rec = Recorder()
    e.add_listener(rec)
    e.start()
    e.run_to_completion()
    first = [p for i, p in rec.phases if i == 3]   # first measurement step
    assert first == [PHASE_ZERO, PHASE_INCREASING, PHASE_APPROACHING, PHASE_APPLIED,
                     PHASE_CAPTURED, PHASE_RELEASING]
    inc = [tq for idx, _, tq, ph in rec.samples if idx == 3 and ph == PHASE_INCREASING]
    assert len(inc) > 5
    assert all(b >= a - 0.2 for a, b in zip(inc, inc[1:]))    # increases (noise tolerant)
    rel = [tq for idx, _, tq, ph in rec.samples if idx == 3 and ph == PHASE_RELEASING]
    assert rel[-1] == 0.0
    dt = rec.samples[1][1] - rec.samples[0][1]
    assert dt == pytest.approx(0.05)                           # 50 ms sampling


def test_data_integrity_series_and_points():
    e = make_engine()
    e.start()
    e.run_to_completion()
    for (series, idx), m in e.measurements.items():
        assert m.series == series and m.point_index == idx
        assert m.target == e.settings.points[idx]
        assert abs(m.value - m.target) <= m.target * 0.0056 + 0.01   # random 0.4 % + bias 0.15 %
    assert sorted(e.measurements) == [(s, i) for s in (1, 2, 3) for i in range(5)]


def test_values_differ_between_runs_without_seed():
    a, b = make_engine(seed=None), make_engine(seed=None)
    for e in (a, b):
        e.start()
        e.run_to_completion()
    va = [m.value for _, m in sorted(a.measurements.items())]
    vb = [m.value for _, m in sorted(b.measurements.items())]
    assert va != vb


@pytest.mark.parametrize("preset", [SPEED_FAST, SPEED_PRESENTATION])
def test_speed_does_not_change_results(preset):
    ref = make_engine(seed=7, preset=SPEED_NORMAL)
    other = make_engine(seed=7, preset=preset)
    for e in (ref, other):
        e.start()
        e.run_to_completion()
    assert {k: m.value for k, m in ref.measurements.items()} == \
           {k: m.value for k, m in other.measurements.items()}


def test_presentation_mode_under_90_seconds_real_time():
    e = make_engine(preset=SPEED_PRESENTATION)
    est = e.estimated_duration()
    assert est < 90
    e.start()
    real, dt = 0.0, 0.05
    while e.state == STATE_RUNNING:
        e.advance(dt)
        real += dt
    assert e.state == STATE_COMPLETED
    assert real < 90
    assert abs(real - est) < 5


def test_pause_resume_continues_from_same_point():
    e = make_engine()
    e.start()
    for _ in range(600):
        e.advance(0.05)
    done = dict(e.measurements)
    step_idx = e.step_idx
    e.pause()
    assert e.state == STATE_PAUSED
    for _ in range(500):
        assert e.advance(0.05) == 0            # nothing happens while paused
    assert e.step_idx == step_idx and dict(e.measurements) == done
    e.resume()
    e.run_to_completion()
    assert e.state == STATE_COMPLETED and len(e.measurements) == 15
    for k, m in done.items():
        assert e.measurements[k] is m


def test_stop_and_restart():
    e = make_engine()
    e.start()
    for _ in range(400):
        e.advance(0.05)
    e.stop()
    assert e.state == STATE_STOPPED
    assert e.advance(1.0) == 0
    e.start()                                  # new run after stop
    assert e.state == STATE_RUNNING and not e.measurements
    e.run_to_completion()
    assert len(e.measurements) == 15


def test_reset_clears_data():
    e = make_engine()
    e.start()
    e.run_to_completion()
    e.reset()
    assert not e.measurements and not e.preloads and e.step_idx == 0


def test_manual_mode_waits_for_next():
    e = make_engine()
    e.set_manual(True)
    e.start()
    e.run_to_completion()
    assert e.state == STATE_WAITING and e.step_idx == 1
    assert e.next_measurement()
    e.run_to_completion()
    assert e.state == STATE_WAITING and e.step_idx == 2
    e.set_manual(False)                        # switching back to AUTO continues
    e.run_to_completion()
    assert e.state == STATE_COMPLETED


def test_no_duplicate_storage(tmp_path):
    db = Database(tmp_path / "t.db")
    e = make_engine()
    cal = db.create_calibration(e.equipment, e.settings, e.sim)
    e.add_listener(DatabaseRecorder(db, cal))
    e.start()
    e.run_to_completion()
    assert db.count_measurements(cal) == 15
    assert len(db.get_preloads(cal)) == 3
    m = db.get_measurements(cal)[0]
    assert db.add_measurement(cal, m) is False         # UNIQUE constraint
    assert db.count_measurements(cal) == 15


def test_crash_recovery_resumes_after_last_point(tmp_path):
    db = Database(tmp_path / "t.db")
    e = make_engine()
    cal = db.create_calibration(e.equipment, e.settings, e.sim)
    e.add_listener(DatabaseRecorder(db, cal))
    e.start()
    while len(e.measurements) < 7:
        e.advance(0.05)
    db.close()                                   # "crash": nothing else is written
    db2 = Database(tmp_path / "t.db")
    rec = db2.find_unfinished()
    assert rec is not None and rec.id == cal and rec.status == STATUS_IN_PROGRESS
    e2 = CalibrationEngine(SimulatedTorqueSource(rec.sim), rec.equipment, rec.settings, rec.sim)
    e2.add_listener(DatabaseRecorder(db2, cal))
    e2.restore(db2.get_preloads(cal), db2.get_measurements(cal))
    assert e2.state == STATE_PAUSED
    assert e2.step_idx == 3 + 7
    e2.resume()
    e2.run_to_completion()
    assert e2.state == STATE_COMPLETED
    assert db2.count_measurements(cal) == 15


def test_hardware_source_is_interface_only():
    hw = HardwareTorqueSource()
    assert hw.is_simulated is False
    assert hw.connect() is False
    with pytest.raises(NotImplementedError):
        hw.begin_application(10)
    e = CalibrationEngine(hw, EquipmentInfo(), CalibrationSettings(), SimulationSettings())
    with pytest.raises(RuntimeError):
        e.start()


def test_preload_excluded_from_results(completed_engine):
    from src.calibration import calculate
    r = calculate(completed_engine.measurements, completed_engine.settings)
    p100 = r.points[-1]
    expected = [completed_engine.measurements[(s, 4)].value for s in (1, 2, 3)]
    assert p100.values == expected
    assert len(completed_engine.preloads) == 3


def test_custom_settings_points_and_series():
    e = make_engine(points=[10, 50, 90], n_series=4, preload_cycles=1)
    e.start()
    e.run_to_completion()
    assert len(e.steps) == 1 + 12 and len(e.measurements) == 12
