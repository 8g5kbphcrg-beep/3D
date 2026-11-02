"""NAUTILE — material library. Every surface is procedural (no image textures)."""
import bpy
from lib import Shader


def tangent_radial(S):
    return S.node("ShaderNodeTangent", direction_type='RADIAL', axis='Z').outputs[0]


def shell_outer():
    """Glossy porcelain shell with flame stripes (Nautilus pompilius), driven by UV = (turns, phi/pi)."""
    S = Shader("Shell_Outer")
    uv = S.sep(S.uv())
    u, v = uv[0], uv[1]
    n1 = S.noise(S.uv(), scale=7.0, detail=6, rough=0.6)
    wob = S.math('MULTIPLY', S.math('SUBTRACT', n1.outputs[0], 0.5), 1.6)
    bend = S.math('MULTIPLY', S.math('SINE', S.math('MULTIPLY', v, 2.6)), 0.55)
    s = S.math('ADD', S.math('ADD', S.math('MULTIPLY', u, 13.0), bend), wob)
    band = S.math('MULTIPLY', S.math('ADD', S.math('SINE', S.math('MULTIPLY', s, 6.2832)), 1.0), 0.5)
    # width variation along the stripe
    wv = S.noise(S.uv(), scale=2.5, detail=2).outputs[0]
    thr = S.maprange(wv, 0.3, 0.7, 0.62, 0.38)
    stripe = S.maprange(S.math('SUBTRACT', band, thr), -0.03, 0.06)
    fade_ap = S.maprange(u, -0.42, -0.13, 1.0, 0.0, interp='SMOOTHSTEP')
    fade_v = S.maprange(v, 0.0, 0.3, 0.15, 1.0, interp='SMOOTHSTEP')
    fac = S.math('MULTIPLY', S.math('MULTIPLY', stripe, fade_ap), fade_v)
    cream = S.ramp(S.noise(S.uv(), scale=40, detail=3).outputs[0],
                   [(0.3, (0.80, 0.72, 0.58)), (0.7, (0.88, 0.82, 0.70))])
    brown = S.ramp(band, [(0.4, (0.42, 0.17, 0.06)), (0.8, (0.22, 0.07, 0.025))])
    col = S.mix(fac, cream, brown)
    # growth lines (fine ridges across the whorl) + micro pitting
    gl = S.math('SINE', S.math('ADD', S.math('MULTIPLY', u, 1400.0), S.math('MULTIPLY', n1.outputs[0], 9.0)))
    micro = S.noise(None, scale=900, detail=2).outputs[0]
    h = S.math('ADD', S.math('MULTIPLY', gl, 0.6), micro)
    nrm = S.bump(h, strength=0.12, distance=0.0015)
    bsdf = S.principled(Base_Color=col, Roughness=S.maprange(micro, 0.3, 0.7, 0.18, 0.32),
                        Coat_Weight=0.9, Coat_Roughness=0.045, Coat_IOR=1.55, Normal=nrm, Coat_Normal=nrm,
                        Subsurface_Weight=0.12, Subsurface_Radius=(0.9, 0.5, 0.25), Subsurface_Scale=0.01)
    return S.output(bsdf)


def nacre(name="Nacre", strength=1.0):
    """Mother-of-pearl: view-dependent pastel interference colours + thin-film specular + growth ridges."""
    S = Shader(name)
    co = S.coord('Object')
    warp = S.noise(co, scale=3.0, detail=5, rough=0.55, dist=1.2)
    tf = S.maprange(warp.outputs[0], 0.25, 0.75, 260.0, 760.0 * strength)
    wave = S.node("ShaderNodeTexWave", {"Scale": 22.0, "Distortion": 9.0, "Detail": 4.0, "Detail Scale": 2.0},
                  wave_type='RINGS', rings_direction='Z', wave_profile='SIN')
    S.set(wave.inputs["Vector"], co)
    lw = S.node("ShaderNodeLayerWeight", {"Blend": 0.35})
    idx = S.math('FRACT', S.math('ADD', S.math('MULTIPLY', lw.outputs["Facing"], 1.6),
                                 S.math('MULTIPLY', warp.outputs[0], 1.4 * strength)))
    irid = S.ramp(idx, [(0.0, (0.44, 0.38, 0.46)), (0.18, (0.32, 0.42, 0.54)), (0.36, (0.30, 0.48, 0.44)),
                        (0.54, (0.52, 0.47, 0.32)), (0.72, (0.54, 0.36, 0.40)), (0.9, (0.38, 0.35, 0.52)),
                        (1.0, (0.44, 0.38, 0.46))])
    base = S.mix(S.maprange(wave.outputs[1], 0, 1, 0.0, 0.3), irid, (0.66, 0.64, 0.61))
    nrm = S.bump(S.math('ADD', wave.outputs[1], S.math('MULTIPLY', S.noise(None, 600, 2).outputs[0], 0.4)),
                 strength=0.08, distance=0.002)
    bsdf = S.principled(Base_Color=base, Metallic=0.18, Roughness=S.maprange(wave.outputs[1], 0, 1, 0.12, 0.26),
                        Thin_Film_Thickness=tf, Thin_Film_IOR=1.62, IOR=1.6, Normal=nrm,
                        Coat_Weight=0.5, Coat_Roughness=0.06, Coat_IOR=1.52, Coat_Normal=nrm,
                        Sheen_Weight=0.25, Sheen_Roughness=0.3, Sheen_Tint=(0.8, 0.85, 1.0))
    return S.output(bsdf)


def section():
    """Sawn shell edge: layered prismatic/nacreous porcelain."""
    S = Shader("Shell_Section")
    co = S.coord('Object')
    lines = S.node("ShaderNodeTexWave", {"Scale": 60.0, "Distortion": 3.0, "Detail": 3.0},
                   wave_type='RINGS', rings_direction='SPHERICAL')
    S.set(lines.inputs["Vector"], co)
    col = S.ramp(lines.outputs[1], [(0.0, (0.86, 0.82, 0.74)), (0.6, (0.93, 0.91, 0.86)), (1.0, (0.80, 0.74, 0.64))])
    bsdf = S.principled(Base_Color=col, Roughness=0.32, Subsurface_Weight=0.25, Subsurface_Scale=0.006,
                        Subsurface_Radius=(1.0, 0.7, 0.45), Thin_Film_Thickness=380.0, Thin_Film_IOR=1.35,
                        Normal=S.bump(S.noise(None, 1500, 2).outputs[0], 0.05, 0.001))
    return S.output(bsdf)


def gold(name="Gold_Grained", color=(1.0, 0.77, 0.42), rough=0.2, aniso=0.75):
    S = Shader(name)
    t = tangent_radial(S)
    var = S.noise(None, scale=60, detail=4).outputs[0]
    scr = S.noise(None, scale=3000, detail=1, dims='3D').outputs[0]
    bsdf = S.principled(Base_Color=color, Metallic=1.0, Roughness=S.maprange(var, 0.3, 0.7, rough * 0.8, rough * 1.25),
                        Anisotropic=aniso, Tangent=t, Normal=S.bump(scr, 0.04, 0.0005))
    return S.output(bsdf)


def metal(name, color, rough, aniso=0.0, radial=False, thin_film=0.0):
    S = Shader(name)
    kw = dict(Base_Color=color, Metallic=1.0, Roughness=rough)
    if aniso:
        kw.update(Anisotropic=aniso, Tangent=tangent_radial(S) if radial else
                  S.node("ShaderNodeTangent", direction_type='UV_MAP', uv_map="UVMap").outputs[0])
    if thin_film:
        kw.update(Thin_Film_Thickness=thin_film, Thin_Film_IOR=2.2)
    nz = S.noise(None, scale=1800, detail=1).outputs[0]
    kw.update(Normal=S.bump(nz, 0.03, 0.0004))
    return S.output(S.principled(**kw))


def ruby():
    S = Shader("Ruby")
    bsdf = S.principled(Base_Color=(0.9, 0.03, 0.08), Transmission_Weight=1.0, IOR=1.77, Roughness=0.02)
    vol = S.node("ShaderNodeVolumeAbsorption", {"Color": (0.95, 0.05, 0.12), "Density": 60.0})
    return S.output(bsdf, volume=vol)


def sapphire_crystal():
    S = Shader("Sapphire_Crystal")
    glass = S.principled(Base_Color=(1, 1, 1), Transmission_Weight=1.0, IOR=1.77, Roughness=0.0, Thin_Wall=True,
                         Specular_IOR_Level=0.22, Thin_Film_Thickness=140.0, Thin_Film_IOR=1.38)
    lp = S.node("ShaderNodeLightPath")
    tr = S.node("ShaderNodeBsdfTransparent")
    m = S.node("ShaderNodeMixShader")
    S.set(m.inputs[0], lp.outputs["Is Shadow Ray"])
    S.set(m.inputs[1], glass); S.set(m.inputs[2], tr.outputs[0])
    return S.output(m.outputs[0])


def carbon_twill(name="Carbon_Twill", scale=90.0):
    """2x2 twill weave, UV driven, anisotropic tows under a glossy epoxy coat."""
    S = Shader(name)
    uv = S.vmath('SCALE', S.uv(), scale=scale)
    xy = S.sep(uv)
    fx, fy = S.math('FLOOR', xy[0]), S.math('FLOOR', xy[1])
    par = S.math('FLOORED_MODULO', S.math('FLOOR', S.math('DIVIDE', S.math('ADD', fx, fy), 2.0)), 2.0)

    frx, fry = S.math('FRACT', xy[0]), S.math('FRACT', xy[1])
    h0 = S.math('SINE', S.math('MULTIPLY', fry, 3.14159))
    h1 = S.math('SINE', S.math('MULTIPLY', frx, 3.14159))
    h = S.mixf(par, h0, h1)
    hh = S.math('POWER', h, 0.5)
    fib = S.noise(S.vmath('SCALE', uv, scale=6.0), scale=8.0, detail=2).outputs[0]
    tint = S.mix(fib, (0.010, 0.011, 0.012), (0.035, 0.036, 0.04))
    tan = S.node("ShaderNodeTangent", direction_type='UV_MAP', uv_map="UVMap").outputs[0]
    bsdf = S.principled(Base_Color=tint, Metallic=0.35, Roughness=0.32, Anisotropic=0.9,
                        Anisotropic_Rotation=S.math('MULTIPLY', par, 0.25), Tangent=tan,
                        Normal=S.bump(hh, 0.35, 0.002), Coat_Weight=1.0, Coat_Roughness=0.025, Coat_IOR=1.5)
    return S.output(bsdf)


def forged_carbon():
    S = Shader("Forged_Carbon")
    co = S.vmath('SCALE', S.coord('Object'), scale=1.0)
    dist = S.noise(co, scale=4, detail=3).outputs[1]
    co2 = S.vmath('ADD', co, S.vmath('SCALE', dist, scale=0.08))
    vo = S.voronoi(co2, scale=6.0, rand=1.0)
    rot = S.sep(vo.outputs["Color"])[0]
    tint = S.mix(S.sep(vo.outputs["Color"])[1], (0.003, 0.003, 0.004), (0.16, 0.16, 0.17))
    edge = S.voronoi(co2, scale=6.0, feature='DISTANCE_TO_EDGE')
    bsdf = S.principled(Base_Color=tint, Metallic=0.85, Roughness=0.22, Anisotropic=1.0, Anisotropic_Rotation=rot,
                        Normal=S.bump(S.maprange(edge.outputs[0], 0, 0.05), 0.15, 0.001),
                        Coat_Weight=1.0, Coat_Roughness=0.03)
    return S.output(bsdf)


def granite():
    """Nero Assoluto: polished top, honed sides, mica glints."""
    S = Shader("Granite_Nero")
    co = S.coord('Object')
    sp = S.voronoi(co, scale=180.0, rand=1.0)
    spk = S.math('GREATER_THAN', S.sep(sp.outputs["Color"])[0], 0.975)
    cloud = S.noise(co, scale=6, detail=6, rough=0.6).outputs[0]
    base = S.mix(S.maprange(cloud, 0.3, 0.7), (0.004, 0.004, 0.0045), (0.011, 0.011, 0.012))
    col = S.mix(spk, base, (0.12, 0.12, 0.13))
    nz = S.sep(S.node("ShaderNodeNewGeometry").outputs["Normal"])[2]
    top = S.math('GREATER_THAN', nz, 0.95)
    scr = S.node("ShaderNodeTexWave", {"Scale": 3.0, "Distortion": 30.0, "Detail": 2}, wave_type='BANDS')
    S.set(scr.inputs["Vector"], S.vmath('MULTIPLY', co, (40, 2, 1)))
    rtop = S.maprange(scr.outputs[1], 0.0, 1.0, 0.035, 0.07)
    rough = S.mixf(top, 0.3, rtop)
    bsdf = S.principled(Base_Color=col, Roughness=rough, Metallic=S.math('MULTIPLY', spk, 0.6),
                        Normal=S.bump(S.noise(co, 300, 3).outputs[0], S.mixf(top, 0.25, 0.01), 0.002))
    return S.output(bsdf)


def floor():
    S = Shader("Floor_WetSlate")
    co = S.coord('Object')
    n = S.noise(co, scale=1.7, detail=8, rough=0.6).outputs[0]
    wet = S.maprange(n, 0.55, 0.62)
    bsdf = S.principled(Base_Color=S.mix(wet, (0.012, 0.013, 0.015), (0.004, 0.0045, 0.005)),
                        Roughness=S.maprange(n, 0.3, 0.7, 0.2, 0.42),
                        Normal=S.bump(S.noise(co, 40, 6).outputs[0], S.mixf(wet, 0.3, 0.02), 0.01))
    return S.output(bsdf)


def marine_snow():
    S = Shader("Marine_Snow")
    bsdf = S.principled(Base_Color=(0.8, 0.85, 0.9), Roughness=0.6, Emission_Color=(0.6, 0.8, 1.0),
                        Emission_Strength=0.12, Transmission_Weight=0.3)
    return S.output(bsdf)


def fog(density=0.003):
    S = Shader("Abyss_Haze")
    vol = S.node("ShaderNodeVolumePrincipled", {"Density": density, "Anisotropy": 0.55,
                                                  "Color": (0.75, 0.85, 0.95)})
    return S.output(None, volume=vol.outputs[0]) if False else _vol_only(S, vol)


def _vol_only(S, vol):
    S.set(S.out.inputs["Volume"], vol.outputs[0])
    return S.mat


def lacquer():
    S = Shader("Blue_Lacquer")
    return S.output(S.principled(Base_Color=(0.002, 0.007, 0.04), Roughness=0.3, Coat_Weight=1.0,
                                 Coat_Roughness=0.05))


def build_all():
    M = {}
    M['outer'] = shell_outer()
    M['nacre'] = nacre()
    M['nacre_sep'] = nacre("Nacre_Septa", 0.8)
    M['section'] = section()
    M['gold'] = gold()
    M['gold_pol'] = gold("Gold_Polished", rough=0.06, aniso=0.0)
    M['rosegold'] = metal("Rose_Gold", (0.96, 0.64, 0.52), 0.09)
    M['steel'] = metal("Steel_Polished", (0.78, 0.78, 0.80), 0.06)
    M['blued'] = metal("Blued_Steel", (0.03, 0.09, 0.62), 0.14, thin_film=0.0)
    M['steel_sun'] = gold("Steel_Circular", color=(0.74, 0.75, 0.78), rough=0.14, aniso=0.85)
    M['ti'] = metal("Titanium_Brushed", (0.55, 0.53, 0.50), 0.26, aniso=0.8, radial=True)
    M['ti_pol'] = metal("Titanium_Polished", (0.60, 0.58, 0.56), 0.07)
    M['ruby'] = ruby()
    M['crystal'] = sapphire_crystal()
    M['carbon'] = carbon_twill()
    M['forged'] = forged_carbon()
    M['granite'] = granite()
    M['floor'] = floor()
    M['snow'] = marine_snow()
    M['fog'] = fog()
    M['lacquer'] = lacquer()
    return M
