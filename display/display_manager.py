from pathlib import Path
from display.epd_interface import EPD

class DisplayManager:
    def __init__(self, dev_mode=True):
        self.dev_mode = dev_mode
        self.load_fonts()
        self.init_display()

    def init_display():
        epd = EPD()
    
        logging.info("init and Clear")
        epd.init()
        pass

    def load_fonts(self):
        picdir = Path(__file__).resolve().parent / 'pic'
        font24 = ImageFont.truetype(str(picdir / 'Font.ttc'), 24)
        font18 = ImageFont.truetype(str(picdir / 'Font.ttc'), 18)
        font35 = ImageFont.truetype(str(picdir / 'Font.ttc'), 35)

    def render_display(self):
        pass