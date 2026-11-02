"""Render the movement loop: python3 anim_render.py CAMERA outdir resx resy samples [start end]"""
import sys, os, bpy
a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
cam, out, rx, ry, spp = a[0], a[1], int(a[2]), int(a[3]), int(a[4])
bpy.ops.wm.open_mainfile(filepath=os.path.join(os.path.dirname(os.path.abspath(__file__)), "nautile.blend"))
sc = bpy.context.scene
sc.camera = bpy.data.objects[cam]
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, 100
sc.cycles.samples = spp
# animation-only speedups: the haze barely reads in the macro framing
bpy.data.objects["Abyss_Haze"].hide_render = True
bpy.data.objects["Marine_Snow"].hide_render = True
cy = sc.cycles
cy.adaptive_threshold = 0.04; cy.max_bounces = 6; cy.glossy_bounces = 3; cy.transmission_bounces = 4
cy.diffuse_bounces = 2; cy.transparent_max_bounces = 8
sc.render.use_persistent_data = True
sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.004, 0.009, 0.016, 1)
sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_depth = '8'
if len(a) > 6:
    sc.frame_start, sc.frame_end = int(a[5]), int(a[6])
sc.render.filepath = os.path.abspath(out) + "/f_"
bpy.ops.render.render(animation=True)
print("DONE")
