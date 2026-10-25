---
name: qcy-watchface
description: Design a custom watch face for the user's QCY Watch GT2 (round 454x454, JieLi/SMA firmware) and install it over Bluetooth LE from this Linux PC. Use when asked to make, change, preview, or upload a watch face / dial for the QCY GT2, or to control the watch from the PC (battery, find, time sync, notifications) with qcywatch.
---

# QCY GT2 watch faces

Everything here was reverse engineered from the QCY app (com.qcymall.googleearphonesetup 4.0.7) and
verified against its real output: the builder reproduces the app's own `dial.bin` byte for byte, and
faces built this way have installed successfully. Format details: [reference.md](reference.md).

Tools (in `scripts/`, run directly; they bootstrap their own deps with `uv`):

| Tool | Purpose |
|---|---|
| `makeface.py OUTDIR [options]` | Generate a digital face (HH:MM, MM-DD, weekday, optional photo). |
| `facekit.py` | Library + `check FACE.bin` + `selftest`. Use it to build custom layouts. |
| `qcywatch` | BLE client (link it onto PATH if you like): `face FILE`, `info`, `battery`, `find`, `time`, `notify T B`, `selftest`. |

## Workflow

1. **Agree the design.** Ask only what is missing: colours, photo background, label text, style.
   Defaults: black AMOLED background, white time, orange (`#ff8c42`) accents, minute ticks.
2. **Generate.** Write output to a fresh directory (the scratchpad is fine):
   ```
   scripts/makeface.py OUT --accent '#3ddc97' --bg-image ~/Pictures/x.jpg --label '' --no-ticks
   ```
   Options: `--accent --time-color --date-color --bg-image --dim (photo brightness, 0.45) --label
   --no-ticks --font --font-med`. For anything else, copy `makeface.py` and edit it, or write a
   new script against `facekit` (see "Custom layouts").
3. **Look at it.** Read `OUT/face_full.png` (the watch screen at 10:09 Sunday) with the image viewer
   tool and fix contrast, overlaps or clipping before going further. Show it to the user.
4. **Check the file.** `makeface.py` already runs `facekit.check`; for hand-built files run
   `scripts/facekit.py check OUT/face.bin`. Never upload a file that fails this check.
5. **Free the watch.** It accepts one BLE connection, so the phone must let go: ask the user to turn
   the phone's Bluetooth off. If the phone is on ADB and the user has agreed, use
   `adb -s SERIAL shell cmd bluetooth_manager disable` (and `enable` afterwards).
6. **Upload.** `qcywatch face OUT/face.bin` (≈30 s for 110 KB). Success prints `face installed`;
   the watch switches to the face by itself.
7. **Confirm and restore.** You cannot see the watch: ask the user whether it shows the face.
   Re-enable the phone's Bluetooth.

## Custom layouts with facekit

```python
import facekit as fk   # sys.path.insert(0, "<skill>/scripts")
els = [
    fk.element(fk.PREVIEW, 0, 0, [preview_280], 280, 280, gravity=0),   # face-picker thumbnail
    fk.element(fk.BACKGROUND, 0, 0, [bg_454x455], 454, 455),            # note: height 455
    fk.element(fk.HOUR, x, y, ten_digit_images, w, h, alpha=True),       # 10 images "0".."9"
    ...
]
open("face.bin", "wb").write(fk.build(els)); fk.check(open("face.bin", "rb").read())
```

Rules (from the working app face; break them only knowingly):
- Keep the element order: PREVIEW, BACKGROUND, then overlays. Preview 280x280 opaque, circle-masked.
- Background is opaque, exactly 454 wide x 455 high. Static decoration (colons, dashes, labels,
  ticks) goes into the background.
- Digit elements (HOUR, MIN, MONTH, DAY, SEC) carry 10 images `0`-`9`, all the element's `w`x`h`,
  `alpha=True`. The watch draws **two** digits side by side from (x, y), so the pair spans `2*w`.
- WEEKDAY carries 7 images, index 0 = **Sunday**.
- x, y are the top-left corner (gravity 9). Everything must fit inside 454x455.
- Tested on the watch: PREVIEW, BACKGROUND, HOUR, MIN, MONTH, DAY, WEEKDAY. Hands (3-5), SEC (11),
  AM/PM (12) and step/heart/calorie/distance (14-17) exist in the format but are untested; say so
  before using them, and expect to iterate with the user.
- Keep files modest; the largest tested upload was 220 KB.

## Troubleshooting

| qcywatch says | Do |
|---|---|
| `watch not advertising` | Phone still connected: turn its Bluetooth off; move the watch closer. |
| `connected over Classic Bluetooth` | `/etc/bluetooth/main.conf` needs `Experimental = true`, then `sudo systemctl restart bluetooth` (user runs it). |
| `watch did not reply` / `failed to discover services` | Weak signal (RSSI below about -85 dBm) or low battery: move closer and retry. |
| `watch refused the face (status 0x..)` | Status 0x14 (busy) for over 30 s. Retry once; if it persists, stop and report. |
| `not a valid watch face file` | The file failed the container check; rebuild it. |

Run `qcywatch selftest` and `scripts/facekit.py selftest` after editing either tool.
By default qcywatch connects to the first watch advertising as "QCY Watch GT2"; pin one with
`--addr` or `QCY_WATCH=AA:BB:...` (find it with `qcywatch info`).
