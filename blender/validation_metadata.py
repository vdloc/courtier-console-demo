"""Stamp validation metadata onto every structural object.

Run after the frame is built and before it is exported:

    blender -b -P blender/generate_structure.py \
            -P blender/validation_metadata.py

Writes five custom properties per object. They ride into the GLB through
export_extras on the same channel as the tags generate_structure.py
already writes, so the viewer reads them off object.userData with no
side-car lookup:

    validation_type     Steel Beam
    dimensions          "6.800 x 0.220 x 0.600"      metres, world axes
    position            "3.800, 6.000, 3.100"        centre, metres
    connected_objects   "Steel_Column_Main_L00_B1, ..."
    validation_status   VALID | CHECK

Connectivity is measured, not assumed: two objects are connected when
their world bounding boxes touch within a 5 mm tolerance. That is the
same test the audit uses for orphaned plates, so the two agree by
construction.
"""

import bpy

TOL = 0.005
MAX_LISTED = 4

# Run this BEFORE assembly_animation.py. The animation keys every object to
# an exploded start position, and matrix_world is evaluated at the current
# frame - annotate afterwards and 2032 of 2993 members report as touching
# nothing, because at frame 1 they genuinely are.

# Fasteners are excluded. A bolt's connections are not something anyone
# inspects in the viewer, and 1888 bolts and welds carrying a neighbour list
# each tripled the GLB on their own.
SKIP = ("Bolt", "Weld")

# Name prefix -> the human type the report asks for.
TYPES = (
    ("Steel_Column_Main", "Steel Column"),
    ("Steel_Beam_", "Steel Beam"),
    ("Steel_Brace_", "Steel Brace"),
    ("Pipe_", "MEP Pipe"),
    ("Bolt_", "Bolt"),
    ("Weld_", "Weld"),
    ("Plate_EndPlate", "End Plate"),
    ("Plate_Splice", "Splice Plate"),
    ("Plate_Base", "Base Plate"),
    ("Bracket_Stiffener", "Stiffener Rib"),
    ("Bracket_Gusset", "Gusset Plate"),
    ("Concrete_Pad", "Concrete Pad"),
    ("Rail_", "Edge Protection"),
)

# What each type has to be touching to count as connected. A member that
# touches nothing it should be touching is the thing worth flagging.
EXPECTS = {
    "Steel Beam": ("Steel Column",),
    "Steel Column": ("Base Plate", "Steel Column", "Steel Beam"),
    "Base Plate": ("Concrete Pad", "Steel Column"),
    "End Plate": ("Steel Beam", "Steel Column"),
    "Splice Plate": ("Steel Column",),
    "Stiffener Rib": ("Steel Beam", "End Plate", "Steel Column"),
    "Steel Brace": ("Steel Column",),
    "Bolt": ("End Plate", "Splice Plate", "Base Plate", "Steel Column",
             "Steel Beam", "Concrete Pad"),
}


def kind(name):
    for prefix, label in TYPES:
        if name.startswith(prefix):
            return label
    return None


def world_box(o):
    pts = [o.matrix_world @ v.co for v in o.data.vertices]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return lo, hi


def touching(a, b):
    return all(a[0][i] - TOL <= b[1][i] and b[0][i] - TOL <= a[1][i]
               for i in range(3))


def annotate():
    # matrix_world is evaluated lazily; without this every object still
    # reports the matrix it had before it was placed.
    bpy.context.view_layer.update()

    objs = [o for o in bpy.data.objects
            if o.type == 'MESH' and kind(o.name) and kind(o.name) not in SKIP]
    boxes = {o.name: world_box(o) for o in objs}

    # Broad phase on X so this stays a few hundred thousand tests rather
    # than five million.
    order = sorted(objs, key=lambda o: boxes[o.name][0][0])
    links = {o.name: [] for o in objs}
    for i, a in enumerate(order):
        alo, ahi = boxes[a.name]
        for b in order[i + 1:]:
            if boxes[b.name][0][0] > ahi[0] + TOL:
                break
            if touching(boxes[a.name], boxes[b.name]):
                links[a.name].append(b.name)
                links[b.name].append(a.name)

    checked = 0
    for o in objs:
        label = kind(o.name)
        lo, hi = boxes[o.name]
        neighbours = links[o.name]
        wanted = EXPECTS.get(label)
        ok = True
        if wanted:
            ok = any(kind(n) in wanted for n in neighbours)

        o["validation_type"] = label
        o["dimensions"] = "%.3f x %.3f x %.3f" % tuple(
            hi[i] - lo[i] for i in range(3))
        o["position"] = "%.3f, %.3f, %.3f" % tuple(
            (lo[i] + hi[i]) * 0.5 for i in range(3))
        o["connected_objects"] = ", ".join(sorted(neighbours)[:MAX_LISTED])
        o["validation_status"] = "VALID" if ok else "CHECK"
        if not ok:
            checked += 1
            print("[validation] CHECK %s (%s) touches %d objects, none of %s"
                  % (o.name, label, len(neighbours), wanted))

    print("[validation] %d objects annotated, %d VALID, %d CHECK"
          % (len(objs), len(objs) - checked, checked))


annotate()
