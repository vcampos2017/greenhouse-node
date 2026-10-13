from __future__ import annotations

import signal
import threading
import time
import socket
import traceback
from datetime import datetime
from pathlib import Path
import led_status
from typing import Any, Callable

from air_sensor import read_air_metrics, c_to_f
from soil_temperature import read_soil_temperature_c
from soil_moisture import read_soil_metrics
from metric_logger import append_metrics_csv
from chatty_talker import post_to_chatty
from web_posting import create_app
from lcd_display import LCDDisplay


# ---------- Configuration ----------
BME280_ADDRESS = 0x76
ADS1115_ADDRESS = 0x48
ADS_CHANNEL = 0
LCD_ADDRESS = 0x27

# Replace these later with your measured values
SOIL_AIR_VOLTAGE = 2.23
SOIL_WET_VOLTAGE = 1.35

LOOP_SECONDS = 10
CSV_LOG_PATH = "greenhouse_log.csv"
WEB_HOST = "0.0.0.0"
WEB_PORT = 5000
CHATTY_POST_EVERY_N_LOOPS = 6  # every 60 seconds if LOOP_SECONDS=10
LCD_SCREEN_SECONDS = 2.5

WATER_ALERT_COOLDOWN_SECONDS = 6 * 60 * 60  # 6 hours
WATER_ALERT_STATE_FILE = Path("last_water_alert.txt")
DRY_BANDS = {"dry", "critically dry"}


LATEST_METRICS: dict[str, Any] = {
    "timestamp": None,
    "air_temperature_c": None,
    "air_temperature_f": None,
    "air_humidity": None,
    "air_pressure_hpa": None,
    "soil_voltage": None,
    "soil_moisture_percent": None,
    "soil_moisture_band": None,
    "soil_temperature_c": None,
    "soil_temperature_f": None,
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


def read_sensor(name: str, read: Callable[[], Any]) -> Any:
    """Run a sensor read, returning None instead of raising if it fails."""
    try:
        return read()
    except Exception as exc:
        print(f"Sensor read failed ({name}): {exc}")
        return None


def round_or_none(value: float | None, digits: int) -> float | None:
    return round(value, digits) if value is not None else None


def collect_metrics() -> dict[str, Any]:
    air = read_sensor("BME280", lambda: read_air_metrics(address=BME280_ADDRESS)) or {}
    temp_c = air.get("temperature_c")
    soil_temp_c = read_sensor("soil temperature", read_soil_temperature_c)

    soil = read_sensor(
        "soil moisture",
        lambda: read_soil_metrics(
            air_voltage=SOIL_AIR_VOLTAGE,
            wet_voltage=SOIL_WET_VOLTAGE,
            i2c_address=ADS1115_ADDRESS,
            channel=ADS_CHANNEL,
        ),
    ) or {}

    metrics = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "air_temperature_c": round_or_none(temp_c, 2),
        "air_temperature_f": round_or_none(c_to_f(temp_c), 2) if temp_c is not None else None,
        "air_humidity": round_or_none(air.get("humidity"), 2),
        "air_pressure_hpa": round_or_none(air.get("pressure_hpa"), 2),
        "soil_voltage": round_or_none(soil.get("soil_voltage"), 3),
        "soil_moisture_percent": soil.get("soil_moisture_percent"),
        "soil_moisture_band": soil.get("soil_moisture_band"),
        "soil_temperature_c": round_or_none(soil_temp_c, 2),
        "soil_temperature_f": round_or_none(c_to_f(soil_temp_c), 2) if soil_temp_c is not None else None,
    }
    return metrics


def metrics_provider() -> dict[str, Any]:
    return dict(LATEST_METRICS)


def run_web_server() -> None:
    led_status.set_blue(True)
    app = create_app(metrics_provider)
    app.run(host=WEB_HOST, port=WEB_PORT, debug=False, use_reloader=False)


def init_lcd() -> LCDDisplay | None:
    try:
        return LCDDisplay(address=LCD_ADDRESS)
    except Exception as exc:
        print(f"LCD not available, continuing without it: {exc}")
        return None


def run_lcd(lcd: LCDDisplay | None, action: Callable[[LCDDisplay], None]) -> None:
    """Run an LCD action, skipping it if there is no LCD and ignoring LCD errors."""
    if lcd is None:
        return
    try:
        action(lcd)
    except Exception as exc:
        print(f"LCD error: {exc}")


def run_lcd_display(lcd: LCDDisplay, ip_address: str, stop: threading.Event) -> None:
    """Cycle the LCD through the latest readings until stop is set.

    Runs in its own thread so the screen pauses don't slow down sensor reads.
    """
    run_lcd(lcd, lambda d: d.write_lines("Greenhouse Node", "Starting..."))
    if stop.wait(2):
        return
    run_lcd(lcd, lambda d: d.write_lines("Web Dashboard:", f"{ip_address}:{WEB_PORT}"))
    if stop.wait(4):
        return

    while True:
        screens = lcd.metric_screens(metrics_provider(), ip_address=ip_address, web_port=WEB_PORT)
        for line1, line2 in screens:
            run_lcd(lcd, lambda d: d.write_lines(line1, line2))
            if stop.wait(LCD_SCREEN_SECONDS):
                return


def load_last_water_alert_time() -> float:
    try:
        return float(WATER_ALERT_STATE_FILE.read_text().strip())
    except (OSError, ValueError):
        return 0.0


def save_last_water_alert_time(ts: float) -> None:
    try:
        WATER_ALERT_STATE_FILE.write_text(str(ts))
    except OSError as exc:
        print(f"Could not save water alert time: {exc}")


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


def handle_sigterm(signum: int, frame: Any) -> None:
    # systemd stops the service with SIGTERM; treat it like Ctrl+C so cleanup runs.
    raise KeyboardInterrupt


def main() -> None:
    signal.signal(signal.SIGTERM, handle_sigterm)
    led_status.setup()
    led_status.set_green(True)
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()

    lcd = init_lcd()
    ip_address = get_local_ip()

    lcd_stop = threading.Event()
    lcd_thread = None
    if lcd is not None:
        lcd_thread = threading.Thread(target=run_lcd_display, args=(lcd, ip_address, lcd_stop), daemon=True)
        lcd_thread.start()

    def stop_lcd_thread() -> None:
        lcd_stop.set()
        if lcd_thread is not None:
            lcd_thread.join(timeout=2)

    loop_count = 0
    last_soil_band = None
    # Persisted so that restarting the node doesn't re-send an alert
    # that already went out within the cooldown window.
    last_water_alert_ts = load_last_water_alert_time()

    try:
        while True:
            cycle_start = time.monotonic()
            try:
                metrics = collect_metrics()
                LATEST_METRICS.update(metrics)

                band = metrics["soil_moisture_band"]
                current_band = band.strip().lower() if band is not None else None
                led_status.set_red(current_band in DRY_BANDS)

                # Sends when the soil is dry and no alert has gone out within the
                # cooldown. A failed post is retried on the next loop, and while the
                # soil stays dry a reminder goes out once per cooldown period.
                if should_send_water_alert(metrics, last_water_alert_ts):
                    alert_message = build_water_alert_message(metrics)
                    print(f"Chatty water alert: {alert_message}")

                    posted = post_to_chatty({
                        **metrics,
                        "alert_type": "water_needed",
                        "alert_message": alert_message,
                    })

                    if posted:
                        print("Water alert posted to Chatty.")
                        last_water_alert_ts = time.time()
                        save_last_water_alert_time(last_water_alert_ts)
                    else:
                        print("Water alert failed to post to Chatty. Will retry next loop.")

                if current_band is not None:
                    if last_soil_band in DRY_BANDS and current_band not in DRY_BANDS:
                        print("Soil recovered from dry state.")
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

                loop_count += 1
                if loop_count % CHATTY_POST_EVERY_N_LOOPS == 0:
                    posted = post_to_chatty(metrics)
                    if posted:
                        print("Posted metrics to Chatty.")
                    else:
                        print("Chatty post skipped or failed.")

            except Exception:
                # Never let one bad cycle (I2C glitch, full disk, etc.) stop the monitor.
                print("Error during monitoring loop; retrying next cycle.")
                traceback.print_exc()

            # Sleep only for what's left of the cycle so readings stay LOOP_SECONDS apart.
            elapsed = time.monotonic() - cycle_start
            time.sleep(max(0.0, LOOP_SECONDS - elapsed))

    except KeyboardInterrupt:
        stop_lcd_thread()
        run_lcd(lcd, lambda d: d.show_message("Monitor stopped", "", delay_seconds=1.5))
    finally:
        stop_lcd_thread()
        run_lcd(lcd, lambda d: d.clear())
        led_status.cleanup()


if __name__ == "__main__":
    main()
