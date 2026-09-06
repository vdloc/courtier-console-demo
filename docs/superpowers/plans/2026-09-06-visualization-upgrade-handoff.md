# Visualization upgrade — handoff

**Date:** 2026-09-06
**Branch:** `feat/structural-digital-twin`
**Stopped because:** usage limit, mid-cycle. Nothing is half-applied; the tree is
clean and every commit below renders.

Six briefs were queued and interrupted before any work started on them. They are
written out in full in *Undone work* so the next session does not have to
reconstruct them.

---

## Where things stand

### Committed this session

| Commit | What |
|---|---|
| `80cc87d` | Lighting rebalance: sun/sky ratio, camera-ray sky split, Nishita aerosol, concrete albedo, steel roughness, procedural ground |
| `844a012` | Paint mottle made visible on dark primer; roughness-variation band widened |
| `3ff3310` | `build_site_context()` — hoarding, compound, laydown, barriers, skip, spoil, and 24 surround massing blocks |

`77c7802` ("docs: unwrap proposal prose") was **not** made by this session —
something auto-committed a reflow of the Vietnamese proposal doc mid-run. The
diff is pure line-unwrapping, 262 insertions against 704 deletions of the same
prose. No content lost. Mentioned only so nobody hunts for it.

### The three findings that cost the most to establish

Re-deriving these is expensive. They are load-bearing for everything below.

1. **Blender's sky texture is not on a physical scale.** At strength 1.0 the
   Nishita sky delivers roughly as much ambient as a 30 W/m² sun. The original
   2.4 W/m² sun was an order of magnitude under the sky, so the scene had *no
   shadows at all* — it was lit by near-uniform ambient. Proved with a
   three-point probe (2.4 / 200 / 800), not reasoned about.

2. **One sky strength cannot serve both lighting and background.** Bright enough
   to photograph as a sky and its ambient erases every shadow; dim enough for
   shadows and the background renders near-black. `setup_world()` now mixes two
   Background nodes off one Sky texture on `Is Camera Ray` — `sky_light` (0.30)
   lights the frame, `sky_view` (1.60) is what the camera sees.

3. **On a low-albedo surface, variation in reflectance sells unevenness and
   variation in colour does not.** `_shift` is multiplicative, so
   `paint_variation` is a *fraction* of base colour: 0.075 on a 0.055 primer was
   four parts in a thousand and invisible. The same mottle routed to roughness
   is plainly visible. This drove both the steel fix and the ground material,
   and it should drive the concrete work in Brief 1.

### Measured state of the scene (fresh headless build of `HEAD`)

```
3,147 objects · 1,074,958 evaluated tris · 242,894 before modifiers
Connections  2,652 obj   939,568 tris  (87%)
  └─ Bolts   1,312 obj   860,672 tris  (80% of the whole scene, mean 656)
Beams          128 obj    58,576 tris
Columns         80 obj    38,400 tris
Accessories    248 obj    26,784 tris
Pipes            9 obj     9,468 tris  (mean 1,052 — worst per object)
Foundation      20 obj     2,160 tris
```

- Bevel: 4 mm, 2 segments, 30° angle limit. **Correct — do not "improve" this.**
- **UV layers: 1 mesh in the entire scene has one. Every other has zero.**
- All materials sample noise in **object space**, so a 12 m column and a 42 mm
  bolt get the same noise scale in their own local coordinates.
- Camera: 50 mm, sensor 36, `shift_y` 0.07 (shift not tilt — correct practice),
  DOF on at f/8 focused 71.99 m.

### Environment / tooling gotchas

- **No GPU.** Cycles is CPU-only. 1280×720 at 32 samples denoised is ~9 s for
  the full scene, so the render-evaluate loop is cheap — use it freely.
- **The Blender MCP bridge needs a GUI Blender behind it.** The MCP server
  process can be up while no Blender is running; `get_scene_info` then fails
  with "Could not connect". Start one with
  `DISPLAY=:0 blender renders/structure.blend` — the addon auto-starts its
  server. **A GUI Blender was left running on `:0`; close it.**
- The GUI instance holds a `.blend` snapshot, not live source. It goes stale the
  moment `generate_structure.py` changes. Audit from a fresh headless build.
- `blender -b` cannot host the MCP addon; it prints
  "cannot start server in background mode" and continues fine.
- Render harness: `/tmp/claude-1000/.../scratchpad/viz/render_pass.py`, invoked
  `blender -b -P render_pass.py -- <tag> <shot...>`. It purges `sys.modules` so
  each run picks up edited source. **Scratchpad is not durable — copy it into
  the repo (`blender/tools/`) if the next session wants it.**
- `renders/` is gitignored. `pass0_hero.png` is the original baseline;
  `c1d_hero.png` is the current state.

---

## Undone work

Six briefs, verbatim intent, in the order given. **None was started.**

### Brief 1 — Materials, without changing structural design

> Current problem: the model looks too clean and synthetic.

**Steel** — add realistic industrial paint, metallic response, roughness
variation, subtle scratches, manufacturing imperfections, edge wear, dust
accumulation. Avoid perfect grey, mirror-like metal, uniform roughness.

**Concrete** — add surface pores, slight colour variation, dust, stains,
roughness variation.

**Connections** — improve bolts, plates, weld areas, mechanical details.

Then render **(1)** a full scene and **(2)** a close-up material inspection, and
compare against real industrial photography.

Notes for whoever picks this up:

- Partially done already. `MAT_Steel_Painted` is at 0.52 roughness with a 0.13
  variation band and a visible mottle; `MAT_Concrete` is at 0.300 albedo. The
  shader in `build_painted_metal` already has scratch, chip, edge-wear
  (pointiness) and bump layers wired — the brief's list is largely *present but
  under-amplitude*, not missing. Audit each layer's contribution before adding
  anything new.
- **Still wrong, measured:** `MAT_Steel_Galvanised` at 0.610 albedo / 0.34
  roughness (real hot-dip is 0.35–0.45 and spangled — it is the brightest thing
  in the model); `MAT_Steel_Bolt` at 0.30 roughness across 1,312 objects (they
  will sparkle as a field); `MAT_Pipe_CHW` / `MAT_Pipe_LTHW` at 0.36. Only
  painted steel was corrected. **These four numbers are the cheapest remaining
  material win and they reach the GLB** through
  `optimize_export.flatten_materials_for_web`.
- Dust accumulation should be driven by world normal (up-facing surfaces), as
  `build_concrete` already does — not by a uniform overlay.
- Use the `detail` shot (85 mm, ~5 m from a beam-to-column joint) for the
  close-up. It is the only camera that resolves any of this; the hero at 72 m
  cannot show a roughness change either way. **Verify every material change on
  `detail` or `corner`, never on `hero`.**
- `js/pbr-materials.js:17` hand-transcribes the `MATERIALS` table for the legacy
  vanilla demo. Keep it in sync.

### Brief 2 — Geometry, only where it increases realism

> Do not unnecessarily increase polygon count.

High value: beam connections, joints, brackets, bolts, pipe connections. Add
realistic bevels, weighted normals, manufacturing details, welding details.
Maintain GLB export compatibility and Three.js performance. Use detail where the
camera can see it.

Notes:

- **The polygon problem here is subtraction, not addition.** Bolts are 80% of
  the scene at mean 656 tris, and an M24 head is sub-pixel from the hero camera.
  The brief's "use detail where the camera can see it" is exactly right and
  points at an LOD split: full bolts only in the `detail` shot's neighbourhood,
  a ~24-tri proxy everywhere else. `optimize_export.simplify_small_parts`
  (`:165`) already decimates small parts — extend that rather than build a
  second system.
- Bevel (4 mm / 2 seg) and the weighted-normal pass are already applied in
  `add_quality_modifiers` (`generate_structure.py:404`) and are correct. The 586
  meshes without a bevel are the 12-tri weld fillets, where it does not matter.
- Pipes at 1,052 tris each for three straight runs with two bends is the other
  easy cut (`pipe_bevel_resolution`, `CONFIG`).

### Brief 3 — Believable environment

Ground: concrete, industrial floor, subtle dirt, contact shadows.
Environment, pick one: **A** construction site · **B** steel fabrication
workshop · **C** industrial yard.
Add atmospheric depth, realistic scale references, environmental reflections.
The structure must feel physically located.

Notes:

- **Largely delivered by `3ff3310`** — option A, construction site. Hoarding,
  compound, laydown, barriers, skip, spoil heaps, plus `SiteSurrounds` massing
  for atmospheric depth. Scale references are the ISO containers, 2.0 m
  hoarding and 3.0 m barrier units.
- Ground is procedural (two-octave noise into colour *and* roughness).
- **Outstanding from the last render (`c1d_hero.png`):** surround blocks read as
  untextured slabs and the nearest crowds the frame — push the radius out
  (140–260 m), vary their material value across two or three variants, and break
  their rooflines. The compound crops at the right frame edge. The apron between
  the frame and the hoarding is still empty.
- Environmental reflections in the *web* build come from
  `<Environment preset="warehouse">` in `Viewer.tsx:83` and are already present.

### Brief 4 — Camera system, as an architectural photographer

Fix robotic movement, unnatural acceleration, poor framing, wrong focal length.
Style: drone inspection, architectural documentary. Use smooth spline paths,
slow acceleration/deceleration, natural pauses. Create hero, engineering
inspection, detail, and final reveal shots. Every movement must communicate
engineering quality.

Notes:

- **The motion half is already built** — `app/src/scene/CameraManager.ts` was
  rewritten earlier this session: polar-space CatmullRom paths, arc-length
  sampling, quaternion slerp against a smoothed target, momentum, breathing,
  and a four-leg 8/10/8/10 s sequence. Do not rebuild it.
- **It has never been evaluated for feel.** SwiftShader runs the viewer at 1–2
  fps on this machine, so only geometry and state were verified. Judge it on a
  real GPU first, then tune the constants at the top of the class.
- **The framing half is genuinely open.** Every render is centred with dead
  ground around it — no thirds, no lead room, no foreground occluder. Focal
  lengths themselves are fine (50/35/85/200). The `corner` shot looks *upward*
  (camera z=4.2, target z=5.5), which is the same geometry that made it
  unreachable under the web viewer's polar clamp.
- `scene_setup.SCENE["shots"]` and `CameraManager.ts:79` mirror each other.
  **Change both or they drift.**

### Brief 5 — Prepare for Three.js

Check polygon count, draw calls, unnecessary objects; texture sizes, material
count. Export `structure_final.glb`. Preserve object names, hierarchy,
animations, metadata. Must work in Three.js, R3F, WebGL.

Notes:

- **Do Brief 2's bolt LOD first** — exporting before that ships 860k triangles
  of sub-pixel fasteners.
- Current pipeline output is 1.0 MB after gltf-transform, 7 materials, hierarchy
  and `extras` metadata intact. Verified working this session.
- **Unresolved:** the committed `dist/structure_demo.glb` is 2,896,836 bytes;
  a clean pipeline run produces 1,049,016. A 64% drop from re-running the same
  scripts. Either the committed artifact was built from different code or the
  current pipeline drops something — animation is the obvious suspect
  (`optimize_export.run` defaults `animation=True`, but that was not verified).
  **Resolve this before publishing `structure_final.glb`.**
  `app/public/structure_demo.glb` is untouched, so the browser build is
  currently unaffected either way.
- Texture sizes are moot until Brief 1 produces textures — and it cannot, see
  below.

### Brief 6 — Final professional review

Score geometry, materials, lighting, camera, environment, engineering realism,
web performance out of 10. For every score below 9, identify the reason, apply
the improvement, render again, repeat until no major realism issues remain.

Do this last. It is a review of Briefs 1–5.

---

## The blocker nothing else routes around

**The scene has no UVs.** One mesh has a UV layer; every other has zero.

This makes the entire bake pipeline in `materials.py` — `bake_material` (`:746`),
`bake_object_ao` (`:791`), `write_manifest` (`:867`), `bake_all` (`:878`) —
non-functional as written. `bake_material` needs a UV target and `bake_object_ao`
explicitly wants a dedicated layer. Nothing in the React app reads
`textures/materials.json` either.

Consequences to plan around:

- **The GLB will carry flat PBR factors no matter how good Cycles looks.** Every
  material improvement from Brief 1 reaches the browser only as a colour,
  metalness and roughness number.
- Brief 1's "dust, stains, pores" are achievable in Cycles today via procedural
  nodes, and **not** achievable in the browser without this fixed.
- Fix is smart-UV-project per member class at generation time, into a *second*
  UV layer so the first stays free. Medium difficulty. It makes textures real,
  which then puts KTX2 compression on the critical path for Brief 5.

Decide explicitly whether the target is a premium *Blender render* or a premium
*web viewer*. They diverge here, and the briefs assume both.

---

## Suggested order

1. **Brief 1's four material numbers** (galvanised, bolt, both pipes) — lowest
   cost, reaches the GLB, fixes the brightest wrong thing in the model.
2. **Brief 3's outstanding items** — surround massing and apron. Cheap, and it
   is the largest remaining perceived-quality gap.
3. **Brief 2's bolt LOD** — unlocks Brief 5.
4. **The UV decision** — everything texture-related waits on it.
5. **Brief 4's framing** (motion needs a GPU), then **Brief 5**, then **Brief 6**.

## Open questions for the user

- **IPE600 at a 7.2 m steel span.** `docs/interpretation/…:180` specifies
  600 mm depth as ≈span/12 explicitly for **RC, C30/37**, and `rc_beam_primary`
  matches it exactly — the concrete path is right. But `profile_mode` is
  `"STEEL"`, and `beam_primary` inherited that depth. Steel floor beams at
  7.2 m are span/18–22, so IPE400 (`beam_edge`, already in CONFIG) is what this
  span asks for. Deliberate demo choice, or a section table never revisited
  after the material changed?
- **Render quality or web quality?** See the UV blocker.
- **Should `dist/structure_demo.glb` be regenerated** (see Brief 5)?
