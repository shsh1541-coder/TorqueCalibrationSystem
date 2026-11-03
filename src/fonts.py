"""
Korean font registration for ReportLab.

ReportLab can embed TrueType fonts only. We look for a Korean TrueType font in
this order and embed the first one found:

  1. resources/fonts/*.ttf / *.ttc   (e.g. drop NanumGothic.ttf here)
  2. Windows:  Malgun Gothic (malgun.ttf / malgunbd.ttf)
  3. macOS:    AppleGothic.ttf, NanumGothic, AppleSDGothicNeo.ttc
  4. Linux:    NanumGothic

If none can be loaded, ReportLab's built-in CID font ``HYGothic-Medium`` is used
(not embedded; macOS Preview, Chrome and Edge display it, Adobe Reader may ask
for the Asian font pack).
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from reportlab.pdfbase import pdfmetrics

from .paths import resource_path

_registered: Optional[Tuple[str, str, bool]] = None


def _candidates() -> List[Tuple[Path, Optional[Path]]]:
    c: List[Tuple[Path, Optional[Path]]] = []
    fdir = resource_path("fonts")
    if fdir.is_dir():
        files = sorted(list(fdir.glob("*.ttf")) + list(fdir.glob("*.ttc")))
        regular = [f for f in files if "bold" not in f.name.lower()]
        bold = [f for f in files if "bold" in f.name.lower()]
        if regular:
            c.append((regular[0], bold[0] if bold else None))
    win = Path("C:/Windows/Fonts")
    c.append((win / "malgun.ttf", win / "malgunbd.ttf"))
    c.append((Path("/Library/Fonts/NanumGothic.ttf"), Path("/Library/Fonts/NanumGothicBold.ttf")))
    c.append((Path.home() / "Library/Fonts/NanumGothic.ttf",
              Path.home() / "Library/Fonts/NanumGothicBold.ttf"))
    c.append((Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf"), None))
    c.append((Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"), None))
    c.append((Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
              Path("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf")))
    return c


def _try_ttf(name: str, path: Path) -> bool:
    from reportlab.pdfbase.ttfonts import TTFont
    if not path or not path.exists():
        return False
    try:
        if path.suffix.lower() == ".ttc":
            pdfmetrics.registerFont(TTFont(name, str(path), subfontIndex=0))
        else:
            pdfmetrics.registerFont(TTFont(name, str(path)))
        return True
    except Exception:
        return False


def register_fonts() -> Tuple[str, str, bool]:
    """Return (regular_font, bold_font, embedded)."""
    global _registered
    if _registered:
        return _registered
    for regular, bold in _candidates():
        if _try_ttf("KR-Regular", regular):
            bold_name = "KR-Bold" if (bold and _try_ttf("KR-Bold", bold)) else "KR-Regular"
            _registered = ("KR-Regular", bold_name, True)
            return _registered
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    pdfmetrics.registerFont(UnicodeCIDFont("HYGothic-Medium"))
    _registered = ("HYGothic-Medium", "HYGothic-Medium", False)
    return _registered
