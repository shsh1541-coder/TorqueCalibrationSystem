"""
OS-independent path handling.

* Resources (styles, icons, fonts) are read from the PyInstaller bundle when the
  program is frozen, otherwise from the project folder.
* Output (database, certificates) is written to the project ``output`` folder in
  development, and to ``~/Documents/TorqueCalibration`` in the packaged app,
  because the inside of a .app bundle / Program Files is not writable.
* The environment variable ``TORQUECAL_HOME`` overrides the output location
  (used by the tests).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_path(*parts: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
    return base.joinpath("resources", *parts)


def _documents_dir() -> Path:
    home = Path.home()
    if sys.platform.startswith("win"):
        # Respect a redirected (e.g. OneDrive) Documents folder when present.
        for env in ("OneDrive", "USERPROFILE"):
            root = os.environ.get(env)
            if root and (Path(root) / "Documents").is_dir():
                return Path(root) / "Documents"
    docs = home / "Documents"
    return docs if docs.is_dir() else home


def output_root() -> Path:
    override = os.environ.get("TORQUECAL_HOME")
    if override:
        root = Path(override)
    elif is_frozen():
        root = _documents_dir() / "TorqueCalibration"
    else:
        root = PROJECT_ROOT / "output"
    return root


def certificates_dir() -> Path:
    d = output_root() / "certificates"
    d.mkdir(parents=True, exist_ok=True)
    return d


def data_dir() -> Path:
    d = output_root() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def database_path() -> Path:
    return data_dir() / "torque_calibration.db"


def safe_filename(name: str) -> str:
    keep = "-_.() "
    cleaned = "".join(c if (c.isalnum() or c in keep) else "_" for c in name)
    return cleaned.strip() or "file"
