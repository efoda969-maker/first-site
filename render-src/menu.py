"""Menu product shots: pinked white paper on the dark walnut table, and the
combo box on the stainless kitchen counter.

  blender -b -P render-src/menu.py -- --item enterrada --out DIR [--size 900 --samples 20]
items: enterrada lance-livre bandeja gancho fries shake sauces combo
"""
import sys
import os
import math
import argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy
from mathutils import Vector

from lib import reset
from smash import build_smash_burger
from props import build_fries, build_shake, build_sauce_cup, build_box
from env import render_settings, world, build_table, build_paper, build_kitchen, area_light, camera, place_camera

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
sc = bpy.context.scene
wbg = world('#050403', 1.0)
table, bgmix = build_table()

item = args.item
target = (0, 0, 0.055)
dist, elev, azim, lens, fstop = 0.5, 8.0, -10.0, 60, 3.2
sc.view_settings.exposure = -1.3
kitchen_scene = False
SAUCES = (('CupHouse', '#e46a24'), ('CupBBQ', '#4a1608'), ('CupCheddar', '#f29a12'))

if item in ('enterrada', 'lance-livre', 'bandeja', 'gancho', 'fries', 'shake', 'sauces'):
    paper, _ = build_paper(seed=sum(map(ord, item)) % 7 + 1.0)

if item == 'enterrada':
    r, _ = build_smash_burger('Enterrada')
    r.location.z = 0.0012
elif item == 'lance-livre':
    r, _ = build_smash_burger('Lance', ['heel', 'pattycheese', 'onions', 'sauce', 'crown'])
    r.location.z = 0.0012
    target = (0, 0, 0.045)
elif item == 'bandeja':
    r, _ = build_smash_burger('Bandeja', ['heel', 'pattycheese', 'pattycheese', 'bacon', 'sauce', 'crown'],
                              {4: {'color': '#5a1c0a'}})
    r.location.z = 0.0012
    target = (0, 0, 0.06)
elif item == 'gancho':
    r, _ = build_smash_burger('Gancho', ['heel', 'lettuce', 'tomato', 'crispy', 'sauce', 'crown'],
                              {4: {'color': '#efe0bd'}})
    r.location.z = 0.0012
elif item == 'fries':
    f = build_fries()
    f.location.z = 0.0012
    f.rotation_euler.z = 0.15
    target = (0, 0, 0.07)
    dist, elev = 0.56, 9.0
elif item == 'shake':
    s = build_shake()
    s.location.z = 0.0012
    target = (0, 0, 0.07)
    dist, elev = 0.55, 8.0
elif item == 'sauces':
    for i, (name, col) in enumerate(SAUCES):
        c = build_sauce_cup(name, col, 41 + i)
        c.location = ((i - 1) * 0.062, 0.012 * abs(i - 1), 0.0012)
        c.rotation_euler.z = i * 0.7
    target = (0, 0, 0.018)
    dist, elev = 0.42, 20.0
elif item == 'combo':
    kitchen_scene = True
    kmix = bpy.data.materials['TableMat'].node_tree.nodes['KitchenMix']
    kmix.outputs[0].default_value = 1.0
    bgmix.outputs[0].default_value = 1.0
    kitchen, glow = build_kitchen()
    glow.outputs[0].default_value = 6.0
    wbg.inputs['Color'].default_value = (0.004, 0.004, 0.0045, 1)
    wbg.inputs['Strength'].default_value = 0.6
    sc.view_settings.exposure = -1.0
    box, hinge = build_box()
    hinge.rotation_euler.x = math.radians(-108)
    b, _ = build_smash_burger('Combo')
    b.location = (-0.13, 0.0, 0.0045)
    fr = build_fries()
    fr.location = (0.05, 0.07, 0.0045)
    sh = build_shake()
    sh.location = (0.165, 0.068, 0.0045)
    sh.rotation_euler.z = -0.25
    for i, (name, col) in enumerate(SAUCES):
        c = build_sauce_cup(name, col, 41 + i)
        c.location = (0.04 + 0.07 * i, -0.088 - 0.007 * (i % 2), 0.0045)
        c.rotation_euler.z = i * 0.6
    target = (0, 0.0, 0.1)
    dist, elev, azim, lens, fstop = 1.45, 30.0, -14.0, 60, 4.0

T = Vector(target)
if not kitchen_scene:
    k = dist / 0.5
    area_light('Key', T + Vector((-0.5, -0.4, 0.4)) * k, target, (0.5 * k, 0.5 * k), 5 * k * k, spread=35)
    area_light('Rim', T + Vector((0.45, 0.7, 0.25)) * k, target, (0.4 * k, 0.7 * k), 8 * k * k, spread=40)
    area_light('RimL', T + Vector((-0.5, 0.6, 0.2)) * k, target, (0.3 * k, 0.5 * k), 4 * k * k, spread=40)
    area_light('Top', T + Vector((0.0, 0.15, 0.85)) * k, target, (0.4 * k, 0.4 * k), 1.2 * k * k, spread=24)
    area_light('Fill', T + Vector((0.35, -0.8, 0.07)) * k, target, (0.6 * k, 0.3 * k), 1.0 * k * k, spread=50)
else:
    area_light('K_Key', (-1.0, -0.75, 1.0), target, (1.0, 0.8), 26, spread=60)
    area_light('K_Rim', (0.9, 1.0, 0.7), target, (1.2, 0.6), 34, spread=60)
    area_light('K_RimL', (-0.9, 0.9, 0.5), target, (0.8, 0.5), 18, spread=60)
    area_light('K_Top', (0.0, 0.2, 1.5), target, (1.0, 0.6), 10, spread=60)
    area_light('K_Fill', (0.6, -1.4, 0.35), target, (1.0, 0.5), 5, spread=70)
cam = camera(lens, fstop)
place_camera(cam, target, dist, elev, azim)
sc.render.filepath = os.path.join(args.out, item + '.png')
bpy.ops.render.render(write_still=True)
print('MENU DONE', item)
