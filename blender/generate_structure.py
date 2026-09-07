"""
Procedural structural frame generator for Blender 5.x (also runs on 4.2+).

Builds a multi-storey industrial steel frame from a single parameter table:
columns (RHS), beams (I-section), bracing (CHS), bolted connections (base
plates, gussets, splice plates, bolts, fillet welds), routed MEP pipework and
edge protection. Everything is generated from CONFIG - no hand modelling - so
the grid, storey heights and section sizes change in one place.

Geometry follows the interpretation document at
docs/interpretation/2026-09-06-rc-frame-bim-interpretation.md: a 4 x 3 bay grid
at 7.2 m / 6.0 m, four storeys at 3.4 m, origin at grid A-1 finished floor
level, Z-up in Blender and Y-up after glTF export.

Set CONFIG["profile_mode"] to "RC" to build the reference-faithful reinforced
concrete variant instead (solid sections, no bolted hardware).

Run inside Blender:

    Scripting workspace -> Open -> Run Script

Run headless and export a GLB:

    blender -b -P blender/generate_structure.py -- --export dist/structure.glb

Add the erection sequence:

    blender -b -P blender/generate_structure.py -- --export dist/structure.glb --animate
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

# ---------------------------------------------------------------------------
# CONFIG - the single source of truth for the whole model
# ---------------------------------------------------------------------------

CONFIG = {
    # --- structural grid, metres -------------------------------------------
    # Bay spacings. len(x_bays) + 1 = number of column lines in X.
    "x_bays": [7.2, 7.2, 7.2, 7.2],       # grid lines 1..5, long facade
    "y_bays": [6.0, 6.0, 6.0],            # grid lines A..D, building depth
    "storeys": [3.4, 3.4, 3.4, 3.4],      # floor-to-floor, L00 -> RF

    # "STEEL": RHS columns, I-section beams, bolted connections.
    # "RC":    solid rectangular concrete sections, no bolted hardware.
    "profile_mode": "STEEL",

    # --- steel sections, metres --------------------------------------------
    # Square hollow sections: outside dimension + wall thickness.
    "col_ground": {"b": 0.400, "h": 0.400, "t": 0.016},   # SHS 400x400x16
    "col_upper": {"b": 0.300, "h": 0.300, "t": 0.012},    # SHS 300x300x12

    # I-sections: overall depth h, flange width b, web thickness tw,
    # flange thickness tf. Values follow IPE600 and IPE400.
    "beam_primary": {"h": 0.600, "b": 0.220, "tw": 0.012, "tf": 0.019},
    "beam_edge": {"h": 0.400, "b": 0.180, "tw": 0.0086, "tf": 0.0135},

    # Circular hollow section used for the ground-storey bracing.
    "brace": {"od": 0.1683, "t": 0.010, "segments": 16},   # CHS 168.3x10

    # --- concrete sections, used when profile_mode == "RC" -----------------
    "rc_col_ground": {"b": 0.500, "h": 0.500},
    "rc_col_upper": {"b": 0.400, "h": 0.400},
    "rc_beam_primary": {"h": 0.600, "b": 0.300},
    "rc_beam_edge": {"h": 0.500, "b": 0.250},

    # --- foundations --------------------------------------------------------
    # No top_z: the pad top is derived from the base plate thickness so the
    # two cannot drift apart. Held as independent numbers they did, and the
    # frame ended up standing on a 60 mm void.
    "pad": {"b": 2.400, "d": 2.400, "t": 0.700},

    # --- connections --------------------------------------------------------
    # Fabrication detail. Each flag adds real objects, so they are switchable:
    # the full set roughly triples the object count, which is right for a
    # marketing render and wrong for a fast turnaround.
    "detail": {
        "shs_corner_radius": True,   # hot-finished SHS have radiused corners
        "root_radius": True,         # rolled I-sections have a web/flange fillet
        "end_plates": True,          # beams bolt to columns, they do not butt
        "stiffeners": True,          # web stiffeners opposite beam flanges
        "nuts_washers": True,        # bolt = head + washer + nut, not a stud
        "shear_studs": False,        # ~3000 more objects; off by default
    },
    "corner_radius_factor": 2.0,     # SHS outer corner radius = 2.0 x wall t
    "root_radius": 0.024,            # IPE600 root fillet, 24 mm
    "profile_arc_segments": 4,       # segments per corner arc

    "end_plate": {"t": 0.020, "margin": 0.060},   # flush end plate
    "stiffener": {"t": 0.012},
    "haunch_rib": 0.140,             # rib depth below the beam bottom flange
    "shear_stud": {"d": 0.019, "h": 0.100, "spacing": 0.300},

    "base_plate": {"b": 0.700, "d": 0.700, "t": 0.040},
    "splice_plate": {"b": 0.320, "h": 0.500, "t": 0.020},
    "splice_lift": 0.600,            # splice height above the floor line
    "rail_offset": 0.250,            # edge protection stands off the frame
    "gusset": {"leg": 0.360, "t": 0.015},
    "bolt": {"shank_d": 0.024, "head_d": 0.042, "head_t": 0.016, "grip": 0.070},
    "weld_leg": 0.010,

    # --- MEP pipework -------------------------------------------------------
    # Routed in the ceiling void beneath the beam soffit.
    "pipes": [
        {"tag": "CHW_MAIN", "od": 0.1143, "spec": "DN100 CS, grooved"},
        {"tag": "LTHW_FLOW", "od": 0.0889, "spec": "DN80 CS, welded"},
        {"tag": "LTHW_RETURN", "od": 0.0889, "spec": "DN80 CS, welded"},
    ],
    "pipe_levels": [1, 2, 3],           # levels that receive a service run
    "pipe_drop": 0.25,                  # clearance below beam soffit
    "pipe_bevel_resolution": 6,         # 6 -> 16-sided tube, enough for web

    # --- accessories --------------------------------------------------------
    "rail": {"height": 1.100, "post_spacing": 2.0, "post": 0.050,
             "rail_d": 0.033, "toe_h": 0.150},
    "make_edge_rails": True,
    "make_bracing": True,

    # --- modelling quality --------------------------------------------------
    "bevel_width": 0.004,               # 4 mm arris - catches a highlight
    "bevel_segments": 2,
    "bevel_angle": math.radians(30.0),

    # --- misc ---------------------------------------------------------------
    "clear_scene": True,
}

# Grid line labels. A-1 is the origin.
X_LABELS = ["1", "2", "3", "4", "5", "6", "7", "8"]
Y_LABELS = ["A", "B", "C", "D", "E", "F", "G", "H"]

ROOT_NAME = "VF_Structure"
GROUPS = ["Foundation", "Columns", "Beams", "Pipes", "Connections", "Accessories"]


# ---------------------------------------------------------------------------
# Scene setup
# ---------------------------------------------------------------------------

def clear_scene():
    """Remove all objects and purge orphaned data so reruns stay clean."""
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    for block_list in (bpy.data.meshes, bpy.data.curves, bpy.data.materials,
                       bpy.data.objects, bpy.data.collections,
                       bpy.data.actions):
        for block in list(block_list):
            if block.users == 0:
                block_list.remove(block)


def setup_units():
    """Metric, metres, with a viewport grid that suits a 7.2 m bay."""
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.system_rotation = "DEGREES"
    scene.unit_settings.length_unit = "METERS"
    scene.unit_settings.scale_length = 1.0

    screen = getattr(bpy.context, "screen", None)
    for area in (screen.areas if screen else []):
        if area.type != "VIEW_3D":
            continue
        for space in area.spaces:
            if space.type == "VIEW_3D":
                space.overlay.grid_scale = 0.5
                space.clip_end = 500.0


def build_hierarchy():
    """Create the collection tree plus a matching tree of empties.

    Collections organise the Blender outliner. The empties are what survives
    glTF export as parent nodes, which is how the Three.js viewer gets its
    layer toggles: traverse one level below VF_Structure.
    """
    root_col = bpy.data.collections.new(ROOT_NAME)
    bpy.context.scene.collection.children.link(root_col)

    root_empty = bpy.data.objects.new(ROOT_NAME, None)
    root_empty.empty_display_type = "PLAIN_AXES"
    root_empty.empty_display_size = 2.0
    root_col.objects.link(root_empty)

    cols, empties = {}, {}
    for name in GROUPS:
        col = bpy.data.collections.new(name)
        root_col.children.link(col)
        cols[name] = col

        empty = bpy.data.objects.new(name, None)
        empty.empty_display_type = "PLAIN_AXES"
        empty.empty_display_size = 1.0
        empty.parent = root_empty
        col.objects.link(empty)
        empties[name] = empty

    return root_empty, cols, empties


# ---------------------------------------------------------------------------
# Grid maths
# ---------------------------------------------------------------------------

def _cumulative(spacings):
    out, run = [0.0], 0.0
    for value in spacings:
        run += value
        out.append(run)
    return out


def grid_x():
    """Absolute X of every column line, starting at 0."""
    return _cumulative(CONFIG["x_bays"])


def grid_y():
    """Absolute Y of every column line, starting at 0."""
    return _cumulative(CONFIG["y_bays"])


def level_z():
    """Absolute Z of each level. L00 = 0.0 (FFL), then cumulative storeys."""
    return _cumulative(CONFIG["storeys"])


def level_name(index):
    """L00, L01, ... with RF for the topmost level."""
    return "RF" if index == len(CONFIG["storeys"]) else "L%02d" % index


def grid_ref(ix, iy):
    return "%s%s" % (Y_LABELS[iy], X_LABELS[ix])


def column_section(level_index):
    """Ground storey carries the most load and gets the heavier section."""
    if CONFIG["profile_mode"] == "RC":
        return CONFIG["rc_col_ground"] if level_index == 0 else CONFIG["rc_col_upper"]
    return CONFIG["col_ground"] if level_index == 0 else CONFIG["col_upper"]


# ---------------------------------------------------------------------------
# Mesh primitives
# ---------------------------------------------------------------------------

def _finalise(bm, name, collection):
    """Turn a bmesh into a linked object with welded verts and sane normals."""
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.validate(verbose=False)

    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    return obj


def extrude_profile(name, outer, inner, length, collection):
    """Extrude a 2D profile along +X into a solid or hollow prism.

    `outer` and `inner` are lists of (y, z) tuples in counter-clockwise order.
    inner=None gives a solid section (I-beam, concrete). Supplying an inner
    loop with the same vertex count gives a hollow section (SHS, CHS) whose
    end caps are a ring of quads rather than a concave n-gon.
    """
    bm = bmesh.new()

    def ring(points, x):
        return [bm.verts.new((x, py, pz)) for (py, pz) in points]

    n = len(outer)
    o0, o1 = ring(outer, 0.0), ring(outer, length)

    for i in range(n):                       # outer skin
        j = (i + 1) % n
        bm.faces.new((o0[i], o0[j], o1[j], o1[i]))

    if inner is None:
        bm.faces.new(tuple(reversed(o0)))    # start cap
        bm.faces.new(tuple(o1))              # end cap
    else:
        i0, i1 = ring(inner, 0.0), ring(inner, length)
        for i in range(n):
            j = (i + 1) % n
            # Inner skin wound the other way so normals face the void.
            bm.faces.new((i0[j], i0[i], i1[i], i1[j]))
            # End caps as quad rings between the two loops.
            bm.faces.new((o0[j], o0[i], i0[i], i0[j]))
            bm.faces.new((o1[i], o1[j], i1[j], i1[i]))

    return _finalise(bm, name, collection)


def _arc(cy, cz, radius, a0, a1, segments):
    """Points along a circular arc, inclusive of both ends."""
    return [(cy + radius * math.cos(a0 + (a1 - a0) * i / segments),
             cz + radius * math.sin(a0 + (a1 - a0) * i / segments))
            for i in range(segments + 1)]


def rect_points(b, h, radius=0.0, segments=None):
    """Rectangle centred on the profile origin, CCW in the YZ plane.

    A non-zero radius rounds the corners, which is what separates a hot-
    finished hollow section from a CAD box: real SHS corners run at roughly
    2x the wall thickness on the outside, and that radius is the first thing
    that catches a highlight along a column edge.
    """
    hb, hh = b * 0.5, h * 0.5
    if radius <= 0.0:
        return [(-hb, -hh), (hb, -hh), (hb, hh), (-hb, hh)]

    radius = min(radius, hb * 0.9, hh * 0.9)
    segments = segments or CONFIG["profile_arc_segments"]
    half_pi = math.pi * 0.5

    points = []
    points += _arc(hb - radius, -hh + radius, radius, -half_pi, 0.0, segments)
    points += _arc(hb - radius, hh - radius, radius, 0.0, half_pi, segments)
    points += _arc(-hb + radius, hh - radius, radius, half_pi, math.pi, segments)
    points += _arc(-hb + radius, -hh + radius, radius, math.pi, 1.5 * math.pi,
                   segments)
    return points


def circle_points(radius, segments):
    """Circle, CCW, in the YZ plane."""
    return [(math.cos(2 * math.pi * i / segments) * radius,
             math.sin(2 * math.pi * i / segments) * radius)
            for i in range(segments)]


def i_section_points(h, b, tw, tf, root_radius=0.0):
    """I-section outline, CCW, centred on its own centroid.

    With `root_radius` the four web-to-flange junctions get a concave fillet,
    which is how a rolled section actually comes out of the mill - the sharp
    inside corner of a CAD I-beam is the single clearest tell that a model was
    drawn rather than rolled. The fillet also removes a stress-raising sharp
    edge from the bevel modifier's path.
    """
    hb, hh, htw = b * 0.5, h * 0.5, tw * 0.5
    if root_radius <= 0.0:
        return [
            (-hb, -hh), (hb, -hh), (hb, -hh + tf), (htw, -hh + tf),
            (htw, hh - tf), (hb, hh - tf), (hb, hh), (-hb, hh),
            (-hb, hh - tf), (-htw, hh - tf), (-htw, -hh + tf), (-hb, -hh + tf),
        ]

    r = min(root_radius, (hb - htw) * 0.8, (hh - tf) * 0.4)
    seg = CONFIG["profile_arc_segments"]
    half_pi = math.pi * 0.5
    yb, yt = -hh + tf, hh - tf          # inner faces of bottom / top flange

    points = [(-hb, -hh), (hb, -hh), (hb, yb)]
    # Bottom-right fillet: from the flange inner face up onto the web.
    points += _arc(htw + r, yb + r, r, 1.5 * math.pi, math.pi, seg)
    # Top-right fillet: off the web back out onto the flange.
    points += _arc(htw + r, yt - r, r, math.pi, half_pi, seg)
    points += [(hb, yt), (hb, hh), (-hb, hh), (-hb, yt)]
    points += _arc(-htw - r, yt - r, r, half_pi, 0.0, seg)
    points += _arc(-htw - r, yb + r, r, 0.0, -half_pi, seg)
    points += [(-hb, yb)]
    return points


def make_box(name, size, collection):
    """Axis-aligned box centred on its own origin."""
    sx, sy, sz = size
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector((sx, sy, sz)), verts=bm.verts)
    return _finalise(bm, name, collection)


def make_wedge(name, leg, thickness, collection):
    """Right-triangle gusset plate: vertical leg on -X, horizontal on +Z."""
    ht = thickness * 0.5
    bm = bmesh.new()
    a = [bm.verts.new(p) for p in ((0.0, -ht, 0.0), (leg, -ht, 0.0),
                                   (0.0, -ht, -leg))]
    b = [bm.verts.new(p) for p in ((0.0, ht, 0.0), (leg, ht, 0.0),
                                   (0.0, ht, -leg))]
    bm.faces.new((a[2], a[1], a[0]))
    bm.faces.new((b[0], b[1], b[2]))
    for i in range(3):
        j = (i + 1) % 3
        bm.faces.new((a[i], a[j], b[j], b[i]))
    return _finalise(bm, name, collection)


# ---------------------------------------------------------------------------
# Modifiers, materials, metadata
# ---------------------------------------------------------------------------

def add_quality_modifiers(obj, bevel=True, width=None, segments=None):
    """Bevel plus weighted normals - the two passes that stop steel reading as CG.

    Blender 4.1 removed mesh auto-smooth, but the Weighted Normal modifier
    still works standalone, so no smooth-by-angle node group is needed.
    """
    if bevel:
        mod = obj.modifiers.new(name="Bevel", type="BEVEL")
        mod.width = CONFIG["bevel_width"] if width is None else width
        mod.segments = CONFIG["bevel_segments"] if segments is None else segments
        mod.limit_method = "ANGLE"
        mod.angle_limit = CONFIG["bevel_angle"]
        mod.miter_outer = "MITER_ARC"
        mod.harden_normals = False       # the weighted-normal pass handles this

    wn = obj.modifiers.new(name="WeightedNormal", type="WEIGHTED_NORMAL")
    wn.mode = "FACE_AREA_WITH_ANGLE"
    wn.weight = 60
    wn.keep_sharp = True


def _material_lib_paths():
    """Directories that might hold materials.py, most specific first."""
    paths = []
    try:
        paths.append(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        pass                       # -P scripts do not always define __file__
    cwd = os.getcwd()
    paths.append(os.path.join(cwd, "blender"))
    paths.append(cwd)
    return paths


def get_material(name):
    """Fetch or create a material.

    Delegates to blender/materials.py when it is importable, which gives the
    full procedural set - paint mottle, wear scratches, concrete blowholes,
    normal-driven dust. The flat presets below are the fallback for running
    this file on its own.
    """
    if name in bpy.data.materials:
        return bpy.data.materials[name]

    # `__file__` is not always defined for a -P script, so try the obvious
    # locations rather than relying on it. Only ImportError is swallowed:
    # catching more would hide a genuine failure inside the library and fall
    # back to flat presets, which is exactly how a broken material set once
    # reached a finished render unnoticed.
    for candidate in _material_lib_paths():
        if candidate and candidate not in sys.path:
            sys.path.insert(0, candidate)
    try:
        import materials as material_lib
    except ImportError:
        material_lib = None

    if material_lib is not None and name in material_lib.MATERIALS:
        return material_lib.get_material(name)

    presets = {
        # name:                    base colour RGBA,        metallic, roughness
        "MAT_Steel_Painted": ((0.29, 0.31, 0.34, 1.0), 0.90, 0.42),
        "MAT_Steel_Galvanised": ((0.62, 0.64, 0.66, 1.0), 0.95, 0.34),
        "MAT_Steel_Bolt": ((0.42, 0.43, 0.45, 1.0), 1.00, 0.28),
        "MAT_Weld_Bead": ((0.34, 0.32, 0.30, 1.0), 0.85, 0.62),
        "MAT_Concrete": ((0.62, 0.61, 0.58, 1.0), 0.00, 0.88),
        "MAT_Pipe_CHW": ((0.16, 0.42, 0.72, 1.0), 0.70, 0.38),
        "MAT_Pipe_LTHW": ((0.72, 0.18, 0.22, 1.0), 0.70, 0.38),
        "MAT_Rail_Safety": ((0.92, 0.72, 0.10, 1.0), 0.30, 0.55),
    }
    colour, metallic, roughness = presets.get(
        name, ((0.5, 0.5, 0.5, 1.0), 0.0, 0.6))

    mat = bpy.data.materials.new(name)
    # Blender 5.x creates the node tree up front and deprecates use_nodes;
    # 4.x still needs the flag flipped.
    if not mat.node_tree:
        mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = colour
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
    return mat


def assign_material(obj, name):
    obj.data.materials.clear()
    obj.data.materials.append(get_material(name))


def tag(obj, element_type, level, ref, section, spec, discipline="STR"):
    """Custom properties ride into the GLB via export_extras.

    The Three.js viewer reads these off object.userData for selection,
    filtering and the annotation panel - no side-car lookup table needed.
    """
    obj["discipline"] = discipline
    obj["element_type"] = element_type
    obj["level"] = level
    obj["grid_ref"] = ref
    obj["section"] = section
    obj["material_spec"] = spec


def parent_to(obj, empty):
    """Parent without moving the child in world space."""
    obj.parent = empty
    obj.matrix_parent_inverse = empty.matrix_world.inverted()


def place(obj, location, rotation=(0.0, 0.0, 0.0)):
    obj.location = location
    obj.rotation_euler = rotation


def copy_modifiers(src, dst):
    """Replicate bevel and weighted-normal settings onto a linked duplicate."""
    for mod in src.modifiers:
        new = dst.modifiers.new(name=mod.name, type=mod.type)
        if mod.type == "BEVEL":
            new.width = mod.width
            new.segments = mod.segments
            new.limit_method = mod.limit_method
            new.angle_limit = mod.angle_limit
            new.miter_outer = mod.miter_outer
        elif mod.type == "WEIGHTED_NORMAL":
            new.mode = mod.mode
            new.weight = mod.weight
            new.keep_sharp = mod.keep_sharp


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def build_foundations(collection, empty):
    """Pad footing under every ground-storey column line."""
    pad = CONFIG["pad"]
    xs, ys = grid_x(), grid_y()
    made = []

    for iy, y in enumerate(ys):
        for ix, x in enumerate(xs):
            ref = grid_ref(ix, iy)
            obj = make_box("Concrete_Pad_Foundation_%s" % ref,
                           (pad["b"], pad["d"], pad["t"]), collection)
            top_z = -CONFIG["base_plate"]["t"]
            place(obj, (x, y, top_z - pad["t"] * 0.5))
            assign_material(obj, "MAT_Concrete")
            add_quality_modifiers(obj, width=0.010)
            tag(obj, "foundation", "L00", ref,
                "%.0fx%.0fx%.0f mm pad" % (pad["b"] * 1000, pad["d"] * 1000,
                                           pad["t"] * 1000),
                "C25/30 concrete, Ø16@150 both ways")
            parent_to(obj, empty)
            made.append(obj)

    return made


def build_columns(collection, empty):
    """One column object per grid node per storey."""
    xs, ys, zs = grid_x(), grid_y(), level_z()
    steel = CONFIG["profile_mode"] == "STEEL"
    made = []

    for li, storey_h in enumerate(CONFIG["storeys"]):
        sec = column_section(li)
        z0 = zs[li]
        lname = level_name(li)

        if steel:
            t = sec["t"]
            # Outer corner radius 2t, inner radius 1t - the geometry a hollow
            # section is actually formed to.
            r_out = (CONFIG["corner_radius_factor"] * t
                     if CONFIG["detail"]["shs_corner_radius"] else 0.0)
            r_in = max(0.0, r_out - t)
            outer = rect_points(sec["b"], sec["h"], r_out)
            inner = rect_points(sec["b"] - 2 * t, sec["h"] - 2 * t, r_in)
            section_txt = "SHS %.0fx%.0fx%.0f" % (sec["b"] * 1000,
                                                  sec["h"] * 1000, t * 1000)
            spec = "S355JR hot-finished hollow section"
            mat = "MAT_Steel_Painted"
            prefix = "Steel_Column_Main"
        else:
            outer = rect_points(sec["b"], sec["h"])
            inner = None
            section_txt = "%.0fx%.0f mm RC" % (sec["b"] * 1000, sec["h"] * 1000)
            spec = "C30/37, 8xØ25 longitudinal, Ø10 links @200"
            mat = "MAT_Concrete"
            prefix = "Concrete_Column_Main"

        for iy, y in enumerate(ys):
            for ix, x in enumerate(xs):
                ref = grid_ref(ix, iy)
                obj = extrude_profile("%s_%s_%s" % (prefix, lname, ref),
                                      outer, inner, storey_h, collection)
                # The profile extrudes along +X, so stand it upright.
                place(obj, (x, y, z0), (0.0, math.radians(-90.0), 0.0))
                assign_material(obj, mat)
                add_quality_modifiers(obj)
                tag(obj, "column", lname, ref, section_txt, spec)
                parent_to(obj, empty)
                made.append(obj)

    return made


def _beam_profile(kind):
    """Return (points, inner, text, spec, material, depth, section)."""
    if CONFIG["profile_mode"] == "STEEL":
        sec = CONFIG["beam_primary"] if kind == "primary" else CONFIG["beam_edge"]
        root = CONFIG["root_radius"] if CONFIG["detail"]["root_radius"] else 0.0
        # Scale the fillet with the section: a 400 deep beam has a smaller
        # root radius than a 600.
        root *= sec["h"] / CONFIG["beam_primary"]["h"]
        pts = i_section_points(sec["h"], sec["b"], sec["tw"], sec["tf"], root)
        txt = "I-section %.0fx%.0f, tw %.1f, tf %.1f" % (
            sec["h"] * 1000, sec["b"] * 1000, sec["tw"] * 1000, sec["tf"] * 1000)
        return (pts, None, txt, "S355JR rolled I-section",
                "MAT_Steel_Painted", sec["h"], sec)

    sec = CONFIG["rc_beam_primary"] if kind == "primary" else CONFIG["rc_beam_edge"]
    pts = rect_points(sec["b"], sec["h"])
    txt = "%.0fx%.0f mm RC" % (sec["b"] * 1000, sec["h"] * 1000)
    return (pts, None, txt, "C30/37, monolithic with slab", "MAT_Concrete",
            sec["h"], sec)


def _beam_end_details(level, ref, origin, yaw, sec, collection, empty):
    """Bolted end-plate connection at one beam end.

    A beam that simply stops at a column face is the clearest CAD tell in the
    whole model - real steel arrives on site with a shop-welded end plate and
    is bolted to the column. This builds that: flush end plate, four M24s,
    fillet welds at both flanges, and a triangular haunch rib.

    `origin` is the beam end face; `yaw` is the beam's plan direction.
    """
    ep = CONFIG["end_plate"]
    made = []
    plate_h = sec["h"] + 2 * ep["margin"]
    plate_b = sec["b"] + 0.040
    forward = Vector((math.cos(yaw), math.sin(yaw), 0.0))
    across = Vector((-math.sin(yaw), math.cos(yaw), 0.0))
    origin = Vector(origin)

    plate = make_box("Plate_EndPlate_%s_%s" % (level, ref),
                     (ep["t"], plate_b, plate_h), collection)
    place(plate, origin, (0.0, 0.0, yaw))
    assign_material(plate, "MAT_Steel_Painted")
    add_quality_modifiers(plate, width=0.002)
    tag(plate, "end_plate", level, ref,
        "%.0fx%.0fx%.0f mm flush end plate" % (plate_b * 1000, plate_h * 1000,
                                               ep["t"] * 1000),
        "S275, shop welded to beam, 4xM24 8.8 to column")
    parent_to(plate, empty)
    made.append(plate)

    # Four bolts, paired just inside each flange - the standard arrangement.
    for dz in (sec["h"] * 0.5 - 0.045, -(sec["h"] * 0.5 - 0.045)):
        for dy in (0.055, -0.055):
            pos = (origin + across * dy + Vector((0.0, 0.0, dz))
                   - forward * (ep["t"] * 0.5))
            bolt = _make_bolt("Bolt_M24_EndPlate_%s_%s_%d%d"
                              % (level, ref, int(dz > 0), int(dy > 0)),
                              collection)
            # Bolts run along the beam axis, so lay them on their side.
            place(bolt, pos, (0.0, math.radians(90.0), yaw))
            assign_material(bolt, "MAT_Steel_Bolt")
            add_quality_modifiers(bolt, width=0.0012)
            tag(bolt, "bolt", level, ref, "M24 8.8", "preloaded HSFG")
            parent_to(bolt, empty)
            made.append(bolt)

    # Fillet welds where the beam flanges meet the plate.
    for dz in (sec["h"] * 0.5, -sec["h"] * 0.5):
        weld = _weld_fillet("Weld_Fillet_EndPlate_%s_%s_%d"
                            % (level, ref, int(dz > 0)),
                            plate_b, CONFIG["weld_leg"], collection)
        place(weld, origin + forward * (ep["t"] * 0.6) + Vector((0, 0, dz)),
              (0.0, 0.0, yaw + math.radians(90.0)))
        assign_material(weld, "MAT_Weld_Bead")
        add_quality_modifiers(weld, bevel=False)
        tag(weld, "weld", level, ref, "8 mm fillet, both flanges",
            "shop weld, E42 electrode")
        parent_to(weld, empty)
        made.append(weld)

    # Haunch rib under the bottom flange, stiffening the plate against prying.
    # Visible, unlike the internal diaphragm an SHS column would really get.
    if CONFIG["detail"]["stiffeners"]:
        rib = make_wedge("Bracket_Stiffener_%s_%s" % (level, ref),
                         CONFIG["haunch_rib"], CONFIG["stiffener"]["t"],
                         collection)
        place(rib, origin + forward * 0.012 + Vector((0.0, 0.0, -sec["h"] * 0.5)),
              (0.0, 0.0, yaw + math.radians(180.0)))
        assign_material(rib, "MAT_Steel_Painted")
        add_quality_modifiers(rib, width=0.002)
        tag(rib, "stiffener", level, ref,
            "140 mm rib x %.0f mm" % (CONFIG["stiffener"]["t"] * 1000),
            "S275, fillet welded to flange and end plate")
        parent_to(rib, empty)
        made.append(rib)

    return made


def build_beams(collection, empty, conn_collection=None, conn_empty=None):
    """Beams on every grid edge of every suspended level.

    Beams are trimmed back to the column faces so nothing interpenetrates, and
    the section hangs below the level datum so the top flange is flush with
    the floor line - exactly how a real drop beam sits.
    """
    xs, ys, zs = grid_x(), grid_y(), level_z()
    made = []

    for li in range(1, len(zs)):                  # no beams at ground level
        z = zs[li]
        lname = level_name(li)
        # Beams frame into the column below them.
        col_sec = column_section(li - 1)
        half_col_x = col_sec["b"] * 0.5
        half_col_y = col_sec["h"] * 0.5
        label = "Roof" if li == len(CONFIG["storeys"]) else "Floor"

        # --- beams running in X --------------------------------------------
        for iy, y in enumerate(ys):
            edge = iy in (0, len(ys) - 1)
            pts, inner, sec_txt, spec, mat, depth, section = _beam_profile(
                "edge" if edge else "primary")

            for ix in range(len(xs) - 1):
                x0 = xs[ix] + half_col_x
                length = (xs[ix + 1] - half_col_x) - x0
                ref = "%s-%s" % (grid_ref(ix, iy), grid_ref(ix + 1, iy))
                name = "Steel_Beam_%s_%s_%s_%s" % (
                    label, "Edge" if edge else "Primary", lname, ref)

                obj = extrude_profile(name, pts, inner, length, collection)
                place(obj, (x0, y, z - depth * 0.5))
                assign_material(obj, mat)
                add_quality_modifiers(obj)
                tag(obj, "beam_x", lname, ref, sec_txt, spec)
                parent_to(obj, empty)
                made.append(obj)

                if conn_collection is not None and CONFIG["detail"]["end_plates"]:
                    for end_x, yaw in ((x0, math.pi), (x0 + length, 0.0)):
                        made += _beam_end_details(
                            lname, ref, (end_x, y, z - depth * 0.5), yaw,
                            section, conn_collection, conn_empty)

        # --- beams running in Y --------------------------------------------
        for ix, x in enumerate(xs):
            edge = ix in (0, len(xs) - 1)
            pts, inner, sec_txt, spec, mat, depth, section = _beam_profile(
                "edge" if edge else "primary")

            for iy in range(len(ys) - 1):
                y0 = ys[iy] + half_col_y
                length = (ys[iy + 1] - half_col_y) - y0
                ref = "%s-%s" % (grid_ref(ix, iy), grid_ref(ix, iy + 1))
                name = "Steel_Beam_%s_%s_%s_%s" % (
                    label, "Edge" if edge else "Secondary", lname, ref)

                obj = extrude_profile(name, pts, inner, length, collection)
                # Rotate the +X extrusion onto +Y.
                place(obj, (x, y0, z - depth * 0.5),
                      (0.0, 0.0, math.radians(90.0)))
                assign_material(obj, mat)
                add_quality_modifiers(obj)
                tag(obj, "beam_y", lname, ref, sec_txt, spec)
                parent_to(obj, empty)
                made.append(obj)

                if conn_collection is not None and CONFIG["detail"]["end_plates"]:
                    half_pi = math.radians(90.0)
                    for end_y, yaw in ((y0, -half_pi), (y0 + length, half_pi)):
                        made += _beam_end_details(
                            lname, ref, (x, end_y, z - depth * 0.5), yaw,
                            section, conn_collection, conn_empty)

    return made


def build_bracing(collection, empty):
    """Diagonal CHS bracing in the end bays of the ground storey.

    Each brace is a tube aimed straight down the diagonal, so both ends land
    on a real column-to-beam node instead of floating.
    """
    if not CONFIG["make_bracing"] or CONFIG["profile_mode"] != "STEEL":
        return []

    cfg = CONFIG["brace"]
    xs, ys, zs = grid_x(), grid_y(), level_z()
    segments = cfg["segments"]
    ring_o = circle_points(cfg["od"] * 0.5, segments)
    ring_i = circle_points(cfg["od"] * 0.5 - cfg["t"], segments)
    z0, z1 = zs[0], zs[1]
    # A grid node is a working point, not a piece of steel. Aimed straight at
    # it, the brace buried its lower end 76 mm under the base plate and drove
    # its upper end through the edge beam. Hold both ends back to the face of
    # what is actually there: clear above the base plate, clear below the beam
    # soffit, and outside the column.
    r = cfg["od"] * 0.5
    clear = 0.010
    # Held back to the column face the brace ends float, connected to
    # nothing. Run them a quarter width past the face instead, so each end
    # dies into the column it braces the way a gusseted end really does.
    inset = CONFIG["col_ground"]["b"] * 0.25
    z_bot = z0 + CONFIG["base_plate"]["t"] + r + clear
    # The beam soffit is not the lowest thing at that node: the end plate
    # hangs a margin below it and the haunch rib hangs deeper still. Clear
    # whichever of the two actually reaches furthest down.
    node_drop = CONFIG["end_plate"]["margin"]
    if CONFIG["detail"]["stiffeners"]:
        node_drop = max(node_drop, CONFIG["haunch_rib"])
    z_top = z1 - CONFIG["beam_edge"]["h"] - node_drop - r - clear
    made = []

    for iy in (0, len(ys) - 1):
        y = ys[iy]
        for ix in (0, len(xs) - 2):
            start = Vector((xs[ix] + inset, y, z_bot))
            delta = Vector((xs[ix + 1] - inset, y, z_top)) - start

            ref = "%s-%s" % (grid_ref(ix, iy), grid_ref(ix + 1, iy))
            obj = extrude_profile("Steel_Brace_Diagonal_L00_%s" % ref,
                                  ring_o, ring_i, delta.length, collection)
            obj.location = start
            obj.rotation_mode = "QUATERNION"
            obj.rotation_quaternion = delta.to_track_quat("X", "Z")

            assign_material(obj, "MAT_Steel_Painted")
            add_quality_modifiers(obj, width=0.003)
            obj.data.shade_smooth()
            tag(obj, "brace", "L00", ref,
                "CHS %.1f x %.0f" % (cfg["od"] * 1000, cfg["t"] * 1000),
                "S355J2H, pinned both ends")
            parent_to(obj, empty)
            made.append(obj)

    return made


def _make_bolt(name, collection):
    """One assembled fastener: hex head, washer, shank, and nut below.

    A bare hex head on a stud reads as a CAD placeholder. The washer is what
    actually sells it - it is the part that catches a rim of light against the
    plate, and it is present on every preloaded connection in the real world.
    """
    cfg = CONFIG["bolt"]
    detail = CONFIG["detail"]["nuts_washers"]
    bm = bmesh.new()

    # Hex head, sitting proud of the plate.
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=6,
        radius1=cfg["head_d"] * 0.5, radius2=cfg["head_d"] * 0.5,
        depth=cfg["head_t"],
        matrix=Matrix.Translation((0.0, 0.0, cfg["head_t"] * 0.5 + 0.003)),
    )
    # Shank through the grip.
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=12,
        radius1=cfg["shank_d"] * 0.5, radius2=cfg["shank_d"] * 0.5,
        depth=cfg["grip"],
        matrix=Matrix.Translation((0.0, 0.0, -cfg["grip"] * 0.5)),
    )

    if detail:
        # Washer under the head: 2x shank diameter, 3 mm thick.
        bmesh.ops.create_cone(
            bm, cap_ends=True, cap_tris=False, segments=16,
            radius1=cfg["shank_d"], radius2=cfg["shank_d"], depth=0.003,
            matrix=Matrix.Translation((0.0, 0.0, 0.0015)),
        )
        # Hex nut on the far side of the grip.
        bmesh.ops.create_cone(
            bm, cap_ends=True, cap_tris=False, segments=6,
            radius1=cfg["head_d"] * 0.5, radius2=cfg["head_d"] * 0.5,
            depth=cfg["head_t"] * 0.85,
            matrix=Matrix.Translation(
                (0.0, 0.0, -cfg["grip"] + cfg["head_t"] * 0.4)),
        )

    return _finalise(bm, name, collection)


def _bolt_group(prefix, centre, spacing, count_x, count_y, collection, empty,
                level, ref):
    """A rectangular bolt pattern sharing one mesh datablock.

    Sharing the datablock is what lets the glTF exporter emit GPU instances
    instead of hundreds of unique meshes.
    """
    made, master = [], None
    ox = (count_x - 1) * spacing * 0.5
    oy = (count_y - 1) * spacing * 0.5

    for i in range(count_x):
        for j in range(count_y):
            name = "%s_%02d" % (prefix, i * count_y + j + 1)
            if master is None:
                obj = _make_bolt(name, collection)
                assign_material(obj, "MAT_Steel_Bolt")
                add_quality_modifiers(obj, width=0.0012)
                master = obj
            else:
                obj = bpy.data.objects.new(name, master.data)
                collection.objects.link(obj)
                copy_modifiers(master, obj)

            place(obj, (centre[0] - ox + i * spacing,
                        centre[1] - oy + j * spacing,
                        centre[2]))
            tag(obj, "bolt", level, ref, "M24 8.8",
                "preloaded HSFG, washer both faces")
            parent_to(obj, empty)
            made.append(obj)

    return made


def _weld_fillet(name, length, leg, collection):
    """Stylised fillet weld: a square bar rotated 45 deg into the corner.

    Not a modelled bead - a leg-sized triangular fillet is the correct
    engineering read at this scale and costs eight vertices.
    """
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector((length, leg * 1.4, leg * 1.4)),
                    verts=bm.verts)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=Vector((0.0, 0.0, 0.0)),
                     matrix=Matrix.Rotation(math.radians(45.0), 3, "X"))
    return _finalise(bm, name, collection)


def build_connections(collection, empty):
    """Base plates and holding-down bolts, splice plates, gussets, welds."""
    if CONFIG["profile_mode"] != "STEEL":
        return []

    xs, ys, zs = grid_x(), grid_y(), level_z()
    bp, sp, gu = CONFIG["base_plate"], CONFIG["splice_plate"], CONFIG["gusset"]
    col0 = CONFIG["col_ground"]
    made = []

    # --- base plates at every ground column --------------------------------
    for iy, y in enumerate(ys):
        for ix, x in enumerate(xs):
            ref = grid_ref(ix, iy)

            plate = make_box("Plate_Base_L00_%s" % ref,
                             (bp["b"], bp["d"], bp["t"]), collection)
            place(plate, (x, y, -bp["t"] * 0.5))
            assign_material(plate, "MAT_Steel_Painted")
            add_quality_modifiers(plate, width=0.003)
            tag(plate, "base_plate", "L00", ref,
                "%.0fx%.0fx%.0f mm plate" % (bp["b"] * 1000, bp["d"] * 1000,
                                             bp["t"] * 1000),
                "S275, welded to column, 4xM24 holding-down bolts")
            parent_to(plate, empty)
            made.append(plate)

            made += _bolt_group("Bolt_M24_HoldingDown_L00_%s" % ref,
                                (x, y, 0.0), bp["b"] * 0.62, 2, 2,
                                collection, empty, "L00", ref)

            # Fillet weld on all four sides of the column-to-plate junction.
            seams = (
                (0.0, col0["h"] * 0.5, 0.0),
                (0.0, -col0["h"] * 0.5, math.radians(180.0)),
                (col0["b"] * 0.5, 0.0, math.radians(90.0)),
                (-col0["b"] * 0.5, 0.0, math.radians(-90.0)),
            )
            # Each run stops one leg short of the corner so the four mitre
            # against each other. Run full width they overlapped by a leg at
            # every corner - a doubled bead no welder would lay.
            leg = CONFIG["weld_leg"]
            for k, (dx, dy, yaw) in enumerate(seams):
                weld = _weld_fillet("Weld_Fillet_Base_L00_%s_%d" % (ref, k + 1),
                                    col0["b"] - 2 * leg, leg, collection)
                place(weld, (x + dx, y + dy, 0.0), (0.0, 0.0, yaw))
                assign_material(weld, "MAT_Weld_Bead")
                add_quality_modifiers(weld, bevel=False)
                tag(weld, "weld", "L00", ref, "10 mm fillet, all round",
                    "E42 electrode, continuous")
                parent_to(weld, empty)
                made.append(weld)

    # --- column splice plates at every intermediate level ------------------
    # A column splice never sits on the floor line - that is where the beams,
    # their end plates and their welds all arrive. Real splices are lifted
    # clear of the connection zone, roughly 600 mm above the floor, which is
    # also where an erector can reach the bolts.
    splice_lift = CONFIG["splice_lift"]
    for li in range(1, len(CONFIG["storeys"])):
        z = zs[li] + splice_lift
        lname = level_name(li)
        sec = column_section(li)

        for iy, y in enumerate(ys):
            for ix, x in enumerate(xs):
                ref = grid_ref(ix, iy)
                offset = sec["h"] * 0.5 + sp["t"] * 0.5

                for side, dy in (("N", offset), ("S", -offset)):
                    plate = make_box("Plate_Splice_%s_%s_%s" % (lname, ref, side),
                                     (sp["b"], sp["t"], sp["h"]), collection)
                    place(plate, (x, y + dy, z))
                    assign_material(plate, "MAT_Steel_Painted")
                    add_quality_modifiers(plate, width=0.002)
                    tag(plate, "splice_plate", lname, ref,
                        "%.0fx%.0fx%.0f mm" % (sp["b"] * 1000, sp["h"] * 1000,
                                               sp["t"] * 1000),
                        "S275 cover plate, 4xM24 8.8 preloaded")
                    parent_to(plate, empty)
                    made.append(plate)

                    # Two bolts above the splice line, two below.
                    made += _bolt_group(
                        "Bolt_M24_Splice_%s_%s_%s" % (lname, ref, side),
                        (x, y + dy + math.copysign(sp["t"], dy), z), 0.16, 2, 1,
                        collection, empty, lname, ref)

    # --- gusset brackets at beam-to-column nodes ---------------------------
    # A gusset is a fin plate: the beam web bolts to it. That is an
    # alternative to a flush end plate, not a companion to one. Built with
    # both, every node carried two different connections occupying the same
    # 10 mm of space. Only draw these when the end plates are switched off.
    if CONFIG["detail"]["end_plates"]:
        return made

    for li in range(1, len(zs)):
        z = zs[li]
        lname = level_name(li)
        sec = column_section(li - 1)
        depth = CONFIG["beam_primary"]["h"]

        for iy, y in enumerate(ys):
            for ix, x in enumerate(xs):
                ref = grid_ref(ix, iy)
                # A gusset on each side of the column that actually has a
                # beam framing into it - skip the free faces at the perimeter.
                faces = []
                if ix < len(xs) - 1:
                    faces.append(("E", sec["b"] * 0.5, 0.0))
                if ix > 0:
                    faces.append(("W", -sec["b"] * 0.5, math.radians(180.0)))

                for side, dx, yaw in faces:
                    gusset = make_wedge("Bracket_Gusset_%s_%s_%s" % (lname, ref, side),
                                        gu["leg"], gu["t"], collection)
                    place(gusset, (x + dx, y, z - depth * 0.15), (0.0, 0.0, yaw))
                    assign_material(gusset, "MAT_Steel_Painted")
                    add_quality_modifiers(gusset, width=0.002)
                    tag(gusset, "gusset", lname, ref,
                        "%.0f mm leg x %.0f mm plate" % (gu["leg"] * 1000,
                                                         gu["t"] * 1000),
                        "S275, fillet welded to column, bolted to beam web")
                    parent_to(gusset, empty)
                    made.append(gusset)

    return made


def build_pipes(collection, empty):
    """MEP runs as bezier curves swept to a tube, then converted to mesh.

    Routed under the beam soffit in the ceiling void, so they clear the
    structure - the coordination case the reference image advertises.
    """
    xs, ys, zs = grid_x(), grid_y(), level_z()
    beam_depth = CONFIG["beam_primary"]["h"]
    made = []

    for li in CONFIG["pipe_levels"]:
        if li >= len(zs):
            continue
        z_soffit = zs[li] - beam_depth
        lname = level_name(li)

        for pi, pipe in enumerate(CONFIG["pipes"]):
            # Stagger the runs laterally and vertically so they read as a
            # coordinated services bundle rather than coincident lines.
            y_base = ys[1] * 0.5 + (pi - 1) * 0.35
            z = z_soffit - CONFIG["pipe_drop"] - pi * 0.02

            curve = bpy.data.curves.new(
                "Pipe_Main_Curved_%s_%s_data" % (lname, pipe["tag"]),
                type="CURVE")
            curve.dimensions = "3D"
            curve.resolution_u = 8
            curve.bevel_depth = pipe["od"] * 0.5
            curve.bevel_resolution = CONFIG["pipe_bevel_resolution"]
            curve.use_fill_caps = True

            spline = curve.splines.new("BEZIER")
            knots = [
                (xs[0] + 0.6, y_base, z),
                (xs[1], y_base, z),
                (xs[2], y_base + 1.2, z),
                (xs[3], y_base + 1.2, z),
                (xs[-1] - 0.6, y_base, z),
            ]
            spline.bezier_points.add(len(knots) - 1)
            for i, co in enumerate(knots):
                point = spline.bezier_points[i]
                point.co = Vector(co)
                # AUTO handles give the smooth swept bends real pipe has.
                point.handle_left_type = "AUTO"
                point.handle_right_type = "AUTO"

            name = "Pipe_Main_Curved_%s_%s" % (lname, pipe["tag"])
            obj = bpy.data.objects.new(name, curve)
            collection.objects.link(obj)

            # Convert to mesh so the GLB carries triangles, not a curve.
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.convert(target="MESH")
            obj = bpy.context.view_layer.objects.active

            obj.data.shade_smooth()
            assign_material(obj, "MAT_Pipe_CHW" if "CHW" in pipe["tag"]
                            else "MAT_Pipe_LTHW")
            add_quality_modifiers(obj, bevel=False)
            tag(obj, "pipe", lname, pipe["tag"],
                "Ø%.1f mm OD" % (pipe["od"] * 1000), pipe["spec"],
                discipline="MEP")
            parent_to(obj, empty)
            made.append(obj)

    return made


def build_accessories(collection, empty):
    """Edge protection around the perimeter of every suspended level."""
    if not CONFIG["make_edge_rails"]:
        return []

    xs, ys, zs = grid_x(), grid_y(), level_z()
    cfg = CONFIG["rail"]
    x_min, x_max, y_min, y_max = xs[0], xs[-1], ys[0], ys[-1]
    made = []

    for li in range(1, len(zs)):
        z = zs[li]
        lname = level_name(li)

        # Edge protection clamps to the slab edge, which is outboard of the
        # frame. Run along the column centreline it speared the beam end
        # plates, their welds and the splice plates - all of which sit at the
        # grid line. Push the whole loop clear of the steel.
        off = CONFIG["rail_offset"]
        runs = (
            ("S", (x_min - off, y_min - off), (x_max + off, y_min - off)),
            ("N", (x_max + off, y_max + off), (x_min - off, y_max + off)),
            ("W", (x_min - off, y_max + off), (x_min - off, y_min - off)),
            ("E", (x_max + off, y_min - off), (x_max + off, y_max + off)),
        )

        for side, (ax, ay), (bx, by) in runs:
            start = Vector((ax, ay, z))
            delta = Vector((bx, by, z)) - start
            length = delta.length
            direction = delta.normalized()
            yaw = math.atan2(direction.y, direction.x)
            mid = start + delta * 0.5

            # Top rail and mid rail.
            for tier, height in (("Top", cfg["height"]),
                                 ("Mid", cfg["height"] * 0.5)):
                bar = make_box("Rail_Edge_%s_%s_%s" % (tier, lname, side),
                               (length, cfg["rail_d"], cfg["rail_d"]),
                               collection)
                place(bar, (mid.x, mid.y, z + height), (0.0, 0.0, yaw))
                assign_material(bar, "MAT_Rail_Safety")
                add_quality_modifiers(bar, width=0.002)
                tag(bar, "guard_rail", lname, side,
                    "%.0f mm rail" % (cfg["rail_d"] * 1000),
                    "temporary edge protection, EN 13374 Class A",
                    discipline="TMP")
                parent_to(bar, empty)
                made.append(bar)

            # Toe board sitting on the floor line.
            toe = make_box("Rail_Edge_ToeBoard_%s_%s" % (lname, side),
                           (length, 0.020, cfg["toe_h"]), collection)
            place(toe, (mid.x, mid.y, z + cfg["toe_h"] * 0.5), (0.0, 0.0, yaw))
            assign_material(toe, "MAT_Rail_Safety")
            add_quality_modifiers(toe, width=0.002)
            tag(toe, "toe_board", lname, side, "150 mm toe board",
                "EN 13374 Class A", discipline="TMP")
            parent_to(toe, empty)
            made.append(toe)

            # Posts at the configured spacing, sharing one mesh datablock.
            n_posts = max(2, int(length / cfg["post_spacing"]) + 1)
            step = length / (n_posts - 1)
            master = None

            # The four runs close a loop, so the post at the end of this run
            # is the post at the start of the next. Emitting both put two
            # posts inside each other at all four corners.
            for p in range(n_posts - 1):
                pname = "Rail_Edge_Post_%s_%s_%02d" % (lname, side, p + 1)
                if master is None:
                    post = make_box(pname, (cfg["post"], cfg["post"],
                                            cfg["height"]), collection)
                    assign_material(post, "MAT_Rail_Safety")
                    add_quality_modifiers(post, width=0.002)
                    master = post
                else:
                    post = bpy.data.objects.new(pname, master.data)
                    collection.objects.link(post)
                    copy_modifiers(master, post)

                pos = start + direction * (step * p)
                place(post, (pos.x, pos.y, z + cfg["height"] * 0.5),
                      (0.0, 0.0, yaw))
                tag(post, "guard_post", lname, side,
                    "%.0fx%.0f mm post @ %.2f m" % (cfg["post"] * 1000,
                                                    cfg["post"] * 1000, step),
                    "clamped to slab edge, M12 into cast-in socket",
                    discipline="TMP")
                parent_to(post, empty)
                made.append(post)

    return made


# ---------------------------------------------------------------------------
# Animation: storey-by-storey erection sequence
# ---------------------------------------------------------------------------

# Order within a storey, following real erection sequence.
PHASE = {
    "foundation": 0, "base_plate": 1, "bolt": 2, "weld": 3,
    "column": 4, "splice_plate": 5, "brace": 6,
    "beam_x": 7, "beam_y": 8, "gusset": 9,
    "guard_post": 10, "guard_rail": 11, "toe_board": 11,
    "pipe": 12,
}


def action_fcurves(anim_data):
    """Return an action's F-curves across the 4.x and 5.x action layouts.

    Blender 4.4 introduced slotted actions and 5.x dropped Action.fcurves
    entirely: curves now live in a channelbag under a layer's strip, keyed by
    the slot the object is bound to.
    """
    action = anim_data.action if anim_data else None
    if action is None:
        return []
    if hasattr(action, "fcurves"):                 # 4.x layout
        return list(action.fcurves)

    slot = getattr(anim_data, "action_slot", None)
    curves = []
    for layer in action.layers:
        for strip in layer.strips:
            bag = strip.channelbag(slot) if slot else None
            if bag is None and getattr(strip, "channelbags", None):
                bag = strip.channelbags[0]
            if bag:
                curves.extend(bag.fcurves)
    return curves


def build_erection_animation(objects, frames_per_level=40, lift=6.0):
    """DEPRECATED - use assembly_animation.build() instead.

    Kept only as a fallback. It keys `hide_viewport`, which glTF cannot
    export, so the sequence is Blender-only.

    Key each element in by storey, in construction order.

    Foundations first, then storey by storey: columns, then the beams and
    connections that land on them. Each element drops into place from `lift`
    metres above its final position, so the sequence reads as erection rather
    than as objects fading in.
    """
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 1

    order = {"L00": 0}
    for i in range(1, len(CONFIG["storeys"]) + 1):
        order[level_name(i)] = i

    for obj in objects:
        level = order.get(obj.get("level", "L00"), 0)
        phase = PHASE.get(obj.get("element_type", ""), 6)
        start = 1 + level * frames_per_level + phase * 2
        end = start + 12

        final = obj.location.copy()
        obj.location = final + Vector((0.0, 0.0, lift))
        obj.keyframe_insert("location", frame=start)
        obj.location = final
        obj.keyframe_insert("location", frame=end)

        # Hidden until its own start frame.
        obj.hide_viewport = obj.hide_render = True
        obj.keyframe_insert("hide_viewport", frame=max(1, start - 1))
        obj.keyframe_insert("hide_render", frame=max(1, start - 1))
        obj.hide_viewport = obj.hide_render = False
        obj.keyframe_insert("hide_viewport", frame=start)
        obj.keyframe_insert("hide_render", frame=start)

        for fcurve in action_fcurves(obj.animation_data):
            is_location = fcurve.data_path == "location"
            for kp in fcurve.keyframe_points:
                kp.interpolation = "BEZIER" if is_location else "CONSTANT"
                if is_location:
                    kp.easing = "EASE_OUT"

        scene.frame_end = max(scene.frame_end, end + 20)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_glb(filepath, animate=False):
    """Write a GLB structured for a Three.js viewer.

    export_yup converts Blender Z-up to glTF Y-up, so on the Three.js side
    storey height is +Y and the footprint lies in XZ. export_extras carries
    the custom properties through to object.userData.
    """
    directory = os.path.dirname(os.path.abspath(filepath))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory, exist_ok=True)

    kwargs = dict(
        filepath=filepath,
        export_format="GLB",
        export_apply=True,          # realise bevel and weighted-normal modifiers
        export_yup=True,
        export_extras=True,         # custom props -> userData
        export_cameras=False,
        export_lights=False,
        export_materials="EXPORT",
        export_texcoords=True,
        export_normals=True,
        export_tangents=False,
        export_animations=animate,
        export_skins=False,
        export_morph=False,
        use_selection=False,
        use_visible=False,
    )

    # Draco is worth roughly 60-70% on geometry this repetitive, but the
    # Three.js side then needs DRACOLoader, so it stays opt-in.
    if os.environ.get("GLTF_DRACO") == "1":
        kwargs["export_draco_mesh_compression_enable"] = True
        kwargs["export_draco_mesh_compression_level"] = 6

    bpy.ops.export_scene.gltf(**kwargs)
    print("[generate_structure] exported %s" % filepath)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def generate():
    if CONFIG["clear_scene"]:
        clear_scene()
    setup_units()

    root, cols, empties = build_hierarchy()

    made = []
    made += build_foundations(cols["Foundation"], empties["Foundation"])
    made += build_columns(cols["Columns"], empties["Columns"])
    made += build_beams(cols["Beams"], empties["Beams"],
                        cols["Connections"], empties["Connections"])
    made += build_bracing(cols["Beams"], empties["Beams"])
    made += build_connections(cols["Connections"], empties["Connections"])
    made += build_pipes(cols["Pipes"], empties["Pipes"])
    made += build_accessories(cols["Accessories"], empties["Accessories"])

    faces = sum(len(o.data.polygons) for o in made if o.type == "MESH")
    print("[generate_structure] %d objects, %d faces before modifiers"
          % (len(made), faces))
    return root, made


def parse_args():
    """Read args after the `--` separator when run headless."""
    argv = sys.argv
    if "--" not in argv:
        return None, False
    argv = argv[argv.index("--") + 1:]

    out, animate = None, False
    i = 0
    while i < len(argv):
        if argv[i] == "--export" and i + 1 < len(argv):
            out = argv[i + 1]
            i += 2
        elif argv[i] == "--animate":
            animate = True
            i += 1
        else:
            i += 1
    return out, animate


def main():
    out, animate = parse_args()
    _root, made = generate()

    if animate:
        # assembly_animation.py supersedes build_erection_animation(): that one
        # keys hide_viewport, which glTF does not export, so its sequence plays
        # in Blender and does nothing in the browser. Fall back to it only if
        # the module is genuinely missing.
        try:
            import assembly_animation
            assembly_animation.build()
        except ImportError:
            build_erection_animation(made)

    if out:
        export_glb(out, animate=animate)


if __name__ == "__main__":
    main()
