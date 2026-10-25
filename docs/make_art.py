#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Render the README artwork: preset faces built by makeface.py, shown on a watch mockup."""
import math
import os
import random
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
MAKEFACE = os.path.join(HERE, "..", "scripts", "makeface.py")
OUT = os.path.join(HERE, "img")
WORK = os.path.join(OUT, ".work")


def aurora(path, seed, colors):
    """Procedural soft-light background (no third-party photos in the repo)."""
    random.seed(seed)
    im = Image.new("RGB", (454, 455), (4, 6, 14))
    for _ in range(7):
        blob = Image.new("RGB", im.size, random.choice(colors))
        mask = Image.new("L", im.size, 0)
        x, y, r = random.randint(40, 414), random.randint(40, 414), random.randint(90, 190)
        ImageDraw.Draw(mask).ellipse([x - r, y - r, x + r, y + r], fill=random.randint(90, 170))
        im = Image.composite(blob, im, mask.filter(ImageFilter.GaussianBlur(70)))
    im.save(path)


PRESETS = {
    "ember": [],
    "mint": ["--accent", "#3ddc97", "--label", ""],
    "aurora": ["--bg-image", "aurora1", "--dim", "0.9", "--accent", "#7cf3ff", "--no-ticks", "--label", ""],
    "sunset": ["--bg-image", "aurora2", "--dim", "0.85", "--accent", "#ffd166", "--date-color", "#fff1d6",
               "--no-ticks", "--label", ""],
    "mono": ["--accent", "#e8e8e8", "--date-color", "#9a9a9a", "--label", "LINUX"],
}


def watch(face, size=520):
    """Face (454x454) inside a brushed-metal case with lugs and a strap stub."""
    W, H = size, int(size * 1.55)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy, R = W // 2, H // 2, int(size * 0.47)
    strap = (24, 24, 28, 255)
    d.rounded_rectangle([cx - R * 0.62, 0, cx + R * 0.62, cy], radius=40, fill=strap)
    d.rounded_rectangle([cx - R * 0.62, cy, cx + R * 0.62, H], radius=40, fill=strap)
    for i in range(0, H, 22):  # strap texture
        d.line([cx - R * 0.55, i, cx + R * 0.55, i], fill=(32, 32, 37, 255), width=2)
    for r, c in ((R, (70, 72, 78)), (R - 6, (150, 152, 160)), (R - 12, (52, 54, 60)), (R - 20, (8, 8, 10))):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c + (255,))
    d.rounded_rectangle([cx + R - 6, cy - 34, cx + R + 14, cy + 34], radius=8, fill=(120, 122, 130, 255))  # crown
    fr = R - 26
    f = face.convert("RGBA").resize((2 * fr, 2 * fr), Image.LANCZOS)
    m = Image.new("L", f.size, 0)
    ImageDraw.Draw(m).ellipse([0, 0, 2 * fr - 1, 2 * fr - 1], fill=255)
    im.paste(f, (cx - fr, cy - fr), m)
    glare = Image.new("L", f.size, 0)  # glass reflection
    ImageDraw.Draw(glare).pieslice([-fr // 2, -fr, 2 * fr, fr], 200, 300, fill=26)
    im.paste(Image.new("RGBA", f.size, (255, 255, 255, 255)), (cx - fr, cy - fr),
             Image.composite(glare, Image.new("L", f.size, 0), m))
    return im


def backdrop(w, h):
    bg = Image.new("RGB", (w, h), (9, 10, 16))
    glow = Image.new("L", (w, h), 0)
    ImageDraw.Draw(glow).ellipse([w * 0.15, -h * 0.3, w * 0.85, h * 1.1], fill=110)
    return Image.composite(Image.new("RGB", (w, h), (34, 28, 60)), bg, glow.filter(ImageFilter.GaussianBlur(160)))


def place(canvas, wimg, x, y, shadow=True):
    if shadow:
        sh = Image.new("RGBA", wimg.size, (0, 0, 0, 0))
        sh.putalpha(wimg.getchannel("A").point(lambda a: int(a * 0.55)))
        sh = sh.filter(ImageFilter.GaussianBlur(28))
        canvas.alpha_composite(sh, (x + 14, y + 26))
    canvas.alpha_composite(wimg, (x, y))


def main():
    os.makedirs(WORK, exist_ok=True)
    aurora(f"{WORK}/aurora1.png", 3, [(30, 200, 170), (40, 90, 220), (120, 40, 200)])
    aurora(f"{WORK}/aurora2.png", 11, [(250, 110, 60), (230, 60, 110), (120, 40, 160)])
    faces = {}
    for name, opts in PRESETS.items():
        opts = [f"{WORK}/{o}.png" if o.startswith("aurora") else o for o in opts]
        subprocess.run([sys.executable, MAKEFACE, f"{WORK}/{name}", *opts], check=True, capture_output=True)
        faces[name] = Image.open(f"{WORK}/{name}/face_full.png")

    # hero: five watches, centre one forward
    W, H = 1800, 900
    hero = backdrop(W, H).convert("RGBA")
    order = ["mono", "aurora", "ember", "sunset", "mint"]
    scales = [0.62, 0.78, 1.0, 0.78, 0.62]
    xs = [70, 330, 640, 1060, 1330]
    for i in (0, 4, 1, 3, 2):
        wimg = watch(faces[order[i]], int(560 * scales[i]))
        place(hero, wimg, xs[i], (H - wimg.height) // 2)
    hero.convert("RGB").save(f"{OUT}/hero.png", optimize=True)

    # gallery row
    G = backdrop(1800, 560).convert("RGBA")
    for i, name in enumerate(PRESETS):
        wimg = watch(faces[name], 300)
        place(G, wimg, 40 + i * 350, (560 - wimg.height) // 2)
    G.convert("RGB").save(f"{OUT}/gallery.png", optimize=True)
    print("wrote", OUT)


main()
