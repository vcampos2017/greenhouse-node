from __future__ import annotations

import smbus2
import bme280


def read_air_temperature_c(address: int = 0x76, port: int = 1) -> float:
    bus = smbus2.SMBus(port)
    try:
        calibration = bme280.load_calibration_params(bus, address)
        data = bme280.sample(bus, address, calibration)
        return float(data.temperature)
    finally:
        bus.close()


def c_to_f(temp_c: float) -> float:
    return (temp_c * 9.0 / 5.0) + 32.0


def read_air_temperature_f(address: int = 0x76, port: int = 1) -> float:
    return c_to_f(read_air_temperature_c(address=address, port=port))
