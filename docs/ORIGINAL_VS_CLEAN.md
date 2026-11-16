# Source recovery and cleanup notes

## Original source recovered

- `server.py`: Flask dashboard API with random temperature/gas and invented weather fallback; local and network attendance lookup used inconsistent response shapes; hard-coded weather API credential.
- `index.html`: original 2025 light-blue dashboard (Home, Environment, Students). CSS, layout, navigation and animations preserved in the cleaned version. Only data-handling labels and JS are modified.
- `face_recognition/motion_recognition.py`: actual PIR / Pi Camera / MTCNN / FaceNet / scikit-learn recognition, but tied to six personally identifiable student records and a trusted local pickle model.
- `temperature/dht22_sensor.py`: real DHT22 sensor monitoring and CSV logs, previously a standalone process not wired into dashboard API.
- `fire_detection/mq2_sensor.py`: digital MQ-2 read; conflicting BCM GPIO defaults 4 and 7, conflicting active-level interpretation, and an overconfident fire alarm claim.
- `demo_attendance.py`: clearly marked simulated attendance program; not part of live code package.
- `model.pkl`: historical trained classifier; **excluded** from GitHub, not loaded/executed during this cleanup.
- `._*` and `__MACOSX`: macOS Finder metadata only; excluded.

## Cleanup decisions

1. No simulated temperature, gas, humidity, weather or attendance records.
2. Actual sensor acquisition uses GPIO; if collector stops, server marks sensor data stale and unavailable.
3. MQ-2 is a *digital threshold indicator*, not a ppm sensor or certified fire/smoke alarm. Active polarity defaults to unset until wiring is confirmed.
4. Attendance depends on local privately enrolled roster and a trusted trained classifier. Any missing dependency means attendance remains unavailable.
5. Original student names, student IDs, photographs, model weights, and exposed API key are not uploaded. Replace/revoke the original weather API key.
6. App runs on loopback by default; no public internet deployment or web authentication.
7. GUI color scheme and page layout preserved; only data labels and fetch behavior changed to avoid false information.

## Test status

Only code-level review is available without original Raspberry Pi equipment and enrolled participants. Physical sensor wiring, camera acquisition, model compatibility, calibration, and attendance correctness have **not** been revalidated. An unchanged visual layout does not imply every hardware integration is operational.
