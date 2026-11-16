"""Offline state contract tests; do not require a Raspberry Pi."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.state import (
    read_json, write_json_atomic, sensor_snapshot, attendance_snapshot,
    utc_now, is_fresh, numeric,
)

class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "latest.json"

    def tearDown(self):
        self.temp.cleanup()

    def test_missing_hardware_never_generates_a_number(self):
        state = sensor_snapshot(self.path, 30)
        self.assertIsNone(state["temperature"])
        self.assertIsNone(state["humidity"])
        self.assertIsNone(state["gas"])
        self.assertEqual(state["gas_status"], "Unavailable")

    def test_live_real_measurements(self):
        write_json_atomic(self.path, {
            "timestamp": utc_now(), "temperature": 24.1, "humidity": 42.3,
            "gas_triggered": False,
        })
        state = sensor_snapshot(self.path, 30)
        self.assertEqual(state["temperature"], 24.1)
        self.assertEqual(state["humidity"], 42.3)
        self.assertEqual(state["gas_status"], "No trigger")
        self.assertEqual(state["gas_source"], "MQ-2 digital")

    def test_triggered_digital_is_not_ppm(self):
        write_json_atomic(self.path, {
            "timestamp": utc_now(), "temperature": None, "humidity": None,
            "gas_triggered": True,
        })
        state = sensor_snapshot(self.path, 30)
        self.assertEqual(state["gas_status"], "Triggered")
        self.assertIsNone(state["temperature"])

    def test_stale_reading_unavailable(self):
        write_json_atomic(self.path, {
            "timestamp": (datetime.now(timezone.utc)-timedelta(days=1)).isoformat(),
            "temperature": 25, "humidity": 50, "gas_triggered": True,
        })
        state = sensor_snapshot(self.path, 30)
        self.assertIsNone(state["temperature"])
        self.assertIsNone(state["gas"])

    def test_bad_inputs_not_accepted(self):
        self.assertIsNone(numeric(float("nan"), -40, 80))
        self.assertIsNone(numeric(True, -40, 80))
        self.assertIsNone(numeric(999, -40, 80))
        self.assertFalse(is_fresh({"timestamp":"not-a-time"},30))

    def test_attendance_unavailable_with_no_private_file(self):
        state = attendance_snapshot(self.path)
        self.assertEqual(state["students"], [])
        self.assertIsNone(state["attendance_percentage"])

    def test_attendance_from_private_file_only(self):
        write_json_atomic(self.path, {
            "timestamp": utc_now(),
            "students": [
                {"id":"private-1","name":"Person A","status":"Present"},
                {"id":"private-2","name":"Person B","status":"Absent"},
            ]
        })
        state = attendance_snapshot(self.path)
        self.assertEqual(state["attendance_percentage"], 50)
        self.assertEqual(state["present_count"], 1)
        self.assertEqual(state["total_students"], 2)

    def test_unsupported_attendance_filtered(self):
        write_json_atomic(self.path, {
            "students":[{"id":"a","name":"Person A","status":"Maybe"}]
        })
        self.assertIsNone(attendance_snapshot(self.path)["attendance_percentage"])

if __name__ == "__main__":
    unittest.main()
