import argparse
import logging
import time
from pathlib import Path

from data.nws_wx_wrapper import NWSWeatherWrapper, WORCESTER_AIRPORT_STATION, WORCESTER_GRID_COORDS
from display.display_manager import DisplayManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

REFRESH_INTERVAL_SECS = 600  # 10 minutes


def main(dev_mode: bool):
    print(f"--dev-mode: {dev_mode}")

    nws = NWSWeatherWrapper()
    display_manager = DisplayManager(dev_mode=dev_mode)

    raw_dir = Path("raw_data") if dev_mode else None

    while True:
        try:
            data = nws.fetch_all(WORCESTER_AIRPORT_STATION, WORCESTER_GRID_COORDS, save_raw_dir=raw_dir)
            display_manager.render_display(data)
        except Exception as e:
            logging.error("Refresh failed: %s", e)

        if dev_mode:
            break

        time.sleep(REFRESH_INTERVAL_SECS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Main application entry point")
    parser.add_argument(
        "--dev", "--dev-mode",
        dest="dev_mode",
        action="store_true",
        help="Enable development mode",
    )
    args = parser.parse_args()

    main(dev_mode=args.dev_mode)
