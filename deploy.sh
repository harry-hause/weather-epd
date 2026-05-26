#!/bin/bash
# Deploy weather-epd to Raspberry Pi.
# Usage:
#   ./deploy.sh                        # uses PI_HOST env var or prompts
#   PI_HOST=pi@192.168.1.42 ./deploy.sh
#   ./deploy.sh --restart              # install deps, sync service file, and restart

set -euo pipefail

REMOTE_DIR="/home/pi/weather-epd"
RESTART=false

for arg in "$@"; do
  case $arg in
    --restart) RESTART=true ;;
    *) echo "Unknown argument: $arg"; exit 1 ;;
  esac
done

PI_HOST="${PI_HOST:-pi@raspberrypi.local}"

echo "→ Deploying to $PI_HOST:$REMOTE_DIR"

# Sync project files (excludes dev artifacts and local venv)
rsync -avz --progress \
  --exclude='.venv/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='.git/' \
  --exclude='raw_data/' \
  --exclude='weather_preview.png' \
  --exclude='.claude/' \
  . "$PI_HOST:$REMOTE_DIR"

if $RESTART; then
  echo "→ Installing Python dependencies on Pi"
  ssh "$PI_HOST" bash <<EOF
set -e
cd "$REMOTE_DIR"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements-pi.txt -q
echo "Dependencies installed."
EOF

  echo "→ Installing systemd service"
  ssh "$PI_HOST" bash <<EOF
set -e
sudo cp "$REMOTE_DIR/weather-epd.service" /etc/systemd/system/weather-epd.service
sudo systemctl daemon-reload
sudo systemctl enable weather-epd
EOF

  echo "→ Restarting weather-epd service"
  ssh "$PI_HOST" "sudo systemctl restart weather-epd && sudo systemctl status weather-epd --no-pager"
fi

echo "✓ Deploy complete."
