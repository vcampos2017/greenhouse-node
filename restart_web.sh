#!/bin/bash

SERVICE_NAME="greenhouse-node"
PROJECT_DIR="$(dirname "$(readlink -f "$0")")"

echo "🧹 CLEAN RESTART: Greenhouse Node"

# If installed as a service (see install_service.sh), let systemd handle it
if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
    echo "🔁 Restarting $SERVICE_NAME service..."
    sudo systemctl restart "$SERVICE_NAME"
    echo "📜 Follow logs with: journalctl -u $SERVICE_NAME -f"
    exit 0
fi

# Step 1: Stop any main.py started from this project directory (not other projects)
echo "🔍 Stopping any running greenhouse app..."
for pid in $(pgrep -f "main\.py"); do
    if [ "$(readlink -f "/proc/$pid/cwd")" = "$PROJECT_DIR" ]; then
        kill "$pid"
    fi
done

# Step 2: Wait for port 5000 to free up
for _ in 1 2 3 4 5; do
    if command -v lsof > /dev/null && [ -n "$(lsof -ti :5000)" ]; then
        sleep 1
    else
        break
    fi
done

if command -v lsof > /dev/null && [ -n "$(lsof -ti :5000)" ]; then
    echo "⚠️ Port 5000 is still in use by PID(s): $(lsof -ti :5000 | tr '\n' ' ')"
    echo "   Not killing it automatically, since it may not be this app."
    exit 1
fi

# Step 3: Move to project directory
cd "$PROJECT_DIR" || exit

# Step 4: Activate environment and load optional settings from .env
echo "🐍 Activating virtual environment..."
source greenhouse-env/bin/activate
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Step 5: Start fresh instance
echo "🚀 Starting main.py..."
python main.py
