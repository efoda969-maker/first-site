"""Procedural cheeseburger: every ingredient is its own object so the
sequence can pull the layers apart and stack them back together."""
import bpy
import bmesh
import math
import random
from mathutils import Vector, Matrix, noise

from lib import (hexc, NB, principled, empty, set_parent, mesh_object, add_subsurf,
                 add_solidify, lathe_bm, jitter_radial, assign_mat_by, bvh_of, link)

_MATS = {}


# ----------------------------------------------------------------------------
# materials
# ----------------------------------------------------------------------------
def mat_bun_crust(height=0.045, top_dark=True):
    key = ('crust', height, top_dark)
    if key in _MATS:
        return _MATS[key]
    mat, nb = principled('BunCrust', rough=0.45, sss=0.12, sss_radius=(1.0, 0.5, 0.2),
                         sss_scale=0.003, coat=0.3, coat_rough=0.22)
    z = nb.sep(nb.texco('Object')).outputs['Z']
    zf = nb.maprange(z, 0.0, height)
    nz = nb.noise(scale=18.0, detail=3.0, rough=0.55)
    # slight noise warp on the gradient so the colour band is not a perfect ring
    zf2 = nb.math('ADD', zf, nb.math('MULTIPLY', nb.math('SUBTRACT', nz.outputs['Fac'], 0.5), 0.6))
    if top_dark:
        stops = [(0.0, hexc('#e2ad62')), (0.1, hexc('#cf8a38')), (0.3, hexc('#a8561a')),
                 (0.6, hexc('#83380c')), (1.0, hexc('#6a2a07'))]
    else:  # heel: pale bottom, golden band, pale near the cut
        stops = [(0.0, hexc('#8a4a16')), (0.25, hexc('#a65e1e')), (0.6, hexc('#c27a2e')),
                 (0.88, hexc('#d99a4c')), (1.0, hexc('#e8b673'))]
    col = nb.ramp(zf2, stops)
    spots = nb.noise(scale=90.0, detail=2.0, rough=0.6)
    spots_m = nb.maprange(spots.outputs['Fac'], 0.55, 0.75, 0.0, 0.25)
    col2 = nb.mix(spots_m, col.outputs['Color'], hexc('#5a2a0b'), blend='MULTIPLY')
    nb.set('Base Color', col2)
    rn = nb.noise(scale=55.0, detail=2.0)
    rough = nb.maprange(rn.outputs['Fac'], 0.35, 0.65, 0.3, 0.62)
    nb.set('Roughness', rough)
    fine = nb.noise(scale=380.0, detail=1.0, rough=0.5)
    nb.set('Normal', nb.bump(fine.outputs['Fac'], strength=0.1, distance=0.0004))
    _MATS[key] = mat
    return mat


def mat_bun_crumb():
    if 'crumb' in _MATS:
        return _MATS['crumb']
    # toasted cut face: golden centre, darker toasted ring
    mat, nb = principled('BunCrumb', rough=0.85, sss=0.3, sss_radius=(1.0, 0.7, 0.4), sss_scale=0.003)
    tc = nb.texco('Object')
    sepn = nb.sep(tc)
    vm = nb.node('ShaderNodeVectorMath', operation='LENGTH')
    comb = nb.node('ShaderNodeCombineXYZ')
    nb.link(sepn.outputs['X'], comb.inputs['X'])
    nb.link(sepn.outputs['Y'], comb.inputs['Y'])
    nb.link(comb.outputs[0], vm.inputs[0])
    r = nb.maprange(vm.outputs['Value'], 0.0, 0.055)
    nz = nb.noise(scale=60.0, detail=5.0, rough=0.6)
    rr = nb.math('ADD', r, nb.math('MULTIPLY', nb.math('SUBTRACT', nz.outputs['Fac'], 0.5), 0.5))
    col = nb.ramp(rr, [(0.0, hexc('#e9c27e')), (0.55, hexc('#d9a457')), (0.85, hexc('#b8742f')),
                       (1.0, hexc('#8f4f18'))])
    nb.set('Base Color', col.outputs['Color'])
    pores = nb.voronoi(scale=520.0, feature='F1', rnd=1.0)
    p2 = nb.noise(scale=300.0, detail=4.0)
    h = nb.math('ADD', pores.outputs['Distance'], nb.math('MULTIPLY', p2.outputs['Fac'], 0.5))
    nb.set('Normal', nb.bump(h, strength=0.45, distance=0.0006))
    _MATS['crumb'] = mat
    return mat


def mat_sesame():
    if 'sesame' in _MATS:
        return _MATS['sesame']
    mat, nb = principled('Sesame', rough=0.4, sss=0.4, sss_radius=(1, 0.85, 0.6), sss_scale=0.001)
    nz = nb.noise(scale=900.0, detail=2.0)
    col = nb.ramp(nz.outputs['Fac'], [(0.3, hexc('#efdcae')), (0.7, hexc('#d2a868'))])
    nb.set('Base Color', col.outputs['Color'])
    _MATS['sesame'] = mat
    return mat


def mat_patty():
    if 'patty' in _MATS:
        return _MATS['patty']
    mat, nb = principled('Patty', rough=0.5, coat=0.12, coat_rough=0.3)
    n1 = nb.noise(scale=140.0, detail=4.0, rough=0.65, distortion=0.4)
    v1 = nb.voronoi(scale=180.0, feature='F1')
    v2 = nb.voronoi(scale=60.0, feature='DISTANCE_TO_EDGE')
    mixv = nb.math('ADD', nb.math('MULTIPLY', n1.outputs['Fac'], 0.7), nb.math('MULTIPLY', v1.outputs['Distance'], 0.5))
    col = nb.ramp(mixv, [(0.25, hexc('#1a0a03')), (0.45, hexc('#36180a')), (0.62, hexc('#552710')),
                         (0.8, hexc('#7a3c17')), (1.0, hexc('#9a5422'))])
    big = nb.noise(scale=25.0, detail=3.0)
    char = nb.maprange(big.outputs['Fac'], 0.5, 0.72, 0.0, 0.45)
    col2 = nb.mix(char, col.outputs['Color'], hexc('#140904'), blend='MIX')
    nb.set('Base Color', col2)
    rough = nb.maprange(n1.outputs['Fac'], 0.35, 0.7, 0.3, 0.7)
    nb.set('Roughness', rough)
    edge = nb.maprange(v2.outputs['Distance'], 0.0, 0.08, 0.0, 1.0)
    h = nb.math('ADD', nb.math('MULTIPLY', mixv, 1.0), nb.math('MULTIPLY', edge, 0.5))
    nb.set('Normal', nb.bump(h, strength=0.75, distance=0.0012))
    _MATS['patty'] = mat
    return mat


def mat_cheese():
    if 'cheese' in _MATS:
        return _MATS['cheese']
    mat, nb = principled('Cheese', rough=0.25, sss=0.5, sss_radius=(1.0, 0.5, 0.12), sss_scale=0.005,
                         coat=0.6, coat_rough=0.12)
    nz = nb.noise(scale=30.0, detail=2.0)
    col = nb.ramp(nz.outputs['Fac'], [(0.3, hexc('#f07d00')), (0.7, hexc('#f69408'))])
    nb.set('Base Color', col.outputs['Color'])
    fine = nb.noise(scale=200.0, detail=2.0)
    nb.set('Normal', nb.bump(fine.outputs['Fac'], strength=0.05, distance=0.0003))
    _MATS['cheese'] = mat
    return mat


def mat_lettuce():
    if 'lettuce' in _MATS:
        return _MATS['lettuce']
    mat, nb = principled('Lettuce', rough=0.35, sss=0.6, sss_radius=(0.5, 1.0, 0.3), sss_scale=0.002,
                         coat=0.2, coat_rough=0.25)
    tc = nb.texco('Object')
    sepn = nb.sep(tc)
    comb = nb.node('ShaderNodeCombineXYZ')
    nb.link(sepn.outputs['X'], comb.inputs['X'])
    nb.link(sepn.outputs['Y'], comb.inputs['Y'])
    ln = nb.node('ShaderNodeVectorMath', operation='LENGTH')
    nb.link(comb.outputs[0], ln.inputs[0])
    r = nb.maprange(ln.outputs['Value'], 0.02, 0.07)
    nz = nb.noise(scale=45.0, detail=4.0)
    rr = nb.math('ADD', r, nb.math('MULTIPLY', nb.math('SUBTRACT', nz.outputs['Fac'], 0.5), 0.4))
    col = nb.ramp(rr, [(0.0, hexc('#e3edb0')), (0.45, hexc('#b5d670')), (0.8, hexc('#86ba45')), (1.0, hexc('#5c9a2c'))])
    nb.set('Base Color', col.outputs['Color'])
    veins = nb.voronoi(scale=35.0, feature='DISTANCE_TO_EDGE')
    vm = nb.maprange(veins.outputs['Distance'], 0.0, 0.05, 1.0, 0.0)
    nb.set('Normal', nb.bump(vm, strength=0.2, distance=0.0005))
    _MATS['lettuce'] = mat
    return mat


def mat_tomato():
    if 'tomato' in _MATS:
        return _MATS['tomato']
    mat, nb = principled('Tomato', rough=0.2, sss=0.5, sss_radius=(1.0, 0.25, 0.15), sss_scale=0.004,
                         coat=0.5, coat_rough=0.1)
    tc = nb.texco('Object')
    sepn = nb.sep(tc)
    comb = nb.node('ShaderNodeCombineXYZ')
    nb.link(sepn.outputs['X'], comb.inputs['X'])
    nb.link(sepn.outputs['Y'], comb.inputs['Y'])
    ln = nb.node('ShaderNodeVectorMath', operation='LENGTH')
    nb.link(comb.outputs[0], ln.inputs[0])
    r = nb.maprange(ln.outputs['Value'], 0.0, 0.035)
    ang = nb.math('ARCTAN2', sepn.outputs['Y'], sepn.outputs['X'])
    nz = nb.noise(scale=80.0, detail=3.0)
    lobes = nb.math('SINE', nb.math('ADD', nb.math('MULTIPLY', ang, 3.0), nb.math('MULTIPLY', nz.outputs['Fac'], 1.5)))
    lobe_m = nb.maprange(lobes, -0.1, 0.5)
    ring_in = nb.maprange(r, 0.28, 0.4)
    ring_out = nb.maprange(r, 0.86, 0.76)
    pocket = nb.math('MULTIPLY', nb.math('MULTIPLY', lobe_m, ring_in), ring_out)
    base = nb.ramp(r, [(0.0, hexc('#e0503a')), (0.25, hexc('#cf2a18')), (0.9, hexc('#c01a0e')),
                       (1.0, hexc('#a3120a'))])
    seeds = nb.voronoi(scale=420.0, feature='F1')
    seed_m = nb.math('MULTIPLY', nb.maprange(seeds.outputs['Distance'], 0.12, 0.05), pocket)
    gel = nb.mix(pocket, base.outputs['Color'], hexc('#f06a4a'))
    col = nb.mix(seed_m, gel, hexc('#f4d38a'))
    nb.set('Base Color', col)
    _MATS['tomato'] = mat
    return mat


def mat_sauce(color='#e0662a', name='Sauce'):
    key = ('sauce', color)
    if key in _MATS:
        return _MATS[key]
    mat, nb = principled(name, color=color, rough=0.12, sss=0.35, sss_radius=(1.0, 0.5, 0.3),
                         sss_scale=0.003, coat=0.6, coat_rough=0.05)
    nz = nb.noise(scale=120.0, detail=3.0)
    nb.set('Normal', nb.bump(nz.outputs['Fac'], strength=0.04, distance=0.0003))
    _MATS[key] = mat
    return mat


def mat_bacon():
    if 'bacon' in _MATS:
        return _MATS['bacon']
    mat, nb = principled('Bacon', rough=0.35, sss=0.3, sss_radius=(1, 0.4, 0.3), sss_scale=0.003,
                         coat=0.4, coat_rough=0.2)
    uv = nb.texco('UV')
    sepn = nb.sep(uv)
    nz = nb.noise(scale=12.0, detail=4.0, vec=uv)
    v = nb.math('ADD', sepn.outputs['Y'], nb.math('MULTIPLY', nz.outputs['Fac'], 0.25))
    stripes = nb.math('SINE', nb.math('MULTIPLY', v, 22.0))
    col = nb.ramp(nb.maprange(stripes, -1, 1), [(0.0, hexc('#5e1608')), (0.35, hexc('#8a2a12')),
                                               (0.65, hexc('#c7744a')), (1.0, hexc('#e7b48a'))])
    burn = nb.noise(scale=30.0, detail=5.0, vec=uv)
    bm = nb.maprange(burn.outputs['Fac'], 0.5, 0.75, 0.0, 0.6)
    col2 = nb.mix(bm, col.outputs['Color'], hexc('#2a0a03'))
    nb.set('Base Color', col2)
    fine = nb.noise(scale=180.0, detail=3.0)
    nb.set('Normal', nb.bump(fine.outputs['Fac'], strength=0.4, distance=0.0006))
    _MATS['bacon'] = mat
    return mat


def mat_crispy():
    if 'crispy' in _MATS:
        return _MATS['crispy']
    mat, nb = principled('CrispyChicken', rough=0.55, sss=0.15, sss_radius=(1, 0.7, 0.4), sss_scale=0.003)
    n1 = nb.noise(scale=90.0, detail=8.0, rough=0.7, distortion=0.6)
    col = nb.ramp(n1.outputs['Fac'], [(0.3, hexc('#8a4a14')), (0.5, hexc('#c27a2a')), (0.7, hexc('#e0a54a')),
                                      (0.85, hexc('#f0c46e'))])
    nb.set('Base Color', col.outputs['Color'])
    v = nb.voronoi(scale=160.0, feature='F1')
    h = nb.math('ADD', n1.outputs['Fac'], v.outputs['Distance'])
    nb.set('Normal', nb.bump(h, strength=0.9, distance=0.0015))
    _MATS['crispy'] = mat
    return mat


def mat_onion():
    if 'onion' in _MATS:
        return _MATS['onion']
    mat, nb = principled('Onion', color='#e9d2e6', rough=0.25, sss=0.7, sss_radius=(1, 0.8, 1),
                         sss_scale=0.003, coat=0.4, coat_rough=0.1)
    _MATS['onion'] = mat
    return mat


def mat_pickle():
    if 'pickle' in _MATS:
        return _MATS['pickle']
    mat, nb = principled('Pickle', rough=0.25, sss=0.5, sss_radius=(0.6, 1, 0.4), sss_scale=0.003,
                         coat=0.5, coat_rough=0.1)
    tc = nb.texco('Object')
    sepn = nb.sep(tc)
    comb = nb.node('ShaderNodeCombineXYZ')
    nb.link(sepn.outputs['X'], comb.inputs['X'])
    nb.link(sepn.outputs['Y'], comb.inputs['Y'])
    ln = nb.node('ShaderNodeVectorMath', operation='LENGTH')
    nb.link(comb.outputs[0], ln.inputs[0])
    r = nb.maprange(ln.outputs['Value'], 0.0, 0.016)
    col = nb.ramp(r, [(0.0, hexc('#c9c46a')), (0.55, hexc('#9fa34a')), (0.85, hexc('#6b7a2a')),
                      (1.0, hexc('#3e5216'))])
    nb.set('Base Color', col.outputs['Color'])
    _MATS['pickle'] = mat
    return mat


# ----------------------------------------------------------------------------
# geometry builders  (each returns (root_empty, height))
# ----------------------------------------------------------------------------
def build_bun_bottom(name='BunBottom', seed=1.0):
    root = empty(name)
    prof = [(0, 0.0), (0.03, 0.0), (0.045, 0.0008), (0.052, 0.0028), (0.0558, 0.0068), (0.0572, 0.012),
            (0.0566, 0.0172), (0.0546, 0.0212), (0.0515, 0.0236), (0.047, 0.0244), (0.02, 0.0246), (0, 0.0246)]
    bm, _ = lathe_bm(prof, 96)
    jitter_radial(bm, 0.0011, 35.0, seed, zamp=0.0004)
    ob = mesh_object(name + '_mesh', bm, [mat_bun_crust(0.0246, top_dark=False), mat_bun_crumb()])
    assign_mat_by(ob, 1, lambda c, n: n.z > 0.75 and c.z > 0.02)
    add_subsurf(ob, 2)
    set_parent(ob, root)
    return root, 0.0246


def build_bun_top(name='BunTop', seed=2.0, seeds=85, height=0.046, radius=0.0585):
    root = empty(name)
    k = radius / 0.0575
    hk = height / 0.0445
    prof = [(0, 0.0), (0.045 * k, 0.0), (0.051 * k, 0.0006), (0.0556 * k, 0.0032 * hk), (0.0575 * k, 0.0085 * hk),
            (0.0571 * k, 0.0145 * hk), (0.0548 * k, 0.0222 * hk), (0.0495 * k, 0.0302 * hk),
            (0.0405 * k, 0.0372 * hk), (0.0285 * k, 0.0418 * hk), (0.0145 * k, 0.0440 * hk), (0, 0.0446 * hk)]
    bm, _ = lathe_bm(prof, 96)
    jitter_radial(bm, 0.0018, 16.0, seed, zamp=0.0014)
    jitter_radial(bm, 0.0006, 45.0, seed + 3, zamp=0.0005)
    ob = mesh_object(name + '_mesh', bm, [mat_bun_crust(0.0446 * hk, top_dark=True), mat_bun_crumb()])
    assign_mat_by(ob, 1, lambda c, n: n.z < -0.75 and c.z < 0.004)
    add_subsurf(ob, 2)
    set_parent(ob, root)
    if seeds:
        bvh = bvh_of(ob)
        rnd = random.Random(int(seed * 100))
        sbm = bmesh.new()
        placed = []
        tries = 0
        while len(placed) < seeds and tries < seeds * 40:
            tries += 1
            a = rnd.uniform(0, 2 * math.pi)
            r = math.sqrt(rnd.uniform(0, 1)) * 0.047 * k
            hit = bvh.ray_cast(Vector((r * math.cos(a), r * math.sin(a), 0.2)), Vector((0, 0, -1)))
            if hit[0] is None:
                continue
            p, nrm = hit[0], hit[1]
            if any((p - q).length < 0.0042 for q in placed):
                continue
            placed.append(p)
            # one seed: flattened ellipsoid aligned to the bun normal
            g = bmesh.ops.create_uvsphere(sbm, u_segments=10, v_segments=6, radius=1.0)
            vs = g['verts']
            sx = rnd.uniform(0.0016, 0.0021)
            rot_z = Matrix.Rotation(rnd.uniform(0, math.pi), 4, 'Z')
            sc = Matrix.Diagonal((sx, sx * 0.55, 0.00065, 1.0))
            align = nrm.to_track_quat('Z', 'Y').to_matrix().to_4x4()
            tilt = Matrix.Rotation(rnd.uniform(-0.25, 0.25), 4, 'X')
            M = Matrix.Translation(p + nrm * 0.0003) @ align @ tilt @ rot_z @ sc
            bmesh.ops.transform(sbm, matrix=M, verts=vs)
        so = mesh_object(name + '_seeds', sbm, [mat_sesame()])
        set_parent(so, root)
    return root, 0.0446 * hk


def build_patty(name='Patty', seed=3.0, radius=0.0635, height=0.019):
    root = empty(name)
    R, H = radius, height
    prof = [(0, 0.0), (R * 0.82, 0.0), (R * 0.935, 0.0009), (R * 0.99, 0.0038), (R, H * 0.5),
            (R * 0.99, H - 0.0038), (R * 0.935, H - 0.0009), (R * 0.82, H), (0, H)]
    bm, _ = lathe_bm(prof, 128)
    jitter_radial(bm, 0.0032, 22.0, seed, zamp=0.0012)
    # second octave for a hand-formed edge
    jitter_radial(bm, 0.0014, 75.0, seed + 4, zamp=0.0006)
    ob = mesh_object(name + '_mesh', bm, [mat_patty()])
    add_subsurf(ob, 2)
    tex = bpy.data.textures.new(name + '_disp', 'VORONOI')
    tex.noise_scale = 0.0032
    tex.distance_metric = 'DISTANCE'
    d = ob.modifiers.new('Displace', 'DISPLACE')
    d.texture = tex
    d.texture_coords = 'LOCAL'
    d.strength = -0.0016
    d.mid_level = 0.5
    add_subsurf(ob, 1)
    set_parent(ob, root)
    return root, H


def build_cheese(name='Cheese', size=0.112, rest_r=0.0585, bend=0.0065, seed=5.0, rot=math.pi / 4, sag=1.0):
    root = empty(name)
    N = 56
    bm = bmesh.new()
    verts = []
    for j in range(N + 1):
        row = []
        for i in range(N + 1):
            x = (i / N - 0.5) * size
            y = (j / N - 0.5) * size
            row.append(bm.verts.new((x, y, 0)))
        verts.append(row)
    for j in range(N):
        for i in range(N):
            bm.faces.new((verts[j][i], verts[j][i + 1], verts[j + 1][i + 1], verts[j + 1][i]))
    rotm = Matrix.Rotation(rot, 3, 'Z')
    phimax = 1.3
    flat = []
    rmax = size * 0.7071
    for v in bm.verts:
        p = rotm @ Vector((v.co.x, v.co.y, 0))
        r = math.hypot(p.x, p.y)
        ang = math.atan2(p.y, p.x)
        # corners melt narrower and longer
        cornerness = abs(math.cos(2 * (ang - rot)))
        nz = noise.noise(Vector((p.x * 60 + seed, p.y * 60, 0))) * 0.0006
        # 'Flat' shape: a loose slice with soft waves, used while floating
        fz = (0.0016 * math.sin(p.x * 70 + seed) * math.cos(p.y * 55) - 0.006 * cornerness * (r / rmax) ** 3)
        flat.append(Vector((p.x, p.y, fz + nz + 0.0002)))
        z = 0.0
        if r > rest_r:
            s = (r - rest_r) * (1.0 + 0.6 * sag * cornerness)
            if s < bend * phimax:
                phi = s / bend
                rad = rest_r + bend * math.sin(phi)
                z = -bend * (1 - math.cos(phi))
            else:
                s2 = s - bend * phimax
                rad = rest_r + bend * math.sin(phimax) + s2 * math.cos(phimax)
                z = -bend * (1 - math.cos(phimax)) - s2 * math.sin(phimax)
            p.x, p.y = p.x / r * rad, p.y / r * rad
        v.co = Vector((p.x, p.y, z + nz + 0.0002))
    ob = mesh_object(name + '_mesh', bm, [mat_cheese()])
    ob.shape_key_add(name='Basis')
    kb = ob.shape_key_add(name='Flat')
    for i, co in enumerate(flat):
        kb.data[i].co = co
    kb.value = 0.0
    add_solidify(ob, 0.0022, offset=1.0)
    add_subsurf(ob, 1)
    set_parent(ob, root)
    return root, 0.0024


def build_lettuce(name='Lettuce', seed=6.0, radius=0.071, base_r=0.054):
    root = empty(name)
    rings, segs = 22, 160
    bm = bmesh.new()
    center = bm.verts.new((0, 0, 0))
    grid = []
    for k in range(1, rings + 1):
        rho = k / rings
        row = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            Rn = radius * (1 + 0.09 * noise.noise(Vector((math.cos(a) * 2 + seed, math.sin(a) * 2, 0)))
                           + 0.05 * noise.noise(Vector((math.cos(a) * 7, math.sin(a) * 7 + seed, 1))))
            r = rho * Rn
            ruffle = (0.0045 * math.sin(13 * a + 2.5 * noise.noise(Vector((math.cos(a) * 3, math.sin(a) * 3, seed))))
                      + 0.0022 * math.sin(31 * a + seed) + 0.001 * math.sin(57 * a)) * rho ** 4
            z = ruffle + 0.0012 * noise.noise(Vector((r * math.cos(a) * 80, r * math.sin(a) * 80, seed)))
            z += 0.0028 * noise.noise(Vector((r * math.cos(a) * 160, r * math.sin(a) * 160, seed + 2))) * rho ** 2
            if r > base_r:
                z -= (r - base_r) * 0.55
            z += 0.0015 * rho ** 2
            row.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z)))
        grid.append(row)
    for i in range(segs):
        bm.faces.new((center, grid[0][i], grid[0][(i + 1) % segs]))
    for k in range(rings - 1):
        for i in range(segs):
            bm.faces.new((grid[k][i], grid[k][(i + 1) % segs], grid[k + 1][(i + 1) % segs], grid[k + 1][i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    ob = mesh_object(name + '_mesh', bm, [mat_lettuce()])
    add_solidify(ob, 0.0009, offset=1.0)
    add_subsurf(ob, 1)
    set_parent(ob, root)
    return root, 0.0045


def build_tomato(name='Tomato', seed=7.0):
    root = empty(name)
    rnd = random.Random(int(seed * 10))
    for idx, (ox, oy, rz) in enumerate(((-0.021, -0.013, 0.4), (0.023, -0.009, 1.9))):
        R, H = 0.035, 0.0068
        prof = [(0, 0), (R * 0.9, 0), (R * 0.985, 0.0009), (R, H * 0.5), (R * 0.985, H - 0.0009), (R * 0.9, H), (0, H)]
        bm, _ = lathe_bm(prof, 72)
        jitter_radial(bm, 0.0008, 40.0, seed + idx, zamp=0.0002)
        ob = mesh_object(f'{name}_{idx}', bm, [mat_tomato()])
        add_subsurf(ob, 2)
        ob.location = (ox, oy, 0.0012 * idx)
        ob.rotation_euler = (rnd.uniform(-0.02, 0.02), rnd.uniform(-0.02, 0.02), rz)
        set_parent(ob, root)
    return root, 0.0062


def build_sauce(name='Sauce', seed=8.0, radius=0.052, color='#e0662a', drips=()):
    root = empty(name)
    rings, segs = 16, 120
    bm = bmesh.new()
    top_c = bm.verts.new((0, 0, 0.0028))
    grid = []
    edge_r = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        Rn = radius * (1 + 0.12 * noise.noise(Vector((math.cos(a) * 2.5 + seed, math.sin(a) * 2.5, 0))))
        for (da, dl) in drips:
            d = math.atan2(math.sin(a - da), math.cos(a - da))
            Rn += dl * 0.55 * math.exp(-(d / 0.09) ** 2)
        edge_r.append(Rn)
    for k in range(1, rings + 1):
        rho = k / rings
        row = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            r = rho * edge_r[i]
            h = 0.0032 * math.sqrt(max(0.0, 1 - rho ** 6)) * (1 + 0.25 * math.sin(5 * a + rho * 14))
            row.append(bm.verts.new((r * math.cos(a), r * math.sin(a), h)))
        grid.append(row)
    bot_c = bm.verts.new((0, 0, 0))
    for i in range(segs):
        bm.faces.new((top_c, grid[0][i], grid[0][(i + 1) % segs]))
    for k in range(rings - 1):
        for i in range(segs):
            bm.faces.new((grid[k][i], grid[k][(i + 1) % segs], grid[k + 1][(i + 1) % segs], grid[k + 1][i]))
    # flat underside
    last = grid[-1]
    for i in range(segs):
        bm.faces.new((last[(i + 1) % segs], last[i], bot_c))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = mesh_object(name + '_mesh', bm, [mat_sauce(color)])
    add_subsurf(ob, 2)
    set_parent(ob, root)
    # drips running over the cheese edge
    for j, (da, dl) in enumerate(drips):
        dbm = bmesh.new()
        bmesh.ops.create_uvsphere(dbm, u_segments=16, v_segments=10, radius=1.0)
        L = dl + 0.004
        for v in dbm.verts:
            t = (v.co.z + 1) / 2  # 0 bottom .. 1 top
            w = 0.0032 * (0.55 + 0.45 * t) if v.co.z < 0.6 else 0.0032
            v.co = Vector((v.co.x * w, v.co.y * w * 0.6, -L * (1 - t)))
        dob = mesh_object(f'{name}_drip{j}', dbm, [mat_sauce(color)])
        rr = radius * 0.98 + dl * 0.2
        dob.location = (rr * math.cos(da), rr * math.sin(da), 0.0015)
        dob.rotation_euler = (0, 0, da + math.pi / 2)
        add_subsurf(dob, 1)
        set_parent(dob, root)
    return root, 0.0028


def build_bacon(name='Bacon', seed=9.0, strips=2):
    root = empty(name)
    rnd = random.Random(int(seed))
    for s in range(strips):
        L, W = 0.13, 0.026
        nu, nv = 60, 8
        bm = bmesh.new()
        uv_layer = bm.loops.layers.uv.new()
        vs = []
        for j in range(nv + 1):
            row = []
            for i in range(nu + 1):
                u, v = i / nu, j / nv
                x = (u - 0.5) * L
                y = (v - 0.5) * W
                z = 0.003 * math.sin(u * math.pi * 5 + s) + 0.0012 * math.sin(u * 23 + v * 4 + seed)
                row.append(bm.verts.new((x, y, z + 0.003)))
            vs.append(row)
        for j in range(nv):
            for i in range(nu):
                f = bm.faces.new((vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i]))
                for loop, (ii, jj) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                    loop[uv_layer].uv = (ii / nu, jj / nv)
        ob = mesh_object(f'{name}_{s}', bm, [mat_bacon()])
        add_solidify(ob, 0.002, offset=1.0)
        add_subsurf(ob, 1)
        # strips cross over the patty and stick out towards the front
        ob.location = ((s - (strips - 1) / 2) * 0.026, -0.012, s * 0.0015)
        ob.rotation_euler = (0, 0, math.pi / 2 + (0.38 if s == 0 else -0.38) + rnd.uniform(-0.05, 0.05))
        set_parent(ob, root)
    return root, 0.008


def build_crispy(name='Crispy', seed=10.0):
    root = empty(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=1.0)
    for v in bm.verts:
        a = math.atan2(v.co.y, v.co.x)
        R = 0.064 * (1 + 0.12 * noise.noise(Vector((math.cos(a) * 1.6 + seed, math.sin(a) * 1.6, 0))))
        v.co = Vector((v.co.x * R * 1.05, v.co.y * R * 0.92, (v.co.z + 1) * 0.0115))
    jitter_radial(bm, 0.003, 45.0, seed, zamp=0.0015)
    ob = mesh_object(name + '_mesh', bm, [mat_crispy()])
    add_subsurf(ob, 1)
    tex = bpy.data.textures.new(name + '_disp', 'CLOUDS')
    tex.noise_scale = 0.0035
    tex.noise_depth = 3
    d = ob.modifiers.new('Displace', 'DISPLACE')
    d.texture = tex
    d.texture_coords = 'LOCAL'
    d.strength = 0.0028
    add_subsurf(ob, 1)
    set_parent(ob, root)
    return root, 0.023


def build_onion_rings(name='Onion', seed=11.0):
    root = empty(name)
    rnd = random.Random(int(seed))
    for k in range(4):
        r = rnd.uniform(0.012, 0.022)
        bpy.ops.mesh.primitive_torus_add(major_radius=r, minor_radius=0.0016, major_segments=48, minor_segments=8)
        ob = bpy.context.active_object
        ob.name = f'{name}_{k}'
        ob.scale = (1, 1, 0.6)
        ob.data.materials.append(mat_onion())
        for p in ob.data.polygons:
            p.use_smooth = True
        ob.location = (rnd.uniform(-0.025, 0.025), rnd.uniform(-0.025, 0.025), 0.001)
        set_parent(ob, root)
    return root, 0.003


def build_pickles(name='Pickles', seed=12.0, count=3):
    root = empty(name)
    rnd = random.Random(int(seed))
    pos = [(-0.022, -0.012), (0.018, -0.018), (0.004, 0.02), (-0.03, 0.02)][:count]
    for k, (x, y) in enumerate(pos):
        R, H = 0.016, 0.003
        prof = [(0, 0), (R, 0), (R, H), (0, H)]
        bm, rings = lathe_bm(prof, 40)
        for v in bm.verts:
            a = math.atan2(v.co.y, v.co.x)
            rr = math.hypot(v.co.x, v.co.y)
            if rr > 1e-6:
                f = 1 + 0.05 * math.sin(a * 14)
                v.co.x *= f
                v.co.y *= f
        ob = mesh_object(f'{name}_{k}', bm, [mat_pickle()])
        add_subsurf(ob, 2)
        ob.location = (x, y, 0.0004 * k)
        ob.rotation_euler = (rnd.uniform(-0.05, 0.05), rnd.uniform(-0.05, 0.05), rnd.uniform(0, 3))
        set_parent(ob, root)
    return root, 0.003


# ----------------------------------------------------------------------------
# full burgers
# ----------------------------------------------------------------------------
LAYER_BUILDERS = {
    'bun_bottom': build_bun_bottom,
    'lettuce': build_lettuce,
    'tomato': build_tomato,
    'patty': build_patty,
    'cheese': build_cheese,
    'sauce': build_sauce,
    'bun_top': build_bun_top,
    'bacon': build_bacon,
    'crispy': build_crispy,
    'onion': build_onion_rings,
    'pickles': build_pickles,
}

# how much the next layer sinks into this one (soft ingredients settle)
SETTLE = {'lettuce': 0.0025, 'cheese': 0.0003, 'sauce': 0.0012, 'tomato': 0.0, 'patty': 0.0,
          'bacon': 0.003, 'onion': 0.001, 'pickles': 0.0005, 'crispy': 0.0}

CLASSIC = ['bun_bottom', 'lettuce', 'tomato', 'patty', 'cheese', 'sauce', 'bun_top']


def build_burger(name='Burger', layers=CLASSIC, opts=None):
    """Builds a stacked burger. Returns (root, [(key, layer_root, rest_z, height)])."""
    opts = opts or {}
    root = empty(name)
    out = []
    z = 0.0
    for i, key in enumerate(layers):
        kw = dict(opts.get(i, {}))
        kw.setdefault('name', f'{name}_{key}_{i}')
        lr, h = LAYER_BUILDERS[key](**kw)
        set_parent(lr, root)
        lr.location = (0, 0, z)
        out.append((key, lr, z, h))
        z += h - SETTLE.get(key, 0.0)
    return root, out
