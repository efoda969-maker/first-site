"""ALL STAR BURGERS - scroll sequence.

Renders the whole story as square frames; the site crops them to 16:9 on
desktop and 9:16 on phones, so every subject is framed inside the central
square-ish safe zone.

  blender -b -P render-src/sequence.py -- --out DIR --frames 180 --size 1280 --samples 8 [--only 0,40,90] [--step 1]

Stage map (p = 0..1, the same numbers drive the copy on the website):
  0.00-0.14  smash burger on pinked white paper, dark walnut table, studio light
  0.14-0.43  camera pushes in, the stack lifts apart, dark -> cream
  0.43-0.62  layers stack again, fries / shake / sauces float in around it
  0.62-0.70  cream -> stainless kitchen counter, the black box slides in open
  0.70-0.91  everything hops into its bay, the lid closes
  0.91-1.00  hero shot of the closed box
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

from lib import reset, hexc, lerp, clamp, seg, ease_in_out, ease_out, ease_in, smooth
from smash import build_smash_burger, LABELS
from props import build_fries, build_shake, build_sauce_cup, build_box, BOX_H
from env import (render_settings, world, build_table, build_paper, build_kitchen, area_light, camera,
                 place_camera, CREAM)

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True)
ap.add_argument('--frames', type=int, default=180)
ap.add_argument('--size', type=int, default=1280)
ap.add_argument('--samples', type=int, default=8)
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
sc = bpy.context.scene
world_bg = world('#050403', 1.0)
table, bgmix = build_table()
kmix = bpy.data.materials['TableMat'].node_tree.nodes['KitchenMix']
kitchen, kitchen_glow = build_kitchen()
paper, paper_alpha = build_paper()
burger, layers = build_smash_burger()
fries = build_fries()
shake = build_shake()
cups = [build_sauce_cup('CupHouse', '#e46a24', 41), build_sauce_cup('CupBBQ', '#4a1608', 42),
        build_sauce_cup('CupCheddar', '#f29a12', 43)]
box, hinge = build_box()
N_LAYERS = len(layers)

# lights: A = dark studio around the burger, B = bright cream studio, K = kitchen
T0 = (0, 0, 0.055)
LA = [
    (area_light('A_Key', (-0.5, -0.4, 0.45), T0, (0.5, 0.5), 1, spread=35), 5.0),
    (area_light('A_Rim', (0.45, 0.7, 0.3), T0, (0.4, 0.7), 1, spread=40), 8.0),
    (area_light('A_RimL', (-0.5, 0.6, 0.25), T0, (0.3, 0.5), 1, spread=40), 4.0),
    (area_light('A_Top', (0.0, 0.15, 0.9), T0, (0.4, 0.4), 1, spread=24), 1.2),
    (area_light('A_Fill', (0.35, -0.8, 0.12), T0, (0.6, 0.3), 1, spread=50), 1.0),
]
TB = (0, 0.05, 0.08)
LB = [
    (area_light('B_Key', (-1.0, -0.6, 1.1), TB, (1.2, 1.2), 1, spread=75), 30.0),
    (area_light('B_Rim', (0.9, 1.1, 0.8), TB, (1.0, 1.0), 1, spread=70), 24.0),
    (area_light('B_Fill', (0.9, -1.3, 0.45), TB, (1.2, 0.6), 1), 9.0),
    (area_light('B_Top', (0.0, 0.2, 1.6), TB, (1.4, 1.4), 1, spread=80), 12.0),
]
YB = 0.36                         # box position (behind the combo)
TK = (0, YB, 0.08)
LK = [
    (area_light('K_Key', (-1.0, YB - 0.75, 1.0), TK, (1.0, 0.8), 1, spread=60), 26.0),
    (area_light('K_Rim', (0.9, YB + 1.0, 0.7), TK, (1.2, 0.6), 1, spread=60), 34.0),
    (area_light('K_RimL', (-0.9, YB + 0.9, 0.5), TK, (0.8, 0.5), 1, spread=60), 18.0),
    (area_light('K_Top', (0.0, YB + 0.2, 1.5), TK, (1.0, 0.6), 1, spread=60), 10.0),
    (area_light('K_Fill', (0.6, YB - 1.4, 0.35), TK, (1.0, 0.5), 1, spread=70), 5.0),
]
cam = camera(60, 2.8)

# ----------------------------------------------------------------------------
# choreography
# ----------------------------------------------------------------------------
# floating combo around the burger: (location, rotation)
COMBO = {
    'fries': ((-0.128, 0.05, 0.08), (0.25, -0.45, 0.5)),
    'shake': ((0.125, 0.07, 0.0), (0.0, 0.0, -0.25)),
    'cups': [((-0.02, 0.1, 0.172), (0.35, 0.2, 0.0)), ((-0.088, -0.105, 0.025), (0.0, 0.25, 0.6)),
             ((0.078, -0.115, 0.06), (-0.2, 0.0, 1.1))],
}
FLOOR = 0.0045
SLOTS = {
    'burger': ((-0.13, YB + 0.0, FLOOR), (0, 0, 0.0)),
    'fries': ((0.05, YB + 0.07, FLOOR), (0, 0, 0.0)),
    'shake': ((0.165, YB + 0.068, FLOOR), (0, 0, -0.25)),
    'cups': [((0.04, YB - 0.088, FLOOR), (0, 0, 0.0)), ((0.11, YB - 0.095, FLOOR), (0, 0, 0.6)),
             ((0.18, YB - 0.088, FLOOR), (0, 0, 1.1))],
}
GAP = 0.03

# camera keys: (p, target, dist, elev, azim, fstop)
CAM_KEYS = [
    (0.00, (0, 0, 0.055), 0.64, 9.0, -9.0, 2.8),
    (0.13, (0, 0, 0.055), 0.56, 8.0, -2.0, 2.8),
    (0.20, (0, 0, 0.07), 0.42, 6.0, 3.0, 3.2),        # push in
    (0.33, (0.045, 0, 0.15), 1.0, 6.0, -3.0, 4.5),     # exploded (explode-driven, see cam_state)
    (0.41, (0.045, 0, 0.15), 1.0, 6.0, 3.0, 4.5),      # drift while the labels show
    (0.47, (0, 0, 0.07), 0.8, 12.0, -4.0, 4.5),
    (0.57, (0, 0, 0.075), 1.18, 14.0, -3.0, 5.6),      # floating combo
    (0.63, (0, 0, 0.075), 1.18, 14.0, 3.0, 5.6),
    (0.71, (0, 0.2, 0.08), 1.9, 22.0, 0.0, 4.0),       # box arrives on the counter
    (0.82, (0, YB, 0.09), 1.7, 30.0, 0.0, 4.0),        # packing, looking in
    (0.89, (0, YB, 0.09), 1.7, 28.0, 0.0, 4.0),
    (0.97, (0, YB, 0.075), 1.78, 14.0, 12.0, 3.5),     # hero
    (1.00, (0, YB, 0.075), 1.76, 14.0, 14.0, 3.5),
]


def show(obj, visible):
    for o in [obj] + list(obj.children_recursive):
        if o.hide_render == visible:
            o.hide_render = not visible


def explode_amount(p):
    return ease_in_out(seg(p, 0.15, 0.31)) - ease_in_out(seg(p, 0.41, 0.475))


def cam_keys(p):
    for a, b in zip(CAM_KEYS, CAM_KEYS[1:]):
        if a[0] <= p <= b[0]:
            hold = a[1] == b[1] and a[2] == b[2]
            t = seg(p, a[0], b[0]) if hold else ease_in_out(seg(p, a[0], b[0]))
            tgt = Vector(a[1]).lerp(Vector(b[1]), t)
            return (tgt, lerp(a[2], b[2], t), lerp(a[3], b[3], t), lerp(a[4], b[4], t), lerp(a[5], b[5], t))
    k = CAM_KEYS[-1]
    return Vector(k[1]), k[2], k[3], k[4], k[5]


def cam_state(p):
    tgt, dist, elev, azim, fstop = cam_keys(p)
    if 0.20 <= p <= 0.33:
        ex = explode_amount(p)
        tgt = Vector((lerp(0.0, 0.045, ex), 0, lerp(0.07, 0.15, ex)))
        dist = lerp(0.42, 1.0, ex)
    return tgt, dist, elev, azim, fstop


def hop(p0, p1, t, h=0.3):
    te = ease_in_out(t)
    pos = Vector(p0).lerp(Vector(p1), te)
    pos.z += h * math.sin(math.pi * te)
    return pos, te


def set_state(p):
    # --- environment: walnut + paper -> cream sweep -> steel kitchen
    bg = smooth(seg(p, 0.17, 0.33))
    km = smooth(seg(p, 0.62, 0.7))
    bgmix.outputs[0].default_value = bg
    kmix.outputs[0].default_value = km
    kitchen_glow.outputs[0].default_value = 6.0 * km
    show(kitchen, km > 0.001)
    paper_alpha.outputs[0].default_value = 1.0 - smooth(seg(p, 0.15, 0.225))
    show(paper, p < 0.23)
    c0, c1, c2 = hexc('#050403'), hexc('#efe6d6'), hexc('#0b0b0c')
    col = [lerp(lerp(c0[i], c1[i], bg), c2[i], km) for i in range(4)]
    world_bg.inputs['Color'].default_value = col
    world_bg.inputs['Strength'].default_value = lerp(lerp(1.0, 0.32, bg), 0.6, km)
    sc.view_settings.exposure = lerp(lerp(-1.3, -0.75, bg), -1.0, km)
    la = 1.0 - smooth(seg(p, 0.2, 0.36))
    lb = smooth(seg(p, 0.18, 0.36)) * (1 - km)
    for group, w in ((LA, la), (LB, lb), (LK, km)):
        for ob, e in group:
            ob.data.energy = e * w
            show(ob, w >= 0.002)

    # --- burger layers
    ex = explode_amount(p)
    lift = 0.015 * ex
    burger.location = Vector((0, 0, 0.0012)).lerp(Vector((0, 0, 0)), seg(p, 0.2, 0.3))
    for i, (k, lr, z, h) in enumerate(layers):
        d = i / (N_LAYERS - 1)
        e_i = ease_in_out(seg(p, 0.15 + 0.012 * (1 - d), 0.31 - 0.01 * d)) - ease_in_out(seg(p, 0.41 + 0.01 * d, 0.475))
        bob = 0.0025 * math.sin(p * 90 + i * 1.3) * ex
        lr.location = (0, 0, z + lift + i * GAP * e_i + bob)
        lr.rotation_euler = Euler((0.06 * math.sin(i * 1.7 + 0.5) * e_i, 0.05 * math.cos(i * 2.3) * e_i,
                                   0.3 * ((i - 2.5) / 2.5) * e_i), 'XYZ')

    # --- combo pieces float in around the burger
    def float_in(obj, spec, t, from_off, k):
        te = ease_out(t)
        loc, rot = spec
        P = Vector(loc) + Vector(from_off) * (1 - te)
        P.z += 0.006 * math.sin(p * 60 + k) * te      # gentle hover
        obj.location = P
        obj.rotation_euler = Euler((rot[0] + 0.5 * (1 - te), rot[1] - 0.4 * (1 - te), rot[2] + 0.8 * (1 - te)), 'XYZ')
        show(obj, t > 0.0)

    float_in(fries, COMBO['fries'], seg(p, 0.47, 0.555), (-0.25, 0.05, 0.25), 1)
    float_in(shake, COMBO['shake'], seg(p, 0.495, 0.58), (0.25, 0.05, 0.3), 2)
    for j, cup in enumerate(cups):
        float_in(cup, COMBO['cups'][j], seg(p, 0.515 + 0.018 * j, 0.585 + 0.012 * j),
                 ((j - 1) * 0.12, -0.25, 0.2), 3 + j)

    # --- box slides in on the counter, lid open
    tb = seg(p, 0.62, 0.71)
    show(box, tb > 0.0)
    tbe = ease_out(tb)
    box.location = (0, lerp(1.7, YB, tbe), 0)
    box.rotation_euler = Euler((0, 0, 0.3 * (1 - tbe)), 'XYZ')
    open_ang = math.radians(-108)
    tl = seg(p, 0.835, 0.885)
    tl2 = seg(p, 0.885, 0.91)
    ang = lerp(open_ang, 0.0, ease_in(tl))
    if tl >= 1.0:
        ang = math.radians(-4) * math.sin(math.pi * tl2) * (1 - tl2)
    hinge.rotation_euler = Euler((ang, 0, 0), 'XYZ')

    # --- products hop into their bays
    if p >= 0.70:
        def put(obj, start, slot, t, h=0.3):
            pos, te = hop(start[0], slot[0], t, h)
            obj.location = pos
            r0, r1 = start[1], slot[1]
            obj.rotation_euler = Euler(tuple(lerp(r0[i], r1[i], te) + (0.2 if i == 0 else 0) * math.sin(math.pi * te)
                                             for i in range(3)), 'XYZ')
        put(fries, COMBO['fries'], SLOTS['fries'], seg(p, 0.70, 0.765), 0.26)
        put(shake, COMBO['shake'], SLOTS['shake'], seg(p, 0.715, 0.78), 0.3)
        put(burger, ((0, 0, 0), (0, 0, 0)), SLOTS['burger'], seg(p, 0.735, 0.80), 0.32)
        for j, cup in enumerate(cups):
            put(cup, COMBO['cups'][j], SLOTS['cups'][j], seg(p, 0.755 + 0.014 * j, 0.81 + 0.01 * j), 0.3)
    else:
        burger.rotation_euler = Euler((0, 0, 0), 'XYZ')

    # --- camera
    tgt, dist, elev, azim, fstop = cam_state(p)
    place_camera(cam, tgt, dist, elev, azim)
    cam.data.dof.aperture_fstop = fstop


# ----------------------------------------------------------------------------
# label anchors for the exploded hold (normalised frame coords, y down)
# ----------------------------------------------------------------------------
LABEL_LAYERS = {0: 'heel', 2: 'pattycheese', 3: 'onions', 4: 'sauce', 5: 'crown'}


def label_anchors(p):
    set_state(p)
    bpy.context.view_layer.update()
    out = []
    for i, (k, lr, z, h) in enumerate(layers):
        if i not in LABEL_LAYERS:
            continue
        c = lr.matrix_world.translation + Vector((0, 0, h * 0.5))
        edge = c + Vector((0.066, 0, 0))
        uc = world_to_camera_view(sc, cam, c)
        ue = world_to_camera_view(sc, cam, edge)
        out.append({'key': k, 'side': 1, 'cx': round(uc.x, 4), 'cy': round(1 - uc.y, 4),
                    'ex': round(ue.x, 4), 'ey': round(1 - ue.y, 4)})
    return out


# ----------------------------------------------------------------------------
# render loop
# ----------------------------------------------------------------------------
N = args.frames
frames = [int(x) for x in args.only.split(',')] if args.only else list(range(args.offset, N, args.step))
lab = {}
for fi in range(N):
    p = fi / (N - 1)
    if 0.29 <= p <= 0.45:
        lab[fi] = label_anchors(p)
meta = {'frames': N, 'size': args.size, 'labels': lab}
if args.offset == 0:
    with open(os.path.join(args.out, 'meta.json'), 'w') as f:
        json.dump(meta, f, ensure_ascii=False)

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
