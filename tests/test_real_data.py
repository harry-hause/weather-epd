"""Tests using snapshots of real NWS/METAR API responses.

Fixtures are in tests/fixtures/ — one file per station. Each station exercises
different real-world quirks; see the fixture module docstrings for details.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data.nws_wx_wrapper import NWSWeatherWrapper
from tests.fixtures import kden, kmia, ksea

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def wrapper():
    return NWSWeatherWrapper()


def _resp(data, status=200):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = data
    return m


_EMPTY_HOURLY = {"properties": {"periods": []}}


def _make_side_effect(metar, nws_obs, grid, summary, hourly=None):
    hourly_resp = hourly or _EMPTY_HOURLY

    def side_effect(url, **kwargs):
        if "aviationweather" in url:
            return _resp([metar])
        if "observations/latest" in url:
            return _resp(nws_obs)
        if "/forecast/hourly" in url:   # must come before /forecast
            return _resp(hourly_resp)
        if "/forecast" in url:
            return _resp(summary)
        if "gridpoints" in url:         # bare gridpoints (no /forecast)
            return _resp(grid)
        raise ValueError(f"Unexpected URL: {url}")
    return side_effect


# ---------------------------------------------------------------------------
# KDEN — Denver (gusts, SCT clouds, null-uom grid keys)
# ---------------------------------------------------------------------------

class TestKDEN:
    def test_fetch_all_succeeds(self, wrapper):
        with patch("requests.get", side_effect=_make_side_effect(
                kden.METAR, kden.NWS_OBS, kden.GRID, kden.SUMMARY)):
            data = wrapper.fetch_all("KDEN", kden.GRID_COORDS)
        assert data.station_id == "KDEN"

    def test_temperature(self, wrapper):
        with patch("requests.get", side_effect=_make_side_effect(
                kden.METAR, kden.NWS_OBS, kden.GRID, kden.SUMMARY)):
            data = wrapper.fetch_all("KDEN", kden.GRID_COORDS)
        # 14.4°C → 57.92°F
        assert data.temp_f == pytest.approx(57.92, abs=0.1)

    def test_gusts_present(self, wrapper):
        with patch("requests.get", side_effect=_make_side_effect(
                kden.METAR, kden.NWS_OBS, kden.GRID, kden.SUMMARY)):
            data = wrapper.fetch_all("KDEN", kden.GRID_COORDS)
        assert data.wind_gust_kt == 25

    def test_sct_clouds_no_ceiling(self, wrapper):
        with patch("requests.get", side_effect=_make_side_effect(
                kden.METAR, kden.NWS_OBS, kden.GRID, kden.SUMMARY)):
            data = wrapper.fetch_all("KDEN", kden.GRID_COORDS)
        assert data.ceiling_ft is None

    def test_altimeter_converted(self, wrapper):
        with patch("requests.get", side_effect=_make_side_effect(
                kden.METAR, kden.NWS_OBS, kden.GRID, kden.SUMMARY)):
            data = wrapper.fetch_all("KDEN", kden.GRID_COORDS)
        # 1010.9 hPa → ~29.85 inHg
        assert data.altimeter_inhg == pytest.approx(29.85, abs=0.02)

    def test_null_uom_grid_does_not_crash(self, wrapper):
        # ceilingHeight and visibility have null uom + empty values — must not TypeError
        df = wrapper.weather_data_to_dataframe(kden.GRID["properties"])
        assert not df.empty
        assert df["ceilingHeight"].isna().all()
        assert df["visibility"].isna().all()

    def test_wx_condition_from_nws_text(self, wrapper):
        with patch("requests.get", side_effect=_make_side_effect(
                kden.METAR, kden.NWS_OBS, kden.GRID, kden.SUMMARY)):
            data = wrapper.fetch_all("KDEN", kden.GRID_COORDS)
        assert data.wx_condition == "Clear"

    def test_forecast_periods(self, wrapper):
        with patch("requests.get", side_effect=_make_side_effect(
                kden.METAR, kden.NWS_OBS, kden.GRID, kden.SUMMARY)):
            data = wrapper.fetch_all("KDEN", kden.GRID_COORDS)
        assert len(data.daily_periods) == 2
        assert data.daily_periods[1]["shortForecast"] == "Mostly Sunny"

    def test_grid_temperature_in_fahrenheit(self, wrapper):
        # Tests weather_data_to_dataframe unit conversion (grid endpoint, not fetch_all)
        df = wrapper.weather_data_to_dataframe(kden.GRID["properties"], convert_to_fahrenheit=True)
        # 5°C → 41°F
        assert df["temperature"].iloc[0] == pytest.approx(41.0, abs=0.1)

    def test_grid_wind_gust_in_knots(self, wrapper):
        df = wrapper.weather_data_to_dataframe(kden.GRID["properties"])
        # 16.668 km/h → 9 kt
        assert df["windGust"].iloc[0] == 9


# ---------------------------------------------------------------------------
# KMIA — Miami (no gusts, negative ceilingHeight = unlimited, tropical temps)
# ---------------------------------------------------------------------------

class TestKMIA:
    def test_fetch_all_succeeds(self, wrapper):
        with patch("requests.get", side_effect=_make_side_effect(
                kmia.METAR, kmia.NWS_OBS, kmia.GRID, kmia.SUMMARY)):
            data = wrapper.fetch_all("KMIA", kmia.GRID_COORDS)
        assert data.station_id == "KMIA"

    def test_no_gusts(self, wrapper):
        with patch("requests.get", side_effect=_make_side_effect(
                kmia.METAR, kmia.NWS_OBS, kmia.GRID, kmia.SUMMARY)):
            data = wrapper.fetch_all("KMIA", kmia.GRID_COORDS)
        assert data.wind_gust_kt is None

    def test_few_clouds_no_ceiling(self, wrapper):
        with patch("requests.get", side_effect=_make_side_effect(
                kmia.METAR, kmia.NWS_OBS, kmia.GRID, kmia.SUMMARY)):
            data = wrapper.fetch_all("KMIA", kmia.GRID_COORDS)
        assert data.ceiling_ft is None

    def test_negative_ceiling_height_treated_as_unlimited(self, wrapper):
        # -30.48 m in the grid = NWS "clear" encoding → must be float('inf'), not -100 ft
        df = wrapper.weather_data_to_dataframe(kmia.GRID["properties"])
        assert df["ceilingHeight"].iloc[0] == float("inf")

    def test_positive_ceiling_height_converted(self, wrapper):
        # 7620 m ≈ 25000 ft — appears in second ceiling slot in KMIA grid
        df = wrapper.weather_data_to_dataframe(kmia.GRID["properties"])
        finite = df["ceilingHeight"]
        finite = finite[finite != float("inf")].dropna()
        assert not finite.empty
        assert finite.iloc[0] == pytest.approx(25000, abs=100)

    def test_tropical_temperature(self, wrapper):
        with patch("requests.get", side_effect=_make_side_effect(
                kmia.METAR, kmia.NWS_OBS, kmia.GRID, kmia.SUMMARY)):
            data = wrapper.fetch_all("KMIA", kmia.GRID_COORDS)
        # 27.8°C → 82.04°F
        assert data.temp_f == pytest.approx(82.04, abs=0.1)

    def test_dewpoint_high_humidity(self, wrapper):
        with patch("requests.get", side_effect=_make_side_effect(
                kmia.METAR, kmia.NWS_OBS, kmia.GRID, kmia.SUMMARY)):
            data = wrapper.fetch_all("KMIA", kmia.GRID_COORDS)
        # 22.2°C → 71.96°F
        assert data.dewpoint_f == pytest.approx(71.96, abs=0.1)

    def test_wx_condition_from_nws_text(self, wrapper):
        with patch("requests.get", side_effect=_make_side_effect(
                kmia.METAR, kmia.NWS_OBS, kmia.GRID, kmia.SUMMARY)):
            data = wrapper.fetch_all("KMIA", kmia.GRID_COORDS)
        assert data.wx_condition == "Mostly Sunny"

    def test_thunderstorm_forecast_string_present(self, wrapper):
        with patch("requests.get", side_effect=_make_side_effect(
                kmia.METAR, kmia.NWS_OBS, kmia.GRID, kmia.SUMMARY)):
            data = wrapper.fetch_all("KMIA", kmia.GRID_COORDS)
        forecasts = [p["shortForecast"] for p in data.daily_periods]
        assert any("Thunderstorm" in f for f in forecasts)

    def test_density_altitude_elevated_by_heat(self, wrapper):
        with patch("requests.get", side_effect=_make_side_effect(
                kmia.METAR, kmia.NWS_OBS, kmia.GRID, kmia.SUMMARY)):
            data = wrapper.fetch_all("KMIA", kmia.GRID_COORDS)
        # Hot and near sea level — DA well above field elevation
        assert data.density_altitude_ft is not None
        assert data.density_altitude_ft > 1500


# ---------------------------------------------------------------------------
# KSEA — Seattle (null-uom grid, PT2H duration expansion, mild temps)
# ---------------------------------------------------------------------------

class TestKSEA:
    def test_fetch_all_succeeds(self, wrapper):
        with patch("requests.get", side_effect=_make_side_effect(
                ksea.METAR, ksea.NWS_OBS, ksea.GRID, ksea.SUMMARY)):
            data = wrapper.fetch_all("KSEA", ksea.GRID_COORDS)
        assert data.station_id == "KSEA"

    def test_null_uom_grid_does_not_crash(self, wrapper):
        df = wrapper.weather_data_to_dataframe(ksea.GRID["properties"])
        assert not df.empty
        assert df["ceilingHeight"].isna().all()
        assert df["visibility"].isna().all()

    def test_temperature(self, wrapper):
        with patch("requests.get", side_effect=_make_side_effect(
                ksea.METAR, ksea.NWS_OBS, ksea.GRID, ksea.SUMMARY)):
            data = wrapper.fetch_all("KSEA", ksea.GRID_COORDS)
        # 24.4°C → 75.92°F
        assert data.temp_f == pytest.approx(75.92, abs=0.1)

    def test_no_gusts(self, wrapper):
        with patch("requests.get", side_effect=_make_side_effect(
                ksea.METAR, ksea.NWS_OBS, ksea.GRID, ksea.SUMMARY)):
            data = wrapper.fetch_all("KSEA", ksea.GRID_COORDS)
        assert data.wind_gust_kt is None

    def test_few_clouds_no_ceiling(self, wrapper):
        with patch("requests.get", side_effect=_make_side_effect(
                ksea.METAR, ksea.NWS_OBS, ksea.GRID, ksea.SUMMARY)):
            data = wrapper.fetch_all("KSEA", ksea.GRID_COORDS)
        assert data.ceiling_ft is None

    def test_wx_condition_from_nws(self, wrapper):
        with patch("requests.get", side_effect=_make_side_effect(
                ksea.METAR, ksea.NWS_OBS, ksea.GRID, ksea.SUMMARY)):
            data = wrapper.fetch_all("KSEA", ksea.GRID_COORDS)
        assert data.wx_condition == "Fair"

    def test_pnw_forecast_contains_cloudy(self, wrapper):
        with patch("requests.get", side_effect=_make_side_effect(
                ksea.METAR, ksea.NWS_OBS, ksea.GRID, ksea.SUMMARY)):
            data = wrapper.fetch_all("KSEA", ksea.GRID_COORDS)
        forecasts = [p["shortForecast"] for p in data.daily_periods]
        assert "Mostly Cloudy" in forecasts

    def test_grid_temperature_fahrenheit(self, wrapper):
        df = wrapper.weather_data_to_dataframe(ksea.GRID["properties"], convert_to_fahrenheit=True)
        # 11.111°C → ~52°F
        assert df["temperature"].iloc[0] == pytest.approx(52.0, abs=0.2)

    def test_multi_hour_duration_expands_rows(self, wrapper):
        # windDirection has a PT2H slot — both hours must get the same value
        df = wrapper.weather_data_to_dataframe(ksea.GRID["properties"])
        t15 = datetime(2026, 5, 21, 15, tzinfo=timezone.utc)
        t16 = datetime(2026, 5, 21, 16, tzinfo=timezone.utc)
        assert df.loc[t15, "windDirection"] == 10
        assert df.loc[t16, "windDirection"] == 10


# ---------------------------------------------------------------------------
# Cross-station: weather_data_to_dataframe edge cases from real responses
# ---------------------------------------------------------------------------

class TestNullUomHandling:
    def test_null_uom_with_empty_values_no_crash(self, wrapper):
        props = {
            "temperature": {
                "uom": "wmoUnit:degC",
                "values": [{"validTime": "2026-05-21T12:00:00+00:00/PT1H", "value": 10}],
            },
            "windDirection": {
                "uom": "wmoUnit:degree_(angle)",
                "values": [{"validTime": "2026-05-21T12:00:00+00:00/PT1H", "value": 180}],
            },
            "windSpeed": {
                "uom": "wmoUnit:km_h-1",
                "values": [{"validTime": "2026-05-21T12:00:00+00:00/PT1H", "value": 10}],
            },
            "windGust": {
                "uom": "wmoUnit:km_h-1",
                "values": [{"validTime": "2026-05-21T12:00:00+00:00/PT1H", "value": None}],
            },
            "ceilingHeight": {"uom": None, "values": []},
            "visibility": {"uom": None, "values": []},
        }
        df = wrapper.weather_data_to_dataframe(props, convert_to_fahrenheit=True)
        assert not df.empty
        assert df["ceilingHeight"].isna().all()
        assert df["visibility"].isna().all()

    def test_negative_ceiling_height_becomes_inf(self, wrapper):
        props = {
            "temperature": {
                "uom": "wmoUnit:degC",
                "values": [{"validTime": "2026-05-21T12:00:00+00:00/PT1H", "value": 20}],
            },
            "windDirection": {
                "uom": "wmoUnit:degree_(angle)",
                "values": [{"validTime": "2026-05-21T12:00:00+00:00/PT1H", "value": 90}],
            },
            "windSpeed": {
                "uom": "wmoUnit:km_h-1",
                "values": [{"validTime": "2026-05-21T12:00:00+00:00/PT1H", "value": 10}],
            },
            "windGust": {
                "uom": "wmoUnit:km_h-1",
                "values": [{"validTime": "2026-05-21T12:00:00+00:00/PT1H", "value": None}],
            },
            "ceilingHeight": {
                "uom": "wmoUnit:m",
                "values": [{"validTime": "2026-05-21T12:00:00+00:00/PT1H", "value": -30.48}],
            },
            "visibility": {
                "uom": "wmoUnit:m",
                "values": [{"validTime": "2026-05-21T12:00:00+00:00/PT1H", "value": 16093}],
            },
        }
        df = wrapper.weather_data_to_dataframe(props)
        assert df["ceilingHeight"].iloc[0] == float("inf")
