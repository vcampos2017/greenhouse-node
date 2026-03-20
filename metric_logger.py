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
]


def append_metrics_csv(log_path: str | Path, metrics: Mapping[str, Any]) -> None:
    path = Path(log_path)
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
    }

    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
