import requests
from datetime import datetime, timedelta
import pandas as pd
import re

WORCESTER_GRID_COORDS = "45,81"
BOSTON_FORECAST_OFFICE_ID = "BOX"


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
    forecast_data = nws.get_grid_area_forecast(WORCESTER_GRID_COORDS)
    print(forecast_data)
    df = nws.weather_data_to_dataframe(forecast_data['properties'], convert_to_fahrenheit=True)

    print(df.to_string())