import requests
from datetime import datetime, timedelta
import pandas as pd
import re

WORCESTER_GRID_COORDS = "45,81"
BOSTON_FORECAST_OFFICE_ID = "BOX"
WORCESTER_AIRPORT_STATION = "KORH"


class NWSWeatherWrapper:
    def __init__(self):
        self.metric_keys = ['temperature', 'windDirection', 'windSpeed', 'windGust', 'ceilingHeight', 'visibility']

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
        # Dictionary to hold time:value pairs for each key
        all_data = {key: {} for key in self.metric_keys}
        
        for key in self.metric_keys:
            if key not in data:
                raise KeyError(f"Key '{key}' not found in the data.")
            
            # Extract the values for the current key
            key_values = data[key]['values']
            
            # Determine the unit of measurement for the current key
            key_unit = data[key].get('uom', '')
            is_celsius = 'degC' in key_unit
            is_kmh = 'km_h' in key_unit
            is_meters = 'm' in key_unit
            
            # Process each value in the key's data
            for entry in key_values:
                valid_time = entry['validTime']
                value = entry['value']
                
                # Convert to Fahrenheit if requested and the data is in Celsius
                if convert_to_fahrenheit and is_celsius and key == 'temperature':
                    value = self.celsius_to_fahrenheit(value)
                
                # Convert wind speed from km/h to knots if applicable
                if is_kmh and key in ['windSpeed', 'windGust']:
                    value = self.kmh_to_knots(value)
                
                # Convert ceiling height from meters to feet if applicable
                if is_meters and key == 'ceilingHeight':
                    if value is not None:
                        value = self.meters_to_feet(value)
                    else:
                        value = float('inf')

                if is_meters and key == 'visibility':
                    if value is not None:
                        value = self.meters_to_miles(value)
                    else:
                        value = float('inf')
                
                # Parse the valid time to get start and end times
                start_time, end_time = self.parse_valid_time(valid_time)
                
                # Create hourly entries from start_time to end_time
                current_time = start_time
                while current_time < end_time:
                    # Add the value to our dictionary for the current key
                    all_data[key][current_time] = value
                    # Move to the next hour
                    current_time += timedelta(hours=1)
        
        # Combine all keys into a single DataFrame
        combined_data = pd.DataFrame()
        for key, time_value_dict in all_data.items():
            key_df = pd.DataFrame(list(time_value_dict.items()), columns=['time_utc', key])
            key_df.set_index('time_utc', inplace=True)
            if combined_data.empty:
                combined_data = key_df
            else:
                combined_data = combined_data.join(key_df, how='outer')
        
        # Sort by time
        combined_data = combined_data.sort_index()
        
        return combined_data


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