from __future__ import annotations

import threading
import time
import socket
from pathlib import Path
import led_status
from typing import Any

from air_temperature import read_air_temperature_c, c_to_f
from soil_temperature import read_soil_temperature_c
from air_humidity import read_air_humidity, read_air_pressure_hpa
from soil_moisture import read_soil_metrics
from metric_logger import append_metrics_csv
from chatty_talker import post_to_chatty
from web_posting import create_app
from lcd_display import LCDDisplay


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

WATER_ALERT_COOLDOWN_SECONDS = 6 * 60 * 60  # 6 hours
WATER_ALERT_STATE_FILE = Path("last_water_alert.txt")
DRY_BANDS = {"dry", "critically dry"}


LATEST_METRICS: dict[str, Any] = {
    "air_temperature_c": None,
    "air_temperature_f": None,
    "air_humidity": None,
    "air_pressure_hpa": None,
    "soil_voltage": None,
    "soil_moisture_percent": None,
    "soil_moisture_band": None,
    "soil_temperature_c": None,
}


def get_local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"
    finally:
        sock.close()
    return ip


def collect_metrics() -> dict[str, Any]:
    temp_c = read_air_temperature_c(address=BME280_ADDRESS)
    humidity = read_air_humidity(address=BME280_ADDRESS)
    pressure = read_air_pressure_hpa(address=BME280_ADDRESS)
    soil_temp_c = read_soil_temperature_c()
    soil_temp_f = c_to_f(soil_temp_c) if soil_temp_c is not None else None

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
        "soil_temperature_c": round(soil_temp_c, 2) if soil_temp_c is not None else None,
        "soil_temperature_f": round(soil_temp_f, 2) if soil_temp_f is not None else None,
    }
    return metrics


def metrics_provider() -> dict[str, Any]:
    return dict(LATEST_METRICS)


def run_web_server() -> None:
    led_status.set_blue(True)
    app = create_app(metrics_provider)
    app.run(host=WEB_HOST, port=WEB_PORT, debug=False, use_reloader=False)


def load_last_water_alert_time() -> float:
    try:
        return float(WATER_ALERT_STATE_FILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0.0


def save_last_water_alert_time(ts: float) -> None:
    WATER_ALERT_STATE_FILE.write_text(str(ts))


def should_send_water_alert(metrics: dict[str, Any], last_alert_ts: float) -> bool:
    band = str(metrics.get("soil_moisture_band", "")).strip().lower()
    if band not in DRY_BANDS:
        return False

    now = time.time()
    return (now - last_alert_ts) >= WATER_ALERT_COOLDOWN_SECONDS


def build_water_alert_message(metrics: dict[str, Any]) -> str:
    percent = metrics.get("soil_moisture_percent")
    band = str(metrics.get("soil_moisture_band", "dry")).strip().lower()
    temp_f = metrics.get("air_temperature_f")

    if band == "critically dry":
        urgency = "Please water the plant soon."
    else:
        urgency = "Watering is recommended."

    return (
        f"Greenhouse alert: Soil is {band} at {percent}%. "
        f"Air temperature is {temp_f} F. {urgency}"
    )


def main() -> None:
    led_status.setup()
    led_status.set_green(True)
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()

    lcd = LCDDisplay(address=0x27)
    ip_address = get_local_ip()

    lcd.show_message("Greenhouse Node", "Starting...", delay_seconds=2)
    lcd.show_ip_address(ip_address, port=WEB_PORT, delay_seconds=4)

    loop_count = 0
    last_soil_band = None
    water_alert_active = False

    try:
        while True:
            metrics = collect_metrics()
            LATEST_METRICS.update(metrics)

            current_band = str(metrics["soil_moisture_band"]).strip().lower()
            led_status.set_red(current_band in DRY_BANDS)

            entered_dry_state = (
                current_band in DRY_BANDS and
                last_soil_band not in DRY_BANDS
            )

            recovered_from_dry = (
                current_band not in DRY_BANDS and
                (last_soil_band in DRY_BANDS if last_soil_band is not None else False)
            )

            if entered_dry_state and not water_alert_active:
                alert_message = build_water_alert_message(metrics)
                print(f"Chatty water alert: {alert_message}")

                posted = post_to_chatty({
                    **metrics,
                    "alert_type": "water_needed",
                    "alert_message": alert_message,
                })

                if posted:
                    print("Water alert posted to Chatty.")
                    water_alert_active = True
                else:
                    print("Water alert failed to post to Chatty.")

            if recovered_from_dry:
                print("Soil recovered from dry state. Water alert reset.")
                water_alert_active = False

            last_soil_band = current_band

            append_metrics_csv(CSV_LOG_PATH, metrics)

            print("-" * 40)
            print(f"Air Temperature: {metrics['air_temperature_c']} C / {metrics['air_temperature_f']} F")
            print(f"Air Humidity   : {metrics['air_humidity']} %")
            print(f"Air Pressure   : {metrics['air_pressure_hpa']} hPa")
            print(f"Soil Voltage   : {metrics['soil_voltage']} V")
            print(f"Soil Temp      : {metrics['soil_temperature_c']} C / {metrics['soil_temperature_f']} F")
            print(f"Soil Moisture  : {metrics['soil_moisture_percent']} %")
            print(f"Soil Status    : {metrics['soil_moisture_band']}")
            print(f"Dashboard      : http://{ip_address}:{WEB_PORT}")

            lcd.show_metrics(
                metrics,
                ip_address=ip_address,
                web_port=WEB_PORT,
                delay_seconds=2.5,
                include_ip=True,
            )

            loop_count += 1
            if loop_count % CHATTTY_POST_EVERY_N_LOOPS == 0:
                posted = post_to_chatty(metrics)
                if posted:
                    print("Posted metrics to Chatty.")
                else:
                    print("Chatty post skipped or failed.")

            time.sleep(LOOP_SECONDS)

    except KeyboardInterrupt:
        lcd.show_message("Monitor stopped", "", delay_seconds=1.5)
    finally:
        lcd.clear()
        led_status.cleanup()


if __name__ == "__main__":
    main()