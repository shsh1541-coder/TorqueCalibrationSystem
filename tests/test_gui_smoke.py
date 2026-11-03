"""GUI smoke test (runs only where PySide6 + pyqtgraph are installed).

    QT_QPA_PLATFORM=offscreen python -m pytest tests/test_gui_smoke.py -s

Builds the main window, runs a full Presentation-mode sequence through the
real QTimer callback, generates the certificate and saves a screenshot to
output/data/gui_smoke.png for visual inspection.
"""
import os

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_main_window_full_run(tmp_path):
    from PySide6.QtWidgets import QApplication, QMessageBox

    from gui import theme
    from gui.main_window import MainWindow
    from src import paths
    from src.database import Database

    app = QApplication.instance() or QApplication([])
    theme.load_app_fonts()
    app.setStyleSheet(theme.stylesheet())
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.Ok)
    db = Database(paths.database_path())
    win = MainWindow(db)
    win.resize(1920, 1080)
    win.show()
    app.processEvents()
    win.b_present.setChecked(True)
    win._on_presentation(True)
    assert win.sim.preset == "Presentation"
    win._on_start()
    assert win.engine.state == "RUNNING"
    win.timer.stop()                      # drive ticks deterministically
    win.elapsed.restart = lambda: 50      # 50 ms per tick
    n = 0
    while win.engine.state == "RUNNING" and n < 5000:
        win._tick()
        if n % 20 == 0:
            app.processEvents()
        if n == 700:
            win.grab().save(str(paths.data_dir() / "gui_smoke_running.png"))
        n += 1
    app.processEvents()
    assert win.engine.state == "COMPLETED"
    assert win.engine.n_measurements_done == 15
    assert win.cert_pdf is not None and win.cert_pdf.exists()
    assert win.b_generate.isEnabled() and win.b_pdf.isEnabled()
    win.grab().save(str(paths.data_dir() / "gui_smoke_completed.png"))
    win.close()
