"""Menu product shots on the dark walnut table.

  blender -b -P render-src/menu.py -- --item classic --out DIR [--size 900 --samples 20]
items: classic double bacon crispy fries shake sauces combo
"""
import sys
import os
import math
import argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy
from mathutils import Vector

from lib import reset
from burger import build_burger
from props import build_fries, build_shake, build_sauce_cup, build_box, BOX_H
from env import render_settings, world, build_table, area_light, camera, place_camera

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--item', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--size', type=int, default=900)
ap.add_argument('--samples', type=int, default=20)
ap.add_argument('--threads', type=int, default=0)
args = ap.parse_args(argv)
os.makedirs(args.out, exist_ok=True)

reset()
render_settings(args.size, args.size, args.samples, threads=args.threads)
world('#050403', 1.0)
table, bgmix = build_table()

item = args.item
target = (0, 0, 0.05)
dist, elev, azim, lens, fstop = 0.62, 12.0, -8.0, 70, 3.2

if item == 'classic':
    build_burger('Classic')
elif item == 'double':
    build_burger('Double', ['bun_bottom', 'sauce', 'patty', 'cheese', 'patty', 'cheese', 'pickles', 'bun_top'],
                 {1: {'radius': 0.045, 'color': '#e0662a', 'seed': 18.0}, 2: {'seed': 13.0},
                  3: {'seed': 15.0}, 4: {'seed': 23.0}, 5: {'seed': 25.0, 'rot': 0.3}})
    target = (0, 0, 0.065)
    dist = 0.7
elif item == 'bacon':
    build_burger('Bacon', ['bun_bottom', 'lettuce', 'patty', 'cheese', 'bacon', 'onion', 'sauce', 'bun_top'],
                 {6: {'color': '#6e2410', 'seed': 31.0}, 2: {'seed': 33.0}})
    target = (0, 0, 0.062)
    dist = 0.7
elif item == 'crispy':
    build_burger('Crispy', ['bun_bottom', 'lettuce', 'tomato', 'crispy', 'sauce', 'bun_top'],
                 {4: {'color': '#efe0bd', 'seed': 41.0}})
    target = (0, 0, 0.058)
elif item == 'fries':
    f = build_fries()
    f.rotation_euler.z = 0.15
    target = (0, 0, 0.075)
    dist, elev = 0.62, 10.0
elif item == 'shake':
    build_shake()
    target = (0, 0, 0.075)
    dist, elev = 0.6, 9.0
elif item == 'sauces':
    for i, (name, col) in enumerate((('CupKetchup', '#b3140c'), ('CupCheddar', '#f08a12'), ('CupMaionese', '#efe2c0'))):
        c = build_sauce_cup(name, col, 41 + i)
        c.location = ((i - 1) * 0.062, 0.012 * abs(i - 1), 0)
        c.rotation_euler.z = i * 0.7
    target = (0, 0, 0.018)
    dist, elev, lens = 0.5, 22.0, 70
elif item == 'combo':
    box, hinge = build_box()
    hinge.rotation_euler.x = math.radians(-112)
    b, _ = build_burger('Combo')
    b.location = (-0.115, 0.0, 0.0045)
    fr = build_fries()
    fr.location = (0.03, 0.058, 0.0045)
    sh = build_shake()
    sh.location = (0.145, 0.055, 0.0045)
    sh.rotation_euler.z = -0.2
    for i, (name, col) in enumerate((('CupKetchup', '#b3140c'), ('CupCheddar', '#f08a12'), ('CupMaionese', '#efe2c0'))):
        c = build_sauce_cup(name, col, 41 + i)
        c.location = (-0.005 + 0.075 * i, -0.08, 0.0045)
        c.rotation_euler.z = i * 0.6
    target = (0, 0.0, 0.12)
    dist, elev, azim, lens, fstop = 1.55, 34.0, -14.0, 60, 6.0

T = Vector(target)
scale = dist / 0.62
area_light('Key', T + Vector((-0.6, -0.15, 0.5)) * scale, target, (0.5 * scale, 0.7 * scale), 7.5 * scale ** 2, spread=45)
area_light('Rim', T + Vector((0.45, 0.7, 0.25)) * scale, target, (0.4 * scale, 0.7 * scale), 13 * scale ** 2, spread=50)
area_light('RimL', T + Vector((-0.5, 0.6, 0.2)) * scale, target, (0.3 * scale, 0.5 * scale), 6.5 * scale ** 2, spread=50)
area_light('Top', T + Vector((0.0, 0.15, 0.85)) * scale, target, (0.4 * scale, 0.4 * scale), 1.8 * scale ** 2, spread=30)
area_light('Fill', T + Vector((0.35, -0.8, 0.08)) * scale, target, (0.6 * scale, 0.3 * scale), 1.6 * scale ** 2, spread=60)
cam = camera(lens, fstop)
place_camera(cam, target, dist, elev, azim)
bpy.context.scene.render.filepath = os.path.join(args.out, item + '.png')
bpy.ops.render.render(write_still=True)
print('MENU DONE', item)
