from __future__ import annotations

import os
import threading
import time
from typing import Any

from air_temperature import read_air_temperature_c, c_to_f
from air_humidity import read_air_humidity, read_air_pressure_hpa
from soil_moisture import read_soil_metrics
from metric_logger import append_metrics_csv
from chatty_talker import post_to_chatty
from web_posting import create_app


# ---------- Configuration ----------
BME280_ADDRESS = 0x76
ADS1115_ADDRESS = 0x48
ADS_CHANNEL = 0

# Replace these later with your measured values
SOIL_AIR_VOLTAGE = 2.23
SOIL_WET_VOLTAGE = 1.35

LOOP_SECONDS = 10
CSV_LOG_PATH = "greenhouse_log.csv"
WEB_HOST = "0.0.0.0"
WEB_PORT = 5000
CHATTTY_POST_EVERY_N_LOOPS = 6  # every 60 seconds if LOOP_SECONDS=10


LATEST_METRICS: dict[str, Any] = {
    "air_temperature_c": None,
    "air_temperature_f": None,
    "air_humidity": None,
    "air_pressure_hpa": None,
    "soil_voltage": None,
    "soil_moisture_percent": None,
    "soil_moisture_band": None,
}


def collect_metrics() -> dict[str, Any]:
    temp_c = read_air_temperature_c(address=BME280_ADDRESS)
    humidity = read_air_humidity(address=BME280_ADDRESS)
    pressure = read_air_pressure_hpa(address=BME280_ADDRESS)

    soil = read_soil_metrics(
        air_voltage=SOIL_AIR_VOLTAGE,
        wet_voltage=SOIL_WET_VOLTAGE,
        i2c_address=ADS1115_ADDRESS,
        channel=ADS_CHANNEL,
    )

    metrics = {
        "air_temperature_c": round(temp_c, 2),
        "air_temperature_f": round(c_to_f(temp_c), 2),
        "air_humidity": round(humidity, 2),
        "air_pressure_hpa": round(pressure, 2),
        "soil_voltage": round(soil["soil_voltage"], 3),
        "soil_moisture_percent": soil["soil_moisture_percent"],
        "soil_moisture_band": soil["soil_moisture_band"],
    }
    return metrics


def metrics_provider() -> dict[str, Any]:
    return dict(LATEST_METRICS)


def run_web_server() -> None:
    app = create_app(metrics_provider)
    app.run(host=WEB_HOST, port=WEB_PORT, debug=False, use_reloader=False)


def main() -> None:
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()

    loop_count = 0

    while True:
        metrics = collect_metrics()
        LATEST_METRICS.update(metrics)

        append_metrics_csv(CSV_LOG_PATH, metrics)

        print("-" * 40)
        print(f"Air Temperature: {metrics['air_temperature_c']} C / {metrics['air_temperature_f']} F")
        print(f"Air Humidity   : {metrics['air_humidity']} %")
        print(f"Air Pressure   : {metrics['air_pressure_hpa']} hPa")
        print(f"Soil Voltage   : {metrics['soil_voltage']} V")
        print(f"Soil Moisture  : {metrics['soil_moisture_percent']} %")
        print(f"Soil Status    : {metrics['soil_moisture_band']}")

        loop_count += 1
        if loop_count % CHATTTY_POST_EVERY_N_LOOPS == 0:
            posted = post_to_chatty(metrics)
            if posted:
                print("Posted metrics to Chatty.")
            else:
                print("Chatty post skipped or failed.")

        time.sleep(LOOP_SECONDS)


if __name__ == "__main__":
    main()