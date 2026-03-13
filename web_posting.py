from __future__ import annotations

from typing import Callable
from flask import Flask, jsonify

MetricsProvider = Callable[[], dict]


def create_app(metrics_provider: MetricsProvider) -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index() -> str:
        metrics = metrics_provider()

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
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Greenhouse Monitor</h1>
                <p>Auto-refreshes every 10 seconds</p>
            </div>

            <div class="card">
                <div class="reading"><span class="label">Air Temperature:</span> {metrics.get("air_temperature_f", "n/a")} °F</div>
                <div class="reading"><span class="label">Air Humidity:</span> {metrics.get("air_humidity", "n/a")} %</div>
                <div class="reading"><span class="label">Air Pressure:</span> {metrics.get("air_pressure_hpa", "n/a")} hPa</div>
                <div class="reading"><span class="label">Soil Voltage:</span> {metrics.get("soil_voltage", "n/a")} V</div>
                <div class="reading"><span class="label">Soil Moisture:</span> {metrics.get("soil_moisture_percent", "n/a")} %</div>
                <div class="reading"><span class="label">Soil Status:</span> {metrics.get("soil_moisture_band", "n/a")}</div>
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