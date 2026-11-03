"""
Excel demo calibration certificate (OpenPyXL).

Sheets
  1 Calibration Certificate  - printable A4 certificate (values linked to "Calculation")
  2 Raw Data                 - all individual measurements
  3 Preloading Data          - preloading cycles (excluded from results)
  4 Calculation              - mean, error, correction, repeatability, uncertainty as
                               Excel formulas referencing "Raw Data"
  5 Graph                    - relative error vs nominal torque with tolerance limits
  6 Measurement Log          - complete event log

The measured values are written once (Raw Data); everything else is computed by
Excel formulas, so the workbook stays consistent with the PDF, which is produced
from the same CertificateData object.
"""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import Reference, ScatterChart, Series
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins

from .config import (DECISION_GUARD, DEMO_BANNER, DEMO_DISCLAIMER, METHOD_NOTE,
                     TOLERANCE_NOTE)
from .report_data import CertificateData
from .uncertainty import assumptions_text

NAVY = "14233C"
NAVY_LIGHT = "E8EDF5"
DEMO_RED = "C62828"
WHITE = "FFFFFF"
THIN = Side(style="thin", color="B8C2D1")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
FONT = "Malgun Gothic"   # falls back to the system font where unavailable

F_TITLE = Font(name=FONT, size=16, bold=True, color=WHITE)
F_SUB = Font(name=FONT, size=11, bold=True, color=WHITE)
F_HEAD = Font(name=FONT, size=10, bold=True, color=WHITE)
F_BOLD = Font(name=FONT, size=10, bold=True)
F_NORM = Font(name=FONT, size=10)
F_SMALL = Font(name=FONT, size=8, color="444444")
F_DEMO = Font(name=FONT, size=11, bold=True, color=WHITE)
F_SECTION = Font(name=FONT, size=11, bold=True, color=NAVY)
FILL_NAVY = PatternFill("solid", fgColor=NAVY)
FILL_LIGHT = PatternFill("solid", fgColor=NAVY_LIGHT)
FILL_RED = PatternFill("solid", fgColor=DEMO_RED)
FILL_INPUT = PatternFill("solid", fgColor="FFF8E1")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)

NUM2 = "0.00"
NUM4 = "0.0000"
PCT2 = '+0.00;-0.00;0.00'

CALC = "Calculation"
RAW = "Raw Data"


def _q(sheet: str) -> str:
    return f"'{sheet}'"


def _hdr(ws, row, col, text, width=None):
    c = ws.cell(row=row, column=col, value=text)
    c.font, c.fill, c.alignment, c.border = F_HEAD, FILL_NAVY, CENTER, BORDER
    if width:
        ws.column_dimensions[get_column_letter(col)].width = width
    return c


def _cell(ws, row, col, value, fmt=None, font=F_NORM, fill=None, align=CENTER, border=True):
    c = ws.cell(row=row, column=col, value=value)
    c.font, c.alignment = font, align
    if fmt:
        c.number_format = fmt
    if fill:
        c.fill = fill
    if border:
        c.border = BORDER
    return c


def _merge(ws, row, c1, c2):
    ws.merge_cells(start_row=row, start_column=c1, end_row=row, end_column=c2)
    for c in range(c1, c2 + 1):
        ws.cell(row=row, column=c).border = BORDER


def _decision_format(ws, rng):
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"PASS"'],
                                                  font=Font(bold=True, color="2E7D32")))
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"FAIL"'],
                                                  font=Font(bold=True, color=DEMO_RED)))
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"INCONCLUSIVE"'],
                                                  font=Font(bold=True, color="B26A00")))


def _banner(ws, row, ncols, text, fill=FILL_RED, font=F_DEMO, height=20):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
    c = ws.cell(row=row, column=1, value=text)
    c.font, c.fill, c.alignment = font, fill, CENTER
    for col in range(2, ncols + 1):
        ws.cell(row=row, column=col).fill = fill
    ws.row_dimensions[row].height = height


class CertificateExcel:
    def __init__(self, data: CertificateData):
        self.d = data
        self.s = data.settings
        self.n = data.settings.n_series
        self.np = len(data.settings.points)

    # Calculation sheet layout
    PARAM_ROW = 5          # first parameter row
    TABLE_HDR = 14         # header row of the calculation table
    @property
    def first_row(self):
        return self.TABLE_HDR + 1

    def calc_cols(self):
        """Column numbers of the Calculation table."""
        n = self.n
        cols = {"nominal": 1}
        for k in range(n):
            cols[f"s{k + 1}"] = 2 + k
        names = ["mean", "error", "rel", "corr", "std", "uA", "uref", "ures", "uadd", "uc",
                 "U", "Urel", "tolabs", "simple", "guard"]
        for i, nm in enumerate(names):
            cols[nm] = 2 + n + i
        return cols

    def ref(self, key, point_index, absolute=True):
        col = get_column_letter(self.calc_cols()[key])
        row = self.first_row + point_index
        return f"{_q(CALC)}!${col}${row}" if absolute else f"{col}{row}"

    # ----------------------------------------------------------------- build
    def build(self, path: Path | str) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        wb = Workbook()
        ws_cert = wb.active
        ws_cert.title = "Calibration Certificate"
        ws_raw = wb.create_sheet(RAW)
        ws_pre = wb.create_sheet("Preloading Data")
        ws_calc = wb.create_sheet(CALC)
        ws_graph = wb.create_sheet("Graph")
        ws_log = wb.create_sheet("Measurement Log")
        self._raw(ws_raw)
        self._preload(ws_pre)
        self._calc(ws_calc)
        self._certificate(ws_cert)
        self._graph(ws_graph)
        self._log(ws_log)
        wb.properties.title = f"{self.d.cert_no} - DEMO Torque Wrench Calibration Certificate"
        wb.properties.subject = DEMO_BANNER
        wb.properties.creator = "Torque Calibration System (Simulation)"
        wb.save(str(path))
        return path

    # ------------------------------------------------------------- raw data
    def raw_cell(self, series, point_index):
        """Address of a measured value in Raw Data (rows ordered series-major)."""
        row = 4 + (series - 1) * self.np + point_index
        return f"{_q(RAW)}!$E${row}"

    def _raw(self, ws):
        _banner(ws, 1, 7, DEMO_BANNER)
        ws.cell(row=2, column=1, value="Raw Data - individual measurements (N·m). "
                                       "Simulated values only.").font = F_SMALL
        heads = [("No.", 7), ("Series", 9), ("Point", 8), ("Nominal (N·m)", 15),
                 ("Measured (N·m)", 16), ("Deviation (N·m)", 16), ("Timestamp", 26)]
        for i, (h, w) in enumerate(heads, start=1):
            _hdr(ws, 3, i, h, w)
        mm = self.d.measurement_map()
        r = 4
        for s in range(1, self.n + 1):
            for i, nominal in enumerate(self.s.points):
                m = mm[(s, i)]
                _cell(ws, r, 1, r - 3)
                _cell(ws, r, 2, s)
                _cell(ws, r, 3, i + 1)
                _cell(ws, r, 4, nominal, NUM2)
                _cell(ws, r, 5, m.value, NUM2, font=F_BOLD)
                _cell(ws, r, 6, f"=E{r}-D{r}", '+0.00;-0.00;0.00')
                _cell(ws, r, 7, m.timestamp)
                r += 1
        ws.freeze_panes = "A4"

    def _preload(self, ws):
        _banner(ws, 1, 5, DEMO_BANNER)
        ws.cell(row=2, column=1, value="Preloading data - recorded separately and NOT used for "
                                       "the mean value or the uncertainty.").font = F_SMALL
        for i, (h, w) in enumerate([("Cycle", 8), ("Target (N·m)", 15), ("Peak (N·m)", 15),
                                    ("Deviation (N·m)", 16), ("Timestamp", 26)], start=1):
            _hdr(ws, 3, i, h, w)
        for k, p in enumerate(self.d.preloads):
            r = 4 + k
            _cell(ws, r, 1, p.cycle)
            _cell(ws, r, 2, p.target, NUM2)
            _cell(ws, r, 3, p.peak, NUM2, font=F_BOLD)
            _cell(ws, r, 4, f"=C{r}-B{r}", '+0.00;-0.00;0.00')
            _cell(ws, r, 5, p.timestamp)

    # ---------------------------------------------------------- calculation
    def _calc(self, ws):
        s, n = self.s, self.n
        cols = self.calc_cols()
        ncols = max(cols.values())
        _banner(ws, 1, ncols, DEMO_BANNER)
        ws.cell(row=2, column=1, value="Calculation - all results are Excel formulas based on "
                                       "'Raw Data'. Yellow cells are editable inputs "
                                       "(educational assumptions).").font = F_SMALL
        ws.cell(row=4, column=1, value="Input parameters").font = F_SECTION
        params = [
            ("Tolerance (± %)", s.tolerance_pct, "Educational assumption"),
            ("Coverage factor k", s.coverage_k, "Expanded uncertainty U = k · uc"),
            ("Reference standard U (%)", s.ref_expanded_u_pct, "of reading"),
            ("Reference standard k", s.ref_k, "from reference certificate"),
            ("Resolution r (N·m)", s.resolution, "rectangular, u = r/(2√3)"),
            ("Additional std. u (%)", s.additional_u_pct, "of reading"),
            ("Number of series n", n, "uA = s/√n"),
        ]
        self.param = {}
        keys = ["tol", "k", "refU", "refk", "res", "add", "n"]
        for i, ((label, val, note), key) in enumerate(zip(params, keys)):
            r = self.PARAM_ROW + i
            _cell(ws, r, 1, label, font=F_BOLD, fill=FILL_LIGHT, align=LEFT)
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
            _cell(ws, r, 3, val, fill=FILL_INPUT)
            ws.cell(row=r, column=4, value=note).font = F_SMALL
            self.param[key] = f"$C${r}"

        heads = {"nominal": "Nominal\n(N·m)", "mean": "Mean\n(N·m)",
                 "error": "Indication Error\n(N·m)", "rel": "Relative Error\n(%)",
                 "corr": "Correction\n(N·m)", "std": "Repeatability s\n(N·m)",
                 "uA": "uA\n(N·m)", "uref": "uref\n(N·m)", "ures": "ures\n(N·m)",
                 "uadd": "uadd\n(N·m)", "uc": "uc\n(N·m)", "U": "U (k)\n(N·m)",
                 "Urel": "U\n(%)", "tolabs": "Tolerance\n(±N·m)",
                 "simple": "Decision\nSimple", "guard": "Decision\nGuarded (w=U)"}
        for k in range(n):
            heads[f"s{k + 1}"] = f"Series {k + 1}\n(N·m)"
        ws.cell(row=self.TABLE_HDR - 1, column=1, value="Results per calibration point").font = F_SECTION
        for key, col in cols.items():
            _hdr(ws, self.TABLE_HDR, col, heads[key], 13)
        ws.row_dimensions[self.TABLE_HDR].height = 34
        P = self.param
        L = lambda key: get_column_letter(cols[key])
        for i, nominal in enumerate(s.points):
            r = self.first_row + i
            _cell(ws, r, cols["nominal"], nominal, NUM2, font=F_BOLD)
            for k in range(n):
                _cell(ws, r, cols[f"s{k + 1}"], f"={self.raw_cell(k + 1, i)}", NUM2)
            rng = f"{L('s1')}{r}:{L(f's{n}')}{r}"
            A = f"{L('nominal')}{r}"
            f = {
                "mean": f"=AVERAGE({rng})",
                "error": f"={L('mean')}{r}-{A}",
                "rel": f"={L('error')}{r}/{A}*100",
                "corr": f"={A}-{L('mean')}{r}",
                "std": f"=_xlfn.STDEV.S({rng})",
                "uA": f"={L('std')}{r}/SQRT({P['n']})",
                "uref": f"={P['refU']}/{P['refk']}/100*{A}",
                "ures": f"={P['res']}/(2*SQRT(3))",
                "uadd": f"={P['add']}/100*{A}",
                "uc": f"=SQRT({L('uA')}{r}^2+{L('uref')}{r}^2+{L('ures')}{r}^2+{L('uadd')}{r}^2)",
                "U": f"={P['k']}*{L('uc')}{r}",
                "Urel": f"={L('U')}{r}/{A}*100",
                "tolabs": f"={P['tol']}/100*{A}",
                "simple": f'=IF(ABS({L("rel")}{r})<={P["tol"]},"PASS","FAIL")',
                "guard": (f'=IF(ABS({L("error")}{r})+{L("U")}{r}<={L("tolabs")}{r},"PASS",'
                          f'IF(ABS({L("error")}{r})-{L("U")}{r}>{L("tolabs")}{r},"FAIL",'
                          f'"INCONCLUSIVE"))'),
            }
            fmts = {"mean": NUM2, "error": '+0.000;-0.000;0.000', "rel": '+0.000;-0.000;0.000',
                    "corr": '+0.000;-0.000;0.000', "std": NUM4, "uA": NUM4, "uref": NUM4,
                    "ures": NUM4, "uadd": NUM4, "uc": NUM4, "U": "0.000", "Urel": "0.000",
                    "tolabs": NUM2}
            for key, formula in f.items():
                font = F_BOLD if key in ("simple", "guard", "U", "rel") else F_NORM
                _cell(ws, r, cols[key], formula, fmts.get(key), font=font)
        last = self.first_row + self.np - 1
        _decision_format(ws, f"{L('simple')}{self.first_row}:{L('guard')}{last}")
        r = last + 2
        rule_col = L("guard") if self.d.result.decision_rule == DECISION_GUARD else L("simple")
        rng = f"{rule_col}{self.first_row}:{rule_col}{last}"
        _cell(ws, r, 1, "Overall conformity", font=F_BOLD, fill=FILL_LIGHT, align=LEFT)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
        _cell(ws, r, 3, f'=IF(COUNTIF({rng},"FAIL")>0,"FAIL",IF(COUNTIF({rng},"INCONCLUSIVE")>0,'
                        f'"INCONCLUSIVE","PASS"))', font=F_BOLD)
        ws.cell(row=r, column=4, value=f"Decision rule applied: "
                                       f"{'Guarded (w = U)' if rule_col == L('guard') else 'Simple'}"
                ).font = F_SMALL
        self.overall_ref = f"{_q(CALC)}!$C${r}"
        r += 2
        ws.cell(row=r, column=1, value="Assumptions").font = F_SECTION
        for i, a in enumerate(assumptions_text(s)):
            ws.cell(row=r + 1 + i, column=1, value=f"• {a}").font = F_SMALL
        ws.column_dimensions["A"].width = 14
        ws.freeze_panes = ws.cell(row=self.first_row, column=2)
        ws.page_setup.orientation = "landscape"
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True

    # ---------------------------------------------------------- certificate
    def _certificate(self, ws):
        d, s, e = self.d, self.s, self.d.equipment
        n = self.n
        ncols = n + 5         # Nominal, S1..Sn, Mean, Error, U, Result
        for c in range(1, ncols + 1):
            ws.column_dimensions[get_column_letter(c)].width = 13.5
        ws.column_dimensions["A"].width = 21
        half = ncols // 2
        ws.column_dimensions[get_column_letter(half + 1)].width = 19
        _banner(ws, 1, ncols, DEMO_BANNER)
        _banner(ws, 2, ncols, "TORQUE WRENCH CALIBRATION CERTIFICATE", FILL_NAVY, F_TITLE, 30)
        _banner(ws, 3, ncols, "교정성적서", FILL_NAVY, F_SUB, 20)
        r = 5

        def kv_row(row, k1, v1, k2=None, v2=None):
            _cell(ws, row, 1, k1, font=F_BOLD, fill=FILL_LIGHT, align=LEFT)
            _cell(ws, row, 2, v1, align=LEFT)
            if k2 is not None:
                _merge(ws, row, 2, half)
                _cell(ws, row, half + 1, k2, font=F_BOLD, fill=FILL_LIGHT, align=LEFT)
                _cell(ws, row, half + 2, v2, align=LEFT)
                _merge(ws, row, half + 2, ncols)
            else:
                _merge(ws, row, 2, ncols)

        def section(row, text):
            c = ws.cell(row=row, column=1, value=text)
            c.font = F_SECTION
            ws.row_dimensions[row].height = 20

        section(r, "1. 기본정보 (General Information)"); r += 1
        for row in [("Certificate No.", d.cert_no, "Calibration Date", d.calibration_date),
                    ("Customer", e.customer, "Issue Date", d.issue_date),
                    ("Equipment", e.equipment, "Manufacturer", e.manufacturer),
                    ("Model", e.model, "Serial Number", e.serial_number),
                    ("Maximum Capacity", f"{e.capacity:g} N·m", "Calibration Range", e.range_text),
                    ("Direction", e.direction, "Location", e.location)]:
            kv_row(r, *row); r += 1
        r += 1
        section(r, "2. 환경조건 (Environmental Conditions)"); r += 1
        kv_row(r, "Temperature", f"{s.temperature:.1f} °C", "Relative Humidity",
               f"{s.humidity:.0f} %RH"); r += 2
        section(r, "3. 교정 방법 (Calibration Method)"); r += 1
        kv_row(r, "Method", "Torque Wrench Calibration Simulation - Educational Reference: "
                            "ISO 6789-2 (reference only)"); r += 1
        kv_row(r, "Note", METHOD_NOTE); ws.row_dimensions[r].height = 34; r += 2

        section(r, "4. 교정 결과 (Calibration Results)"); r += 1
        heads = ["Nominal Torque\n(N·m)"] + [f"Series {k + 1}\n(N·m)" for k in range(n)] + \
                ["Mean\n(N·m)", "Error\n(%)", f"U (k={s.coverage_k:g})\n(N·m)", "Result"]
        for i, h in enumerate(heads, start=1):
            _hdr(ws, r, i, h)
        ws.row_dimensions[r].height = 32
        r += 1
        rule_key = "guard" if d.result.decision_rule == DECISION_GUARD else "simple"
        res_col = get_column_letter(n + 5)
        _decision_format(ws, f"{res_col}{r}:{res_col}{r + self.np - 1}")
        for i in range(self.np):
            vals = ["nominal"] + [f"s{k + 1}" for k in range(n)] + ["mean", "rel", "U", rule_key]
            fm = [NUM2] + [NUM2] * n + [NUM2, '+0.00;-0.00;0.00', NUM2, None]
            for c, (key, f) in enumerate(zip(vals, fm), start=1):
                font = F_BOLD if key in ("nominal", rule_key) else F_NORM
                _cell(ws, r, c, f"={self.ref(key, i)}", f, font=font)
            r += 1
        ws.cell(row=r, column=1, value="Torque unit N·m; values with two decimals; "
                                       "Error (%) = (Mean - Nominal)/Nominal x 100.").font = F_SMALL
        r += 2
        section(r, "5. 추가 결과 (Additional Results)"); r += 1
        last = self.first_row + self.np - 1
        U_col = get_column_letter(self.calc_cols()["U"])
        Urel_col = get_column_letter(self.calc_cols()["Urel"])
        add = [
            ("Calibration Direction", e.direction),
            ("Number of Measurements", f"{d.n_measurements} ({n} series x {self.np} points)"),
            ("Preloading Cycles", f"{len(d.preloads)} x "
                                  f"{s.effective_preload_torque(e.capacity):g} N·m (excluded)"),
            ("Reference Instrument", s.reference_instrument),
            ("Measurement Uncertainty",
             f'="U = "&TEXT(MIN({_q(CALC)}!{Urel_col}{self.first_row}:{Urel_col}{last}),"0.00")&'
             f'" % ~ "&TEXT(MAX({_q(CALC)}!{Urel_col}{self.first_row}:{Urel_col}{last}),"0.00")&'
             f'" % of reading (k = {s.coverage_k:g}); max "&'
             f'TEXT(MAX({_q(CALC)}!{U_col}{self.first_row}:{U_col}{last}),"0.000")&" N·m"'),
            ("Tolerance", f"±{s.tolerance_pct:g} % of nominal (educational assumption)"),
            ("Conformity Assessment", f"={self.overall_ref}"),
            ("Decision Rule", d.result.decision_rule_text),
        ]
        for k, v in add:
            kv_row(r, k, v)
            if k == "Decision Rule":
                ws.row_dimensions[r].height = 46 if d.result.decision_rule == DECISION_GUARD else 34
            if k == "Conformity Assessment":
                color = {"PASS": "2E7D32", "FAIL": DEMO_RED}.get(d.result.overall, "B26A00")
                ws.cell(row=r, column=2).font = Font(name=FONT, size=10, bold=True, color=color)
            r += 1
        r += 1
        section(r, "6. 비고 (Remarks)"); r += 1
        for t in [TOLERANCE_NOTE, "All values are simulated (virtual torque measuring device). "
                                  "Relative error chart: see sheet 'Graph'."]:
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
            c = ws.cell(row=r, column=1, value=t)
            c.font, c.alignment = F_SMALL, LEFT
            ws.row_dimensions[r].height = 24
            r += 1
        r += 1
        section(r, "7. 서명 (Signatures)"); r += 1
        kv_row(r, "Performed by", s.performed_by, "Reviewed by", s.reviewed_by); r += 1
        kv_row(r, "Signature", "", "Signature", ""); ws.row_dimensions[r].height = 36; r += 1
        kv_row(r, "Date", "", "Date", ""); r += 2
        _banner(ws, r, ncols, DEMO_BANNER); r += 1
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
        c = ws.cell(row=r, column=1, value=DEMO_DISCLAIMER)
        c.font, c.alignment = Font(name=FONT, size=9, bold=True, color=DEMO_RED), CENTER

        ws.page_setup.orientation = "portrait"
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_margins = PageMargins(left=0.5, right=0.5, top=0.6, bottom=0.6)
        ws.print_area = f"A1:{get_column_letter(ncols)}{r}"
        ws.oddHeader.center.text = DEMO_BANNER
        ws.oddFooter.center.text = f"{d.cert_no} - Page &P of &N - SIMULATED DATA ONLY"
        ws.sheet_view.showGridLines = False

    # ---------------------------------------------------------------- graph
    def _graph(self, ws):
        _banner(ws, 1, 6, DEMO_BANNER)
        for i, (h, w) in enumerate([("Nominal (N·m)", 15), ("Relative Error (%)", 18),
                                    ("+Tolerance (%)", 15), ("-Tolerance (%)", 15),
                                    ("Rel. Error + U (%)", 18), ("Rel. Error - U (%)", 18)], start=1):
            _hdr(ws, 3, i, h, w)
        for i in range(self.np):
            r = 4 + i
            _cell(ws, r, 1, f"={self.ref('nominal', i)}", NUM2)
            _cell(ws, r, 2, f"={self.ref('rel', i)}", "0.000")
            _cell(ws, r, 3, f"={_q(CALC)}!{self.param['tol']}", "0.00")
            _cell(ws, r, 4, f"=-{_q(CALC)}!{self.param['tol']}", "0.00")
            _cell(ws, r, 5, f"=B{r}+{self.ref('Urel', i)}", "0.000")
            _cell(ws, r, 6, f"=B{r}-{self.ref('Urel', i)}", "0.000")
        last = 3 + self.np
        ch = ScatterChart()
        ch.title = "Relative Error vs Nominal Torque (SIMULATED DATA)"
        ch.style = 13
        ch.x_axis.title = "Nominal Torque (N·m)"
        ch.y_axis.title = "Relative Error (%)"
        ch.x_axis.scaling.min = 0
        ch.x_axis.scaling.max = float(max(max(self.s.points), self.d.equipment.capacity) * 1.1)
        lim = self.s.tolerance_pct * 1.5
        ch.y_axis.scaling.min = -lim
        ch.y_axis.scaling.max = lim
        ch.x_axis.delete = False
        ch.y_axis.delete = False
        ch.x_axis.tickLblPos = "low"          # labels at the bottom, zero line kept
        ch.y_axis.number_format = "0.0"
        ch.x_axis.number_format = "0"
        ch.x_axis.majorUnit = float(self.s.points[1] - self.s.points[0]) if self.np > 1 else 10.0
        ch.height, ch.width = 10, 20
        xref = Reference(ws, min_col=1, min_row=4, max_row=last)
        spec = [(2, "Relative Error (%)", "14233C", None, True),
                (3, "+Tolerance", "C62828", "dash", False),
                (4, "-Tolerance", "C62828", "dash", False),
                (5, "Rel. Error + U", "1F6FEB", "sysDot", True),
                (6, "Rel. Error - U", "1F6FEB", "sysDot", True)]
        for col, title, color, dash, marker in spec:
            yref = Reference(ws, min_col=col, min_row=3, max_row=last)
            ser = Series(yref, xref, title_from_data=True)
            ser.graphicalProperties.line.solidFill = color
            ser.graphicalProperties.line.width = 22000 if col == 2 else 15000
            if dash:
                ser.graphicalProperties.line.dashStyle = dash
            if marker:
                ser.marker.symbol = "circle"
                ser.marker.size = 7 if col == 2 else 4
                ser.marker.graphicalProperties.solidFill = color
                ser.marker.graphicalProperties.line.solidFill = color
            else:
                ser.marker.symbol = "none"
            ser.smooth = False
            ch.series.append(ser)
        ch.legend.position = "b"
        ws.cell(row=last + 2, column=1, value="Dashed red lines: tolerance limits (educational "
                                              "assumption). Dotted blue: ±U band.").font = F_SMALL
        ws.add_chart(ch, f"A{last + 4}")
        ws.page_setup.orientation = "landscape"
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 1
        ws.sheet_properties.pageSetUpPr.fitToPage = True

    # ------------------------------------------------------------------ log
    def _log(self, ws):
        _banner(ws, 1, 4, DEMO_BANNER)
        for i, (h, w) in enumerate([("No.", 7), ("Timestamp", 26), ("Phase", 12),
                                    ("Message", 90)], start=1):
            _hdr(ws, 3, i, h, w)
        events = self.d.events or [{"timestamp": "", "phase": "-", "message": "No events recorded."}]
        for k, ev in enumerate(events):
            r = 4 + k
            _cell(ws, r, 1, k + 1)
            _cell(ws, r, 2, ev.get("timestamp", ""))
            _cell(ws, r, 3, ev.get("phase", ""))
            _cell(ws, r, 4, ev.get("message", ""), align=LEFT)
        ws.freeze_panes = "A4"
        ws.auto_filter.ref = f"A3:D{3 + len(events)}"


def generate_excel(data: CertificateData, path: Path | str) -> Path:
    return CertificateExcel(data).build(path)
