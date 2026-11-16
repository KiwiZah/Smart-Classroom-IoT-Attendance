"""Privacy-conscious motion-triggered attendance from a real Raspberry Pi camera.

Not an enrolled/model training tool. Requires a private trusted classifier and
private consented roster. Cannot run without genuine camera, PIR and model.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from .state import DATA, ROOT, utc_now, write_json_atomic

LOG = logging.getLogger(__name__)


def load_roster(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict) or not isinstance(data.get("students"), list):
        raise ValueError("Expected private students.json with a 'students' list")
    roster = []
    labels = set()
    for item in data["students"]:
        if not isinstance(item, dict):
            raise ValueError("Invalid student roster record")
        label, student_id, name = (str(item.get(k, "")).strip() for k in ("model_label","id","name"))
        if not all((label, student_id, name)) or label in labels:
            raise ValueError("Each private student requires unique model_label, id and name")
        labels.add(label)
        roster.append({"model_label":label,"id":student_id,"name":name,"status":"Absent"})
    if not roster:
        raise ValueError("Private roster is empty")
    return roster


def run() -> None:
    # All the following imports are Raspberry Pi-specific and deliberately lazy.
    # NEVER open model files from untrusted sources: joblib/pickle can execute code.
    import RPi.GPIO as gpio
    from picamera2 import Picamera2
    import numpy as np
    import torch
    from facenet_pytorch import MTCNN, InceptionResnetV1
    from PIL import Image
    import joblib

    roster_file = DATA / "students.json"
    model_file = ROOT / "models" / "model.pkl"
    if not roster_file.is_file() or not model_file.is_file():
        raise FileNotFoundError("Private consented data/students.json AND trusted models/model.pkl required")
    roster = load_roster(roster_file)
    by_label = {s["model_label"]: s for s in roster}
    clf = joblib.load(model_file)  # trusted files only; never commit or load public .pkl
    if not all(hasattr(clf, name) for name in ("predict", "predict_proba")):
        raise ValueError("Classifier must support predict and predict_proba")

    device = torch.device("cpu")
    mtcnn = MTCNN(image_size=160, margin=0, device=device, keep_all=True)
    resnet = InceptionResnetV1(pretrained="vggface2").eval().to(device)
    threshold = float(os.getenv("FACE_CONFIDENCE_THRESHOLD", "0.7"))
    if not 0.0 < threshold <= 1:
        raise ValueError("FACE_CONFIDENCE_THRESHOLD must be in (0,1]")
    pir_pin = int(os.getenv("PIR_GPIO", "27"))
    last_seen = {}
    cooldown_seconds = 60.0

    def save() -> None:
        write_json_atomic(DATA / "attendance_data.json", {
            "timestamp": utc_now(),
            "students": [{"id":s["id"],"name":s["name"],"status":s["status"]} for s in roster],
            "source": "on-device enrollment/recognition",
        })

    gpio.setwarnings(False)
    gpio.setmode(gpio.BCM)
    gpio.setup(pir_pin, gpio.IN)
    last_trigger = 0.0
    save()  # All absent until actually recognized; no invented detected identities.
    try:
        while True:
            if gpio.input(pir_pin) and time.monotonic() - last_trigger >= 10:
                last_trigger = time.monotonic()
                camera = Picamera2()
                try:
                    config = camera.create_preview_configuration(
                        main={"size": (640, 480), "format": "RGB888"}
                    )
                    camera.configure(config)
                    camera.start()
                    time.sleep(2.0)
                    end_at = time.monotonic() + 10
                    with torch.no_grad():
                        while time.monotonic() < end_at:
                            rgb_frame = camera.capture_array()
                            # Camera is configured to RGB888; don't swap channels again.
                            image = Image.fromarray(np.asarray(rgb_frame, dtype=np.uint8), mode="RGB")
                            faces = mtcnn(image)
                            if faces is None:
                                time.sleep(0.2)
                                continue
                            if faces.ndim == 3:
                                faces = faces.unsqueeze(0)
                            for face in faces:
                                embedding = resnet(face.unsqueeze(0).to(device)).cpu().numpy()
                                try:
                                    probabilities = clf.predict_proba(embedding)[0]
                                    pred = str(clf.predict(embedding)[0])
                                except Exception as exc:
                                    LOG.error("Classifier error: %s", type(exc).__name__)
                                    continue
                                score = float(np.max(probabilities))
                                if pred not in by_label or not np.isfinite(score) or score < threshold:
                                    continue
                                now = time.monotonic()
                                if now - last_seen.get(pred, float("-inf")) < cooldown_seconds:
                                    continue
                                last_seen[pred] = now
                                if by_label[pred]["status"] == "Absent":
                                    by_label[pred]["status"] = "Present"
                                    save()
                                    LOG.info("Recorded a verified attendance event for an enrolled participant")
                            time.sleep(0.2)
                except Exception as exc:
                    LOG.error("Camera/recognition unavailable: %s", type(exc).__name__)
                finally:
                    try:
                        camera.stop()
                    except Exception:
                        pass
                    camera.close()
            time.sleep(0.2)
    finally:
        gpio.cleanup()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
