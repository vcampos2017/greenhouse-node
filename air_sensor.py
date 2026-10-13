from __future__ import annotations

import smbus2
import bme280


def read_air_metrics(address: int = 0x76, port: int = 1) -> dict[str, float]:
    """Read temperature, humidity and pressure from the BME280 in a single sample."""
    bus = smbus2.SMBus(port)
    try:
        calibration = bme280.load_calibration_params(bus, address)
        data = bme280.sample(bus, address, calibration)
        return {
            "temperature_c": float(data.temperature),
            "humidity": float(data.humidity),
            "pressure_hpa": float(data.pressure),
        }
    finally:
        bus.close()


def c_to_f(temp_c: float) -> float:
    return (temp_c * 9.0 / 5.0) + 32.0
