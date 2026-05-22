"""Real API response snapshots for KDEN (Denver International, CO) — fetched 2026-05-22.

Quirks captured:
- Gusts present (wgst=25)
- All SCT clouds → no ceiling
- ceilingHeight and visibility have null uom + empty values list in the grid endpoint
"""

METAR = {
    "icaoId": "KDEN",
    "obsTime": 1779411180,
    "temp": 14.4,
    "dewp": 3.9,
    "wdir": 360,
    "wspd": 16,
    "wgst": 25,
    "visib": "10+",
    "altim": 1010.9,
    "fltCat": "VFR",
    "clouds": [
        {"cover": "SCT", "base": 8500},
        {"cover": "SCT", "base": 12000},
        {"cover": "SCT", "base": 20000},
    ],
    "cover": "SCT",
    "wxString": None,
}

NWS_OBS = {
    "properties": {
        "textDescription": "Clear",
        "timestamp": "2026-05-22T01:25:00+00:00",
    }
}

GRID = {
    "properties": {
        "temperature": {
            "uom": "wmoUnit:degC",
            "values": [
                {"validTime": "2026-05-21T12:00:00+00:00/PT1H", "value": 5},
                {"validTime": "2026-05-21T13:00:00+00:00/PT1H", "value": 6.667},
                {"validTime": "2026-05-21T14:00:00+00:00/PT1H", "value": 8.333},
            ],
        },
        "windDirection": {
            "uom": "wmoUnit:degree_(angle)",
            "values": [
                {"validTime": "2026-05-21T12:00:00+00:00/PT1H", "value": 200},
                {"validTime": "2026-05-21T13:00:00+00:00/PT2H", "value": 210},
                {"validTime": "2026-05-21T15:00:00+00:00/PT1H", "value": 200},
            ],
        },
        "windSpeed": {
            "uom": "wmoUnit:km_h-1",
            "values": [
                {"validTime": "2026-05-21T12:00:00+00:00/PT2H", "value": 11.112},
                {"validTime": "2026-05-21T14:00:00+00:00/PT1H", "value": 9.26},
                {"validTime": "2026-05-21T15:00:00+00:00/PT1H", "value": 7.408},
            ],
        },
        "windGust": {
            "uom": "wmoUnit:km_h-1",
            "values": [
                {"validTime": "2026-05-21T12:00:00+00:00/PT2H", "value": 16.668},
                {"validTime": "2026-05-21T14:00:00+00:00/PT1H", "value": 12.964},
                {"validTime": "2026-05-21T15:00:00+00:00/PT1H", "value": 11.112},
            ],
        },
        # Real quirk: null uom + empty values when grid has no ceiling/vis data
        "ceilingHeight": {"uom": None, "values": []},
        "visibility": {"uom": None, "values": []},
    }
}

SUMMARY = {
    "properties": {
        "periods": [
            {
                "name": "Tonight",
                "isDaytime": False,
                "temperature": 39,
                "temperatureUnit": "F",
                "windSpeed": "8 to 13 mph",
                "windDirection": "NNE",
                "shortForecast": "Chance Showers And Thunderstorms",
                "detailedForecast": "A chance of showers and thunderstorms.",
            },
            {
                "name": "Friday",
                "isDaytime": True,
                "temperature": 63,
                "temperatureUnit": "F",
                "windSpeed": "9 mph",
                "windDirection": "NE",
                "shortForecast": "Mostly Sunny",
                "detailedForecast": "Mostly sunny, with a high near 63.",
            },
        ]
    }
}

GRID_COORDS = "75,66"
