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


        self.draw_wind_barb(60, 200, 15, 120, scale=2)
        self.draw.line([(0, 400), (WIDTH, 400)], fill='black', width=2)
        # self.draw_wind_barb(120, 300, 5, 270, scale=2)
        # self.draw_wind_barb(200, 200, 10, 270, scale=2)
        # self.draw_wind_barb(300, 300, 25, 360, scale=2)
        # self.draw_wind_barb(350, 330, 65, 180, scale=2)
        # self.draw_wind_barb(500, 400, 45, 200, scale=2)


        if not self.dev_mode:
            self.epd.display(self.epd.getbuffer(self.image))
            time.sleep(20)
        else: self.save_display_preview('weather_preview.png')

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
        self.scale_and_display_bmp(picdir, position=(0, 50))
        self.draw.text((10, 120), 'Cloudy', font=self.font24)

        return
    
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