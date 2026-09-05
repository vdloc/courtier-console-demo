# Courtier Console Demo

A portfolio/skill-showcase demo: an admin-console-style configuration form
whose numeric inputs drive a live parametric diagram, rendered in both 2D
(SVG) and 3D (Three.js), with a modal to enlarge the diagram. It replicates
the interaction pattern of a "console courtier" screenshot — a French-labelled
form (`Cadre`, `Poteau`, `Plaque d'appui`, ...) for describing the dimensions
of a support structure and pipe run.

It demonstrates:

- Driving two independent renderers (an SVG 2D elevation view and a
  Three.js 3D scene) off one shared data model, so they can never disagree.
- A minimal pub-sub state store with no framework.
- Re-parenting a single live WebGL canvas + CSS2D label overlay between a
  thumbnail panel and a modal, instead of creating a second renderer.
- Camera bounding-box fitting, WebGL resource disposal on rebuild, and a
  2D viewBox derived from actual content rather than a fixed constant.

This is a static, no-build, no-backend site: plain HTML/CSS/JS (ES modules),
Three.js r169 loaded via a pinned `importmap`. No npm, no bundler, no
`package.json`.

## Run it

A plain `file://` open of `index.html` will **not** work: this project uses
native ES modules (`<script type="module">`) and a pinned `importmap` for
Three.js, and browsers apply CORS restrictions to module imports served
from the `file:` scheme — the modules will fail to load silently or with a
CORS error in the console. Serve the directory over HTTP instead:

```
python3 -m http.server 8000
```

Then open http://localhost:8000/ in a browser.

## Run the tests

```
node --test tests/*.mjs
```

Note the glob: on this machine (Node v22.16.0), the form `node --test tests/`
suggested by some Node docs fails with a module-resolution error. The glob
form above is the one that actually runs and has been verified to pass all
tests.

Only `js/state.js` and `js/dimensions.js` are covered by these automated
tests — they have no DOM or WebGL dependency, so they're testable directly
with Node's built-in `node:test` + `node:assert/strict`, no test framework
or browser needed. Everything else (`js/diagram2d.js`, `js/diagram3d.js`,
`js/app.js`, `js/modal.js`) is DOM/WebGL-dependent and is verified manually
in-browser — see `docs/superpowers/specs/2026-09-05-courtier-console-design.md`
§10 for the manual verification checklist.

## Architecture

- **`js/state.js`** — a flat `params` object (all values in meters) plus a
  tiny pub-sub store: `getParams()`, `setParam(key, value)`, `subscribe(fn)`.
  Every `setParam` call notifies all subscribers synchronously with the full
  params object.

- **`js/dimensions.js`** — the single source of truth that keeps the 2D and
  3D views from drifting apart. It exports `dimensionRecords`, one array of
  records (not duplicated per view) where each record describes one
  annotated dimension as a pair of 3D anchor functions (`from(params)`,
  `to(params)`), an offset direction for the witness line, and a label
  function. `js/diagram3d.js` builds dashed 3D witness lines + CSS2D labels
  directly from these anchors; `js/diagram2d.js` projects the *same*
  anchors onto a 2D elevation plane to draw SVG lines + text. Because both
  renderers read the same records, they cannot disagree numerically. This
  file also exports `visualScale(key, value)`, which clamps thin members
  (insulation/pipe thickness, offsets) to a visible floor for rendering
  only — the label text always shows the true value.

- **`js/diagram3d.js`** — the Three.js scene (box + pipe + dimension lines
  and labels), rebuilt wholesale from `dimensionRecords` on every param
  change (cheap at this scale, no incremental diffing). It disposes the
  previous frame's geometries/materials and detaches stale CSS2D label DOM
  nodes before each rebuild, and fits the camera to a bounding box of the
  current geometry (preserving the user's current orbit direction) rather
  than resetting to a fixed camera position.

- **`js/diagram2d.js`** — an SVG view of the same dimension records,
  projected onto a 2D plane. The `viewBox` is derived from the actual
  projected extent of the current geometry (not a fixed constant), so it
  never clips regardless of param values.

- **`js/app.js`** — the entry point. Wires form inputs to `setParam`, mounts
  both diagram views into the thumbnail panel, and re-renders both plus the
  right-rail result rows on every state change. View mode (`'2d'` vs
  `'3d'`) is a closure-local variable here, exposed via
  `window.__courtierApp.getViewMode()` / `setViewMode(mode)` so that
  `js/modal.js` and the thumbnail's own toggle buttons drive the exact same
  state through the same setter — the two toggles cannot disagree.

- **`js/modal.js`** — "enlarge diagram" behavior. Only one WebGL context
  exists at any time: opening the modal re-parents the live canvas, its
  CSS2D overlay, and the SVG element into the modal's container and calls
  `resize()`; closing moves them back to the thumbnail panel. Nothing is
  duplicated or recreated.

See `docs/superpowers/specs/2026-09-05-courtier-console-design.md` for the
full design spec and `docs/superpowers/plans/2026-09-05-courtier-console-demo.md`
for the implementation plan this was built from.

## What this is not

- **No backend, no persistence.** All state lives in memory; reloading the
  page resets every field to its default. There's no server, no database,
  no auth.
- **No real engineering calculations.** The dimensions and the "OK"
  validation chips are cosmetic. Nothing here is validated against any
  structural, thermal, or plumbing code or standard — see spec §2
  (Non-goals). Do not use this to size or validate a real installation.
- **No build step, no framework.** Plain ES modules and a pinned Three.js
  importmap; there is deliberately no bundler, no TypeScript, and no
  `package.json`.
- **No routing.** The sidebar's other nav items are decorative; only the
  one active screen exists.
- **Not mobile-responsive.** This mirrors a desktop-only console UI
  screenshot and hasn't been adapted for small viewports.
