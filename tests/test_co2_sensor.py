"""Tests for co2_sensor.py (SCD-40) with a pretend sensor. Plain Python, no smbus2.
Run: python3 tests/test_co2_sensor.py"""
import io
import os
import sys
import tempfile
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import co2_sensor as co2  # noqa: E402
import greenhouse_status as gs  # noqa: E402
import metric_logger  # noqa: E402


class FakeSensor:
    """Answers like an SCD-40: a command is 2 bytes (+ word + CRC), replies are words + CRC."""

    def __init__(self, present=True, ppm=812, t_raw=26214, rh_raw=39321):
        self.present = present
        self.ppm, self.t_raw, self.rh_raw = ppm, t_raw, rh_raw
        self.ready = True
        self.measuring = False
        self.last = None
        self.writes = []
        self.garble = False

    def write(self, data):
        if not self.present:
            raise OSError(121, "Remote I/O error")
        self.writes.append(bytes(data))
        cmd = (data[0] << 8) | data[1]
        if cmd == co2.START_PERIODIC:
            self.measuring = True
        elif cmd == co2.STOP_PERIODIC:
            self.measuring = False
        self.last = cmd

    def read(self, n):
        if not self.present:
            raise OSError(121, "Remote I/O error")
        if self.last == co2.DATA_READY:
            vals = [0x8006 if self.ready else 0x8000]
        elif self.last == co2.READ_MEASUREMENT:
            vals = [self.ppm, self.t_raw, self.rh_raw]
        else:
            vals = [0] * (n // 3)
        out = b"".join(co2.word_bytes(v) for v in vals)
        if self.garble:
            out = out[:-1] + bytes([out[-1] ^ 0xFF])
        return out[:n]


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def _sensor(fake, clock=None):
    return co2.SCD40(link=fake, clock=clock or Clock(), sleep=lambda s: None)


def test_crc_matches_datasheet_example():
    assert co2.crc8(b"\xbe\xef") == 0x92   # Sensirion's example
    assert co2.words(b"\xbe\xef\x92") == [0xBEEF]


def test_reads_co2_temperature_humidity():
    fake = FakeSensor()
    s = _sensor(fake)
    with redirect_stdout(io.StringIO()):
        r = s.read()
    assert fake.measuring
    assert r["co2_ppm"] == 812 and r["co2_band"] == "normal"
    assert abs(r["co2_temperature_c"] - 25.0) < 0.1      # 26214 -> 25 C
    assert abs(r["co2_temperature_f"] - 77.0) < 0.2
    assert abs(r["co2_humidity"] - 60.0) < 0.1           # 39321 -> 60 %


def test_missing_sensor_gives_none_and_retries_later():
    fake = FakeSensor(present=False)
    clock = Clock()
    s = _sensor(fake, clock)
    out = io.StringIO()
    with redirect_stdout(out):
        r = s.read()
        assert all(v is None for v in r.values()) and set(r) == set(co2.KEYS)
        s.read()   # no second complaint, no retry yet
    assert out.getvalue().count("not found") == 1
    fake.present = True
    clock.t += 10
    with redirect_stdout(io.StringIO()):
        assert s.read()["co2_ppm"] is None     # still waiting for the retry time
    clock.t += co2.RETRY_SECONDS
    with redirect_stdout(io.StringIO()):
        assert s.read()["co2_ppm"] == 812      # plugged in later: found


def test_unplugged_mid_run_then_stale_values_dropped():
    fake = FakeSensor()
    clock = Clock()
    s = _sensor(fake, clock)
    with redirect_stdout(io.StringIO()):
        assert s.read()["co2_ppm"] == 812
        fake.present = False
        clock.t += 10
        assert s.read()["co2_ppm"] == 812      # last good one, still fresh
        clock.t += co2.STALE_SECONDS + 1
        assert s.read()["co2_ppm"] is None     # too old: nothing rather than old numbers


def test_bad_crc_keeps_last_good_reading():
    fake = FakeSensor()
    s = _sensor(fake)
    with redirect_stdout(io.StringIO()):
        s.read()
        fake.garble, fake.ppm = True, 5000
        assert s.read()["co2_ppm"] == 812


def test_not_ready_and_zero_ppm_ignored():
    fake = FakeSensor()
    fake.ready = False
    s = _sensor(fake)
    with redirect_stdout(io.StringIO()):
        assert s.read()["co2_ppm"] is None
        fake.ready, fake.ppm = True, 0
        assert s.read()["co2_ppm"] is None


def test_pressure_sent_once_and_only_when_sane():
    fake = FakeSensor()
    s = _sensor(fake)
    with redirect_stdout(io.StringIO()):
        s.read()
    s.set_pressure(1012.4)
    s.set_pressure(1012.2)     # same hPa: not sent again
    s.set_pressure(5.0)        # nonsense: ignored
    sent = [w for w in fake.writes if (w[0] << 8 | w[1]) == co2.AMBIENT_PRESSURE]
    assert len(sent) == 1 and co2.words(sent[0][2:]) == [1012]


def test_bands():
    assert co2.band(None) is None
    assert co2.band(300) == "low"
    assert co2.band(420) == "normal"
    assert co2.band(2000) == "high"


def test_read_co2_metrics_never_raises():
    class Broken:
        def set_pressure(self, hpa):
            raise RuntimeError("boom")
    co2._sensor = Broken()
    with redirect_stdout(io.StringIO()):
        r = co2.read_co2_metrics(1000)
    assert r == co2.empty()
    co2._sensor = None


def test_log_and_login_screen_show_co2():
    p = os.path.join(tempfile.mkdtemp(), "greenhouse_log.csv")
    metrics = {"air_temperature_f": 70.0, "soil_moisture_band": "moderate",
               "co2_ppm": 640, "co2_temperature_f": 71.2, "co2_humidity": 58.0}
    metric_logger.append_metrics_csv(p, metrics)
    row = gs.latest_reading(p)
    line = gs.co2_line(row)
    assert "640 ppm" in line and "normal" in line and "58% humidity" in line
    assert gs.co2_line(gs.latest_reading(p) | {"co2_ppm": ""}) is None   # no sensor: no line


def test_old_log_is_moved_aside_not_mixed():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "greenhouse_log.csv")
    old_header = metric_logger.FIELDNAMES[:10]
    with open(p, "w") as f:
        f.write(",".join(old_header) + "\n" + ",".join(["2026-11-20T10:00:00"] + ["1"] * 9) + "\n")
    with redirect_stdout(io.StringIO()):
        metric_logger.append_metrics_csv(p, {"co2_ppm": 700})
    files = sorted(os.listdir(d))
    assert len(files) == 2 and any(f.startswith("greenhouse_log-") for f in files)
    with open(p) as f:
        assert f.readline().strip().split(",") == metric_logger.FIELDNAMES
    assert gs.latest_reading(p)["co2_ppm"] == "700"
    metric_logger.append_metrics_csv(p, {"co2_ppm": 710})   # same header now: appended
    assert len(os.listdir(d)) == 2


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
