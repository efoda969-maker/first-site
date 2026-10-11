"""Quick look-dev still: blender -b -P render-src/test_still.py -- out.png [w h samples elev dist explode bgmix]"""
import sys
import os
import math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy
from lib import reset
from burger import build_burger
from env import render_settings, world, build_table, build_paper, area_light, camera, place_camera

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
out = argv[0] if argv else '/tmp/still.png'
W = int(argv[1]) if len(argv) > 1 else 960
H = int(argv[2]) if len(argv) > 2 else 540
S = int(argv[3]) if len(argv) > 3 else 64
ELEV = float(argv[4]) if len(argv) > 4 else 11
DIST = float(argv[5]) if len(argv) > 5 else 0.62
EXPL = float(argv[6]) if len(argv) > 6 else 0.0
BG = float(argv[7]) if len(argv) > 7 else 0.0

reset()
render_settings(W, H, S)
bgn = world('#050403', 1.0)
table, bgmix = build_table()
bgmix.outputs[0].default_value = BG
paper, _ = build_paper()
root, layers = build_burger()
root.location.z = 0.0012
for i, (k, lr, z, h) in enumerate(layers):
    lr.location.z = z + EXPL * i * 0.034
target = (0, 0, 0.048 + EXPL * 0.1)
area_light('Key', (-0.6, -0.15, 0.55), target, (0.5, 0.7), 7, spread=55)
area_light('Rim', (0.45, 0.7, 0.3), target, (0.4, 0.7), 12, spread=60)
area_light('RimL', (-0.5, 0.6, 0.25), target, (0.3, 0.5), 6, spread=60)
area_light('Top', (0.0, 0.15, 0.9), target, (0.6, 0.6), 2.5, spread=50)
area_light('Fill', (0.35, -0.8, 0.12), target, (0.6, 0.3), 1.2)
cam = camera(85, 2.8)
place_camera(cam, target, DIST, ELEV, 0)
if not os.environ.get('NORENDER'):
    import time
    bpy.context.scene.render.filepath = out
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print('RENDER_TIME', time.time() - t0)
