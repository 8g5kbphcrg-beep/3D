"""Render a camera of nautile.blend.
python3 render.py CAM_Hero out.png [scale%] [samples] [resx resy]"""
import sys, os, bpy
args = sys.argv[1:]
cam, out = args[0], args[1]
pct = int(args[2]) if len(args) > 2 else 100
spp = int(args[3]) if len(args) > 3 else 256
bpy.ops.wm.open_mainfile(filepath=os.path.join(os.path.dirname(os.path.abspath(__file__)), "nautile.blend"))
sc = bpy.context.scene
sc.camera = bpy.data.objects[cam]
if len(args) > 5:
    sc.render.resolution_x, sc.render.resolution_y = int(args[4]), int(args[5])
sc.render.resolution_percentage = pct
sc.cycles.samples = spp
sc.cycles.device = 'CPU'
sc.render.threads_mode = 'AUTO'
sc.render.filepath = os.path.abspath(out)
bpy.ops.render.render(write_still=True)
print("DONE", out)
