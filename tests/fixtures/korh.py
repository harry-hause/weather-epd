"""API response fixtures for KORH (Worcester Regional, MA).

Used as the default/baseline fixture in test_data.py. Values are representative
rather than a live snapshot — chosen to exercise common parsing paths (CLR sky,
no gusts, "10+" visibility string, VFR/MVFR mix in hourly, fog period for LIFR path).
"""

METAR = {
    "icaoId": "KORH",
    "obsTime": 1779411240,
    "temp": 13.3,
    "dewp": -2.8,
    "wdir": 320,
    "wspd": 6,
    "visib": "10+",
    "altim": 1024.5,   # hPa — must be converted to inHg
    "fltCat": "VFR",
    "clouds": [],
    "cover": "CLR",
    "wxString": "",
}

NWS_OBS = {
    "properties": {
        "timestamp": "2026-05-22T01:25:00+00:00",
        "textDescription": "Clear",
        "presentWeather": [],
    }
}

# 6-hour block so the DataFrame gets one row per hour for the covered window
GRID = {
    "properties": {
        "temperature": {
            "uom": "wmoUnit:degC",
            "values": [{"validTime": "2026-05-22T00:00:00+00:00/PT6H", "value": 15.0}],
        },
        "dewpoint": {
            "uom": "wmoUnit:degC",
            "values": [{"validTime": "2026-05-22T00:00:00+00:00/PT6H", "value": -2.8}],
        },
        "relativeHumidity": {
            "uom": "wmoUnit:percent",
            "values": [{"validTime": "2026-05-22T00:00:00+00:00/PT6H", "value": 45}],
        },
        "skyCover": {
            "uom": "wmoUnit:percent",
            "values": [{"validTime": "2026-05-22T00:00:00+00:00/PT6H", "value": 0}],
        },
        "windDirection": {
            "uom": "wmoUnit:degree_(angle)",
            "values": [{"validTime": "2026-05-22T00:00:00+00:00/PT6H", "value": 270}],
        },
        "windSpeed": {
            "uom": "wmoUnit:km_h-1",
            "values": [{"validTime": "2026-05-22T00:00:00+00:00/PT6H", "value": 18.52}],
        },
        "windGust": {
            "uom": "wmoUnit:km_h-1",
            "values": [{"validTime": "2026-05-22T00:00:00+00:00/PT6H", "value": None}],
        },
        "ceilingHeight": {
            "uom": "wmoUnit:m",
            "values": [{"validTime": "2026-05-22T00:00:00+00:00/PT6H", "value": None}],
        },
        "visibility": {
            "uom": "wmoUnit:m",
            "values": [{"validTime": "2026-05-22T00:00:00+00:00/PT6H", "value": 16093.0}],
        },
        "probabilityOfPrecipitation": {
            "uom": "wmoUnit:percent",
            "values": [{"validTime": "2026-05-22T00:00:00+00:00/PT6H", "value": 0}],
        },
    }
}

SUMMARY = {
    "properties": {
        "periods": [
            {
                "name": "Today",
                "isDaytime": True,
                "temperature": 65,
                "temperatureUnit": "F",
                "windSpeed": "10 mph",
                "windDirection": "W",
                "shortForecast": "Mostly Sunny",
                "detailedForecast": "Mostly sunny skies.",
            },
            {
                "name": "Tonight",
                "isDaytime": False,
                "temperature": 45,
                "temperatureUnit": "F",
                "windSpeed": "5 mph",
                "windDirection": "W",
                "shortForecast": "Partly Cloudy",
                "detailedForecast": "Partly cloudy skies.",
            },
        ]
    }
}

HOURLY_FORECAST = {
    "properties": {
        "periods": [
            {
                "number": 1,
                "startTime": "2026-05-22T20:00:00-04:00",
                "endTime": "2026-05-22T21:00:00-04:00",
                "isDaytime": True,
                "temperature": 65,
                "temperatureUnit": "F",
                "windSpeed": "10 mph",
                "windDirection": "W",
                "icon": "https://api.weather.gov/icons/land/day/skc?size=small",
                "shortForecast": "Clear",
                "probabilityOfPrecipitation": {"unitCode": "wmoUnit:percent", "value": 0},
                "relativeHumidity": {"unitCode": "wmoUnit:percent", "value": 45},
            },
            {
                "number": 2,
                "startTime": "2026-05-22T21:00:00-04:00",
                "endTime": "2026-05-22T22:00:00-04:00",
                "isDaytime": False,
                "temperature": 58,
                "temperatureUnit": "F",
                "windSpeed": "7 mph",
                "windDirection": "NW",
                "icon": "https://api.weather.gov/icons/land/night/bkn?size=small",
                "shortForecast": "Mostly Cloudy",
                "probabilityOfPrecipitation": {"unitCode": "wmoUnit:percent", "value": 10},
                "relativeHumidity": {"unitCode": "wmoUnit:percent", "value": 62},
            },
            {
                "number": 3,
                "startTime": "2026-05-22T22:00:00-04:00",
                "endTime": "2026-05-22T23:00:00-04:00",
                "isDaytime": False,
                "temperature": 52,
                "temperatureUnit": "F",
                "windSpeed": "5 mph",
                "windDirection": "NE",
                "icon": "https://api.weather.gov/icons/land/night/fog?size=small",
                "shortForecast": "Patchy Fog",
                "probabilityOfPrecipitation": {"unitCode": "wmoUnit:percent", "value": 0},
                "relativeHumidity": {"unitCode": "wmoUnit:percent", "value": 88},
            },
        ]
    }
}

GRID_COORDS = "45,81"
