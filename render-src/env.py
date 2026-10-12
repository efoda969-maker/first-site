"""Studio environment: dark wood table that can fade into a cream sweep,
white paper, advertising-style lighting, camera and render settings."""
import bpy
import bmesh
import math
from mathutils import Vector, noise

from lib import hexc, NB, principled, mesh_object, add_subsurf, link


CREAM = '#efe6d6'


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
    # PBR Neutral keeps food colours saturated (AgX drifts bright oranges to salmon)
    sc.view_settings.view_transform = 'Khronos PBR Neutral'
    sc.view_settings.look = 'None'
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

    mat, nb = principled('TableMat', rough=0.65, spec=0.25)
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
    wood = nb.ramp(nb.math('ADD', g, tone), [(0.2, hexc('#070403')), (0.55, hexc('#140c08')),
                                              (0.8, hexc('#24160e')), (1.0, hexc('#352214'))])
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
    # kitchen phase: brushed steel counter, charcoal wall
    kmix = nb.node('ShaderNodeValue')
    kmix.name = 'KitchenMix'
    kmix.outputs[0].default_value = 0.0
    brushed = nb.node('ShaderNodeMapping')
    brushed.inputs['Scale'].default_value = (1.5, 260.0, 1.5)
    nb.link(tc, brushed.inputs['Vector'])
    bn = nb.noise(scale=6.0, detail=4.0, vec=brushed.outputs['Vector'])
    floor_m = nb.maprange(sepn.outputs['Z'], 0.25, 0.05)
    steel_c = nb.mix(nb.maprange(bn.outputs['Fac'], 0.3, 0.7, 0.0, 1.0), hexc('#55585c'), hexc('#7a7e82'))
    kit_c = nb.mix(floor_m, hexc('#121213'), steel_c)
    col = nb.mix(kmix.outputs[0], col, kit_c)
    nb.set('Base Color', col)
    nb.set('Metallic', nb.math('MULTIPLY', kmix.outputs[0], floor_m))
    rough_w = nb.maprange(grainn.outputs['Fac'], 0.3, 0.7, 0.55, 0.85)
    rough = nb.math('ADD', nb.math('MULTIPLY', rough_w, nb.math('SUBTRACT', 1.0, bgmix.outputs[0])),
                    nb.math('MULTIPLY', 0.9, bgmix.outputs[0]))
    steel_r = nb.maprange(bn.outputs['Fac'], 0.3, 0.7, 0.36, 0.5)
    rough = nb.math('ADD', nb.math('MULTIPLY', rough, nb.math('SUBTRACT', 1.0, kmix.outputs[0])),
                    nb.math('MULTIPLY', steel_r, kmix.outputs[0]))
    nb.set('Roughness', rough)
    h = nb.math('ADD', nb.math('MULTIPLY', g, 0.4), nb.math('MULTIPLY', seam, -1.0))
    bstr = nb.math('ADD', nb.math('MULTIPLY', nb.math('SUBTRACT', 1.0, bgmix.outputs[0]), 0.35),
                   nb.math('MULTIPLY', kmix.outputs[0], 0.04))
    bump = nb.node('ShaderNodeBump')
    bump.inputs['Distance'].default_value = 0.002
    nb.link(bstr, bump.inputs['Strength'])
    nb.link(h, bump.inputs['Height'])
    nb.set('Normal', bump.outputs['Normal'])
    # in the cream phase the sweep glows softly so the backdrop reads as clean paper
    nb.set('Emission Color', hexc('#f3e9d8'))
    wall = nb.maprange(sepn.outputs['Z'], 0.0, 0.7, 0.3, 1.25)
    nb.set('Emission Strength', nb.math('MULTIPLY', nb.math('MULTIPLY', bgmix.outputs[0], wall),
                                        nb.math('SUBTRACT', 1.0, kmix.outputs[0])))
    ob = mesh_object(name, bm, [mat])
    ob['kmix'] = kmix.name
    return ob, bgmix


def build_paper(name='Paper', size=0.3, rot=0.28, flat_r=0.07, seed=3.0):
    """Butcher paper with pinked (zig-zag) edges and real crinkles."""
    n = 160                       # 4 cells per tooth
    h = size / 2
    depth = 0.0028
    bm = bmesh.new()
    rows = []
    rnd = __import__('random').Random(int(seed * 10))
    folds = []
    for _ in range(7):
        a = rnd.uniform(0, math.pi)
        folds.append((math.cos(a), math.sin(a), rnd.uniform(-0.12, 0.12), rnd.uniform(0.0008, 0.0026) * rnd.choice((-1, 1)),
                      rnd.uniform(0.006, 0.016)))

    def valley(k):
        return 1 - abs((k % 4) - 2) / 2.0

    for j in range(n + 1):
        row = []
        for i in range(n + 1):
            x = -h + size * i / n
            y = -h + size * j / n
            if i == 0:
                x += depth * valley(j)
            elif i == n:
                x -= depth * valley(j)
            if j == 0:
                y += depth * valley(i)
            elif j == n:
                y -= depth * valley(i)
            p = Vector((x, y, 0))
            z = (0.0024 * noise.noise(p * 8 + Vector((3, 1, seed))) + 0.0009 * noise.noise(p * 24 + Vector((0, 7, 2)))
                 + 0.0004 * noise.noise(p * 80))
            for (fx, fy, c, amp, wdt) in folds:
                d = abs(x * fx + y * fy - c)
                z += amp * max(0.0, 1 - d / wdt)
            r = math.hypot(x, y)
            w = min(1.0, max(0.0, (r - flat_r) / 0.05))
            z = (z + 0.003) * w + 0.0012
            z += 0.01 * max(0.0, (max(abs(x), abs(y)) - h * 0.72) / (h * 0.28)) ** 2.2
            row.append(bm.verts.new((x, y, z)))
        rows.append(row)
    for j in range(n):
        for i in range(n):
            bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
    mat, nb = principled('PaperMat', color='#d9d6cf', rough=0.55, sss=0.2, sss_radius=(1, 1, 1), sss_scale=0.002,
                         sheen=0.2)
    fib = nb.noise(scale=500.0, detail=4.0)
    nb.set('Normal', nb.bump(fib.outputs['Fac'], strength=0.06, distance=0.0003))
    alpha = nb.node('ShaderNodeValue')
    alpha.name = 'PaperAlpha'
    alpha.outputs[0].default_value = 1.0
    nb.set('Alpha', alpha.outputs[0])
    ob = mesh_object(name, bm, [mat])
    m = ob.modifiers.new('Solidify', 'SOLIDIFY')
    m.thickness = 0.0004
    ob.rotation_euler = (0, 0, rot)
    return ob, alpha


def build_kitchen(name='Kitchen'):
    """Out-of-focus commercial kitchen behind the steel counter: warm light
    strips and steel blocks. Returns (root, [emissive materials' strength sockets])."""
    from lib import empty, set_parent
    root = empty(name)
    lights = []
    em, nb = principled('KitchenGlow', color='#000000', rough=1.0)
    nb.set('Emission Color', hexc('#ffd7a0'))
    glow = nb.node('ShaderNodeValue')
    glow.outputs[0].default_value = 0.0
    nb.set('Emission Strength', glow.outputs[0])
    steel, snb = principled('KitchenSteel', color='#3c3f42', rough=0.5, metal=1.0)
    for i, (x, z, w) in enumerate(((-1.5, 0.78, 0.9), (-0.35, 0.86, 1.1), (0.9, 0.74, 0.8), (2.0, 0.82, 1.0))):
        bpy.ops.mesh.primitive_plane_add(size=1.0, location=(x, 2.35, z), rotation=(math.pi / 2, 0, 0))
        o = bpy.context.active_object
        o.scale = (w, 0.06, 1)
        o.data.materials.append(em)
        set_parent(o, root)
    for i, (x, sx, sz) in enumerate(((-1.25, 0.8, 0.85), (-0.2, 0.5, 0.95), (0.75, 0.9, 0.8), (1.8, 0.7, 0.9))):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, 2.05, 0.1 + sz / 2))
        o = bpy.context.active_object
        o.scale = (sx, 0.45, sz)
        o.data.materials.append(steel)
        set_parent(o, root)
    for i in range(10):
        x = -1.8 + i * 0.4
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.025, location=(x, 2.2, 0.3 + 0.18 * ((i * 7) % 3) / 2))
        o = bpy.context.active_object
        o.data.materials.append(em)
        set_parent(o, root)
    return root, glow


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
