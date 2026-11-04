"""Check in with Chatty over MQTT (the node network).

The greenhouse node joins the same network as the rain node. Once a minute
it posts a heartbeat and its latest readings to Chatty's MQTT broker:

    chatty/nodes/greenhouse/status  {"state": "online", "every": 60, "ts": ..., "title": "Greenhouse node"}
    chatty/nodes/greenhouse/data    {"air_temperature_f": ..., "soil_moisture_percent": ...,
                                     "soil_moisture_band": ..., ..., "ts": ...}

Readings also go out right away when the soil band changes (say, moist to
dry). Both topics are "retained", so anything that connects later (Chatty
after a restart, the word clock) gets the latest right away. If this Pi
drops off WiFi, loses power, or main.py stops, the broker posts
{"state": "offline"} for it (the "last will"), and Chatty shows
"Greenhouse node went quiet".

This runs as a background thread inside main.py. If the MQTT library is
missing or the broker can't be reached, the rest of the node (sensors,
LCD, web dashboard, CSV log) carries on as before.

Settings (environment variables):
    MQTT_HOST   broker address (default chatty-node.local, Chatty's Pi)
    MQTT_PORT   default 1883
    NODE_NAME   default "greenhouse"
    GREENHOUSE_MQTT=0   turn this off

Needs paho-mqtt. In the greenhouse-env venv: pip install paho-mqtt
"""
from __future__ import annotations

import json
import os
import socket
import threading
import time
from typing import Any, Callable

ENABLED = os.getenv("GREENHOUSE_MQTT", "1") != "0"
HOST = os.getenv("MQTT_HOST", "chatty-node.local").strip()
PORT = int(os.getenv("MQTT_PORT", "1883"))
NAME = os.getenv("NODE_NAME", "greenhouse").strip() or "greenhouse"
TITLE = "Greenhouse node"
EVERY = 60    # heartbeat and readings, seconds
POLL = 10     # how often to look for a soil band change, seconds

STATUS = f"chatty/nodes/{NAME}/status"
DATA = f"chatty/nodes/{NAME}/data"

MetricsProvider = Callable[[], dict]


def status_payload(state: str = "online") -> str:
    return json.dumps({"state": state, "every": EVERY, "ts": int(time.time()),
                       "title": TITLE, "host": socket.gethostname()})


def data_payload(metrics: dict[str, Any]) -> str | None:
    """The readings as JSON, or None before the first sensor loop has run."""
    readings = {k: v for k, v in metrics.items() if v is not None}
    if not readings:
        return None
    readings["ts"] = int(time.time())
    return json.dumps(readings)


class CheckIn:
    def __init__(self, metrics_provider: MetricsProvider):
        self.metrics_provider = metrics_provider
        self.client = None
        self.connected = False

    def _on_connect(self, client, userdata, flags, *rest):
        self.connected = True
        print(f"Node network: connected to {HOST}:{PORT}", flush=True)
        client.publish(STATUS, status_payload(), qos=1, retain=True)
        self._publish_data()

    def _on_disconnect(self, *args):
        if self.connected:
            print("Node network: lost the broker, retrying", flush=True)
        self.connected = False

    def _publish_data(self) -> None:
        try:
            payload = data_payload(self.metrics_provider())
        except Exception as e:
            print("Node network: couldn't read metrics:", repr(e), flush=True)
            return
        if payload and self.client is not None:
            self.client.publish(DATA, payload, qos=1, retain=True)

    def _make_client(self, mqtt):
        cid = f"{NAME}-{socket.gethostname()}"
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=cid)
        except AttributeError:  # paho-mqtt 1.x
            client = mqtt.Client(client_id=cid)
        client.will_set(STATUS, json.dumps({"state": "offline"}), qos=1, retain=True)
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.reconnect_delay_set(min_delay=2, max_delay=60)
        return client

    def _loop(self) -> None:
        last_beat = 0.0
        last_band = None
        while True:
            now = time.monotonic()
            try:
                band = self.metrics_provider().get("soil_moisture_band")
            except Exception:
                band = None
            beat = now - last_beat >= EVERY
            if self.connected and (beat or band != last_band):
                if beat:
                    self.client.publish(STATUS, status_payload(), qos=1, retain=True)
                    last_beat = now
                self._publish_data()
                last_band = band
            time.sleep(POLL)

    def start(self) -> bool:
        if not ENABLED:
            print("Node network: off (GREENHOUSE_MQTT=0)", flush=True)
            return False
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            print("Node network: off (paho-mqtt not installed; "
                  "run: pip install paho-mqtt)", flush=True)
            return False
        self.client = self._make_client(mqtt)
        self.client.connect_async(HOST, PORT, keepalive=30)
        self.client.loop_start()
        threading.Thread(target=self._loop, daemon=True, name="mqtt-checkin").start()
        print(f"Node network: checking in with {HOST}:{PORT} as '{NAME}'", flush=True)
        return True


def start(metrics_provider: MetricsProvider) -> CheckIn:
    """Start checking in. Never raises, so it can't take the node down."""
    checkin = CheckIn(metrics_provider)
    try:
        checkin.start()
    except Exception as e:
        print("Node network: couldn't start:", repr(e), flush=True)
    return checkin
