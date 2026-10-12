"""Look-dev for the combo props: blender -b -P render-src/test_props.py -- out.png w h samples mode"""
import sys
import os
import math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy
from lib import reset
from burger import build_burger
from props import build_fries, build_shake, build_sauce_cup, build_box
from env import render_settings, world, build_table, build_paper, area_light, camera, place_camera

argv = sys.argv[sys.argv.index('--') + 1:]
out, W, H, S, mode = argv[0], int(argv[1]), int(argv[2]), int(argv[3]), argv[4]

reset()
render_settings(W, H, S)
bg = world('#efe3c8', 0.6)
table, bgmix = build_table()
bgmix.outputs[0].default_value = 1.0
root, layers = build_burger()
fries = build_fries()
shake = build_shake()
cups = [build_sauce_cup('CupK', '#b3140c'), build_sauce_cup('CupM', '#f08a12'), build_sauce_cup('CupY', '#efe2c0')]
box, hinge = build_box()

if mode == 'combo':
    root.location = (0, 0, 0)
    fries.location = (-0.15, 0.09, 0)
    fries.rotation_euler.z = 0.25
    shake.location = (0.15, 0.1, 0)
    for c, p in zip(cups, ((-0.095, -0.11, 0), (0.0, -0.135, 0), (0.095, -0.11, 0))):
        c.location = p
    box.location = (0, 0.6, 0)
    target = (0, 0, 0.06)
    elev, dist, lens = 18, 1.0, 50
else:  # box
    box.location = (0, 0, 0)
    hinge.rotation_euler.x = math.radians(-105 if mode == 'boxopen' else 0)
    root.location = (-0.115, -0.01, 0.004)
    fries.location = (0.02, 0.06, 0.004)
    shake.location = (0.135, 0.02, 0.004)
    for c, p in zip(cups, ((-0.0, -0.085, 0.004), (0.07, -0.095, 0.004), (0.15, -0.09, 0.004))):
        c.location = p
    target = (0, 0, 0.12)
    elev, dist, lens = 30 if mode == 'boxopen' else 22, 1.3, 50

area_light('Key', (-0.8, -0.5, 1.0), target, (1.0, 1.0), 30, spread=70)
area_light('Rim', (0.7, 0.9, 0.6), target, (0.8, 0.8), 25, spread=70)
area_light('Fill', (0.6, -1.0, 0.4), target, (1.0, 0.6), 8)
cam = camera(lens, 5.6)
place_camera(cam, target, dist, elev, 0)
bpy.context.scene.render.filepath = out
bpy.ops.render.render(write_still=True)
