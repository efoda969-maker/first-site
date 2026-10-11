"""Shared helpers for the ALL STAR BURGERS Blender scenes.

Run inside Blender (4.5 LTS):  blender -b -P render-src/sequence.py -- [options]
Everything is procedural: geometry is built with bmesh, materials with nodes.
"""
import bpy
import bmesh
import math
import random
from mathutils import Vector, Matrix, noise
from mathutils.bvhtree import BVHTree


# ----------------------------------------------------------------------------
# colour helpers
# ----------------------------------------------------------------------------
def _s2l(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hexc(h, a=1.0):
    """'#rrggbb' (sRGB) -> linear RGBA tuple for shader sockets."""
    h = h.lstrip('#')
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return (_s2l(r), _s2l(g), _s2l(b), a)


def lerp(a, b, t):
    return a + (b - a) * t


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def smooth(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def ease_in_out(t):
    t = clamp(t)
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in(t):
    t = clamp(t)
    return t * t * t


def ease_out_back(t, s=1.4):
    t = clamp(t)
    c3 = s + 1
    return 1 + c3 * (t - 1) ** 3 + s * (t - 1) ** 2


def seg(f, a, b):
    """0..1 progress of frame f within [a, b]."""
    if b <= a:
        return 1.0 if f >= b else 0.0
    return clamp((f - a) / (b - a))


# ----------------------------------------------------------------------------
# scene / object helpers
# ----------------------------------------------------------------------------
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    random.seed(7)


def link(ob, coll=None):
    (coll or bpy.context.scene.collection).objects.link(ob)
    return ob


def empty(name, loc=(0, 0, 0), parent=None):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_size = 0.02
    ob.location = loc
    link(ob)
    if parent:
        set_parent(ob, parent)
    return ob


def set_parent(child, parent):
    child.parent = parent
    child.matrix_parent_inverse = Matrix.Identity(4)


def mesh_object(name, bm, mats=(), smooth_shade=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    if smooth_shade:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    link(ob)
    return ob


def add_subsurf(ob, levels=2, render_levels=None):
    m = ob.modifiers.new('Subsurf', 'SUBSURF')
    m.levels = levels
    m.render_levels = render_levels if render_levels is not None else levels
    return m


def add_solidify(ob, thickness, offset=-1.0):
    m = ob.modifiers.new('Solidify', 'SOLIDIFY')
    m.thickness = thickness
    m.offset = offset
    m.use_even_offset = True
    return m


def add_bevel(ob, width, segments=3):
    m = ob.modifiers.new('Bevel', 'BEVEL')
    m.width = width
    m.segments = segments
    m.limit_method = 'ANGLE'
    return m


def lathe_bm(profile, segs=96):
    """Revolve (r, z) profile points around Z. Points with r == 0 become poles.
    Returns (bm, rings) where rings is a list of vertex lists."""
    bm = bmesh.new()
    rings = []
    for (r, z) in profile:
        if r < 1e-7:
            rings.append([bm.verts.new((0, 0, z))])
        else:
            ring = []
            for i in range(segs):
                a = 2 * math.pi * i / segs
                ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z)))
            rings.append(ring)
    for k in range(len(rings) - 1):
        A, B = rings[k], rings[k + 1]
        if len(A) == 1 and len(B) == 1:
            continue
        if len(A) == 1:
            for i in range(segs):
                bm.faces.new((A[0], B[i], B[(i + 1) % segs]))
        elif len(B) == 1:
            for i in range(segs):
                bm.faces.new((A[i], A[(i + 1) % segs], B[0]))
        else:
            for i in range(segs):
                bm.faces.new((A[i], A[(i + 1) % segs], B[(i + 1) % segs], B[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm, rings


def jitter_radial(bm, amp, freq, seed=0.0, zamp=0.0, axis_scale=(1, 1, 1)):
    """Organic irregularity: push verts radially with 3D noise."""
    off = Vector((seed * 13.1, seed * 7.7, seed * 3.3))
    for v in bm.verts:
        p = Vector((v.co.x * axis_scale[0], v.co.y * axis_scale[1], v.co.z * axis_scale[2]))
        n = noise.noise(p * freq + off)
        rr = Vector((v.co.x, v.co.y, 0))
        if rr.length > 1e-6:
            v.co += rr.normalized() * n * amp
        if zamp:
            v.co.z += noise.noise(p * freq * 1.3 + off + Vector((5, 5, 5))) * zamp


def assign_mat_by(ob, index, pred):
    """Set material index for polygons where pred(center, normal) is True."""
    for p in ob.data.polygons:
        if pred(p.center, p.normal):
            p.material_index = index


def bvh_of(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    return BVHTree.FromObject(ob, dg)


# ----------------------------------------------------------------------------
# node helpers
# ----------------------------------------------------------------------------
class NB:
    """Tiny node-builder to keep material code readable."""

    def __init__(self, mat):
        self.mat = mat
        self.nt = mat.node_tree
        self.n = self.nt.nodes
        self.l = self.nt.links
        self.bsdf = self.n.get('Principled BSDF')
        self.out = self.n.get('Material Output')

    def node(self, kind, **props):
        nd = self.n.new(kind)
        for k, v in props.items():
            setattr(nd, k, v)
        return nd

    def link(self, a, b):
        self.l.new(a, b)

    def val(self, v):
        nd = self.n.new('ShaderNodeValue')
        nd.outputs[0].default_value = v
        return nd.outputs[0]

    def texco(self, which='Object'):
        if not hasattr(self, '_tc'):
            self._tc = self.n.new('ShaderNodeTexCoord')
        return self._tc.outputs[which]

    def noise(self, scale=5.0, detail=4.0, rough=0.5, vec=None, dim='3D', w=0.0, distortion=0.0):
        nd = self.n.new('ShaderNodeTexNoise')
        nd.noise_dimensions = dim
        nd.inputs['Scale'].default_value = scale
        nd.inputs['Detail'].default_value = detail
        nd.inputs['Roughness'].default_value = rough
        nd.inputs['Distortion'].default_value = distortion
        if dim in ('4D', '1D'):
            nd.inputs['W'].default_value = w
        self.link(vec if vec is not None else self.texco('Object'), nd.inputs['Vector'])
        return nd

    def voronoi(self, scale=5.0, vec=None, feature='F1', rnd=1.0):
        nd = self.n.new('ShaderNodeTexVoronoi')
        nd.feature = feature
        nd.inputs['Scale'].default_value = scale
        nd.inputs['Randomness'].default_value = rnd
        self.link(vec if vec is not None else self.texco('Object'), nd.inputs['Vector'])
        return nd

    def ramp(self, inp, stops, interp='LINEAR'):
        nd = self.n.new('ShaderNodeValToRGB')
        cr = nd.color_ramp
        cr.interpolation = interp
        # stops: list of (pos, rgba)
        while len(cr.elements) < len(stops):
            cr.elements.new(0.5)
        for el, (pos, col) in zip(cr.elements, stops):
            el.position = pos
            el.color = col
        self.link(inp, nd.inputs['Fac'])
        return nd

    def maprange(self, inp, a, b, c=0.0, d=1.0, clamp_=True):
        nd = self.n.new('ShaderNodeMapRange')
        nd.clamp = clamp_
        nd.inputs['From Min'].default_value = a
        nd.inputs['From Max'].default_value = b
        nd.inputs['To Min'].default_value = c
        nd.inputs['To Max'].default_value = d
        self.link(inp, nd.inputs['Value'])
        return nd.outputs['Result']

    def math(self, op, a, b=None, clamp_=False):
        nd = self.n.new('ShaderNodeMath')
        nd.operation = op
        nd.use_clamp = clamp_
        for i, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                nd.inputs[i].default_value = x
            else:
                self.link(x, nd.inputs[i])
        return nd.outputs[0]

    def mix(self, fac, a, b, blend='MIX'):
        nd = self.n.new('ShaderNodeMix')
        nd.data_type = 'RGBA'
        nd.blend_type = blend
        for sock, x in ((nd.inputs[0], fac), (nd.inputs[6], a), (nd.inputs[7], b)):
            if isinstance(x, (int, float)):
                sock.default_value = x
            elif isinstance(x, tuple):
                sock.default_value = x
            else:
                self.link(x, sock)
        return nd.outputs[2]

    def sep(self, vec):
        nd = self.n.new('ShaderNodeSeparateXYZ')
        self.link(vec, nd.inputs[0])
        return nd

    def bump(self, height, strength=0.2, distance=0.001, normal=None):
        nd = self.n.new('ShaderNodeBump')
        nd.inputs['Strength'].default_value = strength
        nd.inputs['Distance'].default_value = distance
        self.link(height, nd.inputs['Height'])
        if normal is not None:
            self.link(normal, nd.inputs['Normal'])
        return nd.outputs['Normal']

    def set(self, name, value):
        sock = self.bsdf.inputs[name]
        if isinstance(value, (int, float, tuple)):
            sock.default_value = value
        else:
            self.link(value, sock)


def principled(name, color='#ffffff', rough=0.5, **kw):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nb = NB(mat)
    nb.bsdf.subsurface_method = 'BURLEY'
    nb.set('Base Color', hexc(color) if isinstance(color, str) else color)
    nb.set('Roughness', rough)
    mapping = {
        'sss': 'Subsurface Weight', 'sss_radius': 'Subsurface Radius', 'sss_scale': 'Subsurface Scale',
        'coat': 'Coat Weight', 'coat_rough': 'Coat Roughness', 'spec': 'Specular IOR Level',
        'metal': 'Metallic', 'trans': 'Transmission Weight', 'ior': 'IOR', 'sheen': 'Sheen Weight',
        'sheen_tint': 'Sheen Tint', 'alpha': 'Alpha',
    }
    for k, v in kw.items():
        nb.set(mapping[k], v)
    return mat, nb
