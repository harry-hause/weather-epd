"""Real API response snapshots for KMIA (Miami International, FL) — fetched 2026-05-22.

Quirks captured:
- No gusts (wgst=None)
- FEW clouds only → no ceiling from METAR
- Negative ceilingHeight values in grid (-30.48 m) = NWS encoding for clear/unlimited
- High humidity: dewpoint 22.2°C (72°F)
- Forecast includes thunderstorm strings
"""

METAR = {
    "icaoId": "KMIA",
    "obsTime": 1779411180,
    "temp": 27.8,
    "dewp": 22.2,
    "wdir": 100,
    "wspd": 11,
    "wgst": None,
    "visib": "10+",
    "altim": 1016.3,
    "fltCat": "VFR",
    "clouds": [
        {"cover": "FEW", "base": 2600},
        {"cover": "SCT", "base": 25000},
    ],
    "cover": "SCT",
    "wxString": None,
}

NWS_OBS = {
    "properties": {
        "textDescription": "Mostly Sunny",
        "timestamp": "2026-05-22T01:30:00+00:00",
    }
}

GRID = {
    "properties": {
        "temperature": {
            "uom": "wmoUnit:degC",
            "values": [
                {"validTime": "2026-05-21T14:00:00+00:00/PT1H", "value": 28.889},
                {"validTime": "2026-05-21T15:00:00+00:00/PT1H", "value": 29.444},
                {"validTime": "2026-05-21T16:00:00+00:00/PT1H", "value": 30.0},
            ],
        },
        "windDirection": {
            "uom": "wmoUnit:degree_(angle)",
            "values": [
                {"validTime": "2026-05-21T14:00:00+00:00/PT6H",  "value": 110},
                {"validTime": "2026-05-21T20:00:00+00:00/PT12H", "value": 100},
            ],
        },
        "windSpeed": {
            "uom": "wmoUnit:km_h-1",
            "values": [
                {"validTime": "2026-05-21T14:00:00+00:00/PT1H", "value": 16.668},
                {"validTime": "2026-05-21T15:00:00+00:00/PT3H", "value": 18.52},
            ],
        },
        "windGust": {
            "uom": "wmoUnit:km_h-1",
            "values": [
                {"validTime": "2026-05-21T14:00:00+00:00/PT1H", "value": 24.076},
                {"validTime": "2026-05-21T15:00:00+00:00/PT1H", "value": 25.928},
            ],
        },
        # Real quirk: -30.48 m = NWS "clear/unlimited" ceiling encoding
        "ceilingHeight": {
            "uom": "wmoUnit:m",
            "values": [
                {"validTime": "2026-05-21T14:00:00+00:00/P1DT10H", "value": -30.48},
                {"validTime": "2026-05-23T00:00:00+00:00/PT2H",    "value": 7620},
                {"validTime": "2026-05-23T02:00:00+00:00/PT5H",    "value": -30.48},
            ],
        },
        "visibility": {
            "uom": "wmoUnit:m",
            "values": [
                {"validTime": "2026-05-21T14:00:00+00:00/PT3H", "value": 16093.44},
                {"validTime": "2026-05-21T17:00:00+00:00/PT2H", "value": 12697.72},
            ],
        },
    }
}

SUMMARY = {
    "properties": {
        "periods": [
            {
                "name": "Tonight",
                "isDaytime": False,
                "temperature": 78,
                "temperatureUnit": "F",
                "windSpeed": "8 to 13 mph",
                "windDirection": "E",
                "shortForecast": "Partly Cloudy",
                "detailedForecast": "Partly cloudy, with a low around 78.",
            },
            {
                "name": "Friday",
                "isDaytime": True,
                "temperature": 89,
                "temperatureUnit": "F",
                "windSpeed": "8 to 13 mph",
                "windDirection": "E",
                "shortForecast": "Mostly Sunny",
                "detailedForecast": "Mostly sunny, with a high near 89.",
            },
            {
                "name": "Friday Night",
                "isDaytime": False,
                "temperature": 79,
                "temperatureUnit": "F",
                "windSpeed": "8 to 13 mph",
                "windDirection": "E",
                "shortForecast": "Slight Chance Showers And Thunderstorms then Partly Cloudy",
                "detailedForecast": "A slight chance of showers and thunderstorms.",
            },
        ]
    }
}

GRID_COORDS = "105,51"
