#!/usr/bin/env python3
"""Generate original, stretchable Fcitx5 UI assets (requires Pillow)."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent / 'liltkey-light'
SCALE = 4


def canvas(size):
    return Image.new('RGBA', (size[0] * SCALE, size[1] * SCALE))


def rounded(image, box, radius, fill, outline=None):
    ImageDraw.Draw(image).rounded_rectangle(
        tuple(round(v * SCALE) for v in box), radius * SCALE,
        fill=fill, outline=outline, width=SCALE)


def save(image, name):
    image.resize((image.width // SCALE, image.height // SCALE),
                 Image.Resampling.LANCZOS).save(OUT / name)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    panel = canvas((96, 96))
    rounded(panel, (12, 14, 84, 86), 13, (30, 48, 68, 38))
    panel = panel.filter(ImageFilter.GaussianBlur(4 * SCALE))
    rounded(panel, (12, 10, 84, 82), 13, '#ffffff', '#e6ebf0')
    save(panel, 'panel.png')

    highlight = canvas((32, 32))
    rounded(highlight, (0, 0, 31.75, 31.75), 9, '#0078d4')
    save(highlight, 'highlight.png')

    for name, points in {
        'prev.png': [(11, 4), (6, 9), (11, 14)],
        'next.png': [(7, 4), (12, 9), (7, 14)],
        'submenu.png': [(7, 4), (12, 9), (7, 14)],
        'check.png': [(4, 9), (8, 13), (14, 5)],
    }.items():
        icon = canvas((18, 18))
        ImageDraw.Draw(icon).line([(x * SCALE, y * SCALE) for x, y in points],
                                 fill='#718096', width=2 * SCALE, joint='curve')
        save(icon, name)


if __name__ == '__main__':
    main()
