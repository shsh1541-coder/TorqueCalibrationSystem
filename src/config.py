"""
Configuration data models and default values.

All defaults below match the project specification (section 3) and are what the
application shows on first launch. Every value can be edited from the GUI.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any, Dict, List, Optional

APP_NAME = "TorqueCalibration"
APP_TITLE = "TORQUE CALIBRATION SYSTEM"
APP_SUBTITLE = "Automatic Torque Wrench Calibration Simulator"
APP_VERSION = "1.0.0"

DEMO_BANNER = "DEMO CERTIFICATE — SIMULATED DATA ONLY"
DEMO_DISCLAIMER = (
    "This document is generated for educational purposes and is not a valid "
    "calibration certificate."
)
TOLERANCE_NOTE = (
    "The default tolerance (±4 %) is an educational assumption and is not a "
    "requirement that applies to every torque wrench."
)
METHOD_NOTE = (
    "Simplified educational sequence with reference to ISO 6789-2. "
    "This simulation does not claim to fulfil all requirements of ISO 6789-2."
)


def _from_dict(cls, data: Optional[Dict[str, Any]]):
    """Build a dataclass from a dict, ignoring unknown keys (forward compatible)."""
    if not data:
        return cls()
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in names})


@dataclass
class EquipmentInfo:
    equipment: str = "Torque Wrench"
    manufacturer: str = "DEMO TOOLS"
    model: str = "TW-100"
    serial_number: str = "TW2026-001"
    capacity: float = 100.0          # N·m
    range_min: float = 20.0          # N·m
    range_max: float = 100.0         # N·m
    direction: str = "Clockwise (CW)"
    customer: str = "UNIVERSITY PROJECT"
    location: str = "Simulation Laboratory"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return _from_dict(cls, data)

    @property
    def range_text(self) -> str:
        return f"{self.range_min:g} ~ {self.range_max:g} N·m"


DECISION_SIMPLE = "simple"
DECISION_GUARD = "guard"
DECISION_RULE_TEXT = {
    DECISION_SIMPLE: (
        "Simple acceptance (단순 상대오차 판정): "
        "PASS if |relative error| ≤ tolerance. Uncertainty is reported but not "
        "taken into account."
    ),
    DECISION_GUARD: (
        "Guarded acceptance (불확도 고려 판정), guard band "
        "w = U: PASS if |error| + U ≤ tolerance; FAIL if |error| − U > "
        "tolerance; otherwise INCONCLUSIVE. Educational rule with reference to the "
        "concept of ILAC-G8:2019."
    ),
}


@dataclass
class CalibrationSettings:
    points: List[float] = field(default_factory=lambda: [20.0, 40.0, 60.0, 80.0, 100.0])
    n_series: int = 3
    preload_cycles: int = 3
    preload_torque: Optional[float] = None  # None -> equipment capacity
    temperature: float = 23.0     # °C
    humidity: float = 50.0        # %RH
    tolerance_pct: float = 4.0    # ± %, educational default
    decision_rule: str = DECISION_SIMPLE
    coverage_k: float = 2.0
    # Uncertainty inputs (educational assumptions, editable)
    reference_instrument: str = "Simulated Reference Torque Transducer (DEMO-REF-01)"
    ref_expanded_u_pct: float = 0.20   # U of reference standard, % of reading, k=2
    ref_k: float = 2.0
    resolution: float = 0.01           # N·m, indication resolution
    additional_u_pct: float = 0.05     # standard uncertainty, % of reading
    performed_by: str = "Student"
    reviewed_by: str = "Instructor"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        obj = _from_dict(cls, data)
        obj.points = [float(p) for p in obj.points]
        return obj

    def effective_preload_torque(self, capacity: float) -> float:
        return float(self.preload_torque) if self.preload_torque else float(capacity)

    def validate(self) -> List[str]:
        errs = []
        if not self.points:
            errs.append("교정점(Calibration Points)이 비어 있습니다.")
        if any(p <= 0 for p in self.points):
            errs.append("교정점은 0보다 커야 합니다.")
        if len(self.points) > 10:
            errs.append("교정점은 최대 10개까지 지원합니다.")
        if not (2 <= self.n_series <= 5):
            errs.append("시리즈 수(Number of Series)는 2~5 사이여야 합니다.")
        if not (0 <= self.preload_cycles <= 5):
            errs.append("사전부하 횟수(Preloading)는 0~5 사이여야 합니다.")
        if self.tolerance_pct <= 0:
            errs.append("허용오차(Tolerance)는 0보다 커야 합니다.")
        if self.coverage_k <= 0 or self.ref_k <= 0:
            errs.append("포함인자(k)는 0보다 커야 합니다.")
        if self.resolution <= 0:
            errs.append("분해능(Resolution)은 0보다 커야 합니다.")
        if self.decision_rule not in DECISION_RULE_TEXT:
            errs.append("알 수 없는 판정 규칙입니다.")
        return errs


SPEED_NORMAL = "Normal"
SPEED_FAST = "Fast"
SPEED_PRESENTATION = "Presentation"

# Speed presets only change timing. Captured values are drawn from the random
# generator independently of timing, so the preset never changes the results.
SPEED_PRESETS: Dict[str, Dict[str, float]] = {
    SPEED_NORMAL: dict(ramp_speed=20.0, hold_time=1.5, inter_step_delay=0.8, speed_factor=1.0),
    SPEED_FAST: dict(ramp_speed=40.0, hold_time=0.8, inter_step_delay=0.4, speed_factor=2.0),
    SPEED_PRESENTATION: dict(ramp_speed=45.0, hold_time=0.8, inter_step_delay=0.4, speed_factor=1.0),
}


@dataclass
class SimulationSettings:
    preset: str = SPEED_NORMAL
    random_error_pct: float = 0.40     # ± % of target, uniform, per measurement
    systematic_error_pct: float = 0.15  # max |bias| % of target, drawn once per run
    noise_level: float = 0.03          # N·m, std-dev of displayed signal noise
    sampling_interval_ms: int = 50     # sample period of the virtual device
    ramp_speed: float = 20.0           # N·m/s while increasing
    hold_time: float = 1.5             # s, torque held before capture
    inter_step_delay: float = 0.8      # s, zero signal between applications
    speed_factor: float = 1.0          # simulated seconds per real second
    seed: Optional[int] = None         # None -> different values every run

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return _from_dict(cls, data)

    def apply_preset(self, name: str) -> None:
        if name not in SPEED_PRESETS:
            raise ValueError(f"Unknown speed preset: {name}")
        self.preset = name
        for k, v in SPEED_PRESETS[name].items():
            setattr(self, k, v)

    def validate(self) -> List[str]:
        errs = []
        if not (10 <= self.sampling_interval_ms <= 500):
            errs.append("샘플링 간격은 10~500 ms 사이여야 합니다.")
        if self.ramp_speed <= 0:
            errs.append("토크 증가 속도(Ramp Speed)는 0보다 커야 합니다.")
        if self.hold_time < 0.1:
            errs.append("유지 시간(Hold Time)은 0.1 s 이상이어야 합니다.")
        if not (0.1 <= self.speed_factor <= 20):
            errs.append("시뮬레이션 속도 배율은 0.1~20 사이여야 합니다.")
        if self.random_error_pct < 0 or self.systematic_error_pct < 0 or self.noise_level < 0:
            errs.append("오차/노이즈 값은 음수일 수 없습니다.")
        return errs
