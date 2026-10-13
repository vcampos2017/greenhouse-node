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

    def metric_screens(
        self,
        metrics: Mapping[str, Any],
        ip_address: str | None = None,
        web_port: int = 5000,
    ) -> list[tuple[str, str]]:
        """Return the (line1, line2) screens to cycle through for these metrics."""
        def value(key: str) -> Any:
            # Failed sensor reads come through as None
            result = metrics.get(key)
            return "n/a" if result is None else result

        screens = [
            (f"T:{value('air_temperature_f')}F H:{value('air_humidity')}%", f"Soil:{value('soil_moisture_percent')}%"),
            ("Soil Temp:", f"{value('soil_temperature_f')} F"),
            ("Pressure:", f"{value('air_pressure_hpa')} hPa"),
            ("Soil Status:", str(value("soil_moisture_band")).capitalize()),
        ]
        if ip_address:
            screens.append(("Web Dashboard:", self._short_ip(ip_address, web_port)))
        return screens

    def _fit(self, text: Any) -> str:
        return str(text)[: self.cols].ljust(self.cols)

    def _short_ip(self, ip_address: str, port: int) -> str:
        text = f"{ip_address}:{port}"
        return text[: self.cols]