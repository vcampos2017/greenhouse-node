from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Mapping, Any


def post_to_chatty(metrics: Mapping[str, Any]) -> bool:
    """
    Posts a snapshot to Chatty if CHATTTY_WEBHOOK_URL or CHATTTY_WEBHOOK_TOKEN is configured.

    Environment variables:
      - CHATTTY_WEBHOOK_URL
      - CHATTTY_WEBHOOK_TOKEN (optional)
    """
    url = os.getenv("CHATTTY_WEBHOOK_URL", "").strip()
    token = os.getenv("CHATTTY_WEBHOOK_TOKEN", "").strip()

    if not url:
        return False

    payload = {
        "source": "greenhouse-pi",
        "metrics": dict(metrics),
    }

    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url=url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, urllib.error.HTTPError):
        return False