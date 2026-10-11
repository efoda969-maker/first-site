"""ALL STAR BURGERS - scroll sequence.

Renders the whole story as square frames; the site crops them to 16:9 on
desktop and 9:16 on phones, so every subject is framed inside the central
square-ish safe zone.

  blender -b -P render-src/sequence.py -- --out DIR --frames 180 --size 1440 --samples 10 [--only 0,40,90] [--step 1]

Stage map (p = 0..1, the same numbers drive the text on the website):
  0.00-0.14  burger on white paper, dark table, ad lighting
  0.14-0.40  burger grows, layers separate vertically, dark -> cream
  0.40-0.62  layers stack again, fries / shake / sauces land around it
  0.62-0.95  black box arrives, products hop in, lid closes
  0.95-1.00  hero shot of the closed box
"""
import sys
import os
import json
import math
import time
import argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy
from mathutils import Vector, Euler
from bpy_extras.object_utils import world_to_camera_view

from lib import reset, hexc, lerp, clamp, seg, ease_in_out, ease_out, ease_in, ease_out_back, smooth, empty
from burger import build_burger
from props import build_fries, build_shake, build_sauce_cup, build_box, BOX_H
from env import render_settings, world, build_table, build_paper, area_light, camera, place_camera, CREAM

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True)
ap.add_argument('--frames', type=int, default=180)
ap.add_argument('--size', type=int, default=1440)
ap.add_argument('--samples', type=int, default=10)
ap.add_argument('--only', default='')
ap.add_argument('--step', type=int, default=1)
ap.add_argument('--offset', type=int, default=0)
ap.add_argument('--force', action='store_true')
ap.add_argument('--threads', type=int, default=0)
args = ap.parse_args(argv)
os.makedirs(args.out, exist_ok=True)

# ----------------------------------------------------------------------------
# scene
# ----------------------------------------------------------------------------
reset()
render_settings(args.size, args.size, args.samples, threads=args.threads)
world_bg = world('#050403', 1.0)
table, bgmix = build_table()
paper, paper_alpha = build_paper()
burger, layers = build_burger()
fries = build_fries()
shake = build_shake()
cups = [build_sauce_cup('CupKetchup', '#b3140c', 41), build_sauce_cup('CupCheddar', '#f08a12', 42),
        build_sauce_cup('CupMaionese', '#efe2c0', 43)]
box, hinge = build_box()
cheese_key = None
for k, lr, z, h in layers:
    if k == 'cheese':
        for ch in lr.children:
            if ch.data and getattr(ch.data, 'shape_keys', None):
                cheese_key = ch.data.shape_keys.key_blocks['Flat']

# lights: A = dramatic set around the burger, B = bright cream studio
T0 = (0, 0, 0.048)
LA = [
    (area_light('A_Key', (-0.6, -0.15, 0.55), T0, (0.5, 0.7), 1, spread=38), 7.5),
    (area_light('A_Rim', (0.45, 0.7, 0.3), T0, (0.4, 0.7), 1, spread=45), 13.0),
    (area_light('A_RimL', (-0.5, 0.6, 0.25), T0, (0.3, 0.5), 1, spread=45), 6.5),
    (area_light('A_Top', (0.0, 0.15, 0.9), T0, (0.4, 0.4), 1, spread=24), 1.6),
    (area_light('A_Fill', (0.35, -0.8, 0.12), T0, (0.6, 0.3), 1, spread=60), 1.4),
]
TB = (0, 0.18, 0.06)
LB = [
    (area_light('B_Key', (-1.0, -0.55, 1.2), TB, (1.2, 1.2), 1, spread=75), 32.0),
    (area_light('B_Rim', (0.9, 1.2, 0.8), TB, (1.0, 1.0), 1, spread=70), 26.0),
    (area_light('B_Fill', (0.9, -1.3, 0.45), TB, (1.2, 0.6), 1), 9.0),
    (area_light('B_Top', (0.0, 0.2, 1.7), TB, (1.4, 1.4), 1, spread=80), 14.0),
]
cam = camera(60, 2.8)

# ----------------------------------------------------------------------------
# choreography
# ----------------------------------------------------------------------------
YB = 0.36                       # final box position (behind the combo)
COMBO = {
    'fries': ((-0.118, 0.07, 0.0), 0.28),      # position, z-rotation
    'shake': ((0.118, 0.075, 0.0), -0.2),
    'cups': [((-0.068, -0.108, 0.0), 0.0), ((0.0, -0.128, 0.0), 0.6), ((0.068, -0.108, 0.0), 1.1)],
}
FLOOR = 0.0045
SLOTS = {
    'burger': ((-0.115, YB + 0.0, FLOOR), 0.0),
    'fries': ((0.03, YB + 0.058, FLOOR), 0.0),
    'shake': ((0.145, YB + 0.055, FLOOR), -0.2),
    'cups': [((-0.005, YB - 0.078, FLOOR), 0.0), ((0.07, YB - 0.085, FLOOR), 0.6), ((0.145, YB - 0.08, FLOOR), 1.1)],
}
GAP = 0.022
N_LAYERS = len(layers)

# camera keys: (p, target, dist, elev, azim, fstop)
CAM_KEYS = [
    (0.00, (0, 0, 0.050), 0.72, 12.0, -7.0, 2.8),
    (0.13, (0, 0, 0.050), 0.64, 11.0, 0.0, 2.8),
    (0.20, (0, 0, 0.07), 0.46, 8.0, 4.0, 3.2),       # burger grows
    (0.33, (0, 0, 0.135), 0.98, 7.0, -3.0, 4.5),     # exploded, framed tall (explode-driven, see cam_state)
    (0.40, (0, 0, 0.135), 0.98, 7.0, 3.0, 4.5),      # slow drift while the labels show
    (0.47, (0, 0, 0.06), 0.85, 14.0, -4.0, 4.5),
    (0.58, (0, -0.01, 0.06), 1.38, 21.0, -2.0, 6.0), # combo
    (0.63, (0, -0.01, 0.06), 1.38, 21.0, 2.0, 6.0),
    (0.71, (0, 0.16, 0.08), 1.95, 28.0, 0.0, 7.0),   # box arrives behind
    (0.82, (0, YB, 0.1), 1.8, 38.0, 0.0, 7.0),       # packing, looking in
    (0.89, (0, YB, 0.1), 1.8, 36.0, 0.0, 7.0),
    (0.97, (0, YB, 0.085), 1.9, 24.0, 16.0, 7.0),    # hero
    (1.00, (0, YB, 0.085), 1.86, 24.0, 19.0, 7.0),
]


def cam_keys(p):
    for a, b in zip(CAM_KEYS, CAM_KEYS[1:]):
        if a[0] <= p <= b[0]:
            # holds (same target/dist) drift linearly, moves ease in/out
            hold = a[1] == b[1] and a[2] == b[2]
            t = seg(p, a[0], b[0]) if hold else ease_in_out(seg(p, a[0], b[0]))
            tgt = Vector(a[1]).lerp(Vector(b[1]), t)
            return (tgt, lerp(a[2], b[2], t), lerp(a[3], b[3], t), lerp(a[4], b[4], t), lerp(a[5], b[5], t))
    k = CAM_KEYS[-1]
    return Vector(k[1]), k[2], k[3], k[4], k[5]


def cam_state(p):
    tgt, dist, elev, azim, fstop = cam_keys(p)
    if 0.20 <= p <= 0.33:
        # while the layers fly apart the framing follows the stack height
        ex = explode_amount(p)
        tgt = Vector((0, 0, lerp(0.07, 0.135, ex)))
        dist = lerp(0.46, 0.98, ex)
        elev = lerp(8.0, 7.0, ex)
    return tgt, dist, elev, azim, fstop


def show(obj, visible):
    for o in [obj] + list(obj.children_recursive):
        if o.hide_render == visible:
            o.hide_render = not visible


def hop(p0, p1, t, h=0.3):
    te = ease_in_out(t)
    pos = Vector(p0).lerp(Vector(p1), te)
    pos.z += h * math.sin(math.pi * te)
    return pos, te


def explode_amount(p):
    return ease_in_out(seg(p, 0.15, 0.31)) - ease_in_out(seg(p, 0.40, 0.475))


def set_state(p):
    # --- environment: dark wood + paper -> cream sweep
    bg = smooth(seg(p, 0.17, 0.33))
    bgmix.outputs[0].default_value = bg
    paper_alpha.outputs[0].default_value = 1.0 - smooth(seg(p, 0.15, 0.225))
    show(paper, p < 0.23)
    c0, c1 = hexc('#050403'), hexc(CREAM)
    world_bg.inputs['Color'].default_value = tuple(lerp(c0[i], c1[i], bg) for i in range(4))
    world_bg.inputs['Strength'].default_value = lerp(1.0, 0.32, bg)
    la = 1.0 - smooth(seg(p, 0.2, 0.36))
    lb = smooth(seg(p, 0.18, 0.36))
    for ob, e in LA:
        ob.data.energy = e * la
        show(ob, la >= 0.002)
    for ob, e in LB:
        ob.data.energy = e * lb
        show(ob, lb >= 0.002)

    # --- burger layers
    ex = explode_amount(p)
    lift = 0.012 * ex
    burger.location = Vector((0, 0, 0.0012)).lerp(Vector((0, 0, 0)), seg(p, 0.2, 0.3))
    for i, (k, lr, z, h) in enumerate(layers):
        d = (i / (N_LAYERS - 1))
        e_i = ease_in_out(seg(p, 0.15 + 0.012 * (1 - d), 0.31 - 0.01 * d)) - ease_in_out(seg(p, 0.40 + 0.01 * d, 0.475))
        bob = 0.0025 * math.sin(p * 90 + i * 1.3) * ex
        lr.location = (0, 0, z + lift + i * GAP * e_i + bob)
        lr.rotation_euler = Euler((0.07 * math.sin(i * 1.7 + 0.5) * e_i, 0.06 * math.cos(i * 2.3) * e_i,
                                   0.35 * ((i - 3) / 3) * e_i), 'XYZ')
    if cheese_key:
        cheese_key.value = ex

    # --- combo pieces land around the burger
    def land(obj, pos, rz, t, from_off):
        te = ease_out(t)
        P = Vector(pos) + Vector(from_off) * (1 - te)
        obj.location = P
        obj.rotation_euler = Euler((from_off[1] * -1.2 * (1 - te), from_off[0] * 1.2 * (1 - te),
                                    rz + 0.6 * (1 - te)), 'XYZ')
        show(obj, t > 0.0)

    tf = seg(p, 0.47, 0.555)
    ts = seg(p, 0.495, 0.58)
    land(fries, COMBO['fries'][0], COMBO['fries'][1], tf, (-0.12, 0.05, 0.42))
    land(shake, COMBO['shake'][0], COMBO['shake'][1], ts, (0.12, 0.05, 0.42))
    for j, cup in enumerate(cups):
        tc = seg(p, 0.52 + 0.018 * j, 0.585 + 0.012 * j)
        land(cup, COMBO['cups'][j][0], COMBO['cups'][j][1], tc, (0.03 * (j - 1), -0.32, 0.1))

    # --- box arrives from behind with the lid open
    tb = seg(p, 0.62, 0.71)
    show(box, tb > 0.0)
    tbe = ease_out(tb)
    box.location = (0, lerp(1.6, YB, tbe), lerp(0.25, 0.0, ease_out(seg(tb, 0.0, 0.8))))
    box.rotation_euler = Euler((0, 0, 0.35 * (1 - tbe)), 'XYZ')
    open_ang = math.radians(-112)
    tl = seg(p, 0.835, 0.885)
    tl2 = seg(p, 0.885, 0.91)
    ang = lerp(open_ang, 0.0, ease_in(tl) if tl < 1 else 1.0)
    if tl >= 1.0:
        ang = math.radians(-4) * math.sin(math.pi * tl2) * (1 - tl2)
    hinge.rotation_euler = Euler((ang, 0, 0), 'XYZ')

    # --- products hop into the box (after landing in the combo)
    if p >= 0.70:
        def put(obj, start, slot, t, h=0.32, spin=0.0):
            pos, te = hop(start[0], slot[0], t, h)
            obj.location = pos
            obj.rotation_euler = Euler((0.25 * math.sin(math.pi * te), -0.2 * math.sin(math.pi * te),
                                        lerp(start[1], slot[1], te) + spin * math.sin(math.pi * te)), 'XYZ')
        put(fries, COMBO['fries'], SLOTS['fries'], seg(p, 0.70, 0.765), 0.3)
        put(shake, COMBO['shake'], SLOTS['shake'], seg(p, 0.715, 0.78), 0.3)
        put(burger, ((0, 0, 0), 0.0), SLOTS['burger'], seg(p, 0.735, 0.80), 0.34)
        for j, cup in enumerate(cups):
            put(cup, COMBO['cups'][j], SLOTS['cups'][j], seg(p, 0.755 + 0.014 * j, 0.81 + 0.01 * j), 0.36)
    else:
        burger.rotation_euler = Euler((0, 0, 0), 'XYZ')

    # --- camera
    tgt, dist, elev, azim, fstop = cam_state(p)
    place_camera(cam, tgt, dist, elev, azim)
    cam.data.dof.aperture_fstop = fstop


# ----------------------------------------------------------------------------
# label anchors for the exploded hold (normalised frame coords, y down)
# ----------------------------------------------------------------------------
def label_anchors(p):
    set_state(p)
    bpy.context.view_layer.update()
    sc = bpy.context.scene
    names = {'bun_bottom': 'PÃO BRIOCHE', 'lettuce': 'ALFACE', 'tomato': 'TOMATE', 'patty': 'BLEND 180G',
             'cheese': 'CHEDDAR', 'sauce': 'MOLHO DA CASA', 'bun_top': 'PÃO BRIOCHE'}
    out = []
    for i, (k, lr, z, h) in enumerate(layers):
        c = lr.matrix_world.translation + Vector((0, 0, h * 0.5))
        side = 1 if i % 2 == 0 else -1
        edge = c + Vector((0.064 * side, 0, 0))
        uc = world_to_camera_view(sc, cam, c)
        ue = world_to_camera_view(sc, cam, edge)
        out.append({'key': k, 'name': names.get(k, k), 'side': side,
                    'cx': round(uc.x, 4), 'cy': round(1 - uc.y, 4), 'ex': round(ue.x, 4), 'ey': round(1 - ue.y, 4)})
    return out


# ----------------------------------------------------------------------------
# render loop
# ----------------------------------------------------------------------------
N = args.frames
frames = [int(x) for x in args.only.split(',')] if args.only else list(range(args.offset, N, args.step))
lab = {}
for fi in range(N):
    p = fi / (N - 1)
    if 0.29 <= p <= 0.44:
        lab[fi] = label_anchors(p)
meta = {'frames': N, 'size': args.size, 'labels': lab}
if args.offset == 0:
    with open(os.path.join(args.out, 'meta.json'), 'w') as f:
        json.dump(meta, f, ensure_ascii=False)

sc = bpy.context.scene
for fi in frames:
    path = os.path.join(args.out, f'{fi:04d}.png')
    if os.path.exists(path) and not args.force:
        continue
    p = fi / (N - 1)
    set_state(p)
    sc.render.filepath = path
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f'FRAME {fi} p={p:.3f} {time.time() - t0:.1f}s', flush=True)
print('DONE', flush=True)
