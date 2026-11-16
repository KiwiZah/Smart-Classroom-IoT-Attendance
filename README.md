# Smart Classroom — IoT Monitoring & Face-Recognition Attendance

**University VIP project (2025) · Raspberry Pi 4 · DHT22 · MQ-2 · PIR · Camera · Flask**

Smart Classroom combines a motion-triggered attendance pipeline with temperature/humidity monitoring, a digital gas/smoke sensor indicator, and a web dashboard. This portfolio repository is a **cleaned reconstruction of recovered university project files**; the original CSS, layout, and visual design of the dashboard are preserved.

> **Hardware-ready, not hardware-verified.** The original classroom prototype was developed as a team project, but the cleaned integration has not been retested on the physical Raspberry Pi. Missing hardware reports **Unavailable**, not generated/random measurements. This is not a certified fire-safety or security system.

## Architecture

```text
DHT22 (GPIO17) ------> sensor collector --> data/sensor_latest.json --+
MQ-2 digital (GPIO7) --> sensor collector -------------------------------+--> Flask API --> Original web dashboard
PIR (GPIO27) --> Pi Camera --> MTCNN/FaceNet/classifier --> attendance_data.json -+
Optional OpenWeather API -----------------------------------------------+
```

- **Temperature/humidity:** actual DHT22 readings only; invalid/stale readings are unavailable.
- **Gas/smoke indicator:** MQ-2 digital threshold signal, **not ppm**, not an accurate fire detection system. GPIO pin and active level are configurable to match the module.
- **Attendance:** PIR triggers a Raspberry Pi camera; MTCNN finds faces, FaceNet extracts features, a **locally supplied and trusted** classifier matches authorized enrolled people, and a private attendance file updates the dashboard.
- **Weather:** optional real OpenWeather data if you supply your own API key. Otherwise unavailable.
- **Dashboard:** original HTML/CSS design preserved. No simulated readings, dummy students, or fake fallback statuses in the live application.

## Quick start — dashboard on Windows or macOS (no sensors required)

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python server.py
```

Open **http://127.0.0.1:8080**. Without an attached Raspberry Pi, measurements and attendance show **Unavailable**. This is expected and demonstrates honest missing-data handling without claiming live hardware.

## Raspberry Pi setup (optional, if hardware becomes available)

1. Use a Raspberry Pi OS compatible with `RPi.GPIO`, `picamera2`, `board` / Adafruit Blinka and PyTorch. Install the camera stack using system packages when supported. Platform-specific PyTorch builds may be necessary; dependency availability depends on the Pi OS/Python version.
2. Create a venv with system packages visible: `python3 -m venv --system-site-packages .venv`; activate it and install `requirements.txt`, `requirements-sensors.txt`, and `requirements-vision.txt`.
3. Wire the DHT22 data pin to GPIO17, PIR output to GPIO27 and **3.3 V-safe** MQ-2 digital output to the selected GPIO (default GPIO7). **A 5 V MQ-2 module output must not connect directly to a Raspberry Pi GPIO**; use a suitable level shifter. Check sensor wiring and power supplies before use.
4. Set `MQ2_GPIO` to the wired BCM pin and **explicitly set** `MQ2_ACTIVE_LEVEL` to `0` or `1` based on your module's actual trigger polarity. Until set, the sensor signal is displayed as **Unconfigured**, not Normal.
5. In separate terminals, start:
   - `python3 -m src.sensor_collector` (real DHT22 and MQ-2 reader)
   - `python3 -m src.motion_recognition` (optional, requires enrolled roster and model; details below)
   - `python3 server.py` (web dashboard)
6. To allow browser access on your private network, start the server with `DASHBOARD_HOST=0.0.0.0` only on a trusted network. No login is implemented; do **not** expose this server to the public internet.

### Face recognition and privacy

The original `model.pkl` and real students' names/IDs **are intentionally excluded**. Never publish trained face models, face embeddings, camera images, or personal attendance logs. The face recognition collector requires:

- `models/model.pkl`: a model **you trained yourself or trust**; loading pickle/joblib files can execute arbitrary code.
- `data/students.json`: a **private** roster based on [config/students.example.json](config/students.example.json) mapping each `model_label` to an authorized `id` and `name`.
- Explicit consent and lawful handling of facial biometrics.

The collector never needs to save photographs; it saves only a timestamp and attendance status for the enrolled roster. If the camera or model is absent, it **does not** invent attendance.

## Source structure

```text
index.html                     Original dashboard appearance with safer live-data JS
server.py                      Flask API (local sensor + attendance files; optional weather)
src/state.py                   Validation, freshness checks, atomic JSON writing
src/sensor_collector.py        Raspberry Pi DHT22 + MQ-2 readings
src/motion_recognition.py      Motion-triggered camera/FaceNet recognition
config/students.example.json   Anonymous template; no real students
tests/test_state.py            Offline tests (no Pi needed)
docs/ORIGINAL_VS_CLEAN.md      Engineering cleanup and limitations
```

## Data accuracy and limitations

- A DHT22 reading is a **measured** value, not calibrated laboratory ground truth.
- MQ-2 here is a **digital comparator output**, not numeric gas concentration or a reliable smoke/fire alarm.
- Face-recognition confidence is classifier-dependent and is **not a validated biometric accuracy metric**.
- The dashboard reads timestamped JSON files and discards stale readings. Hardware errors report unavailable rather than substituting random values.
- The original team materials vary in team labeling. This repository uses neutral attribution until the historical title/team roster is confirmed.
- No external face images are uploaded by this code; OpenWeather is optional.

## Attribution

University group project. This repository is a privacy-scrubbed, source-level cleanup of the original files. Specific individual contributions should be credited accurately when confirmed. Do not represent this code as a physical-hardware validation of the edited version.

## Run source-only tests

```bash
python -m unittest discover -s tests -v
```

There is no license granted for use of personal data, models, or media.
