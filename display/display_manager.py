from __future__ import annotations

import math
import os
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
from pathlib import Path
import logging

import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageChops

from data.models import WeatherData
from display.icons import get_icon_path

logger = logging.getLogger()

WIDTH = 800
HEIGHT = 480


def _is_nan(v) -> bool:
    try:
        return math.isnan(v)
    except (TypeError, ValueError):
        return False


def _flight_category(ceiling_ft, visibility_sm) -> str:
    ceiling = float('inf') if ceiling_ft is None or _is_nan(ceiling_ft) else float(ceiling_ft)
    vis = float('inf') if visibility_sm is None or _is_nan(visibility_sm) else float(visibility_sm)
    if ceiling < 500 or vis < 1:
        return 'LIFR'
    if ceiling < 1000 or vis < 3:
        return 'IFR'
    if ceiling < 3000 or vis < 5:
        return 'MVFR'
    return 'VFR'


def _filter_daily_periods(periods: list) -> list:
    """Return daytime-only periods; keep the first period if it is a night period
    (i.e. current time is night, so 'Tonight' should be shown)."""
    if not periods:
        return []
    result = []
    start = 0
    if not periods[0].get('isDaytime', True):
        result.append(periods[0])
        start = 1
    result.extend(p for p in periods[start:] if p.get('isDaytime', True))
    return result


def _period_start_utc(p: dict) -> datetime | None:
    """Parse a period's startTime to a UTC datetime, return None on failure."""
    raw = p.get('startTime')
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).astimezone(timezone.utc)
    except Exception:
        return None


def _period_end_utc(p: dict) -> datetime | None:
    raw = p.get('endTime')
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).astimezone(timezone.utc)
    except Exception:
        return None


def _compute_time_window(periods: list, now_utc: datetime) -> tuple[datetime, datetime]:
    """Return (window_start, window_end) snapped to local calendar-day (midnight) boundaries.

    window_start = midnight of today (Eastern)
    window_end   = midnight of (last period's local date + 1 day)
    """
    today_midnight = now_utc.astimezone(EASTERN).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    window_start = today_midnight.astimezone(timezone.utc)

    if not periods:
        return window_start, window_start + timedelta(days=7)

    last_start = _period_start_utc(periods[-1])
    if last_start:
        last_date = last_start.astimezone(EASTERN).date()
        last_midnight = datetime(last_date.year, last_date.month, last_date.day,
                                  tzinfo=EASTERN) + timedelta(days=1)
        window_end = last_midnight.astimezone(timezone.utc)
    else:
        window_end = window_start + timedelta(days=7)

    return window_start, window_end


def _time_to_x(t: datetime, window_start: datetime, window_end: datetime) -> int:
    total = (window_end - window_start).total_seconds()
    if total <= 0:
        return 0
    return max(0, min(WIDTH, int((t - window_start).total_seconds() / total * WIDTH)))




def _relative_humidity(temp_f: float, dewpoint_f: float) -> int:
    tc = (temp_f - 32) * 5 / 9
    td = (dewpoint_f - 32) * 5 / 9
    rh = 100 * math.exp(17.625 * td / (243.04 + td)) / math.exp(17.625 * tc / (243.04 + tc))
    return round(min(100, max(0, rh)))


class DisplayManager:
    def __init__(self, dev_mode=True):
        self.dev_mode = dev_mode

        self.font12: ImageFont = None
        self.font18: ImageFont = None
        self.font24: ImageFont = None
        self.font35: ImageFont = None

        if not dev_mode:
            self.epd = self.init_display()

        self.image = self.init_image()
        self.draw = self.init_draw(self.image)

        self.load_fonts()

    def init_display(self):
        from display.epd_interface import EPD
        epd = EPD()
        return epd

    def init_image(self):
        return Image.new('1', (WIDTH, HEIGHT), 255)

    def init_draw(self, image: Image):
        return ImageDraw.Draw(image)

    def load_fonts(self):
        picdir = Path(__file__).resolve().parent / 'pic'
        self.font24 = ImageFont.truetype(str(picdir / 'Font.ttc'), 24)
        self.font18 = ImageFont.truetype(str(picdir / 'Font.ttc'), 18)
        self.font35 = ImageFont.truetype(str(picdir / 'Font.ttc'), 35)
        self.font12 = ImageFont.truetype(str(picdir / 'Font.ttc'), 14)

    def get_text_size(self, draw, text, font):
        if hasattr(draw, 'textbbox'):
            bbox = draw.textbbox((0, 0), text, font=font)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]
        else:
            return draw.textsize(text, font=font)

    def render_display(self, data: WeatherData):
        # Reset image for a fresh render each cycle
        self.image = self.init_image()
        self.draw = self.init_draw(self.image)

        self.draw.text((10, 10), data.station_id, font=self.font35, fill=0)

        elapsed = self._elapsed_str(data.obs_time)
        self.draw_right_aligned_text(elapsed, 10, 10, self.font18)

        self.draw_current_icon(data.wx_condition, data.station_id)

        summary_info = self.draw_summary_grid(data)

        center_x = None
        if summary_info and 'left_x' in summary_info:
            try:
                center_x = int(summary_info['left_x'] + 1.5 * summary_info['cell_w'])
            except Exception:
                pass

        self.draw_current_time(data.obs_time, center_x=center_x)
        self.draw_hourly_grid(data.hourly_df)
        filtered_periods = _filter_daily_periods(data.daily_periods)
        now_utc = datetime.now(tz=timezone.utc)
        window_start, window_end = _compute_time_window(filtered_periods, now_utc)
        self.draw_daily_grid(filtered_periods, window_start, window_end, hourly_df=data.hourly_df)

        if not self.dev_mode:
            logger.info("Init EPD")
            self.epd.init()
            self.epd.display(self.epd.getbuffer(self.image))
            logger.info("EPD sleep")
            self.epd.sleep()
        else:
            self.save_display_preview('weather_preview.png')

    def _elapsed_str(self, obs_time: datetime) -> str:
        delta = datetime.now(tz=timezone.utc) - obs_time
        mins = max(0, int(delta.total_seconds() / 60))
        if mins < 1:
            return "just now"
        if mins < 60:
            return f"{mins}m ago"
        return f"{mins // 60}h {mins % 60}m ago"

    def draw_current_time(self, obs_time: datetime, center_x: int = None):
        local_dt = obs_time.astimezone(EASTERN) if isinstance(obs_time, datetime) else obs_time.to_pydatetime().astimezone(EASTERN)
        text = local_dt.strftime("%A, %b %-d, %H:%M %Z")

        font = self.font18
        text_w, text_h = self.get_text_size(self.draw, text, font=font)
        if center_x is None:
            x = (WIDTH - text_w) // 2
        else:
            x = int(center_x - text_w // 2)
        y = 10
        self.draw.text((x, y), text, font=font, fill=0)
        return y + text_h

    def _is_night_now(self) -> bool:
        """Return True if the current local time is between sunset and sunrise."""
        try:
            from astral import LocationInfo
            from astral.sun import sun as astral_sun
            observer = LocationInfo(latitude=42.2673, longitude=-71.8752).observer
            now = datetime.now(tz=EASTERN)
            s = astral_sun(observer, date=now.date(), tzinfo=EASTERN)
            return not (s['sunrise'] <= now <= s['sunset'])
        except Exception:
            return False

    def _get_sun_events(self, rows: list) -> list:
        """Return list parallel to rows; each entry is None or ('rise'/'set', datetime)."""
        try:
            from astral import LocationInfo
            from astral.sun import sun as astral_sun
        except ImportError:
            return [None] * len(rows)

        observer = LocationInfo(latitude=42.2673, longitude=-71.8752).observer

        dates = set()
        for row in rows:
            if row is not None:
                dates.add(row.name.to_pydatetime().astimezone(EASTERN).date())

        all_events = []
        for d in dates:
            s = astral_sun(observer, date=d, tzinfo=EASTERN)
            all_events.append(('rise', s['sunrise']))
            all_events.append(('set', s['sunset']))

        result = []
        for row in rows:
            if row is None:
                result.append(None)
                continue
            ts = row.name.to_pydatetime()
            end = ts + timedelta(hours=1)
            match = next(
                (ev for ev in all_events if ts <= ev[1] < end),
                None,
            )
            result.append(match)
        return result

    def draw_hourly_grid(self, hourly_df: pd.DataFrame):
        top_y = 210
        self.draw.line([(0, top_y), (WIDTH, top_y)], fill='black', width=2)

        bottom_y = 375
        num_lines = 12
        for i in range(1, num_lines + 1):
            x = int(i * WIDTH / (num_lines + 1))
            self.draw.line([(x, top_y), (x, bottom_y)], fill='black', width=2)

        num_boxes = num_lines + 1  # 13

        now_utc = datetime.now(tz=timezone.utc)
        if not hourly_df.empty:
            future_df = hourly_df[hourly_df.index >= now_utc]
            rows = [future_df.iloc[i] if i < len(future_df) else None for i in range(num_boxes)]
        else:
            rows = [None] * num_boxes

        sun_events = self._get_sun_events(rows)

        for i, row in enumerate(rows):
            left = int(round(i * WIDTH / num_boxes))
            right = int(round((i + 1) * WIDTH / num_boxes))
            cell_w = right - left
            padding = 6
            inner_x = left + padding
            inner_w = cell_w - padding * 2
            inner_h = bottom_y - top_y - padding * 2
            self.draw_hourly_block(inner_x, top_y + padding, inner_w, inner_h, row, sun_event=sun_events[i])

    def draw_daily_grid(self, daily_periods: list, window_start: datetime = None,
                        window_end: datetime = None, hourly_df: pd.DataFrame = None):
        top_y = 375
        self.draw.line([(0, top_y), (WIDTH, top_y)], fill='black', width=2)

        flight_band_height = 20
        band_top = HEIGHT - flight_band_height  # 460
        padding = 6

        periods = list(daily_periods or [])
        if not periods:
            return

        now_utc = datetime.now(tz=timezone.utc)
        if window_start is None or window_end is None:
            window_start, window_end = _compute_time_window(periods, now_utc)

        # Each period maps to its calendar-day column: local midnight → midnight
        columns = []
        for i, period in enumerate(periods):
            period_start = _period_start_utc(period)
            if period_start:
                col_date = period_start.astimezone(EASTERN).date()
            else:
                col_date = (now_utc + timedelta(days=i)).astimezone(EASTERN).date()
            col_start = datetime(col_date.year, col_date.month, col_date.day,
                                  tzinfo=EASTERN).astimezone(timezone.utc)
            col_end = col_start + timedelta(days=1)
            x0 = _time_to_x(col_start, window_start, window_end)
            x1 = _time_to_x(col_end, window_start, window_end)
            columns.append((x0, x1, col_start, col_end))

        # Determine if today's column should use night icons (after sunset)
        today_is_night = self._is_night_now()
        today_date = now_utc.astimezone(EASTERN).date()

        # Draw day block content (dividers drawn last so they sit on top of band fills)
        for period, (x0, x1, col_start, col_end) in zip(periods, columns):
            cell_w = x1 - x0
            if cell_w > padding * 2:
                col_date = col_start.astimezone(EASTERN).date()
                is_night = today_is_night and col_date == today_date
                self.draw_daily_block(x0 + padding, top_y + padding,
                                       cell_w - padding * 2, band_top - top_y - padding * 2, period,
                                       is_night=is_night)

        # Flight category band — fills rendered before column dividers
        self._draw_flight_band(hourly_df, columns, window_start, window_end,
                                flight_band_height, now_utc)

        # Column dividers span the day grid only; flight band is a continuous bar
        for i, (x0, x1, col_start, col_end) in enumerate(columns):
            if i < len(columns) - 1:
                self.draw.line([(x1, top_y), (x1, band_top)], fill='black', width=2)

    def draw_daily_block(self, x, y, w, h, period: dict | None, is_night: bool = False):
        if period is None:
            return

        name = period.get('name', '')
        temp = period.get('temperature')
        temp_unit = period.get('temperatureUnit', 'F')
        forecast = period.get('shortForecast', '')

        label_font = self.font12
        label_w, label_h = self.get_text_size(self.draw, name, font=label_font)
        label_x = x + (w - label_w) // 2
        self.draw.text((label_x, y), name, font=label_font, fill=0)

        icon_top = y + label_h + 4
        icon_path = str(get_icon_path(forecast, is_night=is_night))
        try:
            orig = Image.open(icon_path)
            ow, oh = orig.size
            max_icon_h = h - label_h - 20
            icon_scale = min(w / ow, max_icon_h / oh, 0.5) if ow > 0 and oh > 0 else 0.3
            icon_cx = x + w // 2
            icon_x = int(icon_cx - (ow * icon_scale) // 2)
            self.scale_and_display_bmp(icon_path, position=(max(0, icon_x), icon_top), scale_factor=icon_scale)
            icon_bottom = icon_top + int(oh * icon_scale)
        except Exception:
            icon_bottom = icon_top

        if temp is not None:
            temp_text = f"{temp}°{temp_unit}"
            t_w, t_h = self.get_text_size(self.draw, temp_text, font=label_font)
            t_x = x + (w - t_w) // 2
            t_y = y + h - t_h - 4
            self.draw.text((t_x, t_y), temp_text, font=label_font, fill=0)

    def draw_hourly_block(self, x, y, w, h, row: pd.Series | None, sun_event=None):
        if row is None:
            return

        small_font = self.font12
        spacing = 4
        center_x = x + w // 2
        cursor_y = y + 2  # 2px top margin above time label

        # Hour label (local time) — convert Timestamp → datetime for astimezone()
        local_dt = row.name.to_pydatetime().astimezone(EASTERN)
        hour_label = local_dt.strftime("%-H:%M")
        hw, hh = self.get_text_size(self.draw, hour_label, font=small_font)
        self.draw.text((int(center_x - hw // 2), cursor_y), hour_label, font=small_font, fill=0)
        cursor_y += hh + spacing

        cat = row.get('flightCategory') or 'VFR'

        # Weather icon
        cursor_y += 8
        forecast = row.get('shortForecast') or ''
        is_night = not bool(row.get('isDaytime', True))
        icon_path = str(get_icon_path(forecast, is_night=is_night))
        try:
            orig = Image.open(icon_path)
            ow, oh = orig.size
            max_icon = min(w, h // 3)
            icon_scale = min(max_icon / ow, max_icon / oh, 0.4) if ow > 0 and oh > 0 else 0.3
            icon_x = int(center_x - (ow * icon_scale) // 2)
            self.scale_and_display_bmp(icon_path, position=(max(0, icon_x), cursor_y), scale_factor=icon_scale)
            cursor_y += int(oh * icon_scale) + spacing
        except Exception:
            icon_r = max(6, min(w, h) // 12)
            icon_cy = cursor_y + icon_r
            self.draw.ellipse(
                [center_x - icon_r, icon_cy - icon_r, center_x + icon_r, icon_cy + icon_r],
                outline=0, width=1,
            )
            cursor_y = icon_cy + icon_r + spacing

        # Sunrise/sunset indicator below the weather icon
        if sun_event is not None:
            ev_type, ev_time = sun_event
            # picdir = Path(__file__).resolve().parent / 'pic'
            # icon_file = 'wi-sunrise.bmp' if ev_type == 'rise' else 'wi-sunset.bmp'
            # sun_icon_path = str(picdir / icon_file)
            # sun_icon_size = 18
            # try:
            #     orig = Image.open(sun_icon_path)
            #     ow, oh = orig.size
            #     sun_scale = sun_icon_size / max(ow, oh)
            #     sun_iw, sun_ih = int(ow * sun_scale), int(oh * sun_scale)
            #     ix = int(center_x - sun_iw // 2)
            #     self.scale_and_display_bmp(sun_icon_path, position=(max(0, ix), cursor_y), scale_factor=sun_scale)
            #     cursor_y += sun_ih + 1
            # except Exception:
            #     pass
            ev_label = ev_time.astimezone(EASTERN).strftime("%-H:%M")
            ew, eh = self.get_text_size(self.draw, ev_label, font=small_font)
            cursor_y -= 6
            self.draw.text((int(center_x - ew // 2), cursor_y), ev_label, font=small_font, fill=0)
            cursor_y += eh + spacing

        # Build the bottom-pinned text block: cat, wind dir, wind speed, temp, precip
        wind_dir = row.get('windDirection')
        wind_spd = row.get('windSpeed')
        wind_gst = row.get('windGust')
        temp = row.get('temperature')
        precip = row.get('precipChance')

        # bottom_lines entries: (text, w, h, icon_path_or_None)
        bottom_lines = []
        cat_w, cat_h = self.get_text_size(self.draw, cat, font=small_font)
        bottom_lines.append((cat, cat_w, cat_h, None))

        if wind_dir is not None and not _is_nan(wind_dir):
            wd_text = f"{int(wind_dir):03d}°"
            wd_w, wd_h = self.get_text_size(self.draw, wd_text, font=small_font)
            bottom_lines.append((wd_text, wd_w, wd_h, None))

        if wind_spd is not None and not _is_nan(wind_spd):
            if wind_gst is not None and not _is_nan(wind_gst) and int(wind_gst) > 10:
                wind_text = f"{int(wind_spd)}-{int(wind_gst)}"
            else:
                wind_text = f"{int(wind_spd)} kts"
            w_w, w_h = self.get_text_size(self.draw, wind_text, font=small_font)
            bottom_lines.append((wind_text, w_w, w_h, None))

        if temp is not None and not _is_nan(temp):
            temp_text = f"{round(temp)}°F"
            t_w, t_h = self.get_text_size(self.draw, temp_text, font=small_font)
            bottom_lines.append((temp_text, t_w, t_h, None))

        if precip is not None and not _is_nan(precip):
            precip_text = f"{int(precip)}%"
            p_w, p_h = self.get_text_size(self.draw, precip_text, font=small_font)
            forecast_str = (row.get('shortForecast') or '').lower()
            is_snow = any(kw in forecast_str for kw in ('snow', 'flurr', 'blizzard', 'sleet', 'wintry'))
            picdir = Path(__file__).resolve().parent / 'pic'
            precip_icon = str(picdir / ('wi-snowflake-cold.bmp' if is_snow else 'wi-raindrop.bmp'))
            bottom_lines.append((precip_text, p_w, p_h, precip_icon))

        # Pin block to bottom with 2px margin; never overlap the icon
        total_h = sum(lh + spacing for _, _, lh, _ in bottom_lines) - spacing
        text_y = max(cursor_y, y + h - total_h - 2)
        for line_text, line_w, line_h, icon_path in bottom_lines:
            if icon_path and os.path.exists(icon_path):
                try:
                    orig = Image.open(icon_path)
                    ow, oh = orig.size
                    icon_scale = line_h * 2 / oh
                    icon_w = int(ow * icon_scale)
                    gap = 2
                    total_w = icon_w + gap + line_w
                    start_x = int(center_x - total_w // 2)
                    self.scale_and_display_bmp(icon_path, position=(max(0, start_x), text_y), scale_factor=icon_scale)
                    self.draw.text((start_x - 4 + icon_w + gap, text_y), line_text, font=small_font, fill=0)
                except Exception:
                    self.draw.text((int(center_x - line_w // 2), text_y), line_text, font=small_font, fill=0)
            else:
                self.draw.text((int(center_x - line_w // 2), text_y), line_text, font=small_font, fill=0)
            text_y += line_h + spacing

    def _draw_flight_band(self, hourly_df: pd.DataFrame, columns: list,
                           window_start: datetime, window_end: datetime,
                           flight_band_height: int, now_utc: datetime):
        top_y = HEIGHT - flight_band_height
        self.draw.line([(0, top_y), (WIDTH, top_y)], fill='black', width=2)

        now_x = _time_to_x(now_utc, window_start, window_end)

        # Future category fills rendered per column — x-bounds match day column dividers exactly
        if hourly_df is not None and not hourly_df.empty:
            for x0, x1, col_start, col_end in columns:
                col_df = hourly_df[
                    (hourly_df.index >= max(now_utc, col_start)) &
                    (hourly_df.index < col_end)
                ]
                run_cat = run_rx0 = run_rx1 = None
                for ts, row in col_df.iterrows():
                    ts_dt = ts.to_pydatetime()
                    rx0 = max(x0, _time_to_x(ts_dt, window_start, window_end))
                    rx1 = min(x1, _time_to_x(ts_dt + timedelta(hours=1), window_start, window_end))
                    if rx0 >= rx1:
                        continue
                    cat = row.get('flightCategory') or 'VFR'
                    if cat == run_cat:
                        run_rx1 = rx1
                    else:
                        if run_cat is not None:
                            self._draw_cat_fill(run_cat, run_rx0, run_rx1, top_y)
                        run_cat, run_rx0, run_rx1 = cat, rx0, rx1
                if run_cat is not None:
                    self._draw_cat_fill(run_cat, run_rx0, run_rx1, top_y)

        # Elapsed fill (diagonal stripes) drawn after category fills to cover the past cleanly
        if now_x > 0:
            self._draw_elapsed_fill(0, now_x, top_y)

        # Now tick
        if 0 < now_x < WIDTH:
            self.draw.line([(now_x, top_y - 5), (now_x, HEIGHT)], fill=0, width=3)

        self.draw.line([(WIDTH - 1, top_y), (WIDTH - 1, HEIGHT)], fill='black', width=1)

    def _draw_cat_fill(self, cat: str, x0: int, x1: int, top_y: int):
        if cat == 'VFR':
            pass
        elif cat == 'MVFR':
            tile = 2
            for xi in range(x0, x1, tile):
                for yi in range(top_y, HEIGHT, tile):
                    if (xi // tile + yi // tile) % 2 == 0:
                        self.draw.rectangle(
                            [(xi, yi), (min(xi + tile - 1, x1), min(yi + tile - 1, HEIGHT))],
                            fill=0,
                        )
        else:
            self.draw.rectangle([(x0, top_y), (x1, HEIGHT)], fill=0)

    def _draw_elapsed_fill(self, x0: int, x1: int, top_y: int):
        """Diagonal \ stripes to mark time that has already passed."""
        stripe = 4
        bar_h = HEIGHT - top_y
        for offset in range(-(bar_h - 1), x1 - x0, stripe):
            ax = x0 + offset
            bx = ax + bar_h - 1
            ay, by = top_y, HEIGHT - 1
            if ax < x0:
                ay += x0 - ax
                ax = x0
            if bx >= x1:
                by -= bx - (x1 - 1)
                bx = x1 - 1
            if ax <= bx and ay <= by:
                self.draw.line([(ax, ay), (bx, by)], fill=0, width=1)

    def draw_right_aligned_text(self, text, y, margin, font, fill=0):
        text_width, text_height = self.get_text_size(self.draw, text, font=font)
        x = self.image.width - text_width - margin
        self.draw.text((x, y), text, font=font, fill=fill)
        return y + text_height

    def save_display_preview(self, filename=None, scale=2):
        import datetime

        if filename is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"eink_preview_{timestamp}.png"

        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)

        preview_image = self.image.copy()

        if preview_image.mode == '1':
            preview_image = preview_image.convert('RGB')
            pixels = preview_image.load()
            width, height = preview_image.size
            for x in range(width):
                for y in range(height):
                    r, g, b = pixels[x, y]
                    if r > 200 and g > 200 and b > 200:
                        pixels[x, y] = (245, 245, 240)

        if scale != 1:
            width, height = preview_image.size
            preview_image = preview_image.resize((width * scale, height * scale), Image.LANCZOS)

        preview_image.save(filename)
        print(f"Preview saved to: {filename}")

        return filename

    def draw_current_icon(self, condition: str, station_id: str = "KORH"):
        icon_path = str(get_icon_path(condition, is_night=self._is_night_now()))

        korh_w, _ = self.get_text_size(self.draw, station_id, font=self.font35)

        icon_top_y = 50

        if os.path.exists(icon_path):
            try:
                orig = Image.open(icon_path)
                ow, oh = orig.size
            except Exception:
                ow, oh = (64, 64)
        else:
            ow, oh = (64, 64)

        scale_factor = 0.9
        scaled_w = int(ow * scale_factor)
        scaled_h = int(oh * scale_factor)

        korh_x = 8
        icon_x = korh_x + max(0, (korh_w - scaled_w) // 2) + 4
        icon_x = max(0, min(icon_x, WIDTH - scaled_w))

        try:
            self.scale_and_display_bmp(icon_path, position=(int(icon_x), int(icon_top_y)), scale_factor=scale_factor)
        except Exception:
            try:
                self.scale_and_display_bmp(icon_path, position=(0, icon_top_y), scale_factor=scale_factor)
            except Exception:
                pass

        try:
            lw, lh = self.get_text_size(self.draw, condition, font=self.font18)
            icon_cx = icon_x + scaled_w / 2
            label_x = int(icon_cx - lw / 2)
            label_y = int(icon_top_y + scaled_h)
            label_x = max(0, min(label_x, WIDTH - lw))
            self.draw.text((label_x, label_y), condition, font=self.font18, fill=0)
        except Exception:
            pass

    def draw_summary_grid(self, data: WeatherData, left_x=None, top_y=None):
        margin = 5
        if left_x is None:
            left_x = margin + 100
        if top_y is None:
            top_y = 35

        right_x = WIDTH - margin - 50
        bottom_y = 215 - margin

        grid_w = right_x - left_x
        grid_h = bottom_y - top_y
        if grid_w <= 0 or grid_h <= 0:
            return

        cols = 3
        rows = 3
        cell_w = grid_w // cols
        cell_h = grid_h // rows

        ceiling_text = "CLR" if (data.ceiling_ft is None or data.ceiling_ft == float('inf')) else f"{data.ceiling_ft:,}'"
        vis_text = f"{data.visibility_sm} sm" if data.visibility_sm is not None else "N/A"

        if data.temp_f is not None:
            temp_c = round((data.temp_f - 32) * 5 / 9)
            temp_text = f"{round(data.temp_f)}°F ({temp_c}°C)"
        else:
            temp_text = "N/A"

        wind_parts = []
        if data.wind_variable:
            wind_parts.append("VAR")
        elif data.wind_dir_deg is not None:
            wind_parts.append(f"{data.wind_dir_deg:03d}°")
        if data.wind_speed_kt is not None:
            if data.wind_gust_kt is not None:
                wind_parts.append(f"@ {data.wind_speed_kt}-{data.wind_gust_kt}")
            else:
                wind_parts.append(f"@ {data.wind_speed_kt}")
        wind_text = " ".join(wind_parts) if wind_parts else "N/A"

        altim_text = f"{data.altimeter_inhg:.2f}" if data.altimeter_inhg is not None else "N/A"

        if data.dewpoint_f is not None and data.temp_f is not None:
            rh = _relative_humidity(data.temp_f, data.dewpoint_f)
            dewpt_text = f"{round(data.dewpoint_f)}°F / {rh}%"
        elif data.dewpoint_f is not None:
            dewpt_text = f"{round(data.dewpoint_f)}°F"
        else:
            dewpt_text = "N/A"

        if data.density_altitude_ft is not None:
            da = data.density_altitude_ft
            da_text = f"+{da:,}'" if da >= 0 else f"{da:,}'"
        else:
            da_text = "N/A"

        cells = [
            {'big': data.flight_category or 'N/A', 'label': 'FLIGHT CAT'},
            {'big': ceiling_text,                   'label': 'CEILING'},
            {'big': vis_text,                        'label': 'VISIBILITY'},
            {'big': temp_text,                       'label': 'TEMPERATURE'},
            {'big': wind_text,                       'label': 'WIND (KTS)'},
            {'big': altim_text,                      'label': 'ALTIMETER'},
            {'big': dewpt_text,                      'label': 'DEWPT / RH'},
            {'big': da_text,                         'label': 'DENSITY ALT'},
            {'big': data.wx_condition or 'N/A',      'label': 'CONDITION'},
        ]

        value_font = self.font24
        label_font = self.font12

        for idx, cell in enumerate(cells):
            col = idx % cols
            row = idx // cols
            x0 = left_x + col * cell_w
            y0 = top_y + row * cell_h

            big = cell['big']
            label = cell['label']

            # Use raw textbbox offsets so visual_gap is the real pixel gap
            b_bb = self.draw.textbbox((0, 0), big, font=value_font)
            l_bb = self.draw.textbbox((0, 0), label, font=label_font)
            b_vis_h = b_bb[3] - b_bb[1]   # actual rendered pixel height of value
            l_vis_h = l_bb[3] - l_bb[1]   # actual rendered pixel height of label
            bw = b_bb[2] - b_bb[0]
            lw = l_bb[2] - l_bb[0]

            visual_gap = 6
            total_vis_h = b_vis_h + visual_gap + l_vis_h
            visual_top = y0 + (cell_h - total_vis_h) // 2

            # Shift anchor so rendered pixels start at visual_top
            value_y = visual_top - b_bb[1]
            label_y = visual_top + b_vis_h + visual_gap - l_bb[1]

            self.draw.text((x0 + (cell_w - bw) // 2, value_y), big, font=value_font, fill=0)
            self.draw.text((x0 + (cell_w - lw) // 2, label_y), label, font=label_font, fill=0)

        return {
            'left_x': left_x,
            'top_y': top_y,
            'cols': cols,
            'rows': rows,
            'cell_w': cell_w,
            'cell_h': cell_h,
            'right_x': right_x,
            'bottom_y': bottom_y,
        }

    def scale_and_display_bmp(self, bmp_path, position=(0, 0), scale_factor=.9, inverted=False):
        if not os.path.exists(bmp_path):
            raise FileNotFoundError(f"BMP file not found: {bmp_path}")

        original_image = Image.open(bmp_path)
        width, height = original_image.size
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)

        if scale_factor != 1.0:
            scaled_image = original_image.resize((new_width, new_height), Image.LANCZOS)
        else:
            scaled_image = original_image

        if scaled_image.mode != '1':
            scaled_image = scaled_image.convert('1')

        if inverted:
            scaled_image = ImageChops.invert(scaled_image)

        self.image.paste(scaled_image, position)

    def draw_wind_barb(self, center_x, center_y, wind_speed, wind_direction, scale=1.0,
                       color='black', line_width=3, barb_angle=290):
        if wind_speed < 3:
            radius = int(6 * scale)
            bbox = [center_x - radius, center_y - radius, center_x + radius, center_y + radius]
            self.draw.ellipse(bbox, outline=color, width=line_width)
            return

        staff_length = int(40 * scale)
        barb_length = int(15 * scale)
        pennant_width = int(15 * scale)

        staff_angle_rad = math.radians(90 - wind_direction)

        start_x = center_x - (staff_length / 2) * math.cos(staff_angle_rad)
        start_y = center_y + (staff_length / 2) * math.sin(staff_angle_rad)
        end_x = center_x + (staff_length / 2) * math.cos(staff_angle_rad)
        end_y = center_y - (staff_length / 2) * math.sin(staff_angle_rad)

        self.draw.line([(start_x, start_y), (end_x, end_y)], fill=color, width=line_width)

        staff_unit_x = math.cos(staff_angle_rad)
        staff_unit_y = -math.sin(staff_angle_rad)

        barb_angle_rad = math.radians(barb_angle)
        barb_direction_rad = staff_angle_rad + barb_angle_rad

        barb_unit_x = math.cos(barb_direction_rad)
        barb_unit_y = -math.sin(barb_direction_rad)

        speed_remaining = wind_speed
        barb_spacing = 0.1 * staff_length

        if 3 < wind_speed < 8:
            barb_start_offset = int(5 * scale)
        else:
            barb_start_offset = 0

        current_x = end_x - barb_start_offset * staff_unit_x
        current_y = end_y - barb_start_offset * staff_unit_y

        while speed_remaining >= 50:
            tip_x = current_x + pennant_width * barb_unit_x
            tip_y = current_y + pennant_width * barb_unit_y
            base_x = current_x - (barb_spacing * 0.8) * staff_unit_x
            base_y = current_y - (barb_spacing * 0.8) * staff_unit_y
            self.draw.polygon([(current_x, current_y), (tip_x, tip_y), (base_x, base_y)], fill=color)
            current_x -= barb_spacing * staff_unit_x * 1.2
            current_y -= barb_spacing * staff_unit_y * 1.2
            speed_remaining -= 50

        while speed_remaining >= 10:
            barb_end_x = current_x + barb_length * barb_unit_x
            barb_end_y = current_y + barb_length * barb_unit_y
            self.draw.line([(current_x, current_y), (barb_end_x, barb_end_y)], fill=color, width=line_width)
            current_x -= barb_spacing * staff_unit_x
            current_y -= barb_spacing * staff_unit_y
            speed_remaining -= 10

        if speed_remaining >= 5:
            half_barb_end_x = current_x + (barb_length / 2) * barb_unit_x
            half_barb_end_y = current_y + (barb_length / 2) * barb_unit_y
            self.draw.line(
                [(current_x, current_y), (half_barb_end_x, half_barb_end_y)],
                fill=color, width=line_width,
            )
