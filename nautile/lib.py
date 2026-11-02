"""NAUTILE — procedural helpers: geometry generators + shader-node DSL (Blender 5.x / bpy)."""
import math
import numpy as np
import bpy
import bmesh
from mathutils import Vector, Matrix

TAU = 2 * math.pi


# ----------------------------------------------------------------------------- mesh
def make_mesh(name, verts, faces, uvs=None, mat_idx=None, smooth=True, sharp_angle=None,
              merge=1e-7, collection=None):
    """verts: (N,3) array; faces: list of index tuples; uvs: optional (N,2) per-vertex."""
    me = bpy.data.meshes.new(name)
    verts = np.asarray(verts, dtype=float)
    me.from_pydata(verts.tolist(), [], [tuple(int(i) for i in f) for f in faces])
    if uvs is not None:
        uvs = np.asarray(uvs, dtype=float)
        uvl = me.uv_layers.new(name="UVMap")
        vi = np.zeros(len(me.loops), dtype=np.int32)
        me.loops.foreach_get("vertex_index", vi)
        uvl.data.foreach_set("uv", uvs[vi].ravel())
    if mat_idx is not None:
        me.polygons.foreach_set("material_index", np.asarray(mat_idx, dtype=np.int32))
    if merge:
        bm = bmesh.new(); bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge)
        bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=merge * 0.1)
        bm.to_mesh(me); bm.free()
    me.validate()
    if smooth:
        me.shade_smooth()
        if sharp_angle is not None:
            me.set_sharp_from_angle(angle=math.radians(sharp_angle))
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    return ob


class MeshBuilder:
    """Accumulate several parts into a single mesh."""
    def __init__(self):
        self.v, self.f, self.uv, self.m = [], [], [], []
        self.n = 0

    def add(self, verts, faces, uvs=None, mat=0):
        verts = np.asarray(verts, dtype=float).reshape(-1, 3)
        self.v.append(verts)
        self.uv.append(np.zeros((len(verts), 2)) if uvs is None else np.asarray(uvs, float).reshape(-1, 2))
        self.f += [tuple(i + self.n for i in f) for f in faces]
        self.m += [mat] * len(faces)
        self.n += len(verts)
        return self

    def add_part(self, part, mat=0, xf=None):
        v, f, uv = part
        if xf is not None:
            v = transform(v, xf)
        return self.add(v, f, uv, mat)

    def build(self, name, **kw):
        return make_mesh(name, np.vstack(self.v), self.f, uvs=np.vstack(self.uv), mat_idx=self.m, **kw)


def transform(v, M):
    v = np.asarray(v, float)
    M = np.array(M)
    return v @ M[:3, :3].T + M[:3, 3]


def grid_faces(nu, nv, wrap_u=False, wrap_v=False, flip=False, offset=0):
    """Quad faces on a (nu x nv) vertex grid, index = i*nv + j."""
    F = []
    iu = nu if wrap_u else nu - 1
    jv = nv if wrap_v else nv - 1
    for i in range(iu):
        i2 = (i + 1) % nu
        for j in range(jv):
            j2 = (j + 1) % nv
            a, b, c, d = i * nv + j, i * nv + j2, i2 * nv + j2, i2 * nv + j
            q = (a, b, c, d) if not flip else (d, c, b, a)
            F.append(tuple(x + offset for x in q))
    return F


def revolve(profile, segs=64, angle0=0.0, angle=TAU, flip=False):
    """Lathe a (r,z) polyline around Z. Returns (verts, faces, uvs)."""
    prof = np.asarray(profile, float)
    full = abs(angle - TAU) < 1e-9
    na = segs if full else segs + 1
    a = angle0 + np.arange(na) * (angle / segs)
    V = np.zeros((na, len(prof), 3))
    V[:, :, 0] = np.cos(a)[:, None] * prof[None, :, 0]
    V[:, :, 1] = np.sin(a)[:, None] * prof[None, :, 0]
    V[:, :, 2] = prof[None, :, 1]
    L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(prof, axis=0), axis=1))])
    UV = np.zeros((na, len(prof), 2))
    UV[:, :, 0] = (np.arange(na) / segs)[:, None]
    UV[:, :, 1] = (L / max(L[-1], 1e-9))[None, :]
    F = grid_faces(na, len(prof), wrap_u=full, flip=not flip)
    return V.reshape(-1, 3), F, UV.reshape(-1, 2)


def ring_solid(outer, inner, z0, z1, closed=True):
    """Solid between two same-count closed 2D loops (outer, inner), extruded z0..z1."""
    outer = np.asarray(outer, float); inner = np.asarray(inner, float)
    n = len(outer)
    V = []
    for loop, z in ((outer, z1), (inner, z1), (inner, z0), (outer, z0)):
        V.append(np.c_[loop, np.full(n, z)])
    V = np.vstack(V)
    F = []
    for k in range(4):
        k2 = (k + 1) % 4
        for i in range(n if closed else n - 1):
            i2 = (i + 1) % n
            F.append((k * n + i, k * n + i2, k2 * n + i2, k2 * n + i))
    UV = np.c_[V[:, 0], V[:, 1]]
    return V, F, UV


def polygon_solid(loop, z0, z1):
    """Extrude a simple closed 2D polygon (CCW) into a prism."""
    loop = np.asarray(loop, float); n = len(loop)
    V = np.vstack([np.c_[loop, np.full(n, z1)], np.c_[loop, np.full(n, z0)]])
    F = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    for i in range(n):
        i2 = (i + 1) % n
        F.append((i2, i, n + i, n + i2))
    return V, F, np.c_[V[:, 0], V[:, 1]]


def strip_solid(path, width, z0, z1, taper=None):
    """Planar ribbon of given width following a 2D path, extruded in z."""
    path = np.asarray(path, float)
    d = np.gradient(path, axis=0)
    d /= np.linalg.norm(d, axis=1)[:, None]
    nrm = np.c_[-d[:, 1], d[:, 0]]
    w = np.full(len(path), width) if taper is None else np.asarray(taper) * width
    left = path + nrm * (w[:, None] / 2)
    right = path - nrm * (w[:, None] / 2)
    loop = np.vstack([right, left[::-1]])
    return polygon_solid(loop, z0, z1)


def circle(r, n=64, a0=0.0):
    a = a0 + np.arange(n) * TAU / n
    return np.c_[np.cos(a) * r, np.sin(a) * r]


def sweep(path, frames_n, frames_b, profile, closed_profile=True, closed_path=False, scale=None):
    """Sweep a 2D profile (p,q) along a 3D path: P = path + p*N + q*B."""
    path = np.asarray(path, float); prof = np.asarray(profile, float)
    s = np.ones(len(path)) if scale is None else np.asarray(scale)
    V = (path[:, None, :] + s[:, None, None] * (prof[None, :, 0, None] * frames_n[:, None, :]
                                               + prof[None, :, 1, None] * frames_b[:, None, :]))
    L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
    UV = np.zeros(V.shape[:2] + (2,))
    UV[:, :, 0] = L[:, None]
    UV[:, :, 1] = (np.arange(len(prof)) / len(prof))[None, :]
    F = grid_faces(len(path), len(prof), wrap_u=closed_path, wrap_v=closed_profile)
    return V.reshape(-1, 3), F, UV.reshape(-1, 2)


def tube_frames(path, up=(0, 0, 1)):
    path = np.asarray(path, float)
    T = np.gradient(path, axis=0)
    T /= np.linalg.norm(T, axis=1)[:, None]
    up = np.asarray(up, float)
    N = np.cross(T, up)
    bad = np.linalg.norm(N, axis=1) < 1e-6
    N[bad] = np.cross(T[bad], [1, 0, 0])
    N /= np.linalg.norm(N, axis=1)[:, None]
    B = np.cross(N, T)
    return T, N, B


def gear_part(teeth, r_root, r_tip, z0, z1, r_rim_in=None, spokes=5, r_hub=None, r_bore=None,
              spoke_w=None, curve=0.5, samples=12):
    """Watch-style wheel: toothed rim + curved spokes + hub. Returns (v,f,uv)."""
    mb = MeshBuilder()
    M = teeth * samples
    a = np.arange(M) * TAU / M
    ph = (np.arange(M) % samples) / samples
    prof = np.interp(ph, [0, .18, .30, .36, .64, .70, .82, 1.0], [0, 0, .78, 1, 1, .78, 0, 0])
    ro = r_root + (r_tip - r_root) * prof
    outer = np.c_[np.cos(a) * ro, np.sin(a) * ro]
    if spokes == 0:  # solid pinion-like wheel with bore
        rb = r_bore if r_bore else r_root * 0.25
        mb.add(*ring_solid(outer, np.c_[np.cos(a) * rb, np.sin(a) * rb], z0, z1))
        return mb.v[0], mb.f, mb.uv[0]
    ri = r_rim_in or r_root * 0.82
    mb.add(*ring_solid(outer, np.c_[np.cos(a) * ri, np.sin(a) * ri], z0, z1))
    rh = r_hub or r_root * 0.22
    rb = r_bore or rh * 0.45
    mb.add(*ring_solid(circle(rh, 48), circle(rb, 48), z0 + (z1 - z0) * 0.0, z1 + (z1 - z0) * 0.35))
    sw = spoke_w or r_root * 0.085
    for k in range(spokes):
        t = np.linspace(0, 1, 14)
        rr = rh * 0.85 + (ri * 1.03 - rh * 0.85) * t
        aa = k * TAU / spokes + curve * np.sin(t * math.pi * 0.9)
        path = np.c_[np.cos(aa) * rr, np.sin(aa) * rr]
        taper = 1.35 - 0.55 * np.sin(t * math.pi) + 0.25 * t
        mb.add(*strip_solid(path, sw, z0 + (z1 - z0) * 0.08, z1 - (z1 - z0) * 0.08, taper=taper))
    v = np.vstack(mb.v); uv = np.vstack(mb.uv)
    return v, mb.f, uv


def screw_part(r, h, slot=True, segs=32):
    """Watch screw: domed polished head with slot (as two head halves). Axis +Z, base at z=0."""
    mb = MeshBuilder()
    prof = [(0.0, h * 1.0), (r * .35, h * .97), (r * .7, h * .86), (r * .93, h * .62), (r, h * .4), (r, 0.0),
            (r * .45, 0.0), (r * .45, -h * 1.4), (0.0, -h * 1.4)]
    if not slot:
        mb.add(*revolve(prof, segs))
    else:
        g = r * 0.09
        for side in (0, 1):
            v, f, uv = revolve(prof, segs // 2, angle0=side * math.pi, angle=math.pi)
            # close the half with a fan — clip slot by shifting halves apart
            v = v.copy(); v[:, 1] += (g if side == 0 else -g)
            # cap the cut plane
            n = len(prof)
            cap1 = tuple(range(n))
            cap2 = tuple((segs // 2) * n + i for i in range(n))
            mb.add(v, f + [cap1[::-1], cap2], uv)
        mb.add(*revolve([(0, h * .3), (r * .44, h * .3), (r * .44, -h * 1.4), (0, -h * 1.4)], segs))
    return np.vstack(mb.v), mb.f, np.vstack(mb.uv)


def jewel_part(r, h, segs=32):
    """Ruby cabochon set in a polished chaton. returns (chaton, ruby) parts."""
    chaton = revolve([(r * .55, h * .5), (r * 1.0, h * .5), (r * 1.25, h * .25), (r * 1.25, -h * .6),
                      (r * .9, -h * .6), (r * .55, h * .1), (r * .55, h * .5)], segs)
    ruby = revolve([(0, h * .75), (r * .3, h * .7), (r * .5, h * .55), (r * .62, h * .3), (r * .62, -h * .3),
                    (0, -h * .3)], segs)
    return chaton, ruby


def xf_matrix(loc=(0, 0, 0), rot=(0, 0, 0), scale=1.0):
    from mathutils import Euler
    M = Matrix.Translation(Vector(loc)) @ Euler(rot, 'XYZ').to_matrix().to_4x4() @ Matrix.Scale(scale, 4)
    return np.array(M)


def frame_matrix(origin, x, y, z):
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = x, y, z, origin
    return M


# ----------------------------------------------------------------------------- shader DSL
class Shader:
    def __init__(self, name):
        self.mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        self.mat.use_nodes = True
        self.nt = self.mat.node_tree
        self.nt.nodes.clear()
        self.out = self.nt.nodes.new("ShaderNodeOutputMaterial")
        self._x = 0

    def node(self, t, inputs=None, **props):
        n = self.nt.nodes.new(t)
        n.location = (self._x, 0); self._x -= 30
        for k, v in props.items():
            setattr(n, k, v)
        for k, v in (inputs or {}).items():
            self.set(n.inputs[k] if not isinstance(k, str) or k in n.inputs else self._find(n.inputs, k), v)
        return n

    @staticmethod
    def _find(socks, key):
        for s in socks:
            if s.identifier == key or s.name == key:
                if s.enabled:
                    return s
        for s in socks:
            if s.identifier == key or s.name == key:
                return s
        raise KeyError(key)

    def set(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, sock)
        elif isinstance(v, bpy.types.Node):
            self.nt.links.new(v.outputs[0], sock)
        else:
            try:
                sock.default_value = v
            except (TypeError, ValueError):
                n = len(sock.default_value)
                sock.default_value = (v,) * n if not hasattr(v, '__len__') else tuple(v) + (1,) * (n - len(v))

    # --- math helpers
    def math(self, op, a, b=0.0, c=0.0, clamp=False):
        n = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        self.set(n.inputs[0], a); self.set(n.inputs[1], b); self.set(n.inputs[2], c)
        return n.outputs[0]

    def vmath(self, op, a, b=(0, 0, 0), scale=None):
        n = self.node("ShaderNodeVectorMath", operation=op)
        self.set(n.inputs[0], a); self.set(n.inputs[1], b)
        if scale is not None:
            self.set(n.inputs[3], scale)
        return n.outputs[1] if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else n.outputs[0]

    def maprange(self, v, a, b, c=0.0, d=1.0, clamp=True, interp='LINEAR'):
        n = self.node("ShaderNodeMapRange", clamp=clamp, interpolation_type=interp)
        for i, x in enumerate((v, a, b, c, d)):
            self.set(n.inputs[i], x)
        return n.outputs[0]

    def mix(self, fac, a, b, blend='MIX'):
        n = self.node("ShaderNodeMix", data_type='RGBA', blend_type=blend)
        self.set(self._find(n.inputs, 'Factor_Float'), fac)
        self.set(self._find(n.inputs, 'A_Color'), a)
        self.set(self._find(n.inputs, 'B_Color'), b)
        return self._find(n.outputs, 'Result_Color')

    def mixf(self, fac, a, b):
        n = self.node("ShaderNodeMix", data_type='FLOAT')
        self.set(self._find(n.inputs, 'Factor_Float'), fac)
        self.set(self._find(n.inputs, 'A_Float'), a)
        self.set(self._find(n.inputs, 'B_Float'), b)
        return self._find(n.outputs, 'Result_Float')

    def ramp(self, fac, stops):
        n = self.node("ShaderNodeValToRGB")
        self.set(n.inputs[0], fac)
        el = n.color_ramp.elements
        while len(el) > 1:
            el.remove(el[-1])
        el[0].position, el[0].color = stops[0][0], tuple(stops[0][1]) + ((1,) if len(stops[0][1]) == 3 else ())
        for p, c in stops[1:]:
            e = el.new(p); e.color = tuple(c) + ((1,) if len(c) == 3 else ())
        return n.outputs[0]

    def noise(self, vec=None, scale=5.0, detail=4.0, rough=0.5, dist=0.0, dims='3D', lac=2.0):
        n = self.node("ShaderNodeTexNoise", {"Scale": scale, "Detail": detail, "Roughness": rough,
                                             "Distortion": dist, "Lacunarity": lac}, noise_dimensions=dims)
        if vec is not None:
            self.set(n.inputs["Vector"], vec)
        return n

    def voronoi(self, vec=None, scale=5.0, feature='F1', rand=1.0, dims='3D'):
        n = self.node("ShaderNodeTexVoronoi", {"Scale": scale, "Randomness": rand}, feature=feature,
                      voronoi_dimensions=dims)
        if vec is not None:
            self.set(n.inputs["Vector"], vec)
        return n

    def coord(self, kind='Object'):
        return self.node("ShaderNodeTexCoord").outputs[kind]

    def uv(self):
        return self.node("ShaderNodeUVMap", uv_map="UVMap").outputs[0]

    def bump(self, height, strength=0.1, distance=0.01, normal=None):
        n = self.node("ShaderNodeBump", {"Strength": strength, "Distance": distance})
        self.set(n.inputs["Height"], height)
        if normal is not None:
            self.set(n.inputs["Normal"], normal)
        return n.outputs[0]

    def principled(self, **kw):
        names = {k.replace('_', ' '): v for k, v in kw.items()}
        n = self.node("ShaderNodeBsdfPrincipled")
        for k, v in names.items():
            self.set(n.inputs[k], v)
        return n.outputs[0]

    def output(self, shader, volume=None, displacement=None):
        self.set(self.out.inputs["Surface"], shader)
        if volume is not None:
            self.set(self.out.inputs["Volume"], volume)
        if displacement is not None:
            self.set(self.out.inputs["Displacement"], displacement)
        return self.mat

    def sep(self, vec):
        n = self.node("ShaderNodeSeparateXYZ"); self.set(n.inputs[0], vec)
        return n.outputs

    def comb(self, x, y, z):
        n = self.node("ShaderNodeCombineXYZ")
        for i, v in enumerate((x, y, z)):
            self.set(n.inputs[i], v)
        return n.outputs[0]


def assign(ob, *mats):
    ob.data.materials.clear()
    for m in mats:
        ob.data.materials.append(m)
    return ob


def bevel(ob, width, segs=2, angle=35, harden=False, clamp=True):
    m = ob.modifiers.new("Bevel", 'BEVEL')
    m.width = width; m.segments = segs; m.limit_method = 'ANGLE'
    m.angle_limit = math.radians(angle); m.harden_normals = harden; m.use_clamp_overlap = clamp
    m.miter_outer = 'MITER_ARC'
    return m
