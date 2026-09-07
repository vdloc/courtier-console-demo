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

    collisions(objs, boxes, clashes)
    findings(objs, boxes, clashes)
    print("\n" + "=" * 68)


def collisions(objs, boxes, clashes):
    """The named relationships, classified the way the review asks.

    CRITICAL is reserved for geometry that could not be built: a member
    meeting nothing, or driven through another. Magnitude ranks within a
    tier, it does not set the tier - a 5 mm lap is minor however precisely
    it is measured.
    """
    print("\n" + "=" * 68)
    print("COLLISION DETECTION")
    print("=" * 68)
    out = defaultdict(list)

    def add(sev, kind, a, b, detail):
        out[sev].append((kind, a, b, detail))

    print("\nCOLUMNS vs BEAMS")
    fit = beam_column_fit(objs, boxes)
    gaps = [r for r in fit if r[3] is not None and r[3] > 0.001]
    deep = [r for r in fit if r[3] is not None and r[3] < -0.001]
    none = [r for r in fit if r[3] is None]
    print("    %d beam ends tested, %d seated, %d gapped, %d over-inserted, "
          "%d unsupported" % (len(fit), len(fit) - len(gaps) - len(deep)
                              - len(none), len(gaps), len(deep), len(none)))
    for name, col, node, _ in none:
        add("CRITICAL", "beam misses column connection", name, "",
            "no column found at node %s carrying this end" % node)
    for name, col, node, g in sorted(gaps, key=lambda r: -r[3])[:6]:
        add("CRITICAL" if g > 0.010 else "MINOR",
            "beam misses column connection", name, col,
            "end stops %.1f mm short of the column face" % (g * 1000))
    for name, col, node, g in sorted(deep, key=lambda r: r[3])[:6]:
        add("CRITICAL" if -g > 0.010 else "MINOR",
            "beam enters column too deeply", name, col,
            "end is driven %.1f mm past the column face" % (-g * 1000))

    off = beam_datum(objs, boxes)
    print("    %d beams off the floor datum" % len(off))
    for name, d in sorted(off, key=lambda r: -abs(r[1]))[:6]:
        add("MEDIUM", "wrong height", name, "",
            "top flange sits %.1f mm %s the floor line"
            % (abs(d) * 1000, "above" if d > 0 else "below"))

    print("\nBEAMS vs BEAMS")
    bb = [r for k, rows in clashes.items() if set(k) == {"BEAM"} for r in rows]
    real = [r for r in bb if r[2] > CONTACT]
    print("    %d beam-to-beam overlaps, %d real" % (len(bb), len(real)))
    for nm_a, nm_b, d, vol in sorted(real, key=lambda r: -r[2])[:6]:
        add("CRITICAL", "accidental overlap", nm_a, nm_b,
            "beams share %.1f mm (%.6f m3)" % (d * 1000, vol))
    dups = [g for g in check_duplicates(objs, boxes)
            if any(family(n) == "BEAM" for n in g)]
    print("    %d duplicate members" % len(dups))
    for g in dups[:6]:
        add("MEDIUM", "duplicate member", g[0], ", ".join(g[1:]),
            "%d beams fill the same volume" % len(g))
    spacing = beam_spacing(objs, boxes)
    print("    %d beams off the bay spacing" % len(spacing))
    for name, length, bay in spacing[:6]:
        add("MEDIUM", "incorrect spacing", name, "",
            "spans %.3f m inside a %.3f m bay" % (length, bay))

    print("\nPIPES")
    pipe_pairs = [(k, r) for k, rows in clashes.items() if "PIPE" in k
                  for r in rows if r[2] > CONTACT]
    print("    %d pipe-vs-anything penetrations" % len(pipe_pairs))
    for k, (nm_a, nm_b, d, vol) in pipe_pairs[:6]:
        add("CRITICAL", "pipe through structure", nm_a, nm_b,
            "%s share %.1f mm" % (" x ".join(k), d * 1000))
    route = pipe_routing(objs, boxes)
    print("    %d routing problems" % len(route))
    for name, why in route[:6]:
        add("MEDIUM", "impossible routing", name, "", why)

    print("\nLOAD PATH")
    breaks, bare, planes = load_path(objs, boxes)
    print("    %d breaks in a column stack" % len(breaks))
    for lower, upper, gap in breaks[:6]:
        add("CRITICAL", "column stack broken", lower, upper,
            "%.1f mm between the two lifts" % (gap * 1000))
    print("    %d splice plates covering no joint" % len(bare))
    for name, mid, js in bare[:6]:
        add("CRITICAL", "splice covers no joint", name, "",
            "plate centred at z=%.2f m; joints at %s"
            % (mid, [round(j, 2) for j in js]))
    print("    bracing planes: %s"
          % ({k: sorted(v) for k, v in planes.items()} or "none"))
    for axis in ("X", "Y"):
        if not planes.get(axis):
            add("CRITICAL", "no lateral system", "frame", "",
                "no bracing in the %s direction at any storey" % axis)

    print("\nCONNECTIONS")
    orphans = orphan_parts(objs, boxes)
    print("    %d floating plates or disconnected bolts" % len(orphans))
    for name, why in orphans[:6]:
        add("CRITICAL", "disconnected part", name, "", why)
    joints = [g for g in check_duplicates(objs, boxes)
              if any(family(n) in ("ENDPLATE", "SPLICE", "BASEPLATE")
                     for n in g)]
    print("    %d duplicated joints" % len(joints))
    for g in joints[:6]:
        add("MEDIUM", "duplicated joint", g[0], ", ".join(g[1:]),
            "%d plates in the same place" % len(g))

    print("\n" + "-" * 68)
    for sev in ("CRITICAL", "MEDIUM", "MINOR"):
        rows = out[sev]
        print("\n%s - %d" % (sev, len(rows)))
        for kind, a, b, detail in rows:
            print("    %s" % kind)
            print("      A: %s" % a)
            print("      B: %s" % (b or "-"))
            print("      %s" % detail)
        if not rows:
            print("    none")


# ---------------------------------------------------------------------------
# Collision detection between named structural relationships
#
# The clash pass asks "does anything overlap that should not". These ask a
# harder question: does each member meet the one it is supposed to meet.
# A beam that stops 40 mm short of its column overlaps nothing at all, so
# no amount of intersection testing will ever mention it.
# ---------------------------------------------------------------------------

AXIS = {"beam_x": 0, "beam_y": 1}


def grid_lines(objs, boxes):
    """Column centre lines, clustered out of the columns themselves.

    level_z() and grid_x() live in the generator's namespace, which a
    second -P script cannot reach, so the grid is recovered from the
    steel rather than assumed.
    """
    def cluster(values):
        out = []
        for v in sorted(values):
            if not out or v - out[-1] > 0.010:
                out.append(v)
        return out

    cols = [o for o in objs if family(o.name) == "COLUMN"]
    xs, ys = [], []
    for o in cols:
        lo, hi = boxes[o.name]
        xs.append((lo[0] + hi[0]) * 0.5)
        ys.append((lo[1] + hi[1]) * 0.5)
    return cluster(xs), cluster(ys)


def beam_column_fit(objs, boxes):
    """Signed distance from each beam end to the column it frames into.

    Positive is a gap - the beam never reaches its connection. Negative is
    penetration - the beam is driven into the column. Zero is the trim
    working. Each beam is matched to its column through the grid
    reference it already carries, not by searching space.
    """
    cols = defaultdict(list)
    for o in objs:
        if family(o.name) == "COLUMN":
            cols[o.get("grid_ref")].append(o)

    rows = []
    for o in objs:
        axis = AXIS.get(o.get("element_type") or "")
        if axis is None:
            continue
        ref = o.get("grid_ref") or ""
        if "-" not in ref:
            continue
        lo, hi = boxes[o.name]
        for end, node in zip((0, 1), ref.split("-", 1)):
            # The column carrying this end is the one at that node whose
            # own span brackets the beam's top - the storey below it.
            support = None
            for c in cols.get(node, ()):
                clo, chi = boxes[c.name]
                if clo[2] < hi[2] - 0.001 <= chi[2] + 0.001:
                    support = c
                    break
            if support is None:
                rows.append((o.name, "", "no column at node %s" % node, None))
                continue
            clo, chi = boxes[support.name]
            # Gap measured along the beam's own axis, toward its column.
            gap = (lo[axis] - chi[axis]) if end == 0 else (clo[axis] - hi[axis])
            rows.append((o.name, support.name, node, gap))
    return rows


def beam_datum(objs, boxes):
    """Every beam on a floor carries its top flange at the same height.

    The floor line cannot be read off the columns: a column runs past the
    floor to its splice, so a column top is 600 mm above the level, not on
    it. Take the datum from the beams themselves instead - group them by
    the level they are tagged with and flag the one that disagrees with
    its own floor.
    """
    floors = defaultdict(list)
    for o in objs:
        if AXIS.get(o.get("element_type") or "") is None:
            continue
        floors[o.get("level")].append(o)

    rows = []
    for level, members in floors.items():
        tops = Counter(round(boxes[o.name][1][2], 3) for o in members)
        (datum, _), = tops.most_common(1)
        for o in members:
            off = boxes[o.name][1][2] - datum
            if abs(off) > 0.002:
                rows.append((o.name, off))
    return rows


def beam_spacing(objs, boxes):
    """Each beam spans one bay, less the half column it stops against at
    either end. A span that is not a bay means the grid drifted."""
    xs, ys = grid_lines(objs, boxes)
    rows = []
    for o in objs:
        axis = AXIS.get(o.get("element_type") or "")
        if axis is None:
            continue
        lines = xs if axis == 0 else ys
        lo, hi = boxes[o.name]
        length = hi[axis] - lo[axis]
        # Nearest pair of grid lines bracketing this beam.
        bays = [b - a for a, b in zip(lines, lines[1:])]
        if not bays:
            continue
        best = min(bays, key=lambda b: abs(b - length))
        # The beam is the bay less one column width; allow any column size.
        if not (0.20 <= best - length <= 0.60):
            rows.append((o.name, length, best))
    return rows


def pipe_routing(objs, boxes):
    """Clash testing cannot see a badly routed pipe that happens to miss
    everything. Check the run hangs under the steel, stays inside the
    building, and does not sit on a column line where it would have to
    pass through one."""
    xs, ys = grid_lines(objs, boxes)
    beams = [o for o in objs if family(o.name) == "BEAM"]
    rows = []
    for o in objs:
        if family(o.name) != "PIPE":
            continue
        lo, hi = boxes[o.name]
        # Soffit of the beams the run passes beneath.
        above = [boxes[b.name][0][2] for b in beams
                 if boxes[b.name][0][2] > hi[2] - 0.001]
        if above and min(above) - hi[2] > 1.0:
            rows.append((o.name, "hangs %.2f m below the nearest soffit"
                         % (min(above) - hi[2])))
        if not above:
            rows.append((o.name, "no beam above the run at any point"))
        if lo[0] < xs[0] - 0.5 or hi[0] > xs[-1] + 0.5 \
                or lo[1] < ys[0] - 0.5 or hi[1] > ys[-1] + 0.5:
            rows.append((o.name, "run leaves the building footprint"))
        for gx in xs:
            if lo[0] < gx < hi[0] and (hi[0] - lo[0]) < 1.0:
                rows.append((o.name, "run sits on column grid line x=%.1f"
                             % gx))
    return rows


def load_path(objs, boxes):
    """Can load actually reach the ground.

    Three questions clash detection cannot ask: is each column stack
    unbroken, does each splice plate cover the joint it is named for, and
    is there a lateral system in both directions at every storey. A frame
    of pinned joints with no bracing is a mechanism however well its
    members are trimmed.
    """
    cols = defaultdict(list)
    for o in objs:
        if family(o.name) == "COLUMN":
            cols[o.get("grid_ref")].append(o)

    breaks, bare = [], []
    joints = defaultdict(list)
    for ref, stack in cols.items():
        stack = sorted(stack, key=lambda o: boxes[o.name][0][2])
        for lower, upper in zip(stack, stack[1:]):
            gap = boxes[upper.name][0][2] - boxes[lower.name][1][2]
            joints[ref].append(boxes[lower.name][1][2])
            if abs(gap) > 0.002:
                breaks.append((lower.name, upper.name, gap))

    for o in objs:
        if family(o.name) != "SPLICE":
            continue
        lo, hi = boxes[o.name]
        ref = o.get("grid_ref")
        if not any(lo[2] < j < hi[2] for j in joints.get(ref, ())):
            bare.append((o.name, (lo[2] + hi[2]) * 0.5,
                         joints.get(ref, [])))

    # Bracing planes, counted per storey and per direction.
    planes = defaultdict(set)
    for o in objs:
        if family(o.name) != "BRACE":
            continue
        lo, hi = boxes[o.name]
        span_x, span_y = hi[0] - lo[0], hi[1] - lo[1]
        axis = "X" if span_x > span_y else "Y"
        planes[axis].add(round((lo[2] + hi[2]) * 0.5, 1))
    return breaks, bare, planes


def orphan_parts(objs, boxes):
    """Plates bolted to nothing, and bolts through nothing.

    check_support() only ever looked at load-bearing members, so the
    fabrication hardware was never tested for being attached at all.
    """
    def touching(a_lo, a_hi, b_lo, b_hi, tol=0.005):
        return all(a_lo[i] - tol <= b_hi[i] and b_lo[i] - tol <= a_hi[i]
                   for i in range(3))

    hosts = [o for o in objs
             if family(o.name) in ("BEAM", "COLUMN", "PAD", "BRACE")]
    plates = [o for o in objs
              if family(o.name) in ("ENDPLATE", "SPLICE", "BASEPLATE",
                                    "STIFFENER", "GUSSET")]
    rows = []
    for p in plates:
        plo, phi = boxes[p.name]
        if not any(touching(plo, phi, *boxes[h.name]) for h in hosts):
            rows.append((p.name, "plate is attached to no member"))

    anchors = plates + hosts
    for b in objs:
        if family(b.name) != "BOLT":
            continue
        blo, bhi = boxes[b.name]
        if not any(touching(blo, bhi, *boxes[a.name]) for a in anchors):
            rows.append((b.name, "bolt passes through nothing"))
    return rows


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
