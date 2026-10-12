"""Look-dev for the smash burger.  blender -b -P render-src/test_smash.py -- out.png size samples mode"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy
from mathutils import Vector
from lib import reset
from smash import build_smash_burger
from env import render_settings, world, build_table, build_paper, area_light, camera, place_camera

argv = sys.argv[sys.argv.index('--') + 1:]
out, SZ, S, mode = argv[0], int(argv[1]), int(argv[2]), argv[3]

reset()
render_settings(SZ, SZ, S)
w = world('#050403', 1.0)
table, bgmix = build_table()
root, layers = build_smash_burger()
if mode == 'hero':
    paper, _ = build_paper()
    root.location.z = 0.0012
    target = (0, 0, 0.055)
    dist, elev, azim, lens, fs = 0.46, 6.0, -10.0, 60, 2.8
    T0 = Vector(target)
    area_light('Key', (-0.5, -0.4, 0.45), target, (0.5, 0.5), 5, spread=35)
    area_light('Rim', (0.45, 0.7, 0.3), target, (0.4, 0.7), 8, spread=40)
    area_light('RimL', (-0.5, 0.6, 0.25), target, (0.3, 0.5), 4, spread=40)
    area_light('Top', (0.0, 0.15, 0.9), target, (0.4, 0.4), 1.2, spread=24)
    area_light('Fill', (0.35, -0.8, 0.12), target, (0.6, 0.3), 1.0, spread=50)
else:
    bgmix.outputs[0].default_value = 1.0
    w.inputs['Color'].default_value = (0.86, 0.78, 0.62, 1)
    w.inputs['Strength'].default_value = 0.32
    for i, (k, lr, z, h) in enumerate(layers):
        lr.location.z = z + i * 0.03 + 0.02
    target = (0.0, 0, 0.12)
    dist, elev, azim, lens, fs = 0.95, 7.0, 0.0, 60, 4.5
    area_light('B_Key', (-1.0, -0.55, 1.2), target, (1.2, 1.2), 32, spread=75)
    area_light('B_Rim', (0.9, 1.2, 0.8), target, (1.0, 1.0), 26, spread=70)
    area_light('B_Fill', (0.9, -1.3, 0.45), target, (1.2, 0.6), 9)
    area_light('B_Top', (0.0, 0.2, 1.7), target, (1.4, 1.4), 14, spread=80)
bpy.context.scene.view_settings.exposure = float(os.environ.get('EXPO', '0'))
cam = camera(lens, fs)
place_camera(cam, target, dist, elev, azim)
bpy.context.scene.render.filepath = out
bpy.ops.render.render(write_still=True)
