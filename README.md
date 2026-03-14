Greenhouse Monitor Node (Raspberry Pi Zero 2 W)

A modular environmental monitoring system for small greenhouses and indoor plants built on a Raspberry Pi Zero 2 W.

The node measures environmental conditions and exposes them through a web dashboard, CSV logging, and optional integration with Chatty nodes or external services.

This project is designed to be:
	•	modular
	•	hackable
	•	lightweight
	•	easy to expand with additional sensors

System architecture diagram

Soil Sensor → ADS1115
                     ↓
BME280 → Raspberry Pi Zero 2W → Web Dashboard
                         ↓
                       CSV Log
                         ↓
                       Chatty
                       
                       
Hardware wiring diagram

Pi GPIO pins
BME280 (I2C)
ADS1115 (I2C)
Soil sensor (A0)
LCD (I2C)


⸻

Features

The system currently supports:
	•	Air temperature monitoring
	•	Air humidity monitoring
	•	Air pressure monitoring
	•	Soil moisture monitoring (capacitive probe + ADS1115 ADC)
	•	Web dashboard for live readings
	•	CSV logging of environmental data
	•	Optional Chatty integration endpoint

Future upgrades may include:
	•	automatic watering triggers
	•	weather integration
	•	long-term environmental graphing
	•	greenhouse automation rules

⸻

Hardware Used

Controller
Raspberry Pi Zero 2 W

Sensors

BME280
Temperature / Humidity / Pressure sensor (I2C)

ADS1115
Analog-to-digital converter (I2C)

Capacitive Soil Moisture Sensor v1.2
Analog soil probe

Optional Output

16x2 LCD display with I2C backpack

⸻

Software Architecture

The project uses a modular Python structure.

greenhouse-node/

main.py
air_temperature.py
air_humidity.py
soil_moisture.py
metric_logger.py
web_posting.py
chatty_talker.py
greenhouse_log.csv

⸻

Module Responsibilities

main.py

Coordinates the system and runs the monitoring loop.

Handles:
	•	sensor readings
	•	logging
	•	web dashboard updates
	•	Chatty communication

⸻

air_temperature.py

Reads air temperature from the BME280 and converts:

Celsius → Fahrenheit

⸻

air_humidity.py

Reads additional BME280 metrics:
	•	relative humidity
	•	barometric pressure

⸻

soil_moisture.py

Reads soil probe voltage using the ADS1115 analog converter.

Converts raw voltage into:
	•	soil moisture percentage
	•	soil moisture band classification

Dry
Moderate
Wet

⸻

metric_logger.py

Stores environmental readings in:

greenhouse_log.csv

Example log format:

timestamp
air_temperature_c
air_temperature_f
air_humidity
air_pressure_hpa
soil_voltage
soil_moisture_percent
soil_moisture_band

This file can later be imported into:
	•	Excel
	•	Google Sheets
	•	Python analysis tools
	•	Grafana dashboards

⸻

web_posting.py

Runs a lightweight Flask web server.

Accessible on your local network:

http://<pi_ip_address>:5000

Displays live environmental readings.

⸻

chatty_talker.py

Optional integration layer that allows the greenhouse node to communicate with:
	•	Chatty nodes
	•	automation systems
	•	remote servers
	•	VPS endpoints

Configuration uses environment variables.

⸻

Installation

Install Dependencies

Activate the Python virtual environment and run:

pip install flask smbus2 RPi.bme280 adafruit-blinka adafruit-circuitpython-ads1x15

⸻

Enable I2C

On the Raspberry Pi run:

sudo raspi-config

Navigate to:

Interface Options
I2C
Enable

⸻

Verify Sensor Detection

Run:

i2cdetect -y 1

Expected devices:

0x76  BME280
0x48  ADS1115
0x27  LCD backpack (optional)

⸻

Running the Monitor

Activate the Python environment:

source greenhouse-env/bin/activate

Start the monitor:

python3 main.py

The system will:
	•	read sensors
	•	log data
	•	start the web dashboard
	•	optionally send updates to Chatty

⸻

Web Dashboard

Open a browser on your phone or computer:

http://<pi_ip>:5000

Example:

http://192.168.1.227:5000

The dashboard refreshes every 10 seconds.

⸻

Soil Moisture Calibration

Capacitive soil sensors require calibration.

Measure two values.

Air reference (dry)

Sensor outside soil.

Example value:

2.23 V

Wet soil reference

Probe inserted in fully wet soil.

Example value:

1.35 V

Update the values in main.py:

SOIL_AIR_VOLTAGE
SOIL_WET_VOLTAGE

The software converts voltage into soil moisture percentage.

⸻

Logging

Environmental readings are stored in:

greenhouse_log.csv

This enables historical tracking of greenhouse conditions.

⸻

Chatty Integration (Optional)

Set environment variables:

CHATTTY_WEBHOOK_URL
CHATTTY_WEBHOOK_TOKEN

The monitor will periodically transmit sensor metrics to the configured endpoint.

⸻

Future Development

Possible upgrades:
	•	automated irrigation triggers
	•	MQTT messaging
	•	historical data graphs
	•	LCD display integration
	•	weather forecast integration
	•	solar-powered outdoor nodes

⸻

License

MIT License

Open for personal and research use.

⸻

Author

Vincent Campos
Greenhouse Sensor Node Project

⸻

Related Projects

This node is part of the broader Chatty Node ecosystem, a distributed network of lightweight environmental sensor nodes designed to explore monitoring, automation, and experimentation.
