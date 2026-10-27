"""EBaC's icon (a red Bible with a gold cross), drawn at any size, as in the
EBaC app (ebac-ha-app's icon.png, 128 pixels), for the brand images:

    python3 tools/draw_icon.py 256 custom_components/ebac/brand/icon.png \
        512 custom_components/ebac/brand/icon@2x.png

Coordinates are in the 128-pixel units of the app's icon.
"""
import sys
from PIL import Image, ImageDraw

COVER, SPINE, OUTLINE = (122, 30, 36), (95, 20, 26), (71, 15, 20)
PAGES, PAGE_EDGE, GOLD = (243, 234, 208), (123, 103, 73), (230, 185, 70)

def icon(size):
    ss = 4                                  # supersampling
    k = size * ss / 128
    im = Image.new("RGBA", (size * ss, size * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    s = lambda *v: [round(x * k) for x in v]
    # the pages, behind the cover, down and to the right
    d.rounded_rectangle(s(24, 20, 115, 117), radius=round(6 * k), fill=PAGES,
                        outline=PAGE_EDGE, width=round(1.2 * k))
    # the cover
    d.rounded_rectangle(s(15.5, 15.5, 108, 110), radius=round(8 * k), fill=COVER,
                        outline=OUTLINE, width=round(1.5 * k))
    # the spine's band
    d.rectangle(s(25, 16.5, 30, 109), fill=SPINE)
    # the cross
    d.rectangle(s(64, 30, 75.5, 90), fill=GOLD)
    d.rectangle(s(49, 41, 91, 52.5), fill=GOLD)
    return im.resize((size, size), Image.LANCZOS)

for size, path in zip(map(int, sys.argv[1::2]), sys.argv[2::2]):
    icon(size).save(path, optimize=True)
