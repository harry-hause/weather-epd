"""Real API response snapshots for KSEA (Seattle-Tacoma International, WA) — fetched 2026-05-22.

Quirks captured:
- No gusts (wgst=None)
- FEW clouds → no ceiling
- ceilingHeight and visibility have null uom + empty values list (same as KDEN)
- windDirection has a PT2H duration slot (tests multi-hour expansion)
- Forecast includes PNW characteristic strings: Mostly Clear, Sunny, Mostly Cloudy
"""

METAR = {
    "icaoId": "KSEA",
    "obsTime": 1779411180,
    "temp": 24.4,
    "dewp": 5.0,
    "wdir": 330,
    "wspd": 8,
    "wgst": None,
    "visib": "10+",
    "altim": 1017.0,
    "fltCat": "VFR",
    "clouds": [{"cover": "FEW", "base": 9000}],
    "cover": "FEW",
    "wxString": None,
}

NWS_OBS = {
    "properties": {
        "textDescription": "Fair",
        "timestamp": "2026-05-22T01:25:00+00:00",
    }
}

GRID = {
    "properties": {
        "temperature": {
            "uom": "wmoUnit:degC",
            "values": [
                {"validTime": "2026-05-21T14:00:00+00:00/PT1H", "value": 11.111},
                {"validTime": "2026-05-21T15:00:00+00:00/PT1H", "value": 12.778},
                {"validTime": "2026-05-21T16:00:00+00:00/PT1H", "value": 13.889},
            ],
        },
        "windDirection": {
            "uom": "wmoUnit:degree_(angle)",
            "values": [
                # PT2H slot — should expand into two separate hourly rows
                {"validTime": "2026-05-21T14:00:00+00:00/PT1H", "value": 20},
                {"validTime": "2026-05-21T15:00:00+00:00/PT2H", "value": 10},
            ],
        },
        "windSpeed": {
            "uom": "wmoUnit:km_h-1",
            "values": [
                {"validTime": "2026-05-21T14:00:00+00:00/PT2H", "value": 3.704},
                {"validTime": "2026-05-21T16:00:00+00:00/PT1H", "value": 5.556},
            ],
        },
        "windGust": {
            "uom": "wmoUnit:km_h-1",
            "values": [
                {"validTime": "2026-05-21T14:00:00+00:00/PT2H", "value": 7.408},
                {"validTime": "2026-05-21T16:00:00+00:00/PT1H", "value": 9.26},
            ],
        },
        # Real quirk: null uom + empty values (no ceiling/visibility data in grid)
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
                "temperature": 52,
                "temperatureUnit": "F",
                "windSpeed": "2 to 7 mph",
                "windDirection": "NNE",
                "shortForecast": "Mostly Clear",
                "detailedForecast": "Mostly clear, with a low around 52.",
            },
            {
                "name": "Friday",
                "isDaytime": True,
                "temperature": 75,
                "temperatureUnit": "F",
                "windSpeed": "1 to 6 mph",
                "windDirection": "NNW",
                "shortForecast": "Sunny",
                "detailedForecast": "Sunny, with a high near 75.",
            },
            {
                "name": "Friday Night",
                "isDaytime": False,
                "temperature": 52,
                "temperatureUnit": "F",
                "windSpeed": "6 mph",
                "windDirection": "NW",
                "shortForecast": "Mostly Cloudy",
                "detailedForecast": "Mostly cloudy, with a low around 52.",
            },
        ]
    }
}

GRID_COORDS = "124,60"
