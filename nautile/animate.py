"""NAUTILE — animate the movement + organise the scene into collections.

Seamless 120-frame loop (5 s @ 24 fps):
  * tourbillon cage: 120°, which is a symmetry of its three-arm cage
  * balance: ±220° oscillation, 2 Hz (10 full beats per loop), carried by the cage
  * chamber gears: one full turn per loop, alternating direction (meshing look)
  * intermediate wheel: one turn; barrel drum + cover: 72° (5-spoke symmetry, 22 teeth)
  * contrate pinion: two turns
Every rotation is about the part's own axis (local Z); keyframes are linear or baked,
so the loop repeats without a visible seam.
"""
import math
import bpy
from mathutils import Matrix

LOOP = 120
TAU = 2 * math.pi


def _linear(ob, total_angle, axis=2):
    ob.rotation_mode = 'XYZ'
    base = ob.rotation_euler[axis]
    for f, a in ((1, 0.0), (1 + LOOP, total_angle)):
        ob.rotation_euler[axis] = base + a
        ob.keyframe_insert("rotation_euler", index=axis, frame=f)
    fc = _fcurve(ob, axis)
    for k in fc.keyframe_points:
        k.interpolation = 'LINEAR'
    fc.extrapolation = 'LINEAR'
    ob.rotation_euler[axis] = base


def _fcurve(ob, index):
    ad = ob.animation_data
    act = ad.action
    # Blender 5 layered actions: walk the channelbag of the object's slot
    try:
        cb = act.layers[0].strips[0].channelbag(ad.action_slot)
        fcs = cb.fcurves
    except Exception:
        fcs = act.fcurves
    for fc in fcs:
        if fc.data_path == "rotation_euler" and fc.array_index == index:
            return fc
    raise RuntimeError("fcurve not found for " + ob.name)


def _baked(ob, fn):
    """fn(frame_index 0..LOOP-1) -> angle; one keyframe per frame, repeated by a Cycles modifier."""
    ob.rotation_mode = 'XYZ'
    base = ob.rotation_euler[2]
    for i in range(LOOP + 1):
        ob.rotation_euler[2] = base + fn(i)
        ob.keyframe_insert("rotation_euler", index=2, frame=1 + i)
    fc = _fcurve(ob, 2)
    for k in fc.keyframe_points:
        k.interpolation = 'LINEAR'
    ob.rotation_euler[2] = base


def _pivot(ob):
    """Put ob under an empty that carries its current transform, so local Z is its own axis."""
    pv = bpy.data.objects.new(ob.name + "_Axis", None)
    pv.empty_display_type = 'SINGLE_ARROW'; pv.empty_display_size = 0.08
    for c in ob.users_collection:
        c.objects.link(pv)
    pv.parent = ob.parent
    pv.matrix_parent_inverse = ob.matrix_parent_inverse.copy()
    pv.matrix_basis = ob.matrix_basis.copy()
    ob.parent = pv
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = Matrix.Identity(4)
    return ob


def setup(scene):
    O = bpy.data.objects
    scene.frame_start, scene.frame_end = 1, LOOP
    scene.render.fps = 24
    cage_rate = (TAU / 3) / LOOP

    cage = ["T_CageLower", "T_CageUpper", "T_Pillars", "T_EscapeWheel", "T_Lever", "T_SecondsHand",
            "T_Screws", "T_Chatons", "T_Rubies", "T_Hairspring"]
    for n in cage:
        _linear(O[n], TAU / 3)
    amp = math.radians(220)
    for n in ("T_BalanceWheel", "T_TimingScrews"):
        _baked(O[n], lambda i: cage_rate * i + amp * math.sin(TAU * i / 12))

    gears = sorted((o for o in O if o.name.startswith("Gear_") and o.type == "MESH"), key=lambda o: o.name)
    for k, g in enumerate(gears):
        _linear(_pivot(g), TAU * (1 if k % 2 == 0 else -1))
    _linear(_pivot(O["Third_Wheel"]), -TAU)
    _linear(_pivot(O["Contrate_Pinion"]), 2 * TAU)
    for n in ("B_Drum", "B_Cover"):
        _linear(O[n], TAU / 5)


def organise(scene):
    root = scene.collection
    groups = {
        "Lumieres": lambda o: o.type == 'LIGHT',
        "Cameras": lambda o: o.type == 'CAMERA' or o.name.startswith("Focus_"),
        "Coquille": lambda o: o.name.split("_")[0] in ("Shell", "Septa", "Siphuncle") or o.name.startswith(("Gear_", "Contrate")),
        "Mouvement": lambda o: o.name.startswith(("Tourbillon", "T_", "Barrel", "B_", "Third_Wheel", "Bridge")),
        "Habillage": lambda o: o.name.startswith(("Bezel", "Sapphire", "Lacquer", "Track_", "Numeral", "Prongs", "NAUTILE_Rig")),
        "Support": lambda o: o.name.startswith(("Yoke", "Pivot", "Stem", "Plinth", "Sig_")),
        "Environnement": lambda o: o.name in ("Floor", "Abyss_Haze", "Marine_Snow"),
    }
    cols = {}
    for name in groups:
        c = bpy.data.collections.new(name); root.children.link(c); cols[name] = c
    for o in list(root.objects):
        dest = next((n for n, test in groups.items() if test(o)), "Coquille")
        cols[dest].objects.link(o)
        root.objects.unlink(o)
