from __future__ import annotations

import json
import logging
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
import re

from data.models import WeatherData, density_altitude, KORH_ELEVATION_FT

logger = logging.getLogger(__name__)

_HPA_TO_INHG = 1 / 33.8639

WORCESTER_GRID_COORDS = "45,81"
BOSTON_FORECAST_OFFICE_ID = "BOX"
WORCESTER_AIRPORT_STATION = "KORH"


def _is_nan_safe(v) -> bool:
    import math
    try:
        return math.isnan(v)
    except (TypeError, ValueError):
        return False


def _flight_cat_from_values(ceiling_ft, visibility_sm) -> str:
    """Compute flight category from actual ceiling (ft) and visibility (sm)."""
    ceiling = float('inf') if ceiling_ft is None or _is_nan_safe(ceiling_ft) else float(ceiling_ft)
    vis = float('inf') if visibility_sm is None or _is_nan_safe(visibility_sm) else float(visibility_sm)
    if ceiling < 500 or vis < 1:
        return 'LIFR'
    if ceiling < 1000 or vis < 3:
        return 'IFR'
    if ceiling < 3000 or vis < 5:
        return 'MVFR'
    return 'VFR'


def _sky_cover_to_forecast(sky_pct) -> str:
    """Derive a shortForecast-style string from sky cover percent (grid fallback)."""
    if sky_pct is None or _is_nan_safe(sky_pct):
        return 'Unknown'
    p = float(sky_pct)
    if p <= 12:  return 'Clear'
    if p <= 25:  return 'Mostly Clear'
    if p <= 50:  return 'Partly Cloudy'
    if p <= 75:  return 'Mostly Cloudy'
    return 'Overcast'


class NWSWeatherWrapper:
    def __init__(self):
        self.metric_keys = [
            'temperature', 'dewpoint', 'relativeHumidity', 'skyCover',
            'windDirection', 'windSpeed', 'windGust',
            'ceilingHeight', 'visibility',
            'probabilityOfPrecipitation',
        ]

    def get_grid_area_forecast(self, grid_coords):
        url = f"https://api.weather.gov/gridpoints/{BOSTON_FORECAST_OFFICE_ID}/{grid_coords}"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error fetching data: {response.status_code}")

    def get_summary_area_forecast(self, grid_coords):
        url = f"https://api.weather.gov/gridpoints/{BOSTON_FORECAST_OFFICE_ID}/{grid_coords}/forecast"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error fetching data: {response.status_code}")

    def get_hourly_forecast(self, grid_coords):
        url = f"https://api.weather.gov/gridpoints/{BOSTON_FORECAST_OFFICE_ID}/{grid_coords}/forecast/hourly"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error fetching hourly forecast: {response.status_code}")

    def get_metar_observation(self, station_id):
        url = f"https://aviationweather.gov/api/data/metar?ids={station_id}&format=json"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            # API returns a list, get the first item if available
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            return data
        else:
            raise Exception(f"Error fetching METAR data: {response.status_code}")

    def get_nws_observation(self, station_id):
        url = f"https://api.weather.gov/stations/{station_id}/observations/latest"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error fetching NWS observation data: {response.status_code}")

    # Function to parse the validTime format
    def parse_valid_time(self, valid_time_str):
        # Split into start time and duration
        parts = valid_time_str.split('/')
        start_time_str = parts[0]
        duration_str = parts[1]
        
        # Parse start time
        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        
        # Parse duration using regex
        hours = 0
        days = 0
        
        # Extract days if present
        d_match = re.search(r'(\d+)D', duration_str)
        if d_match:
            days = int(d_match.group(1))
        
        # Extract hours if present
        h_match = re.search(r'(\d+)H', duration_str)
        if h_match:
            hours = int(h_match.group(1))
        
        # Handle PT1H format (special case for 1 hour)
        if duration_str == 'PT1H':
            hours = 1
        
        # Calculate end time
        end_time = start_time + timedelta(days=days, hours=hours)
        
        return start_time, end_time

    # Function to convert Celsius to Fahrenheit
    def celsius_to_fahrenheit(self, celsius):
        return (celsius * 9/5) + 32

    def kmh_to_knots(self, kmh):
        return int(kmh * 0.539957)

    # Function to convert meters to feet
    def meters_to_feet(self, meters):
        return int(meters * 3.28084)
    
    def meters_to_miles(self, meters):
        return round(meters / 1609.344, 2)

    def weather_data_to_dataframe(self, data, convert_to_fahrenheit=False):
        all_data = {}

        for key in self.metric_keys:
            if key not in data:
                continue  # optional — skip absent fields gracefully

            all_data[key] = {}
            key_unit = data[key].get('uom') or ''
            is_celsius = 'degC' in key_unit
            is_kmh = 'km_h' in key_unit
            is_meters = key_unit == 'wmoUnit:m'  # exact match avoids false positives

            for entry in data[key]['values']:
                valid_time = entry['validTime']
                value = entry['value']

                # Temperature and dewpoint: °C → °F
                if convert_to_fahrenheit and is_celsius and key in ('temperature', 'dewpoint'):
                    if value is not None:
                        value = self.celsius_to_fahrenheit(value)

                # Wind speed / gust: km/h → knots
                if is_kmh and key in ('windSpeed', 'windGust'):
                    if value is not None:
                        value = self.kmh_to_knots(value)

                # Ceiling height: m → ft; negative = NWS "clear/unlimited" encoding
                if is_meters and key == 'ceilingHeight':
                    if value is not None and value >= 0:
                        value = self.meters_to_feet(value)
                    else:
                        value = float('inf')

                # Visibility: m → statute miles
                if is_meters and key == 'visibility':
                    if value is not None:
                        value = self.meters_to_miles(value)
                    else:
                        value = float('inf')

                start_time, end_time = self.parse_valid_time(valid_time)
                current_time = start_time
                while current_time < end_time:
                    all_data[key][current_time] = value
                    current_time += timedelta(hours=1)

        combined_data = pd.DataFrame()
        for key, time_value_dict in all_data.items():
            key_df = pd.DataFrame(list(time_value_dict.items()), columns=['time_utc', key])
            key_df.set_index('time_utc', inplace=True)
            if combined_data.empty:
                combined_data = key_df
            else:
                combined_data = combined_data.join(key_df, how='outer')

        return combined_data.sort_index()


    # ------------------------------------------------------------------
    # High-level fetch
    # ------------------------------------------------------------------

    def fetch_all(self, station_id: str, grid_coords: str, save_raw_dir: Path = None) -> WeatherData:
        """Fetch all data sources and return a WeatherData instance.

        Grid forecast is the primary hourly data source (ceiling, visibility, wind gust,
        sky cover, etc.) and is used to compute accurate flight categories.
        Hourly forecast is secondary — used only to merge shortForecast/isDaytime for
        icon display. If hourly fails, both are derived from skyCover/timestamp.
        """
        metar = self.get_metar_observation(station_id)

        try:
            nws_obs = self.get_nws_observation(station_id)
        except Exception as e:
            logger.warning("NWS observation unavailable, degrading: %s", e)
            nws_obs = {}

        try:
            summary = self.get_summary_area_forecast(grid_coords)
        except Exception as e:
            logger.warning("Summary forecast unavailable, degrading: %s", e)
            summary = {}

        # --- current obs fields from METAR ---
        temp_c = metar.get('temp')
        temp_f = self.celsius_to_fahrenheit(temp_c) if temp_c is not None else None

        dewp_c = metar.get('dewp') if metar.get('dewp') is not None else metar.get('dwpt')
        dewpoint_f = self.celsius_to_fahrenheit(dewp_c) if dewp_c is not None else None

        wind_dir = metar.get('wdir')
        wind_speed = metar.get('wspd')
        wind_gust = metar.get('wgst')

        visibility_sm = self._parse_visibility(metar.get('visib'))

        altim_hpa = metar.get('altim')
        altimeter_inhg = round(altim_hpa * _HPA_TO_INHG, 2) if altim_hpa is not None else None

        flight_category = metar.get('fltCat') or metar.get('fltcat')

        clouds = metar.get('clouds') or []
        ceiling = self._metar_ceiling(clouds)

        obs_time = self._parse_obs_time(metar.get('obsTime') or metar.get('reportTime'))
        wx_condition = self._wx_condition(metar, nws_obs)

        da = None
        if temp_f is not None and altimeter_inhg is not None:
            da = density_altitude(temp_f, altimeter_inhg, KORH_ELEVATION_FT)

        # --- grid API → primary hourly DataFrame ---
        grid_data = {}
        hourly_df = pd.DataFrame()
        try:
            grid_data = self.get_grid_area_forecast(grid_coords)
            hourly_df = self.weather_data_to_dataframe(
                grid_data['properties'], convert_to_fahrenheit=True
            )
            # Rename for consistency with display layer
            hourly_df.rename(
                columns={'probabilityOfPrecipitation': 'precipChance'}, inplace=True, errors='ignore'
            )
            # Compute accurate flight category from actual ceiling + visibility
            hourly_df['flightCategory'] = [
                _flight_cat_from_values(
                    hourly_df.at[t, 'ceilingHeight'] if 'ceilingHeight' in hourly_df.columns else None,
                    hourly_df.at[t, 'visibility'] if 'visibility' in hourly_df.columns else None,
                )
                for t in hourly_df.index
            ]
        except Exception as e:
            logger.warning("Grid area forecast unavailable, degrading: %s", e)
            hourly_df = pd.DataFrame()

        # --- hourly API → merge shortForecast + isDaytime for icon display ---
        hourly_data = {}
        try:
            hourly_data = self.get_hourly_forecast(grid_coords)
            for p in hourly_data.get('properties', {}).get('periods', []):
                t = datetime.fromisoformat(p['startTime']).astimezone(timezone.utc)
                if not hourly_df.empty and t in hourly_df.index:
                    hourly_df.at[t, 'shortForecast'] = p.get('shortForecast') or ''
                    hourly_df.at[t, 'isDaytime'] = bool(p.get('isDaytime', True))
        except Exception as e:
            logger.warning("Hourly forecast for icons unavailable, degrading: %s", e)

        # Fill any missing shortForecast/isDaytime from grid skyCover / local time
        if not hourly_df.empty:
            if 'shortForecast' not in hourly_df.columns:
                if 'skyCover' in hourly_df.columns:
                    hourly_df['shortForecast'] = hourly_df['skyCover'].apply(
                        lambda x: _sky_cover_to_forecast(x) if not _is_nan_safe(x) else 'Unknown'
                    )
                else:
                    hourly_df['shortForecast'] = 'Unknown'
            if 'isDaytime' not in hourly_df.columns:
                hourly_df['isDaytime'] = hourly_df.index.map(
                    lambda t: 6 <= t.to_pydatetime().astimezone().hour < 20
                )

        # --- daily periods ---
        daily_periods = summary.get('properties', {}).get('periods', []) or []

        # --- optionally dump raw payloads to disk (dev mode) ---
        if save_raw_dir is not None:
            raw_dir = Path(save_raw_dir)
            raw_dir.mkdir(parents=True, exist_ok=True)
            payloads = {
                "metar.json": metar,
                "nws_obs.json": nws_obs,
                "summary_forecast.json": summary,
                "grid_forecast.json": grid_data,
                "hourly_forecast.json": hourly_data,
            }
            for filename, payload in payloads.items():
                try:
                    (raw_dir / filename).write_text(json.dumps(payload, indent=2, default=str))
                except Exception as e:
                    logger.warning("Could not save raw payload %s: %s", filename, e)

        return WeatherData(
            station_id=station_id,
            obs_time=obs_time,
            temp_f=temp_f,
            dewpoint_f=dewpoint_f,
            wind_dir_deg=wind_dir,
            wind_speed_kt=wind_speed,
            wind_gust_kt=wind_gust,
            visibility_sm=visibility_sm,
            ceiling_ft=ceiling,
            altimeter_inhg=altimeter_inhg,
            flight_category=flight_category,
            wx_condition=wx_condition,
            density_altitude_ft=da,
            hourly_df=hourly_df,
            daily_periods=daily_periods,
        )

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _metar_ceiling(self, clouds: list) -> int | None:
        """Return ceiling in feet (lowest BKN or OVC layer), or None if clear."""
        ceiling = None
        for layer in clouds:
            cover = layer.get('cover', '')
            base = layer.get('base')
            if cover in ('BKN', 'OVC') and base is not None:
                base_ft = base * 100
                if ceiling is None or base_ft < ceiling:
                    ceiling = base_ft
        return ceiling

    def _parse_visibility(self, raw) -> float | None:
        """Parse METAR visibility which may be a string like '10+', '1/4', '1 1/2'."""
        if raw is None:
            return None
        s = str(raw).strip().lstrip('M').lstrip('<').rstrip('+').strip()
        if '/' in s:
            parts = s.split()
            if len(parts) == 2:
                whole, frac = float(parts[0]), parts[1]
            else:
                whole, frac = 0.0, parts[0]
            num, den = frac.split('/')
            return whole + float(num) / float(den)
        try:
            return float(s)
        except ValueError:
            return None

    def _parse_obs_time(self, raw) -> datetime:
        """Parse obsTime (Unix timestamp int) or ISO-8601 string into a UTC datetime."""
        if isinstance(raw, (int, float)):
            return datetime.fromtimestamp(raw, tz=timezone.utc)
        if isinstance(raw, str):
            try:
                return datetime.fromisoformat(raw.replace('Z', '+00:00'))
            except ValueError:
                pass
        return datetime.now(tz=timezone.utc)

    def _wx_condition(self, metar: dict, nws_obs: dict) -> str:
        """Derive a natural-language weather condition string for icon lookup.

        Priority: NWS textDescription → decoded METAR wxString → flight category.
        """
        text = nws_obs.get('properties', {}).get('textDescription', '').strip()
        if text:
            return text

        wx_string = metar.get('wxString', '').strip()
        if wx_string:
            return self._decode_wx_string(wx_string)

        return metar.get('fltCat') or metar.get('fltcat') or 'Unknown'

    def _decode_wx_string(self, wx: str) -> str:
        """Translate a METAR wx code to a natural-language string for icon lookup."""
        u = wx.upper()
        if 'TS' in u:
            return 'Thunderstorm'
        if 'FZRA' in u or 'FZDZ' in u:
            return 'Freezing Rain'
        if 'GR' in u or 'GS' in u:
            return 'Hail'
        if 'SN' in u or 'SG' in u:
            return 'Snow'
        if 'PL' in u:
            return 'Sleet'
        if 'RA' in u:
            return 'Rain'
        if 'DZ' in u:
            return 'Drizzle'
        if 'FG' in u:
            return 'Fog'
        if 'BR' in u:
            return 'Mist'
        if 'HZ' in u:
            return 'Haze'
        if 'FU' in u:
            return 'Smoke'
        if 'DU' in u or 'SA' in u:
            return 'Dust'
        return wx


if __name__ == "__main__":
    # Example usage
    nws = NWSWeatherWrapper()

    # Get current METAR observation
    print("=" * 80)
    print("CURRENT METAR OBSERVATION")
    print("=" * 80)
    metar_data = nws.get_metar_observation(WORCESTER_AIRPORT_STATION)

    if metar_data:
        print(f"\nStation: {metar_data.get('icaoId', 'N/A')}")
        print(f"Observation Time: {metar_data.get('obsTime', 'N/A')}")
        print(f"Report Time: {metar_data.get('reportTime', 'N/A')}")
        print(f"\nRaw METAR: {metar_data.get('rawOb', 'N/A')}")

        # Temperature (already in Celsius)
        temp_c = metar_data.get('temp')
        if temp_c is not None:
            temp_f = nws.celsius_to_fahrenheit(temp_c)
            print(f"\nTemperature: {temp_f:.1f}°F ({temp_c:.1f}°C)")

        # Dewpoint (already in Celsius)
        dewpoint_c = metar_data.get('dwpt')
        if dewpoint_c is not None:
            dewpoint_f = nws.celsius_to_fahrenheit(dewpoint_c)
            print(f"Dewpoint: {dewpoint_f:.1f}°F ({dewpoint_c:.1f}°C)")

        # Wind (already in knots)
        wind_dir = metar_data.get('wdir')
        wind_speed = metar_data.get('wspd')
        wind_gust = metar_data.get('wgst')
        if wind_dir is not None and wind_speed is not None:
            print(f"Wind: {wind_dir}° at {wind_speed} kt", end="")
            if wind_gust is not None:
                print(f" gusting to {wind_gust} kt")
            else:
                print()
        elif metar_data.get('wdir') == 0 and metar_data.get('wspd') == 0:
            print("Wind: Calm")

        # Visibility (in statute miles)
        visibility = metar_data.get('visib')
        if visibility is not None:
            print(f"Visibility: {visibility} miles")

        # Barometric Pressure (in inches Hg)
        pressure = metar_data.get('altim')
        if pressure is not None:
            print(f"Pressure: {pressure:.2f} inHg")

        # Flight Category
        flight_cat = metar_data.get('fltcat')
        if flight_cat:
            print(f"Flight Category: {flight_cat}")

        # Cloud Layers
        clouds = metar_data.get('clouds')
        if clouds:
            print("\nCloud Layers:")
            for cloud in clouds:
                cover = cloud.get('cover', 'N/A')
                base = cloud.get('base')
                if base is not None:
                    # Base is in hundreds of feet
                    base_ft = base * 100
                    print(f"  {cover}: {base_ft} ft")
                else:
                    print(f"  {cover}")

        # Weather conditions
        wx_string = metar_data.get('wxString')
        if wx_string:
            print(f"\nWeather: {wx_string}")

    # Get NWS observation for present weather
    print("\n" + "=" * 80)
    print("NWS OBSERVATION (for present weather)")
    print("=" * 80)
    nws_obs_data = nws.get_nws_observation(WORCESTER_AIRPORT_STATION)

    if 'properties' in nws_obs_data:
        props = nws_obs_data['properties']
        print(f"\nStation: {props.get('station', 'N/A')}")
        print(f"Timestamp: {props.get('timestamp', 'N/A')}")

        # Present Weather
        present_weather = props.get('presentWeather')
        if present_weather:
            print(f"\nPresent Weather:")
            for wx in present_weather:
                intensity = wx.get('intensity', 'N/A')
                modifier = wx.get('modifier', 'N/A')
                weather = wx.get('weather', 'N/A')
                raw_string = wx.get('rawString', 'N/A')
                print(f"  Intensity: {intensity}")
                print(f"  Modifier: {modifier}")
                print(f"  Weather: {weather}")
                print(f"  Raw: {raw_string}")
                print()
        else:
            print("\nPresent Weather: None reported")

        # Text Description
        text_desc = props.get('textDescription')
        if text_desc:
            print(f"Text Description: {text_desc}")

    # Get detailed grid forecast
    print("\n" + "=" * 80)
    print("DETAILED GRID FORECAST")
    print("=" * 80)
    forecast_data = nws.get_grid_area_forecast(WORCESTER_GRID_COORDS)
    df = nws.weather_data_to_dataframe(forecast_data['properties'], convert_to_fahrenheit=True)
    print(df.to_string())

    # Get summary area forecast
    print("\n" + "=" * 80)
    print("DAILY FORECAST")
    print("=" * 80)
    summary_forecast = nws.get_summary_area_forecast(WORCESTER_GRID_COORDS)

    # Print parsed summary forecast data grouped by day
    if 'properties' in summary_forecast and 'periods' in summary_forecast['properties']:
        periods = summary_forecast['properties']['periods']

        # Group periods into days (pairing day and night periods)
        i = 0
        while i < len(periods):
            day_period = None
            night_period = None

            # Get current and next period
            current = periods[i]
            next_period = periods[i + 1] if i + 1 < len(periods) else None

            # Determine which is day and which is night
            if current.get('isDaytime'):
                day_period = current
                night_period = next_period
                i += 2
            else:
                # If we start with a night period, just show it and move on
                night_period = current
                day_period = next_period
                i += 1
                if next_period:
                    i += 1

            # Only display if we have a day period (user wants day by day only)
            if day_period:
                day_name = day_period.get('name', 'N/A')
                high_temp = day_period.get('temperature', 'N/A')
                temp_unit = day_period.get('temperatureUnit', 'F')

                # Get low from night period if available
                low_temp = night_period.get('temperature', 'N/A') if night_period else 'N/A'

                print(f"\n{day_name}:")
                print(f"  High: {high_temp}°{temp_unit} / Low: {low_temp}°{temp_unit}")
                print(f"  Wind: {day_period.get('windSpeed', 'N/A')} {day_period.get('windDirection', 'N/A')}")
                print(f"  Forecast: {day_period.get('shortForecast', 'N/A')}")
                print(f"  Details: {day_period.get('detailedForecast', 'N/A')}")
    else:
        print("No forecast periods found in response")
        print(f"Response keys: {summary_forecast.keys()}")