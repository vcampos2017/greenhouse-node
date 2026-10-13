from __future__ import annotations

import time
from typing import Mapping, Any

from RPLCD.i2c import CharLCD


class LCDDisplay:
    def __init__(
        self,
        address: int = 0x27,
        port: int = 1,
        cols: int = 16,
        rows: int = 2,
    ) -> None:
        self.address = address
        self.port = port
        self.cols = cols
        self.rows = rows
        self.lcd = CharLCD(
            i2c_expander="PCF8574",
            address=self.address,
            port=self.port,
            cols=self.cols,
            rows=self.rows,
            charmap="A02",
            auto_linebreaks=False,
        )

    def clear(self) -> None:
        self.lcd.clear()

    def close(self) -> None:
        self.lcd.clear()
        self.lcd.backlight_enabled = False

    def write_lines(self, line1: str = "", line2: str = "") -> None:
        self.lcd.clear()
        self.lcd.cursor_pos = (0, 0)
        self.lcd.write_string(self._fit(line1))
        self.lcd.cursor_pos = (1, 0)
        self.lcd.write_string(self._fit(line2))

    def show_message(self, line1: str, line2: str = "", delay_seconds: float | None = None) -> None:
        self.write_lines(line1, line2)
        if delay_seconds is not None:
            time.sleep(delay_seconds)

    def show_ip_address(self, ip_address: str, port: int = 5000, delay_seconds: float = 4.0) -> None:
        self.write_lines("Web Dashboard:", self._short_ip(ip_address, port))
        time.sleep(delay_seconds)

    def show_metrics(
        self,
        metrics: Mapping[str, Any],
        ip_address: str | None = None,
        web_port: int = 5000,
        delay_seconds: float = 4.0,
        include_ip: bool = False,
    ) -> None:
        def value(key: str) -> Any:
            # Failed sensor reads come through as None
            result = metrics.get(key)
            return "n/a" if result is None else result

        temp_f = value("air_temperature_f")
        humidity = value("air_humidity")
        pressure = value("air_pressure_hpa")
        soil_percent = value("soil_moisture_percent")
        soil_band = value("soil_moisture_band")
        soil_temp_f = value("soil_temperature_f")

        self.write_lines(
            f"T:{temp_f}F H:{humidity}%",
            f"Soil:{soil_percent}%"
        )
        time.sleep(delay_seconds)

        self.write_lines(
            "Soil Temp:",
            f"{soil_temp_f} F"
        )
        time.sleep(delay_seconds)

        self.write_lines(
            "Pressure:",
            f"{pressure} hPa"
        )
        time.sleep(delay_seconds)

        self.write_lines(
            "Soil Status:",
            str(soil_band).capitalize()
        )
        time.sleep(delay_seconds)

        if include_ip and ip_address:
            self.show_ip_address(ip_address, port=web_port, delay_seconds=delay_seconds)

    def _fit(self, text: Any) -> str:
        return str(text)[: self.cols].ljust(self.cols)

    def _short_ip(self, ip_address: str, port: int) -> str:
        text = f"{ip_address}:{port}"
        return text[: self.cols]