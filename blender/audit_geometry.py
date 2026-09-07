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
        # Site dressing from scene_setup.py. Not structural, but "every
        # object" means every object, and the hoarding and compound are
        # close enough to the frame to be worth testing against it.
        ("Site_Hoarding_", "HOARDING"),
        ("Site_Cabin_", "CABIN"),
        ("Site_Skip", "SKIP"),
        ("Site_Bundle_", "BUNDLE"),
        ("Site_Bearer_", "BEARER"),
        ("Site_Barrier_", "BARRIER"),
        ("Site_Spoil_", "SPOIL"),
        ("Site_Surround_", "SURROUND"),
    ):
        if name.startswith(prefix):
            return fam
    return "OTHER"


SITE = ("HOARDING", "CABIN", "SKIP", "BUNDLE", "BEARER", "BARRIER",
        "SPOIL", "SURROUND", "GROUND")


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


# Site props stand on the ground next to each other; stacked steel touches
# its bearers, and spoil heaps touch the ground. None of that is a defect.
PERMITTED |= {frozenset(p) for p in (
    ("BUNDLE", "BEARER"), ("BEARER", "GROUND"), ("BUNDLE", "GROUND"),
    ("SPOIL", "GROUND"), ("CABIN", "GROUND"), ("SKIP", "GROUND"),
    ("HOARDING", "GROUND"), ("BARRIER", "GROUND"), ("SURROUND", "GROUND"),
    ("PAD", "GROUND"), ("CABIN", "CABIN"), ("BARRIER", "BARRIER"),
)}


def targets():
    """Every mesh in the file. Empties and the camera carry no geometry."""
    return [o for o in bpy.data.objects if o.type == 'MESH']


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
        fam = family(o.name)
        if fam == "BRACE" or fam in SITE:
            # Braces run down a diagonal, and the site props are jittered on
            # purpose - a stack of steel dropped off a lorry does not land
            # square. Holding either to the structural grid reports the
            # realism as the defect.
            continue
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


def cross_section(o, boxes):
    """The two smaller bounding-box dimensions - a prismatic member's
    profile, independent of which way it was laid down."""
    lo, hi = boxes[o.name]
    dims = sorted(hi[i] - lo[i] for i in range(3))
    return (round(dims[0], 4), round(dims[1], 4))


def check_sections(objs, boxes):
    """Members carrying the same section tag must have the same profile.

    The generator writes the section into a custom property, so the model
    states what each member claims to be. Two objects both tagged
    SHS 400x400x16 whose profiles measure differently means the profile
    builder drifted from the label.
    """
    groups = defaultdict(list)
    for o in objs:
        sec = o.get("section")
        if sec:
            groups[sec].append(o)

    bad = []
    for sec, members in groups.items():
        counts = Counter(cross_section(o, boxes) for o in members)
        if len(counts) < 2:
            continue
        (common, _), = counts.most_common(1)
        for o in members:
            got = cross_section(o, boxes)
            if got != common:
                bad.append((o.name, sec, got, common))
    return bad


def check_orientation(objs, boxes):
    """Members laid down on the wrong axis.

    A column's long axis is vertical. A beam's is not - and its web must
    stand up, so its vertical extent has to exceed its flange width. Roll
    a beam 90 degrees about its own axis and that inequality flips, which
    is the one rotation error a 90-degree-multiple check cannot see.
    """
    bad = []
    for o in objs:
        fam = family(o.name)
        lo, hi = boxes[o.name]
        dx, dy, dz = (hi[i] - lo[i] for i in range(3))
        if fam == "COLUMN":
            if dz < max(dx, dy):
                bad.append((o.name, "column is not standing up",
                            (round(dx, 3), round(dy, 3), round(dz, 3))))
        elif fam == "BEAM":
            span = max(dx, dy)
            width = min(dx, dy)
            if dz > span:
                bad.append((o.name, "beam is standing on end",
                            (round(dx, 3), round(dy, 3), round(dz, 3))))
            elif dz < width:
                bad.append((o.name, "beam web is lying on its side",
                            (round(dx, 3), round(dy, 3), round(dz, 3))))
    return bad


def check_alignment(objs, boxes):
    """Members sharing a grid reference must share a centreline.

    Every object carries the grid node it belongs to. Columns stacked at
    A1 across four storeys, and the pad and base plate under them, all
    have to sit on one vertical line; a level's columns all have to start
    at one height. This catches a member nudged off its node without
    needing to know the grid spacings.
    """
    plumb = defaultdict(list)
    datum = defaultdict(list)
    for o in objs:
        ref, lvl = o.get("grid_ref"), o.get("level")
        fam = family(o.name)
        if fam not in ("COLUMN", "PAD", "BASEPLATE"):
            continue
        lo, hi = boxes[o.name]
        centre = ((lo[0] + hi[0]) * 0.5, (lo[1] + hi[1]) * 0.5)
        if ref:
            plumb[ref].append((o.name, centre))
        if lvl and fam == "COLUMN":
            datum[lvl].append((o.name, lo[2]))

    bad = []
    for ref, members in plumb.items():
        xs = [c[0] for _, c in members]
        ys = [c[1] for _, c in members]
        off = max(max(xs) - min(xs), max(ys) - min(ys))
        if off > 0.002:
            bad.append(("grid %s off plumb" % ref, off, members[0][0]))
    for lvl, members in datum.items():
        zs = [z for _, z in members]
        off = max(zs) - min(zs)
        if off > 0.002:
            bad.append(("level %s columns not level" % lvl, off,
                        members[0][0]))
    return bad


def overlap_volume(a, b, boxes):
    """Volume of the shared bounding boxes, in cubic metres.

    This is the AABB intersection, not a mesh boolean. Every member here
    is axis-aligned bar the four braces, for which it is an upper bound.
    A boolean over 3000 objects would take hours to rank findings that
    penetration depth already ranks.
    """
    alo, ahi = boxes[a.name]
    blo, bhi = boxes[b.name]
    v = 1.0
    for i in range(3):
        v *= max(0.0, min(ahi[i], bhi[i]) - max(alo[i], blo[i]))
    return v


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
            clashes[key].append((a.name, b.name, penetration(a, b, boxes),
                                 overlap_volume(a, b, boxes)))
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
    # An audit claiming completeness has to show its denominator.
    unknown = [o.name for o in objs if family(o.name) == "OTHER"]
    print("coverage: %d meshes, %d classified, %d unclassified%s"
          % (len(objs), len(objs) - len(unknown), len(unknown),
             (" -> " + ", ".join(unknown[:5])) if unknown else ""))
    lo = [min(boxes[o.name][0][i] for o in objs) for i in range(3)]
    hi = [max(boxes[o.name][1][i] for o in objs) for i in range(3)]
    print("extents: min (%.2f, %.2f, %.2f)  max (%.2f, %.2f, %.2f) m"
          % (lo[0], lo[1], lo[2], hi[0], hi[1], hi[2]))

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

    print("\n[2b] AXIS ORIENTATION")
    bad = check_orientation(objs, boxes)
    print("    %d" % len(bad))
    for row in bad[:8]:
        print("      ", row)

    print("\n[2c] SECTION CONSISTENCY")
    bad = check_sections(objs, boxes)
    print("    %d members disagree with their section tag" % len(bad))
    for row in bad[:8]:
        print("      ", row)

    print("\n[2d] GRID ALIGNMENT")
    bad = check_alignment(objs, boxes)
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
        for nm_a, nm_b, d, vol in sorted(real, key=lambda r: -r[2])[:3]:
            print("          %6.1f mm  %9.6f m3  %s | %s"
                  % (d * 1000, vol, nm_a, nm_b))

    findings(objs, boxes, clashes)
    print("\n" + "=" * 68)


# ---------------------------------------------------------------------------
# Paired findings report
# ---------------------------------------------------------------------------

def findings(objs, boxes, clashes):
    """One block per defect, in the schema the review asks for.

    Single-object defects - scale, rotation, section, alignment - leave
    Object B blank rather than inventing a partner for them.
    """
    rows = []

    for name, scale in check_scale(objs):
        rows.append((name, "", "Object carries a non-unit scale %s; the "
                     "transform was never applied." % (scale,), "HIGH",
                     "Apply the scale so the mesh data carries the size. "
                     "Unapplied scale skews normals through the glTF export."))

    for name, axis, deg in check_rotation(objs):
        rows.append((name, "", "Rotated %.3f deg about %s, off the 90 deg "
                     "grid every other member follows." % (deg, axis), "HIGH",
                     "Snap the rotation to the nearest right angle."))

    for name, sec, got, want in check_sections(objs, boxes):
        rows.append((name, "", "Tagged %s but measures %s; the rest of that "
                     "group measures %s." % (sec, got, want), "HIGH",
                     "Rebuild the profile from the section table so the "
                     "geometry matches the label the viewer reads."))

    for name, why, dims in check_orientation(objs, boxes):
        rows.append((name, "", "%s - bounding box %s." % (why, dims), "HIGH",
                     "Re-place the member on its correct axis."))

    for label, off, example in check_alignment(objs, boxes):
        rows.append((example, "", "%s by %.1f mm." % (label, off * 1000),
                     "MEDIUM",
                     "Re-derive the position from the grid rather than "
                     "offsetting it by hand."))

    for name, z in check_support(objs, boxes):
        rows.append((name, "", "Underside at z=%.3f m with nothing beneath "
                     "it." % z, "HIGH",
                     "Seat the member on the element that carries it."))

    for group in check_duplicates(objs, boxes):
        rows.append((group[0], ", ".join(group[1:]),
                     "%d objects fill exactly the same volume." % len(group),
                     "MEDIUM",
                     "Emit the shared element once. Coincident geometry "
                     "z-fights on screen and doubles the export weight."))

    for key, entries in clashes.items():
        real = sorted([e for e in entries if e[2] > CONTACT],
                      key=lambda r: -r[2])
        if not real:
            continue
        nm_a, nm_b, d, vol = real[0]
        sev = "HIGH" if d > 0.010 else "MEDIUM"
        rows.append((nm_a, nm_b, "%s members interpenetrate by %.1f mm "
                     "(%.6f m3 shared); %d such pairs."
                     % (" x ".join(key), d * 1000, vol, len(real)), sev,
                     "Trim one member back to the face of the other, or "
                     "record the pair as a permitted assembly."))

    print("\n" + "=" * 68)
    print("FINDINGS - %d" % len(rows))
    print("=" * 68)
    if not rows:
        print("\nNo defects. Every check above returned clean.")
        return
    for i, (a, b, problem, sev, fix) in enumerate(rows, 1):
        print("\n%d. Object A: %s" % (i, a))
        print("   Object B: %s" % (b or "-"))
        print("   Problem:  %s" % problem)
        print("   Severity: %s" % sev)
        print("   Correction: %s" % fix)


report()
