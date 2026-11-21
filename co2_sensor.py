"""CO2, temperature and humidity from a Sensirion SCD-40 (Adafruit STEMMA QT board).

The SCD-40 sits on the same I2C bus as the BME280, the ADS1115 and the LCD, at
address 0x62. It measures by itself every 5 seconds once started; main.py calls
`read()` once per loop and gets the newest values. Plain smbus2 (already
installed for the BME280), no extra library.

Never stops the node: if the sensor is missing, unplugged or answers garbage,
`read()` returns None for every value and tries to start it again every
SCD40_RETRY_SECONDS. Nothing is ever written to the sensor's memory (no
calibration changes), so a restart leaves it as it was.

The air pressure from the BME280 is passed on to it (`set_pressure`), which
makes the CO2 reading a little more accurate.

What the CO2 numbers mean in a greenhouse (CO2_LOW / CO2_HIGH):
    below 350 ppm   "low": the plants used up the CO2 (sunny day, closed vents)
    350-1500 ppm    "normal" (outside air is about 420)
    above 1500 ppm  "high": stuffy, open a vent

Settings (environment variables):
    SCD40=0                 turn it off
    SCD40_ADDRESS           default 0x62
    SCD40_RETRY_SECONDS     default 300 (look for a missing sensor again)
    CO2_LOW / CO2_HIGH      default 350 / 1500 ppm

Check it on the Pi: python3 co2_sensor.py
"""
from __future__ import annotations

import os
import time
from typing import Any, Callable, Optional

ENABLED = os.getenv("SCD40", "1") != "0"
ADDRESS = int(os.getenv("SCD40_ADDRESS", "0x62"), 0)
RETRY_SECONDS = float(os.getenv("SCD40_RETRY_SECONDS", "300"))
CO2_LOW = float(os.getenv("CO2_LOW", "350"))
CO2_HIGH = float(os.getenv("CO2_HIGH", "1500"))
STALE_SECONDS = 60   # no new reading for this long: report nothing rather than old numbers

# SCD4x commands (Sensirion datasheet)
START_PERIODIC = 0x21B1
STOP_PERIODIC = 0x3F86
DATA_READY = 0xE4B8
READ_MEASUREMENT = 0xEC05
AMBIENT_PRESSURE = 0xE000
REINIT = 0x3646

KEYS = ("co2_ppm", "co2_band", "co2_temperature_c", "co2_temperature_f", "co2_humidity")


def crc8(data: bytes) -> int:
    """Sensirion's CRC-8 (polynomial 0x31, start 0xFF)."""
    crc = 0xFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def words(raw: bytes) -> list[int]:
    """Split a reply into 16-bit words, checking each word's CRC."""
    if len(raw) % 3:
        raise ValueError("odd reply length")
    out = []
    for i in range(0, len(raw), 3):
        pair = bytes(raw[i:i + 2])
        if crc8(pair) != raw[i + 2]:
            raise ValueError("bad CRC")
        out.append((pair[0] << 8) | pair[1])
    return out


def word_bytes(value: int) -> bytes:
    pair = bytes([(value >> 8) & 0xFF, value & 0xFF])
    return pair + bytes([crc8(pair)])


def band(ppm: Optional[float]) -> Optional[str]:
    if ppm is None:
        return None
    if ppm < CO2_LOW:
        return "low"
    if ppm > CO2_HIGH:
        return "high"
    return "normal"


def convert(co2: int, t_raw: int, rh_raw: int) -> dict[str, Any]:
    temp_c = -45 + 175 * t_raw / 65535
    return {
        "co2_ppm": co2,
        "co2_band": band(co2),
        "co2_temperature_c": round(temp_c, 2),
        "co2_temperature_f": round(temp_c * 9 / 5 + 32, 2),
        "co2_humidity": round(100 * rh_raw / 65535, 2),
    }


def empty() -> dict[str, Any]:
    return {k: None for k in KEYS}


class SMBusLink:
    """Raw I2C to the sensor through smbus2 (opened per call, like the BME280 code)."""

    def __init__(self, address: int = ADDRESS, port: int = 1):
        self.address, self.port = address, port

    def write(self, data: bytes) -> None:
        import smbus2
        with smbus2.SMBus(self.port) as bus:
            bus.i2c_rdwr(smbus2.i2c_msg.write(self.address, list(data)))

    def read(self, n: int) -> bytes:
        import smbus2
        with smbus2.SMBus(self.port) as bus:
            msg = smbus2.i2c_msg.read(self.address, n)
            bus.i2c_rdwr(msg)
            return bytes(msg)


class SCD40:
    def __init__(self, link=None, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.link = link or SMBusLink()
        self.clock, self.sleep = clock, sleep
        self.started = False
        self.next_try = 0.0
        self.latest: dict[str, Any] = empty()
        self.latest_at: Optional[float] = None
        self.pressure_sent: Optional[int] = None
        self.said_missing = False

    def _command(self, cmd: int, arg: Optional[int] = None) -> None:
        data = bytes([cmd >> 8, cmd & 0xFF])
        if arg is not None:
            data += word_bytes(arg)
        self.link.write(data)

    def _ask(self, cmd: int, n_words: int, wait: float = 0.001) -> list[int]:
        self._command(cmd)
        self.sleep(wait)
        return words(self.link.read(3 * n_words))

    def start(self) -> bool:
        """Start measuring. A sensor left measuring by an earlier run is stopped first."""
        try:
            self._command(STOP_PERIODIC)
            self.sleep(0.5)
            self._command(START_PERIODIC)
        except (OSError, ValueError) as e:
            self.started = False
            self.next_try = self.clock() + RETRY_SECONDS
            if not self.said_missing:
                print(f"CO2 sensor (SCD-40) not found at {hex(ADDRESS)}: {e!r}. "
                      f"The rest of the node carries on; I'll look again every "
                      f"{RETRY_SECONDS:.0f} s.", flush=True)
                self.said_missing = True
            return False
        self.started = True
        self.pressure_sent = None
        if self.said_missing:
            print("CO2 sensor (SCD-40) found.", flush=True)
        self.said_missing = False
        print("CO2 sensor (SCD-40) measuring every 5 s.", flush=True)
        return True

    def set_pressure(self, hpa: Optional[float]) -> None:
        """Pass the BME280's air pressure on (more accurate CO2). Never raises."""
        if not self.started or hpa is None:
            return
        value = int(round(hpa))
        if not 700 <= value <= 1200 or value == self.pressure_sent:
            return
        try:
            self._command(AMBIENT_PRESSURE, value)
            self.pressure_sent = value
        except (OSError, ValueError):
            pass

    def read(self) -> dict[str, Any]:
        """The newest CO2 / temperature / humidity, or all None. Never raises."""
        if not ENABLED:
            return empty()
        now = self.clock()
        if not self.started and now >= self.next_try:
            self.start()
        if self.started:
            try:
                ready = self._ask(DATA_READY, 1)[0] & 0x07FF
                if ready:
                    co2, t_raw, rh_raw = self._ask(READ_MEASUREMENT, 3)
                    if co2:   # 0 means "not measured yet"
                        self.latest, self.latest_at = convert(co2, t_raw, rh_raw), now
            except ValueError:
                pass   # one garbled reply: keep the last good one
            except OSError as e:
                print(f"CO2 sensor (SCD-40) stopped answering: {e!r}", flush=True)
                self.started = False
                self.said_missing = True
                self.next_try = now + 10
        if self.latest_at is None or now - self.latest_at > STALE_SECONDS:
            return empty()
        return dict(self.latest)


_sensor: Optional[SCD40] = None


def read_co2_metrics(pressure_hpa: Optional[float] = None) -> dict[str, Any]:
    """For main.py: the readings as a dict (all None without a sensor). Never raises."""
    global _sensor
    try:
        if _sensor is None:
            _sensor = SCD40()
        _sensor.set_pressure(pressure_hpa)
        return _sensor.read()
    except Exception as e:   # belt and braces: the node must keep going
        print("CO2 sensor (SCD-40) error:", repr(e), flush=True)
        return empty()


if __name__ == "__main__":
    s = SCD40()
    if not s.start():
        raise SystemExit("No SCD-40 found. Check the STEMMA QT cable, then: i2cdetect -y 1 (look for 62)")
    print("Waiting for readings (the first one takes about 5 seconds)...")
    for _ in range(6):
        time.sleep(5)
        r = s.read()
        if r["co2_ppm"] is None:
            print("  not ready yet")
        else:
            print(f"  CO2 {r['co2_ppm']} ppm ({r['co2_band']}), "
                  f"{r['co2_temperature_f']:.1f} F, {r['co2_humidity']:.0f}% humidity")
