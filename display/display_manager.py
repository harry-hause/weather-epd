import math
import os
import time
from pathlib import Path
import logging
from PIL import Image,ImageDraw,ImageFont, ImageChops

logger = logging.getLogger()

WIDTH = 800
HEIGHT = 480

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
        
        logger.info("Init EPD display")
        epd.init()

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
        self.font12 = ImageFont.truetype(str(picdir / 'Font.ttc'), 12)

    def get_text_size(self, draw, text, font):
        # Try the new method first (Pillow 8.0.0+)
        if hasattr(draw, 'textbbox'):
            bbox = draw.textbbox((0, 0), text, font=font)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]
        # Fall back to the old method (Pillow < 10.0.0)
        else:
            return draw.textsize(text, font=font)


    def render_display(self):
        self.draw.text((10, 10), f"KORH", font=self.font35, fill=0)
        self.draw_right_aligned_text("39m ago", 10, 10, self.font18)

        self.draw_current_icon()


        # self.draw_wind_barb(40, 175, 15, 120, scale=1.5)

        # Draw the 3x3 summary grid to the right of the large icon / wind barb
        summary_info = self.draw_summary_grid()

        # Center the date/time above the middle column of the summary grid
        if summary_info and 'left_x' in summary_info:
            # middle column center = left_x + 1.5 * cell_w
            try:
                center_x = int(summary_info['left_x'] + 1.5 * summary_info['cell_w'])
            except Exception:
                center_x = None
        else:
            center_x = None

        self.draw_current_time(center_x=center_x)

        self.draw_hourly_grid()
        self.draw_daily_grid()
        self.draw_flight_category_bar(flight_band_height=20)

        if not self.dev_mode:
            self.epd.display(self.epd.getbuffer(self.image))
            time.sleep(20)
        else:
            self.save_display_preview('weather_preview.png')

    def draw_current_time(self, center_x: int = None):
        """Draw the current local time (mocked) centered at the top.

        If center_x is provided, center the text at that x-coordinate; otherwise
        center in the full display width.

        Format (mock for now): "Sunday, Jan 25, 16:00 EST"
        """
        mock = "Sunday, Jan 25, 16:00 EST"

        font = self.font18 or self.font24
        text_w, text_h = self.get_text_size(self.draw, mock, font=font)
        if center_x is None:
            x = (WIDTH - text_w) // 2
        else:
            x = int(center_x - text_w // 2)
        y = 10
        self.draw.text((x, y), mock, font=font, fill=0)
        return y + text_h

    def draw_hourly_grid(self):
        top_y = 210
        self.draw.line([(0, top_y), (WIDTH, top_y)], fill='black', width=2)
        
        bottom_y = 375
        num_lines = 12
        for i in range(1, num_lines + 1):
            x = int(i * WIDTH / (num_lines + 1))  # positions that split width into (num_lines+1) equal segments
            self.draw.line([(x, top_y), (x, bottom_y)], fill='black', width=2)
        # Draw mock content inside each hourly box
        num_boxes = num_lines + 1
        # Use rounded cell boundaries to avoid cumulative truncation drift
        for i in range(num_boxes):
            left = int(round(i * WIDTH / num_boxes))
            right = int(round((i + 1) * WIDTH / num_boxes))
            cell_w = right - left
            # small padding so lines don't overlap
            padding = 6
            inner_x = left + padding
            inner_w = cell_w - padding * 2
            inner_h = bottom_y - top_y - padding * 2
            self.draw_hourly_block(inner_x, top_y + padding, inner_w, inner_h, mock_hour_index=i)

    def draw_daily_grid(self):
        top_y = 375
        self.draw.line([(0, top_y), (WIDTH, top_y)], fill='black', width=2)
        
        # Reserve a small band at the very bottom for flight category (VFR/MVFR/IFR/LIFR)
        flight_band_height = 20
        bottom_y = HEIGHT - flight_band_height
        num_lines = 9
        for i in range(1, num_lines + 1):
            x = int(i * WIDTH / (num_lines + 1))  # positions that split width into (num_lines+1) equal segments
            self.draw.line([(x, top_y), (x, bottom_y)], fill='black', width=2)
        # Draw mock content inside each daily box
        num_boxes = num_lines + 1
        box_width = int(WIDTH / num_boxes)
        for i in range(num_boxes):
            left = i * box_width
            right = left + box_width
            # small padding so lines don't overlap
            padding = 6
            self.draw_daily_block(left + padding, top_y + padding, box_width - padding * 2, bottom_y - top_y - padding * 2, mock_index=i)

    def draw_daily_block(self, x, y, w, h, mock_index=0):
        """Draw a single daily grid block at (x,y) with width w and height h.

        Layout (top to bottom):
          - Day label (e.g., 'Sun 25') centered near top
          - Icon placeholder (simple circle) centered in the middle
          - Temp / dewpoint text at bottom centered (e.g., '72\u00b0 / 55\u00b0')

        This uses mock data for now based on mock_index.
        """
        # Mock data (vary by index for visual variety)
        days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun', 'Mon']
        day = days[mock_index % len(days)]
        date_num = 25 + (mock_index % 7)
        day_label = f"{day} {date_num}"

        # Temperatures (mock)
        temp = 68 + (mock_index % 7)
        dew = 50 + (mock_index % 5)
        temp_text = f"{temp}\u00b0 / {dew}\u00b0"

        # Draw day label near top
        label_font = self.font18 or self.font24
        label_w, label_h = self.get_text_size(self.draw, day_label, font=label_font)
        label_x = x + (w - label_w) // 2
        label_y = y
        self.draw.text((label_x, label_y), day_label, font=label_font, fill=0)

        # Draw icon placeholder (circle) in center area
        icon_radius = min(w, h) // 6
        icon_cx = x + w // 2
        # place icon below the day label, leave some spacing
        icon_cy = y + label_h + icon_radius + 12
        bbox = [icon_cx - icon_radius, icon_cy - icon_radius, icon_cx + icon_radius, icon_cy + icon_radius]
        self.draw.ellipse(bbox, outline=0, width=2)
        # Draw a simple symbol inside (e.g., cloud lines) to indicate weather
        self.draw.line([(bbox[0] + 3, icon_cy), (bbox[2] - 3, icon_cy)], fill=0, width=1)
        self.draw.line([(bbox[0] + 5, icon_cy + 6), (bbox[2] - 5, icon_cy + 6)], fill=0, width=1)

        # Draw temperature at bottom
        temp_font = self.font18 or self.font24
        temp_w, temp_h = self.get_text_size(self.draw, temp_text, font=temp_font)
        temp_x = x + (w - temp_w) // 2
        temp_y = y + h - temp_h
        self.draw.text((temp_x, temp_y), temp_text, font=temp_font, fill=0)

    def draw_hourly_block(self, x, y, w, h, mock_hour_index=0):
        """Draw a single hourly block with vertically stacked mock info.

        Items (top to bottom):
          - Hour (24h, e.g., 15:00)
          - Small icon placeholder
          - Flight category text (VFR/MVFR/IFR/LIFR)
          - Ceiling in feet and the label "Ceiling"
          - Wind direction (compass)
          - Wind magnitude (with gusts if any)
          - Temperature in °F
          - Precipitation chance (%)
        """
        # Mock generators
        categories = ['VFR', 'MVFR', 'IFR', 'LIFR']

        hour = mock_hour_index % 24
        hour_label = f"{hour:02d}:00"

        cat = categories[mock_hour_index % len(categories)]

        ceiling = 500 + (mock_hour_index % 10) * 200  # e.g., 500, 700, ...

        # Mock wind direction in degrees (varying by hour). Format as three digits + degree symbol.
        deg = (mock_hour_index * 37) % 360
        wd = f"{deg:03d}\u00b0"

        base_speed = 5 + (mock_hour_index % 12)
        gust_mode = mock_hour_index % 3
        if gust_mode == 0:
            wind_mag = f"{base_speed}-{base_speed + 8}"
        elif gust_mode == 1:
            wind_mag = f"{base_speed}"
        else:
            wind_mag = f"{base_speed}-{base_speed + 12}"

        temp = 30 + (mock_hour_index % 30)
        precip = (mock_hour_index * 13) % 100

        # Fonts
        hour_font = self.font12
        small_font = self.font12

        # Vertical layout: compute sizes and positions
        spacing = 6
        cursor_y = y

        # Use the cell center for horizontal alignment to avoid drift
        center_x = x + w // 2

        # Hour at top
        hw, hh = self.get_text_size(self.draw, hour_label, font=hour_font)
        hx = int(center_x - hw // 2)
        self.draw.text((hx, cursor_y), hour_label, font=hour_font, fill=0)
        cursor_y += hh + spacing + 5

        # Icon placeholder (small circle)
        icon_r = max(6, min(w, h) // 12)
        icon_cx = center_x
        icon_cy = cursor_y + icon_r
        self.draw.ellipse([icon_cx - icon_r, icon_cy - icon_r, icon_cx + icon_r, icon_cy + icon_r], outline=0, width=1)
        cursor_y = icon_cy + icon_r + spacing

        # Flight category text
        cat_w, cat_h = self.get_text_size(self.draw, cat, font=small_font)
        cat_x = int(center_x - cat_w // 2)
        self.draw.text((cat_x, cursor_y), cat, font=small_font, fill=0)
        cursor_y += cat_h + spacing + 4

        # Ceiling value and label
        ceil_text = f"{ceiling}'"
        ceil_w, ceil_h = self.get_text_size(self.draw, ceil_text, font=small_font)
        ceil_x = int(center_x - ceil_w // 2)
        self.draw.text((ceil_x, cursor_y), ceil_text, font=small_font, fill=0)
        cursor_y += ceil_h + 4
        label_text = "Ceiling"
        lbl_w, lbl_h = self.get_text_size(self.draw, label_text, font=small_font)
        lbl_x = int(center_x - lbl_w // 2)
        self.draw.text((lbl_x, cursor_y), label_text, font=small_font, fill=0)
        cursor_y += lbl_h + spacing

        # Wind direction
        wd_w, wd_h = self.get_text_size(self.draw, wd, font=small_font)
        wd_x = int(center_x - wd_w // 2)
        self.draw.text((wd_x, cursor_y), wd, font=small_font, fill=0)
        cursor_y += wd_h + spacing

        # Wind magnitude
        wind_w, wind_h = self.get_text_size(self.draw, wind_mag, font=small_font)
        wind_x = int(center_x - wind_w // 2)
        self.draw.text((wind_x, cursor_y), wind_mag, font=small_font, fill=0)
        cursor_y += wind_h + spacing

        # Temperature
        temp_text = f"{temp}\u00b0F"
        t_w, t_h = self.get_text_size(self.draw, temp_text, font=small_font)
        t_x = int(center_x - t_w // 2)
        self.draw.text((t_x, cursor_y), temp_text, font=small_font, fill=0)
        cursor_y += t_h + spacing

        # Precip chance at bottom
        precip_text = f"{precip}%"
        p_w, p_h = self.get_text_size(self.draw, precip_text, font=small_font)
        p_x = int(center_x - p_w // 2)
        # Align to bottom of the block if there's still space
        bottom_y = y + h - p_h
        if cursor_y + p_h + spacing > y + h:
            # not enough space, draw where cursor is
            self.draw.text((p_x, cursor_y), precip_text, font=small_font, fill=0)
        else:
            self.draw.text((p_x, bottom_y), precip_text, font=small_font, fill=0)

    def draw_flight_category_bar(self, flight_band_height=40):
        """Draw a bottom bar showing hourly flight categories (mock data).

        The bar occupies the bottom `flight_band_height` pixels and is divided
        into hourly cells. Each cell shows one of: VFR, MVFR, IFR, LIFR.
        """
        top_y = HEIGHT - flight_band_height
        # Top border of the band
        self.draw.line([(0, top_y), (WIDTH, top_y)], fill='black', width=2)

        # Divide into 24 hourly cells (mock hourly resolution)
        num_hours = 24 * 9
        cell_width = WIDTH / num_hours

        # mock sequence includes LIFR, but for shading we treat IFR and LIFR the same (solid)
        mock_sequence = ['VFR', 'MVFR', 'IFR', 'LIFR']

        # Draw each hourly cell with the requested shading:
        # - VFR: clear (no fill)
        # - MVFR: checkered pattern
        # - IFR or LIFR: solid fill
        for hour in range(num_hours):
            x0 = int(hour * cell_width)
            x1 = int((hour + 1) * cell_width) if hour < num_hours - 1 else WIDTH

            # vertical separator between hours (optional for grid clarity)
            if hour > 0:
                self.draw.line([(x0, top_y), (x0, HEIGHT)], fill='black', width=1)

            cat = mock_sequence[hour % len(mock_sequence)]

            if cat == 'VFR':
                # leave clear (do nothing)
                pass
            elif cat == 'MVFR':
                # checkered pattern: draw small squares alternating
                tile = 2
                # align pattern to the cell origin
                for xi in range(x0, x1, tile):
                    for yi in range(top_y, HEIGHT, tile):
                        # calculate offset within cell to choose which squares to fill
                        cell_x_index = (xi - x0) // tile
                        cell_y_index = (yi - top_y) // tile
                        if (cell_x_index + cell_y_index) % 2 == 0:
                            x_fill0 = xi
                            y_fill0 = yi
                            x_fill1 = min(xi + tile - 1, x1)
                            y_fill1 = min(yi + tile - 1, HEIGHT)
                            self.draw.rectangle([(x_fill0, y_fill0), (x_fill1, y_fill1)], fill=0)
            else:
                # IFR or LIFR -> solid fill
                # fill the entire cell rectangle
                self.draw.rectangle([(x0, top_y), (x1, HEIGHT)], fill=0)

        # Rightmost border
        self.draw.line([(WIDTH - 1, top_y), (WIDTH - 1, HEIGHT)], fill='black', width=1)

    def draw_right_aligned_text(self, text, y, margin, font, fill=0):
        """Draw text right-aligned with a consistent margin"""
        text_width, text_height = self.get_text_size(self.draw, text, font=font)
        x = self.image.width - text_width - margin
        # Draw the text
        self.draw.text((x, y), text, font=font, fill=fill)
        return y + text_height

    def save_display_preview(self, filename=None, scale=2):
        """
        Save a preview of the e-ink display content to a file and optionally open it.
        
        Args:
            image: PIL Image object containing the display content
            filename: Path where to save the preview (default: creates a timestamped file)
            preview: If True, tries to open the image in the default viewer
            scale: Scale factor to make the preview larger and more visible (default: 2)
        
        Returns:
            Path to the saved preview file
        """
        import os
        import datetime
        from PIL import Image, ImageOps
        
        if filename is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"eink_preview_{timestamp}.png"
        
        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
        
        # Create a copy of the image to avoid modifying the original
        preview_image = self.image.copy()
        
        # Convert to RGB to better simulate e-ink appearance
        if preview_image.mode == '1':
            # For 1-bit images, convert to RGB with proper black and white
            preview_image = preview_image.convert('RGB')
            
            # Optional: Add slight gray tinting to simulate e-ink appearance
            pixels = preview_image.load()
            width, height = preview_image.size
            for x in range(width):
                for y in range(height):
                    r, g, b = pixels[x, y]
                    if r > 200 and g > 200 and b > 200:  # If it's close to white
                        pixels[x, y] = (245, 245, 240)  # Slight off-white for e-ink simulation
        
        # Scale up for better visibility
        if scale != 1:
            width, height = preview_image.size
            preview_image = preview_image.resize((width * scale, height * scale), Image.LANCZOS)
        
        preview_image.save(filename)
        print(f"Preview saved to: {filename}")
        
        return filename
    
    def draw_current_icon(self):
        picdir = Path(__file__).resolve().parent / 'pic' / 'wi-cloud.bmp'
        korh_text = "KORH"
        # Compute KORH text width to center the icon under it (KORH is drawn at x=10)
        try:
            korh_w, korh_h = self.get_text_size(self.draw, korh_text, font=self.font35)
        except Exception:
            korh_w = 0

        # Default desired top y for icon
        icon_top_y = 50

        # Load original icon to compute scaled size
        if os.path.exists(picdir):
            try:
                orig = Image.open(picdir)
                ow, oh = orig.size
            except Exception:
                ow, oh = (64, 64)
        else:
            ow, oh = (64, 64)

        scale_factor = 0.9
        scaled_w = int(ow * scale_factor)
        scaled_h = int(oh * scale_factor)

        # KORH x position is 10 in render_display; center icon under the KORH text block
        korh_x = 10
        icon_x = korh_x + max(0, (korh_w - scaled_w) // 2)
        # ensure icon_x is within display
        icon_x = max(0, min(icon_x, WIDTH - scaled_w))

        # Paste scaled icon at computed position
        try:
            self.scale_and_display_bmp(picdir, position=(int(icon_x), int(icon_top_y)), scale_factor=scale_factor)
        except Exception:
            # fallback to default position
            try:
                self.scale_and_display_bmp(picdir, position=(0, icon_top_y), scale_factor=scale_factor)
            except Exception:
                pass

        # Draw small label under the icon centered to the icon
        try:
            label = 'Cloudy'
            lw, lh = self.get_text_size(self.draw, label, font=self.font24)
            icon_cx = icon_x + scaled_w / 2
            label_x = int(icon_cx - lw / 2)
            label_y = int(icon_top_y + scaled_h)
            # ensure label stays on-screen
            label_x = max(0, min(label_x, WIDTH - lw))
            self.draw.text((label_x, label_y), label, font=self.font24, fill=0)
        except Exception:
            pass

        return

    def draw_summary_grid(self, left_x=None, top_y=None):
        """Draw a 3x3 summary grid to the right of the main icon/wind area using mock data.

        The grid will occupy the horizontal space to the right of `left_x` and extend
        down to just above the hourly grid (which starts at y=225 in this layout).
        """
        # Defaults: place grid to the right of the icon/barb area and under the header
        margin = 5
        if left_x is None:
            # Center the summary grid horizontally by default so the middle column sits at display center.
            left_x = margin + 100
        if top_y is None:
            top_y = 40

        right_x = WIDTH - margin - 50
        bottom_y = 225 - margin  # leave space for hourly grid which starts at 225

        grid_w = right_x - left_x
        grid_h = bottom_y - top_y
        if grid_w <= 0 or grid_h <= 0:
            return

        cols = 3
        rows = 3
        cell_w = grid_w // cols
        cell_h = grid_h // rows

        # Define cell content (3 columns x 3 rows). Each entry: (big_text, label, subtext)
        cells = [
            # Column 1
            { 'big': 'LIFR', 'label': 'FLIGHT CATEGORY', 'sub': '' },
            { 'big': "500'", 'label': 'CEILING', 'sub': '' },
            { 'big': '0.5 sm', 'label': 'VISIBILITY', 'sub': '' },
            # Column 2
            { 'big': "5\u00b0F (-15\u00b0C)", 'label': 'TEMPERATURE', 'sub': '' },
            { 'big': "044\u00b0 @ 10-19", 'label': 'WIND (KTS)', 'sub': '' },
            { 'big': '30.21', 'label': 'ALTIMETER', 'sub': '' },
            # Column 3
            { 'big': "2\u00b0F / 85%", 'label': 'DEWPT/HUMIDITY', 'sub': '' },
            { 'big': "-2,833'", 'label': 'DENSITY ALT', 'sub': '' },
            { 'big': '99% (1.0")', 'label': 'SNOW', 'sub': '' },
        ]

        # Fonts
        big_font = self.font24 or self.font18
        value_font = self.font24 or self.font18
        label_font = self.font12 or self.font18

        for idx, cell in enumerate(cells):
            col = idx % cols
            row = idx // cols
            x0 = left_x + col * cell_w
            y0 = top_y + row * cell_h
            x1 = x0 + cell_w
            y1 = y0 + cell_h

            padding = 0
            inner_x = x0 + padding
            inner_w = cell_w - padding * 2

            # Draw cell separators (vertical and horizontal) for clarity
            # vertical lines will be drawn at column boundaries later; draw horizontal lines now
            # self.draw.line([(x0, y1), (x1, y1)], fill='black', width=1)

            # Big primary text (top-left-ish)
            big = cell['big']
            label = cell['label']

            # Draw big text centered near top half of the cell
            bw, bh = self.get_text_size(self.draw, big, font=value_font)
            bx = x0 + (cell_w - bw) // 2
            by = y0 + padding
            self.draw.text((bx, by), big, font=value_font, fill=0)

            # Draw label under the big text
            lw, lh = self.get_text_size(self.draw, label, font=label_font)
            lx = x0 + (cell_w - lw) // 2
            ly = by + bh + 6
            self.draw.text((lx, ly), label, font=label_font, fill=0)

        # Draw vertical separators between columns
        # for c in range(1, cols):
        #     sx = left_x + c * cell_w
        #     self.draw.line([(sx, top_y), (sx, bottom_y)], fill='black', width=1)

        # Top border
        # self.draw.line([(left_x, top_y), (right_x, top_y)], fill='black', width=1)

        # Return summary grid geometry so callers can align other elements (like centered time)
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
    
    def scale_and_display_bmp(self, bmp_path, position=(0, 0), scale_factor=.9, 
                          inverted=False):
        """
        Scales a BMP icon and adds it to an image.
        
        Args:
            bmp_path: Path to the BMP file
            position: Tuple (x, y) for positioning the icon on the display
            scale_factor: Factor to scale the icon (1.0 = original size)
            inverted: If True, invert the colors (black becomes white and vice versa)
            update_display: If True, immediately update the display
        
        Returns:
            The PIL Image with the icon added
        """
        # Check if the file exists
        if not os.path.exists(bmp_path):
            raise FileNotFoundError(f"BMP file not found: {bmp_path}")
        
        # Open the BMP file
        original_image = Image.open(bmp_path)
        
        # Calculate the new dimensions
        width, height = original_image.size
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        
        # Scale the image using high-quality resampling
        if scale_factor != 1.0:
            scaled_image = original_image.resize((new_width, new_height), Image.LANCZOS)
        else:
            scaled_image = original_image
        
        # Convert to 1-bit mode for e-ink display if needed
        if scaled_image.mode != '1':
            scaled_image = scaled_image.convert('1')
        
        # Invert if requested
        if inverted:
            scaled_image = ImageChops.invert(scaled_image)
        
        # Paste the scaled icon at the specified position
        self.image.paste(scaled_image, position)

    def draw_wind_barb(self, center_x, center_y, wind_speed, wind_direction, scale=1.0, 
                    color='black', line_width=3, barb_angle=290):
        """
        Draw a wind barb symbol centered at a specific point.
        Barbs are drawn at a specified angle from the staff.
        
        Args:
            center_x, center_y: Center position of the wind barb
            wind_speed: Wind speed in knots
            wind_direction: Wind direction in degrees (0-360, where 0/360 is North)
            scale: Scale factor for the barb size (default 1.0)
            color: Color of the barb lines (default 'black')
            line_width: Width of the barb lines (default 2)
            barb_angle: Angle of barbs from staff in degrees (default 45)
                        0 = along staff, 90 = perpendicular to staff
                        Positive = counterclockwise from staff (left side)
                        Negative = clockwise from staff (right side)
        """
        
        # Handle calm wind (< 3 knots)
        if wind_speed < 3:
            # Draw a circle for calm wind
            radius = int(6 * scale)
            bbox = [center_x - radius, center_y - radius, center_x + radius, center_y + radius]
            self.draw.ellipse(bbox, outline=color, width=line_width)
            return
        
        # Base dimensions scaled
        staff_length = int(40 * scale)
        barb_length = int(15 * scale)
        pennant_width = int(15 * scale)
        
        # Convert wind direction to radians
        # Wind direction is "from" direction, so we need to reverse it for the barb
        # Also convert from meteorological (0° = North, clockwise) to mathematical (0° = East, counterclockwise)
        staff_angle_rad = math.radians(90 - wind_direction)
        
        # Calculate staff start and end points from center
        # Staff is centered at the specified coordinates
        start_x = center_x - (staff_length / 2) * math.cos(staff_angle_rad)
        start_y = center_y + (staff_length / 2) * math.sin(staff_angle_rad)
        end_x = center_x + (staff_length / 2) * math.cos(staff_angle_rad)
        end_y = center_y - (staff_length / 2) * math.sin(staff_angle_rad)
        
        # Draw the staff (main line)
        self.draw.line([(start_x, start_y), (end_x, end_y)], fill=color, width=line_width)
        
        # Calculate the unit vector along the staff (direction of wind)
        staff_unit_x = math.cos(staff_angle_rad)
        staff_unit_y = -math.sin(staff_angle_rad)
        
        # Convert barb angle to radians
        barb_angle_rad = math.radians(barb_angle)
        
        # Calculate barb direction by adding the barb angle to the staff angle
        barb_direction_rad = staff_angle_rad + barb_angle_rad

        # Calculate unit vectors for the barb direction
        barb_unit_x = math.cos(barb_direction_rad)
        barb_unit_y = -math.sin(barb_direction_rad)
        
        # Calculate barb components
        speed_remaining = wind_speed
        barb_spacing = 0.1 * staff_length  # Fixed spacing in pixels
        
        # Position along staff for barbs (start near the end and work backward)
        if 3 < wind_speed < 8:
            barb_start_offset = int(5 * scale)  # Small offset from the very end
        else:
            barb_start_offset = 0
        
        # Initial position for first barb
        current_x = end_x - barb_start_offset * staff_unit_x
        current_y = end_y - barb_start_offset * staff_unit_y
        
        # Draw pennants (50 knot flags)
        while speed_remaining >= 50:
            # Pennant tip (at specified angle from staff)
            tip_x = current_x + pennant_width * barb_unit_x
            tip_y = current_y + pennant_width * barb_unit_y
            
            # Base of pennant (back along staff)
            base_x = current_x - (barb_spacing * 0.8) * staff_unit_x
            base_y = current_y - (barb_spacing * 0.8) * staff_unit_y
            
            # Draw filled triangle for pennant
            self.draw.polygon([(current_x, current_y), (tip_x, tip_y), (base_x, base_y)], fill=color)
            
            # Move position back along staff for next barb
            current_x -= barb_spacing * staff_unit_x * 1.2
            current_y -= barb_spacing * staff_unit_y * 1.2
            
            speed_remaining -= 50
        
        # Draw full barbs (10 knot lines)
        while speed_remaining >= 10:
            # Calculate barb end point (at specified angle from staff)
            barb_end_x = current_x + barb_length * barb_unit_x
            barb_end_y = current_y + barb_length * barb_unit_y
            
            # Draw the barb
            self.draw.line([(current_x, current_y), (barb_end_x, barb_end_y)], fill=color, width=line_width)
            
            # Move position back along staff for next barb
            current_x -= barb_spacing * staff_unit_x
            current_y -= barb_spacing * staff_unit_y
            
            speed_remaining -= 10
        
        # Draw half barb (5 knot line)
        if speed_remaining >= 5:
            # Calculate half-barb end point (at specified angle from staff, half length)
            half_barb_end_x = current_x + (barb_length / 2) * barb_unit_x
            half_barb_end_y = current_y + (barb_length / 2) * barb_unit_y
            
            # Draw the half-barb
            self.draw.line([(current_x, current_y), (half_barb_end_x, half_barb_end_y)], 
                        fill=color, width=line_width)