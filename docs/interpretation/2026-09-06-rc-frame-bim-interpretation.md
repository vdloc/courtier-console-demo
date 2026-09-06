# 3D Interpretation Document — RC Frame Building (Structural Shell + MEP Overlay)

**Source:** reference image, side-by-side comparison graphic captioned
"3D Modelling" (left) / "BIM Modeling" (right).
**Date:** 2026-09-06
**Author role:** structural engineer / technical artist, joint read.

---

## 0. Premise correction (read first)

The brief describes the reference as "a simplified technical drawing of a steel
structure." It is neither simplified, technical, nor steel:

- It is a pair of **rendered 3D models**, not a drawing — no dimension lines, no
  grid bubbles, no section marks, no title block.
- The left panel is a **cast-in-place reinforced concrete (RC) frame**. Evidence:
  square/rectangular grey columns of constant section with no flange-web
  silhouette; monolithic beam-to-column junctions with no visible connection
  hardware; thick flat floor plates with concrete-grey surface and formwork-scale
  edges; drop beams cast integral with the slab soffit. A steel frame at this
  scale would show I-sections, base plates, gusseted brace connections, and
  bolt-pattern shadows. None are present.
- The yellow linear elements on the roof and floor edges are **temporary edge
  protection guard-rail** (site safety), not structural members.
- The right panel is the **same class of building** shown as an LOD 350/400
  dollhouse cutaway: HVAC supply ducts (yellow rectangular runs), piping
  (magenta/pink), suspended ceiling grid, partitions, doors, and furniture.

The component list in the brief ("curved members, pipe sections, connection
plates, support brackets") is prefixed *"Example:"* in the prompt and is
boilerplate. Curved members, gusset plates and brackets **do not exist in this
reference** and are not invented here. Pipes exist — but as MEP services in the
right panel, not as structure.

**The organising idea of this document:** the two panels are one building at two
information levels. Left = structural shell (LOD 200/300). Right = same shell
with architecture and services (LOD 350/400). This maps directly onto the
delivery target: **one layered GLB set, with a section-box cutaway** that
reproduces the right panel's view on demand.

---

## A. Overall structure

### A.1 Structural purpose

A **multi-storey reinforced concrete moment frame** carrying gravity load through
a regular orthogonal column grid, with lateral stability provided by frame action
(beam–column moment continuity) rather than by bracing or shear walls — no
bracing or core is visible in the model.

Load path, top-down:

1. Floor slab spans one- or two-way onto **secondary/edge beams**.
2. Beams span between **columns** on the grid.
3. Columns carry accumulated axial load down through each storey.
4. Ground-storey columns terminate into **pad or raft foundations** (not modelled
   in the reference — the model is cut at ground floor level).

The frame is monolithic: beams, columns and slab are cast as one continuous
reinforced element, so every joint is fixed (moment-transferring) by default.

### A.2 Probable industrial application

The proportions — regular bays, uniform storey heights, flat roof with edge
protection, a single roof-penetrating cylindrical stack, and the furnished
interior in the right panel — read as **commercial office or mid-rise
residential/mixed-use**, shown *at the structural-completion stage* (frame cast,
no cladding, no infill walls). The graphic's purpose is BIM-service marketing, so
the subject is deliberately generic: a "typical" RC frame.

Not: industrial process plant (no pipe racks, no equipment foundations, no crane
girders), not a car park (edge beams and full floor plates present, no ramps).

### A.3 Assembly logic (construction sequence — drives the animation plan)

Cast-in-place RC is built **storey by storey**, and this ordering is the
authoritative sequence for any build-up animation:

1. Foundations / pile caps / raft (below the modelled cut).
2. Column starter bars projecting from foundation.
3. **Storey N columns**: cage tied, formwork erected, concrete poured, cured,
   stripped.
4. **Storey N+1 floor**: falsework/props → beam and slab formwork → beam cages
   and slab mesh tied → cast-in services (sleeves, conduits) → single monolithic
   pour of beams + slab together.
5. Props remain 7–28 days; back-propping while the next storey proceeds.
6. Repeat 3–5 per storey.
7. Roof slab, then roof plant and the cylindrical stack.
8. Edge protection guard-rail follows each completed slab (visible in the image
   as yellow rails on every open edge).

Critically: **the slab and its beams are one pour**. Any animation showing beams
landing on columns like steel erection is wrong for this structure.

### A.4 Storey count and grid — derived from countable features

Method: count floor plates and columns on visible faces *before* assigning
dimensions, so every number below is traceable.

| Countable feature | Read from image | Note |
|---|---|---|
| Floor plates above ground | 3 suspended floors + 1 roof slab | 4 slabs total |
| Storeys | 4 (G + 3) | ground storey open, columns exposed |
| Column lines, long face | 5 (≈ 4 bays) | front-left elevation |
| Column lines, short face | 4 (≈ 3 bays) | right return elevation |

The source model is small and low-resolution; treat the bay counts as **±1 bay**
and parameterise them (see §D) rather than hard-coding.

### A.5 Approximate dimensions (derived, standard-based)

Bay spans and storey heights assigned from ordinary RC practice for this building
class, then multiplied out — **not** measured off the image:

| Quantity | Value | Basis |
|---|---|---|
| Typical bay, X | 7.2 m | economic office RC grid (6.0–7.5 m) |
| Typical bay, Y | 6.0 m | shorter span direction |
| Storey height (floor-to-floor) | 3.4 m | office: 3.0–3.6 m typical |
| Clear height under beam | ≈ 2.7 m | 3.4 − 0.55 beam drop − 0.15 finishes |
| Overall footprint | **28.8 m × 18.0 m** | 4 × 7.2 by 3 × 6.0 |
| Overall height (FFL to roof top) | **13.6 m** | 4 × 3.4 |
| Gross floor area | ≈ 518 m²/floor, ≈ 2 073 m² total | footprint × 4 |

### A.6 Proportions

- Plan aspect ratio **1.6 : 1** (28.8 / 18.0) — a squat, stable rectangle.
- Height : least plan dimension **13.6 / 18.0 = 0.76** — very low slenderness.
  Confirms lateral stability by frame action alone is plausible; no core needed.
- Storey height : bay span **3.4 / 7.2 ≈ 0.47** — the classic "wide and low" RC
  office proportion, and why the model reads as horizontally banded.
- Column section : storey height ≈ 0.5 / 3.4 ≈ 1 : 7 — visually stocky, matching
  the render.

---

## B. Components

Every component below is present in the reference. Nothing is added.

### B.1 Structural shell (left panel)

---

**1. Ground-storey column**

- **Purpose:** carries the full accumulated gravity load of all storeys above
  into the foundation; forms the lower half of every ground-level moment joint.
  Highest axial demand in the structure.
- **Approximate dimensions:** 500 × 500 mm square section × 3 400 mm storey
  height (cast height ≈ 2 850 mm between slab soffits).
- **Material:** reinforced concrete, C30/37 (≈ 4 350 psi), density 2 400 kg/m³.
  Reinforcement: 8 × Ø25 mm longitudinal bars, Ø10 mm links at 200 mm centres,
  40 mm cover.
- **Connection method:** **monolithic**. Starter bars lapped from the foundation
  (lap ≈ 40 × bar Ø = 1 000 mm), continuous into the slab above where column bars
  lap with the next storey's starters. No bolts, no plates, no welds.
- **Blender object type:** `MESH` — box primitive, generated by script from the
  grid table. Bevel 5 mm on vertical arrises (formwork chamfer).

---

**2. Upper-storey column**

- **Purpose:** as above, with reduced axial load at height.
- **Approximate dimensions:** 400 × 400 mm from level 2 upward. The section
  step-down is standard practice and adds engineering credibility to the model.
- **Material:** RC, C30/37. 8 × Ø20 longitudinal, Ø10 links @ 200.
- **Connection method:** monolithic; bars lapped through each floor slab.
- **Blender object type:** `MESH`, same generator, different section parameter.

---

**3. Primary beam (spanning the 7.2 m direction)**

- **Purpose:** collects slab load and spans column-to-column; forms the beam half
  of the moment frame resisting lateral load.
- **Approximate dimensions:** 300 mm wide × 600 mm overall depth (≈ span/12),
  i.e. **400 mm drop** below a 200 mm slab soffit. Length = 7 200 mm minus column
  faces.
- **Material:** RC, C30/37. Bottom steel 4 × Ø25 at midspan; top steel 4 × Ø20
  over supports (hogging); Ø10 links @ 150 near supports, @ 250 midspan.
- **Connection method:** monolithic with column and slab, cast in one operation;
  beam top steel anchored *through* the joint into the adjacent span (continuity
  reinforcement). This is what makes the joint fixed.
- **Blender object type:** `MESH` — box, generated. Its top 200 mm is coincident
  with the slab; model the **drop only** and let the slab own the rest, to avoid
  z-fighting on the soffit plane.

---

**4. Secondary / edge beam**

- **Purpose:** perimeter beam closing the floor plate; supports slab edge,
  cladding load, and the guard-rail posts. Visible in the image as the pronounced
  band at every floor edge.
- **Approximate dimensions:** 250 mm wide × 500 mm overall depth (300 mm drop).
- **Material:** RC, C30/37. Bottom 3 × Ø20, top 3 × Ø16, Ø10 links @ 200. Edge
  beams also carry torsion — closed links mandatory.
- **Connection method:** monolithic; cast with the slab.
- **Blender object type:** `MESH`, generated along the plan perimeter loop.

---

**5. Floor slab (suspended)**

- **Purpose:** carries occupancy load to beams; acts as a **rigid diaphragm**
  distributing lateral load to the columns. The most visually dominant element in
  the reference.
- **Approximate dimensions:** 28 800 × 18 000 × **200 mm** thick (two-way slab on
  beams, short-span/30 rule for a 6.0 m span).
- **Material:** RC, C30/37. Two-way mesh: Ø12 @ 150 bottom both ways, Ø12 @ 200
  top over supports. Cover 25 mm.
- **Connection method:** monolithic with beams and columns; slab reinforcement
  continues over supports without interruption.
- **Blender object type:** `MESH` — a solidified plane, one object per storey,
  with column penetrations **boolean-cut at generation time**, not at runtime.

---

**6. Roof slab**

- **Purpose:** as floor slab, plus weather envelope and plant support; carries the
  stack and roof equipment.
- **Approximate dimensions:** as floor slab, 250 mm thick, with a 1 : 60 fall to
  drainage (≈ 1° tilt — worth modelling; it catches light and reads as real).
- **Material:** RC C30/37 + waterproof membrane + insulation (≈ 150 mm build-up).
- **Connection method:** monolithic.
- **Blender object type:** `MESH`, same generator, tilt applied per drainage
  field.

---

**7. Temporary edge protection guard-rail**

- **Purpose:** site fall protection at every open slab edge. **Not structural.**
  These are the yellow lines in the image, and they are the strongest single cue
  that the model depicts a building *under construction*.
- **Approximate dimensions:** posts at 2 000 mm centres, 1 100 mm high; top rail,
  mid rail (≈ 500 mm), toe board 150 mm high at slab level. Post section
  ≈ 50 × 50 mm.
- **Material:** **the only steel in the reference** — galvanised or powder-coated
  yellow proprietary steel system; occasionally timber.
- **Connection method:** clamped/bolted to the slab edge via cast-in socket or
  screw-on base plate. A genuinely bolted connection — but on temporary works.
- **Blender object type:** `CURVE` for the rail runs (bevelled to a profile,
  very cheap) + instanced `MESH` posts. Ideal Geometry Nodes case: one closed
  perimeter curve per storey, `Instance on Points` for posts, `Curve to Mesh`
  for rails.

---

**8. Roof stack / flue**

- **Purpose:** vertical service penetration — boiler flue, kitchen extract, or
  smoke vent — rising through the roof slab. Cylindrical, dark, offset from
  centre in the image.
- **Approximate dimensions:** Ø600 mm × 2 000 mm above roof level.
- **Material:** twin-wall insulated steel flue, dark grey.
- **Connection method:** flanged sections; base flashed and sealed into a
  cast-in roof upstand.
- **Blender object type:** `MESH` cylinder, 24-sided, with separate cap and
  flange ring.

---

**9. Column head / beam–column joint zone**

- **Purpose:** the region where beam and column reinforcement interlock; the
  hinge of the whole moment frame. Not a separate object in the reference, but
  the detail the visualization must get *conceptually* right.
- **Approximate dimensions:** joint core = column section × beam depth,
  500 × 500 × 600 mm.
- **Material:** RC, congested with reinforcement; often a higher grade than the
  beams (C40/50) where column loads are high.
- **Connection method:** monolithic. Beam bottom bars anchored into the joint,
  top bars continuous through, column links continued through the joint depth
  (a code requirement in seismic detailing).
- **Blender object type:** **no separate geometry.** It emerges where column and
  beam meshes intersect. Represent it as an *annotation hotspot* in the Three.js
  layer — exactly the kind of "connection detail" a structural client clicks on.

---

**10. Foundation (implied, below the cut)**

- **Purpose:** spreads column load into the ground.
- **Approximate dimensions:** pad footing 2 400 × 2 400 × 700 mm under each
  ground column, top at −1 000 mm.
- **Material:** RC, C25/30, blinding below.
- **Connection method:** column starter bars cast into the pad.
- **Blender object type:** `MESH`, generated on the same grid. Include it — it
  enables a "reveal below ground" toggle, which reads as digital-twin capability.

### B.2 Architecture + MEP overlay (right panel)

---

**11. Internal partition**

- **Purpose:** space division; non-loadbearing.
- **Approximate dimensions:** 100–125 mm thick, full storey height.
- **Material:** metal-stud + plasterboard, or blockwork.
- **Connection method:** head deflection track under the slab soffit (must allow
  slab deflection — a real detail worth annotating), fixed at floor.
- **Blender object type:** `MESH`, solidified from a floorplan curve.

---

**12. HVAC supply duct**

- **Purpose:** conditioned air distribution — the bright yellow rectangular runs
  dominating the right panel.
- **Approximate dimensions:** main run 600 × 400 mm; branches 400 × 250 mm and
  300 × 200 mm; routed in the ceiling void beneath the beam soffit.
- **Material:** galvanised sheet steel, 0.8 mm gauge for this size class;
  external insulation on supply runs.
- **Connection method:** flanged (Mez/TDC) joints every 1.2–3.0 m; drop rods
  anchored to the slab soffit at ≤ 2.4 m centres.
- **Blender object type:** `CURVE` (route) + **rectangular bevel profile** →
  `Curve to Mesh`. Fittings (bends, tees, reducers) as instanced `MESH` only at
  direction changes. The single most important performance decision in the whole
  model — see §D.7.

---

**13. Pipework (heating / chilled water / sprinkler)**

- **Purpose:** fluid distribution — the magenta/pink runs.
- **Approximate dimensions:** mains DN80 (88.9 mm OD), branches DN50 (60.3 mm)
  and DN25 (33.7 mm); sprinkler mains DN100.
- **Material:** carbon steel to EN 10255 (medium grade) or copper for small
  branches; insulated on heating/chilled services.
- **Connection method:** welded or grooved-coupling (Victaulic) on mains,
  threaded on small bore; clevis hangers to slab soffit at 2.5–3.0 m centres.
- **Blender object type:** `CURVE` with circular bevel, radius per DN. Bends as
  curve fillets — **not** separate meshes; pipe bends are genuinely swept, unlike
  duct fittings.

---

**14. Suspended ceiling grid**

- **Purpose:** conceals the services above; the flat plane the cutaway looks
  down through.
- **Approximate dimensions:** 600 × 600 mm module, 24 mm exposed tee, void depth
  ≈ 500 mm below beam soffit.
- **Material:** pre-finished steel tee sections + mineral fibre tiles.
- **Connection method:** hanger wires to slab soffit at 1.2 m centres.
- **Blender object type:** a single `MESH` plane with a **tiled texture**, never
  modelled grid bars. Modelling the tees is the second-largest polygon trap after
  duct fittings.

---

**15. Lighting fixtures / diffusers / terminals**

- **Purpose:** the point elements terminating every service run — grilles,
  luminaires, sprinkler heads.
- **Approximate dimensions:** 600 × 600 mm recessed luminaire; 300 × 300 mm
  supply diffuser; Ø15 mm sprinkler head at 3.0–4.0 m spacing.
- **Material:** steel/aluminium, painted white.
- **Connection method:** clipped into the ceiling grid; flex duct to diffuser.
- **Blender object type:** `MESH`, **instanced**, one source object per type.

---

**16. Furniture and fit-out**

- **Purpose:** scale and context only. Zero engineering value.
- **Blender object type:** low-poly `MESH` proxies, or omit. Budget them last —
  the first thing to cut when the GLB exceeds target.

---

## C. Coordinate system

### C.1 Blender (authoring, Z-up)

| Axis | Direction | Meaning |
|---|---|---|
| **X** | +X = East, along the **long facade** (28.8 m) | grid lines **1…5**, bay spacing 7.2 m |
| **Y** | +Y = North, building **depth** (18.0 m) | grid lines **A…D**, bay spacing 6.0 m |
| **Z** | +Z = **up** | storey levels, +3.4 m per floor |

**Origin (0, 0, 0) = intersection of grid A-1 at ground-storey Finished Floor
Level.** Surveying convention. Consequences: every level is a clean multiple of
3.4; every column centre is a clean multiple of 7.2 / 6.0; foundations are the
only negative-Z geometry. Level naming: `L00` = 0.0, `L01` = +3.4, `L02` = +6.8,
`L03` = +10.2, `RF` = +13.6.

### C.2 glTF / Three.js (delivery, Y-up)

**The glTF exporter rewrites the axes.** After export:

| Blender | glTF / Three.js |
|---|---|
| +X | +X (unchanged) |
| +Y (depth / North) | **−Z** |
| +Z (up) | **+Y** |

Every camera position, section-plane normal, and raycast assumption on the
Three.js side must be written in **Y-up**. Storey height is `+Y`; the building
footprint lies in the **XZ plane**. Do not disable the conversion — fighting the
exporter causes more bugs than it solves.

### C.3 Standard views

Defined off the **structural grid**, not off the reference image's camera.

| View | Direction | Blender camera (Z-up) | Three.js camera (Y-up) | Shows |
|---|---|---|---|---|
| **Front elevation** | looking +Y (North) | (14.4, −60, 6.8) | (14.4, 6.8, 60) → −Z | long facade, 4 bays × 4 storeys |
| **Side elevation** | looking −X (West) | (60, 9.0, 6.8) | (60, 6.8, −9.0) | 3-bay depth, column spacing |
| **Top / plan** | looking down | (14.4, 9.0, 60) | (14.4, 60, −9.0) → −Y | column grid, beam layout, slab edges |
| **Isometric hero** | SE, 30° above | (55, −45, 30) | (55, 30, 45) | matches the reference's left panel |
| **Cutaway / dollhouse** | hero + section box | clipping planes | `localClippingEnabled` + `Plane[]` | reproduces the right panel |

Front is the **long** face (X extent), matching the reference's dominant
elevation.

---

## D. Modeling strategy

### D.1 The governing decision: generate, don't model

This building has **~20 columns per storey × 4 storeys, ~30 beams per storey × 4,
4 slabs** — roughly 250 structural objects, every one a box on a regular grid.
Modelling them by hand is both slow and wrong: the client *will* ask "what if the
bay is 6.0 instead of 7.2," and a hand-built model cannot answer.

**Build a bay-grid generator driven by a single table.** This is the pattern
already proven in this repo — `/home/vdloc/Projects/courtier-console-demo/js/dimensions.js`
holds one dimension table and both the 2D SVG and 3D Three.js renderers draw from
it, so the two views cannot disagree. Extend that principle across the Blender
boundary: the same JSON table feeds the Blender generator *and* ships alongside
the GLB for the Three.js annotation layer.

```
grid = {
  x_bays:  [7.2, 7.2, 7.2, 7.2],     # metres; len = bay count
  y_bays:  [6.0, 6.0, 6.0],
  storeys: [3.4, 3.4, 3.4, 3.4],
  col:          {ground: 0.50, upper: 0.40},
  beam_primary: {w: 0.30, d: 0.60},
  beam_edge:    {w: 0.25, d: 0.50},
  slab:         {t: 0.20, roof_t: 0.25},
}
```

### D.2 Per-component technique

| Component | Type | Technique | Why |
|---|---|---|---|
| Columns | `MESH` | scripted box per grid node per storey | regular, orthogonal, boolean-free |
| Beams | `MESH` | scripted box per grid edge | ditto |
| Slabs | `MESH` | plane + Solidify, columns boolean-subtracted **at build time** | one object per storey keeps draw calls low |
| Foundations | `MESH` | scripted box per ground node | same generator, negative Z |
| Guard-rail | `CURVE` + GN | perimeter curve → `Curve to Mesh` (rails) + `Instance on Points` (posts) | linear, repetitive, cheap |
| Stack | `MESH` | cylinder, 24 segments | single object |
| Ducts | `CURVE` + GN | route curve + rectangular profile → `Curve to Mesh`; fittings instanced at kinks | see §D.7 |
| Pipes | `CURVE` | circular bevel, filleted bends | genuinely swept geometry |
| Ceiling | `MESH` | plane + tiled texture | never model tees |
| Terminals, luminaires | `MESH` | one source, `Collection Instance` | instancing survives to GPU instancing on export |
| Furniture | `MESH` | low-poly proxy, decimated | first to cut |

Rule of thumb: **prismatic and orthogonal → mesh box; linear and swept → curve;
repeated → instance.** Nothing in this building justifies NURBS, subdivision, or
sculpting.

### D.3 Object naming — grid-addressed, machine-parseable

Naming is not cosmetic here: the Three.js layer selects, highlights and annotates
by parsing these names out of the GLB node tree. Use a strict schema:

```
<DISCIPLINE>_<TYPE>_<LEVEL>_<GRIDREF>[_<VARIANT>]

STR_COL_L00_A1             ground column at grid A-1
STR_COL_L02_C3
STR_BMP_L01_A1-B1          primary beam, level 1, spanning A1 to B1
STR_BME_L01_A1-A2          edge beam
STR_SLB_L01                level-1 slab (single object)
STR_FND_L00_A1             pad footing
TMP_RAIL_L01_PERIM         guard-rail run
MEP_DUCT_L02_SUP_MAIN      supply duct main
MEP_PIPE_L02_CHW_BR07      chilled-water branch 07
ARC_CEIL_L02
ARC_PART_L02_012
```

Discipline prefixes (`STR` / `ARC` / `MEP` / `TMP`) become the **layer toggles**
in the viewer for free. Grid refs become the annotation labels for free.

### D.4 Hierarchy

Blender collections export as glTF nodes; mirror the discipline/level split so
the viewer can toggle by traversing one level of the tree.

```
BUILDING_A
├── STRUCTURE
│   ├── FOUNDATIONS         STR_FND_*
│   ├── LEVEL_00            STR_COL_L00_*
│   ├── LEVEL_01            STR_COL_L01_*, STR_BMP_L01_*, STR_BME_L01_*, STR_SLB_L01
│   ├── LEVEL_02            …
│   ├── LEVEL_03            …
│   └── ROOF                STR_SLB_RF, roof stack
├── TEMPORARY_WORKS
│   └── EDGE_PROTECTION     TMP_RAIL_L01..RF
├── ARCHITECTURE
│   ├── PARTITIONS_L01..L03
│   └── CEILINGS_L01..L03
├── MEP
│   ├── HVAC                MEP_DUCT_*, terminals
│   ├── PIPEWORK            MEP_PIPE_*
│   └── ELECTRICAL          luminaires, containment
└── CONTEXT
    ├── FURNITURE           (cuttable)
    └── GROUND_PLANE
```

Parenting: keep transforms **flat** (every object at world origin with baked
coordinates) except for instanced collections. Deep parent chains cost node
traversal on load and complicate the section-box maths.

### D.5 Modifiers

| Modifier | Applied to | Purpose | Apply before export? |
|---|---|---|---|
| **Solidify** | slabs, partitions, ceilings | thickness from a plane | Yes |
| **Bevel** (0.005 m, 2 seg, angle 30°) | columns, beams | formwork arris chamfer — the highest-value realism modifier; without it every edge is a mathematically perfect line and reads as CG | Yes |
| **Boolean (Difference)** | slabs − columns, slabs − duct penetrations | clean openings | Yes, at build time |
| **Array** | guard-rail posts, hangers | repetition | Prefer GN instancing |
| **Geometry Nodes** | rails, ducts, hangers, terminals | procedural instancing | Realise on export |
| **Weighted Normal** | all structural | clean shading on beveled boxes | Yes |
| **Decimate** | furniture only | budget control | Yes |

**Never** apply Subdivision Surface to a structural member. Concrete is faceted
and flat; subdivision inflates it and reads instantly as fake.

### D.6 Topology

- **All-quad, orthogonal, no n-gons on visible faces.** Every structural member
  is a box; there is no excuse for messy topology here.
- **Column: 8 verts + bevel ≈ 48 verts.** Beam: same. A ~250-object structural
  shell lands at roughly **15 k triangles** — trivially cheap.
- Slabs: quad plane, subdivided only where boolean cuts require it. Clean up
  boolean residue at generation time (limited dissolve, merge by distance
  0.1 mm).
- **UVs:** box-project structural members at a **consistent world-space texel
  density** (recommend 512 px/m) so concrete texture scale never jumps between a
  column and the slab beside it. This is the difference between "textured" and
  "believable."
- Curve resolution: bevel resolution 6–8 for round pipe (12 is invisible waste at
  web scale); profile resolution 1 for rectangular duct.
- Normals: all outward. `Shade Flat` on structure; `Shade Auto Smooth` (30°) only
  on the round stack and pipework.

### D.7 Performance cliff — scope the MEP honestly

The structural shell is ~15 k triangles. A **fully modelled MEP floor** — every
duct fitting, hanger and tee modelled, ceiling grid as geometry — is roughly an
**order of magnitude heavier per floor**, and there are three floors. This is
where the web-performance requirement dies.

Mitigations, in order of value:

1. Ducts as swept curves; **fittings only at direction changes**, instanced from
   a library of ~8 fitting types.
2. Ceiling grid as a **texture**, never geometry.
3. Terminals, luminaires, sprinkler heads: **instanced**, one source mesh each.
4. Hangers/drop rods: instanced, or omitted above the ceiling plane where they
   are never seen.
5. Furniture: proxy or cut.
6. MEP shipped as a **separate GLB, lazy-loaded** when the user enables the
   layer — the structural view must never pay for services it isn't showing.

---

## E. Engineering accuracy

The brief asks for "steel thickness, beam profile, pipe diameter, connection
style." Three of those four do not apply to an RC frame; answering them literally
is where fabrication would start. They are reinterpreted below to their RC
equivalents, with the steel questions answered where steel genuinely exists
(reinforcement, guard-rail, ductwork, pipework).

### E.1 Concrete sections — the RC answer to "beam profile"

| Member | Section (w × d) | Sizing rule | Concrete |
|---|---|---|---|
| Ground column | 500 × 500 mm | axial ≈ 0.4 f_ck A_c | C30/37 |
| Upper column | 400 × 400 mm | reduced load with height | C30/37 |
| Primary beam | 300 × 600 mm | depth ≈ span/12 (7 200/12 = 600) | C30/37 |
| Edge beam | 250 × 500 mm | depth ≈ span/12; width torsion-governed | C30/37 |
| Floor slab | 200 mm | two-way on beams, ≈ short span/30 | C30/37 |
| Roof slab | 250 mm | + drainage falls, plant loading | C30/37 |
| Pad footing | 2 400 × 2 400 × 700 mm | 200 kPa bearing assumed | C25/30 |

Grade notation: **C30/37** = 30 MPa cylinder / 37 MPa cube characteristic
strength at 28 days (Eurocode); ≈ **4 350 psi** in ACI terms.

### E.2 Reinforcement — the RC answer to "steel thickness"

| Element | Longitudinal | Transverse | Cover |
|---|---|---|---|
| Ground column | 8 × Ø25 | Ø10 links @ 200 | 40 mm |
| Upper column | 8 × Ø20 | Ø10 links @ 200 | 40 mm |
| Primary beam | 4 × Ø25 bottom; 4 × Ø20 top over supports | Ø10 links @ 150 / 250 | 35 mm |
| Edge beam | 3 × Ø20 bottom; 3 × Ø16 top | Ø10 **closed** links @ 200 (torsion) | 35 mm |
| Slab | Ø12 @ 150 both ways bottom; Ø12 @ 200 top at supports | — | 25 mm |
| Footing | Ø16 @ 150 both ways bottom | — | 50 mm (75 mm cast against blinding) |

Steel grade **B500B** (500 MPa yield, Class B ductility) — the global default.
Lap lengths ≈ 40 × bar diameter. Reinforcement ratio typically 1–2 % in columns,
0.5–1 % in beams.

**Modelling note:** do *not* model rebar as geometry across the whole building —
millions of triangles for a detail nobody sees. Model **one exemplar joint** (the
beam–column cage at grid B-2, level 1) as a separate high-detail GLB, loaded only
when the user clicks that joint's annotation hotspot. That single detail sells
more engineering credibility than any amount of shell polish.

### E.3 Connection style — monolithic, not bolted

**No bolt grades, weld sizes, gusset plates or base plates exist in this
structure.** The RC equivalents:

| Junction | Mechanism | Key detail |
|---|---|---|
| Column → foundation | Starter bars cast into pad, lapped 40 Ø with column bars | construction joint at FFL, roughened and cleaned |
| Column → beam → slab | **Monolithic joint core**: beam top steel continuous through, bottom steel anchored into the core, column links continued through the joint depth | full moment transfer — the frame's stability mechanism |
| Column storey lift | Bars lapped through the slab; construction joint just above slab | kicker (75–100 mm) cast with the slab |
| Beam → slab | Cast in one pour; slab acts as compression flange (T-beam action) | effective flange width per code |
| Slab → slab (pour break) | Day-joint at ¼ span with continuous reinforcement | never at midspan |

**Where bolts genuinely exist:** the yellow guard-rail (M12 into cast-in sockets
or screw-on base plates), duct flanges (M8 at Mez flange corners), pipe grooved
couplings, and hanger drop rods (M10/M12 into anchors).

### E.4 Pipe and duct sizing — the MEP answer

| Service | Size | Wall / gauge | Joint | Support centres |
|---|---|---|---|---|
| HVAC supply main | 600 × 400 mm rect. | 0.8 mm galv. sheet | Mez/TDC flange @ 1.2–3.0 m | 2.4 m |
| HVAC branch | 400 × 250 / 300 × 200 mm | 0.6 mm | slip / flange | 2.4 m |
| Heating flow & return | DN80 (88.9 mm OD) | 3.2 mm CS | welded / grooved | 3.0 m |
| Chilled water branch | DN50 (60.3 mm OD) | 2.9 mm | threaded / grooved | 2.5 m |
| Domestic cold | DN25 copper (28 mm OD) | 1.2 mm | press / solder | 1.8 m |
| Sprinkler main | DN100 (114.3 mm OD) | 3.6 mm | grooved | 3.5 m |
| Roof flue | Ø600 mm | twin-wall insulated | flanged | per manufacturer |

Sheet-metal gauge by duct's largest dimension (DW/144, the standard everyone
actually uses): ≤ 450 mm → 0.6 mm; 451–1 000 mm → 0.8 mm; 1 001–1 250 mm →
1.0 mm; > 1 250 mm → 1.2 mm.

**Coordination reality worth showing in the demo:** services must pass *under*
600 mm-deep beams within a ~500 mm ceiling void, or through cast-in sleeves in
the beam web — permitted only in the middle third of the span, ≤ 0.25 × beam
depth, never near supports. That clash — beam depth vs. duct depth vs. ceiling
height — is *the* everyday BIM problem, and it is precisely what the right-hand
panel of the reference is advertising. A clash-highlight interaction on that
junction is the most persuasive single feature this demo can carry.

### E.5 Loads assumed (for annotation credibility)

| Load | Value |
|---|---|
| Slab self-weight (200 mm) | 5.0 kN/m² |
| Superimposed dead (finishes, services, ceiling) | 1.5 kN/m² |
| Partitions allowance | 1.0 kN/m² |
| Imposed — office | 2.5 kN/m² |
| Imposed — roof (maintenance) | 1.5 kN/m² |
| **ULS design** 1.35 G + 1.5 Q | ≈ **13.0 kN/m²** |
| Ground column axial (interior, 43 m² tributary × 4 storeys) | ≈ **2 240 kN** |
| Capacity check: 0.4 × 30 × 500² / 1000 | = 3 000 kN > 2 240 kN ✓ |

The 500 × 500 ground column is confirmed adequate by that check — which is why
that section, rather than a guessed one, is specified in §E.1.

---

## F. What this feeds (bridge to the production plan)

| This document | Downstream artefact |
|---|---|
| §A.3 assembly sequence | storey-by-storey build-up animation timeline |
| §B component table | material assignment map, annotation hotspot list |
| §C coordinate system | Blender scene setup + Three.js camera / clipping-plane maths |
| §D.1 grid table | Blender Python generator + shared JSON for the viewer |
| §D.3 naming schema | layer toggles and pick-to-inspect, parsed from GLB node names |
| §D.7 performance scope | GLB split: `structure.glb` (eager) + `mep.glb` (lazy) |
| §E.2 rebar | single high-detail `joint_B2_L01.glb`, loaded on demand |
| §E.4 clash geometry | the demo's headline interaction |
