import glob
import os
from typing import Optional

W1_BASE_DIR = "/sys/bus/w1/devices"


def find_sensor() -> Optional[str]:
    """
    Return the path to the first detected DS18B20 sensor directory.
    Example: /sys/bus/w1/devices/28-0000005d2c81
    """
    matches = glob.glob(os.path.join(W1_BASE_DIR, "28-*"))
    return matches[0] if matches else None


def read_soil_temperature_c() -> Optional[float]:
    """
    Read soil temperature in Celsius from a DS18B20.
    Returns None if the sensor is unavailable or the read is invalid.
    """
    sensor_dir = find_sensor()
    if not sensor_dir:
        return None

    sensor_file = os.path.join(sensor_dir, "w1_slave")
    if not os.path.exists(sensor_file):
        return None

    try:
        with open(sensor_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if len(lines) < 2:
            return None

        # CRC check
        if not lines[0].strip().endswith("YES"):
            return None

        temp_index = lines[1].find("t=")
        if temp_index == -1:
            return None

        temp_milli_c = int(lines[1][temp_index + 2 :].strip())
        return round(temp_milli_c / 1000.0, 2)

    except (OSError, ValueError):
        return None


def read_soil_temperature_f() -> Optional[float]:
    """
    Read soil temperature in Fahrenheit.
    """
    temp_c = read_soil_temperature_c()
    if temp_c is None:
        return None
    return round((temp_c * 9 / 5) + 32, 2)
