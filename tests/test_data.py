"""Tests for the data fetching and parsing layer."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data.models import WeatherData, density_altitude, KORH_ELEVATION_FT
from data.nws_wx_wrapper import NWSWeatherWrapper, _flight_cat_from_values
from tests.fixtures import korh

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def wrapper():
    return NWSWeatherWrapper()


def _resp(data, status=200):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = data
    return m


def _mock_get(metar=None, nws_obs=None, hourly=None, summary=None, grid=None,
              metar_status=200, nws_obs_status=200, hourly_status=200, summary_status=200, grid_status=200):
    """Return a requests.get side_effect that dispatches by URL."""
    metar = metar or korh.METAR
    nws_obs = nws_obs or korh.NWS_OBS
    hourly = hourly or korh.HOURLY_FORECAST
    summary = summary or korh.SUMMARY
    grid = grid or korh.GRID

    def side_effect(url, **kwargs):
        if 'aviationweather' in url:
            return _resp([metar], metar_status)
        if 'observations/latest' in url:
            return _resp(nws_obs, nws_obs_status)
        if '/forecast/hourly' in url:
            return _resp(hourly, hourly_status)
        if '/forecast' in url:
            return _resp(summary, summary_status)
        if 'gridpoints' in url:
            return _resp(grid, grid_status)
        raise ValueError(f"Unexpected URL in mock: {url}")

    return side_effect


# ---------------------------------------------------------------------------
# density_altitude
# ---------------------------------------------------------------------------

class TestDensityAltitude:
    def test_standard_sea_level(self):
        # At sea level, standard pressure, ISA temp (59°F) → DA ≈ 0
        da = density_altitude(59.0, 29.92, elevation_ft=0)
        assert abs(da) < 50  # within 50 ft of 0

    def test_standard_korh(self):
        # At KORH, ISA conditions (altitude-adjusted temp) → DA ≈ KORH elevation
        isa_temp_f = 59.0 - 3.5 * (KORH_ELEVATION_FT / 1000.0)
        da = density_altitude(isa_temp_f, 29.92, KORH_ELEVATION_FT)
        assert abs(da - KORH_ELEVATION_FT) < 50

    def test_hot_day_raises_da(self):
        baseline = density_altitude(59.0, 29.92, 0)
        hot = density_altitude(95.0, 29.92, 0)
        assert hot > baseline + 2000  # hot summer day adds >2000 ft

    def test_low_pressure_raises_da(self):
        standard = density_altitude(59.0, 29.92, 0)
        low_pressure = density_altitude(59.0, 29.00, 0)
        assert low_pressure > standard + 800

    def test_returns_int(self):
        da = density_altitude(70.0, 29.92, KORH_ELEVATION_FT)
        assert isinstance(da, int)


# ---------------------------------------------------------------------------
# _metar_ceiling
# ---------------------------------------------------------------------------

class TestMetarCeiling:
    def test_empty_clouds_returns_none(self, wrapper):
        assert wrapper._metar_ceiling([]) is None

    def test_few_only_returns_none(self, wrapper):
        # FEW (<3/8 coverage) is not a ceiling
        assert wrapper._metar_ceiling([{"cover": "FEW", "base": 25}]) is None

    def test_sct_only_returns_none(self, wrapper):
        # SCT (<5/8 coverage) is not a ceiling
        assert wrapper._metar_ceiling([{"cover": "SCT", "base": 30}]) is None

    def test_bkn_returns_ceiling(self, wrapper):
        assert wrapper._metar_ceiling([{"cover": "BKN", "base": 40}]) == 4000

    def test_ovc_returns_ceiling(self, wrapper):
        assert wrapper._metar_ceiling([{"cover": "OVC", "base": 5}]) == 500

    def test_multiple_layers_picks_lowest(self, wrapper):
        clouds = [
            {"cover": "FEW", "base": 10},
            {"cover": "BKN", "base": 40},
            {"cover": "OVC", "base": 80},
        ]
        assert wrapper._metar_ceiling(clouds) == 4000  # lowest BKN/OVC

    def test_multiple_bkn_picks_lowest(self, wrapper):
        clouds = [
            {"cover": "BKN", "base": 80},
            {"cover": "BKN", "base": 30},
        ]
        assert wrapper._metar_ceiling(clouds) == 3000

    def test_layer_with_null_base_skipped(self, wrapper):
        clouds = [
            {"cover": "BKN", "base": None},
            {"cover": "OVC", "base": 20},
        ]
        assert wrapper._metar_ceiling(clouds) == 2000

    def test_base_in_hundreds_of_feet(self, wrapper):
        # base=10 → 10 × 100 = 1000 ft
        assert wrapper._metar_ceiling([{"cover": "OVC", "base": 10}]) == 1000


# ---------------------------------------------------------------------------
# _parse_visibility
# ---------------------------------------------------------------------------

class TestParseVisibility:
    def test_numeric_string(self, wrapper):
        assert wrapper._parse_visibility("10") == 10.0

    def test_plus_suffix(self, wrapper):
        assert wrapper._parse_visibility("10+") == 10.0

    def test_fraction_quarter(self, wrapper):
        assert wrapper._parse_visibility("1/4") == pytest.approx(0.25)

    def test_fraction_half(self, wrapper):
        assert wrapper._parse_visibility("1/2") == pytest.approx(0.5)

    def test_mixed_fraction(self, wrapper):
        assert wrapper._parse_visibility("1 1/2") == pytest.approx(1.5)

    def test_m_prefix_less_than(self, wrapper):
        # "M1/4" means less than 1/4 SM; treat as 1/4
        assert wrapper._parse_visibility("M1/4") == pytest.approx(0.25)

    def test_numeric_float_passthrough(self, wrapper):
        assert wrapper._parse_visibility(10.0) == 10.0

    def test_none_returns_none(self, wrapper):
        assert wrapper._parse_visibility(None) is None

    def test_integer_passthrough(self, wrapper):
        assert wrapper._parse_visibility(6) == 6.0


# ---------------------------------------------------------------------------
# _parse_obs_time
# ---------------------------------------------------------------------------

class TestParseObsTime:
    def test_unix_timestamp(self, wrapper):
        ts = 1779411240
        dt = wrapper._parse_obs_time(ts)
        assert dt == datetime.fromtimestamp(ts, tz=timezone.utc)
        assert dt.tzinfo is not None

    def test_iso_string_with_z(self, wrapper):
        dt = wrapper._parse_obs_time("2026-05-22T01:00:00Z")
        assert dt.year == 2026
        assert dt.month == 5
        assert dt.tzinfo is not None

    def test_iso_string_with_offset(self, wrapper):
        dt = wrapper._parse_obs_time("2026-05-22T01:25:00+00:00")
        assert dt.year == 2026

    def test_none_returns_recent_datetime(self, wrapper):
        dt = wrapper._parse_obs_time(None)
        now = datetime.now(tz=timezone.utc)
        assert abs((now - dt).total_seconds()) < 5


# ---------------------------------------------------------------------------
# _wx_condition
# ---------------------------------------------------------------------------

class TestWxCondition:
    def test_prefers_nws_text_description(self, wrapper):
        metar = {**korh.METAR, "wxString": "RA"}
        nws_obs = {"properties": {"textDescription": "Light Rain"}}
        assert wrapper._wx_condition(metar, nws_obs) == "Light Rain"

    def test_falls_back_to_decoded_wx_string(self, wrapper):
        metar = {**korh.METAR, "wxString": "-RA"}
        nws_obs = {"properties": {"textDescription": ""}}
        assert wrapper._wx_condition(metar, nws_obs) == "Rain"

    def test_empty_nws_falls_back_to_wx_string(self, wrapper):
        metar = {**korh.METAR, "wxString": "SN"}
        nws_obs = {}
        assert wrapper._wx_condition(metar, nws_obs) == "Snow"

    def test_falls_back_to_flight_category(self, wrapper):
        metar = {**korh.METAR, "wxString": ""}
        nws_obs = {}
        assert wrapper._wx_condition(metar, nws_obs) == "VFR"


class TestDecodeWxString:
    @pytest.mark.parametrize("code,expected", [
        ("TSRA", "Thunderstorm"),
        ("TS",   "Thunderstorm"),
        ("FZRA", "Freezing Rain"),
        ("FZDZ", "Freezing Rain"),
        ("-RA",  "Rain"),
        ("+RA",  "Rain"),
        ("SN",   "Snow"),
        ("SG",   "Snow"),      # snow grains
        ("PL",   "Sleet"),     # ice pellets
        ("GR",   "Hail"),
        ("GS",   "Hail"),      # small hail
        ("-DZ",  "Drizzle"),
        ("FG",   "Fog"),
        ("BR",   "Mist"),
        ("HZ",   "Haze"),
        ("FU",   "Smoke"),
        ("DU",   "Dust"),
        ("SA",   "Dust"),      # sand
    ])
    def test_decode(self, wrapper, code, expected):
        assert wrapper._decode_wx_string(code) == expected

    def test_unknown_code_returned_as_is(self, wrapper):
        assert wrapper._decode_wx_string("ZZZZ") == "ZZZZ"


# ---------------------------------------------------------------------------
# weather_data_to_dataframe — edge cases
# ---------------------------------------------------------------------------

class TestWeatherDataToDataframe:
    def test_null_wind_gust_becomes_nan_not_crash(self, wrapper):
        props = {
            **korh.GRID["properties"],
            "windGust": {
                "uom": "wmoUnit:km_h-1",
                "values": [{"validTime": "2026-05-22T00:00:00+00:00/PT1H", "value": None}],
            },
        }
        df = wrapper.weather_data_to_dataframe(props, convert_to_fahrenheit=True)
        assert pd.isna(df["windGust"].iloc[0])

    def test_null_temperature_becomes_nan_not_crash(self, wrapper):
        props = {
            **korh.GRID["properties"],
            "temperature": {
                "uom": "wmoUnit:degC",
                "values": [{"validTime": "2026-05-22T00:00:00+00:00/PT1H", "value": None}],
            },
        }
        df = wrapper.weather_data_to_dataframe(props, convert_to_fahrenheit=True)
        assert pd.isna(df["temperature"].iloc[0])

    def test_null_ceiling_becomes_inf(self, wrapper):
        df = wrapper.weather_data_to_dataframe(korh.GRID["properties"], convert_to_fahrenheit=True)
        assert df["ceilingHeight"].iloc[0] == float("inf")

    def test_missing_optional_key_excluded_from_df(self, wrapper):
        # All metric_keys are optional — absent keys are skipped, not raised
        props = {k: v for k, v in korh.GRID["properties"].items() if k != "windGust"}
        df = wrapper.weather_data_to_dataframe(props)
        assert "windGust" not in df.columns
        assert not df.empty

    def test_temperature_converted_to_fahrenheit(self, wrapper):
        df = wrapper.weather_data_to_dataframe(korh.GRID["properties"], convert_to_fahrenheit=True)
        # 15°C → 59°F
        assert df["temperature"].iloc[0] == pytest.approx(59.0)

    def test_wind_speed_converted_to_knots(self, wrapper):
        df = wrapper.weather_data_to_dataframe(korh.GRID["properties"])
        # 18.52 km/h × 0.539957 ≈ 10 kt
        assert df["windSpeed"].iloc[0] == 10


# ---------------------------------------------------------------------------
# _flight_cat_from_values — unit tests
# ---------------------------------------------------------------------------

class TestFlightCatFromValues:
    def test_lifr_low_ceiling(self):
        assert _flight_cat_from_values(400, 5.0) == "LIFR"

    def test_lifr_low_visibility(self):
        assert _flight_cat_from_values(5000, 0.5) == "LIFR"

    def test_ifr_ceiling(self):
        assert _flight_cat_from_values(800, 5.0) == "IFR"

    def test_ifr_visibility(self):
        assert _flight_cat_from_values(5000, 2.0) == "IFR"

    def test_mvfr_ceiling(self):
        assert _flight_cat_from_values(2000, 10.0) == "MVFR"

    def test_mvfr_visibility(self):
        assert _flight_cat_from_values(5000, 4.0) == "MVFR"

    def test_vfr(self):
        assert _flight_cat_from_values(5000, 10.0) == "VFR"

    def test_none_ceiling_and_visibility_is_vfr(self):
        assert _flight_cat_from_values(None, None) == "VFR"

    def test_inf_ceiling_high_vis_is_vfr(self):
        assert _flight_cat_from_values(float("inf"), 10.0) == "VFR"


# ---------------------------------------------------------------------------
# fetch_all — integration (mocked HTTP)
# ---------------------------------------------------------------------------

class TestFetchAll:
    def test_normal_case_returns_weather_data(self, wrapper):
        with patch("requests.get", side_effect=_mock_get()):
            data = wrapper.fetch_all("KORH", "45,81")

        assert isinstance(data, WeatherData)
        assert data.station_id == "KORH"
        assert data.temp_f == pytest.approx(wrapper.celsius_to_fahrenheit(13.3))
        assert data.flight_category == "VFR"
        assert data.wx_condition == "Clear"
        assert data.ceiling_ft is None  # CLR sky
        assert not data.hourly_df.empty
        assert len(data.daily_periods) == 2

    def test_altimeter_converted_from_hpa(self, wrapper):
        with patch("requests.get", side_effect=_mock_get()):
            data = wrapper.fetch_all("KORH", "45,81")
        # 1024.5 hPa → ~30.25 inHg
        assert data.altimeter_inhg == pytest.approx(30.25, abs=0.01)

    def test_density_altitude_computed(self, wrapper):
        with patch("requests.get", side_effect=_mock_get()):
            data = wrapper.fetch_all("KORH", "45,81")
        assert data.density_altitude_ft is not None

    def test_missing_temp_yields_none_fields(self, wrapper):
        metar = {**korh.METAR, "temp": None}
        with patch("requests.get", side_effect=_mock_get(metar=metar)):
            data = wrapper.fetch_all("KORH", "45,81")
        assert data.temp_f is None
        assert data.density_altitude_ft is None  # can't compute without temp

    def test_missing_dewpoint_yields_none(self, wrapper):
        metar = {k: v for k, v in korh.METAR.items() if k not in ("dewp", "dwpt")}
        with patch("requests.get", side_effect=_mock_get(metar=metar)):
            data = wrapper.fetch_all("KORH", "45,81")
        assert data.dewpoint_f is None

    def test_calm_winds(self, wrapper):
        metar = {**korh.METAR, "wdir": 0, "wspd": 0}
        with patch("requests.get", side_effect=_mock_get(metar=metar)):
            data = wrapper.fetch_all("KORH", "45,81")
        assert data.wind_dir_deg == 0
        assert data.wind_speed_kt == 0

    def test_no_gust_field_yields_none(self, wrapper):
        metar = {k: v for k, v in korh.METAR.items() if k != "wgst"}
        with patch("requests.get", side_effect=_mock_get(metar=metar)):
            data = wrapper.fetch_all("KORH", "45,81")
        assert data.wind_gust_kt is None

    def test_visibility_string_parsed(self, wrapper):
        metar = {**korh.METAR, "visib": "10+"}
        with patch("requests.get", side_effect=_mock_get(metar=metar)):
            data = wrapper.fetch_all("KORH", "45,81")
        assert data.visibility_sm == 10.0

    def test_low_visibility_fraction_parsed(self, wrapper):
        metar = {**korh.METAR, "visib": "1/4"}
        with patch("requests.get", side_effect=_mock_get(metar=metar)):
            data = wrapper.fetch_all("KORH", "45,81")
        assert data.visibility_sm == pytest.approx(0.25)

    def test_ceiling_computed_from_bkn_layer(self, wrapper):
        metar = {
            **korh.METAR,
            "clouds": [{"cover": "FEW", "base": 10}, {"cover": "BKN", "base": 25}],
        }
        with patch("requests.get", side_effect=_mock_get(metar=metar)):
            data = wrapper.fetch_all("KORH", "45,81")
        assert data.ceiling_ft == 2500

    def test_nws_obs_failure_falls_back_to_metar_wx(self, wrapper):
        metar = {**korh.METAR, "wxString": "SN"}
        with patch("requests.get", side_effect=_mock_get(metar=metar, nws_obs_status=503)):
            data = wrapper.fetch_all("KORH", "45,81")
        assert data.wx_condition == "Snow"

    def test_nws_obs_empty_text_falls_back_to_flight_cat(self, wrapper):
        nws_obs = {"properties": {"textDescription": ""}}
        metar = {**korh.METAR, "wxString": ""}
        with patch("requests.get", side_effect=_mock_get(metar=metar, nws_obs=nws_obs)):
            data = wrapper.fetch_all("KORH", "45,81")
        assert data.wx_condition == "VFR"

    def test_metar_failure_raises(self, wrapper):
        with patch("requests.get", side_effect=_mock_get(metar_status=500)):
            with pytest.raises(Exception):
                wrapper.fetch_all("KORH", "45,81")

    def test_grid_failure_yields_empty_df(self, wrapper):
        # Grid is primary — its failure empties hourly_df
        with patch("requests.get", side_effect=_mock_get(grid_status=503)):
            data = wrapper.fetch_all("KORH", "45,81")
        assert data.hourly_df.empty

    def test_hourly_failure_still_has_df(self, wrapper):
        # Hourly API failure should NOT empty the df — grid is primary
        with patch("requests.get", side_effect=_mock_get(hourly_status=503)):
            data = wrapper.fetch_all("KORH", "45,81")
        assert not data.hourly_df.empty
        assert "flightCategory" in data.hourly_df.columns

    def test_summary_failure_returns_empty_periods(self, wrapper):
        with patch("requests.get", side_effect=_mock_get(summary_status=503)):
            data = wrapper.fetch_all("KORH", "45,81")
        assert data.daily_periods == []

    def test_hourly_df_has_expected_columns(self, wrapper):
        with patch("requests.get", side_effect=_mock_get()):
            data = wrapper.fetch_all("KORH", "45,81")
        expected = {
            "temperature", "dewpoint", "relativeHumidity", "skyCover",
            "windSpeed", "windDirection", "windGust",
            "ceilingHeight", "visibility", "precipChance",
            "shortForecast", "isDaytime", "flightCategory",
        }
        assert expected.issubset(set(data.hourly_df.columns))

    def test_hourly_df_wind_gust_is_nan(self, wrapper):
        # KORH grid fixture has windGust value=None → NaN in df
        with patch("requests.get", side_effect=_mock_get()):
            data = wrapper.fetch_all("KORH", "45,81")
        assert pd.isna(data.hourly_df["windGust"].iloc[0])

    def test_hourly_df_flight_category_vfr(self, wrapper):
        # KORH grid: ceiling=inf (null value), visibility=10sm → all VFR
        with patch("requests.get", side_effect=_mock_get()):
            data = wrapper.fetch_all("KORH", "45,81")
        assert (data.hourly_df["flightCategory"] == "VFR").all()

    def test_dwpt_fallback_field_name(self, wrapper):
        # Older METAR responses use 'dwpt' instead of 'dewp'
        metar = {k: v for k, v in korh.METAR.items() if k != "dewp"}
        metar["dwpt"] = -2.8
        with patch("requests.get", side_effect=_mock_get(metar=metar)):
            data = wrapper.fetch_all("KORH", "45,81")
        assert data.dewpoint_f == pytest.approx(wrapper.celsius_to_fahrenheit(-2.8))

    def test_fltcat_lowercase_fallback(self, wrapper):
        # Some responses use 'fltcat' (lowercase) instead of 'fltCat'
        metar = {k: v for k, v in korh.METAR.items() if k != "fltCat"}
        metar["fltcat"] = "IFR"
        with patch("requests.get", side_effect=_mock_get(metar=metar)):
            data = wrapper.fetch_all("KORH", "45,81")
        assert data.flight_category == "IFR"
