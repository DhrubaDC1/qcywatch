# QCY GT2 protocol and watch-face format

Watch: "QCY Watch GT2", platform JL, prototype S3 (model id 0xAAF1), firmware S3_V023, JieLi AC695N.
Sources: QCY app 4.0.7 (SMA `com.szabh.smable3` SDK, `libsmawatchface.so`), HCI captures of the app,
and the app's own `dial.bin` + `*.png.bin` files from a real custom-face sync.

## BLE transport

- Nordic UART service `6e400001-b5a3-f393-e0a9-e50e24dcca9e`; write `…0002` (handle 0x0006, write
  without response), notify `…0003` (handle 0x0008, CCCD 0x0009). The watch is dual-mode; force LE.
- Frame: `AB | flags | len u16 | crc u16 | cmd | key | action | data`. Big-endian. flags `0x01`
  request, `0x11` reply, `0x20` bit = NACK. `len` = data + 3. CRC-16/ARC over cmd..end.
- Actions: `00` update, `10` read, `11` read-continue, `20` create, `30` delete, `40` reset.
- Stop-and-wait: every request gets a reply echoing cmd/key/action; the app retries 3 times.
- Login first: SESSION `03 02` create with `ff ff ff ff`; reply `00` = OK (works unpaired).
- Long frames are split across ATT writes/notifications; reassemble using `len`.

## Watch-face upload (WATCH_FACE `07 01`, action update)

Request data: `type u8 (0) | total size u32 | offset u32 | chunk` (chunk ≤ 1018 bytes, the watch's
IO buffer). Reply data: `status u8 | total size u32 | next offset u32`. Status `0x14` = busy
(preparing flash): resend the same chunk after ~1 s; the app saw it 3 times on the first chunk.
Done when next offset == total size; the watch then shows the new face. Nothing else is sent.

## Face file (little-endian)

```
u16 image_count | u8 element_count | u8 image_format (1)
element_count x 20-byte records:
  u32 data_offset (absolute) | u16 first_image_index | u16 w | u16 h | i16 x | i16 y
  u8 image_count | u8 type (| 0x80 if alpha) | u8 gravity | u8 ignore_black (4)
  u8 play_interval or bottom_offset (0) | u8 left_offset (0)
image_count x u32 image sizes
image data, element by element, contiguous
```

App's face (7 elements, 49 images, 219660 bytes): PREVIEW 280x280 grav 0; BACKGROUND 454x455;
HOUR 54x76 @120,166; MIN 54x76 @252,166; MONTH 24x36 @120,248; DAY 24x36 @192,248;
WEEKDAY 94x36 @260,248 (7 images). Overlays alpha, gravity 9.

Element types: 1 preview, 2 background, 3/4/5 hour/min/sec hands, 6 year, 7 month, 8 day, 9 hour,
10 min, 11 sec, 12 AM/PM, 13 weekday, 14 steps, 15 heart, 16 calories, 17 distance, 18 battery,
19 Bluetooth, 20 hour divider, 21 month divider, 22 icon, 23 dynamic bg, 44 bg image array.

## Image blob (JieLi BmpConvert, 2D-acceleration path)

- `h` x u32 row table: bits 0-20 = byte offset of the row (from blob start), bits 21-31 = row length.
- Row = PackBits RLE of pixels. Byte `0x80|n` (n 1-127): next pixel repeated n times (used for
  runs ≥ 3). Byte `n` (1-127): n literal pixels follow.
- Opaque pixel: RGB565 big-endian (`r>>3, g>>2, b>>3`, truncated). Alpha pixel: `A` then RGB565;
  fully transparent pixels are written `00 00 00` regardless of colour; colours are not premultiplied.
- Blob zero-padded to a multiple of 4 (size field includes the padding).
