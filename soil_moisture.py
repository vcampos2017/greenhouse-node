from __future__ import annotations

import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn


def read_soil_voltage(i2c_address: int = 0x48, channel: int = 0) -> float:
    i2c = busio.I2C(board.SCL, board.SDA)
    ads = ADS.ADS1115(i2c, address=i2c_address)
    chan = AnalogIn(ads, channel)
    return float(chan.voltage)


def voltage_to_percent(voltage: float, air_voltage: float, wet_voltage: float) -> int:
    if air_voltage == wet_voltage:
        return 0

    percent = ((air_voltage - voltage) / (air_voltage - wet_voltage)) * 100.0
    percent = max(0.0, min(100.0, percent))
    return int(round(percent))


def moisture_band(percent: int) -> str:
    if percent < 25:
        return "dry"
    if percent < 60:
        return "moderate"
    return "wet"


def read_soil_metrics(
    air_voltage: float,
    wet_voltage: float,
    i2c_address: int = 0x48,
    channel: int = 0,
) -> dict:
    voltage = read_soil_voltage(i2c_address=i2c_address, channel=channel)
    percent = voltage_to_percent(voltage, air_voltage=air_voltage, wet_voltage=wet_voltage)
    band = moisture_band(percent)
    return {
        "soil_voltage": voltage,
        "soil_moisture_percent": percent,
        "soil_moisture_band": band,
    }