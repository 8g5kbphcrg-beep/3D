# NAUTILE — Calibre Φ 1.618

*A sectioned Nautilus pompilius that has grown its own haute-horlogerie movement.*

The shell is cut along its plane of symmetry and shows its 32 pearly chambers. The **siphuncle**, the thin tube a real nautilus uses to adjust its buoyancy, becomes a gold drive shaft. Each chamber holds a gear whose size follows the shell's logarithmic growth, so the gears form a golden spiral. In the last chamber (the body chamber), the shaft drives a **mainspring barrel**, then an intermediate wheel, then a **tourbillon** with a three-arm cage, a balance with timing screws and a 13-turn blued hairspring.
The shell floats inside a brushed titanium bezel, held by three claws under a sapphire crystal. Fibonacci numbers (144 · 1 · 1 · 2 · 3 · 5 · 8 · 13 · 21 · 34 · 55 · 89) stand in for the hours. The bezel sits in a twill-carbon yoke on a block of Nero Assoluto granite.
Setting: a dark "abyssal" studio with blue haze and marine snow drifting through the depth of field.

## Contents

| File | Role |
|---|---|
| `nautile.blend` | Complete Blender 5.2 scene: geometry, materials, lights, 4 cameras, Cycles settings |
| `build.py` | Generates the whole scene procedurally (shell, septa, gear train, tourbillon, bezel, stand, lighting) |
| `materials.py` | 21 fully procedural materials (no image textures) |
| `lib.py` | Geometry generators (lathe, sweeps, watch wheels, screws, jewels) + a shader-node DSL |
| `animate.py` | Animates the movement (120-frame seamless loop) and sorts the scene into collections |
| `anim_render.py` | Renders the animation: `python3 anim_render.py CAM_Macro renders/anim 1120 630 16` |
| `render.py` | Renders one camera: `python3 render.py CAM_Hero out.png 100 128 1600 2000` |
| `renders/` | Final renders |

## Rebuild

```bash
pip install bpy==5.2.3        # Blender as a Python module (or open nautile.blend in Blender 5.2+)
python3 build.py              # -> nautile.blend
./final.sh                    # -> renders/*.png
```

## Animation

Seamless 5 s loop (120 frames at 24 fps), stored as keyframes in `nautile.blend`. Press Play in Blender to watch the movement turn:
- tourbillon cage: 120° per loop, which brings the three-arm cage back to an identical position;
- balance: ±220° at 2 Hz, carried by the cage;
- chamber gears: one turn per loop, alternating direction (each gear turns about its own axis through a `*_Axis` empty);
- intermediate wheel: one turn; barrel: 72° (5-spoke symmetry); contrate pinion: two turns.

Collections: Coquille, Mouvement, Habillage, Support, Environnement, Lumieres, Cameras.

## Construction notes

- **Shell**: log spiral `r = r0·e^(bθ)` with a growth factor of 3.0 per turn (the real nautilus value), a half-elliptical section swept over 3.6 turns, then Solidify with thickness proportional to radius (vertex group). Separate materials for the outer surface (flame stripes generated from the growth parameters), the inner nacre and the saw-cut edge.
- **Septa**: domed surfaces convex toward the apex (each sag is computed in spiral coordinates, so it stays inside the tube), solidified, with gold collars where the siphuncle passes through.
- **Wheels**: watch-style tooth profile, curved spokes, hub, pinion, arbor, ruby in a gold chaton. Tooth counts scale with size.
- **Tourbillon / barrel**: about 15 assembled sub-components (cages, pillars, balance, timing screws, Archimedean hairspring, escape wheel, lever, mainspring, sawtooth ratchet, click, slotted screws).
- **Materials**: thin-film nacre with view-dependent iridescence, gold and steel with circular graining (radial anisotropy), blued steel, absorbing ruby, AR-coated sapphire (thin film, shadow-transparent), 2×2 twill carbon with alternating tow anisotropy, forged carbon (Voronoi flakes), polished/honed granite with mica glints, wet slate.
- **Render**: Cycles CPU, AgX Punchy, OIDN, 7-blade bokeh, volumetric haze, light tree.

Detail: there are **34 rubies** in the movement (26 + 6 + 1 + 1). That is also a Fibonacci number.
