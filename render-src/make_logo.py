"""Generates the ALL STAR BURGERS logo as self-contained SVG (glyphs converted
to paths with fontTools) plus the SVG artwork used as textures in Blender.

usage: python make_logo.py <fonts_dir> <svg_out_dir> <texture_svg_dir>
"""
import math
import os
import sys

from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen

FONTS, OUT, TEX = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)
os.makedirs(TEX, exist_ok=True)

BLACK = '#0d0b0a'
CREAM = '#f3e9d2'
RED = '#d62718'
ORANGE = '#ff7a1a'


class Font:
    def __init__(self, path):
        self.f = TTFont(path)
        self.gs = self.f.getGlyphSet()
        self.cmap = self.f.getBestCmap()
        self.upm = self.f['head'].unitsPerEm
        self.hmtx = self.f['hmtx']
        os2 = self.f['OS/2']
        self.cap = getattr(os2, 'sCapHeight', 0) or self.upm * 0.7

    def width(self, text, size, tracking=0.0):
        s = size / self.upm
        w = 0
        for c in text:
            g = self.cmap.get(ord(c))
            w += self.hmtx[g][0] * s + tracking
        return w - tracking

    def cap_h(self, size):
        return self.cap * size / self.upm

    def path(self, text, x, y, size, fill, tracking=0.0, anchor='start'):
        """y is the baseline. Returns svg <g>."""
        s = size / self.upm
        if anchor == 'middle':
            x -= self.width(text, size, tracking) / 2
        elif anchor == 'end':
            x -= self.width(text, size, tracking)
        parts = []
        for c in text:
            g = self.cmap.get(ord(c))
            if c != ' ':
                pen = SVGPathPen(self.gs)
                self.gs[g].draw(pen)
                d = pen.getCommands()
                if d:
                    parts.append(f'<path transform="translate({x:.2f} {y:.2f}) scale({s:.5f} {-s:.5f})" d="{d}"/>')
            x += self.hmtx[g][0] * s + tracking
        return f'<g fill="{fill}">' + ''.join(parts) + '</g>'


ANTON = Font(os.path.join(FONTS, 'Anton-Regular.ttf'))
BARLOW = Font(os.path.join(FONTS, 'BarlowCondensed-Bold.ttf'))
BARLOW_SB = Font(os.path.join(FONTS, 'BarlowCondensed-SemiBold.ttf'))


def star_points(cx, cy, R, r=None, rot=-90):
    r = r if r is not None else R * 0.43
    pts = []
    for i in range(10):
        rad = R if i % 2 == 0 else r
        a = math.radians(rot + i * 36)
        pts.append(f'{cx + rad * math.cos(a):.2f},{cy + rad * math.sin(a):.2f}')
    return ' '.join(pts)


def star(cx, cy, R, fill, r=None):
    return f'<polygon points="{star_points(cx, cy, R, r)}" fill="{fill}" stroke="{fill}" stroke-width="{R*0.06:.2f}" stroke-linejoin="round"/>'


def badge(cx, top, scale, cream=CREAM, accent=ORANGE, star_col=None):
    """Stacked logo. Returns (svg, width, height)."""
    star_col = star_col or accent
    S = scale
    parts = []
    y = top
    R = 34 * S
    parts.append(star(cx, y + R, R, star_col))
    y += 2 * R + 14 * S
    size1 = 150 * S
    capA = ANTON.cap_h(size1)
    parts.append(ANTON.path('ALL STAR', cx, y + capA, size1, cream, tracking=4 * S, anchor='middle'))
    wA = ANTON.width('ALL STAR', size1, 4 * S)
    y += capA + 22 * S
    size2 = 46 * S
    capB = BARLOW.cap_h(size2)
    trk = 15 * S
    wB = BARLOW.width('BURGERS', size2, trk)
    parts.append(BARLOW.path('BURGERS', cx, y + capB, size2, accent, tracking=trk, anchor='middle'))
    ly = y + capB / 2
    gap = 18 * S
    x1 = cx - wB / 2 - gap
    x2 = cx + wB / 2 + gap
    parts.append(f'<rect x="{cx - wA/2:.2f}" y="{ly - 2*S:.2f}" width="{x1 - (cx - wA/2):.2f}" height="{4*S:.2f}" fill="{accent}"/>')
    parts.append(f'<rect x="{x2:.2f}" y="{ly - 2*S:.2f}" width="{(cx + wA/2) - x2:.2f}" height="{4*S:.2f}" fill="{accent}"/>')
    y += capB
    return ''.join(parts), wA, y - top


def horizontal(x, cy, scale, cream=CREAM, accent=ORANGE):
    """Header logo: star + ALL STAR / BURGERS stacked to the right."""
    S = scale
    parts = []
    R = 26 * S
    parts.append(star(x + R, cy, R, accent))
    tx = x + 2 * R + 14 * S
    size1 = 52 * S
    capA = ANTON.cap_h(size1)
    size2 = 23 * S
    capB = BARLOW.cap_h(size2)
    total = capA + 7 * S + capB
    yA = cy - total / 2 + capA
    parts.append(ANTON.path('ALL STAR', tx, yA, size1, cream, tracking=1.5 * S))
    wA = ANTON.width('ALL STAR', size1, 1.5 * S)
    wB0 = BARLOW.width('BURGERS', size2, 0)
    trk = (wA - wB0) / 6
    parts.append(BARLOW.path('BURGERS', tx, yA + 7 * S + capB, size2, accent, tracking=trk))
    return ''.join(parts), tx + wA - x


def svg(w, h, body, bg=None):
    rect = f'<rect width="{w}" height="{h}" fill="{bg}"/>' if bg else ''
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}" width="{w:.0f}" height="{h:.0f}">'
            f'{rect}{body}</svg>')


def write(path, content):
    with open(path, 'w') as f:
        f.write(content)


# ---------------------------------------------------------------- site logos
body, w, h = badge(400, 20, 1.0)
write(os.path.join(OUT, 'logo-badge.svg'), svg(800, h + 40, body))
body, w, h = badge(400, 20, 1.0, cream=BLACK, accent=RED)
write(os.path.join(OUT, 'logo-badge-dark.svg'), svg(800, h + 40, body))

body, w = horizontal(4, 40, 1.0)
write(os.path.join(OUT, 'logo.svg'), svg(w + 8, 80, body))
body, w = horizontal(4, 40, 1.0, cream=BLACK, accent=RED)
write(os.path.join(OUT, 'logo-dark.svg'), svg(w + 8, 80, body))

# favicon: orange star on black rounded square
fav = (f'<rect width="64" height="64" rx="14" fill="{BLACK}"/>' + star(32, 34, 24, ORANGE))
write(os.path.join(OUT, 'favicon.svg'), svg(64, 64, fav))

# ---------------------------------------------------------------- textures
# box lid top (box is 0.44 x 0.30 m)  -> 2200 x 1500
W, H = 2200, 1500
b, bw, bh = badge(W / 2, 0, 2.15)
lid = [f'<g transform="translate(0 {(H - bh) / 2 - 10:.1f})">{b}</g>']
m = 70
lid.append(f'<rect x="{m}" y="{m}" width="{W-2*m}" height="{H-2*m}" fill="none" stroke="{ORANGE}" stroke-width="6"/>')
lid.append(f'<rect x="{m+22}" y="{m+22}" width="{W-2*m-44}" height="{H-2*m-44}" fill="none" stroke="{CREAM}" stroke-opacity="0.35" stroke-width="2"/>')
for (sx, sy) in ((m + 70, m + 70), (W - m - 70, m + 70), (m + 70, H - m - 70), (W - m - 70, H - m - 70)):
    lid.append(star(sx, sy, 18, ORANGE))
lid.append(BARLOW_SB.path('HAMBURGUERIA ARTESANAL', W / 2, H - m - 62, 40, CREAM, tracking=12, anchor='middle'))
lid.append(BARLOW_SB.path('FEITO NA BRASA · SERVIDO COM ATITUDE', W / 2, m + 92, 34, CREAM, tracking=9, anchor='middle'))
write(os.path.join(TEX, 'box_lid.svg'), svg(W, H, ''.join(lid), bg=BLACK))

# box front (0.44 x 0.19 m) -> 2200 x 950 ; lid skirt (0.44 x 0.04) shares the stripe
W, H = 2200, 950
fr = []
hb, hw = horizontal(0, 0, 4.2)
fr.append(f'<g transform="translate({(W - hw) / 2:.1f} {H*0.6:.1f})">{hb}</g>')
fr.append(f'<rect x="0" y="{H-70}" width="{W}" height="22" fill="{ORANGE}"/>')
fr.append(f'<rect x="0" y="{H-40}" width="{W}" height="10" fill="{RED}"/>')
write(os.path.join(TEX, 'box_front.svg'), svg(W, H, ''.join(fr), bg=BLACK))

# fries carton front (red) -> 1000 x 1100
W, H = 1000, 1100
fc = []
b, bw, bh = badge(W / 2, 0, 1.25, cream=CREAM, accent=BLACK, star_col=CREAM)
fc.append(f'<g transform="translate(0 {H*0.36:.1f})">{b}</g>')
write(os.path.join(TEX, 'fries_front.svg'), svg(W, H, ''.join(fc), bg=RED))

# shake cup band: black stripe with repeated wordmark -> 2400 x 400
W, H = 2400, 400
sb = []
for i in range(3):
    hb, hw = horizontal(0, 0, 2.3)
    sb.append(f'<g transform="translate({i * 800 + (800 - hw) / 2:.1f} {H/2:.1f})">{hb}</g>')
sb.append(f'<rect x="0" y="18" width="{W}" height="8" fill="{ORANGE}"/>')
sb.append(f'<rect x="0" y="{H-26}" width="{W}" height="8" fill="{ORANGE}"/>')
write(os.path.join(TEX, 'cup_band.svg'), svg(W, H, ''.join(sb), bg=BLACK))
print('ok')
