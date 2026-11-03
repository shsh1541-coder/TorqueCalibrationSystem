"""Certificate preview window (Qt PDF module, with system viewer fallback)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton, QTextBrowser,
                               QVBoxLayout)

try:  # QtPdf ships with the PySide6 wheels for macOS and Windows
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtPdfWidgets import QPdfView
    HAS_QTPDF = True
except Exception:  # pragma: no cover - depends on the Qt build
    HAS_QTPDF = False


class CertificatePreview(QDialog):
    def __init__(self, pdf_path: Path, summary_html: str = "", parent=None,
                 on_export_pdf=None, on_export_excel=None):
        super().__init__(parent)
        self.pdf_path = Path(pdf_path)
        self.setWindowTitle(f"Certificate Preview  성적서 미리보기 - {self.pdf_path.name}")
        self.resize(900, 1000)
        lay = QVBoxLayout(self)
        banner = QLabel("DEMO CERTIFICATE — SIMULATED DATA ONLY")
        banner.setStyleSheet("background:#c62828; color:white; font-weight:700; padding:6px;"
                             "letter-spacing:1px;")
        lay.addWidget(banner)
        if HAS_QTPDF:
            self.doc = QPdfDocument(self)
            self.doc.load(str(self.pdf_path))
            self.view = QPdfView(self)
            self.view.setPageMode(QPdfView.PageMode.MultiPage)
            self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            self.view.setDocument(self.doc)
            lay.addWidget(self.view, 1)
        else:
            tb = QTextBrowser()
            tb.setHtml(summary_html or "<p>Qt PDF module not available - use "
                                       "'Open in system viewer'.</p>")
            lay.addWidget(tb, 1)
        row = QHBoxLayout()
        b_ext = QPushButton("외부 뷰어로 열기 (Open in system viewer)")
        b_ext.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.pdf_path))))
        row.addWidget(b_ext)
        if on_export_pdf:
            b = QPushButton("EXPORT PDF")
            b.clicked.connect(on_export_pdf)
            row.addWidget(b)
        if on_export_excel:
            b = QPushButton("EXPORT EXCEL")
            b.clicked.connect(on_export_excel)
            row.addWidget(b)
        row.addStretch(1)
        close = QPushButton("닫기 (Close)")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        lay.addLayout(row)
        row_info = QLabel(str(self.pdf_path))
        row_info.setStyleSheet("color:#8ea0bd;")
        lay.addWidget(row_info)
