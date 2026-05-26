# Deploying weather-epd to Raspberry Pi

## Prerequisites

### On your Mac
- SSH access to the Pi (`ssh pi@raspberrypi.local` works, or use the IP)
- `rsync` (pre-installed on macOS)
- SSH key set up to avoid typing a password on every deploy:
  ```bash
  ssh-copy-id pi@raspberrypi.local
  ```

### On the Pi (one-time setup)
SSH in and run the following.

**1. Enable SPI**
```bash
sudo raspi-config
# Interface Options → SPI → Enable
# Reboot when prompted
```

**2. Add pi user to hardware groups** (avoids needing sudo to access GPIO/SPI)
```bash
sudo usermod -a -G gpio,spi pi
# Log out and back in for this to take effect
```

**3. Install system dependencies**
```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv libopenjp2-7
```

> `libopenjp2-7` is required by Pillow on Pi OS.

**4. Create the app directory**
```bash
mkdir -p /home/pi/weather-epd
```

---

## Deploying

From your Mac, in the project root:

```bash
# First deploy (or any time dependencies change)
PI_HOST=pi@raspberrypi.local ./deploy.sh

# Subsequent deploys — just sync code, skip pip if deps unchanged
PI_HOST=pi@raspberrypi.local ./deploy.sh

# Deploy and restart the running service
PI_HOST=pi@raspberrypi.local ./deploy.sh --restart
```

To avoid typing the host every time, export it in your shell profile:
```bash
export PI_HOST=pi@raspberrypi.local
```

---

## Running manually on the Pi

SSH in, then:

```bash
cd /home/pi/weather-epd
.venv/bin/python main.py
```

No `sudo` needed if the `gpio`/`spi` group membership is active (see prerequisites above).

---

## Running as a systemd service (auto-start on boot)

The `weather-epd.service` file is included in the project and deployed by `deploy.sh`.

**Install and enable the service (first time):**
```bash
sudo cp /home/pi/weather-epd/weather-epd.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable weather-epd
sudo systemctl start weather-epd
```

**Common service commands:**
```bash
sudo systemctl status weather-epd       # check if running
sudo systemctl restart weather-epd      # restart after a deploy
sudo systemctl stop weather-epd         # stop
journalctl -u weather-epd -f            # stream live logs
journalctl -u weather-epd --since today # logs since midnight
```

---

## Troubleshooting

**`RuntimeError: Cannot determine SOC peripheral base address` or SPI errors**
→ SPI is not enabled. Run `sudo raspi-config` and enable it under Interface Options.

**`PermissionError: [Errno 13]` on `/dev/spidev*` or `/dev/gpiomem`**
→ The pi user isn't in the `spi`/`gpio` groups yet. Run the `usermod` command above and log out/in.

**`ModuleNotFoundError: No module named 'RPi'`**
→ Dependencies weren't installed with `requirements-pi.txt`. Re-run `deploy.sh` or manually:
```bash
cd /home/pi/weather-epd && .venv/bin/pip install -r requirements-pi.txt
```

**Display shows nothing / stays white after first run**
→ The EPD needs a full clear cycle on first use. It can take 15–20 seconds. Check logs:
```bash
journalctl -u weather-epd -n 50
```

**Checking the Pi's IP address**
```bash
# From your Mac
ping raspberrypi.local
# or
arp -a | grep raspberry
```
