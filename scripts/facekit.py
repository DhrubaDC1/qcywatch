#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""QCY Watch GT2 watch-face file builder / checker (SMA smable3 container, JieLi 2D-accelerated images).

    facekit.py check FACE.bin      decode every image and validate the container
    facekit.py selftest            golden vectors captured from the QCY app

Image codec = JieLi BmpConvert.bitmapConvertBlock (type 3: RGB565, type 4: alpha + RGB565):
one u32 per row (low 21 bits = byte offset, high 11 bits = byte length), each row PackBits-RLE
of big-endian pixels, whole blob zero-padded to 4 bytes. Container = libsmawatchface buildWatchFace.
"""
import struct
import sys

# element types (com.szabh.smable3.watchface.WatchFaceBuilder)
PREVIEW, BACKGROUND = 1, 2
NEEDLE_HOUR, NEEDLE_MIN, NEEDLE_SEC = 3, 4, 5
YEAR, MONTH, DAY, HOUR, MIN, SEC, AMPM, WEEKDAY = 6, 7, 8, 9, 10, 11, 12, 13
STEP, HEART, CALORIE, DISTANCE = 14, 15, 16, 17
DIGIT_COUNT = {MONTH: 10, DAY: 10, HOUR: 10, MIN: 10, SEC: 10, WEEKDAY: 7}  # WEEKDAY image 0 = Sunday

SCREEN = 454          # round AMOLED; background element is SCREEN x (SCREEN + 1), as the app sends
PREVIEW_SIZE = 280


def _pixel(p, alpha):
    r, g, b, a = p
    rgb = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
    if not alpha:
        return rgb.to_bytes(2, "big")
    return b"\0\0\0" if a == 0 else bytes([a]) + rgb.to_bytes(2, "big")


def _row(px):
    out, i, n = bytearray(), 0, len(px)

    def run_at(j):
        k = j
        while k < n and k - j < 127 and px[k] == px[j]:
            k += 1
        return k - j

    while i < n:
        r = run_at(i)
        if r >= 3:
            out += bytes([0x80 | r]) + px[i]
            i += r
            continue
        j = i
        while j < n and j - i < 127 and run_at(j) < 3:
            j += 1
        out += bytes([j - i]) + b"".join(px[i:j])
        i = j
    return bytes(out)


def encode_image(img, alpha):
    """PIL image -> JieLi blob. alpha=True for digits/overlays, False for preview/background."""
    img = img.convert("RGBA")
    w, h = img.size
    raw = img.tobytes()
    data = [raw[i:i + 4] for i in range(0, len(raw), 4)]
    rows = [_row([_pixel(p, alpha) for p in data[y * w:(y + 1) * w]]) for y in range(h)]
    table, off = bytearray(), h * 4
    for r in rows:
        assert len(r) < 2048 and off < (1 << 21), "image too large for the row table"
        table += struct.pack("<I", (len(r) << 21) | off)
        off += len(r)
    blob = bytes(table) + b"".join(rows)
    return blob + b"\0" * (-len(blob) % 4)


def decode_image(blob, w, h, alpha):
    """JieLi blob -> list of raw pixel byte strings (2 or 3 bytes each); raises on corruption."""
    bpp, px = (3 if alpha else 2), []
    for y in range(h):
        e = struct.unpack_from("<I", blob, y * 4)[0]
        off, ln = e & 0x1FFFFF, e >> 21
        row, i = [], off
        while i < off + ln:
            c = blob[i]
            i += 1
            if c & 0x80:
                row += [blob[i:i + bpp]] * (c & 0x7F)
                i += bpp
            else:
                row += [blob[i + k * bpp:i + (k + 1) * bpp] for k in range(c)]
                i += c * bpp
        if len(row) != w:
            raise ValueError(f"row {y}: {len(row)} pixels, expected {w}")
        px += row
    return px


def element(type, x, y, images, w, h, alpha=False, gravity=9):
    """images: list of PIL images (all w x h). gravity 9 = left|top (what the app uses)."""
    return dict(type=type, x=x, y=y, w=w, h=h, alpha=alpha, gravity=gravity,
                images=[encode_image(i, alpha) for i in images])


def build(elements, image_format=1):
    nimg = sum(len(e["images"]) for e in elements)
    out = struct.pack("<HBB", nimg, len(elements), image_format)
    off = 4 + 20 * len(elements) + 4 * nimg
    recs, sizes, idx = bytearray(), bytearray(), 0
    for e in elements:
        recs += struct.pack("<IHHHhhBBBBBB", off, idx, e["w"], e["h"], e["x"], e["y"], len(e["images"]),
                            e["type"] | (0x80 if e.get("alpha") else 0), e.get("gravity", 9),
                            e.get("ignore_black", 4), 0, 0)
        for im in e["images"]:
            sizes += struct.pack("<I", len(im))
            off += len(im)
        idx += len(e["images"])
    return out + bytes(recs) + bytes(sizes) + b"".join(b"".join(e["images"]) for e in elements)


def check(data, verbose=True):
    """Validate container + decode every image. Returns list of element dicts (without images)."""
    nimg, nel, fmt = struct.unpack_from("<HBB", data, 0)
    sizes = struct.unpack_from(f"<{nimg}I", data, 4 + nel * 20)
    if 4 + nel * 20 + nimg * 4 + sum(sizes) != len(data):
        raise ValueError("size fields do not add up to the file length")
    els, pos = [], 4 + nel * 20 + nimg * 4
    for i in range(nel):
        off, idx, w, h, x, y, cnt, typ, grav, *_ = struct.unpack_from("<IHHHhhBBBBBB", data, 4 + i * 20)
        if off != pos:
            raise ValueError(f"element {i}: data offset {off}, expected {pos}")
        t, alpha = typ & 0x7F, bool(typ & 0x80)
        if t in DIGIT_COUNT and cnt != DIGIT_COUNT[t]:
            raise ValueError(f"element {i} (type {t}) has {cnt} images, needs {DIGIT_COUNT[t]}")
        if x < 0 or y < 0 or x + w > SCREEN or y + h > SCREEN + 1:
            raise ValueError(f"element {i} (type {t}) at {x},{y} {w}x{h} is off screen")
        for k in range(cnt):
            decode_image(data[pos:pos + sizes[idx + k]], w, h, alpha)
            pos += sizes[idx + k]
        els.append(dict(type=t, alpha=alpha, x=x, y=y, w=w, h=h, images=cnt, gravity=grav))
        if verbose:
            print(f"  element {i}: type={t} {w}x{h} at ({x},{y}) images={cnt} alpha={int(alpha)}")
    if verbose:
        print(f"ok: {len(data)} bytes, {nel} elements, {nimg} images, format {fmt}")
    return els


def selftest():
    from PIL import Image

    def row(pixels, alpha):
        im = Image.new("RGBA", (len(pixels), 1))
        im.putdata(pixels)
        blob = encode_image(im, alpha)
        return blob[4:4 + (struct.unpack_from("<I", blob)[0] >> 21)].hex()

    W, T, K = (255, 255, 255, 255), (255, 255, 255, 0), (0, 0, 0, 0)
    # rows taken from the QCY app's own converter output (preview background, digit "1")
    assert row([(0, 0, 0, 255)] * 280, False) == "ff0000ff00009a0000"
    assert row([T] * 54, True) == "b6000000"
    assert row([T] * 13 + [W] * 20 + [(255, 255, 255, 0x80)] + [T] * 20, True) == "8d00000094ffffff0180ffff94000000"
    assert row([T] * 13 + [K] * 10 + [(255, 255, 255, 0xBF)] + [W] * 9 + [(255, 255, 255, 0x80)] + [T] * 20, True) \
        == "9700000001bfffff89ffffff0180ffff94000000"
    # first element record of the app's 7-element / 49-image dial.bin
    dummy = lambda n, size=8: [b"\0" * size] * n
    els = [dict(type=PREVIEW, w=280, h=280, x=0, y=0, gravity=0, images=dummy(1))] + \
          [dict(type=t, w=1, h=1, x=0, y=0, images=dummy(n)) for t, n in ((2, 1), (9, 10), (10, 10), (7, 10), (8, 10), (13, 7))]
    assert build(els)[:24].hex() == "310007015401000000001801180100000000010100040000"
    # round trip
    im = Image.new("RGBA", (40, 7), (10, 200, 30, 255))
    im.putpixel((3, 3), (255, 0, 0, 128))
    assert len(decode_image(encode_image(im, True), 40, 7, True)) == 280
    print("facekit selftest ok")


if __name__ == "__main__":
    if sys.argv[1:2] == ["selftest"]:
        selftest()
    elif sys.argv[1:2] == ["check"] and len(sys.argv) == 3:
        try:
            check(open(sys.argv[2], "rb").read())
        except (ValueError, struct.error) as e:
            sys.exit(f"invalid face: {e}")
    else:
        sys.exit(__doc__)
