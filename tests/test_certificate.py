"""Certificate tests: PDF and Excel generation and consistency with the measurements."""
import shutil
import subprocess

import pytest
from openpyxl import load_workbook

from src.certificate_excel import generate_excel
from src.certificate_pdf import generate_pdf
from src.config import DEMO_BANNER
from src.report_data import build_from_db, build_from_engine


@pytest.fixture
def cert_data(completed_engine):
    return build_from_engine(completed_engine, "DEMO-2026-0001", 1,
                             [{"timestamp": "2026-01-01T00:00:00", "phase": "SYSTEM", "message": "x"}])


def test_pdf_generated(tmp_path, cert_data):
    path = generate_pdf(cert_data, tmp_path / "c.pdf")
    raw = path.read_bytes()
    assert raw.startswith(b"%PDF") and len(raw) > 10_000


def test_pdf_contains_demo_statements_and_values(tmp_path, cert_data):
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext not installed")
    path = generate_pdf(cert_data, tmp_path / "c.pdf")
    txt = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True,
                         text=True).stdout
    assert txt.count("DEMO CERTIFICATE") >= 4                # top + bottom of both pages
    assert "not a valid calibration certificate" in txt
    assert "DEMO-2026-0001" in txt
    for m in cert_data.measurements:
        assert f"{m.value:.2f}" in txt
    for p in cert_data.result.points:
        assert f"{p.rel_error_pct:+.2f}" in txt


def test_excel_sheets_and_raw_data(tmp_path, cert_data):
    path = generate_excel(cert_data, tmp_path / "c.xlsx")
    wb = load_workbook(path)
    assert wb.sheetnames == ["Calibration Certificate", "Raw Data", "Preloading Data",
                             "Calculation", "Graph", "Measurement Log"]
    raw = wb["Raw Data"]
    values = [raw.cell(r, 5).value for r in range(4, 19)]
    assert values == [m.value for m in cert_data.measurements]
    assert raw["A1"].value == DEMO_BANNER
    calc = wb["Calculation"]
    assert str(calc["E15"].value).startswith("=AVERAGE(")
    assert "STDEV.S" in str(calc["I15"].value)
    assert len(wb["Graph"]._charts) == 1
    assert wb["Preloading Data"].max_row == 3 + 3


def test_excel_formulas_match_python(tmp_path, cert_data):
    """Recalculate with LibreOffice (if available) and compare with the PDF values."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        pytest.skip("LibreOffice not installed - formula recalculation not verified")
    src = generate_excel(cert_data, tmp_path / "c.xlsx")
    out = tmp_path / "lo"
    out.mkdir()
    subprocess.run([soffice, "--headless", "--convert-to", "xlsx", "--outdir", str(out), str(src)],
                   capture_output=True, timeout=180)
    wb = load_workbook(out / "c.xlsx", data_only=True)
    calc = wb["Calculation"]
    for i, p in enumerate(cert_data.result.points):
        r = 15 + i
        assert calc.cell(r, 5).value == pytest.approx(p.mean, abs=1e-9)
        assert calc.cell(r, 7).value == pytest.approx(p.rel_error_pct, abs=1e-9)
        assert calc.cell(r, 8).value == pytest.approx(p.correction, abs=1e-9)
        assert calc.cell(r, 9).value == pytest.approx(p.std_dev, abs=1e-9)
        assert calc.cell(r, 15).value == pytest.approx(p.U, abs=1e-9)
        assert calc.cell(r, 18).value == p.decision_simple
        assert calc.cell(r, 19).value == p.decision_guard


def test_regenerate_from_database(tmp_path, completed_engine):
    from src.database import STATUS_COMPLETED, Database
    db = Database(tmp_path / "t.db")
    e = completed_engine
    cal = db.create_calibration(e.equipment, e.settings, e.sim)
    for p in e.preloads.values():
        db.add_preload(cal, p)
    for m in e.measurements.values():
        db.add_measurement(cal, m)
    db.set_status(cal, STATUS_COMPLETED)
    d1 = build_from_db(db, cal)
    d2 = build_from_db(db, cal)
    assert d1.cert_no == d2.cert_no == f"DEMO-{d1.cert_no[5:9]}-0001"
    assert [p.mean for p in d1.result.points] == [p.mean for p in d2.result.points]
    generate_pdf(d1, tmp_path / "a.pdf")
    generate_excel(d1, tmp_path / "a.xlsx")
    assert (tmp_path / "a.pdf").exists() and (tmp_path / "a.xlsx").exists()
