"""Studio environment: dark wood table that can fade into a cream sweep,
white paper, advertising-style lighting, camera and render settings."""
import bpy
import bmesh
import math
from mathutils import Vector, noise

from lib import hexc, NB, principled, mesh_object, add_subsurf, link


CREAM = '#efe3c8'


def render_settings(width, height, samples=96, threads=0):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    cy = sc.cycles
    cy.device = 'CPU'
    cy.samples = samples
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.02
    cy.use_denoising = True
    cy.denoiser = 'OPENIMAGEDENOISE'
    cy.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
    cy.max_bounces = 8
    cy.diffuse_bounces = 2
    cy.glossy_bounces = 3
    cy.transmission_bounces = 8
    cy.transparent_max_bounces = 8
    cy.caustics_reflective = False
    cy.caustics_refractive = False
    cy.sample_clamp_indirect = 6.0
    cy.blur_glossy = 1.0
    sc.render.resolution_x = width
    sc.render.resolution_y = height
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.use_persistent_data = True
    if threads:
        sc.render.threads_mode = 'FIXED'
        sc.render.threads = threads
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Punchy'
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGB'
    sc.render.image_settings.color_depth = '8'


def world(dark='#060504', strength=1.0):
    w = bpy.data.worlds.new('World')
    bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = hexc(dark)
    bg.inputs['Strength'].default_value = strength
    return bg


def build_table(name='Table'):
    """Seamless sweep: flat floor that curves into a back wall. Material mixes
    dark walnut planks -> cream paper through the 'BGMix' value node."""
    bm = bmesh.new()
    nx = 40
    width = 8.0
    pts = []
    # profile in (y, z): floor from y=-3 to y=1.6, then quarter circle r=0.9, then wall up to z=4
    for i in range(30):
        pts.append((-3.0 + i * (4.6 / 29), 0.0))
    R = 0.9
    for i in range(1, 16):
        a = (i / 15) * (math.pi / 2)
        pts.append((1.6 + R * math.sin(a), R * (1 - math.cos(a))))
    for i in range(1, 8):
        pts.append((1.6 + R, R + i * (3.1 / 7)))
    grid = []
    for (y, z) in pts:
        row = []
        for i in range(nx + 1):
            x = -width / 2 + width * i / nx
            row.append(bm.verts.new((x, y, z)))
        grid.append(row)
    for j in range(len(grid) - 1):
        for i in range(nx):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        if f.normal.z < -0.1 or f.normal.y > 0.1:
            f.normal_flip()

    mat, nb = principled('TableMat', rough=0.6, spec=0.3)
    tc = nb.texco('Object')
    sepn = nb.sep(tc)
    plank_w = 0.155
    # plank id along Y
    yq = nb.math('DIVIDE', sepn.outputs['Y'], plank_w)
    pid = nb.math('FLOOR', yq)
    frac = nb.math('FRACT', yq)
    # per-plank random offset
    wn = nb.node('ShaderNodeTexWhiteNoise')
    wn.noise_dimensions = '1D'
    nb.link(pid, wn.inputs['W'])
    # grain coordinates: stretch along X
    comb = nb.node('ShaderNodeCombineXYZ')
    nb.link(nb.math('ADD', sepn.outputs['X'], nb.math('MULTIPLY', wn.outputs['Value'], 37.0)), comb.inputs['X'])
    nb.link(nb.math('MULTIPLY', sepn.outputs['Y'], 9.0), comb.inputs['Y'])
    nb.link(nb.math('MULTIPLY', wn.outputs['Value'], 11.0), comb.inputs['Z'])
    wave = nb.node('ShaderNodeTexWave')
    wave.wave_type = 'BANDS'
    wave.bands_direction = 'Y'
    wave.inputs['Scale'].default_value = 3.0
    wave.inputs['Distortion'].default_value = 7.0
    wave.inputs['Detail'].default_value = 3.0
    wave.inputs['Detail Scale'].default_value = 1.5
    nb.link(comb.outputs[0], wave.inputs['Vector'])
    grainn = nb.noise(scale=3.0, detail=6.0, rough=0.6, vec=comb.outputs[0])
    g = nb.math('ADD', nb.math('MULTIPLY', wave.outputs['Fac'], 0.6), nb.math('MULTIPLY', grainn.outputs['Fac'], 0.5))
    tone = nb.math('MULTIPLY', wn.outputs['Value'], 0.25)
    wood = nb.ramp(nb.math('ADD', g, tone), [(0.2, hexc('#080504')), (0.55, hexc('#150e0a')),
                                              (0.8, hexc('#241812')), (1.0, hexc('#33241a'))])
    # dark seams between planks
    seam = nb.math('MAXIMUM', nb.maprange(frac, 0.012, 0.0, 0.0, 1.0), nb.maprange(frac, 0.988, 1.0, 0.0, 1.0))
    wood_c = nb.mix(seam, wood.outputs['Color'], hexc('#020101'))
    # cream sweep with a whisper of paper texture
    papern = nb.noise(scale=60.0, detail=3.0)
    cream = nb.mix(nb.maprange(papern.outputs['Fac'], 0.3, 0.7, 0.0, 0.06), hexc(CREAM), hexc('#d9c9a8'))
    bgmix = nb.node('ShaderNodeValue')
    bgmix.name = 'BGMix'
    bgmix.outputs[0].default_value = 0.0
    col = nb.mix(bgmix.outputs[0], wood_c, cream)
    nb.set('Base Color', col)
    rough_w = nb.maprange(grainn.outputs['Fac'], 0.3, 0.7, 0.5, 0.78)
    rough = nb.math('ADD', nb.math('MULTIPLY', rough_w, nb.math('SUBTRACT', 1.0, bgmix.outputs[0])),
                    nb.math('MULTIPLY', 0.9, bgmix.outputs[0]))
    nb.set('Roughness', rough)
    h = nb.math('ADD', nb.math('MULTIPLY', g, 0.4), nb.math('MULTIPLY', seam, -1.0))
    bstr = nb.math('MULTIPLY', nb.math('SUBTRACT', 1.0, bgmix.outputs[0]), 0.35)
    bump = nb.node('ShaderNodeBump')
    bump.inputs['Distance'].default_value = 0.002
    nb.link(bstr, bump.inputs['Strength'])
    nb.link(h, bump.inputs['Height'])
    nb.set('Normal', bump.outputs['Normal'])
    # in the cream phase the sweep glows softly so the backdrop reads as clean paper
    nb.set('Emission Color', hexc('#f2dcb2'))
    wall = nb.maprange(sepn.outputs['Z'], 0.0, 1.4, 0.2, 1.25)
    nb.set('Emission Strength', nb.math('MULTIPLY', bgmix.outputs[0], wall))
    ob = mesh_object(name, bm, [mat])
    return ob, bgmix


def build_paper(name='Paper', size=0.27, rot=0.32, flat_r=0.075):
    n = 72
    bm = bmesh.new()
    rows = []
    for j in range(n + 1):
        row = []
        for i in range(n + 1):
            x = (i / n - 0.5) * size
            y = (j / n - 0.5) * size
            p = Vector((x, y, 0))
            z = (0.0035 * noise.noise(p * 9 + Vector((3, 1, 0))) + 0.0012 * noise.noise(p * 26 + Vector((0, 7, 2)))
                 + 0.0005 * noise.noise(p * 70))
            # crisp crease lines
            z += 0.0022 * max(0.0, 1 - abs(x * 0.8 + y * 0.6 - 0.05) / 0.012)
            z += 0.0016 * max(0.0, 1 - abs(-x * 0.5 + y * 0.86 + 0.08) / 0.01)
            r = math.hypot(x, y)
            w = min(1.0, max(0.0, (r - flat_r) / 0.04))
            z = (z + 0.0045) * w + 0.0012
            # corners lift a little
            z += 0.012 * max(0.0, (max(abs(x), abs(y)) - size * 0.38) / (size * 0.12)) ** 2
            row.append(bm.verts.new((x, y, z)))
        rows.append(row)
    for j in range(n):
        for i in range(n):
            bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
    mat, nb = principled('PaperMat', color='#dedbd3', rough=0.62, sss=0.15, sss_radius=(1, 1, 1), sss_scale=0.002)
    fib = nb.noise(scale=400.0, detail=4.0)
    nb.set('Normal', nb.bump(fib.outputs['Fac'], strength=0.05, distance=0.0003))
    alpha = nb.node('ShaderNodeValue')
    alpha.name = 'PaperAlpha'
    alpha.outputs[0].default_value = 1.0
    nb.set('Alpha', alpha.outputs[0])
    ob = mesh_object(name, bm, [mat])
    m = ob.modifiers.new('Solidify', 'SOLIDIFY')
    m.thickness = 0.0004
    ob.rotation_euler = (0, 0, rot)
    return ob, alpha


def area_light(name, loc, target, size=(0.6, 0.6), power=50.0, color=(1, 1, 1), spread=180.0):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.shape = 'RECTANGLE'
    ld.size, ld.size_y = size
    ld.energy = power
    ld.color = color
    ld.spread = math.radians(spread)
    ob = bpy.data.objects.new(name, ld)
    link(ob)
    ob.location = loc
    aim(ob, target)
    return ob


def aim(ob, target):
    d = Vector(target) - Vector(ob.location)
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def camera(lens=70.0, fstop=3.5):
    cd = bpy.data.cameras.new('Cam')
    cd.lens = lens
    cd.sensor_width = 36.0
    cd.sensor_fit = 'HORIZONTAL'
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = fstop
    cam = bpy.data.objects.new('Cam', cd)
    link(cam)
    bpy.context.scene.camera = cam
    return cam


def place_camera(cam, target, dist, elev_deg, azim_deg, roll_deg=0.0):
    """Orbit placement: azimuth 0 = looking from -Y towards +Y."""
    t = Vector(target)
    e, a = math.radians(elev_deg), math.radians(azim_deg)
    off = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
    cam.location = t + off
    q = (t - cam.location).to_track_quat('-Z', 'Y')
    cam.rotation_euler = q.to_euler()
    if roll_deg:
        cam.rotation_euler.rotate_axis('Z', math.radians(roll_deg))
    cam.data.dof.focus_distance = dist
