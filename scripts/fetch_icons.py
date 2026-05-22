#!/usr/bin/env python3
"""Download and convert weather icons from erikflowers/weather-icons to 1-bit BMP.

Usage:
    pip install cairosvg pillow
    python scripts/fetch_icons.py

On macOS with Homebrew cairo, cairosvg can't find the library without help:
    DYLD_LIBRARY_PATH=/opt/homebrew/lib python scripts/fetch_icons.py

Icons are written to display/pic/. Already-present files are skipped.
SVGs are sourced from github.com/erikflowers/weather-icons.
"""

import io
import json
import sys
import urllib.request
from pathlib import Path

try:
    import cairosvg
except ImportError:
    sys.exit("cairosvg not installed. Run: pip install cairosvg")

from PIL import Image

REPO_RAW = "https://raw.githubusercontent.com/erikflowers/weather-icons/master/svg"
REPO_ROOT = Path(__file__).resolve().parent.parent
PICDIR = REPO_ROOT / 'display' / 'pic'
MAP_PATH = REPO_ROOT / 'display' / 'icon_map.json'

# Target pixel width for converted icons. The e-ink panel is 800x480
# and the main icon occupies roughly 100px; small grid icons are ~30px.
# We bake them at 100px and let DisplayManager scale down as needed.
OUTPUT_WIDTH = 100


def icons_from_map() -> set[str]:
    with open(MAP_PATH) as f:
        data = json.load(f)
    icons = {entry['icon'] for entry in data['rules']}
    icons.add(data.get('fallback', 'wi-cloud.bmp'))
    return icons


def svg_to_bmp(svg_bytes: bytes, output_width: int) -> Image.Image:
    png_bytes = cairosvg.svg2png(bytestring=svg_bytes, output_width=output_width)
    img = Image.open(io.BytesIO(png_bytes)).convert('RGBA')

    # Composite onto white background before converting to 1-bit so transparent
    # areas become white rather than black.
    background = Image.new('RGBA', img.size, (255, 255, 255, 255))
    background.paste(img, mask=img.split()[3])
    return background.convert('1')


def main() -> None:
    PICDIR.mkdir(parents=True, exist_ok=True)
    icons = icons_from_map()

    ok = skipped = failed = 0
    for bmp_name in sorted(icons):
        dest = PICDIR / bmp_name
        if dest.exists():
            print(f"  skip  {bmp_name}")
            skipped += 1
            continue

        svg_name = bmp_name.replace('.bmp', '.svg')
        url = f"{REPO_RAW}/{svg_name}"
        try:
            print(f"  fetch {svg_name} ... ", end='', flush=True)
            with urllib.request.urlopen(url, timeout=15) as resp:
                svg_bytes = resp.read()
            img = svg_to_bmp(svg_bytes, OUTPUT_WIDTH)
            img.save(dest)
            print(f"ok ({img.size[0]}x{img.size[1]})")
            ok += 1
        except Exception as e:
            print(f"FAILED: {e}")
            failed += 1

    print(f"\nDone: {ok} downloaded, {skipped} skipped, {failed} failed.")
    if failed:
        sys.exit(1)


if __name__ == '__main__':
    main()
