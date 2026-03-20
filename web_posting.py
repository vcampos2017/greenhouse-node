from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from flask import Flask, jsonify

MetricsProvider = Callable[[], dict]


def _read_recent_history(log_path: Path, hours: int = 24) -> list[dict]:
    if not log_path.exists():
        return []

    cutoff = datetime.now() - timedelta(hours=hours)
    rows: list[dict] = []

    with log_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts_raw = row.get("timestamp")
            if not ts_raw:
                continue
            try:
                ts = datetime.fromisoformat(ts_raw)
            except ValueError:
                continue
            if ts >= cutoff:
                row["_parsed_timestamp"] = ts
                rows.append(row)

    rows.sort(key=lambda r: r["_parsed_timestamp"])
    return rows


def _safe_float(value: str | None) -> float | None:
    if value in (None, "", "n/a"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_timestamp(value: str | None) -> str:
    if not value:
        return "n/a"
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%Y-%m-%d %I:%M:%S %p")
    except ValueError:
        return value


def _build_history_rows(rows: list[dict]) -> str:
    if not rows:
        return "<tr><td colspan='6'>No readings found for the last 24 hours.</td></tr>"

    rendered: list[str] = []
    for row in reversed(rows[-200:]):
        rendered.append(
            f"""
            <tr>
                <td>{_format_timestamp(row.get("timestamp"))}</td>
                <td>{row.get("air_temperature_f", "n/a")} °F</td>
                <td>{row.get("air_humidity", "n/a")} %</td>
                <td>{row.get("soil_moisture_percent", "n/a")} %</td>
                <td>{row.get("soil_temperature_f", "n/a")} °F</td>
                <td>{row.get("soil_moisture_band", "n/a")}</td>
            </tr>
            """
        )
    return "".join(rendered)


def _build_summary(rows: list[dict]) -> dict:
    if not rows:
        return {
            "count": 0,
            "air_temp_min": "n/a",
            "air_temp_max": "n/a",
            "soil_temp_min": "n/a",
            "soil_temp_max": "n/a",
            "soil_moisture_min": "n/a",
            "soil_moisture_max": "n/a",
        }

    air_temps = [_safe_float(r.get("air_temperature_f")) for r in rows]
    soil_temps = [_safe_float(r.get("soil_temperature_f")) for r in rows]
    soil_moisture = [_safe_float(r.get("soil_moisture_percent")) for r in rows]

    air_temps = [v for v in air_temps if v is not None]
    soil_temps = [v for v in soil_temps if v is not None]
    soil_moisture = [v for v in soil_moisture if v is not None]

    def fmt_min(values: list[float]) -> str:
        return f"{min(values):.2f}" if values else "n/a"

    def fmt_max(values: list[float]) -> str:
        return f"{max(values):.2f}" if values else "n/a"

    return {
        "count": len(rows),
        "air_temp_min": fmt_min(air_temps),
        "air_temp_max": fmt_max(air_temps),
        "soil_temp_min": fmt_min(soil_temps),
        "soil_temp_max": fmt_max(soil_temps),
        "soil_moisture_min": fmt_min(soil_moisture),
        "soil_moisture_max": fmt_max(soil_moisture),
    }


def create_app(metrics_provider: MetricsProvider, log_path: str = "greenhouse_log.csv") -> Flask:
    app = Flask(__name__)
    log_file = Path(log_path)

    @app.route("/")
    def index() -> str:
        metrics = metrics_provider()
        history = _read_recent_history(log_file, hours=24)
        latest_timestamp = history[-1].get("timestamp") if history else None

        return f"""
        <!doctype html>
        <html>
        <head>
            <meta http-equiv="refresh" content="10">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Greenhouse Monitor</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 24px;
                    background: #f6f8f7;
                    color: #1f2a1f;
                }}
                .card {{
                    background: white;
                    border-radius: 14px;
                    padding: 20px;
                    margin-bottom: 16px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                }}
                .reading {{
                    font-size: 1.2rem;
                    margin: 10px 0;
                }}
                .label {{
                    font-weight: bold;
                }}
                a.button {{
                    display: inline-block;
                    margin-top: 12px;
                    padding: 10px 14px;
                    border-radius: 10px;
                    background: #2f6f57;
                    color: white;
                    text-decoration: none;
                    font-weight: bold;
                }}
                .subtle {{
                    color: #4f5f55;
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Greenhouse Monitor</h1>
                <p>Auto-refreshes every 10 seconds</p>
                <p class="subtle"><strong>Last Updated:</strong> {_format_timestamp(latest_timestamp)}</p>
                <a class="button" href="/history">View 24-Hour History</a>
            </div>

            <div class="card">
                <div class="reading"><span class="label">Air Temperature:</span> {metrics.get("air_temperature_f", "n/a")} °F</div>
                <div class="reading"><span class="label">Air Humidity:</span> {metrics.get("air_humidity", "n/a")} %</div>
                <div class="reading"><span class="label">Air Pressure:</span> {metrics.get("air_pressure_hpa", "n/a")} hPa</div>
                <div class="reading"><span class="label">Soil Voltage:</span> {metrics.get("soil_voltage", "n/a")} V</div>
                <div class="reading"><span class="label">Soil Moisture:</span> {metrics.get("soil_moisture_percent", "n/a")} %</div>
                <div class="reading"><span class="label">Soil Temperature:</span> {metrics.get("soil_temperature_f", "n/a")} °F</div>
                <div class="reading"><span class="label">Soil Status:</span> {metrics.get("soil_moisture_band", "n/a")}</div>
            </div>
        </body>
        </html>
        """

    @app.route("/history")
    def history() -> str:
        rows = _read_recent_history(log_file, hours=24)
        summary = _build_summary(rows)

        return f"""
        <!doctype html>
        <html>
        <head>
            <meta http-equiv="refresh" content="30">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Greenhouse Monitor - 24 Hour History</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 24px;
                    background: #f6f8f7;
                    color: #1f2a1f;
                }}
                .card {{
                    background: white;
                    border-radius: 14px;
                    padding: 20px;
                    margin-bottom: 16px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    font-size: 0.95rem;
                }}
                th, td {{
                    text-align: left;
                    padding: 10px;
                    border-bottom: 1px solid #dfe7e2;
                }}
                th {{
                    background: #eef4f0;
                }}
                a.button {{
                    display: inline-block;
                    margin-top: 12px;
                    padding: 10px 14px;
                    border-radius: 10px;
                    background: #2f6f57;
                    color: white;
                    text-decoration: none;
                    font-weight: bold;
                }}
                .grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                    gap: 12px;
                }}
                .mini {{
                    background: #f8fbf9;
                    border-radius: 10px;
                    padding: 12px;
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <h1>24-Hour History</h1>
                <p>Recent readings from the last 24 hours.</p>
                <a class="button" href="/">Back to Dashboard</a>
            </div>

            <div class="card">
                <div class="grid">
                    <div class="mini"><strong>Readings:</strong><br>{summary["count"]}</div>
                    <div class="mini"><strong>Air Temp Range:</strong><br>{summary["air_temp_min"]} °F to {summary["air_temp_max"]} °F</div>
                    <div class="mini"><strong>Soil Temp Range:</strong><br>{summary["soil_temp_min"]} °F to {summary["soil_temp_max"]} °F</div>
                    <div class="mini"><strong>Soil Moisture Range:</strong><br>{summary["soil_moisture_min"]} % to {summary["soil_moisture_max"]} %</div>
                </div>
            </div>

            <div class="card">
                <table>
                    <thead>
                        <tr>
                            <th>Timestamp</th>
                            <th>Air Temp</th>
                            <th>Humidity</th>
                            <th>Soil Moisture</th>
                            <th>Soil Temp</th>
                            <th>Soil Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {_build_history_rows(rows)}
                    </tbody>
                </table>
            </div>
        </body>
        </html>
        """

    @app.route("/metrics.json")
    def metrics_json():
        return jsonify(metrics_provider())

    @app.route("/health")
    def health():
        return {"ok": True}

    return app