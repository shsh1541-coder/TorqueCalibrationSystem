"""
Torque Wrench Automatic Calibration & Certificate Generation System
(Simulation Mode - educational graduate-school project)

Run:  python main.py
"""
from __future__ import annotations

import sys
import traceback

from src.config import APP_NAME, APP_VERSION


def _cli() -> bool:
    if "--version" in sys.argv:
        print(f"{APP_NAME} {APP_VERSION}")
        return True
    return False


def main() -> int:
    if _cli():
        return 0
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMessageBox

    from gui import theme
    from gui.main_window import MainWindow
    from src import paths
    from src.database import Database

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("University Project")
    icon = paths.resource_path("icons", "app.png")
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    theme.load_app_fonts()
    app.setFont(theme.ui_font(13))
    app.setStyleSheet(theme.stylesheet())

    def excepthook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            log = paths.data_dir() / "error.log"
            with open(log, "a", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except OSError:
            pass
        QMessageBox.critical(None, "Unexpected error 오류",
                             f"{exc_type.__name__}: {exc}\n\nDetails were written to error.log.")

    sys.excepthook = excepthook

    try:
        db = Database(paths.database_path())
    except Exception as exc:
        QMessageBox.critical(None, "Database error", f"Cannot open database:\n{exc}")
        return 1
    win = MainWindow(db)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
