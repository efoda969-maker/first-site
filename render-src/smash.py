"""Smash burger: thin patties with lacy crispy edges, American cheese melted
onto each patty and dripping, caramelized onions, glossy seedless brioche."""
import bpy
import bmesh
import math
import random
from mathutils import Vector, Matrix, noise

from lib import (hexc, principled, empty, set_parent, mesh_object, add_subsurf, add_solidify,
                 lathe_bm, jitter_radial, assign_mat_by)
from burger import mat_bun_crumb, mat_sauce, mat_pickle, build_pickles, build_bacon, build_crispy, build_lettuce, build_tomato

_M = {}


def _n(x, y=0.0, z=0.0):
    return noise.noise(Vector((x, y, z)))


# ----------------------------------------------------------------------------
# materials
# ----------------------------------------------------------------------------
def mat_brioche(height, heel=False):
    key = ('brioche', round(height, 4), heel)
    if key in _M:
        return _M[key]
    mat, nb = principled('Brioche', rough=0.38, sss=0.05, sss_radius=(1.0, 0.6, 0.3), sss_scale=0.002,
                         coat=0.35, coat_rough=0.18)
    z = nb.sep(nb.texco('Object')).outputs['Z']
    zf = nb.maprange(z, 0.0, height)
    nz = nb.noise(scale=14.0, detail=3.0, rough=0.55)
    zf2 = nb.math('ADD', zf, nb.math('MULTIPLY', nb.math('SUBTRACT', nz.outputs['Fac'], 0.5), 0.45))
    if not heel:
        stops = [(0.0, hexc('#e8b467')), (0.07, hexc('#d98d36')), (0.22, hexc('#c4681c')),
                 (0.5, hexc('#a44c12')), (1.0, hexc('#7f340a'))]
    else:
        stops = [(0.0, hexc('#9a4d16')), (0.3, hexc('#c06d27')), (0.75, hexc('#dc9a4c')), (1.0, hexc('#ebbe7c'))]
    col = nb.ramp(zf2, stops)
    mott = nb.noise(scale=60.0, detail=2.0)
    mm = nb.maprange(mott.outputs['Fac'], 0.5, 0.75, 0.0, 0.18)
    nb.set('Base Color', nb.mix(mm, col.outputs['Color'], hexc('#6e2e08')))
    rn = nb.noise(scale=40.0, detail=2.0)
    nb.set('Roughness', nb.maprange(rn.outputs['Fac'], 0.35, 0.65, 0.22, 0.48))
    # stretched noise = soft wrinkles of a proofed brioche
    vec = nb.node('ShaderNodeMapping')
    vec.inputs['Scale'].default_value = (1.0, 1.0, 3.0)
    nb.link(nb.texco('Object'), vec.inputs['Vector'])
    wr = nb.noise(scale=55.0, detail=3.0, vec=vec.outputs['Vector'])
    fine = nb.noise(scale=420.0, detail=1.0)
    h = nb.math('ADD', wr.outputs['Fac'], nb.math('MULTIPLY', fine.outputs['Fac'], 0.25))
    nb.set('Normal', nb.bump(h, strength=0.12, distance=0.0006))
    _M[key] = mat
    return mat


def mat_smash():
    if 'smash' in _M:
        return _M['smash']
    mat, nb = principled('SmashPatty', rough=0.5, spec=0.35)
    tc = nb.texco('Object')
    sep = nb.sep(tc)
    comb = nb.node('ShaderNodeCombineXYZ')
    nb.link(sep.outputs['X'], comb.inputs['X'])
    nb.link(sep.outputs['Y'], comb.inputs['Y'])
    ln = nb.node('ShaderNodeVectorMath', operation='LENGTH')
    nb.link(comb.outputs[0], ln.inputs[0])
    edge = nb.maprange(ln.outputs['Value'], 0.045, 0.066)          # 0 centre .. 1 lacy rim
    n1 = nb.noise(scale=160.0, detail=5.0, rough=0.7, distortion=0.5)
    v1 = nb.voronoi(scale=220.0, feature='F1')
    crust = nb.math('ADD', nb.math('MULTIPLY', n1.outputs['Fac'], 0.75), nb.math('MULTIPLY', v1.outputs['Distance'], 0.5))
    col = nb.ramp(crust, [(0.25, hexc('#140602')), (0.42, hexc('#2e1206')), (0.58, hexc('#4f230b')),
                          (0.74, hexc('#743914')), (0.9, hexc('#9a5622'))])
    rim = nb.mix(nb.math('MULTIPLY', edge, 0.65), col.outputs['Color'], hexc('#2a1006'))
    big = nb.noise(scale=30.0, detail=2.0)
    nb.set('Base Color', nb.mix(nb.maprange(big.outputs['Fac'], 0.55, 0.75, 0.0, 0.35), rim, hexc('#120602')))
    juicy = nb.noise(scale=70.0, detail=2.0)
    nb.set('Roughness', nb.maprange(juicy.outputs['Fac'], 0.4, 0.65, 0.18, 0.62))
    h = nb.math('ADD', crust, nb.math('MULTIPLY', edge, 0.4))
    nb.set('Normal', nb.bump(h, strength=0.85, distance=0.0012))
    _M['smash'] = mat
    return mat


def mat_american():
    if 'american' in _M:
        return _M['american']
    mat, nb = principled('AmericanCheese', rough=0.28, sss=0.3, sss_radius=(1.0, 0.6, 0.2), sss_scale=0.003,
                         coat=0.3, coat_rough=0.12)
    nz = nb.noise(scale=25.0, detail=2.0)
    col = nb.ramp(nz.outputs['Fac'], [(0.3, hexc('#f39200')), (0.7, hexc('#fbaa1c'))])
    nb.set('Base Color', col.outputs['Color'])
    fine = nb.noise(scale=160.0, detail=2.0)
    nb.set('Normal', nb.bump(fine.outputs['Fac'], strength=0.04, distance=0.0003))
    _M['american'] = mat
    return mat


def mat_onion():
    if 'caramel_onion' in _M:
        return _M['caramel_onion']
    mat, nb = principled('CaramelOnion', rough=0.22, sss=0.7, sss_radius=(1.0, 0.55, 0.25), sss_scale=0.003,
                         coat=0.6, coat_rough=0.08)
    nz = nb.noise(scale=90.0, detail=3.0)
    col = nb.ramp(nz.outputs['Fac'], [(0.25, hexc('#7a3a10')), (0.5, hexc('#b8661f')), (0.75, hexc('#dc9a45'))])
    nb.set('Base Color', col.outputs['Color'])
    _M['caramel_onion'] = mat
    return mat


# ----------------------------------------------------------------------------
# builders
# ----------------------------------------------------------------------------
def _disc_surfaces(name, R_of, top_h, bot_h, rings=26, segs=180, mats=()):
    """Closed 'pancake': top surface z=top_h(rho, a, r), bottom z=bot_h(...), meeting at the rim."""
    bm = bmesh.new()
    top_c = bm.verts.new((0, 0, top_h(0.0, 0.0, 0.0)))
    bot_c = bm.verts.new((0, 0, bot_h(0.0, 0.0, 0.0)))
    top, bot = [], []
    for k in range(1, rings + 1):
        rho = k / rings
        rt, rb = [], []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            R = R_of(a)
            r = rho * R
            x, y = r * math.cos(a), r * math.sin(a)
            if k == rings:
                v = bm.verts.new((x, y, (top_h(rho, a, r) + bot_h(rho, a, r)) / 2))
                rt.append(v)
                rb.append(v)
            else:
                rt.append(bm.verts.new((x, y, top_h(rho, a, r))))
                rb.append(bm.verts.new((x, y, bot_h(rho, a, r))))
        top.append(rt)
        bot.append(rb)
    for i in range(segs):
        j = (i + 1) % segs
        bm.faces.new((top_c, top[0][i], top[0][j]))
        bm.faces.new((bot_c, bot[0][j], bot[0][i]))
    for k in range(rings - 1):
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((top[k][i], top[k + 1][i], top[k + 1][j], top[k][j]))
            bm.faces.new((bot[k][i], bot[k][j], bot[k + 1][j], bot[k + 1][i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_object(name, bm, mats)


def build_smash_patty(name='Smash', seed=3.0, radius=0.064, thick=0.0145):
    root = empty(name)
    s = seed * 3.7

    def R_of(a):
        c, si = math.cos(a), math.sin(a)
        return radius * (1 + 0.08 * _n(c * 1.4 + s, si * 1.4) + 0.05 * _n(c * 4 + s, si * 4, 1)
                         + 0.035 * _n(c * 11, si * 11 + s, 2) + 0.025 * _n(c * 30 + s, si * 30, 3)
                         + 0.012 * _n(c * 70, si * 70, s))

    def prof(rho):
        return (max(0.0, 1 - rho ** 5)) ** 0.45

    def top_h(rho, a, r):
        x, y = r * math.cos(a), r * math.sin(a)
        lump = 0.0016 * _n(x * 90 + s, y * 90) + 0.0007 * _n(x * 260, y * 260 + s)
        return (thick * 0.42 + thick * 0.55 * prof(rho) + lump * (0.4 + 0.6 * prof(rho))
                + 0.0028 * rho ** 3 * _n(x * 120, y * 120, s) + 0.0012 * rho ** 4 * _n(x * 300, y * 300, s + 1))

    def bot_h(rho, a, r):
        x, y = r * math.cos(a), r * math.sin(a)
        return thick * 0.42 - thick * 0.42 * prof(rho) + 0.0005 * _n(x * 120, y * 120, s + 5)

    ob = _disc_surfaces(name + '_mesh', R_of, top_h, bot_h, mats=[mat_smash()])
    add_subsurf(ob, 1)
    tex = bpy.data.textures.new(name + '_disp', 'VORONOI')
    tex.noise_scale = 0.0028
    d = ob.modifiers.new('Displace', 'DISPLACE')
    d.texture = tex
    d.texture_coords = 'LOCAL'
    d.strength = -0.0011
    add_subsurf(ob, 1)
    set_parent(ob, root)
    return root, thick * 0.97


def build_american(name='American', seed=5.0, size=0.112, rest_r=0.05, rot=0.6, patty_r=0.064,
                   drips=None):
    """Square slice melted over a patty: flat on top, slumping over the rim and dripping."""
    root = empty(name)
    rnd = random.Random(int(seed * 17))
    if drips is None:
        drips = [(rnd.uniform(0, 2 * math.pi), rnd.uniform(0.007, 0.016), rnd.uniform(0.14, 0.26)) for _ in range(6)]
        drips.append((-math.pi / 2 + rnd.uniform(-0.5, -0.1), 0.02, 0.2))       # towards the camera
        drips.append((-math.pi / 2 + rnd.uniform(0.2, 0.6), 0.013, 0.16))
    N = 64
    bm = bmesh.new()
    verts = []
    for j in range(N + 1):
        row = []
        for i in range(N + 1):
            row.append(bm.verts.new(((i / N - 0.5) * size, (j / N - 0.5) * size, 0)))
        verts.append(row)
    for j in range(N):
        for i in range(N):
            bm.faces.new((verts[j][i], verts[j][i + 1], verts[j + 1][i + 1], verts[j + 1][i]))
    rotm = Matrix.Rotation(rot, 3, 'Z')
    bend = 0.004
    phimax = 1.45
    for v in bm.verts:
        q = Vector((v.co.x, v.co.y, 0))
        rq = q.length
        if rq > 1e-6:
            sq = max(abs(q.x), abs(q.y)) / rq          # 1 on axes, 0.707 on diagonals
            q *= (0.62 + 0.38 * sq ** 1.0) / 0.9 * 0.93
        p = rotm @ q
        r = math.hypot(p.x, p.y)
        ang = math.atan2(p.y, p.x)
        extra = 0.0
        for (da, dl, w) in drips:
            d = math.atan2(math.sin(ang - da), math.cos(ang - da))
            extra += dl * math.exp(-(d / w) ** 4)        # flat-topped: rounded tongues, not fangs
        z = 0.0
        if r > rest_r:
            s = (r - rest_r) * 1.05 + extra * min(1.0, (r - rest_r) / 0.006)
            if s < bend * phimax:
                phi = s / bend
                rad = rest_r + bend * math.sin(phi)
                z = -bend * (1 - math.cos(phi))
            else:
                s2 = s - bend * phimax
                rad = rest_r + bend * math.sin(phimax) + s2 * math.cos(phimax) * 0.5
                z = -bend * (1 - math.cos(phimax)) - s2 * math.sin(phimax)
            # hug the patty: do not stick out much past its rim
            rad = min(rad, patty_r + 0.004 + 0.002 * _n(ang * 3, seed))
            p.x, p.y = p.x / r * rad, p.y / r * rad
        z += 0.0007 * _n(p.x * 70 + seed, p.y * 70)
        v.co = Vector((p.x, p.y, z + 0.0002))
    ob = mesh_object(name + '_mesh', bm, [mat_american()])
    add_solidify(ob, 0.0026, offset=1.0)
    add_subsurf(ob, 1)
    set_parent(ob, root)
    return root, 0.0026


def build_patty_cheese(name='PattyCheese', seed=3.0, cheese=True, radius=0.064):
    """One unit = smash patty with its slice melted on top (they move together)."""
    root = empty(name)
    p, ph = build_smash_patty(name + '_patty', seed, radius)
    set_parent(p, root)
    h = ph
    if cheese:
        c, ch = build_american(name + '_cheese', seed + 11, rot=seed * 0.9, patty_r=radius)
        set_parent(c, root)
        c.location.z = ph - 0.0006
        h += ch - 0.0006
    return root, h


def build_onions(name='Onions', seed=9.0, count=80, radius=0.046):
    root = empty(name)
    rnd = random.Random(int(seed * 31))
    bm = bmesh.new()
    for k in range(count):
        rr = radius * math.sqrt(rnd.random())
        ca = rnd.uniform(0, 2 * math.pi)
        cx, cy = rr * math.cos(ca), rr * math.sin(ca)
        ar = rnd.uniform(0.006, 0.02)
        span = rnd.uniform(1.0, 3.0)
        a0 = rnd.uniform(0, 2 * math.pi)
        z0 = rnd.uniform(0.0, 0.009) * (1 - 0.55 * rr / radius)
        w = rnd.uniform(0.0035, 0.0055)
        lean = rnd.uniform(0.25, 0.75)          # 0 = flat, 1 = upright
        seg = 18
        prev = None
        for i in range(seg + 1):
            t = i / seg
            a = a0 + span * t
            px, py = cx + ar * math.cos(a), cy + ar * math.sin(a)
            nx, ny = math.cos(a), math.sin(a)
            z = z0 + 0.0022 * math.sin(t * math.pi) + 0.0012 * math.sin(t * 9 + k)
            dx, dy, dz = nx * w * (1 - lean), ny * w * (1 - lean), w * lean
            v1 = bm.verts.new((px - dx / 2, py - dy / 2, z))
            v2 = bm.verts.new((px + dx / 2, py + dy / 2, z + dz))
            if prev:
                bm.faces.new((prev[0], v1, v2, prev[1]))
            prev = (v1, v2)
    ob = mesh_object(name + '_mesh', bm, [mat_onion()])
    add_solidify(ob, 0.0016, offset=0.0)
    add_subsurf(ob, 1)
    set_parent(ob, root)
    return root, 0.009


def build_brioche_top(name='BriocheTop', seed=2.0, radius=0.062, height=0.05):
    root = empty(name)
    k, hk = radius / 0.062, height / 0.05
    prof = [(0, 0.0), (0.047 * k, 0.0), (0.054 * k, 0.0008), (0.0594 * k, 0.0042 * hk), (0.062 * k, 0.0105 * hk),
            (0.0612 * k, 0.0175 * hk), (0.058 * k, 0.026 * hk), (0.052 * k, 0.034 * hk),
            (0.0425 * k, 0.0415 * hk), (0.03 * k, 0.0466 * hk), (0.015 * k, 0.0492 * hk), (0, 0.05 * hk)]
    bm, _ = lathe_bm(prof, 120)
    jitter_radial(bm, 0.0022, 12.0, seed, zamp=0.0018)
    jitter_radial(bm, 0.0008, 38.0, seed + 3, zamp=0.0007)
    ob = mesh_object(name + '_mesh', bm, [mat_brioche(0.05 * hk), mat_bun_crumb()])
    assign_mat_by(ob, 1, lambda c, n: n.z < -0.75 and c.z < 0.004)
    add_subsurf(ob, 2)
    set_parent(ob, root)
    return root, 0.05 * hk


def build_brioche_heel(name='BriocheHeel', seed=1.0, radius=0.06):
    root = empty(name)
    k = radius / 0.06
    prof = [(0, 0.0), (0.035 * k, 0.0), (0.049 * k, 0.0009), (0.0558 * k, 0.003), (0.0594 * k, 0.0075), (0.0602 * k, 0.0128),
            (0.0592 * k, 0.018), (0.0566 * k, 0.0218), (0.053 * k, 0.0238), (0.047 * k, 0.0246), (0.02 * k, 0.0248), (0, 0.0248)]
    bm, _ = lathe_bm(prof, 120)
    jitter_radial(bm, 0.0012, 30.0, seed, zamp=0.0005)
    ob = mesh_object(name + '_mesh', bm, [mat_brioche(0.0248, heel=True), mat_bun_crumb()])
    assign_mat_by(ob, 1, lambda c, n: n.z > 0.75 and c.z > 0.02)
    add_subsurf(ob, 2)
    set_parent(ob, root)
    return root, 0.0248


def build_house_sauce(name='HouseSauce', seed=8.0, radius=0.048, color='#e46a24'):
    root = empty(name)
    rings, segs = 16, 140
    bm = bmesh.new()
    c = bm.verts.new((0, 0, 0.0034))
    grid = []
    edge = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        edge.append(radius * (1 + 0.14 * _n(math.cos(a) * 2.2 + seed, math.sin(a) * 2.2) + 0.05 * _n(math.cos(a) * 7, math.sin(a) * 7, seed)))
    for kk in range(1, rings + 1):
        rho = kk / rings
        row = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            r = rho * edge[i]
            h = 0.0034 * math.sqrt(max(0.0, 1 - rho ** 6)) * (1 + 0.3 * math.sin(4 * a + rho * 12))
            row.append(bm.verts.new((r * math.cos(a), r * math.sin(a), h)))
        grid.append(row)
    b = bm.verts.new((0, 0, 0))
    for i in range(segs):
        j = (i + 1) % segs
        bm.faces.new((c, grid[0][i], grid[0][j]))
        bm.faces.new((grid[-1][j], grid[-1][i], b))
    for kk in range(rings - 1):
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((grid[kk][i], grid[kk][j], grid[kk + 1][j], grid[kk + 1][i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = mesh_object(name + '_mesh', bm, [mat_sauce(color)])
    add_subsurf(ob, 2)
    set_parent(ob, root)
    return root, 0.003


BUILDERS = {
    'heel': build_brioche_heel,
    'crown': build_brioche_top,
    'pattycheese': build_patty_cheese,
    'onions': build_onions,
    'sauce': build_house_sauce,
    'pickles': build_pickles,
    'bacon': build_bacon,
    'crispy': build_crispy,
    'lettuce': build_lettuce,
    'tomato': build_tomato,
}
SETTLE = {'onions': 0.003, 'sauce': 0.0014, 'pattycheese': 0.0004, 'pickles': 0.0006, 'bacon': 0.003,
          'lettuce': 0.0025}

SMASH = ['heel', 'pattycheese', 'pattycheese', 'onions', 'sauce', 'crown']
LABELS = {
    'crown': ('Pão brioche', 'Tostado na manteiga'),
    'sauce': ('Molho da casa', 'Receita secreta'),
    'onions': ('Cebola caramelizada', 'Na chapa, bem devagar'),
    'pattycheese': ('Smash + cheddar', '2 × 90g, crosta crocante'),
    'heel': ('Pão tostado', 'Base que segura tudo'),
}


def build_smash_burger(name='Burger', layers=SMASH, opts=None):
    opts = opts or {}
    root = empty(name)
    out = []
    z = 0.0
    for i, key in enumerate(layers):
        kw = dict(opts.get(i, {}))
        kw.setdefault('name', f'{name}_{key}_{i}')
        if key == 'pattycheese' and 'seed' not in kw:
            kw['seed'] = 3.0 + i * 2.3
        lr, h = BUILDERS[key](**kw)
        set_parent(lr, root)
        lr.location = (0, 0, z)
        out.append((key, lr, z, h))
        z += h - SETTLE.get(key, 0.0)
    return root, out
