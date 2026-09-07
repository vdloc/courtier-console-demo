"""Negative control for the collision checks.

A clean audit proves nothing unless the instrument can fail. Break four
things on purpose, one per check, and confirm each is caught.

    blender -b -P blender/generate_structure.py -P blender/scene_setup.py \
            -P blender/audit_selftest.py -P blender/audit_geometry.py
"""

import bpy

bpy.context.view_layer.update()


def first(prefix):
    for o in bpy.data.objects:
        if o.name.startswith(prefix):
            return o
    raise SystemExit("no object named %s*" % prefix)


# 1. Slide a beam along its own axis: gap at one end, penetration at the other.
beam = first("Steel_Beam_Floor_Primary_L01")
beam.location.x += 0.050
print("[fault] slid %s +50 mm in X" % beam.name)

# 2. Lift a different beam off the floor datum.
beam2 = first("Steel_Beam_Floor_Edge_L02")
beam2.location.z += 0.040
print("[fault] raised %s +40 mm in Z" % beam2.name)

# 3. Send a bolt into open air.
bolt = first("Bolt_M24_EndPlate_L01")
bolt.location.y += 3.0
print("[fault] moved %s 3 m off its plate" % bolt.name)

# 4. Drive a pipe up into the beams above it.
pipe = first("Pipe_Main_Curved_L01")
pipe.location.z += 0.60
print("[fault] raised %s +600 mm into the steel" % pipe.name)

bpy.context.view_layer.update()
