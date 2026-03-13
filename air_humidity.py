from __future__ import annotations

import smbus2
import bme280


def read_air_humidity(address: int = 0x76, port: int = 1) -> float:
    bus = smbus2.SMBus(port)
    try:
        calibration = bme280.load_calibration_params(bus, address)
        data = bme280.sample(bus, address, calibration)
        return float(data.humidity)
    finally:
        bus.close()


def read_air_pressure_hpa(address: int = 0x76, port: int = 1) -> float:
    bus = smbus2.SMBus(port)
    try:
        calibration = bme280.load_calibration_params(bus, address)
        data = bme280.sample(bus, address, calibration)
        return float(data.pressure)
    finally:
        bus.close()