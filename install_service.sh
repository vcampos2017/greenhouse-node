#!/bin/bash
# Installs greenhouse-node as a systemd service that starts on boot and
# restarts automatically if it crashes. Run it from the Pi: ./install_service.sh

set -euo pipefail

SERVICE_NAME="greenhouse-node"
PROJECT_DIR="$(dirname "$(readlink -f "$0")")"
RUN_USER="${SUDO_USER:-$USER}"
PYTHON="$PROJECT_DIR/greenhouse-env/bin/python"

if [ ! -x "$PYTHON" ]; then
    echo "❌ Virtual environment not found at $PROJECT_DIR/greenhouse-env" >&2
    exit 1
fi

echo "📝 Writing /etc/systemd/system/$SERVICE_NAME.service (user: $RUN_USER, dir: $PROJECT_DIR)"
sudo tee "/etc/systemd/system/$SERVICE_NAME.service" > /dev/null <<EOF
[Unit]
Description=Greenhouse monitor node
Wants=network-online.target
After=network-online.target

[Service]
User=$RUN_USER
WorkingDirectory=$PROJECT_DIR
# Optional: CHATTY_WEBHOOK_URL, CHATTY_WEBHOOK_TOKEN, GREENHOUSE_COMMAND_TOKEN
EnvironmentFile=-$PROJECT_DIR/.env
Environment=PYTHONUNBUFFERED=1
ExecStart=$PYTHON main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"

echo "✅ Installed. Useful commands:"
echo "   sudo systemctl status $SERVICE_NAME"
echo "   sudo systemctl restart $SERVICE_NAME"
echo "   journalctl -u $SERVICE_NAME -f"
