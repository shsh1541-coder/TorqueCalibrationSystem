import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _isolated_output(tmp_path, monkeypatch):
    monkeypatch.setenv("TORQUECAL_HOME", str(tmp_path / "home"))
    yield


@pytest.fixture
def completed_engine():
    from src.config import CalibrationSettings, EquipmentInfo, SimulationSettings
    from src.data_source import SimulatedTorqueSource
    from src.simulator import CalibrationEngine
    sim = SimulationSettings(seed=2026)
    eng = CalibrationEngine(SimulatedTorqueSource(sim), EquipmentInfo(), CalibrationSettings(), sim)
    eng.start()
    eng.run_to_completion()
    return eng
