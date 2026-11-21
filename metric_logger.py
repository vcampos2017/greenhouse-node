from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Mapping, Any


FIELDNAMES = [
    "timestamp",
    "air_temperature_c",
    "air_temperature_f",
    "air_humidity",
    "air_pressure_hpa",
    "soil_voltage",
    "soil_moisture_percent",
    "soil_temperature_c",
    "soil_temperature_f",
    "soil_moisture_band",
    # added 2026-11 (SCD-40 CO2 sensor): at the end, so older logs still line up
    "co2_ppm",
    "co2_temperature_f",
    "co2_humidity",
]


def _start_fresh_if_old(path: Path) -> None:
    """A log written before new columns were added keeps its own header, so its
    new rows wouldn't line up. Move it aside once (greenhouse_log-YYYYMMDD.csv)
    and start a new one with the full header. Nothing is deleted."""
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            header = next(csv.reader([f.readline()]), [])
    except OSError:
        return
    if not header or header == FIELDNAMES:
        return
    old = path.with_name(f"{path.stem}-{datetime.now():%Y%m%d-%H%M%S}{path.suffix}")
    try:
        path.rename(old)
        print(f"Log: new columns, so the old log is now {old.name}", flush=True)
    except OSError:
        pass


def append_metrics_csv(log_path: str | Path, metrics: Mapping[str, Any]) -> None:
    path = Path(log_path)
    if path.exists():
        _start_fresh_if_old(path)
    file_exists = path.exists()

    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "air_temperature_c": metrics.get("air_temperature_c"),
        "air_temperature_f": metrics.get("air_temperature_f"),
        "air_humidity": metrics.get("air_humidity"),
        "air_pressure_hpa": metrics.get("air_pressure_hpa"),
        "soil_voltage": metrics.get("soil_voltage"),
        "soil_moisture_percent": metrics.get("soil_moisture_percent"),
        "soil_moisture_band": metrics.get("soil_moisture_band"),
        "soil_temperature_c": metrics.get("soil_temperature_c"),
        "soil_temperature_f": metrics.get("soil_temperature_f"),
        "co2_ppm": metrics.get("co2_ppm"),
        "co2_temperature_f": metrics.get("co2_temperature_f"),
        "co2_humidity": metrics.get("co2_humidity"),
    }

    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
