"""Web dashboard for genuine local sensor and attendance data.

No random data and no default student identities. Keep this service on localhost,
or on a trusted private LAN only; authentication is not implemented.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from flask import Flask, jsonify, send_from_directory
import requests

from src.state import DATA, attendance_snapshot, sensor_snapshot

ROOT = Path(__file__).resolve().parent
app = Flask(__name__)
app.json.ensure_ascii = False
_cached_weather = {"time": 0.0, "payload": None}


def real_weather() -> dict:
    """Fetch optional live weather only; never substitute fabricated values."""
    key = os.getenv("OPENWEATHER_API_KEY", "").strip()
    if not key:
        return {"weather": None, "weather_source": "unavailable"}
    now = time.monotonic()
    if _cached_weather["payload"] is not None and now - _cached_weather["time"] < 600:
        return _cached_weather["payload"]
    try:
        response = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": os.getenv("WEATHER_CITY", "Incheon"), "appid": key, "units": "metric"},
            timeout=4,
        )
        response.raise_for_status()
        data = response.json()
        weather = data.get("weather") or []
        description = str(weather[0]["description"]).capitalize() if weather else None
        result = {"weather": description, "weather_source": "OpenWeather" if description else "unavailable"}
    except (requests.RequestException, ValueError, TypeError, KeyError):
        result = {"weather": None, "weather_source": "unavailable"}
    _cached_weather.update({"time": now, "payload": result})
    return result


@app.get("/")
def index():
    return send_from_directory(ROOT, "index.html")


@app.get("/api/sensor")
def sensor_data():
    ttl = float(os.getenv("SENSOR_STALE_SECONDS", "20"))
    sensors = sensor_snapshot(DATA / "sensor_latest.json", ttl)
    attendance = attendance_snapshot(DATA / "attendance_data.json")
    weather = real_weather()
    return jsonify({
        "temperature": sensors["temperature"],
        "gas": sensors["gas"],
        "gas_status": sensors["gas_status"],
        "weather": weather["weather"],
        "humidity": sensors["humidity"],
        "students": attendance["students"],
        "present_count": attendance["present_count"],
        "total_students": attendance["total_students"],
        "attendance_percentage": attendance["attendance_percentage"],
        "attendance_source": attendance["attendance_source"],
        "data_sources": {
            "temperature": sensors["sensor_source"],
            "humidity": sensors["sensor_source"],
            "gas": sensors["gas_source"],
            "weather": weather["weather_source"],
        },
    })


@app.get("/api/attendance")
def attendance():
    return jsonify(attendance_snapshot(DATA / "attendance_data.json"))


@app.get("/api/status")
def status():
    ttl = float(os.getenv("SENSOR_STALE_SECONDS", "20"))
    sensors = sensor_snapshot(DATA / "sensor_latest.json", ttl)
    return jsonify({"status": "ok", "sensor_available": sensors["sensor_source"] != "unavailable",
                    "attendance_available": attendance_snapshot(DATA / "attendance_data.json")["attendance_source"] != "unavailable"})


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", "8080"))
    app.run(host=os.getenv("DASHBOARD_HOST", "127.0.0.1"), port=port, debug=False)
