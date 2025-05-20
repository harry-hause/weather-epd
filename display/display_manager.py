import math
import time
from pathlib import Path
import logging
from PIL import Image,ImageDraw,ImageFont

logger = logging.getLogger()

class DisplayManager:
    def __init__(self, dev_mode=True):
        self.dev_mode = dev_mode

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

    def init_image(self, width: int = 800, height: int = 480):
        return Image.new('1', (width, height), 255)
    
    def init_draw(self, image: Image):
        return ImageDraw.Draw(image)

    def load_fonts(self):
        picdir = Path(__file__).resolve().parent / 'pic'
        self.font24 = ImageFont.truetype(str(picdir / 'Font.ttc'), 24)
        self.font18 = ImageFont.truetype(str(picdir / 'Font.ttc'), 18)
        self.font35 = ImageFont.truetype(str(picdir / 'Font.ttc'), 35)

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
        self.draw_right_aligned_text(self.draw, "39m ago", 10, 10, self.font18)

        self.draw_wind_barb(self.draw, 250, 50, 2, 270, scale=2)
        self.draw_wind_barb(self.draw, 250, 120, 6, 270, scale=2)
        self.draw_wind_barb(self.draw, 250, 190, 8, 270, scale=2)
        self.draw_wind_barb(self.draw, 250, 260, 12, 270, scale=2)
        self.draw_wind_barb(self.draw, 250, 330, 15, 270, scale=2)
        self.draw_wind_barb(self.draw, 250, 400, 130, 270, scale=2)


        if not self.dev_mode:
            self.epd.display(self.epd.getbuffer(self.image))
            time.sleep(20)
        else: self.save_display_preview('weather_preview.png')

    def draw_right_aligned_text(self, draw, text, y, margin, font, fill=0):
        """Draw text right-aligned with a consistent margin"""
        text_width, text_height = self.get_text_size(draw, text, font=font)
        x = self.image.width - text_width - margin
        # Draw the text
        draw.text((x, y), text, font=font, fill=fill)
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

    def draw_wind_barb(self, draw, x, y, wind_speed, wind_direction, scale=1.0, color='black', line_width=2):
        """
        Draw a wind barb symbol on an image.

        See:
            https://www.weather.gov/hfo/windbarbinfo
        
        Args:
            draw: PIL ImageDraw object
            x, y: Center position of the wind barb
            wind_speed: Wind speed in knots
            wind_direction: Wind direction in degrees (0-360, where 0/360 is North)
            scale: Scale factor for the barb size (default 1.0)
            color: Color of the barb lines (default 'black')
            line_width: Width of the barb lines (default 2)
        """
        
        # Handle calm wind (< 3 knots)
        if wind_speed < 3:
            # Draw a circle for calm wind
            radius = int(6 * scale)
            bbox = [x - radius, y - radius, x + radius, y + radius]
            draw.ellipse(bbox, outline=color, width=line_width)
            return
        
        # Convert wind direction to radians
        # Wind direction is "from" direction, so we add 180° to get "to" direction for barb orientation
        # Also convert from meteorological (0° = North, clockwise) to mathematical (0° = East, counterclockwise)
        angle_rad = math.radians(90 - wind_direction)
        
        # Base dimensions scaled
        staff_length = int(40 * scale)
        barb_length = int(15 * scale)
        pennant_width = int(15 * scale)
        
        # Calculate staff end points
        end_x = x + staff_length * math.cos(angle_rad)
        end_y = y - staff_length * math.sin(angle_rad)
        
        # Draw the staff (main line)
        draw.line([(x, y), (end_x, end_y)], fill=color, width=line_width)
        
        # Calculate barb components
        speed_remaining = wind_speed
        barb_spacing = 0.10  # Space between barbs as fraction of staff length
        
        # Start position depends on whether we have a 5-knot barb
        # If we have a 5-knot component, start further from tip to leave room for offset
        if 3 < wind_speed < 8:
            barb_position = 0.9  # Start further from tip
        else:
            barb_position = 1  # Start closer to tip
        
        # Calculate direction for barbs (45 degrees from the staff, to the right)
        barb_angle = angle_rad + math.pi / 2.5  # 45 degrees instead of 90
        
        # Draw pennants (50 knot flags) - flush with tip
        while speed_remaining >= 50:
            pos_along_staff = barb_position
            staff_x = x + (end_x - x) * pos_along_staff
            staff_y = y + (end_y - y) * pos_along_staff
            
            # Pennant tip
            tip_x = staff_x + pennant_width * math.cos(barb_angle)
            tip_y = staff_y + pennant_width * math.sin(barb_angle)
            
            # Pennant base (slightly back along staff)
            base_pos = pos_along_staff - barb_spacing * 0.7
            base_x = x + (end_x - x) * base_pos
            base_y = y + (end_y - y) * base_pos
            
            # Draw filled triangle for pennant
            points = [(staff_x, staff_y), (tip_x, tip_y), (base_x, base_y)]
            draw.polygon(points, fill=color)
            
            speed_remaining -= 50
            barb_position -= barb_spacing
        
        # Draw full barbs (10 knot lines) - flush with tip
        while speed_remaining >= 8:
            pos_along_staff = barb_position
            staff_x = x + (end_x - x) * pos_along_staff
            staff_y = y + (end_y - y) * pos_along_staff
            
            barb_end_x = staff_x + barb_length * math.cos(barb_angle)
            barb_end_y = staff_y + barb_length * math.sin(barb_angle)
            
            draw.line([(staff_x, staff_y), (barb_end_x, barb_end_y)], fill=color, width=line_width)
            
            speed_remaining -= 10
            barb_position -= barb_spacing
        
        # Draw half barb (5 knot line) - offset from tip, closer to center
        if speed_remaining >= 3:
            # Half barb is positioned further back from the tip
            pos_along_staff = barb_position
            staff_x = x + (end_x - x) * pos_along_staff
            staff_y = y + (end_y - y) * pos_along_staff
            
            half_barb_end_x = staff_x + (barb_length / 2) * math.cos(barb_angle)
            half_barb_end_y = staff_y + (barb_length / 2) * math.sin(barb_angle)
            
            draw.line([(staff_x, staff_y), (half_barb_end_x, half_barb_end_y)], fill=color, width=line_width)