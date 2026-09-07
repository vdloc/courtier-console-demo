"""Structural geometry validation for the generated frame.

Run inside Blender against a built scene:

    exec(open("blender/audit_geometry.py").read())

The generator is the fix target; this script is only the measuring
instrument. It reports, it never edits.

Interpenetration is not by itself a defect. Bolt shanks pass through
plates, weld fillets bite into both parts they join, stiffeners are
welded inside the column they stiffen. `PERMITTED` below encodes which
family pairs are allowed to share volume; everything else is a clash.
"""

import math
from collections import Counter, defaultdict

import bpy
from mathutils.bvhtree import BVHTree

TOL = 1e-4


# ---------------------------------------------------------------------------
# Element families, derived from the names the generator assigns
# ---------------------------------------------------------------------------

def family(name):
    for prefix, fam in (
        ("Steel_Column_Main", "COLUMN"),
        ("Steel_Beam_", "BEAM"),
        ("Steel_Brace_", "BRACE"),
        ("Pipe_", "PIPE"),
        ("Bolt_", "BOLT"),
        ("Weld_", "WELD"),
        ("Plate_EndPlate", "ENDPLATE"),
        ("Plate_Splice", "SPLICE"),
        ("Plate_Base", "BASEPLATE"),
        ("Bracket_Stiffener", "STIFFENER"),
        ("Bracket_Gusset", "GUSSET"),
        ("Concrete_Pad", "PAD"),
        ("Rail_", "RAIL"),
        ("Ground_Plane", "GROUND"),
    ):
        if name.startswith(prefix):
            return fam
    return "OTHER"


# Pairs whose members are fabricated to occupy the same volume.
PERMITTED = {
    frozenset(p) for p in (
        # Fasteners and welds bite into whatever they join.
        ("BOLT", "ENDPLATE"), ("BOLT", "SPLICE"), ("BOLT", "BASEPLATE"),
        ("BOLT", "COLUMN"), ("BOLT", "BEAM"), ("BOLT", "PAD"),
        ("BOLT", "GUSSET"), ("BOLT", "STIFFENER"), ("BOLT", "BOLT"),
        ("BOLT", "WELD"),   # a holding-down bolt rises through its own bead
        ("WELD", "ENDPLATE"), ("WELD", "BASEPLATE"), ("WELD", "COLUMN"),
        ("WELD", "BEAM"), ("WELD", "STIFFENER"), ("WELD", "GUSSET"),
        ("WELD", "BRACE"), ("WELD", "SPLICE"),
        # Two beads that meet at a shared node fuse into one another; that is
        # what a welder does. Caveat: this also hides a bead laid twice down
        # the same face, which is a real defect - the base-plate collars had
        # exactly that, overlapping by a full leg, and were fixed by trimming
        # each run rather than by widening this list.
        ("WELD", "WELD"),
        # Shop-welded assemblies.
        ("ENDPLATE", "BEAM"), ("ENDPLATE", "COLUMN"), ("ENDPLATE", "STIFFENER"),
        ("STIFFENER", "COLUMN"), ("STIFFENER", "BEAM"),
        ("SPLICE", "COLUMN"),
        ("GUSSET", "COLUMN"), ("GUSSET", "BEAM"), ("GUSSET", "BRACE"),
        ("BASEPLATE", "COLUMN"), ("BASEPLATE", "PAD"),
        ("BRACE", "COLUMN"), ("BRACE", "BEAM"),
        # Site and secondary.
        ("PAD", "GROUND"), ("PAD", "PAD"),
        ("RAIL", "RAIL"), ("RAIL", "BEAM"), ("RAIL", "COLUMN"),
    )
}


def targets():
    """Mesh objects that carry structural meaning."""
    return [o for o in bpy.data.objects
            if o.type == 'MESH' and family(o.name) != "OTHER"]


# ---------------------------------------------------------------------------
# Cheap O(n) checks
# ---------------------------------------------------------------------------

def check_scale(objs):
    bad = []
    for o in objs:
        s = o.scale
        if max(abs(s[i] - 1.0) for i in range(3)) > TOL:
            bad.append((o.name, tuple(round(v, 4) for v in s)))
    return bad


def check_rotation(objs):
    """The generator only ever uses multiples of 90 degrees, plus the
    brace diagonals which are aimed down their own axis."""
    bad = []
    for o in objs:
        if family(o.name) == "BRACE":
            continue                      # genuinely off-axis by design
        for axis, ang in zip("XYZ", o.rotation_euler):
            deg = math.degrees(ang)
            if abs(deg - round(deg / 90.0) * 90.0) > 0.01:
                bad.append((o.name, axis, round(deg, 3)))
    return bad


def check_duplicates(objs, boxes):
    """Two objects filling the same world-space box with the same vertex
    count are the same object modelled twice.

    Keyed on the world bounding box, not the origin: the generator bakes
    some geometry into local coordinates and leaves the origin at the
    world centre, so several unrelated objects share an origin.
    """
    seen = defaultdict(list)
    for o in objs:
        lo, hi = boxes[o.name]
        key = (tuple(round(v, 4) for v in lo),
               tuple(round(v, 4) for v in hi),
               len(o.data.vertices))
        seen[key].append(o.name)
    return [names for names in seen.values() if len(names) > 1]


def world_bbox(o):
    pts = [o.matrix_world @ v.co for v in o.data.vertices]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return lo, hi


def check_support(objs, boxes):
    """A structural member with nothing beneath it is floating.

    Support means another member's bounding box overlaps in plan and
    reaches the candidate's underside. Bolts, welds and rails are
    excluded - they hang off their parent by design.
    """
    load_bearing = ("COLUMN", "BEAM", "BRACE", "PAD", "PIPE")
    floating = []
    for o in objs:
        fam = family(o.name)
        if fam not in load_bearing:
            continue
        lo, hi = boxes[o.name]
        if lo[2] < 0.05:                  # founded on or below grade
            continue
        supported = False
        for other in objs:
            if other is o:
                continue
            olo, ohi = boxes[other.name]
            if ohi[0] < lo[0] - 0.02 or olo[0] > hi[0] + 0.02:
                continue
            if ohi[1] < lo[1] - 0.02 or olo[1] > hi[1] + 0.02:
                continue
            # Anything reaching the underside, from either direction.
            if olo[2] - 0.02 <= lo[2] <= ohi[2] + 0.02:
                supported = True
                break
        if not supported:
            floating.append((o.name, round(lo[2], 3)))
    return floating


# ---------------------------------------------------------------------------
# Intersections: broad-phase AABB sweep, narrow-phase BVH
# ---------------------------------------------------------------------------

def bvh(o):
    """Base mesh in world space - deliberately not the evaluated mesh.

    The Bevel modifier multiplies the mesh 4.4x and shrinks edges very
    slightly, so the base cage is both far cheaper and conservative in
    the right direction for a clash test.
    """
    m = o.matrix_world
    verts = [m @ v.co for v in o.data.vertices]
    polys = [list(p.vertices) for p in o.data.polygons]
    return BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)


def penetration(a, b, boxes):
    """Depth of the shared volume, in metres.

    Two members that meet at a splice or a trimmed beam end share a face,
    and BVHTree.overlap() calls that an intersection. It is not one. The
    smallest of the three axis overlaps separates the two cases: a shared
    face measures zero, a member driven into another measures the distance
    it went in. Every member here is axis-aligned except the braces, for
    which this is an upper bound.
    """
    alo, ahi = boxes[a.name]
    blo, bhi = boxes[b.name]
    return min(min(ahi[i], bhi[i]) - max(alo[i], blo[i]) for i in range(3))


def check_clashes(objs, boxes, limit_per_pair=6):
    # Broad phase: sort on X, sweep.
    order = sorted(objs, key=lambda o: boxes[o.name][0][0])
    candidates = []
    for i, a in enumerate(order):
        alo, ahi = boxes[a.name]
        for b in order[i + 1:]:
            blo, bhi = boxes[b.name]
            if blo[0] > ahi[0]:
                break                     # sweep line has passed a
            if bhi[1] < alo[1] or blo[1] > ahi[1]:
                continue
            if bhi[2] < alo[2] or blo[2] > ahi[2]:
                continue
            pair = frozenset((family(a.name), family(b.name)))
            if pair in PERMITTED:
                continue
            candidates.append((a, b, pair))

    # Narrow phase, only on survivors.
    cache = {}
    clashes = defaultdict(list)
    for a, b, pair in candidates:
        for o in (a, b):
            if o.name not in cache:
                cache[o.name] = bvh(o)
        if cache[a.name].overlap(cache[b.name]):
            key = tuple(sorted(pair))
            clashes[key].append((a.name, b.name, penetration(a, b, boxes)))
    return len(candidates), clashes


CONTACT = 0.001     # 1 mm - below this, two members are touching, not clashing


def check_datums(objs, boxes):
    """Vertical continuity at the interfaces that have to close.

    A gap here is a member hanging in space; a negative gap is a member
    buried in the one below. Both read as errors long before anyone
    measures them.
    """
    by_fam = defaultdict(list)
    for o in objs:
        by_fam[family(o.name)].append(o)

    def span(fam, axis=2):
        vals = [(boxes[o.name][0][axis], boxes[o.name][1][axis])
                for o in by_fam[fam]]
        return (min(v[0] for v in vals), max(v[1] for v in vals)) if vals else None

    # Each row is (label, measured gap, lowest acceptable, highest acceptable).
    rows = []
    pad = span("PAD")
    base = span("BASEPLATE")
    if pad and base:
        rows.append(("pad top -> base plate underside",
                     base[0] - pad[1], 0.0, 0.0))
    col = [o for o in by_fam["COLUMN"] if "_L00_" in o.name]
    if col and base:
        lo = min(boxes[o.name][0][2] for o in col)
        rows.append(("base plate top -> L00 column foot",
                     lo - base[1], 0.0, 0.0))
    brace = span("BRACE")
    if brace and base:
        # Clearance, not a gap: the brace has to pass over the base plate.
        # Negative means it is buried in the plate, which is what it used
        # to be. More than 150 mm and it has stopped meeting the column.
        rows.append(("base plate top -> brace underside",
                     brace[0] - base[1], 0.0, 0.150))
    return rows


# ---------------------------------------------------------------------------

def report():
    # Blender evaluates matrix_world lazily. Run straight after a build,
    # every object still reports the matrix it had before place() moved it,
    # and the whole audit measures a scene collapsed onto the origin.
    bpy.context.view_layer.update()

    objs = targets()
    boxes = {o.name: world_bbox(o) for o in objs}

    print("=" * 68)
    print("STRUCTURAL GEOMETRY AUDIT - %d objects" % len(objs))
    print("=" * 68)

    fams = Counter(family(o.name) for o in objs)
    print("families:", dict(sorted(fams.items())))

    print("\n[1] NON-UNIT SCALE")
    bad = check_scale(objs)
    print("    %d" % len(bad))
    for row in bad[:8]:
        print("      ", row)

    print("\n[2] OFF-AXIS ROTATION")
    bad = check_rotation(objs)
    print("    %d" % len(bad))
    for row in bad[:8]:
        print("      ", row)

    print("\n[3] COINCIDENT DUPLICATES")
    dups = check_duplicates(objs, boxes)
    print("    %d groups, %d redundant objects"
          % (len(dups), sum(len(g) - 1 for g in dups)))
    for g in dups[:8]:
        print("      ", g[:3], "..." if len(g) > 3 else "")

    print("\n[4] FLOATING / UNSUPPORTED")
    fl = check_support(objs, boxes)
    print("    %d" % len(fl))
    for row in fl[:12]:
        print("      ", row)

    print("\n[5] DATUM CONTINUITY")
    for label, gap, lo_ok, hi_ok in check_datums(objs, boxes):
        if gap < lo_ok - 0.002:
            mark = "BURIED"
        elif gap > hi_ok + 0.002:
            mark = "GAP"
        else:
            mark = "ok"
        print("      %-38s %8.1f mm  %s" % (label, gap * 1000, mark))

    print("\n[6] CLASHES (outside the permitted-pair allowlist)")
    ncand, clashes = check_clashes(objs, boxes)
    print("    %d broad-phase candidates" % ncand)
    total = sum(len(v) for v in clashes.values())
    print("    %d overlaps in %d family pairs" % (total, len(clashes)))
    print("    depth <= %.0f mm = shared face (members touching, not clashing)"
          % (CONTACT * 1000))
    for key, rows in sorted(clashes.items(), key=lambda kv: -len(kv[1])):
        real = [r for r in rows if r[2] > CONTACT]
        flag = "PENETRATION" if real else "contact only"
        print("      %-22s %4d overlaps, %4d real   %s"
              % (" x ".join(key), len(rows), len(real), flag))
        for name_a, name_b, d in sorted(real, key=lambda r: -r[2])[:3]:
            print("          %6.1f mm  %s | %s" % (d * 1000, name_a, name_b))

    print("\n" + "=" * 68)


report()
