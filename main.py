import argparse
import logging
import time
from pathlib import Path

import requests

from data.nws_wx_wrapper import NWSWeatherWrapper, WORCESTER_AIRPORT_STATION, WORCESTER_GRID_COORDS
from display.display_manager import DisplayManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

REFRESH_INTERVAL_SECS = 600  # 10 minutes
NETWORK_RETRY_SECS = 30      # retry interval when network is unavailable
NETWORK_RETRY_MAX = 20       # give up after ~10 minutes of retries


def main(dev_mode: bool):
    logger.info("Starting weather-epd (dev_mode=%s)", dev_mode)

    nws = NWSWeatherWrapper()
    display_manager = DisplayManager(dev_mode=dev_mode)

    raw_dir = Path("raw_data") if dev_mode else None

    while True:
        logger.info("Fetching weather data")
        network_retries = 0
        while True:
            try:
                data = nws.fetch_all(WORCESTER_AIRPORT_STATION, WORCESTER_GRID_COORDS, save_raw_dir=raw_dir)
                logger.info("Fetch complete — obs time: %s, condition: %s", data.obs_time, data.wx_condition)
                logger.info("Rendering display")
                display_manager.render_display(data)
                logger.info("Display updated successfully")
                break
            except requests.exceptions.ConnectionError as e:
                network_retries += 1
                if network_retries >= NETWORK_RETRY_MAX:
                    logger.error("Network unavailable after %d retries, giving up until next cycle: %s", network_retries, e)
                    break
                logger.warning("Network error (attempt %d/%d), retrying in %ds: %s",
                               network_retries, NETWORK_RETRY_MAX, NETWORK_RETRY_SECS, e)
                time.sleep(NETWORK_RETRY_SECS)
            except Exception as e:
                logger.error("Refresh failed: %s", e, exc_info=True)
                break

        if dev_mode:
            break

        logger.info("Sleeping %ds until next refresh", REFRESH_INTERVAL_SECS)
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
