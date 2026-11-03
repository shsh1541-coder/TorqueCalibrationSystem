"""
Calibration result calculation (section 10).

    Mean               = (M1 + ... + Mn) / n
    Indication error   = Mean - Reference torque              [N·m]
    Relative error     = Error / Reference torque x 100       [%]
    Correction         = Reference torque - Mean              [N·m]
    Repeatability s    = STDEV.S(M1..Mn)
    Uncertainty        -> see uncertainty.py
    Conformity         -> simple or guarded (uncertainty-aware) decision rule
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

from .config import (DECISION_GUARD, DECISION_RULE_TEXT, DECISION_SIMPLE,
                     CalibrationSettings)
from .uncertainty import UncertaintyBudget, evaluate_point, sample_std

PASS = "PASS"
FAIL = "FAIL"
INCONCLUSIVE = "INCONCLUSIVE"


@dataclass
class PointResult:
    nominal: float
    values: List[float]
    mean: float
    error: float
    rel_error_pct: float
    correction: float
    std_dev: float
    budget: UncertaintyBudget
    tolerance_abs: float
    decision_simple: str
    decision_guard: str

    @property
    def U(self) -> float:
        return self.budget.U

    @property
    def uA(self) -> float:
        return self.budget.component("uA").u

    def decision(self, rule: str) -> str:
        return self.decision_guard if rule == DECISION_GUARD else self.decision_simple

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["budget"] = self.budget.to_dict()
        return d


@dataclass
class CalibrationResult:
    points: List[PointResult]
    tolerance_pct: float
    decision_rule: str
    overall: str
    notes: List[str] = field(default_factory=list)

    @property
    def decision_rule_text(self) -> str:
        return DECISION_RULE_TEXT[self.decision_rule]

    @property
    def max_abs_rel_error(self) -> float:
        return max((abs(p.rel_error_pct) for p in self.points), default=0.0)

    @property
    def max_U(self) -> float:
        return max((p.U for p in self.points), default=0.0)

    def to_dict(self) -> Dict:
        return {"tolerance_pct": self.tolerance_pct, "decision_rule": self.decision_rule,
                "overall": self.overall, "points": [p.to_dict() for p in self.points]}


def decide_simple(rel_error_pct: float, tolerance_pct: float) -> str:
    return PASS if abs(rel_error_pct) <= tolerance_pct + 1e-12 else FAIL


def decide_guarded(error: float, U: float, tolerance_abs: float) -> str:
    """Guard band w = U (concept of ILAC-G8:2019, educational)."""
    if abs(error) + U <= tolerance_abs + 1e-12:
        return PASS
    if abs(error) - U > tolerance_abs:
        return FAIL
    return INCONCLUSIVE


def overall_decision(decisions: Iterable[str]) -> str:
    ds = list(decisions)
    if not ds:
        return INCONCLUSIVE
    if any(d == FAIL for d in ds):
        return FAIL
    if any(d == INCONCLUSIVE for d in ds):
        return INCONCLUSIVE
    return PASS


def calculate_point(nominal: float, values: Sequence[float],
                    settings: CalibrationSettings) -> PointResult:
    vals = [float(v) for v in values]
    if len(vals) < 2:
        raise ValueError("At least two series are required to calculate a point.")
    mean = sum(vals) / len(vals)
    error = mean - nominal
    rel = error / nominal * 100.0
    corr = nominal - mean
    s = sample_std(vals)
    budget = evaluate_point(nominal, vals, settings)
    tol_abs = settings.tolerance_pct / 100.0 * nominal
    return PointResult(
        nominal=float(nominal), values=vals, mean=mean, error=error, rel_error_pct=rel,
        correction=corr, std_dev=s, budget=budget, tolerance_abs=tol_abs,
        decision_simple=decide_simple(rel, settings.tolerance_pct),
        decision_guard=decide_guarded(error, budget.U, tol_abs),
    )


def values_matrix(measurements: Dict[Tuple[int, int], object],
                  settings: CalibrationSettings) -> List[List[Optional[float]]]:
    """Rows = calibration points, columns = series. Missing values -> None."""
    rows = []
    for i, _ in enumerate(settings.points):
        row = []
        for s in range(1, settings.n_series + 1):
            m = measurements.get((s, i))
            row.append(None if m is None else float(getattr(m, "value", m)))
        rows.append(row)
    return rows


def calculate(measurements: Dict[Tuple[int, int], object],
              settings: CalibrationSettings) -> CalibrationResult:
    """Calculate all points. Requires the complete set of measurements."""
    matrix = values_matrix(measurements, settings)
    missing = sum(v is None for row in matrix for v in row)
    if missing:
        raise ValueError(f"Calibration incomplete: {missing} measurement(s) missing.")
    points = [calculate_point(p, row, settings) for p, row in zip(settings.points, matrix)]
    rule = settings.decision_rule if settings.decision_rule in (DECISION_SIMPLE, DECISION_GUARD) \
        else DECISION_SIMPLE
    overall = overall_decision(p.decision(rule) for p in points)
    return CalibrationResult(points, settings.tolerance_pct, rule, overall)


def partial_row(values: Sequence[Optional[float]], nominal: float):
    """Mean and relative error for a partially filled row (live table)."""
    vals = [v for v in values if v is not None]
    if not vals:
        return None, None
    mean = sum(vals) / len(vals)
    return mean, (mean - nominal) / nominal * 100.0


# ------------------------------------------------------------------ pandas
def measurements_dataframe(measurements: Dict[Tuple[int, int], object],
                           settings: CalibrationSettings) -> pd.DataFrame:
    rows = []
    for (s, i), m in sorted(measurements.items()):
        rows.append({"No.": len(rows) + 1, "Series": s, "Point": i + 1,
                     "Nominal (N·m)": settings.points[i], "Measured (N·m)": m.value,
                     "Deviation (N·m)": m.value - settings.points[i],
                     "Timestamp": m.timestamp})
    return pd.DataFrame(rows)


def results_dataframe(result: CalibrationResult, n_series: int) -> pd.DataFrame:
    rows = []
    for p in result.points:
        row = {"Nominal (N·m)": p.nominal}
        for k in range(n_series):
            row[f"Series {k + 1}"] = p.values[k]
        row.update({"Mean": p.mean, "Error (N·m)": p.error, "Error (%)": p.rel_error_pct,
                    "Correction": p.correction, "s": p.std_dev, "uA": p.uA,
                    "uc": p.budget.uc, "U (k=2)": p.U,
                    "Decision": p.decision(result.decision_rule)})
        rows.append(row)
    return pd.DataFrame(rows)
