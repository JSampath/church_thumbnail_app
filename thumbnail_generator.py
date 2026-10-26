"""
thumbnail_generator.py
-----------------------------------------
Core Pillow-based compositing engine that builds a single 1280x720 YouTube
livestream thumbnail. Fully generic -- usable for any channel, organization,
or event, not tied to any specific one.

Everything here is a pure function of its inputs (no Streamlit, no global
state) so it can be unit-tested or reused from a CLI script as well as the
Streamlit app. The only side effect is reading image/font files from disk.

Font roles are configurable (see ThumbnailConfig.font_*): pick any .ttf/.otf
file dropped into fonts/ for the title, hero word, script lines, or body
text (date/time, subscribe bar, LIVE badge, badge year/ribbon text).

All image files are opened via a `with` block so the file handle is released
immediately after the pixel data is loaded -- important on Windows, where a
file that's still held open can't be overwritten or deleted (e.g. uploading
a new logo/badge, or the "Remove badge" button in the app).
"""

import os
import random
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(HERE, "fonts")
ASSETS_DIR = os.path.join(HERE, "assets")
BACKGROUNDS_DIR = os.path.join(HERE, "backgrounds")

CANVAS_W, CANVAS_H = 1280, 720

# Default font for each role -- all overridable per-thumbnail via ThumbnailConfig.
FONT_TITLE = os.path.join(FONTS_DIR, "LeagueSpartan-Black.otf")    # main title
FONT_TITLE_ALT = os.path.join(FONTS_DIR, "LeagueSpartan-Bold.otf")  # = default "body" role
FONT_BODY = FONT_TITLE_ALT
FONT_HERO = os.path.join(FONTS_DIR, "BebasNeue-Bold.otf")          # big hero word + badge number
FONT_SCRIPT = os.path.join(FONTS_DIR, "DancingScript-Bold.otf")    # cursive lines

NAVY = (16, 30, 74)
GOLD = (244, 196, 66)
WHITE = (255, 255, 255)
CREAM = (255, 250, 240)
RED = (209, 33, 39)
DARK = (10, 12, 20)

RGB = Tuple[int, int, int]


def hex_to_rgb(value: Optional[str], default: RGB) -> RGB:
    """'#f4c442' -> (244, 196, 66). Anything unparseable falls back to `default`."""
    try:
        v = (value or "").strip().lstrip("#")
        if len(v) == 3:
            v = "".join(c * 2 for c in v)
        return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except (ValueError, TypeError):
        return default


def rgb_to_hex(rgb: RGB) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _shade(rgb: RGB, factor: float) -> RGB:
    """Darken (factor < 1) a colour, e.g. for outlines and ribbon folds."""
    return tuple(max(0, min(255, int(c * factor))) for c in rgb)  # type: ignore[return-value]


@dataclass
class Palette:
    """The three theme colours every element is drawn with."""
    primary: RGB = NAVY      # outlines, badge body
    accent: RGB = GOLD       # script lines, time text, badge number
    highlight: RGB = RED     # LIVE dot, ribbon, Subscribe button


# --------------------------------------------------------------------------
# Generic helpers
# --------------------------------------------------------------------------

@lru_cache(maxsize=64)
def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _resolve_font(path: Optional[str], default: str) -> str:
    """Fall back to `default` if `path` is empty or no longer exists on disk
    (e.g. a font file the user removed after picking it)."""
    if path and os.path.isfile(path):
        return path
    return default


def _load_image(path: str) -> Image.Image:
    """Open an image file, fully decode it into memory, and close the file
    handle immediately (instead of leaving it open via lazy-loaded
    Image.open). Avoids Windows file-lock issues when the same path is
    overwritten or deleted right after (e.g. re-uploading a logo/badge, or
    the "Remove badge" button)."""
    with Image.open(path) as f:
        f.load()
        return f.convert("RGBA")


def list_backgrounds():
    if not os.path.isdir(BACKGROUNDS_DIR):
        return []
    exts = (".jpg", ".jpeg", ".png", ".webp")
    return sorted(
        os.path.join(BACKGROUNDS_DIR, f)
        for f in os.listdir(BACKGROUNDS_DIR)
        if f.lower().endswith(exts)
    )


def list_fonts():
    """All .ttf/.otf font files available in fonts/ (built-in + user-added)."""
    if not os.path.isdir(FONTS_DIR):
        return []
    exts = (".ttf", ".otf")
    return sorted(
        os.path.join(FONTS_DIR, f)
        for f in os.listdir(FONTS_DIR)
        if f.lower().endswith(exts)
    )


def pick_random_background(exclude: Optional[str] = None) -> Optional[str]:
    paths = list_backgrounds()
    if not paths:
        return None
    if exclude and len(paths) > 1:
        paths = [p for p in paths if p != exclude]
    return random.choice(paths)


def cover_resize_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Resize `img` so it fully covers (target_w, target_h), then center-crop."""
    img = img.convert("RGB")
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w, new_h = int(round(src_w * scale)), int(round(src_h * scale))
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def fit_font(text: str, font_path: str, max_width: float, max_size: int, min_size: int = 14) -> ImageFont.FreeTypeFont:
    """Largest font size (<= max_size, >= min_size) so `text` fits in max_width."""
    size = max_size
    tmp = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(tmp)
    while size > min_size:
        font = _font(font_path, size)
        w = draw.textlength(text, font=font)
        if w <= max_width:
            return font
        size -= 2
    return _font(font_path, min_size)


def fit_font_box(text: str, font_path: str, max_width: float, max_height: float,
                  max_size: int, min_size: int = 14) -> ImageFont.FreeTypeFont:
    """Largest font size so `text` fits inside BOTH max_width and max_height."""
    size = max_size
    tmp = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(tmp)
    while size > min_size:
        font = _font(font_path, size)
        w = draw.textlength(text, font=font)
        bbox = draw.textbbox((0, 0), text, font=font)
        h = bbox[3] - bbox[1]
        if w <= max_width and h <= max_height:
            return font
        size -= 2
    return _font(font_path, min_size)


def draw_text_outlined(draw, xy, text, font, fill, outline, outline_width, anchor=None, shadow=True):
    """Draw text with a stroke outline plus a soft drop shadow for max legibility."""
    x, y = xy
    if shadow:
        shadow_offset = max(2, outline_width // 2 + 2)
        draw.text(
            (x + shadow_offset, y + shadow_offset),
            text,
            font=font,
            fill=(0, 0, 0, 110),
            anchor=anchor,
        )
    draw.text(
        xy,
        text,
        font=font,
        fill=fill,
        stroke_width=outline_width,
        stroke_fill=outline,
        anchor=anchor,
    )


def rounded_panel(size: Tuple[int, int], radius: int, fill) -> Image.Image:
    panel = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(panel).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=fill)
    return panel


def soft_shadow(size: Tuple[int, int], radius: int, blur: int = 12, alpha: int = 90) -> Image.Image:
    pad = blur * 2
    layer = Image.new("RGBA", (size[0] + pad * 2, size[1] + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(
        [pad, pad, pad + size[0] - 1, pad + size[1] - 1], radius=radius, fill=(0, 0, 0, alpha)
    )
    return layer.filter(ImageFilter.GaussianBlur(blur))


# --------------------------------------------------------------------------
# Sub-components
# --------------------------------------------------------------------------

def draw_top_bottom_gradient(canvas: Image.Image, dim: int = 0):
    """Subtle dark gradient bands top + bottom so text sits cleanly on ANY photo.
    `dim` (0-70) additionally darkens the whole photo evenly, for busy or
    very bright backgrounds."""
    w, h = canvas.size
    overlay = Image.new("L", (1, h), 0)
    px = overlay.load()
    top_h, bottom_h = 240, 260
    base = int(255 * max(0, min(70, dim)) / 100)
    for y in range(h):
        if y < top_h:
            a = int(150 * (1 - y / top_h))
        elif y > h - bottom_h:
            a = int(185 * (1 - (h - y) / bottom_h))
        else:
            a = 0
        px[0, y] = min(255, a + base - a * base // 255)
    overlay = overlay.resize((w, h))
    black = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    black.putalpha(overlay)
    canvas.alpha_composite(black)


def paste_logo(canvas: Image.Image, logo_path: Optional[str], center=(96, 96), radius=66):
    shadow = soft_shadow((radius * 2, radius * 2), radius, blur=10, alpha=110)
    canvas.alpha_composite(shadow, (center[0] - radius - 20, center[1] - radius - 20 + 6))

    backing = Image.new("RGBA", (radius * 2, radius * 2), (0, 0, 0, 0))
    ImageDraw.Draw(backing).ellipse([0, 0, radius * 2 - 1, radius * 2 - 1], fill=(255, 255, 255, 235))
    canvas.alpha_composite(backing, (center[0] - radius, center[1] - radius))

    if logo_path and os.path.isfile(logo_path):
        logo = _load_image(logo_path)
        inner = int(radius * 1.78)
        logo.thumbnail((inner, inner), Image.LANCZOS)
        lx = center[0] - logo.width // 2
        ly = center[1] - logo.height // 2
        canvas.alpha_composite(logo, (lx, ly))


def draw_title_block(canvas: Image.Image, draw, title: str, presented_by: str,
                      avoid_left: int, avoid_right: int, font_title: str, font_script: str,
                      pal: Palette = Palette()):
    max_w = CANVAS_W - avoid_left - avoid_right
    font = fit_font(title.upper(), font_title, max_w, max_size=50, min_size=24)
    w = draw.textlength(title.upper(), font=font)
    x = (CANVAS_W - w) / 2
    draw_text_outlined(draw, (x, 22), title.upper(), font, WHITE, pal.primary, 4, shadow=True)

    if presented_by:
        bbox = draw.textbbox((0, 0), title.upper(), font=font)
        title_bottom = 22 + (bbox[3] - bbox[1]) + 6
        pfont = _font(font_script, 30)
        pw = draw.textlength(presented_by, font=pfont)
        draw_text_outlined(draw, ((CANVAS_W - pw) / 2, title_bottom), presented_by, pfont, pal.accent, pal.primary, 2, shadow=False)


def draw_shield_badge(canvas: Image.Image, draw, box, start_year: str, end_year: str, number: str, caption: str,
                       font_body: str, font_hero: str, font_script: str,
                       pal: Palette = Palette(), ribbon_text: str = "ANNIVERSARY"):
    """Procedurally draw a gold/navy shield anniversary badge into `box`."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    point_y = y0 + h * 0.78

    outer = [
        (x0, y0 + h * 0.12), (x0 + w * 0.5, y0), (x1, y0 + h * 0.12),
        (x1, y0 + h * 0.55), (x0 + w * 0.5, point_y + 14), (x0, y0 + h * 0.55),
    ]
    shadow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow_layer).polygon([(p[0] + 5, p[1] + 8) for p in outer], fill=(0, 0, 0, 110))
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(6))
    canvas.alpha_composite(shadow_layer)

    draw.polygon(outer, fill=pal.accent, outline=_shade(pal.accent, 0.5))
    inset = 7
    inner = [
        (x0 + inset, y0 + h * 0.12 + inset * 0.6), (x0 + w * 0.5, y0 + inset),
        (x1 - inset, y0 + h * 0.12 + inset * 0.6), (x1 - inset, y0 + h * 0.5),
        (x0 + w * 0.5, point_y + 6), (x0 + inset, y0 + h * 0.5),
    ]
    draw.polygon(inner, fill=pal.primary)

    yr_font = _font(font_body, 14)
    yrs_text = f"{start_year}  •  {end_year}" if (start_year and end_year) else (start_year or end_year or "")
    yw = draw.textlength(yrs_text, font=yr_font)
    draw.text((x0 + w / 2 - yw / 2, y0 + h * 0.16), yrs_text, font=yr_font, fill=pal.accent)

    num_font = fit_font(number, font_hero, w * 0.62, max_size=58, min_size=24)
    nw = draw.textlength(number, font=num_font)
    draw.text((x0 + w / 2 - nw / 2, y0 + h * 0.27), number, font=num_font, fill=pal.accent)

    cap_font = _font(font_script, 17)
    cw = draw.textlength(caption, font=cap_font)
    draw.text((x0 + w / 2 - cw / 2, y0 + h * 0.55), caption, font=cap_font, fill=WHITE)

    # ribbon banner across the bottom point
    band_y0, band_y1 = y0 + h * 0.68, y0 + h * 0.80
    draw.polygon(
        [(x0 - 6, band_y0 + 4), (x1 + 6, band_y0 + 4), (x1 + 6, band_y1 + 4), (x0 - 6, band_y1 + 4)],
        fill=_shade(pal.highlight, 0.72),
    )
    draw.polygon([(x0 - 6, band_y0 + 4), (x0 + 12, (band_y0 + band_y1) / 2 + 4), (x0 - 6, band_y1 + 4)], fill=_shade(pal.highlight, 0.45))
    draw.polygon([(x1 + 6, band_y0 + 4), (x1 - 12, (band_y0 + band_y1) / 2 + 4), (x1 + 6, band_y1 + 4)], fill=_shade(pal.highlight, 0.45))
    ann_text = (ribbon_text or "").upper()
    ann_font = fit_font(ann_text, font_body, w + 4, max_size=13, min_size=9)
    aw = draw.textlength(ann_text, font=ann_font)
    draw.text((x0 + w / 2 - aw / 2, band_y0 + 6), ann_text, font=ann_font, fill=WHITE)


def paste_anniversary_image(canvas: Image.Image, badge_path: str, box):
    """Paste a user-supplied anniversary badge image into `box`, preserving its
    aspect ratio (contain-fit) and centering it within the box. A soft shadow
    is added behind it so it sits consistently with the rest of the design.
    Used automatically (instead of `draw_shield_badge`) whenever the user
    has uploaded their own badge graphic -- mirrors how the logo works.
    """
    x0, y0, x1, y1 = box
    box_w, box_h = int(x1 - x0), int(y1 - y0)

    badge = _load_image(badge_path)
    badge.thumbnail((box_w, box_h), Image.LANCZOS)

    sx = int(x0 + (box_w - badge.width) / 2)
    sy = int(y0 + (box_h - badge.height) / 2)

    shadow = soft_shadow(badge.size, min(badge.size) // 8 or 1, blur=10, alpha=100)
    shadow_x = sx - (shadow.width - badge.width) // 2
    shadow_y = sy - (shadow.height - badge.height) // 2 + 6
    canvas.alpha_composite(shadow, (shadow_x, shadow_y))
    canvas.alpha_composite(badge, (sx, sy))


def draw_date_time_panel(canvas: Image.Image, draw, date_text: str, time_text: str, right_x: int, top_y: int,
                          font_body: str, pal: Palette = Palette()):
    if not date_text and not time_text:
        return
    f1 = fit_font(date_text, font_body, 360, max_size=34, min_size=18)
    f2 = fit_font(time_text, font_body, 360, max_size=30, min_size=16)

    b1 = draw.textbbox((0, 0), date_text, font=f1)
    b2 = draw.textbbox((0, 0), time_text, font=f2)
    w1, h1 = b1[2] - b1[0], b1[3] - b1[1]
    w2, h2 = b2[2] - b2[0], b2[3] - b2[1]
    pad_x, pad_y, gap = 22, 14, 6
    panel_w = max(w1, w2) + pad_x * 2
    panel_h = h1 + h2 + gap + pad_y * 2

    panel_x0 = right_x - panel_w
    panel = rounded_panel((panel_w, panel_h), 16, (8, 10, 18, 150))
    canvas.alpha_composite(panel, (panel_x0, top_y))

    draw_text_outlined(draw, (right_x - pad_x - w1, top_y + pad_y - b1[1]), date_text, f1, WHITE, pal.primary, 2, anchor=None, shadow=False)
    draw_text_outlined(draw, (right_x - pad_x - w2, top_y + pad_y + h1 + gap - b2[1]), time_text, f2, pal.accent, pal.primary, 2, anchor=None, shadow=False)


def draw_hero_text(canvas: Image.Image, draw, hero_line: str, script_line: str, left_x: int, baseline_y: int,
                    max_w: int, font_hero: str, font_script: str, bottom_limit: int = CANVAS_H - 20,
                    pal: Palette = Palette()):
    if hero_line:
        hf = fit_font(hero_line.upper(), font_hero, max_w, max_size=150, min_size=48)
        draw_text_outlined(draw, (left_x, baseline_y), hero_line.upper(), hf, WHITE, (0, 0, 0), 9)
        hb = draw.textbbox((left_x, baseline_y), hero_line.upper(), font=hf)
        hero_bottom = hb[3]
        hero_left = hb[0]
    else:
        hero_bottom = baseline_y
        hero_left = left_x

    if script_line:
        sx = hero_left + (40 if hero_line else 0)
        sy = hero_bottom - 16
        max_h = max(40, bottom_limit - sy)
        sf = fit_font_box(script_line, font_script, max_w * 0.85, max_h, max_size=120, min_size=36)
        draw_text_outlined(draw, (sx, sy), script_line, sf, pal.accent, _shade(pal.accent, 0.18), 4)


def draw_live_badge(canvas: Image.Image, draw, pos, font_body: str, pal: Palette = Palette(), label: str = "LIVE"):
    x, y = pos
    label = (label or "LIVE").upper()
    font = _font(font_body, 20)
    w, h = max(104, int(draw.textlength(label, font=font)) + 56), 38
    panel = rounded_panel((w, h), h // 2, (10, 10, 12, 210))
    canvas.alpha_composite(panel, (x, y))
    dot_r = 7
    cx, cy = x + 20, y + h // 2
    draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=pal.highlight)
    draw.text((x + 36, y + h / 2), label, font=font, fill=WHITE, anchor="lm")


def _youtube_icon(size=(46, 32)) -> Image.Image:
    icon = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(icon)
    d.rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=8, fill=RED)
    w, h = size
    tri = [(w * 0.40, h * 0.26), (w * 0.40, h * 0.74), (w * 0.72, h * 0.5)]
    d.polygon(tri, fill=WHITE)
    return icon


def draw_subscribe_bar(canvas: Image.Image, draw, handle: str, box, font_body: str,
                       pal: Palette = Palette(), label: str = "SUBSCRIBE"):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    panel = rounded_panel((w, h), h // 2, (8, 10, 16, 195))
    canvas.alpha_composite(panel, (x0, y0))

    icon = _youtube_icon((int(h * 0.62), int(h * 0.46)))
    icon_x, icon_y = x0 + 18, y0 + (h - icon.height) // 2
    canvas.alpha_composite(icon, (icon_x, icon_y))

    handle_font = fit_font(handle, font_body, w - 280, max_size=24, min_size=14)
    htext_x = icon_x + icon.width + 14
    draw.text((htext_x, y0 + h / 2), handle, font=handle_font, fill=WHITE, anchor="lm")

    label = (label or "SUBSCRIBE").upper()
    bfont = _font(font_body, 18)
    btn_w, btn_h = max(132, int(draw.textlength(label, font=bfont)) + 40), int(h * 0.62)
    btn_x0 = x1 - 18 - btn_w
    btn_y0 = y0 + (h - btn_h) // 2
    btn = rounded_panel((btn_w, btn_h), btn_h // 2, tuple(pal.highlight) + (255,))
    canvas.alpha_composite(btn, (btn_x0, btn_y0))
    draw.text((btn_x0 + btn_w / 2, btn_y0 + btn_h / 2), label, font=bfont, fill=WHITE, anchor="mm")


# --------------------------------------------------------------------------
# Public config + entrypoint
# --------------------------------------------------------------------------

@dataclass
class ThumbnailConfig:
    title: str = "YOUR ORGANIZATION NAME"
    presented_by: str = "Presents"
    hero_line: str = "LIVE"
    script_line: str = "Stream"
    date_text: str = "28th June 2026"
    time_text: str = "09:30 AM onwards"

    show_anniversary: bool = True
    anniversary_start_year: str = "1974"
    anniversary_end_year: str = "2026"
    anniversary_number: str = "52"
    anniversary_caption: str = "Years"
    # If set (and the file exists), this image is pasted into the badge box
    # INSTEAD OF the procedurally generated shield -- exactly like logo_path
    # below. Leave as None to auto-generate the badge from the fields above.
    anniversary_badge_path: Optional[str] = None

    show_live_badge: bool = True
    show_subscribe_bar: bool = True
    youtube_handle: str = "@yourchannel"

    logo_path: Optional[str] = field(default_factory=lambda: (
        os.path.join(ASSETS_DIR, "logo.png") if os.path.isfile(os.path.join(ASSETS_DIR, "logo.png")) else None
    ))
    background_path: Optional[str] = None  # if None, one is chosen at random

    # Font roles -- any .ttf/.otf path. Defaults to the bundled fonts; pick a
    # different file (built-in or user-uploaded into fonts/) to restyle text.
    font_title: str = FONT_TITLE      # main title
    font_hero: str = FONT_HERO        # big hero word + badge number
    font_script: str = FONT_SCRIPT    # cursive lines (Presents / occasion / caption)
    font_body: str = FONT_BODY        # date/time, LIVE badge, subscribe bar, badge year/ribbon

    # Theme colours as hex strings (what a colour picker returns).
    primary_color: str = rgb_to_hex(NAVY)     # outlines + badge body
    accent_color: str = rgb_to_hex(GOLD)      # script lines, time, badge number
    highlight_color: str = rgb_to_hex(RED)    # LIVE dot, ribbon, Subscribe button

    # Extra darkening of the whole photo (0-70 %) for busy/bright backgrounds.
    background_dim: int = 0

    # Editable small labels (handy for other languages, e.g. Telugu fonts).
    show_logo: bool = True
    live_label: str = "LIVE"
    subscribe_label: str = "SUBSCRIBE"
    ribbon_text: str = "ANNIVERSARY"

    def palette(self) -> Palette:
        return Palette(
            primary=hex_to_rgb(self.primary_color, NAVY),
            accent=hex_to_rgb(self.accent_color, GOLD),
            highlight=hex_to_rgb(self.highlight_color, RED),
        )


def generate_thumbnail(cfg: ThumbnailConfig) -> Image.Image:
    font_title = _resolve_font(cfg.font_title, FONT_TITLE)
    font_hero = _resolve_font(cfg.font_hero, FONT_HERO)
    font_script = _resolve_font(cfg.font_script, FONT_SCRIPT)
    font_body = _resolve_font(cfg.font_body, FONT_BODY)
    pal = cfg.palette()

    bg_path = cfg.background_path or pick_random_background()
    if bg_path and os.path.isfile(bg_path):
        with Image.open(bg_path) as f:
            f.load()
            canvas = cover_resize_crop(f, CANVAS_W, CANVAS_H).convert("RGBA")
    else:
        canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (60, 40, 70, 255))

    draw_top_bottom_gradient(canvas, dim=cfg.background_dim)
    draw = ImageDraw.Draw(canvas)

    badge_box = (CANVAS_W - 178, 24, CANVAS_W - 24, 224)
    avoid_right = (CANVAS_W - badge_box[0] + 16) if cfg.show_anniversary else 40
    avoid_left = 210 if cfg.show_logo else 40

    if cfg.show_logo:
        paste_logo(canvas, cfg.logo_path)
    draw_title_block(canvas, draw, cfg.title, cfg.presented_by, avoid_left, avoid_right, font_title, font_script, pal)

    if cfg.show_anniversary:
        if cfg.anniversary_badge_path and os.path.isfile(cfg.anniversary_badge_path):
            paste_anniversary_image(canvas, cfg.anniversary_badge_path, badge_box)
        else:
            draw_shield_badge(
                canvas, draw, badge_box,
                cfg.anniversary_start_year, cfg.anniversary_end_year,
                cfg.anniversary_number, cfg.anniversary_caption,
                font_body, font_hero, font_script,
                pal=pal, ribbon_text=cfg.ribbon_text,
            )

    date_top = badge_box[3] + 18 if cfg.show_anniversary else 110
    draw_date_time_panel(canvas, draw, cfg.date_text, cfg.time_text, right_x=CANVAS_W - 40, top_y=date_top,
                          font_body=font_body, pal=pal)

    subscribe_box = (40, CANVAS_H - 84, CANVAS_W - 40, CANVAS_H - 20)
    hero_bottom_limit = (subscribe_box[1] - 14) if cfg.show_subscribe_bar else (CANVAS_H - 20)
    draw_hero_text(canvas, draw, cfg.hero_line, cfg.script_line, left_x=56, baseline_y=400, max_w=860,
                    font_hero=font_hero, font_script=font_script, bottom_limit=hero_bottom_limit, pal=pal)

    if cfg.show_live_badge:
        draw_live_badge(canvas, draw, (56, 178), font_body=font_body, pal=pal, label=cfg.live_label)

    if cfg.show_subscribe_bar:
        draw_subscribe_bar(canvas, draw, cfg.youtube_handle, box=subscribe_box, font_body=font_body,
                           pal=pal, label=cfg.subscribe_label)

    return canvas.convert("RGB")


if __name__ == "__main__":
    img = generate_thumbnail(ThumbnailConfig())
    out_path = os.path.join(HERE, "_preview4.png")
    img.save(out_path)
    print("wrote", out_path)
