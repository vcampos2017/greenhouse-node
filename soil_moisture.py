from __future__ import annotations

import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn


_i2c: busio.I2C | None = None
_ads: dict[int, ADS.ADS1115] = {}


def _get_ads(i2c_address: int) -> ADS.ADS1115:
    """Return a cached ADS1115 so the I2C bus isn't reopened on every read."""
    global _i2c
    if _i2c is None:
        _i2c = busio.I2C(board.SCL, board.SDA)
    if i2c_address not in _ads:
        _ads[i2c_address] = ADS.ADS1115(_i2c, address=i2c_address)
    return _ads[i2c_address]


def _reset_i2c() -> None:
    global _i2c
    _ads.clear()
    if _i2c is not None:
        try:
            _i2c.deinit()
        except Exception:
            pass
        _i2c = None


def read_soil_voltage(i2c_address: int = 0x48, channel: int = 0) -> float:
    try:
        chan = AnalogIn(_get_ads(i2c_address), channel)
        return float(chan.voltage)
    except Exception:
        # Start from a fresh connection next time in case the bus got into a bad state
        _reset_i2c()
        raise


def voltage_to_percent(voltage: float, air_voltage: float, wet_voltage: float) -> int:
    if air_voltage == wet_voltage:
        return 0

    percent = ((air_voltage - voltage) / (air_voltage - wet_voltage)) * 100.0
    percent = max(0.0, min(100.0, percent))
    return int(round(percent))


def moisture_band(percent: int) -> str:
    if percent < 10:
        return "critically dry"
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