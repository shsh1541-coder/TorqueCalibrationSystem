"""
SQLite persistence.

Every captured value is committed immediately (WAL journal), so if the program
or the computer stops in the middle of a run, the next start can recover the
run from the last captured point. UNIQUE constraints make duplicate storage of
a preload cycle or a (series, point) measurement impossible at database level.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import CalibrationSettings, EquipmentInfo, SimulationSettings
from .simulator import EngineListener, Measurement, PreloadRecord, Step

STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_COMPLETED = "COMPLETED"
STATUS_STOPPED = "STOPPED"
STATUS_ABORTED = "ABORTED"

SCHEMA = """
CREATE TABLE IF NOT EXISTS calibrations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    uid             TEXT NOT NULL UNIQUE,
    cert_no         TEXT,
    status          TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    completed_at    TEXT,
    equipment_json  TEXT NOT NULL,
    settings_json   TEXT NOT NULL,
    sim_json        TEXT NOT NULL,
    results_json    TEXT,
    overall         TEXT
);
CREATE TABLE IF NOT EXISTS preloads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    calibration_id  INTEGER NOT NULL REFERENCES calibrations(id) ON DELETE CASCADE,
    cycle           INTEGER NOT NULL,
    target          REAL NOT NULL,
    peak            REAL NOT NULL,
    timestamp       TEXT NOT NULL,
    UNIQUE (calibration_id, cycle)
);
CREATE TABLE IF NOT EXISTS measurements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    calibration_id  INTEGER NOT NULL REFERENCES calibrations(id) ON DELETE CASCADE,
    series          INTEGER NOT NULL,
    point_index     INTEGER NOT NULL,
    target          REAL NOT NULL,
    value           REAL NOT NULL,
    timestamp       TEXT NOT NULL,
    UNIQUE (calibration_id, series, point_index)
);
CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    calibration_id  INTEGER REFERENCES calibrations(id) ON DELETE CASCADE,
    timestamp       TEXT NOT NULL,
    phase           TEXT NOT NULL,
    message         TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS certificates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    calibration_id  INTEGER NOT NULL REFERENCES calibrations(id) ON DELETE CASCADE,
    cert_no         TEXT NOT NULL,
    file_type       TEXT NOT NULL,
    path            TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS app_settings (
    key             TEXT PRIMARY KEY,
    value_json      TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class CalibrationRecord:
    id: int
    uid: str
    cert_no: Optional[str]
    status: str
    created_at: str
    completed_at: Optional[str]
    equipment: EquipmentInfo
    settings: CalibrationSettings
    sim: SimulationSettings
    results: Optional[Dict[str, Any]]
    overall: Optional[str]


class Database:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        try:
            self.conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.DatabaseError:
            pass
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        try:
            self.conn.commit()
            self.conn.close()
        except sqlite3.Error:
            pass

    # ---------------------------------------------------------- calibrations
    def create_calibration(self, equipment: EquipmentInfo, settings: CalibrationSettings,
                           sim: SimulationSettings) -> int:
        cur = self.conn.execute(
            "INSERT INTO calibrations (uid, status, created_at, equipment_json, settings_json, sim_json)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, STATUS_IN_PROGRESS, _now(), json.dumps(equipment.to_dict()),
             json.dumps(settings.to_dict()), json.dumps(sim.to_dict())))
        self.conn.commit()
        return int(cur.lastrowid)

    def set_status(self, cal_id: int, status: str) -> None:
        completed = _now() if status == STATUS_COMPLETED else None
        self.conn.execute("UPDATE calibrations SET status = ?, completed_at = COALESCE(?, completed_at)"
                          " WHERE id = ?", (status, completed, cal_id))
        self.conn.commit()

    def save_results(self, cal_id: int, results: Dict[str, Any], overall: str) -> None:
        self.conn.execute("UPDATE calibrations SET results_json = ?, overall = ? WHERE id = ?",
                          (json.dumps(results), overall, cal_id))
        self.conn.commit()

    def assign_cert_no(self, cal_id: int, year: Optional[int] = None) -> str:
        row = self.conn.execute("SELECT cert_no FROM calibrations WHERE id = ?", (cal_id,)).fetchone()
        if row and row["cert_no"]:
            return row["cert_no"]
        year = year or datetime.now().year
        prefix = f"DEMO-{year}-"
        n = self.conn.execute("SELECT COUNT(*) FROM calibrations WHERE cert_no LIKE ?",
                              (prefix + "%",)).fetchone()[0]
        cert_no = f"{prefix}{n + 1:04d}"
        self.conn.execute("UPDATE calibrations SET cert_no = ? WHERE id = ?", (cert_no, cal_id))
        self.conn.commit()
        return cert_no

    def get_calibration(self, cal_id: int) -> Optional[CalibrationRecord]:
        row = self.conn.execute("SELECT * FROM calibrations WHERE id = ?", (cal_id,)).fetchone()
        return self._record(row) if row else None

    def list_calibrations(self, limit: int = 500) -> List[CalibrationRecord]:
        rows = self.conn.execute("SELECT * FROM calibrations ORDER BY id DESC LIMIT ?",
                                 (limit,)).fetchall()
        return [self._record(r) for r in rows]

    def find_unfinished(self) -> Optional[CalibrationRecord]:
        row = self.conn.execute("SELECT * FROM calibrations WHERE status = ? ORDER BY id DESC LIMIT 1",
                                (STATUS_IN_PROGRESS,)).fetchone()
        return self._record(row) if row else None

    def delete_calibration(self, cal_id: int) -> None:
        self.conn.execute("DELETE FROM calibrations WHERE id = ?", (cal_id,))
        self.conn.commit()

    @staticmethod
    def _record(row) -> CalibrationRecord:
        return CalibrationRecord(
            id=row["id"], uid=row["uid"], cert_no=row["cert_no"], status=row["status"],
            created_at=row["created_at"], completed_at=row["completed_at"],
            equipment=EquipmentInfo.from_dict(json.loads(row["equipment_json"])),
            settings=CalibrationSettings.from_dict(json.loads(row["settings_json"])),
            sim=SimulationSettings.from_dict(json.loads(row["sim_json"])),
            results=json.loads(row["results_json"]) if row["results_json"] else None,
            overall=row["overall"])

    # ---------------------------------------------------------- data points
    def add_preload(self, cal_id: int, rec: PreloadRecord) -> bool:
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO preloads (calibration_id, cycle, target, peak, timestamp)"
            " VALUES (?, ?, ?, ?, ?)", (cal_id, rec.cycle, rec.target, rec.peak, rec.timestamp))
        self.conn.commit()
        return cur.rowcount == 1

    def add_measurement(self, cal_id: int, m: Measurement) -> bool:
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO measurements (calibration_id, series, point_index, target, value,"
            " timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (cal_id, m.series, m.point_index, m.target, m.value, m.timestamp))
        self.conn.commit()
        return cur.rowcount == 1

    def get_preloads(self, cal_id: int) -> List[PreloadRecord]:
        rows = self.conn.execute("SELECT * FROM preloads WHERE calibration_id = ? ORDER BY cycle",
                                 (cal_id,)).fetchall()
        return [PreloadRecord(r["cycle"], r["target"], r["peak"], r["timestamp"]) for r in rows]

    def get_measurements(self, cal_id: int) -> List[Measurement]:
        rows = self.conn.execute(
            "SELECT * FROM measurements WHERE calibration_id = ? ORDER BY series, point_index",
            (cal_id,)).fetchall()
        return [Measurement(r["series"], r["point_index"], r["target"], r["value"], r["timestamp"])
                for r in rows]

    def count_measurements(self, cal_id: int) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM measurements WHERE calibration_id = ?",
                                 (cal_id,)).fetchone()[0]

    def add_event(self, cal_id: Optional[int], phase: str, message: str,
                  timestamp: Optional[str] = None) -> None:
        self.conn.execute("INSERT INTO events (calibration_id, timestamp, phase, message)"
                          " VALUES (?, ?, ?, ?)",
                          (cal_id, timestamp or datetime.now().isoformat(timespec="milliseconds"),
                           phase, message))
        self.conn.commit()

    def get_events(self, cal_id: int) -> List[Dict[str, str]]:
        rows = self.conn.execute("SELECT timestamp, phase, message FROM events"
                                 " WHERE calibration_id = ? ORDER BY id", (cal_id,)).fetchall()
        return [dict(r) for r in rows]

    def add_certificate(self, cal_id: int, cert_no: str, file_type: str, path: str) -> None:
        self.conn.execute("INSERT INTO certificates (calibration_id, cert_no, file_type, path,"
                          " created_at) VALUES (?, ?, ?, ?, ?)",
                          (cal_id, cert_no, file_type, path, _now()))
        self.conn.commit()

    def get_certificates(self, cal_id: int) -> List[Dict[str, str]]:
        rows = self.conn.execute("SELECT * FROM certificates WHERE calibration_id = ? ORDER BY id",
                                 (cal_id,)).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------- settings
    def save_app_setting(self, key: str, value: Any) -> None:
        self.conn.execute("INSERT INTO app_settings (key, value_json) VALUES (?, ?)"
                          " ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json",
                          (key, json.dumps(value)))
        self.conn.commit()

    def load_app_setting(self, key: str, default: Any = None) -> Any:
        row = self.conn.execute("SELECT value_json FROM app_settings WHERE key = ?", (key,)).fetchone()
        return json.loads(row["value_json"]) if row else default


class DatabaseRecorder(EngineListener):
    """Engine listener that persists every capture and event immediately."""

    def __init__(self, db: Database, cal_id: int):
        self.db = db
        self.cal_id = cal_id

    def on_preload_captured(self, record: PreloadRecord) -> None:
        self.db.add_preload(self.cal_id, record)

    def on_measurement_captured(self, step: Step, m: Measurement) -> None:
        self.db.add_measurement(self.cal_id, m)

    def on_log(self, phase: str, message: str) -> None:
        self.db.add_event(self.cal_id, phase, message)
