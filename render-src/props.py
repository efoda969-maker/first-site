"""Combo props: fries in a branded carton, milkshake, sauce cups, and the
black ALL STAR box with a hinged lid."""
import bpy
import bmesh
import math
import os
import random
from mathutils import Vector, Matrix, noise

from lib import (hexc, NB, principled, empty, set_parent, mesh_object, add_subsurf, add_solidify,
                 add_bevel, lathe_bm, jitter_radial, link)
from burger import mat_sauce

TEX_DIR = os.environ.get('ASB_TEX', os.path.join(os.path.dirname(__file__), '..', 'build', 'tex'))


def image(name):
    path = os.path.join(TEX_DIR, name)
    img = bpy.data.images.load(path, check_existing=True)
    return img


def image_node(nb, img_name, vec, extension='CLIP'):
    nd = nb.n.new('ShaderNodeTexImage')
    nd.image = image(img_name)
    nd.extension = extension
    nd.interpolation = 'Cubic'
    nb.link(vec, nd.inputs['Vector'])
    return nd


def planar_uv(nb, axis_u, axis_v, u0, u1, v0, v1):
    """Object-space planar projection -> 0..1 vector."""
    sep = nb.sep(nb.texco('Object'))
    comb = nb.node('ShaderNodeCombineXYZ')
    nb.link(nb.maprange(sep.outputs[axis_u], u0, u1, 0, 1, clamp_=False), comb.inputs['X'])
    nb.link(nb.maprange(sep.outputs[axis_v], v0, v1, 0, 1, clamp_=False), comb.inputs['Y'])
    return comb.outputs[0]


# ----------------------------------------------------------------------------
# FRIES
# ----------------------------------------------------------------------------
def mat_fry():
    mat, nb = principled('Fry', rough=0.45, sss=0.35, sss_radius=(1, 0.75, 0.35), sss_scale=0.004,
                         coat=0.25, coat_rough=0.3)
    nz = nb.noise(scale=120.0, detail=3.0)
    big = nb.noise(scale=22.0, detail=2.0)
    col = nb.ramp(big.outputs['Fac'], [(0.3, hexc('#f4c55a')), (0.55, hexc('#eab043')), (0.75, hexc('#d48a26'))])
    spots = nb.maprange(nz.outputs['Fac'], 0.58, 0.75, 0.0, 0.5)
    col2 = nb.mix(spots, col.outputs['Color'], hexc('#a95d16'))
    nb.set('Base Color', col2)
    salt = nb.voronoi(scale=900.0, feature='F1')
    h = nb.math('ADD', nz.outputs['Fac'], nb.maprange(salt.outputs['Distance'], 0.0, 0.25, 0.6, 0.0))
    nb.set('Normal', nb.bump(h, strength=0.25, distance=0.0004))
    return mat


def mat_carton():
    mat, nb = principled('Carton', color='#0d0b0a', rough=0.5, spec=0.4)
    # front panel artwork (front faces -Y). UV from object coords of the front.
    vec = planar_uv(nb, 'X', 'Z', -0.05, 0.05, 0.0, 0.11 * 0.88)
    img = image_node(nb, 'fries_front.png', vec)
    nrm = nb.sep(nb.texco('Normal'))
    front = nb.maprange(nrm.outputs['Y'], -0.5, -0.8, 0.0, 1.0)
    inside = nb.n.new('ShaderNodeNewGeometry')
    back = nb.math('SUBTRACT', 1.0, inside.outputs['Backfacing'])
    m = nb.math('MULTIPLY', nb.math('MULTIPLY', front, img.outputs['Alpha']), back)
    red = hexc('#0d0b0a')
    col = nb.mix(m, red, img.outputs['Color'])
    inner = nb.mix(inside.outputs['Backfacing'], col, hexc('#1c1816'))
    nb.set('Base Color', inner)
    return mat


def build_fries(name='Fries', seed=21, count=34):
    root = empty(name)
    rnd = random.Random(seed)
    # carton: tapered tube, front edge dips in the middle
    nu, nv = 96, 16
    bw, bd = 0.074, 0.04      # bottom width / depth
    tw, td = 0.096, 0.058     # top width / depth
    H = 0.095
    bm = bmesh.new()

    def rect_point(u, w, d):
        # perimeter param u in [0,1): front(-Y) -> right -> back -> left
        per = 2 * (w + d)
        s = u * per
        if s < w:
            return Vector((-w / 2 + s, -d / 2, 0)), 'front', s / w
        s -= w
        if s < d:
            return Vector((w / 2, -d / 2 + s, 0)), 'side', 0
        s -= d
        if s < w:
            return Vector((w / 2 - s, d / 2, 0)), 'back', s / w
        s -= w
        return Vector((-w / 2, d / 2 - s, 0)), 'side', 0

    grid = []
    for j in range(nv + 1):
        v = j / nv
        row = []
        for i in range(nu):
            u = i / nu
            pb, side, t = rect_point(u, bw, bd)
            pt, _, _ = rect_point(u, tw, td)
            top = H
            if side == 'front':
                top = H - 0.026 * math.sin(t * math.pi) ** 1.5
            elif side == 'side':
                # sides blend from the lower front to the back height
                y = pt.y / (td / 2)
                top = H - 0.012 * (1 - y) / 2
            p = pb.lerp(pt, v)
            p.z = top * v
            row.append(bm.verts.new(p))
        grid.append(row)
    for j in range(nv):
        for i in range(nu):
            bm.faces.new((grid[j][i], grid[j][(i + 1) % nu], grid[j + 1][(i + 1) % nu], grid[j + 1][i]))
    bm.faces.new(list(reversed(grid[0])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = mesh_object(name + '_carton', bm, [mat_carton()], smooth_shade=True)
    add_solidify(ob, 0.0012, offset=-1.0)
    m = ob.modifiers.new('Bevel', 'BEVEL')
    m.width = 0.002
    m.segments = 2
    m.limit_method = 'ANGLE'
    m.angle_limit = math.radians(50)
    set_parent(ob, root)

    # fries
    fmat = mat_fry()
    fbm = bmesh.new()
    placed = 0
    while placed < count:
        x = rnd.uniform(-0.032, 0.032)
        y = rnd.uniform(-0.011, 0.016)
        L = rnd.uniform(0.075, 0.1)
        t = rnd.uniform(0.0075, 0.0095)
        g = bmesh.ops.create_cube(fbm, size=1.0)
        vs = g['verts']
        bmesh.ops.scale(fbm, vec=(t, t * rnd.uniform(0.9, 1.1), L), verts=vs)
        # slight bend
        for v in vs:
            v.co.x += 0.002 * (v.co.z / L) ** 2 * rnd.choice((-1, 1))
        tilt_x = rnd.uniform(-0.12, 0.16)
        tilt_y = rnd.uniform(-0.18, 0.18) + x * 3.0
        M = (Matrix.Translation((x, y, 0.03 + L / 2 + rnd.uniform(-0.012, 0.015)))
             @ Matrix.Rotation(tilt_y, 4, 'Y') @ Matrix.Rotation(tilt_x, 4, 'X')
             @ Matrix.Rotation(rnd.uniform(0, 3.14), 4, 'Z'))
        bmesh.ops.transform(fbm, matrix=M, verts=vs)
        placed += 1
    fo = mesh_object(name + '_fries', fbm, [fmat], smooth_shade=False)
    bv = fo.modifiers.new('Bevel', 'BEVEL')
    bv.width = 0.0016
    bv.segments = 3
    for p in fo.data.polygons:
        p.use_smooth = True
    set_parent(fo, root)
    return root


# ----------------------------------------------------------------------------
# MILKSHAKE
# ----------------------------------------------------------------------------
def build_shake(name='Shake', seed=31):
    root = empty(name)
    rb, rt, H = 0.028, 0.038, 0.088
    # clear cup (thin shell)
    prof = [(0, 0.0), (rb - 0.004, 0.0), (rb, 0.003), (rt, H), (rt - 0.0012, H), (rb - 0.0012, 0.0042),
            (rb - 0.005, 0.0012), (0, 0.0012)]
    bm, _ = lathe_bm(prof, 96)
    glass, nb = principled('CupPlastic', color='#ffffff', rough=0.04, trans=1.0, ior=1.45)
    cup = mesh_object(name + '_cup', bm, [glass])
    add_subsurf(cup, 1)
    set_parent(cup, root)
    # rim
    bpy.ops.mesh.primitive_torus_add(major_radius=rt - 0.0004, minor_radius=0.0011, major_segments=96, minor_segments=8,
                                     location=(0, 0, H))
    rim = bpy.context.active_object
    rim.name = name + '_rim'
    rim.data.materials.append(glass)
    for p in rim.data.polygons:
        p.use_smooth = True
    set_parent(rim, root)

    # shake liquid (chocolate) - slightly smaller than the cup
    def r_at(z):
        return rb + (rt - rb) * (z / H)
    lz = H - 0.004
    lprof = [(0, 0.0016), (r_at(0.002) - 0.0018, 0.0016), (r_at(lz) - 0.0018, lz), (0, lz)]
    lbm, _ = lathe_bm(lprof, 96)
    lmat, lnb = principled('ShakeCookie', rough=0.45, sss=0.4, sss_radius=(1, 0.85, 0.7), sss_scale=0.003)
    nz = lnb.noise(scale=40.0, detail=3.0)
    sepz = lnb.sep(lnb.texco('Object'))
    ang = lnb.math('ARCTAN2', sepz.outputs['Y'], sepz.outputs['X'])
    # chocolate drizzle running down the inside of the cup
    wav = lnb.math('ADD', lnb.math('MULTIPLY', ang, 5.0),
                   lnb.math('MULTIPLY', lnb.math('SINE', lnb.math('MULTIPLY', sepz.outputs['Z'], 90.0)), 0.35))
    wav = lnb.math('ADD', wav, lnb.math('MULTIPLY', nz.outputs['Fac'], 1.2))
    stripe = lnb.maprange(lnb.math('SINE', wav), 0.55, 0.8)
    lower = lnb.maprange(sepz.outputs['Z'], 0.095, 0.02)
    drizzle = lnb.math('MULTIPLY', stripe, lower)
    base = lnb.ramp(nz.outputs['Fac'], [(0.3, hexc('#e6d6bd')), (0.7, hexc('#d6c1a0'))])
    specks = lnb.voronoi(scale=380.0, feature='F1')
    sm = lnb.maprange(specks.outputs['Distance'], 0.1, 0.04, 0.0, 1.0)
    c1 = lnb.mix(sm, base.outputs['Color'], hexc('#24150c'))
    lnb.set('Base Color', lnb.mix(drizzle, c1, hexc('#3a1d0c')))
    liq = mesh_object(name + '_liquid', lbm, [lmat])
    add_subsurf(liq, 1)
    set_parent(liq, root)

    # branded band (black sleeve) wrapped around the cup
    bz0, bz1 = 0.022, 0.07
    sprof = [(r_at(bz0) + 0.0007, bz0), (r_at(bz1) + 0.0007, bz1)]
    sbm = bmesh.new()
    segs = 128
    uvl = sbm.loops.layers.uv.new()
    rings = []
    for (r, z) in sprof:
        rings.append([sbm.verts.new((r * math.cos(2 * math.pi * i / segs), r * math.sin(2 * math.pi * i / segs), z))
                      for i in range(segs)])
    for i in range(segs):
        f = sbm.faces.new((rings[0][i], rings[0][(i + 1) % segs], rings[1][(i + 1) % segs], rings[1][i]))
        u0, u1 = i / segs, (i + 1) / segs
        for loop, uv in zip(f.loops, ((u0, 0), (u1, 0), (u1, 1), (u0, 1))):
            loop[uvl].uv = uv
    bmat, bnb = principled('CupDecal', color='#0d0b0a', rough=0.3)
    uvn = bnb.texco('UV')
    mapping = bnb.node('ShaderNodeMapping')
    mapping.inputs['Location'].default_value = (0.37, 0, 0)
    bnb.link(uvn, mapping.inputs['Vector'])
    img = image_node(bnb, 'cup_band.png', mapping.outputs['Vector'], extension='REPEAT')
    bnb.set('Base Color', img.outputs['Color'])
    bnb.set('Alpha', img.outputs['Alpha'])
    band = mesh_object(name + '_band', sbm, [bmat])
    add_solidify(band, 0.0006, offset=1.0)
    set_parent(band, root)

    # whipped cream swirl: star-profile tube along a shrinking helix
    cream, cnb = principled('WhippedCream', color='#fbf5ea', rough=0.5, sss=0.8, sss_radius=(1, 0.95, 0.85),
                            sss_scale=0.004)
    cn = cnb.noise(scale=260.0, detail=2.0)
    cnb.set('Normal', cnb.bump(cn.outputs['Fac'], strength=0.15, distance=0.0004))
    crumbs = cnb.voronoi(scale=260.0, feature='F1')
    cm = cnb.maprange(crumbs.outputs['Distance'], 0.12, 0.06, 0.0, 1.0)
    cnb.set('Base Color', cnb.mix(cm, hexc('#fbf5ea'), hexc('#2a170c')))
    cbm = bmesh.new()
    steps, ring_n = 240, 16
    turns = 2.6
    rings = []
    for k in range(steps + 1):
        t = k / steps
        a = t * turns * 2 * math.pi
        R = (rt - 0.012) * (1 - t) ** 0.9
        z = H - 0.006 + 0.034 * t ** 0.85
        tube = 0.0115 * (1 - 0.65 * t) + 0.002
        c = Vector((R * math.cos(a), R * math.sin(a), z))
        tangent = Vector((-math.sin(a), math.cos(a), 0.12)).normalized()
        nrm = Vector((math.cos(a), math.sin(a), 0))
        bin_ = tangent.cross(nrm).normalized()
        ring = []
        for q in range(ring_n):
            ph = 2 * math.pi * q / ring_n
            rr = tube * (1 + 0.16 * math.cos(8 * ph + t * 6))
            p = c + (nrm * math.cos(ph) + bin_ * math.sin(ph)) * rr
            ring.append(cbm.verts.new(p))
        rings.append(ring)
    for k in range(steps):
        for q in range(ring_n):
            cbm.faces.new((rings[k][q], rings[k][(q + 1) % ring_n], rings[k + 1][(q + 1) % ring_n], rings[k + 1][q]))
    # caps
    cbm.faces.new(list(reversed(rings[0])))
    tip = cbm.verts.new(rings[-1][0].co * 0 + sum((v.co for v in rings[-1]), Vector()) / ring_n + Vector((0, 0, 0.004)))
    for q in range(ring_n):
        cbm.faces.new((rings[-1][q], rings[-1][(q + 1) % ring_n], tip))
    bmesh.ops.recalc_face_normals(cbm, faces=cbm.faces)
    co = mesh_object(name + '_cream', cbm, [cream])
    add_subsurf(co, 1)
    set_parent(co, root)

    # cherry
    cmat, chb = principled('Cherry', color='#9c0a12', rough=0.12, sss=0.3, sss_radius=(1, 0.2, 0.2),
                           sss_scale=0.003, coat=0.8, coat_rough=0.05)
    top_z = H - 0.006 + 0.034 + 0.005
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.0105, segments=32, ring_count=16, location=(0.002, -0.002, top_z + 0.008))
    ch = bpy.context.active_object
    ch.name = name + '_cherry'
    ch.scale = (1, 1, 0.92)
    ch.data.materials.append(cmat)
    for p in ch.data.polygons:
        p.use_smooth = True
    set_parent(ch, root)
    # stem
    stem_mat, _ = principled('Stem', color='#5a3a14', rough=0.5)
    curve = bpy.data.curves.new(name + '_stemc', 'CURVE')
    curve.dimensions = '3D'
    curve.bevel_depth = 0.0008
    sp = curve.splines.new('BEZIER')
    sp.bezier_points.add(1)
    p0, p1 = sp.bezier_points
    p0.co = (0.002, -0.002, top_z + 0.016)
    p0.handle_left = p0.co
    p0.handle_right = (0.004, -0.002, top_z + 0.028)
    p1.co = (0.012, 0.0, top_z + 0.034)
    p1.handle_left = (0.008, -0.001, top_z + 0.032)
    p1.handle_right = p1.co
    stem = bpy.data.objects.new(name + '_stem', curve)
    link(stem)
    curve.materials.append(stem_mat)
    set_parent(stem, root)

    # straw (red & cream stripes)
    smat, snb = principled('Straw', rough=0.2, coat=0.5, coat_rough=0.1)
    sepo = snb.sep(snb.texco('Object'))
    ang = snb.math('ARCTAN2', sepo.outputs['Y'], sepo.outputs['X'])
    st = snb.math('SINE', snb.math('ADD', snb.math('MULTIPLY', sepo.outputs['Z'], 260.0), ang))
    stm = snb.maprange(st, -0.15, 0.15)
    snb.set('Base Color', snb.mix(stm, hexc('#f3e9d2'), hexc('#d62718')))
    bpy.ops.mesh.primitive_cylinder_add(radius=0.0036, depth=0.14, vertices=32, location=(0, 0, 0))
    straw = bpy.context.active_object
    straw.name = name + '_straw'
    straw.data.materials.append(smat)
    # pivot at base of straw
    straw.data.transform(Matrix.Translation((0, 0, 0.07)))
    straw.location = (-0.012, 0.01, 0.01)
    straw.rotation_euler = (math.radians(-12), math.radians(-14), 0)
    for p in straw.data.polygons:
        p.use_smooth = True
    sol = straw.modifiers.new('Solidify', 'SOLIDIFY')
    sol.thickness = 0.0004
    set_parent(straw, root)
    return root


# ----------------------------------------------------------------------------
# SAUCE CUPS
# ----------------------------------------------------------------------------
def build_sauce_cup(name='Cup', color='#b3140c', seed=41):
    root = empty(name)
    rb, rt, H = 0.019, 0.026, 0.026
    segs = 120
    prof = [(0, 0), (rb, 0), (rt, H)]
    bm, rings = lathe_bm(prof, segs)
    for v in bm.verts:
        a = math.atan2(v.co.y, v.co.x)
        rr = math.hypot(v.co.x, v.co.y)
        if rr > 1e-6 and v.co.z > 0.0005 or rr > rb * 0.98:
            k = 1 + 0.028 * math.sin(a * 36) * min(1.0, v.co.z / H + 0.3)
            v.co.x *= k
            v.co.y *= k
    paper, pnb = principled('CupPaper', color='#f1eee6', rough=0.6, sss=0.2, sss_radius=(1, 1, 1), sss_scale=0.002)
    ob = mesh_object(name + '_paper', bm, [paper])
    add_solidify(ob, 0.0006, offset=-1.0)
    add_subsurf(ob, 1)
    set_parent(ob, root)
    # sauce surface: a domed dollop with a soft swirl peak
    sbm = bmesh.new()
    rings_n = 18
    center = sbm.verts.new((0, 0, H - 0.003 + 0.007))
    grid = []
    for k in range(1, rings_n + 1):
        rho = k / rings_n
        row = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            r = rho * (rt - 0.0012)
            z = H - 0.0035 + 0.007 * (1 - rho ** 2) ** 1.5 + 0.0012 * math.sin(3 * a + rho * 9) * (1 - rho) + 0.0006 * rho ** 8
            row.append(sbm.verts.new((r * math.cos(a), r * math.sin(a), z)))
        grid.append(row)
    for i in range(segs):
        sbm.faces.new((center, grid[0][i], grid[0][(i + 1) % segs]))
    for k in range(rings_n - 1):
        for i in range(segs):
            sbm.faces.new((grid[k][i], grid[k][(i + 1) % segs], grid[k + 1][(i + 1) % segs], grid[k + 1][i]))
    # close underneath
    bot = sbm.verts.new((0, 0, H - 0.008))
    for i in range(segs):
        sbm.faces.new((grid[-1][(i + 1) % segs], grid[-1][i], bot))
    bmesh.ops.recalc_face_normals(sbm, faces=sbm.faces)
    so = mesh_object(name + '_sauce', sbm, [mat_sauce(color, name='Sauce_' + color)])
    add_subsurf(so, 1)
    set_parent(so, root)
    return root


# ----------------------------------------------------------------------------
# BOX
# ----------------------------------------------------------------------------
BOX_W, BOX_D, BOX_H = 0.48, 0.32, 0.15
LID_SKIRT = 0.045


def mat_box_outer(tex_lid='box_lid.png', tex_front='box_front.png', is_lid=False, lid_dims=(0.492, 0.332)):
    mat, nb = principled('BoxOuterLid' if is_lid else 'BoxOuter', color='#0d0b0a', rough=0.55, spec=0.35,
                         sheen=0.08, sheen_tint=(0.8, 0.8, 0.8, 1))
    nrm = nb.sep(nb.texco('Normal'))
    black = hexc('#0b0a09')
    if is_lid:
        # lid top: local coords centred, top at z = 0 .. projection on x/y
        vec = planar_uv(nb, 'X', 'Y', -lid_dims[0] / 2, lid_dims[0] / 2, -lid_dims[1], 0.0)
        img = image_node(nb, tex_lid, vec)
        top = nb.maprange(nrm.outputs['Z'], 0.6, 0.85)
        m = nb.math('MULTIPLY', top, 1.0)
        col = nb.mix(m, black, img.outputs['Color'])
        # foil-ish print: printed areas a bit glossier
        lum = nb.math('MULTIPLY', m, nb.maprange(img.outputs['Color'], 0.05, 0.4))
    else:
        vec = planar_uv(nb, 'X', 'Z', -BOX_W / 2, BOX_W / 2, 0.0, BOX_H)
        img = image_node(nb, tex_front, vec)
        front = nb.maprange(nrm.outputs['Y'], -0.6, -0.85)
        col = nb.mix(front, black, img.outputs['Color'])
        lum = nb.math('MULTIPLY', front, nb.maprange(img.outputs['Color'], 0.05, 0.4))
    nb.set('Base Color', col)
    nb.set('Roughness', nb.maprange(lum, 0, 1, 0.55, 0.28))
    fib = nb.noise(scale=500.0, detail=2.0)
    nb.set('Normal', nb.bump(fib.outputs['Fac'], strength=0.04, distance=0.0003))
    return mat


def mat_box_inner(printed=None, lid_dims=(0.492, 0.332)):
    mat, nb = principled('BoxInnerPrinted' if printed else 'BoxInner', color='#151312', rough=0.7)
    fib = nb.noise(scale=400.0, detail=2.0)
    nb.set('Normal', nb.bump(fib.outputs['Fac'], strength=0.05, distance=0.0003))
    if printed:
        # underside of the lid: u = x, v = towards the front edge (reads upright when the lid is open)
        sep = nb.sep(nb.texco('Object'))
        comb = nb.node('ShaderNodeCombineXYZ')
        nb.link(nb.maprange(sep.outputs['X'], -lid_dims[0] / 2, lid_dims[0] / 2, 0, 1, clamp_=False), comb.inputs['X'])
        nb.link(nb.maprange(sep.outputs['Y'], 0.0, -lid_dims[1], 0, 1, clamp_=False), comb.inputs['Y'])
        img = image_node(nb, printed, comb.outputs[0])
        nrm = nb.sep(nb.texco('Normal'))
        under = nb.maprange(nrm.outputs['Z'], -0.6, -0.85)
        col = nb.mix(under, hexc('#151312'), img.outputs['Color'])
        nb.set('Base Color', col)
    return mat


def _open_box_bm(w, d, h):
    """Open-top box (5 faces) centred on x, front at y=-d/2, bottom at z=0."""
    bm = bmesh.new()
    x0, x1, y0, y1 = -w / 2, w / 2, -d / 2, d / 2
    vb = [bm.verts.new(p) for p in ((x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0))]
    vt = [bm.verts.new(p) for p in ((x0, y0, h), (x1, y0, h), (x1, y1, h), (x0, y1, h))]
    bm.faces.new(list(reversed(vb)))
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((vb[i], vb[j], vt[j], vt[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # open box: make normals point outward explicitly (recalc may flip for non-manifold)
    for f in bm.faces:
        c = f.calc_center_median()
        out = Vector((c.x, c.y, c.z - h / 2))
        if f.normal.dot(out) < 0:
            f.normal_flip()
    return bm


def build_box(name='Box'):
    root = empty(name)
    outer = mat_box_outer()
    inner = mat_box_inner()
    bm = _open_box_bm(BOX_W, BOX_D, BOX_H)
    base = mesh_object(name + '_base', bm, [outer, inner], smooth_shade=False)
    sol = base.modifiers.new('Solidify', 'SOLIDIFY')
    sol.thickness = 0.004
    sol.offset = -1.0
    sol.material_offset = 1
    sol.material_offset_rim = 0
    bev = base.modifiers.new('Bevel', 'BEVEL')
    bev.width = 0.0025
    bev.segments = 3
    bev.limit_method = 'ANGLE'
    bev.harden_normals = False
    set_parent(base, root)

    # hinge at the back top edge; lid geometry hangs from it, closed = rotation 0,
    # opening = negative rotation around X
    hinge = empty(name + '_hinge', (0, BOX_D / 2 + 0.006, BOX_H + 0.0045), parent=root)
    lw, ld = BOX_W + 0.012, BOX_D + 0.012
    lbm = bmesh.new()
    yb, yf = 0.0, -ld
    top = [lbm.verts.new(p) for p in ((-lw / 2, yf, 0), (lw / 2, yf, 0), (lw / 2, yb, 0), (-lw / 2, yb, 0))]
    bot = [lbm.verts.new((v.co.x, v.co.y, -LID_SKIRT)) for v in top]
    lbm.faces.new(top)
    for i in range(4):
        j = (i + 1) % 4
        lbm.faces.new((bot[i], bot[j], top[j], top[i]))
    cx, cy = 0.0, -ld / 2
    for f in lbm.faces:
        c = f.calc_center_median()
        out = Vector((c.x - cx, c.y - cy, c.z + LID_SKIRT / 2))
        if f.normal.dot(out) < 0:
            f.normal_flip()
    lid = mesh_object(name + '_lid', lbm, [mat_box_outer(is_lid=True, lid_dims=(lw, ld)),
                                           mat_box_inner('box_lid_inner.png', (lw, ld))], smooth_shade=False)
    sol = lid.modifiers.new('Solidify', 'SOLIDIFY')
    sol.thickness = 0.004
    sol.offset = -1.0
    sol.material_offset = 1
    bev = lid.modifiers.new('Bevel', 'BEVEL')
    bev.width = 0.0025
    bev.segments = 3
    bev.limit_method = 'ANGLE'
    set_parent(lid, hinge)

    # cardboard dividers: burger bay on the left, fries + shake behind, sauces in front
    x_in = BOX_W / 2 - 0.005
    for (cx, cy, sx, sy, sz) in ((-0.045, 0.0, 0.003, BOX_D - 0.01, 0.085),
                                 ((-0.045 + x_in) / 2, -0.035, x_in + 0.045, 0.003, 0.06)):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, cy, sz / 2))
        d = bpy.context.active_object
        d.name = name + '_divider'
        d.scale = (sx, sy, sz)
        d.data.materials.append(inner)
        set_parent(d, root)
    return root, hinge
