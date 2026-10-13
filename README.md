# Greenhouse Monitor Node (Raspberry Pi Zero 2 W)

A modular environmental monitoring system for small greenhouses and indoor plants built on a Raspberry Pi Zero 2 W.

The node measures environmental conditions and exposes them through a web dashboard, CSV logging, and optional integration with Chatty nodes or external services.

This project is designed to be:

- modular
- hackable
- lightweight
- easy to expand with additional sensors

## System architecture

```
Soil Sensor → ADS1115
                     ↓
BME280 → Raspberry Pi Zero 2W → Web Dashboard
                         ↓
                       CSV Log
                         ↓
                       Chatty
```

## Hardware wiring

| Device | Connection |
| --- | --- |
| BME280 | I2C |
| ADS1115 | I2C |
| Soil moisture sensor | ADS1115 A0 |
| DS18B20 soil temperature probe | 1-Wire |
| LCD (optional) | I2C |
| Status LEDs | GPIO 17 (green), 27 (blue), 22 (red) |

---

## Features

The system currently supports:

- Air temperature monitoring
- Air humidity monitoring
- Air pressure monitoring
- Soil moisture monitoring (capacitive probe + ADS1115 ADC)
- Soil temperature monitoring (DS18B20)
- Web dashboard for live readings and 24-hour history
- CSV logging of environmental data
- 16x2 LCD display and status LEDs
- Optional Chatty integration, including water alerts

Future upgrades may include:

- automatic watering triggers
- weather integration
- long-term environmental graphing
- greenhouse automation rules

---

## Hardware used

**Controller**

- Raspberry Pi Zero 2 W

**Sensors**

- **BME280**: temperature / humidity / pressure sensor (I2C)
- **ADS1115**: analog-to-digital converter (I2C)
- **Capacitive Soil Moisture Sensor v1.2**: analog soil probe
- **DS18B20**: waterproof soil temperature probe (1-Wire)

**Optional output**

- 16x2 LCD display with I2C backpack (the node keeps running without it)
- Status LEDs: green = monitor running, blue = web server started, red = soil is dry

---

## Software architecture

The project uses a modular Python structure.

```
greenhouse-node/
├── main.py               # monitoring loop
├── air_sensor.py         # BME280 air temperature, humidity, pressure
├── soil_moisture.py      # ADS1115 soil moisture
├── soil_temperature.py   # DS18B20 soil temperature
├── metric_logger.py      # CSV logging
├── web_posting.py        # Flask dashboard and API
├── chatty_talker.py      # Chatty webhook
├── lcd_display.py        # 16x2 LCD
├── led_status.py         # status LEDs
├── install_service.sh    # install as a systemd service
├── restart_web.sh        # restart the monitor
└── greenhouse_log.csv    # created at runtime
```

### Module responsibilities

**main.py**

Coordinates the system and runs the monitoring loop. Handles:

- sensor readings
- logging
- web dashboard updates
- LCD and LED updates
- Chatty communication and water alerts

A failed sensor read is reported as missing for that cycle instead of stopping the monitor.

**air_sensor.py**

Reads air temperature, relative humidity and barometric pressure from the BME280 in a single sample, and converts Celsius → Fahrenheit.

**soil_moisture.py**

Reads soil probe voltage using the ADS1115 analog converter. Converts raw voltage into:

- soil moisture percentage
- soil moisture band classification:
  - Critically dry (< 10%)
  - Dry (< 25%)
  - Moderate (< 60%)
  - Wet

**soil_temperature.py**

Reads soil temperature from a DS18B20 probe over 1-Wire.

**metric_logger.py**

Stores environmental readings in `greenhouse_log.csv`. Columns:

```
timestamp
air_temperature_c
air_temperature_f
air_humidity
air_pressure_hpa
soil_voltage
soil_moisture_percent
soil_temperature_c
soil_temperature_f
soil_moisture_band
```

This file can later be imported into:

- Excel
- Google Sheets
- Python analysis tools
- Grafana dashboards

**web_posting.py**

Runs a lightweight Flask web server, accessible on your local network at `http://<pi_ip_address>:5000`. Displays live environmental readings and a 24-hour history.

**chatty_talker.py**

Optional integration layer that allows the greenhouse node to communicate with:

- Chatty nodes
- automation systems
- remote servers
- VPS endpoints

Configuration uses environment variables.

---

## Installation

### Install dependencies

Activate the Python virtual environment and run:

```bash
pip install -r requirements.txt
```

### Enable I2C and 1-Wire

On the Raspberry Pi run:

```bash
sudo raspi-config
```

Then enable both under **Interface Options**:

- I2C
- 1-Wire (for the DS18B20 soil temperature probe)

### Verify sensor detection

Run:

```bash
i2cdetect -y 1
```

Expected devices:

| Address | Device |
| --- | --- |
| `0x76` | BME280 |
| `0x48` | ADS1115 |
| `0x27` | LCD backpack (optional) |

The DS18B20 should appear as `/sys/bus/w1/devices/28-*`.

---

## Configuration

Optional settings are read from environment variables. The easiest way to set them is a `.env` file in the project directory (it is ignored by git):

```
CHATTY_WEBHOOK_URL=https://example.com/chat
CHATTY_WEBHOOK_TOKEN=your-chatty-token
GREENHOUSE_COMMAND_TOKEN=pick-a-long-random-string
```

Both `install_service.sh` and `restart_web.sh` load this file.

---

## Running the monitor

### As a service (recommended)

Install the monitor as a systemd service so it starts on boot and restarts automatically if it crashes:

```bash
./install_service.sh
```

Then:

```bash
sudo systemctl status greenhouse-node     # is it running?
sudo systemctl restart greenhouse-node    # restart after changes
journalctl -u greenhouse-node -f          # follow the output
```

### Manually

```bash
./restart_web.sh
```

This stops any running copy of the monitor and starts a fresh one in the foreground. If the service is installed, it restarts the service instead.

Or run it directly:

```bash
source greenhouse-env/bin/activate
python3 main.py
```

The system will:

- read sensors
- log data
- start the web dashboard
- optionally send updates to Chatty

---

## Web dashboard

Open a browser on your phone or computer:

```
http://<pi_ip>:5000
```

Example: `http://192.168.1.227:5000`

The dashboard refreshes every 10 seconds, matching the sensor read interval.

---

## API endpoints

The Greenhouse Node exposes lightweight local HTTP endpoints for monitoring and integration.

| Endpoint | Description |
| --- | --- |
| `GET /` | Dashboard |
| `GET /history` | 24-hour history page |
| `GET /status` | Current status with node identity and nested metrics |
| `GET /metrics.json` | Raw metrics JSON |
| `GET /health` | Health check |
| `POST /command` | Commands (token required, currently simulated) |

Metrics include a `timestamp` field with the time of the latest reading.

### Health check

The `/health` endpoint reports:

- node identity
- overall status
- ok true/false
- missing metrics
- available metrics

Example health response:

```json
{
  "node": "greenhouse-node",
  "status": "ok",
  "ok": true,
  "missing_metrics": [],
  "metrics_available": [
    "air_humidity",
    "air_pressure_hpa",
    "air_temperature_c",
    "air_temperature_f",
    "soil_moisture_band",
    "soil_moisture_percent",
    "soil_temperature_c",
    "soil_temperature_f",
    "soil_voltage",
    "timestamp"
  ]
}
```

### Commands

Body: `{"action": "water_on"}` or `{"action": "water_off"}`

Commands must include the header `x-greenhouse-token` matching the `GREENHOUSE_COMMAND_TOKEN` environment variable. If `GREENHOUSE_COMMAND_TOKEN` is not set, all commands are refused.

```bash
curl -X POST http://<pi_ip>:5000/command \
  -H "Content-Type: application/json" \
  -H "x-greenhouse-token: $GREENHOUSE_COMMAND_TOKEN" \
  -d '{"action": "water_on"}'
```

For Chatty-Node integration, `/status` is the preferred endpoint for sensor readings, while `/health` is the preferred endpoint for checking whether the node is alive and reporting complete data.

---

## Soil moisture calibration

Capacitive soil sensors require calibration. Measure two values:

- **Air reference (dry)**: sensor outside soil. Example value: `2.23 V`
- **Wet soil reference**: probe inserted in fully wet soil. Example value: `1.35 V`

Update the values in `main.py`:

```python
SOIL_AIR_VOLTAGE
SOIL_WET_VOLTAGE
```

The software converts voltage into soil moisture percentage.

---

## Logging

Environmental readings are stored in `greenhouse_log.csv`. This enables historical tracking of greenhouse conditions.

---

## Chatty integration (optional)

Set the environment variables (see [Configuration](#configuration)):

```
CHATTY_WEBHOOK_URL
CHATTY_WEBHOOK_TOKEN
```

The monitor will periodically transmit sensor metrics to the configured endpoint.

When the soil reads dry or critically dry, a water alert is sent. Alerts are limited to one every 6 hours (`WATER_ALERT_COOLDOWN_SECONDS` in `main.py`). While the soil stays dry, a reminder is sent each time the cooldown expires. A failed alert is retried on the next loop. The time of the last alert is stored in `last_water_alert.txt`, so restarting the node does not re-send it.

---

## Future development

Possible upgrades:

- automated irrigation triggers
- MQTT messaging
- historical data graphs
- weather forecast integration
- solar-powered outdoor nodes

---

## License

MIT License

Open for personal and research use.

---

## Author

Vincent Campos
Greenhouse Sensor Node Project

---

## Related projects

This node is part of the broader Chatty Node ecosystem, a distributed network of lightweight environmental sensor nodes designed to explore monitoring, automation, and experimentation.
