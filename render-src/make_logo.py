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


def arc_text(font, text, cx, cy, r, size, fill, tracking=0.0, bottom=False):
    """Glyphs set along a circle; top arc reads clockwise, bottom arc reads left to right."""
    s = size / font.upm
    total = font.width(text, size, tracking)
    ang_total = total / r
    parts = []
    # centre angle: -90deg (top) or +90deg (bottom)
    if not bottom:
        a = -math.pi / 2 - ang_total / 2
    else:
        a = math.pi / 2 + ang_total / 2
    for c in text:
        g = font.cmap.get(ord(c))
        adv = font.hmtx[g][0] * s
        mid = a + (adv / 2) / r * (1 if not bottom else -1)
        if c != ' ':
            pen = SVGPathPen(font.gs)
            font.gs[g].draw(pen)
            d = pen.getCommands()
            x = cx + r * math.cos(mid)
            y = cy + r * math.sin(mid)
            rot = math.degrees(mid) + (90 if not bottom else -90)
            cap = font.cap_h(size)
            # glyph baseline sits on the circle (top) / cap line on the circle (bottom)
            dy = 0 if not bottom else cap
            parts.append(f'<path transform="translate({x:.2f} {y:.2f}) rotate({rot:.2f}) translate({-adv/2:.2f} {dy:.2f}) scale({s:.5f} {-s:.5f})" d="{d}"/>')
        a += (adv + tracking) / r * (1 if not bottom else -1)
    return f'<g fill="{fill}">' + ''.join(parts) + '</g>'


def emblem(cx, cy, R, disc=RED, ink=CREAM):
    """Round badge: red disc, cream rings, arc lettering and a big star."""
    p = [f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="{disc}"/>',
         f'<circle cx="{cx}" cy="{cy}" r="{R*0.9:.2f}" fill="none" stroke="{ink}" stroke-width="{R*0.035:.2f}"/>',
         f'<circle cx="{cx}" cy="{cy}" r="{R*0.6:.2f}" fill="none" stroke="{ink}" stroke-width="{R*0.022:.2f}"/>']
    p.append(arc_text(BARLOW, 'ALL STAR', cx, cy, R * 0.66, R * 0.2, ink, tracking=R * 0.05))
    p.append(arc_text(BARLOW, 'BURGERS', cx, cy, R * 0.66, R * 0.2, ink, tracking=R * 0.05, bottom=True))
    p.append(star(cx, cy, R * 0.42, ink))
    for sx in (-1, 1):
        p.append(star(cx + sx * R * 0.745, cy, R * 0.055, ink))
    return ''.join(p)


def wordmark(cx, top, S, ink=CREAM, accent=RED, tagline=None, tag_ink=None):
    """ALL ★ STAR / — BURGERS — / tagline.  Returns (svg, width, height)."""
    parts = []
    size1 = 150 * S
    capA = ANTON.cap_h(size1)
    gapw = 120 * S
    wL = ANTON.width('ALL', size1, 4 * S)
    wR = ANTON.width('STAR', size1, 4 * S)
    W = wL + gapw + wR
    x0 = cx - W / 2
    base = top + capA
    parts.append(ANTON.path('ALL', x0, base, size1, ink, tracking=4 * S))
    parts.append(star(x0 + wL + gapw / 2, base - capA / 2, capA * 0.34, accent))
    parts.append(ANTON.path('STAR', x0 + wL + gapw, base, size1, ink, tracking=4 * S))
    y = base + 26 * S
    size2 = 52 * S
    capB = BARLOW.cap_h(size2)
    trk = 14 * S
    wB = BARLOW.width('BURGERS', size2, trk)
    parts.append(BARLOW.path('BURGERS', cx, y + capB, size2, accent, tracking=trk, anchor='middle'))
    ly = y + capB / 2
    g = 22 * S
    parts.append(f'<rect x="{x0:.2f}" y="{ly - 2.5*S:.2f}" width="{(cx - wB/2 - g) - x0:.2f}" height="{5*S:.2f}" fill="{accent}"/>')
    parts.append(f'<rect x="{cx + wB/2 + g:.2f}" y="{ly - 2.5*S:.2f}" width="{(x0 + W) - (cx + wB/2 + g):.2f}" height="{5*S:.2f}" fill="{accent}"/>')
    y += capB
    if tagline:
        size3 = 30 * S
        cap3 = BARLOW_SB.cap_h(size3)
        y += 30 * S
        parts.append(BARLOW_SB.path(tagline, cx, y + cap3, size3, tag_ink or ink, tracking=9 * S, anchor='middle'))
        y += cap3
    return ''.join(parts), W, y - top


def header_logo(x, cy, S, ink=CREAM, accent=RED):
    """Emblem + ALL STAR / BURGERS."""
    R = 30 * S
    parts = [emblem(x + R, cy, R)]
    tx = x + 2 * R + 14 * S
    size1 = 44 * S
    capA = ANTON.cap_h(size1)
    size2 = 22 * S
    capB = BARLOW.cap_h(size2)
    total = capA + 6 * S + capB
    yA = cy - total / 2 + capA
    parts.append(ANTON.path('ALL STAR', tx, yA, size1, ink, tracking=1.5 * S))
    wA = ANTON.width('ALL STAR', size1, 1.5 * S)
    wB0 = BARLOW.width('BURGERS', size2, 0)
    trk = (wA - wB0) / 6
    parts.append(BARLOW.path('BURGERS', tx, yA + 6 * S + capB, size2, accent, tracking=trk))
    return ''.join(parts), tx + wA - x


def svg(w, h, body, bg=None):
    rect = f'<rect width="{w}" height="{h}" fill="{bg}"/>' if bg else ''
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}" width="{w:.0f}" height="{h:.0f}">'
            f'{rect}{body}</svg>')


def write(path, content):
    with open(path, 'w') as f:
        f.write(content)


# ---------------------------------------------------------------- site logos
body, w, h = wordmark(400, 30, 1.0, tagline='FEITO NA HORA · FEITO COM GARRA', tag_ink=CREAM)
write(os.path.join(OUT, 'logo-badge.svg'), svg(800, h + 60, body))
body, w, h = wordmark(400, 30, 1.0, ink=BLACK, accent=RED, tagline='FEITO NA HORA · FEITO COM GARRA', tag_ink=BLACK)
write(os.path.join(OUT, 'logo-badge-dark.svg'), svg(800, h + 60, body))
write(os.path.join(OUT, 'emblem.svg'), svg(400, 400, emblem(200, 200, 196)))

body, w = header_logo(4, 40, 1.0)
write(os.path.join(OUT, 'logo.svg'), svg(w + 8, 80, body))
body, w = header_logo(4, 40, 1.0, ink=BLACK)
write(os.path.join(OUT, 'logo-dark.svg'), svg(w + 8, 80, body))

write(os.path.join(OUT, 'favicon.svg'), svg(64, 64, emblem(32, 32, 31)))

# ---------------------------------------------------------------- textures
TAG = 'FEITO NA HORA · FEITO COM GARRA'

# box lid top (0.492 x 0.332 m) -> 2400 x 1620: emblem centred, thin frame
W, H = 2400, 1620
lid = [emblem(W / 2, H / 2, 390)]
m = 64
lid.append(f'<rect x="{m}" y="{m}" width="{W-2*m}" height="{H-2*m}" fill="none" stroke="{RED}" stroke-width="5"/>')
for i, (sx, sy) in enumerate(((m + 60, m + 60), (W - m - 60, m + 60), (m + 60, H - m - 60), (W - m - 60, H - m - 60))):
    lid.append(star(sx, sy, 16, RED))
lid.append(BARLOW_SB.path(TAG, W / 2, H - m - 54, 38, CREAM, tracking=12, anchor='middle'))
lid.append(BARLOW_SB.path('ALL STAR BURGERS · SMASH · MOLHO · SHAKE', W / 2, m + 86, 32, CREAM, tracking=10, anchor='middle'))
write(os.path.join(TEX, 'box_lid.svg'), svg(W, H, ''.join(lid), bg=BLACK))

# lid underside: big wordmark (seen when the box is open)
W, H = 2400, 1620
wb, ww, wh = wordmark(W / 2, 0, 3.6, tagline=TAG)
under = [f'<g transform="translate(0 {(H - wh) / 2:.1f})">{wb}</g>']
write(os.path.join(TEX, 'box_lid_inner.svg'), svg(W, H, ''.join(under), bg=BLACK))

# box front (0.48 x 0.15 m) -> 2400 x 750 : emblem left + wordmark right
W, H = 2400, 750
fr = [emblem(560, H * 0.56, 190)]
wb, ww, wh = wordmark(1420, 0, 2.0, tagline=TAG)
fr.append(f'<g transform="translate(0 {H * 0.56 - wh / 2:.1f})">{wb}</g>')
write(os.path.join(TEX, 'box_front.svg'), svg(W, H, ''.join(fr), bg=BLACK))

# fries carton (black) -> 1000 x 1100
W, H = 1000, 1100
fc = [emblem(W / 2, H * 0.6, 230)]
fc.append(f'<rect x="0" y="{H - 90}" width="{W}" height="14" fill="{RED}"/>')
write(os.path.join(TEX, 'fries_front.svg'), svg(W, H, ''.join(fc), bg=BLACK))

# cup decal: two emblems on a transparent band -> 2400 x 600
W, H = 2400, 600
cb = [emblem(600, H / 2, 270), emblem(1800, H / 2, 270)]
write(os.path.join(TEX, 'cup_band.svg'), svg(W, H, ''.join(cb)))
print('ok')
