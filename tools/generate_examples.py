"""Generate the example PDF / Excel certificates in output/certificates (no GUI needed).

    python tools/generate_examples.py [--seed 2026]
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import paths                                         # noqa: E402
from src.certificate_excel import generate_excel              # noqa: E402
from src.certificate_pdf import generate_pdf                  # noqa: E402
from src.config import CalibrationSettings, EquipmentInfo, SimulationSettings  # noqa: E402
from src.data_source import SimulatedTorqueSource             # noqa: E402
from src.database import STATUS_COMPLETED, Database, DatabaseRecorder  # noqa: E402
from src.report_data import build_from_db                     # noqa: E402
from src.simulator import CalibrationEngine                   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--db", default=None, help="database file (default: output/data/examples.db)")
    a = ap.parse_args()
    db = Database(a.db or paths.data_dir() / "examples.db")
    sim = SimulationSettings(seed=a.seed)
    eq, cs = EquipmentInfo(), CalibrationSettings()
    eng = CalibrationEngine(SimulatedTorqueSource(sim, cs.resolution), eq, cs, sim)
    cal = db.create_calibration(eq, cs, sim)
    eng.add_listener(DatabaseRecorder(db, cal))
    eng.start()
    eng.run_to_completion()
    from src.calibration import calculate
    res = calculate(eng.measurements, cs)
    db.save_results(cal, res.to_dict(), res.overall)
    db.set_status(cal, STATUS_COMPLETED)
    data = build_from_db(db, cal)
    out = paths.certificates_dir()
    pdf = generate_pdf(data, out / f"EXAMPLE_{data.cert_no}.pdf")
    xls = generate_excel(data, out / f"EXAMPLE_{data.cert_no}.xlsx")
    print(f"Overall: {res.overall}")
    for p in res.points:
        print(f"  {p.nominal:6.1f}  mean {p.mean:8.3f}  err {p.rel_error_pct:+.3f} %  "
              f"U {p.U:.3f} N·m  {p.decision_simple}")
    print(pdf)
    print(xls)


if __name__ == "__main__":
    main()
