#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
import os
from pathlib import Path

picdir = Path(__file__).resolve().parent / 'pic'
import logging
from display.epd_interface import EPD
import time
from PIL import Image,ImageDraw,ImageFont
import traceback

logging.basicConfig(level=logging.DEBUG)

def save_display_preview(image, filename=None, scale=2):
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
    import subprocess
    from PIL import Image, ImageOps
    
    if filename is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"eink_preview_{timestamp}.png"
    
    os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
    
    # Create a copy of the image to avoid modifying the original
    preview_image = image.copy()
    
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

def scale_and_display_bmp(epd, bmp_path, position=(0, 0), scale_factor=1.0, 
                          inverted=False, base_image=None, update_display=True):
    """
    Scales a BMP icon and adds it to an image, optionally displaying on the e-paper display.
    
    Args:
        epd: The e-paper display object
        bmp_path: Path to the BMP file
        position: Tuple (x, y) for positioning the icon on the display
        scale_factor: Factor to scale the icon (1.0 = original size)
        inverted: If True, invert the colors (black becomes white and vice versa)
        base_image: Optional PIL Image to paste icon onto (creates new if None)
        update_display: If True, immediately update the display
    
    Returns:
        The PIL Image with the icon added
    """
    import os
    from PIL import Image, ImageChops
    
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
    
    # Create or use base image
    if base_image is None:
        base_image = Image.new('1', (epd.width, epd.height), 255)  # White background
    elif base_image.mode != '1':
        base_image = base_image.convert('1')
    
    # Paste the scaled icon at the specified position
    base_image.paste(scaled_image, position)
    
    # Display the image if requested
    if update_display:
        epd.display(epd.getbuffer(base_image))
    
    return base_image

def draw_right_aligned_text(draw, text, y, margin, font, fill=0):
    """Draw text right-aligned with a consistent margin"""
    # Get text dimensions
    text_width, text_height = draw.textsize(text, font=font)
    # Calculate starting x position
    x = epd.width - text_width - margin
    # Draw the text
    draw.text((x, y), text, font=font, fill=fill)
    return y + text_height  # Return the y position after this text

# Example usage for a weather display:
def create_weather_screen(epd, dev_mode=True):
    # Create a base image
    image = Image.new('1', (epd.width, epd.height), 255)
    draw = ImageDraw.Draw(image)

    font24 = ImageFont.truetype(str(picdir / 'Font.ttc'), 24)
    font18 = ImageFont.truetype(str(picdir / 'Font.ttc'), 18)
    font35 = ImageFont.truetype(str(picdir / 'ARIAL'), 35)
    font_test = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf')

    draw.text((10, 10), f"KORH", font=font35, fill=0)
    draw_right_aligned_text(draw, "39m ago", 10, 10, font_test)
    # draw.text((epd.width - 150, 10), "39m ago", font=font24)

    draw.text((10, 60), "VFR", font=font24, fill=0)
    draw.text((10, 90), "Flight Category", font=font18)

    weather_data = {
        'temp': 12,
        'humidity': 2
    }
    
    # Add some text
    font = ImageFont.truetype(str(picdir / 'Font.ttc'), 35)
    # draw.text((10, 10), f"Temperature: {weather_data['temp']}°C", font=font, fill=0)
    
    # Add appropriate weather icon based on condition
    # if weather_data['condition'] == 'sunny':
    #     icon_path = "/path/to/icons/sunny.bmp"
    # elif weather_data['condition'] == 'cloudy':
    #     icon_path = "/path/to/icons/cloudy.bmp"
    # else:
    #     icon_path = "/path/to/icons/default.bmp"
    icon_path = picdir / 'wi-cloud_1.bmp'
    
    # Add the icon to our image
    # image = scale_and_display_bmp(
    #     epd, 
    #     icon_path, 
    #     position=(epd.width - 150, 10),  # Top right
    #     scale_factor=0.8,
    #     base_image=image,
    #     update_display=False  # Don't update yet
    # )
    
    # Add more weather info
    # draw.text((10, 50), f"Humidity: {weather_data['humidity']}%", font=font, fill=0)
    
    # Now display the complete image
    if not dev_mode:
        epd.display(epd.getbuffer(image))
        time.sleep(20)
    else: save_display_preview(image, 'weather_preview.png')
    
    return image

try:
    logging.info("epd7in5_V2 Demo")
    epd = EPD()
    
    logging.info("init and Clear")
    epd.init()
    epd.Clear()

    font24 = ImageFont.truetype(str(picdir / 'Font.ttc'), 24)
    font18 = ImageFont.truetype(str(picdir / 'Font.ttc'), 18)
    font35 = ImageFont.truetype(str(picdir / 'Font.ttc'), 35)

    create_weather_screen(epd)

    # logging.info('imported fonts')
    # logging.info("read bmp file")
    # Himage = Image.open(os.path.join(picdir, 'wi-cloud.bmp'))
    # epd.display(epd.getbuffer(Himage))
    # time.sleep(5)

    # logging.info("read bmp file on window")
    # Himage2 = Image.new('1', (epd.width, epd.height), 255)  # 255: clear the frame
    # bmp = Image.open(os.path.join(picdir, '100x100.bmp'))
    # Himage2.paste(bmp, (50,10))
    # epd.display(epd.getbuffer(Himage2))
    # time.sleep(2)

    # # Drawing on the Horizontal image
    # logging.info("Drawing on the Horizontal image...")
    # epd.init_fast()
    # Himage = Image.new('1', (epd.width, epd.height), 255)  # 255: clear the frame
    # draw = ImageDraw.Draw(Himage)
    # draw.text((10, 0), 'hello world', font = font24, fill = 0)
    # draw.text((10, 20), '7.5inch e-Paper', font = font24, fill = 0)
    # draw.text((150, 0), u'微雪电子', font = font24, fill = 0)
    # draw.line((20, 50, 70, 100), fill = 0)
    # draw.line((70, 50, 20, 100), fill = 0)
    # draw.rectangle((20, 50, 70, 100), outline = 0)
    # draw.line((165, 50, 165, 100), fill = 0)
    # draw.line((140, 75, 190, 75), fill = 0)
    # draw.arc((140, 50, 190, 100), 0, 360, fill = 0)
    # draw.rectangle((80, 50, 130, 100), fill = 0)
    # draw.chord((200, 50, 250, 100), 0, 360, fill = 0)
    # epd.display(epd.getbuffer(Himage))
    # time.sleep(2)

    # # partial update
    # logging.info("5.show time")
    # epd.init_part()
    # # Himage = Image.new('1', (epd.width, epd.height), 0)
    # # draw = ImageDraw.Draw(Himage)
    # num = 0
    # while (True):
    #     draw.rectangle((10, 120, 130, 170), fill = 255)
    #     draw.text((10, 120), time.strftime('%H:%M:%S'), font = font24, fill = 0)
    #     epd.display_Partial(epd.getbuffer(Himage),0, 0, epd.width, epd.height)
    #     num = num + 1
    #     if(num == 10):
    #         break



    # # Drawing on the Vertical image
    # logging.info("2.Drawing on the Vertical image...")
    # epd.init()
    # Limage = Image.new('1', (epd.height, epd.width), 255)  # 255: clear the frame
    # draw = ImageDraw.Draw(Limage)
    # draw.text((2, 0), 'hello world', font = font18, fill = 0)
    # draw.text((2, 20), '7.5inch epd', font = font18, fill = 0)
    # draw.text((20, 50), u'微雪电子', font = font18, fill = 0)
    # draw.line((10, 90, 60, 140), fill = 0)
    # draw.line((60, 90, 10, 140), fill = 0)
    # draw.rectangle((10, 90, 60, 140), outline = 0)
    # draw.line((95, 90, 95, 140), fill = 0)
    # draw.line((70, 115, 120, 115), fill = 0)
    # draw.arc((70, 90, 120, 140), 0, 360, fill = 0)
    # draw.rectangle((10, 150, 60, 200), fill = 0)
    # draw.chord((70, 150, 120, 200), 0, 360, fill = 0)
    # epd.display(epd.getbuffer(Limage))
    # time.sleep(2)


    # '''4Gray display'''
    # # The feature will only be available on screens sold after 24/10/23
    # logging.info("4Gray display--------------------------------")
    # epd.init_4Gray()
    
    # Limage = Image.new('L', (epd.width, epd.height), 0)  # 255: clear the frame
    # draw = ImageDraw.Draw(Limage)
    # draw.text((20, 0), u'微雪电子', font = font35, fill = epd.GRAY1)
    # draw.text((20, 35), u'微雪电子', font = font35, fill = epd.GRAY2)
    # draw.text((20, 70), u'微雪电子', font = font35, fill = epd.GRAY3)
    # draw.text((40, 110), 'hello world', font = font18, fill = epd.GRAY1)
    # draw.line((10, 140, 60, 190), fill = epd.GRAY1)
    # draw.line((60, 140, 10, 190), fill = epd.GRAY1)
    # draw.rectangle((10, 140, 60, 190), outline = epd.GRAY1)
    # draw.line((95, 140, 95, 190), fill = epd.GRAY1)
    # draw.line((70, 165, 120, 165), fill = epd.GRAY1)
    # draw.arc((70, 140, 120, 190), 0, 360, fill = epd.GRAY1)
    # draw.rectangle((10, 200, 60, 250), fill = epd.GRAY1)
    # draw.chord((70, 200, 120, 250), 0, 360, fill = epd.GRAY1)
    # epd.display_4Gray(epd.getbuffer_4Gray(Limage))
    # time.sleep(2)
    

    logging.info("Clear...")
    epd.init()
    epd.Clear()

    logging.info("Goto Sleep...")
    epd.sleep()
    
except IOError as e:
    logging.info(e)
    
except KeyboardInterrupt:    
    logging.info("ctrl + c:")
    epd7in5_V2.epdconfig.module_exit(cleanup=True)
    exit()
