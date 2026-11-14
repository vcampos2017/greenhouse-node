"""Tests for greenhouse_status.py (the SSH login summary). Plain Python.
Run: python3 tests/test_greenhouse_status.py"""
import io
import os
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import greenhouse_status as gs  # noqa: E402
import metric_logger  # noqa: E402


def _log(rows, header=None):
    d = tempfile.mkdtemp()
    p = os.path.join(d, "greenhouse_log.csv")
    with open(p, "w") as f:
        f.write(",".join(header or gs.FIELDNAMES) + "\n")
        for r in rows:
            f.write(",".join(r) + "\n")
    return p


def test_fieldnames_match_logger():
    assert gs.FIELDNAMES == metric_logger.FIELDNAMES


def test_reads_newest_row_of_real_log():
    p = os.path.join(tempfile.mkdtemp(), "log.csv")
    base = {"air_temperature_c": 22.0, "air_temperature_f": 71.6, "air_humidity": 64.0,
            "air_pressure_hpa": 1012.0, "soil_voltage": 1.8,
            "soil_moisture_percent": 49, "soil_moisture_band": "moderate"}
    for i in range(500):
        metric_logger.append_metrics_csv(p, dict(base, soil_moisture_percent=i))
    row = gs.latest_reading(p)
    assert row["soil_moisture_percent"] == "499"
    assert row["soil_moisture_band"] == "moderate"
    assert "moderate" in gs.soil_line(row) and "499%" in gs.soil_line(row)
    assert "71.6 F" in gs.air_line(row) and "64% humidity" in gs.air_line(row)


def test_empty_or_missing_log():
    assert gs.latest_reading(_log([])) is None
    assert gs.latest_reading("/nonexistent/x.csv") is None


def test_older_header_is_used_when_columns_differ():
    header = ["timestamp", "air_temperature_f", "soil_moisture_band"]
    row = gs.latest_reading(_log([["2026-11-14T10:00:00", "70.0", "dry"]], header))
    assert row["soil_moisture_band"] == "dry" and row["air_temperature_f"] == "70.0"


def test_zero_volts_means_unplugged():
    line = gs.soil_line({"soil_voltage": "0.002", "soil_moisture_percent": "100",
                         "soil_moisture_band": "wet"})
    assert "unplugged" in line and "wet" not in line


def test_reading_age_and_ago():
    now = datetime(2026, 11, 14, 11, 0, 0)
    age, ts = gs.reading_age({"timestamp": (now - timedelta(seconds=30)).isoformat()}, now)
    assert age == 30 and ts.hour == 10
    assert gs.ago(30) == "30 s ago"
    assert gs.ago(5 * 60) == "5 min ago"
    assert gs.ago(3 * 86400) == "3 days ago"
    assert gs.reading_age({"timestamp": "junk"}) == (None, None)


def test_main_prints_banner_and_never_crashes():
    p = _log([[(datetime.now()).isoformat(timespec="seconds"), "21", "69.8", "60", "1010",
               "1.9", "40", "", "", "moderate"]])
    gs.LOG_PATH = p
    gs.latest_reading.__defaults__ = (p,)
    gs.service_state = lambda name: "active"
    gs.mqtt_peer = lambda: "100.69.130.79"
    gs.WIFI_STATUS = _log([])  # not JSON: falls back quietly
    out = io.StringIO()
    with redirect_stdout(out):
        gs.main()
    text = out.getvalue()
    assert "GREENHOUSE" in text and "moderate" in text
    assert "greenhouse active" in text and "mqtt tailscale" in text
    assert "readings stopped" not in text


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
