"""The house style for a field-card plate: a square crop of a photograph, one ink colour on
paper, a soft vignette. Every plate goes through this so 79 photographs from 79 phones read
as one set. Pillow + NumPy only, so it runs wherever the pipeline does.

    python3 duotone.py in.jpg out.jpg [--crop x0,y0,x1,y1] [--size 660]

Ink is stone-900 (#2b2620, the body text colour) and paper is the surface colour (#fffdf7),
both from client/src/design-system/tokens/colors.css; pass --ink/--paper to change them.
"""
import sys
import numpy as np
from PIL import Image, ImageFilter, ImageOps

INK = (0x2B, 0x26, 0x20)
PAPER = (0xFF, 0xFD, 0xF7)


def _hex(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def square_crop(im, crop=None):
    w, h = im.size
    if crop:
        x0, y0, x1, y1 = crop
        im = im.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
        w, h = im.size
    n = min(w, h)
    x, y = (w - n) // 2, (h - n) // 2
    return im.crop((x, y, x + n, y + n))


def duotone(im, size=660, ink=INK, paper=PAPER, lift=0.06, gamma=0.95, vignette=0.22):
    im = ImageOps.exif_transpose(im).convert("L").resize((size, size), Image.LANCZOS)
    # local contrast: unsharp at a large radius is the Pillow-only stand-in for CLAHE
    im = ImageOps.autocontrast(im, cutoff=1)
    im = im.filter(ImageFilter.UnsharpMask(radius=40, percent=35, threshold=0))
    g = np.asarray(im).astype(np.float32) / 255.0
    g = np.clip((g - 0.04) / 0.92, 0, 1) ** gamma
    g = lift + (1 - lift) * g
    Y, X = np.ogrid[:size, :size]
    r = np.sqrt(((X - size / 2) / (size / 2)) ** 2 + ((Y - size / 2) / (size / 2)) ** 2)
    g = g * (1 - vignette * np.clip((r - 0.7) / 0.7, 0, 1) ** 1.5)
    ink_a = np.array(ink, np.float32)
    paper_a = np.array(paper, np.float32)
    out = ink_a[None, None, :] * (1 - g[..., None]) + paper_a[None, None, :] * g[..., None]
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    kw, crop = {}, None
    args = sys.argv[3:]
    while args:
        a = args.pop(0)
        if a == "--crop":
            crop = tuple(float(x) for x in args.pop(0).split(","))
        elif a == "--size":
            kw["size"] = int(args.pop(0))
        elif a == "--ink":
            kw["ink"] = _hex(args.pop(0))
        elif a == "--paper":
            kw["paper"] = _hex(args.pop(0))
    out = duotone(square_crop(Image.open(src), crop), **kw)
    out.save(dst, quality=84, optimize=True)
    print("wrote", dst, out.size)
