"""
build_backgrounds.py
---------------------
One-off utility that procedurally generates a starter set of warm
gradient + bokeh "light" background images into the backgrounds/ folder,
so the thumbnail app has variety to pick from the moment it's installed --
no stock-photo API key required.

These are intentionally abstract (gradients + soft light orbs) so there
are zero licensing concerns. For best results, drop your own real photos
(.jpg/.png) into backgrounds/ -- the app will mix them in automatically.

Run once with:  python build_backgrounds.py
"""

import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 1920, 1080  # generate at higher res than 1280x720 so crops stay sharp

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backgrounds")

# A handful of warm-toned color palettes (top color, bottom color)
PALETTES = [
    ((255, 196, 84), (120, 30, 20)),   # golden sunset -> deep maroon
    ((255, 158, 90), (40, 18, 60)),    # amber -> twilight purple
    ((250, 140, 60), (25, 25, 70)),    # orange -> midnight blue
    ((255, 210, 120), (90, 20, 40)),   # warm gold -> wine red
    ((255, 170, 110), (20, 40, 70)),   # peach -> deep navy
    ((255, 200, 100), (60, 15, 15)),   # honey -> dark ember
    ((245, 180, 130), (35, 35, 35)),   # soft amber -> charcoal
    ((255, 224, 150), (70, 25, 55)),   # cream gold -> plum
]


def vertical_gradient(top_color, bottom_color, w=W, h=H):
    top = np.array(top_color, dtype=np.float32)
    bottom = np.array(bottom_color, dtype=np.float32)
    t = np.linspace(0, 1, h, dtype=np.float32).reshape(h, 1, 1)
    grad = top.reshape(1, 1, 3) * (1 - t) + bottom.reshape(1, 1, 3) * t
    grad = np.repeat(grad, w, axis=1).astype(np.uint8)
    return Image.fromarray(grad, mode="RGB")


def add_bokeh(img, n_orbs=18, seed=0):
    rng = random.Random(seed)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = img.size
    for _ in range(n_orbs):
        r = rng.randint(int(0.02 * w), int(0.09 * w))
        x = rng.randint(0, w)
        y = rng.randint(0, h)
        alpha = rng.randint(35, 90)
        color = (255, rng.randint(200, 235), rng.randint(140, 200), alpha)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=color)
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=max(8, int(0.01 * w))))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def add_light_rays(img, seed=0):
    rng = random.Random(seed)
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    cx, cy = rng.randint(int(w * 0.2), int(w * 0.8)), rng.randint(-int(h * 0.2), int(h * 0.3))
    for i in range(10):
        angle = math.radians(rng.uniform(0, 360))
        length = w * 1.4
        width = rng.uniform(0.01, 0.035) * w
        dx, dy = math.cos(angle) * length, math.sin(angle) * length
        perp = (-dy, dx)
        norm = math.hypot(*perp) or 1
        perp = (perp[0] / norm * width, perp[1] / norm * width)
        pts = [
            (cx + perp[0], cy + perp[1]),
            (cx - perp[0], cy - perp[1]),
            (cx - perp[0] + dx, cy - perp[1] + dy),
            (cx + perp[0] + dx, cy + perp[1] + dy),
        ]
        draw.polygon(pts, fill=(255, 235, 190, rng.randint(8, 18)))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=20))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def add_grain(img, amount=6, seed=0):
    rng = np.random.default_rng(seed)
    arr = np.array(img).astype(np.int16)
    noise = rng.integers(-amount, amount + 1, arr.shape, dtype=np.int16)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def vignette(img, strength=0.55):
    w, h = img.size
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = w / 2, h / 2
    dist = np.sqrt(((xx - cx) / (w / 2)) ** 2 + ((yy - cy) / (h / 2)) ** 2)
    mask = np.clip(1 - strength * (dist - 0.4), 0, 1)
    mask = (mask * 255).astype(np.uint8)
    mask_img = Image.fromarray(mask, mode="L").filter(ImageFilter.GaussianBlur(60))
    black = Image.new("RGB", img.size, (0, 0, 0))
    return Image.composite(img, black, mask_img)


def make_background(idx, palette, seed):
    top, bottom = palette
    img = vertical_gradient(top, bottom)
    img = add_light_rays(img, seed=seed)
    img = add_bokeh(img, n_orbs=22, seed=seed + 1)
    img = img.filter(ImageFilter.GaussianBlur(radius=2))
    img = vignette(img, strength=0.45)
    img = add_grain(img, amount=4, seed=seed + 2)
    return img


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for i, palette in enumerate(PALETTES):
        img = make_background(i, palette, seed=i * 7 + 3)
        path = os.path.join(OUT_DIR, f"background_{i + 1:02d}.jpg")
        img.save(path, quality=92)
        print("wrote", path)


if __name__ == "__main__":
    main()
