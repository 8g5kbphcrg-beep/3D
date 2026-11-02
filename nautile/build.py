"""NAUTILE — Calibre Φ 1.618
A sectioned Nautilus pompilius grown into a haute-horlogerie movement.
Run:  python3 build.py   -> writes nautile.blend
"""
import math, os, sys, random
import numpy as np
import bpy
from mathutils import Vector, Matrix, Euler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *          # noqa
import materials

OUT = os.path.dirname(os.path.abspath(__file__))
rng = np.random.default_rng(1618)
random.seed(1618)

# ============================================================================ reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
M = materials.build_all()

# ============================================================================ spiral maths
GROWTH = 3.0                         # whorl expansion per turn (nautilus ~3)
B = math.log(GROWTH) / TAU
R0 = 1.2                             # tube centre radius at the aperture
K = 0.52                             # half-width / radius
HK = 0.70                            # depth / half-width
TH_MIN = -3.6 * TAU
SPIRAL_ROT = math.radians(-118)      # orientation of the aperture in the frame
LAST_SEPT = -0.36 * TAU
D_SEPT = TAU / 11.0
SQ = math.sqrt(1 + B * B)


def r_(t): return R0 * np.exp(B * np.asarray(t))
def w_(t): return K * r_(t)
def h_(t): return HK * w_(t)


def P(t, u, z):
    """Shell-local point (cut plane z=0, body at z<0, viewed from +z)."""
    t = np.asarray(t, float); a = t + SPIRAL_ROT
    rr = r_(t) + u
    return np.stack([np.cos(a) * rr, np.sin(a) * rr, np.broadcast_to(z, np.shape(rr))], -1)


def frame(t):
    a = t + SPIRAL_ROT
    er = np.array([math.cos(a), math.sin(a), 0.0])
    et = np.array([-math.sin(a), math.cos(a), 0.0])
    return er, et, np.array([0, 0, 1.0])


coll = scene.collection
rig = bpy.data.objects.new("NAUTILE_Rig", None); coll.objects.link(rig)
shell_root = bpy.data.objects.new("Shell_Root", None); coll.objects.link(shell_root)
shell_root.parent = rig


def parent(ob, p=None):
    ob.parent = p or shell_root
    return ob


# ============================================================================ shell
def build_shell():
    nT, nP = 1000, 80
    T = np.linspace(TH_MIN, 0.0, nT)
    phi = np.linspace(0, math.pi, nP)
    Wt, Ht = w_(T), h_(T)
    # aperture lip: slight flare over the last few degrees
    flare = 1 + 0.035 * np.clip((T + 0.25) / 0.25, 0, 1) ** 2
    u = (Wt * flare)[:, None] * np.cos(phi)[None, :]
    z = -(Ht * flare)[:, None] * np.sin(phi)[None, :]
    V = P(T[:, None], u, z).reshape(-1, 3)
    UV = np.stack(np.broadcast_arrays((T / TAU)[:, None], (phi / math.pi)[None, :]), -1).reshape(-1, 2)
    F = grid_faces(nT, nP, flip=True)
    ob = make_mesh("Shell", V, F, uvs=UV)
    # outward-normal check: the deepest point's normal must point to -z
    me = ob.data
    mid = me.polygons[(nT // 2) * (nP - 1) + nP // 2]
    if mid.normal.z > 0:
        me.flip_normals()
    vg = ob.vertex_groups.new(name="thick")
    wts = (r_(T) / R0)[:, None].repeat(nP, 1).ravel()
    for i, wv in enumerate(wts):
        vg.add([i], float(wv), 'REPLACE')
    sol = ob.modifiers.new("Solidify", 'SOLIDIFY')
    sol.thickness = 0.034 * w_(0.0); sol.offset = -1.0; sol.vertex_group = "thick"
    sol.thickness_vertex_group = 0.0; sol.use_even_offset = True; sol.use_quality_normals = True
    sol.material_offset = 1; sol.material_offset_rim = 2
    sub = ob.modifiers.new("Bevel", 'BEVEL'); sub.width = 0.0012; sub.segments = 2; sub.limit_method = 'ANGLE'
    assign(ob, M['outer'], M['nacre'], M['section'])
    return parent(ob)


def septa_thetas():
    th = []
    t = LAST_SEPT
    while t > TH_MIN + 0.35 * TAU:
        th.append(t); t -= D_SEPT
    return th


def sag_dtheta(t, rho, s=0.42):
    return s * w_(t) * (1 - rho ** 2) / (r_(t) * SQ)


def build_septa():
    mb = MeshBuilder(); wts = []
    nR, nP = 14, 40
    for t in septa_thetas():
        rho = np.linspace(0, 1, nR)[:, None]; phi = np.linspace(0, math.pi, nP)[None, :]
        tt = t - sag_dtheta(t, rho) + 0 * phi
        u = rho * w_(tt) * 0.985 * np.cos(phi)
        z = -rho * h_(tt) * 0.985 * np.sin(phi)
        V = P(tt, u, z).reshape(-1, 3)
        mb.add(V, grid_faces(nR, nP), np.c_[np.full(len(V), t), np.zeros(len(V))])
        wts += [float(r_(t) / R0)] * len(V)
    ob = mb.build("Septa")
    # vertex weights survive merge only approximately; use per-vertex distance to centre instead
    vg = ob.vertex_groups.new(name="thick")
    co = np.array([v.co[:] for v in ob.data.vertices])
    rr = np.linalg.norm(co[:, :2], axis=1)
    for i, x in enumerate(np.clip(rr / R0, 0.02, 1.0)):
        vg.add([i], float(x), 'REPLACE')
    sol = ob.modifiers.new("Solidify", 'SOLIDIFY')
    sol.thickness = 0.022 * w_(0.0); sol.offset = 0.0; sol.vertex_group = "thick"
    sol.thickness_vertex_group = 0.0; sol.material_offset_rim = 1; sol.use_even_offset = True
    assign(ob, M['nacre_sep'], M['section'])
    return parent(ob)


def siphuncle_path(t0, t1, n):
    T = np.linspace(t0, t1, n)
    rs = 0.05 * w_(T)
    path = P(T, 0.0 * T, -rs * 1.15)
    return T, path, rs


def build_siphuncle(t_end):
    T, path, rs = siphuncle_path(TH_MIN + 0.45 * TAU, t_end, 900)
    Tg, N, Bv = tube_frames(path)
    prof = circle(1.0, 20)
    v, f, uv = sweep(path, N, Bv, prof, scale=rs)
    mb = MeshBuilder(); mb.add(v, f, uv, 0)
    # septal necks: polished collars where the shaft pierces each septum
    for t in septa_thetas():
        if t < T[0]:
            continue
        rs_t = 0.05 * w_(t)
        tt = t - sag_dtheta(t, 0.0)
        o = P(tt, 0.0, -rs_t * 1.15)
        er, et, ez = frame(tt)
        xf = frame_matrix(o, er, ez, et)          # collar axis along tangent
        col = revolve([(rs_t * 1.0, -rs_t * .9), (rs_t * 1.55, -rs_t * .6), (rs_t * 1.7, 0), (rs_t * 1.55, rs_t * .6),
                       (rs_t * 1.0, rs_t * .9)], 24)
        mb.add_part(col, 1, xf)
    ob = mb.build("Siphuncle_DriveShaft")
    assign(ob, M['rosegold'], M['gold_pol'])
    return parent(ob)


# ============================================================================ gear train in chambers
def build_chamber_gears():
    th = septa_thetas()
    gears = []
    for i in range(len(th) - 1):
        t_hi, t_lo = th[i], th[i + 1]
        rho_g = 0.5
        tc = 0.5 * (t_hi + t_lo) - sag_dtheta(0.5 * (t_hi + t_lo), rho_g)
        if r_(tc) < 0.06:
            continue
        w = w_(tc); r = r_(tc)
        arc = r * D_SEPT * SQ
        rg = min(0.36 * w, 0.40 * arc)
        zz = -0.20 * h_(tc)
        thick = 0.045 * w
        o = P(tc, rho_g * w, zz)
        er, et, ez = frame(tc)
        spin = rng.uniform(0, TAU)
        c, s = math.cos(spin), math.sin(spin)
        X = c * er + s * et; Y = -s * er + c * et
        xf = frame_matrix(o, X, Y, ez)
        teeth = int(np.clip(round(rg / w_(0.0) * 150), 24, 66))
        mb = MeshBuilder()
        mb.add_part(gear_part(teeth, rg * 0.93, rg, -thick / 2, thick / 2, spokes=5 if i % 2 == 0 else 4,
                              curve=0.55 if i % 2 == 0 else -0.45), 0)
        # pinion stacked under the wheel + arbor
        mb.add_part(gear_part(9, rg * 0.22, rg * 0.27, -thick * 3.2, -thick * 0.5, spokes=0, r_bore=rg * 0.05), 1)
        mb.add_part(revolve([(0, -thick * 6), (rg * .045, -thick * 6), (rg * .045, thick * 1.2), (rg * .03, thick * 1.6),
                             (0, thick * 1.65)], 16), 1)
        ch, rb = jewel_part(rg * 0.11, thick * 0.9)
        mb.add_part(ch, 3, xf_matrix((0, 0, thick * 0.95)))
        mb.add_part(rb, 2, xf_matrix((0, 0, thick * 0.95)))
        ob = mb.build(f"Gear_{i:02d}", sharp_angle=40)
        assign(ob, M['gold'], M['steel'], M['ruby'], M['gold_pol'])
        bevel(ob, min(0.002, thick * 0.12), 2, 40)
        ob.matrix_world = Matrix(xf.tolist())
        parent(ob)
        gears.append(ob)
    return gears


# ============================================================================ tourbillon
TH_T = -0.12 * TAU
TH_B = -0.29 * TAU
Z_TRAIN = -0.135


def build_tourbillon():
    w = w_(TH_T); Rc = 0.55 * w
    o = P(TH_T, 0.0, 0.0)
    er, et, ez = frame(TH_T)
    base_xf = frame_matrix(o, er, et, ez)
    parts = {}

    def add(name, part, mat, xf=None, mb=None):
        parts.setdefault(name, (MeshBuilder(), mat))[0].add_part(part, 0, xf)

    # fixed fourth wheel (ring gear) deep in the chamber
    add("T_FourthWheel", gear_part(96, Rc * 1.12, Rc * 1.17, Z_TRAIN - 0.008, Z_TRAIN + 0.008, spokes=6,
                                   r_hub=Rc * .24, curve=0.35), 'gold')
    # lower cage plate: ring + 3 arms
    lc = MeshBuilder()
    lc.add(*ring_solid(circle(Rc * .98, 96), circle(Rc * .86, 96), -Rc * .34, -Rc * .30))
    for k in range(3):
        a = k * TAU / 3 + 0.3
        path = np.c_[np.cos(a) * np.linspace(Rc * .1, Rc * .9, 12), np.sin(a) * np.linspace(Rc * .1, Rc * .9, 12)]
        lc.add(*strip_solid(path, Rc * .12, -Rc * .34, -Rc * .30, taper=np.linspace(1.4, 0.8, 12)))
    lc.add(*ring_solid(circle(Rc * .17, 48), circle(Rc * .06, 48), -Rc * .35, -Rc * .29))
    parts["T_CageLower"] = (lc, 'steel')
    # upper cage bridge: lyre-shaped arms meeting at hub
    uc = MeshBuilder()
    uc.add(*ring_solid(circle(Rc * .96, 96), circle(Rc * .88, 96), Rc * .04, Rc * .08))
    for k in range(3):
        a0 = k * TAU / 3
        t = np.linspace(0, 1, 24)
        rr = Rc * (.12 + .80 * t); aa = a0 + 0.55 * np.sin(t * math.pi)
        for sgn in (1, -1):
            aa2 = a0 + sgn * 0.32 * np.sin(t * math.pi) + 0.15 * t
            uc.add(*strip_solid(np.c_[np.cos(aa2) * rr, np.sin(aa2) * rr], Rc * .045, Rc * .04, Rc * .08))
    uc.add(*ring_solid(circle(Rc * .16, 48), circle(Rc * .05, 48), Rc * .035, Rc * .095))
    parts["T_CageUpper"] = (uc, 'steel')
    # pillars
    pil = MeshBuilder()
    for k in range(3):
        a = k * TAU / 3 + TAU / 6
        pil.add_part(revolve([(0, -Rc * .30), (Rc * .035, -Rc * .30), (Rc * .025, -Rc * .1), (Rc * .025, Rc * .0),
                              (Rc * .035, Rc * .04), (0, Rc * .04)], 20),
                     0, xf_matrix((math.cos(a) * Rc * .92, math.sin(a) * Rc * .92, 0)))
    parts["T_Pillars"] = (pil, 'steel')
    # balance wheel: rim, 2 arms, 8 timing screws
    bw = MeshBuilder()
    Rb = Rc * .60
    bw.add(*ring_solid(circle(Rb, 128), circle(Rb * .9, 128), -Rc * .12, -Rc * .06))
    for k in range(2):
        a = k * math.pi + 0.4
        bw.add(*strip_solid(np.c_[np.cos(a) * np.linspace(-Rb * .02, Rb * .92, 8), np.sin(a) * np.linspace(-Rb * .02, Rb * .92, 8)],
                            Rc * .05, -Rc * .11, -Rc * .07))
    bw.add_part(revolve([(0, -Rc * .2), (Rc * .03, -Rc * .2), (Rc * .03, Rc * .02), (0, Rc * .02)], 16))
    parts["T_BalanceWheel"] = (bw, 'gold_pol')
    scr = MeshBuilder()
    for k in range(10):
        a = k * TAU / 10 + 0.15
        er2 = np.array([math.cos(a), math.sin(a), 0]); et2 = np.array([-math.sin(a), math.cos(a), 0])
        xf = frame_matrix(er2 * Rb * 0.99 + np.array([0, 0, -Rc * .09]), et2, np.array([0, 0, 1.0]), er2)
        scr.add_part(screw_part(Rc * .022, Rc * .03, slot=False, segs=16), 0, xf)
    parts["T_TimingScrews"] = (scr, 'gold_pol')
    # hairspring (Archimedean, flat) – palladium / blued
    hs = MeshBuilder()
    turns = 13; n = 1400
    t = np.linspace(0, 1, n)
    rr = Rc * (.06 + .34 * t); aa = t * turns * TAU
    hs.add(*strip_solid(np.c_[np.cos(aa) * rr, np.sin(aa) * rr], Rc * .007, -Rc * .17, -Rc * .135))
    parts["T_Hairspring"] = (hs, 'blued')
    # escape wheel & pallet lever (inside the cage, offset)
    ew_xf = xf_matrix((Rc * .58, -Rc * .18, 0))
    esc = MeshBuilder()
    M_ = 15 * 10; a = np.arange(M_) * TAU / M_; ph = (np.arange(M_) % 10) / 10
    ro = Rc * (.16 + .07 * np.interp(ph, [0, .6, .65, 1.0], [0, 1, 0, 0]))
    esc.add(*ring_solid(np.c_[np.cos(a) * ro, np.sin(a) * ro], circle(Rc * .13, M_), -Rc * .27, -Rc * .245))
    for k in range(4):
        aa = k * TAU / 4
        esc.add(*strip_solid(np.c_[np.cos(aa) * np.linspace(0, Rc * .14, 5), np.sin(aa) * np.linspace(0, Rc * .14, 5)],
                             Rc * .025, -Rc * .27, -Rc * .245))
    esc.add_part(gear_part(8, Rc * .04, Rc * .055, -Rc * .42, -Rc * .27, spokes=0, r_bore=Rc * .01))
    parts["T_EscapeWheel"] = (esc, 'steel')
    lev = MeshBuilder()
    lev.add(*strip_solid(np.c_[np.linspace(Rc * .05, Rc * .42, 10), np.linspace(-Rc * .03, -Rc * .1, 10)], Rc * .045,
                         -Rc * .245, -Rc * .225))
    lev.add(*strip_solid(np.c_[np.full(6, Rc * .36), np.linspace(-Rc * .2, Rc * .02, 6)], Rc * .035, -Rc * .245, -Rc * .225))
    parts["T_Lever"] = (lev, 'blued')
    # seconds indicator on cage top
    hand = MeshBuilder()
    hand.add(*polygon_solid([(Rc * -.25, -Rc * .012), (Rc * .86, -Rc * .004), (Rc * .9, 0), (Rc * .86, Rc * .004),
                             (Rc * -.25, Rc * .012)], Rc * .10, Rc * .115))
    hand.add_part(revolve([(0, Rc * .095), (Rc * .05, Rc * .095), (Rc * .05, Rc * .125), (0, Rc * .13)], 24))
    parts["T_SecondsHand"] = (hand, 'blued')
    # jewels
    jw = MeshBuilder(); rb_ = MeshBuilder()
    for pos in [(0, 0, Rc * .1), (0, 0, -Rc * .36), (Rc * .58, -Rc * .18, -Rc * .43)]:
        c, r = jewel_part(Rc * .05, Rc * .04)
        jw.add_part(c, 0, xf_matrix(pos)); rb_.add_part(r, 0, xf_matrix(pos))
    for k in range(3):
        a = k * TAU / 3 + 0.3
        c, r = jewel_part(Rc * .03, Rc * .025)
        p = (math.cos(a) * Rc * .55, math.sin(a) * Rc * .55, -Rc * .29)
        jw.add_part(c, 0, xf_matrix(p)); rb_.add_part(r, 0, xf_matrix(p))
    parts["T_Chatons"] = (jw, 'gold_pol'); parts["T_Rubies"] = (rb_, 'ruby')
    # blued screws on upper cage
    bs = MeshBuilder()
    for k in range(3):
        a = k * TAU / 3 + 0.15
        bs.add_part(screw_part(Rc * .04, Rc * .025, segs=24), 0,
                    xf_matrix((math.cos(a) * Rc * .92, math.sin(a) * Rc * .92, Rc * .08), (0, 0, a + .7)))
    parts["T_Screws"] = (bs, 'blued')

    obs = []
    tb_root = bpy.data.objects.new("Tourbillon", None); coll.objects.link(tb_root)
    tb_root.parent = shell_root
    tb_root.matrix_world = Matrix(base_xf.tolist())
    for name, (mb, mat) in parts.items():
        ob = mb.build(name, sharp_angle=38)
        assign(ob, M[mat])
        if name not in ("T_Hairspring",):
            bevel(ob, Rc * 0.004, 2, 40)
        ob.parent = tb_root
        obs.append(ob)
    return Rc, base_xf, obs


def build_bridge(Rc, base_xf):
    """Forged-carbon bridge spanning the body chamber, holding the tourbillon's top pivot."""
    w = w_(TH_T)
    z0, z1 = 0.028, 0.05
    mb = MeshBuilder()
    mb.add(*ring_solid(circle(Rc * .30, 64), circle(Rc * .17, 64), z0, z1))
    for sgn in (1, -1):
        t = np.linspace(0, 1, 30)
        x = sgn * (Rc * .27 + t * (w * 1.04 - Rc * .27))
        y = 0.18 * Rc * np.sin(t * math.pi) * sgn
        mb.add(*strip_solid(np.c_[x, y], Rc * .22, z0, z1, taper=1.0 - 0.35 * np.sin(t * math.pi)))
        foot = circle(Rc * .17, 40) + np.array([sgn * w * 1.04, 0])
        mb.add(*polygon_solid(foot, z0, z1))
    ob = mb.build("Bridge_ForgedCarbon", sharp_angle=35)
    assign(ob, M['forged']); bevel(ob, 0.003, 3, 35)
    ob.matrix_world = Matrix(base_xf.tolist()); parent(ob)
    # chaton + ruby + blued screws on the bridge
    hw = MeshBuilder(); rb = MeshBuilder(); sc = MeshBuilder()
    c, r = jewel_part(Rc * .075, Rc * .05)
    hw.add_part(c, 0, xf_matrix((0, 0, z1 + Rc * .015)))
    rb.add_part(r, 0, xf_matrix((0, 0, z1 + Rc * .015)))
    hw.add_part(revolve([(Rc * .17, z1), (Rc * .19, z1), (Rc * .19, z1 + .004), (Rc * .17, z1 + .006)], 64))
    for sgn in (1, -1):
        for dy in (-1, 1):
            sc.add_part(screw_part(Rc * .05, Rc * .035, segs=28), 0,
                        xf_matrix((sgn * w * 1.04 + dy * Rc * .05, dy * Rc * .06, z1), (0, 0, rng.uniform(0, 3))))
    for nm, b_, m in (("Bridge_Chaton", hw, 'gold_pol'), ("Bridge_Ruby", rb, 'ruby'), ("Bridge_Screws", sc, 'blued')):
        o2 = b_.build(nm, sharp_angle=38); assign(o2, M[m]); o2.matrix_world = Matrix(base_xf.tolist()); parent(o2)
    return ob


def build_barrel(Rc):
    """Mainspring barrel (skeletonised) + intermediate wheel feeding the tourbillon."""
    wB = w_(TH_B); R = 0.62 * wB
    o = P(TH_B, 0.0, 0.0); er, et, ez = frame(TH_B)
    xf = frame_matrix(o, er, et, ez)
    root = bpy.data.objects.new("Barrel", None); coll.objects.link(root); root.parent = shell_root
    root.matrix_world = Matrix(xf.tolist())
    parts = {}
    def add(nm, part, mat, x=None):
        parts.setdefault(nm, (MeshBuilder(), mat))[0].add_part(part, 0, x)
    zg0, zg1 = Z_TRAIN - 0.008, Z_TRAIN + 0.008
    add("B_Drum", gear_part(110, R * .965, R, zg0, zg1, spokes=0, r_bore=R * .9), 'gold')
    add("B_Drum", ring_solid(circle(R * .93, 160), circle(R * .885, 160), zg0 - 0.006, -0.03), 'gold')
    add("B_Drum", ring_solid(circle(R * .93, 160), circle(R * .12, 160), zg0 - 0.012, zg0 - 0.004), 'gold')
    # skeleton cover
    cov = MeshBuilder()
    cov.add(*ring_solid(circle(R * .935, 160), circle(R * .80, 160), -0.036, -0.026))
    for k in range(5):
        t = np.linspace(0, 1, 16); rr = R * (.28 + .55 * t); aa = k * TAU / 5 + 0.6 * np.sin(t * 2.6)
        cov.add(*strip_solid(np.c_[np.cos(aa) * rr, np.sin(aa) * rr], R * .07, -0.036, -0.026,
                             taper=1.2 - 0.5 * np.sin(t * math.pi)))
    parts["B_Cover"] = (cov, 'gold')
    # mainspring: thick Archimedean strip
    t = np.linspace(0, 1, 1600); rr = R * (.2 + .66 * t ** 0.9); aa = -t * 7.5 * TAU
    add("B_Mainspring", strip_solid(np.c_[np.cos(aa) * rr, np.sin(aa) * rr], R * .022, zg0 - 0.002, -0.04), 'blued')
    add("B_Arbor", revolve([(0, zg0 - 0.03), (R * .18, zg0 - 0.03), (R * .18, -0.03), (R * .1, -0.02), (R * .1, 0.004),
                            (0, 0.006)], 48), 'steel')
    # ratchet wheel (sawtooth) with circular graining + screws
    n = 44 * 8; a = np.arange(n) * TAU / n; ph = (np.arange(n) % 8) / 8
    ro = R * (.56 + .05 * np.interp(ph, [0, .85, .9, 1], [0, 1, 0, 0]))
    rat = MeshBuilder(); rat.add(*ring_solid(np.c_[np.cos(a) * ro, np.sin(a) * ro], circle(R * .1, n), -0.022, -0.006))
    parts["B_Ratchet"] = (rat, 'steel_sun')
    for k in range(3):
        aa = k * TAU / 3 + 0.4
        add("B_Screws", screw_part(R * .045, R * .03, segs=24), 'blued',
            xf_matrix((math.cos(aa) * R * .3, math.sin(aa) * R * .3, -0.006), (0, 0, aa)))
    # click + spring (blued)
    add("B_Click", strip_solid(np.c_[np.linspace(R * .45, R * .7, 8), np.linspace(R * .5, R * .32, 8)], R * .06,
                               -0.02, -0.008, taper=np.linspace(1.3, 0.5, 8)), 'blued')
    for nm, (mb, mat) in parts.items():
        ob = mb.build(nm, sharp_angle=38); assign(ob, M[mat])
        if nm != "B_Mainspring":
            bevel(ob, R * 0.005, 2, 40)
        ob.parent = root
    # intermediate (third) wheel between barrel and tourbillon, in the same plane
    pb = P(TH_B, 0, Z_TRAIN); pt = P(TH_T, 0, Z_TRAIN)
    D = np.linalg.norm(pt - pb); R4 = Rc * 1.17
    rm = (D - R4 - R) / 2 + 0.006
    pm = pb + (pt - pb) * (R + rm) / D
    tm = 0.5 * (TH_B + TH_T); er2, et2, ez2 = frame(tm)
    ob = MeshBuilder()
    ob.add_part(gear_part(int(rm / R * 110), rm * .965, rm, -0.008, 0.008, spokes=5, curve=-0.6, r_hub=rm * .25), 0)
    ob.add_part(gear_part(10, rm * .18, rm * .23, -0.05, -0.008, spokes=0, r_bore=rm * .04), 1)
    ob.add_part(revolve([(0, -0.07), (rm * .04, -0.07), (rm * .04, 0.02), (0, 0.022)], 16), 1)
    c, r = jewel_part(rm * .09, 0.012)
    ob.add_part(c, 3, xf_matrix((0, 0, 0.014))); ob.add_part(r, 2, xf_matrix((0, 0, 0.014)))
    g = ob.build("Third_Wheel", sharp_angle=40)
    assign(g, M['gold'], M['steel'], M['ruby'], M['gold_pol']); bevel(g, 0.0015, 2, 40)
    g.matrix_world = Matrix(frame_matrix(pm, er2, et2, ez2).tolist()); parent(g)
    # second bridge (forged carbon) across the barrel
    zb0, zb1 = 0.004, 0.026
    br = MeshBuilder()
    br.add(*ring_solid(circle(R * .26, 64), circle(R * .13, 64), zb0, zb1))
    for sgn in (1, -1):
        tt = np.linspace(0, 1, 30); x = sgn * (R * .24 + tt * (wB * 1.04 - R * .24)); y = -0.25 * R * np.sin(tt * math.pi) * sgn
        br.add(*strip_solid(np.c_[x, y], R * .2, zb0, zb1, taper=1.0 - 0.3 * np.sin(tt * math.pi)))
        br.add(*polygon_solid(circle(R * .15, 40) + np.array([sgn * wB * 1.04, 0]), zb0, zb1))
    bo = br.build("Bridge_Barrel", sharp_angle=35); assign(bo, M['forged']); bevel(bo, 0.003, 3, 35)
    bo.matrix_world = Matrix(xf.tolist()); parent(bo)
    sc = MeshBuilder()
    for sgn in (1, -1):
        sc.add_part(screw_part(R * .06, R * .04, segs=28), 0, xf_matrix((sgn * wB * 1.04, 0, zb1), (0, 0, rng.uniform(0, 3))))
    so = sc.build("Bridge_Barrel_Screws", sharp_angle=38); assign(so, M['blued'])
    so.matrix_world = Matrix(xf.tolist()); parent(so)
    return R


def build_contrate(Rbar):
    """Contrate pinion at the end of the siphuncle drive shaft, engaging the barrel."""
    oB = P(TH_B, 0, 0)
    ts = np.linspace(LAST_SEPT, TH_B, 400)
    d = np.linalg.norm(P(ts, 0 * ts, 0 * ts) - oB, axis=1)
    t_end = ts[np.argmin(np.abs(d - Rbar * 1.06))]
    rs = 0.05 * w_(t_end)
    o = P(t_end, 0.0, -rs * 1.15)
    er, et, ez = frame(t_end)
    xf = frame_matrix(o, er, -ez, et)
    pin = MeshBuilder()
    pin.add_part(gear_part(12, rs * 2.0, rs * 2.7, 0, rs * 1.6, spokes=0, r_bore=rs * .4))
    ob = pin.build("Contrate_Pinion", sharp_angle=38); assign(ob, M['gold_pol'])
    ob.matrix_world = Matrix(xf.tolist()); parent(ob)
    return t_end


# ============================================================================ assemble shell
shell = build_shell()
septa = build_septa()
gears = build_chamber_gears()
Rc, tb_xf, tb_obs = build_tourbillon()
bridge = build_bridge(Rc, tb_xf)
Rbar = build_barrel(Rc)
t_end = build_contrate(Rbar)
siph = build_siphuncle(t_end)

# centre shell in its bezel: bounding circle of the outline
T = np.linspace(TH_MIN + TAU * 2.2, 0, 600)
outline = np.vstack([P(T, w_(T), 0)[:, :2], P(T, -w_(T), 0)[:, :2]])
lo, hi = outline.min(0), outline.max(0)
centre = (lo + hi) / 2
R_SHELL = np.linalg.norm(outline - centre, axis=1).max()
print("shell bbox", lo, hi, "Rmax", R_SHELL)
shell_root.location = (-centre[0], -centre[1], 0.0)

# ============================================================================ bezel ring
R_IN = R_SHELL + 0.12
R_OUT = R_IN + 0.26
Z_FRONT = 0.125


def build_bezel():
    prof = [(R_IN, -0.34), (R_IN, 0.066), (R_IN + 0.025, 0.066), (R_IN + 0.025, 0.10), (R_IN + 0.045, Z_FRONT),
            (R_OUT - 0.035, Z_FRONT), (R_OUT - 0.008, Z_FRONT - 0.012), (R_OUT, Z_FRONT - 0.04),
            (R_OUT, -0.30), (R_OUT - 0.012, -0.33), (R_OUT - 0.04, -0.345), (R_IN + 0.02, -0.36), (R_IN, -0.34)]
    v, f, uv = revolve(prof, 720)
    # coin-edge fluting on the outer flank
    rr = np.linalg.norm(v[:, :2], axis=1)
    flank = (np.abs(rr - R_OUT) < 1e-6) & (v[:, 2] < Z_FRONT - 0.05) & (v[:, 2] > -0.29)
    ang = np.arctan2(v[:, 1], v[:, 0])
    k = 1 - 0.006 / R_OUT * (0.5 + 0.5 * np.cos(ang * 240))
    v[flank, :2] *= k[flank, None]
    mb = MeshBuilder(); mb.add(v, f, uv, 0)
    # inner flank fluting is cut later; tick marks (raised, polished)
    for i in range(60):
        a = math.pi / 2 - i * TAU / 60
        major = i % 5 == 0
        L = 0.06 if major else 0.032
        wdt = 0.012 if major else 0.005
        r0 = R_IN + 0.055
        cx, cy = math.cos(a), math.sin(a)
        loop = [(r0, -wdt / 2), (r0 + L, -wdt / 2), (r0 + L, wdt / 2), (r0, wdt / 2)]
        loop = [(x * cx - y * cy, x * cy + y * cx) for x, y in loop]
        mb.add(*polygon_solid(loop, Z_FRONT - 0.002, Z_FRONT + 0.0045), mat=1)
    ob = mb.build("Bezel_Titanium", sharp_angle=30)
    assign(ob, M['ti'], M['gold_pol'])
    parent(ob, rig)
    # sapphire crystal
    cv, cf, cuv = revolve([(0, 0.098), (R_IN * 0.5, 0.098), (R_IN + 0.02, 0.098)], 256)
    cr = make_mesh("Sapphire_Crystal", cv, cf, uvs=cuv)
    assign(cr, M['crystal']); parent(cr, rig)
    # grand-feu blue lacquer track carrying the numerals
    lv, lf, luv = revolve([(R_IN + 0.115, Z_FRONT + 0.0006), (R_IN + 0.235, Z_FRONT + 0.0006)], 360)
    lt = make_mesh("Lacquer_Track", lv, lf, uvs=luv); assign(lt, M['lacquer']); parent(lt, rig)
    for rr_, nm in ((R_IN + 0.112, "a"), (R_IN + 0.238, "b")):
        gv, gf, guv = revolve([(rr_ - 0.003, Z_FRONT), (rr_ - 0.003, Z_FRONT + 0.003), (rr_ + 0.003, Z_FRONT + 0.003),
                               (rr_ + 0.003, Z_FRONT)], 360)
        gl = make_mesh(f"Track_Filet_{nm}", gv, gf, uvs=guv); assign(gl, M['gold_pol']); parent(gl, rig)
    # Fibonacci numerals in place of hours
    fib = [144, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89]
    for i, nmb in enumerate(fib):
        a = math.pi / 2 - i * TAU / 12
        cu = bpy.data.curves.new(f"Num_{i}", 'FONT')
        cu.body = str(nmb); cu.size = 0.085; cu.extrude = 0.0025; cu.align_x = 'CENTER'; cu.align_y = 'CENTER'
        cu.bevel_depth = 0.0008; cu.space_character = 1.05
        to = bpy.data.objects.new(f"Numeral_{nmb}_{i}", cu); coll.objects.link(to)
        rr_ = R_IN + 0.175
        to.location = (math.cos(a) * rr_, math.sin(a) * rr_, Z_FRONT + 0.0032)
        to.rotation_euler = (0, 0, a - math.pi / 2)
        cu.materials.append(M['gold_pol']); to.parent = rig
    # signature on the lower part of the bezel
    cu = bpy.data.curves.new("Sig", 'FONT'); cu.body = "Φ"; cu.size = 0.11; cu.extrude = 0.003
    cu.align_x = 'CENTER'; cu.align_y = 'CENTER'
    return ob


def build_prongs():
    """Three titanium claws suspending the shell inside the bezel."""
    mb = MeshBuilder()
    off = np.array([-centre[0], -centre[1], 0])
    for tc in (-0.25, -2.25, -4.35):
        p_shell = P(tc, w_(tc) * 0.97, -0.38 * h_(tc)) + off
        d2 = p_shell[:2] / np.linalg.norm(p_shell[:2])
        p_ring = np.array([d2[0] * (R_IN + 0.02), d2[1] * (R_IN + 0.02), -0.16])
        tt = np.linspace(0, 1, 40)[:, None]
        mid = (p_shell + p_ring) / 2 + np.array([0, 0, -0.07])
        path = (1 - tt) ** 2 * p_ring + 2 * (1 - tt) * tt * mid + tt ** 2 * p_shell
        Tn, N, Bv = tube_frames(path, up=(0, 0, 1))
        sc = 0.022 * (1 - 0.45 * tt[:, 0]) + 0.012 * np.exp(-((tt[:, 0] - 0.0) / 0.08) ** 2)
        v, f, uv = sweep(path, N, Bv, circle(1.0, 20), scale=sc)
        mb.add(v, f, uv)
        # claw cup at the shell end
        e = path[-1]; dvec = (path[-1] - path[-2]); dvec /= np.linalg.norm(dvec)
        x = np.cross(dvec, [0, 0, 1.0]); x /= np.linalg.norm(x); y = np.cross(dvec, x)
        mb.add_part(revolve([(0, -0.012), (0.017, -0.01), (0.02, 0.0), (0.016, 0.012), (0, 0.014)], 24), 0,
                    frame_matrix(e, x, y, dvec))
    ob = mb.build("Prongs", sharp_angle=50); assign(ob, M['ti_pol']); parent(ob, rig)


bezel = build_bezel()
build_prongs()

# stand the rig up: local +z (cut face) -> world -y (towards camera), tilt slightly back
RING_Z = R_OUT + 0.55
rig.rotation_euler = (math.radians(90 - 7), 0, math.radians(0))
rig.location = (0, 0, RING_Z)

# ============================================================================ stand: carbon yoke, pivots, stem, plinth
def build_stand():
    Ry = R_OUT + 0.13
    zc = RING_Z
    a = np.linspace(math.pi * 1.0, math.pi * 2.0, 220)
    path = np.c_[np.cos(a) * Ry, np.zeros_like(a), zc + np.sin(a) * Ry]
    Tn = np.gradient(path, axis=0); Tn /= np.linalg.norm(Tn, axis=1)[:, None]
    Bv = np.tile([0, 1.0, 0], (len(a), 1)); N = np.cross(Bv, Tn)
    # rounded-rectangle section, slimmer at the top
    th = np.linspace(0, TAU, 48, endpoint=False)
    ex = 4.0
    px = np.sign(np.cos(th)) * np.abs(np.cos(th)) ** (2 / ex) * 0.05
    py = np.sign(np.sin(th)) * np.abs(np.sin(th)) ** (2 / ex) * 0.09
    taper = 0.75 + 0.45 * np.sin(np.linspace(0, math.pi, len(a)))
    V = path[:, None, :] + taper[:, None, None] * (px[None, :, None] * N[:, None, :] + py[None, :, None] * Bv[:, None, :])
    L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
    UV = np.stack(np.broadcast_arrays(L[:, None] * 0.6, (th / TAU)[None, :] * 0.35), -1)
    F = grid_faces(len(a), 48, wrap_v=True)
    nV = len(a) * 48
    V = V.reshape(-1, 3); UV = UV.reshape(-1, 2)
    caps = [tuple(range(47, -1, -1)), tuple(range(nV - 48, nV))]
    yoke = make_mesh("Yoke_CarbonTwill", V, F + caps, uvs=UV)
    assign(yoke, M['carbon']); bevel(yoke, 0.006, 3, 60)
    # pivots
    for sgn in (-1, 1):
        x0 = sgn * (R_OUT - 0.01); x1 = sgn * (Ry + 0.07)
        prof = [(0, 0), (0.05, 0), (0.05, 0.10), (0.065, 0.11), (0.065, abs(x1 - x0) - 0.06), (0.085, abs(x1 - x0) - 0.05),
                (0.09, abs(x1 - x0) - 0.02), (0.075, abs(x1 - x0)), (0, abs(x1 - x0) + 0.005)]
        v, f, uv = revolve(prof, 64)
        xf = frame_matrix((x0, 0, zc), (0, 1, 0), (0, 0, 1) if sgn > 0 else (0, 0, -1), (sgn, 0, 0))
        po = make_mesh(f"Pivot_{'R' if sgn > 0 else 'L'}", transform(v, xf), f, uvs=uv, sharp_angle=30)
        assign(po, M['ti_pol']); bevel(po, 0.003, 2, 30)
        sv, sf, suv = screw_part(0.035, 0.02, segs=32)
        so = make_mesh(f"PivotScrew_{sgn}", transform(sv, xf @ xf_matrix((0, 0, abs(x1 - x0) + 0.0), (0, 0, 0.6))), sf,
                       uvs=suv, sharp_angle=40)
        assign(so, M['blued'])
    # stem (revolved, carbon core with titanium collars)
    ztop = zc - Ry
    st = revolve([(0, 0.0), (0.16, 0.0), (0.16, 0.03), (0.11, 0.05), (0.075, 0.09), (0.06, ztop * 0.5),
                  (0.075, ztop - 0.07), (0.11, ztop - 0.02), (0.11, ztop + 0.02), (0, ztop + 0.02)], 96)
    sto = make_mesh("Stem", *st[:2], uvs=st[2], sharp_angle=35); assign(sto, M['ti_pol']); bevel(sto, 0.003, 2)
    core = revolve([(0, 0.08), (0.068, 0.08), (0.062, ztop * 0.5), (0.068, ztop - 0.08), (0, ztop - 0.08)], 96)
    co = make_mesh("Stem_Carbon", *core[:2], uvs=core[2] * [3, 1]); assign(co, M['carbon'])
    # plinth: granite block + titanium plinth plate
    bpy.ops.mesh.primitive_cube_add(size=1)
    pl = bpy.context.active_object; pl.name = "Plinth_Granite"
    pl.scale = (3.1, 1.4, 0.42); pl.location = (0, 0.05, -0.21)
    bpy.ops.object.transform_apply(scale=True)
    assign(pl, M['granite']); bevel(pl, 0.035, 5, 30); pl.data.shade_smooth()
    pl.data.set_sharp_from_angle(angle=math.radians(30))
    plate = revolve([(0, 0.0), (0.42, 0.0), (0.42, 0.012), (0.405, 0.022), (0, 0.022)], 128)
    po = make_mesh("Plinth_Plate", *plate[:2], uvs=plate[2], sharp_angle=30); assign(po, M['ti'])
    # engraved signature on the front face
    for txt, size, z, sp, nm in (("N A U T I L E", 0.085, -0.17, 1.6, "Sig_Main"),
                                  ("CALIBRE  Φ 1.618  ·  TOURBILLON ABYSSAL", 0.032, -0.29, 1.25, "Sig_Sub")):
        cu = bpy.data.curves.new(nm, 'FONT'); cu.body = txt; cu.size = size; cu.extrude = 0.002
        cu.align_x = 'CENTER'; cu.align_y = 'CENTER'; cu.space_character = sp; cu.bevel_depth = 0.0004
        to = bpy.data.objects.new(nm, cu); coll.objects.link(to)
        to.location = (0, 0.05 - 0.70 - 0.0015, z); to.rotation_euler = (math.pi / 2, 0, 0)
        cu.materials.append(M['rosegold'])


build_stand()

# ============================================================================ environment
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, -0.42))
fl = bpy.context.active_object; fl.name = "Floor"; assign(fl, M['floor'])

bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 2, 5))
fogbox = bpy.context.active_object; fogbox.name = "Abyss_Haze"; fogbox.scale = (40, 40, 12)
assign(fogbox, M['fog'])
fogbox.visible_shadow = True

# marine snow: drifting particles (bokeh in DOF)
mb = MeshBuilder()
ico = None
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1)
ico = bpy.context.active_object
iv = np.array([v.co[:] for v in ico.data.vertices]); ifc = [tuple(p.vertices) for p in ico.data.polygons]
bpy.data.objects.remove(ico)
for _ in range(520):
    p = np.array([rng.uniform(-6, 6), rng.uniform(-9, 7), rng.uniform(-0.3, 6.5)])
    if np.linalg.norm(p[[0, 2]] - [0, RING_Z]) < 2.2 and abs(p[1]) < 1.0:
        continue
    if p[1] < -1.8:
        continue
    s = rng.uniform(0.003, 0.009) * (1 + rng.exponential(0.4))
    mb.add(iv * s + p, ifc)
snow = mb.build("Marine_Snow"); assign(snow, M['snow'])
snow.visible_shadow = False

world = bpy.data.worlds.new("Abyss"); scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.0006, 0.0014, 0.003, 1); bg.inputs[1].default_value = 1.0


# ============================================================================ lights
def area(name, loc, target, size, energy, color, shape='RECTANGLE', size_y=None, spread=180):
    ld = bpy.data.lights.new(name, 'AREA'); ld.shape = shape; ld.size = size
    if size_y: ld.size_y = size_y
    ld.energy = energy; ld.color = color; ld.spread = math.radians(spread)
    ob = bpy.data.objects.new(name, ld); coll.objects.link(ob); ob.location = loc
    d = Vector(target) - Vector(loc); ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return ob


def spot(name, loc, target, energy, color, size_deg, blend=0.5, radius=0.05):
    ld = bpy.data.lights.new(name, 'SPOT'); ld.energy = energy; ld.color = color
    ld.spot_size = math.radians(size_deg); ld.spot_blend = blend; ld.shadow_soft_size = radius
    ob = bpy.data.objects.new(name, ld); coll.objects.link(ob); ob.location = loc
    d = Vector(target) - Vector(loc); ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return ob


C = (0, 0, RING_Z)
area("Key_Softbox", (-5.6, -2.4, 5.6), (0, 0, RING_Z - 0.2), 2.6, 3200, (1.0, 0.87, 0.74), size_y=1.1)
spot("Rim_Abyss", (3.2, 9.0, 11.5), (0, 0, RING_Z), 26000, (0.42, 0.72, 1.0), 26, 0.7, 0.15)
area("Rim_Teal", (-4.5, 4.5, 2.5), (0, 0, RING_Z), 1.8, 1500, (0.35, 0.95, 0.9), size_y=0.6)
area("Top_Strip", (0.0, -0.8, 7.0), (0, 0, 0), 4.0, 900, (0.85, 0.92, 1.0), size_y=0.5)
kick = area("Face_Kicker", (2.8, -5.5, 1.4), (0, 0, RING_Z), 1.0, 160, (1.0, 0.8, 0.6), shape='DISK')
kick.visible_glossy = False
spot("Plinth_Graze", (0.0, -3.0, 0.9), (0, -0.6, -0.15), 900, (1.0, 0.82, 0.62), 30, 0.8, 0.3)

# ============================================================================ cameras
def camera(name, loc, target, lens, fstop, focus_obj=None, focus_dist=None, sensor=36):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.sensor_width = sensor
    cd.dof.use_dof = True; cd.dof.aperture_fstop = fstop; cd.dof.aperture_blades = 7; cd.dof.aperture_rotation = 0.3
    ob = bpy.data.objects.new(name, cd); coll.objects.link(ob); ob.location = loc
    d = Vector(target) - Vector(loc); ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    if focus_obj is not None:
        cd.dof.focus_object = focus_obj
    elif focus_dist:
        cd.dof.focus_distance = focus_dist
    return ob


bpy.context.view_layer.update()
tb_world = bpy.data.objects["Tourbillon"].matrix_world.translation.copy()
focus_tb = bpy.data.objects.new("Focus_Tourbillon", None); coll.objects.link(focus_tb); focus_tb.location = tb_world
mid_gear = gears[len(gears) // 3].matrix_world.translation.copy()
focus_g = bpy.data.objects.new("Focus_Gears", None); coll.objects.link(focus_g); focus_g.location = mid_gear
print("tourbillon world", tb_world, "gear", mid_gear)

cam_hero = camera("CAM_Hero", (-2.9, -9.6, 3.1), (0.05, 0, RING_Z - 0.55), 62, 1.6, focus_tb)
bar_world = bpy.data.objects["Barrel"].matrix_world.translation.copy()
spiral_c = bpy.data.objects["Shell_Root"].matrix_world @ Vector((0, 0, 0))
mid_tb = (tb_world + bar_world) / 2
print("barrel", bar_world, "spiral centre", spiral_c)
cam_macro = camera("CAM_Macro", mid_tb + Vector((-2.0, -5.0, 1.1)), mid_tb + Vector((0.2, 0, -0.12)), 85, 0.9, focus_tb)
sp_off = Vector((1.15, -4.6, -0.75))
cam_gears = camera("CAM_Spiral", spiral_c + sp_off, spiral_c + Vector((-0.12, 0, 0.0)), 120, 0.75, None, sp_off.length * 0.97)
cam_back = camera("CAM_Back", (6.6, 7.2, 3.6), (0, 0, RING_Z - 0.4), 58, 1.8, None, 9.8)
scene.camera = cam_hero

# ============================================================================ render settings
r = scene.render; cy = scene.cycles
r.engine = 'CYCLES'; cy.device = 'CPU'
cy.samples = 256; cy.adaptive_threshold = 0.015; cy.use_denoising = True; cy.denoiser = 'OPENIMAGEDENOISE'
cy.max_bounces = 12; cy.diffuse_bounces = 3; cy.glossy_bounces = 6; cy.transmission_bounces = 10
cy.volume_bounces = 1; cy.transparent_max_bounces = 16
cy.caustics_reflective = False; cy.caustics_refractive = False; cy.blur_glossy = 0.8
cy.sample_clamp_indirect = 6.0; cy.use_light_tree = True
r.resolution_x, r.resolution_y = 1600, 2000
r.film_transparent = False
scene.view_settings.view_transform = 'AgX'; scene.view_settings.look = 'AgX - Punchy'
scene.view_settings.exposure = 0.0
r.image_settings.file_format = 'PNG'; r.image_settings.color_depth = '16'

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "nautile.blend"), compress=True)
print("SAVED", sum(len(o.data.vertices) for o in bpy.data.objects if o.type == 'MESH'), "base verts")
