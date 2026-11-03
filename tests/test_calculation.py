"""Calculation tests: mean, error, correction, repeatability, uncertainty, decisions."""
import math

import numpy as np
import pytest

from src.calibration import (FAIL, INCONCLUSIVE, PASS, calculate, calculate_point, decide_guarded,
                             decide_simple, overall_decision, partial_row)
from src.config import CalibrationSettings
from src.simulator import Measurement
from src.uncertainty import evaluate_point, sample_std


def test_point_basic_formulas():
    s = CalibrationSettings()
    p = calculate_point(40.0, [40.10, 40.20, 40.30], s)
    assert p.mean == pytest.approx(40.20)
    assert p.error == pytest.approx(0.20)                  # Mean - Reference
    assert p.rel_error_pct == pytest.approx(0.5)           # 0.20 / 40 * 100
    assert p.correction == pytest.approx(-0.20)            # Reference - Mean
    assert p.std_dev == pytest.approx(0.10)                # STDEV.S
    assert p.uA == pytest.approx(0.10 / math.sqrt(3))      # s / sqrt(3)


def test_sample_std_matches_excel_stdev_s():
    vals = [99.78, 100.34, 100.34]
    assert sample_std(vals) == pytest.approx(np.std(vals, ddof=1))
    assert sample_std(vals) == pytest.approx(0.3233161507, rel=1e-9)


def test_uncertainty_budget_rss_and_k():
    s = CalibrationSettings(ref_expanded_u_pct=0.2, ref_k=2, resolution=0.01, additional_u_pct=0.05,
                            coverage_k=2)
    b = evaluate_point(100.0, [100.0, 100.2, 99.8], s)
    uA = 0.2 / math.sqrt(3)
    uref = 0.1
    ures = 0.01 / (2 * math.sqrt(3))
    uadd = 0.05
    uc = math.sqrt(uA ** 2 + uref ** 2 + ures ** 2 + uadd ** 2)
    assert b.component("uA").u == pytest.approx(uA)
    assert b.component("uref").u == pytest.approx(uref)
    assert b.component("ures").u == pytest.approx(ures)
    assert b.component("uadd").u == pytest.approx(uadd)
    assert b.uc == pytest.approx(uc)
    assert b.U == pytest.approx(2 * uc)
    assert b.U_rel_pct == pytest.approx(2 * uc)


def test_simple_decision():
    assert decide_simple(3.99, 4.0) == PASS
    assert decide_simple(-4.0, 4.0) == PASS
    assert decide_simple(4.01, 4.0) == FAIL


def test_guarded_decision():
    tol = 4.0      # N·m
    assert decide_guarded(3.0, 0.5, tol) == PASS            # 3.5 <= 4
    assert decide_guarded(3.8, 0.5, tol) == INCONCLUSIVE    # 4.3 > 4 but 3.3 <= 4
    assert decide_guarded(-4.6, 0.5, tol) == FAIL           # 4.1 > 4
    assert overall_decision([PASS, PASS]) == PASS
    assert overall_decision([PASS, INCONCLUSIVE]) == INCONCLUSIVE
    assert overall_decision([INCONCLUSIVE, FAIL]) == FAIL


def test_tolerance_is_editable():
    p = calculate_point(20.0, [20.5, 20.5, 20.5], CalibrationSettings(tolerance_pct=2.0))
    assert p.rel_error_pct == pytest.approx(2.5)
    assert p.decision_simple == FAIL
    p = calculate_point(20.0, [20.5, 20.5, 20.5], CalibrationSettings(tolerance_pct=4.0))
    assert p.decision_simple == PASS


def test_calculate_requires_complete_data():
    s = CalibrationSettings()
    m = {(1, 0): Measurement(1, 0, 20, 20.0, "t")}
    with pytest.raises(ValueError):
        calculate(m, s)


def test_full_calculation_and_overall(completed_engine):
    r = calculate(completed_engine.measurements, completed_engine.settings)
    assert len(r.points) == 5
    for p, nominal in zip(r.points, [20, 40, 60, 80, 100]):
        assert p.nominal == nominal
        assert len(p.values) == 3
        assert p.mean == pytest.approx(sum(p.values) / 3)
        assert p.U > 0
    assert r.overall == PASS      # default simulation error (±0.4 %) is far inside ±4 %


def test_partial_row():
    mean, rel = partial_row([20.1, None, None], 20.0)
    assert mean == pytest.approx(20.1)
    assert rel == pytest.approx(0.5)
    assert partial_row([None, None], 20.0) == (None, None)
