from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Mapping, Any


def post_to_chatty(metrics: Mapping[str, Any]) -> bool:
    """
    Sends a plain-text message to Chatty's /chat endpoint.

    Environment variables:
      - CHATTY_WEBHOOK_URL
      - CHATTY_WEBHOOK_TOKEN
    """
    url = os.getenv("CHATTY_WEBHOOK_URL", "").strip()
    token = os.getenv("CHATTY_WEBHOOK_TOKEN", "").strip()

    if not url or not token:
        return False

    metrics_dict = dict(metrics)

    message = metrics_dict.get("alert_message")
    if not message:
        soil_pct = metrics_dict.get("soil_moisture_percent")
        soil_band = metrics_dict.get("soil_moisture_band")
        air_temp_f = metrics_dict.get("air_temperature_f")
        message = (
            f"Greenhouse status update: soil is {soil_band} at {soil_pct}%. "
            f"Air temperature is {air_temp_f} F."
        )

    payload = {
        "text": message
    }

    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "x-chatty-token": token,
    }

    request = urllib.request.Request(
        url=url,
        data=data,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"Chatty webhook failed: {exc}")
        return False
