"""Read real DHT22 and MQ-2 digital threshold; publish timestamped local readings.

Run on a Raspberry Pi with the required sensors wired. No artificial fallback data.
An MQ-2 digital comparator does not provide ppm and cannot act as a fire alarm.
"""
from __future__ import annotations

import logging
import os
import time

from .state import DATA, utc_now, write_json_atomic

LOG = logging.getLogger(__name__)


def read_loop() -> None:
    # Import Raspberry Pi-only dependencies *inside* the Pi-specific path.
    import board
    import adafruit_dht
    import RPi.GPIO as gpio

    dht_pin_num = int(os.getenv("DHT22_GPIO", "17"))
    mq_pin_num = int(os.getenv("MQ2_GPIO", "7"))
    polarity = os.getenv("MQ2_ACTIVE_LEVEL", "").strip()
    if polarity not in ("", "0", "1"):
        raise ValueError("MQ2_ACTIVE_LEVEL must be empty, 0 or 1")
    active_level = int(polarity) if polarity else None
    if not 0 <= mq_pin_num <= 27:
        raise ValueError("MQ2_GPIO is not a supported BCM GPIO pin")
    dht_pin = getattr(board, f"D{dht_pin_num}", None)
    if dht_pin is None:
        raise ValueError("Invalid DHT22_GPIO pin")
    dht = adafruit_dht.DHT22(dht_pin, use_pulseio=False)
    gpio.setmode(gpio.BCM)
    gpio.setwarnings(False)
    gpio.setup(mq_pin_num, gpio.IN)
    try:
        while True:
            temp, humid = None, None
            for attempt in range(3):
                try:
                    reading_t = dht.temperature
                    reading_h = dht.humidity
                    if reading_t is not None and reading_h is not None:
                        temp, humid = float(reading_t), float(reading_h)
                        break
                except RuntimeError as exc:
                    LOG.warning("DHT22 transient error: %s", exc)
                except Exception as exc:
                    LOG.error("DHT22 error: %s", exc)
                    break
                time.sleep(0.5)

            gas_triggered = None
            gas_status = "Unconfigured" if active_level is None else "Unavailable"
            if active_level is not None:
                try:
                    gas_triggered = bool(gpio.input(mq_pin_num) == active_level)
                    gas_status = "Triggered" if gas_triggered else "No trigger"
                except Exception as exc:
                    LOG.error("MQ-2 GPIO read failed: %s", exc)

            write_json_atomic(DATA / "sensor_latest.json", {
                "timestamp": utc_now(),
                "temperature": temp,
                "humidity": humid,
                "gas_triggered": gas_triggered,
                "gas_status": gas_status
            })
            LOG.info("DHT22: %s °C / %s %% | MQ-2: %s", temp, humid, gas_status)
            time.sleep(3)
    finally:
        dht.exit()
        gpio.cleanup()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    read_loop()
