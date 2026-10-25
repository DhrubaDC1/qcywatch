#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Generate a digital QCY GT2 watch face: HH:MM, MM-DD, weekday, optional photo background.

usage: makeface.py OUTDIR [--accent '#ff8c42'] [--time-color '#ffffff'] [--date-color '#dcdcdc']
                          [--bg-image PHOTO] [--dim 0.45] [--label GT2] [--no-ticks] [--font TTF]
Writes OUTDIR/face.bin (upload this), preview.png, face_full.png (look at this), background.png.
"""
import argparse
import math
import os
import subprocess
import sys

from PIL import Image, ImageColor, ImageDraw, ImageEnhance, ImageFont, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import facekit as fk

S = fk.SCREEN
WEEK = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]  # watch picks image 0 on Sunday
TW, TH, COLON = 62, 96, 28                 # time digit cell, colon gap
TX, TY = (S - (4 * TW + COLON)) // 2, 142
DW, DH, DASH, GAP, WKW = 26, 38, 18, 20, 94  # date digit cell, dash, gap, weekday cell
DX, DY = (S - (4 * DW + DASH + GAP + WKW)) // 2, 268


def rgb(s):
    return ImageColor.getrgb(s)[:3]


def font_file(path, fallback):
    if os.path.exists(path):
        return path
    try:  # fontconfig is on every Linux desktop; ask it for something close
        found = subprocess.run(["fc-match", "-f", "%{file}", fallback], capture_output=True, text=True).stdout
    except FileNotFoundError:
        found = ""
    if not found or not os.path.exists(found):
        sys.exit(f"font {path} not found; pass --font/--font-med with a .ttf path")
    return found


def glyphs(texts, w, h, font, size, color):
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    while size > 8:  # shrink until the widest/tallest glyph fits its cell (wide fallback fonts)
        f = ImageFont.truetype(font, size)
        boxes = [probe.textbbox((0, 0), t, font=f) for t in texts]
        if all(r - l <= w and b - t0 <= h for l, t0, r, b in boxes):
            break
        size -= 2
    out = []
    for t in texts:
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        l, t0, r, b = d.textbbox((0, 0), t, font=f)
        d.text(((w - (r - l)) / 2 - l, (h - (b - t0)) / 2 - t0), t, font=f, fill=color + (255,))
        out.append(im)
    return out


def background(a):
    im = Image.new("RGB", (S, S + 1), (0, 0, 0))  # app sends screenHeight + 1 rows
    if a.bg_image:
        photo = ImageOps.fit(Image.open(a.bg_image).convert("RGB"), (S, S + 1), Image.LANCZOS)
        im = ImageEnhance.Brightness(photo).enhance(a.dim)  # keep digits readable
    d = ImageDraw.Draw(im)
    c, acc = S / 2, rgb(a.accent)
    if a.ticks:
        for i in range(60):
            ang = math.radians(i * 6 - 90)
            r1, r2, col, wid = (196, 216, acc, 5) if i % 5 == 0 else (206, 214, (70, 70, 70), 2)
            d.line([(c + r1 * math.cos(ang), c + r1 * math.sin(ang)), (c + r2 * math.cos(ang), c + r2 * math.sin(ang))],
                   fill=col, width=wid)
    # static separators live in the background
    x = TX + 2 * TW + COLON // 2
    for y in (TY + 30, TY + 64):
        d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=acc)
    x = DX + 2 * DW
    d.rectangle([x + 4, DY + DH // 2 - 2, x + DASH - 4, DY + DH // 2 + 2], fill=rgb(a.date_color))
    if a.label:
        d.text((c, 356), a.label, font=ImageFont.truetype(a.font_med, 22), fill=(110, 110, 110), anchor="mm")
    return im


def main():
    p = argparse.ArgumentParser()
    p.add_argument("out")
    p.add_argument("--accent", default="#ff8c42")
    p.add_argument("--time-color", default="#ffffff")
    p.add_argument("--date-color", default="#dcdcdc")
    p.add_argument("--bg-image")
    p.add_argument("--dim", type=float, default=0.45, help="photo brightness factor")
    p.add_argument("--label", default="GT2")
    p.add_argument("--no-ticks", dest="ticks", action="store_false")
    p.add_argument("--font", default="/usr/share/fonts/noto/NotoSans-CondensedBold.ttf")
    p.add_argument("--font-med", default="/usr/share/fonts/noto/NotoSans-SemiCondensedBold.ttf")
    a = p.parse_args()
    a.font = font_file(a.font, "sans:bold:condensed")
    a.font_med = font_file(a.font_med, "sans:bold")
    os.makedirs(a.out, exist_ok=True)

    bg = background(a)
    tdig = glyphs([str(i) for i in range(10)], TW, TH, a.font, 104, rgb(a.time_color))
    ddig = glyphs([str(i) for i in range(10)], DW, DH, a.font_med, 34, rgb(a.date_color))
    week = glyphs(WEEK, WKW, DH, a.font_med, 32, rgb(a.accent))

    # what the watch will show at 10:09 on Sunday 25 Oct (also becomes the face-picker preview)
    full = bg.convert("RGBA")
    for i, dg in enumerate("1009"):
        full.alpha_composite(tdig[int(dg)], (TX + i * TW + (COLON if i > 1 else 0), TY))
    for i, dg in enumerate("1025"):
        full.alpha_composite(ddig[int(dg)], (DX + i * DW + (DASH if i > 1 else 0), DY))
    full.alpha_composite(week[0], (DX + 4 * DW + DASH + GAP, DY))
    full = full.crop((0, 0, S, S))
    mask = Image.new("L", (fk.PREVIEW_SIZE,) * 2, 0)
    ImageDraw.Draw(mask).ellipse([0, 0, fk.PREVIEW_SIZE - 1, fk.PREVIEW_SIZE - 1], fill=255)
    prev = Image.composite(full.resize((fk.PREVIEW_SIZE,) * 2, Image.LANCZOS),
                           Image.new("RGBA", (fk.PREVIEW_SIZE,) * 2, (0, 0, 0, 255)), mask)

    els = [
        fk.element(fk.PREVIEW, 0, 0, [prev], fk.PREVIEW_SIZE, fk.PREVIEW_SIZE, gravity=0),
        fk.element(fk.BACKGROUND, 0, 0, [bg], S, S + 1),
        fk.element(fk.HOUR, TX, TY, tdig, TW, TH, alpha=True),
        fk.element(fk.MIN, TX + 2 * TW + COLON, TY, tdig, TW, TH, alpha=True),
        fk.element(fk.MONTH, DX, DY, ddig, DW, DH, alpha=True),
        fk.element(fk.DAY, DX + 2 * DW + DASH, DY, ddig, DW, DH, alpha=True),
        fk.element(fk.WEEKDAY, DX + 4 * DW + DASH + GAP, DY, week, WKW, DH, alpha=True),
    ]
    blob = fk.build(els)
    fk.check(blob, verbose=False)
    open(f"{a.out}/face.bin", "wb").write(blob)
    prev.save(f"{a.out}/preview.png")
    full.save(f"{a.out}/face_full.png")
    bg.save(f"{a.out}/background.png")
    print(f"wrote {a.out}/face.bin ({len(blob)} bytes, checked) and {a.out}/face_full.png")


if __name__ == "__main__":
    main()
