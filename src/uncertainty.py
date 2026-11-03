"""
Measurement uncertainty evaluation (GUM approach, simplified for education).

Per calibration point:

    uA    = s / sqrt(n)                          Type A, repeatability of the mean
    uref  = (U_ref% / k_ref) / 100 * T           reference standard (from its certificate)
    ures  = r / (2 * sqrt(3))                    resolution, rectangular distribution
    uadd  = u_add% / 100 * T                     additional component (environment, etc.)
    uc    = sqrt(uA^2 + uref^2 + ures^2 + uadd^2)
    U     = k * uc                               default k = 2

Assumptions (also shown in the GUI and on the certificate):
  * All input quantities are uncorrelated, sensitivity coefficients = 1.
  * k = 2 is used as the coverage factor. With only n = 3 readings the Type A
    component has 2 degrees of freedom; a rigorous evaluation would use the
    Welch-Satterthwaite effective degrees of freedom and a larger k. This is a
    deliberate educational simplification.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Dict, List, Sequence

import numpy as np

from .config import CalibrationSettings


@dataclass
class UncertaintyComponent:
    symbol: str
    name: str
    source_value: str        # human readable input value
    distribution: str
    divisor: str
    u: float                 # standard uncertainty, N·m

    def to_dict(self):
        return asdict(self)


@dataclass
class UncertaintyBudget:
    nominal: float
    components: List[UncertaintyComponent]
    uc: float
    k: float
    U: float

    @property
    def U_rel_pct(self) -> float:
        return self.U / self.nominal * 100.0 if self.nominal else 0.0

    def component(self, symbol: str) -> UncertaintyComponent:
        for c in self.components:
            if c.symbol == symbol:
                return c
        raise KeyError(symbol)

    def to_dict(self) -> Dict:
        return {"nominal": self.nominal, "uc": self.uc, "k": self.k, "U": self.U,
                "U_rel_pct": self.U_rel_pct,
                "components": [c.to_dict() for c in self.components]}


def sample_std(values: Sequence[float]) -> float:
    """Sample standard deviation (Excel STDEV.S)."""
    if len(values) < 2:
        return 0.0
    return float(np.std(np.asarray(values, dtype=float), ddof=1))


def evaluate_point(nominal: float, values: Sequence[float],
                   settings: CalibrationSettings) -> UncertaintyBudget:
    n = len(values)
    s = sample_std(values)
    u_a = s / math.sqrt(n) if n else 0.0
    u_ref = settings.ref_expanded_u_pct / settings.ref_k / 100.0 * nominal
    u_res = settings.resolution / (2.0 * math.sqrt(3.0))
    u_add = settings.additional_u_pct / 100.0 * nominal
    comps = [
        UncertaintyComponent("uA", "Type A - Repeatability (A형)", f"s = {s:.4f} N·m, n = {n}",
                             "Normal", f"√{n}", u_a),
        UncertaintyComponent("uref", "Reference Standard (기준기)",
                             f"U = {settings.ref_expanded_u_pct:g} % (k={settings.ref_k:g})",
                             "Normal", f"{settings.ref_k:g}", u_ref),
        UncertaintyComponent("ures", "Resolution (분해능)", f"r = {settings.resolution:g} N·m",
                             "Rectangular", "2√3", u_res),
        UncertaintyComponent("uadd", "Additional (추가 성분)",
                             f"u = {settings.additional_u_pct:g} % of reading",
                             "Normal (std. u)", "1", u_add),
    ]
    uc = math.sqrt(sum(c.u ** 2 for c in comps))
    U = settings.coverage_k * uc
    return UncertaintyBudget(nominal, comps, uc, settings.coverage_k, U)


def assumptions_text(settings: CalibrationSettings) -> List[str]:
    return [
        "Input quantities are assumed uncorrelated; sensitivity coefficients = 1.",
        f"Type A: uA = s / √n (n = {settings.n_series}).",
        f"Reference standard: U = {settings.ref_expanded_u_pct:g} % of reading at "
        f"k = {settings.ref_k:g} (educational assumption).",
        f"Resolution r = {settings.resolution:g} N·m, rectangular distribution, "
        "u = r / (2√3).",
        f"Additional standard uncertainty = {settings.additional_u_pct:g} % of reading "
        "(environment / reproducibility allowance, assumed).",
        f"Expanded uncertainty U = k · uc with k = {settings.coverage_k:g}. "
        "With n = 3 the Type A component has only 2 degrees of freedom; a full GUM "
        "evaluation (Welch-Satterthwaite) would give a larger k. Simplified on purpose.",
    ]
