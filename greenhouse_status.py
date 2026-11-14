"""Print a short greenhouse-node status summary in the terminal.

Meant to run when you log in over SSH (see README), like the rain node's
rain_status.py. You can also run it any time with:

    python3 ~/projects/greenhouse-node/greenhouse_status.py

It only reads things (the CSV log, systemctl, /run/node-wifi.json, `ss`), so
it is safe to run as often as you like. Plain Python, no venv needed.

Settings (optional):
    GREENHOUSE_LOG   the CSV log to read (default greenhouse_log.csv next to
                     this file, which is where greenhouse.service writes it)
"""
from __future__ import annotations

import csv
import json
import os
import socket
import subprocess
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.getenv("GREENHOUSE_LOG", os.path.join(HERE, "greenhouse_log.csv"))
WIFI_STATUS = os.getenv("NODE_WIFI_STATUS_FILE", "/run/node-wifi.json")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

# Same column order metric_logger.py writes every row in (kept here so this
# script needs nothing from the sensor libraries).
FIELDNAMES = [
    "timestamp",
    "air_temperature_c",
    "air_temperature_f",
    "air_humidity",
    "air_pressure_hpa",
    "soil_voltage",
    "soil_moisture_percent",
    "soil_temperature_c",
    "soil_temperature_f",
    "soil_moisture_band",
]

SERVICES = [("greenhouse", "greenhouse"), ("node-wifi", "wifi"), ("tailscaled", "tailscale")]
STALE_SECONDS = 120   # main.py logs every ~15 s; older than this, it has stopped
UNPLUGGED_VOLTS = 0.1  # about 0 V means the probe is unplugged, not 100% wet

COLOR = sys.stdout.isatty()


def paint(text, code):
    return f"\033[{code}m{text}\033[0m" if COLOR else text


def dot(good):
    return paint("●", "32" if good else "31")


def get_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "no network"


def last_line(path, chunk=4096):
    """The last non-empty line of a file, read from the end (the log grows big)."""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            end = f.tell()
            data = b""
            pos = end
            while pos > 0:
                step = min(chunk, pos)
                pos -= step
                f.seek(pos)
                data = f.read(step) + data
                lines = [x for x in data.splitlines() if x.strip()]
                if len(lines) >= 2 or (pos == 0 and lines):
                    return lines[-1].decode("utf-8", "replace")
    except OSError:
        return None
    return None


def first_line(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.readline().strip()
    except OSError:
        return None


def latest_reading(path=LOG_PATH):
    """The newest row of the CSV log as a dict, or None."""
    line = last_line(path)
    if not line:
        return None
    row = next(csv.reader([line]), [])
    if not row or row[0] == "timestamp":
        return None
    if len(row) == len(FIELDNAMES):
        names = FIELDNAMES
    else:  # an older log with a different set of columns: trust its header
        header = first_line(path)
        names = next(csv.reader([header]), []) if header else []
        if len(names) != len(row):
            return None
    return dict(zip(names, row))


def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def ago(seconds):
    minutes = int(seconds // 60)
    if seconds < 60:
        return f"{int(seconds)} s ago"
    if minutes < 60:
        return f"{minutes} min ago"
    hours, minutes = divmod(minutes, 60)
    if hours < 48:
        return f"{hours} h {minutes} min ago"
    return f"{hours // 24} days ago"


def soil_line(row):
    band = (row.get("soil_moisture_band") or "").strip() or "unknown"
    pct = num(row.get("soil_moisture_percent"))
    volts = num(row.get("soil_voltage"))
    if volts is not None and volts < UNPLUGGED_VOLTS:
        return paint("probe unplugged?", "33") + f"  ({volts:.2f} V)"
    color = {"dry": "31", "critically dry": "31", "moderate": "33", "wet": "36"}.get(band.lower(), "0")
    parts = []
    if pct is not None:
        parts.append(f"{pct:.0f}%")
    if volts is not None:
        parts.append(f"{volts:.2f} V")
    extra = f"  ({', '.join(parts)})" if parts else ""
    return paint(band, color) + extra


def air_line(row):
    f = num(row.get("air_temperature_f"))
    c = num(row.get("air_temperature_c"))
    rh = num(row.get("air_humidity"))
    hpa = num(row.get("air_pressure_hpa"))
    bits = []
    if f is not None:
        bits.append(f"{f:.1f} F" + (f" ({c:.1f} C)" if c is not None else ""))
    if rh is not None:
        bits.append(f"{rh:.0f}% humidity")
    if hpa is not None:
        bits.append(f"{hpa:.0f} hPa")
    return "   ".join(bits) or "no reading"


def reading_age(row, now=None):
    try:
        ts = datetime.fromisoformat(row.get("timestamp", ""))
    except ValueError:
        return None, None
    now = now or datetime.now()
    return (now - ts).total_seconds(), ts


def service_state(name):
    try:
        result = subprocess.run(["systemctl", "is-active", name],
                                capture_output=True, text=True, timeout=5)
        return result.stdout.strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def mqtt_peer():
    """Chatty's address if the node holds an open MQTT link to her, else None.

    The MQTT link lives inside greenhouse.service, so instead of asking the
    service we look for an open connection to port 1883 (no root needed)."""
    try:
        out = subprocess.run(["ss", "-Htn", "state", "established",
                              f"( dport = :{MQTT_PORT} )"],
                             capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in out.splitlines():
        cols = line.split()
        if len(cols) >= 4:
            peer = cols[-1]
            return peer.rsplit(":", 1)[0].strip("[]")
    return None


def wifi_line():
    try:
        with open(WIFI_STATUS) as f:
            st = json.load(f)
    except (OSError, ValueError):
        st = None
    if st:
        ssid = st.get("ssid") or "no WiFi"
        sig = st.get("signal")
        sig_txt = f" {sig}%" if isinstance(sig, (int, float)) else ""
        weak = isinstance(sig, (int, float)) and sig < 40
        net = "internet ok" if st.get("online") else "no internet"
        return f"{dot(st.get('online') and not weak)} {ssid}{sig_txt}  ({net})"
    try:  # keeper not installed: at least name the network
        ssid = subprocess.run(["iwgetid", "-r"], capture_output=True,
                              text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        ssid = ""
    return f"{dot(bool(ssid))} {ssid or 'unknown'}"


def pi_line():
    bits = []
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            temp = int(f.read().strip()) / 1000
        bits.append(paint(f"{temp:.0f} C", "31" if temp >= 75 else "0"))
    except (OSError, ValueError):
        pass
    try:
        with open("/proc/uptime") as f:
            up = float(f.read().split()[0])
        days, rest = divmod(int(up), 86400)
        hours = rest // 3600
        bits.append(f"up {days} d {hours} h" if days else f"up {hours} h {rest % 3600 // 60} min")
    except (OSError, ValueError, IndexError):
        pass
    return "   ".join(bits)


def main():
    print(paint(f" GREENHOUSE  {socket.gethostname()} @ {get_ip()} ", "30;42"))

    row = latest_reading()
    if row:
        print(f"  Soil:      {soil_line(row)}")
        soil_f = num(row.get("soil_temperature_f"))
        if soil_f is not None:
            print(f"  Soil temp: {soil_f:.1f} F")
        print(f"  Air:       {air_line(row)}")
        age, ts = reading_age(row)
        if age is not None:
            when = f"{ago(max(age, 0))} ({ts:%a %H:%M})"
            if age > STALE_SECONDS:
                when = paint(when + "  readings stopped?", "31")
            print(f"  Reading:   {when}")
    else:
        print("  No readings logged yet.")

    states = []
    for unit, label in SERVICES:
        state = service_state(unit)
        if label == "tailscale" and state in ("inactive", "unknown"):
            continue  # not installed or not used: leave it out
        states.append(f"{dot(state == 'active')} {label} {state}")
    peer = mqtt_peer()
    if peer:
        via = "tailscale" if peer.startswith("100.") else "lan"
        states.append(f"{dot(True)} mqtt {via}")
    else:
        states.append(f"{dot(False)} mqtt not linked")
    print("  Services:  " + "   ".join(states))
    print(f"  WiFi:      {wifi_line()}")
    pi = pi_line()
    if pi:
        print(f"  Pi:        {pi}")


if __name__ == "__main__":
    main()
