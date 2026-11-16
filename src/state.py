"""Small, dependency-free state store for data produced by actual devices.

No fallback measurements are generated. Missing, corrupt or old data is unavailable.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json_atomic(path: Path, payload: dict) -> None:
    """Write a single JSON document atomically, never leave a half-written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix="._state_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(payload, out, indent=2, ensure_ascii=False, allow_nan=False)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def read_json(path: Path) -> dict | None:
    try:
        with open(path, encoding="utf-8") as stream:
            value = json.load(stream)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def is_fresh(payload: dict | None, ttl: float) -> bool:
    if not isinstance(payload, dict):
        return False
    try:
        timestamp = datetime.fromisoformat(str(payload["timestamp"]).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            return False
        age = (datetime.now(timezone.utc) - timestamp.astimezone(timezone.utc)).total_seconds()
        return 0 <= age <= ttl
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def numeric(value: object, low: float, high: float) -> float | None:
    """Keep realistic data ranges; reject bool/NaN/inf/invalid values."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or not low <= value <= high:
        return None
    return float(value)


def sensor_snapshot(path: Path, ttl: float) -> dict:
    result = {
        "temperature": None,
        "humidity": None,
        "gas": None,
        "gas_status": "Unavailable",
        "sensor_timestamp": None,
        "sensor_source": "unavailable",
        "gas_source": "unavailable",
    }
    payload = read_json(path)
    if not is_fresh(payload, ttl):
        return result

    result["sensor_timestamp"] = payload.get("timestamp")
    temp = numeric(payload.get("temperature"), -40, 80)
    humid = numeric(payload.get("humidity"), 0, 100)
    if temp is not None and humid is not None:
        result["temperature"] = round(temp, 1)
        result["humidity"] = round(humid, 1)
        result["sensor_source"] = "DHT22"

    # A GPIO digital comparator produces either a trigger or a non-trigger,
    # never a calibrated concentration in ppm.
    signal = payload.get("gas_triggered")
    if signal is True:
        result.update(gas=1, gas_status="Triggered", gas_source="MQ-2 digital")
    elif signal is False:
        result.update(gas=0, gas_status="No trigger", gas_source="MQ-2 digital")
    elif payload.get("gas_status") == "Unconfigured":
        result["gas_status"] = "Unconfigured"
    return result


def attendance_snapshot(path: Path) -> dict:
    payload = read_json(path)
    if not payload or not isinstance(payload.get("students"), list):
        return {"students": [], "present_count": None, "total_students": None,
                "attendance_percentage": None, "attendance_source": "unavailable", "attendance_timestamp": None}
    students = []
    seen = set()
    for item in payload["students"]:
        if not isinstance(item, dict):
            continue
        student_id = str(item.get("id", "")).strip()
        name = str(item.get("name", "")).strip()
        status = item.get("status")
        if not student_id or not name or status not in ("Present", "Absent") or student_id in seen:
            continue
        seen.add(student_id)
        students.append({"id": student_id, "name": name, "status": status})
    if not students:
        return {"students": [], "present_count": None, "total_students": None,
                "attendance_percentage": None, "attendance_source": "unavailable", "attendance_timestamp": None}
    count = sum(s["status"] == "Present" for s in students)
    return {"students": students, "present_count": count,
            "total_students": len(students),
            "attendance_percentage": round(count * 100 / len(students)),
            "attendance_source": "local enrollment/recognition",
            "attendance_timestamp": payload.get("timestamp")}
