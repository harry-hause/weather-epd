# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Python app that renders aviation weather data onto a Waveshare 7.5" e-ink display (800×480, 1-bit black/white) connected to a Raspberry Pi. Data is sourced from the NWS grid forecast API and the FAA aviation weather METAR API, targeting Worcester Regional Airport (KORH, NWS office BOX).

## Running

```bash
# Activate the venv first
source .venv/bin/activate

# Dev mode — renders to weather_preview.png instead of the e-ink display
python main.py --dev

# Production (Raspberry Pi only, requires sudo for SPI/GPIO)
sudo python main.py
```

`display/scratch.py` is an older prototype; `main.py` is the canonical entry point.

To exercise the data layer independently:
```bash
python -m data.nws_wx_wrapper   # prints live METAR + NWS forecast to stdout
```

## Installation

```bash
pip install -r requirements.txt
```

Note: `gpiozero`, `RPi.GPIO`, and `spidev` only work on Raspberry Pi. On macOS/Linux dev machines, importing `display.epd_interface` or `display.epd_config` will fail — this is why `--dev` mode lazy-imports the EPD driver only when needed.

## Architecture

### Two-mode design

`DisplayManager.__init__` checks `dev_mode`:
- `dev_mode=True` (default): skips EPD hardware init; `render_display()` saves a PNG preview via `save_display_preview()`
- `dev_mode=False`: initializes the Waveshare EPD via SPI, pushes the buffer to the display

### Rendering pipeline (`display/display_manager.py`)

All rendering builds a single `Image.new('1', (800, 480), 255)` PIL image, then pushes it to the display or saves as PNG. Layout zones (y-coordinates are approximate):

| Zone | Y range | Description |
|------|---------|-------------|
| Header | 0–210 | Station ID, timestamp, current icon, 3×3 summary grid |
| Hourly grid | 210–375 | 13 columns: hour, icon, flight category, ceiling, wind dir/speed, temp, precip |
| Daily grid | 375–460 | 10 columns: day label, icon, temp/dewpoint |
| Flight category bar | 460–480 | Solid/hatched/clear band for IFR/MVFR/VFR |

### Hardware layer (`display/epd_interface.py`, `display/epd_config.py`)

Waveshare's EPD driver communicates over SPI with GPIO control pins (RST=17, DC=25, CS=8, BUSY=24, PWR=18). `epd_config.py` wraps `gpiozero` and `spidev`. The `EPD` class in `epd_interface.py` handles init sequences, buffer conversion (PIL 0=black → EPD 1=black, inverted via XOR), and display commands.

### Data layer (`data/nws_wx_wrapper.py`)

`NWSWeatherWrapper` fetches from two APIs:
- `api.weather.gov` — grid forecast (temperature, windSpeed, windGust, windDirection, ceilingHeight, visibility) as time-series with ISO 8601 duration intervals, flattened to hourly Pandas DataFrames via `weather_data_to_dataframe()`
- `aviationweather.gov` — METAR JSON for current observation

All units are converted on ingestion: Celsius→Fahrenheit, km/h→knots, meters→feet/miles.

**The data layer is not yet wired into `DisplayManager`** — all `draw_*` methods currently use mock/hardcoded data.

### Assets

Icons are BMP files in `display/pic/` (not tracked in git). Source SVGs: https://github.com/erikflowers/weather-icons. Convert to BMP at 500 DPI pixel density. Font is `Font.ttc` (also in `display/pic/`), loaded at sizes 12, 18, 24, 35px.
