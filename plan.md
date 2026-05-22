# Implementation Plan

## 1. Icon system (`display/icons.py`, new file)

Create a module with a mapping from weather conditions → BMP filename and a `get_icon_path(condition: str) -> Path` lookup function.

**Condition sources:**
- Current obs: METAR `wxString` codes (`RA`, `SN`, `FG`, `TS`, etc.) and `shortForecast` text from NWS (`"Mostly Cloudy"`, `"Rain"`, etc.)
- Hourly/daily: NWS `shortForecast` text from the summary forecast periods

**Mapping strategy:** keyword scan on lowercased condition string → icon name. Fallback to `wi-cloud.bmp` if no match. Example:

```
thunderstorm → wi-thunderstorm.bmp
snow         → wi-snow.bmp
rain/drizzle → wi-rain.bmp
fog/mist/haze→ wi-fog.bmp
clear/sunny  → wi-day-sunny.bmp
partly cloudy→ wi-day-cloudy.bmp
cloudy       → wi-cloud.bmp
wind/breezy  → wi-strong-wind.bmp
```

Currently only `wi-cloud.bmp` exists — need to download ~8–10 additional BMPs from the
[erikflowers weather-icons repo](https://github.com/erikflowers/weather-icons/tree/master),
convert to BMP at 500 DPI, drop in `display/pic/`. The icon module logs a warning and falls
back if a file is missing so the app never crashes over a missing asset.

---

## 2. Data layer wiring

### 2a. `WeatherData` dataclass (new `data/models.py`)

A single object passed into `DisplayManager` so draw methods don't call the API directly:

```python
@dataclass
class WeatherData:
    station_id: str
    obs_time: datetime
    # current obs (from METAR)
    temp_f: float
    dewpoint_f: float
    wind_dir_deg: int
    wind_speed_kt: int
    wind_gust_kt: int | None
    visibility_sm: float
    ceiling_ft: int          # None = unlimited
    altimeter_inhg: float
    flight_category: str     # VFR/MVFR/IFR/LIFR
    wx_condition: str        # raw wxString or shortForecast for icon lookup
    # hourly forecast (DataFrame, already unit-converted)
    hourly_df: pd.DataFrame  # columns: temperature, windDirection, windSpeed, windGust, ceilingHeight, visibility
    # daily forecast
    daily_periods: list[dict]  # raw NWS period dicts
```

### 2b. `NWSWeatherWrapper.fetch_all(station_id, grid_coords) -> WeatherData`

One method that calls all three endpoints and returns the dataclass. Raises on failure so
the retry loop in `main.py` can catch and log it.

### 2c. Density altitude utility (in `data/nws_wx_wrapper.py`)

```
KORH_ELEVATION_FT = 1009
pressure_altitude = (29.92 - altimeter_inhg) * 1000 + KORH_ELEVATION_FT
isa_temp_f = 59 - (3.5 * KORH_ELEVATION_FT / 1000)
density_altitude = pressure_altitude + 118.8 * (temp_f - isa_temp_f)
```

### 2d. Thread `WeatherData` through `DisplayManager`

- `DisplayManager.__init__` no longer fetches data; it only owns display/image state.
- `DisplayManager.render_display(data: WeatherData)` calls each `draw_*` method with real values.
- Each `draw_*` method gains the fields it needs:
  - `draw_summary_grid(data: WeatherData)`
  - `draw_current_icon(condition: str)`
  - `draw_current_time(obs_time: datetime)`
  - `draw_hourly_block(x, y, w, h, hour_row: pd.Series)`
  - `draw_daily_block(x, y, w, h, period: dict)`

---

## 3. Refresh loop (`main.py`)

```python
REFRESH_INTERVAL_SECS = 600   # 10 min; e-ink refresh takes ~3s

nws = NWSWeatherWrapper()
display_manager = DisplayManager(dev_mode=dev_mode)

while True:
    try:
        data = nws.fetch_all(WORCESTER_AIRPORT_STATION, WORCESTER_GRID_COORDS)
        display_manager.render_display(data)
    except Exception as e:
        logging.error(f"Refresh failed: {e}")
    time.sleep(REFRESH_INTERVAL_SECS)
```

In dev mode, exit after one iteration rather than looping every 10 minutes.

---

## Order of work

1. Add `display/icons.py` with condition→icon map and `get_icon_path()`
2. Download and convert the ~8 missing icon BMPs into `display/pic/`
3. Add `WeatherData` dataclass in `data/models.py`
4. Add `fetch_all()` + density altitude util to `NWSWeatherWrapper`
5. Refactor `draw_summary_grid`, `draw_current_icon`, `draw_current_time` to use real data
6. Refactor `draw_hourly_block` / `draw_hourly_grid` to iterate over `hourly_df` rows
7. Refactor `draw_daily_block` / `draw_daily_grid` to use `daily_periods`
8. Wire the refresh loop into `main.py`
