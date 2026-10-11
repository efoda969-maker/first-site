"""Turns the rendered square PNG frames into the web image sequences.

  python build_assets.py <seq_png_dir> <menu_png_dir> <site_root>

- desktop: 16:9 centre crop, WebP
- mobile:  9:16 centre crop, WebP
- per-frame edge colours (left, right, top, bottom, average) so the page
  background and legibility shades follow the render
- menu shots: tighter crop, WebP
"""
import json
import os
import sys
import time

from PIL import Image, ImageFilter

SEQ_IN, MENU_IN, ROOT = sys.argv[1], sys.argv[2], sys.argv[3]
OUT = os.path.join(ROOT, 'assets', 'seq')

meta_in = json.load(open(os.path.join(SEQ_IN, 'meta.json')))
N = meta_in['frames']
S = meta_in['size']

SETS = {
    # crop box in square px, output size, quality, safe zone (min visible fraction w, h)
    'desktop': {'crop': (0, (S - S * 9 // 16) // 2, S, S * 9 // 16), 'out': (1280, 720), 'q': 74, 'safe': (0.56, 0.9)},
    'mobile': {'crop': ((S - S * 9 // 16) // 2, 0, S * 9 // 16, S), 'out': (720, 1280), 'q': 70, 'safe': (0.8, 0.62)},
}


def hexc(rgb):
    return '#%02x%02x%02x' % tuple(int(round(c)) for c in rgb)


def mean(img):
    small = img.resize((1, 1), Image.Resampling.BOX)
    return small.getpixel((0, 0))


def edges(img):
    w, h = img.size
    bw, bh = max(2, w // 50), max(2, h // 50)
    L = mean(img.crop((0, 0, bw, h)))
    R = mean(img.crop((w - bw, 0, w, h)))
    T = mean(img.crop((0, 0, w, bh)))
    B = mean(img.crop((0, h - bh, w, h)))
    avg = tuple((L[i] + R[i] + T[i] + B[i]) / 4 for i in range(3))
    return [hexc(L), hexc(R), hexc(T), hexc(B), hexc(avg)]


meta = {'frames': N, 'size': S, 'version': int(time.time()), 'labels': meta_in['labels']}
total = 0
for name, cfg in SETS.items():
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    x, y, w, h = cfg['crop']
    eds = []
    for i in range(N):
        src = Image.open(os.path.join(SEQ_IN, f'{i:04d}.png')).convert('RGB')
        im = src.crop((x, y, x + w, y + h))
        if im.size != cfg['out']:
            im = im.resize(cfg['out'], Image.Resampling.LANCZOS)
        im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=40, threshold=2))
        eds.append(edges(im))
        p = os.path.join(d, f'{i:04d}.webp')
        im.save(p, 'WEBP', quality=cfg['q'], method=6)
        total += os.path.getsize(p)
        if name == 'desktop' and i == 0:
            im.save(os.path.join(OUT, 'poster.webp'), 'WEBP', quality=80, method=6)
    meta[name] = {'ext': 'webp', 'w': cfg['out'][0], 'h': cfg['out'][1], 'crop': [x, y, w, h],
                  'safe': list(cfg['safe']), 'edges': eds}
    size = sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d))
    print(f'{name}: {N} frames, {size / 1e6:.1f} MB')

with open(os.path.join(OUT, 'meta.json'), 'w') as f:
    json.dump(meta, f, ensure_ascii=False, separators=(',', ':'))

# social preview from the combo moment
og = Image.open(os.path.join(SEQ_IN, f'{int(N * 0.6):04d}.png')).convert('RGB')
x, y, w, h = SETS['desktop']['crop']
og.crop((x, y, x + w, y + h)).resize((1200, 675), Image.Resampling.LANCZOS).save(
    os.path.join(ROOT, 'assets', 'img', 'og.jpg'), 'JPEG', quality=84, optimize=True)

# menu
if os.path.isdir(MENU_IN):
    md = os.path.join(ROOT, 'assets', 'img', 'menu')
    os.makedirs(md, exist_ok=True)
    CROP = {'combo': 0.9, 'sauces': 0.6}
    for fn in sorted(os.listdir(MENU_IN)):
        if not fn.endswith('.png'):
            continue
        im = Image.open(os.path.join(MENU_IN, fn)).convert('RGB')
        k = CROP.get(fn[:-4], 0.76)
        W, H = im.size
        cw = int(W * k)
        cx, cy = W // 2, int(H * 0.52)
        box = (cx - cw // 2, cy - cw // 2, cx + cw // 2, cy + cw // 2)
        im = im.crop(box).resize((900, 900), Image.Resampling.LANCZOS)
        im = im.filter(ImageFilter.UnsharpMask(radius=1.0, percent=35, threshold=2))
        im.save(os.path.join(md, fn.replace('.png', '.webp')), 'WEBP', quality=82, method=6)
        print('menu', fn)
