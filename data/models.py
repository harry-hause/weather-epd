from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

KORH_ELEVATION_FT = 1009  # Worcester Regional Airport (KORH) MSL elevation


@dataclass
class WeatherData:
    station_id: str
    obs_time: datetime
    # Current observation — any field may be None if the METAR is incomplete
    temp_f: float | None
    dewpoint_f: float | None
    wind_dir_deg: int | None
    wind_variable: bool
    wind_speed_kt: int | None
    wind_gust_kt: int | None
    visibility_sm: float | None
    ceiling_ft: int | None       # None = clear / unlimited
    altimeter_inhg: float | None
    flight_category: str | None  # VFR / MVFR / IFR / LIFR
    wx_condition: str            # natural-language string for icon lookup
    density_altitude_ft: int | None
    # Forecast
    hourly_df: pd.DataFrame      # columns: temperature, windDirection, windSpeed, windGust, ceilingHeight, visibility
    daily_periods: list[dict]    # NWS summary forecast period dicts


def density_altitude(temp_f: float, altimeter_inhg: float, elevation_ft: int = KORH_ELEVATION_FT) -> int:
    """Calculate density altitude in feet using the standard FAA approximation.

    DA = PA + 118.8 × (OAT − ISA_temp)
    where PA is pressure altitude and ISA_temp is the standard temperature at elevation.
    """
    pressure_alt = (29.92 - altimeter_inhg) * 1000 + elevation_ft
    isa_temp_f = 59.0 - 3.5 * (elevation_ft / 1000.0)
    return round(pressure_alt + 118.8 * (temp_f - isa_temp_f))
