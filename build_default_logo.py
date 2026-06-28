"""
build_default_logo.py
----------------------
Generates a neutral placeholder logo (assets/logo.png) used ONLY until you
upload your own logo through the app's sidebar uploader. It's a simple
circular seal with a generic play-button icon and "YOUR LOGO GOES HERE" arc
text -- deliberately generic so it works for any organization or channel,
not tied to any specific one.

You almost certainly want to replace the output by uploading your real logo
inside the app instead -- this is just so the app looks complete on first run.
"""

import math
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
ASSETS = os.path.join(HERE, "assets")

SIZE = 600  # render large, downscaled at composite time for crisp edges


def _spread(a, b, n):
    if n <= 1:
        yield (a + b) / 2
        return
    step = (b - a) / (n - 1)
    for i in range(n):
        yield a + step * i


def arc_text(img, text, center, radius, font, fill, start_deg, end_deg, upper=True):
    """Draw `text` evenly spaced along a circular arc onto `img` (RGBA).

    Angles follow screen convention (0=right, 90=down/bottom, 180=left,
    270=top), increasing clockwise. start_deg -> end_deg defines the
    left-to-right reading sweep (pass start > end to sweep through the
    bottom, start < end to sweep through the top).

    For the TOP arc, glyph "up" points outward (away from center) -- the
    normal, instantly-legible orientation. For the BOTTOM arc, glyph "up"
    points inward (toward center) so the text reads upright to a viewer
    instead of upside-down, matching standard seal/crest typography.
    """
    angles = list(_spread(start_deg, end_deg, len(text)))

    for ch, ang in zip(text, angles):
        glyph_layer = Image.new("RGBA", (140, 140), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glyph_layer)
        bbox = gdraw.textbbox((0, 0), ch, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        gdraw.text((70 - w / 2 - bbox[0], 70 - h / 2 - bbox[1]), ch, font=font, fill=fill)

        rad = math.radians(ang)
        x = center[0] + radius * math.cos(rad)
        y = center[1] + radius * math.sin(rad)

        outward_rotation = -(ang + 90)
        rotation = outward_rotation if upper else outward_rotation + 180
        rotated = glyph_layer.rotate(rotation, resample=Image.BICUBIC, center=(70, 70))
        img.alpha_composite(rotated, (int(x - 70), int(y - 70)))


def main():
    os.makedirs(ASSETS, exist_ok=True)
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    c = SIZE // 2

    navy = (19, 35, 91, 255)
    red = (196, 30, 35, 255)
    cream = (255, 252, 244, 255)
    gold = (210, 165, 60, 255)

    draw.ellipse([4, 4, SIZE - 4, SIZE - 4], fill=red)
    draw.ellipse([16, 16, SIZE - 16, SIZE - 16], fill=navy)
    draw.ellipse([26, 26, SIZE - 26, SIZE - 26], fill=cream)

    bold = ImageFont.truetype(os.path.join(FONTS, "LeagueSpartan-Black.otf"), 34)
    small_bold = ImageFont.truetype(os.path.join(FONTS, "LeagueSpartan-Bold.otf"), 26)

    arc_text(img, "YOUR LOGO", (c, c), 230, bold, navy, 200, 340, upper=True)
    arc_text(img, "GOES HERE", (c, c), 230, small_bold, navy, 160, 20, upper=False)

    for ang in range(0, 360, 10):
        if 195 < ang < 345 or 15 < ang < 165:
            continue
        rad = math.radians(ang)
        x = c + 250 * math.cos(rad)
        y = c + 250 * math.sin(rad)
        draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=gold)

    # Centered play-button triangle -- a generic "livestream/video" icon
    # instead of any organization-specific symbol.
    r = 95
    tri = [
        (c - r * 0.55, c - r),
        (c - r * 0.55, c + r),
        (c + r * 0.95, c),
    ]
    draw.polygon(tri, fill=navy)

    img.save(os.path.join(ASSETS, "logo.png"))
    print("wrote", os.path.join(ASSETS, "logo.png"))


if __name__ == "__main__":
    main()
