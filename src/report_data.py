"""
Single data bundle used by both the PDF and the Excel certificate, so the two
documents are always generated from exactly the same measurement data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

from .calibration import CalibrationResult, calculate
from .config import CalibrationSettings, EquipmentInfo, SimulationSettings
from .simulator import Measurement, PreloadRecord


@dataclass
class CertificateData:
    cert_no: str
    calibration_id: Optional[int]
    calibration_date: str
    equipment: EquipmentInfo
    settings: CalibrationSettings
    sim: SimulationSettings
    measurements: List[Measurement]
    preloads: List[PreloadRecord]
    events: List[Dict[str, str]] = field(default_factory=list)
    result: Optional[CalibrationResult] = None
    issue_date: str = field(default_factory=lambda: date.today().isoformat())

    def __post_init__(self):
        if self.result is None:
            self.result = calculate(self.measurement_map(), self.settings)

    def measurement_map(self):
        return {(m.series, m.point_index): m for m in self.measurements}

    def value(self, series: int, point_index: int) -> float:
        return self.measurement_map()[(series, point_index)].value

    @property
    def n_measurements(self) -> int:
        return len(self.measurements)


def build_from_engine(engine, cert_no: str, calibration_id: Optional[int],
                      events: Optional[List[Dict[str, str]]] = None) -> CertificateData:
    meas = sorted(engine.measurements.values(), key=lambda m: (m.series, m.point_index))
    pre = sorted(engine.preloads.values(), key=lambda p: p.cycle)
    cal_date = meas[-1].timestamp[:10] if meas else date.today().isoformat()
    return CertificateData(cert_no, calibration_id, cal_date, engine.equipment, engine.settings,
                           engine.sim, meas, pre, events or [])


def build_from_db(db, cal_id: int) -> CertificateData:
    rec = db.get_calibration(cal_id)
    if rec is None:
        raise ValueError(f"Calibration record {cal_id} not found.")
    meas = db.get_measurements(cal_id)
    cert_no = rec.cert_no or db.assign_cert_no(cal_id)
    cal_date = (rec.completed_at or rec.created_at)[:10]
    return CertificateData(cert_no, cal_id, cal_date, rec.equipment, rec.settings, rec.sim,
                           meas, db.get_preloads(cal_id), db.get_events(cal_id))
