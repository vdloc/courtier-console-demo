# Courtier Console Demo — Design Spec

Date: 2026-09-05
Status: Approved by user (chat), pending spec review gate

## 1. Purpose

Portfolio/skill-showcase demo replicating the interaction pattern of the
"Console Courtier" screenshot: an admin-console shell around a config form
whose numeric inputs drive a live parametric diagram (2D and 3D), with a
modal to enlarge that diagram. Not a real product — no backend, no auth,
no persistence beyond in-memory state.

## 2. Non-goals

- No build tooling (no bundler, no npm install, no TypeScript compiler).
- No real engineering/insulation calculations — dimensions are cosmetic,
  not validated against any code/standard.
- No multi-page routing. Sidebar nav items other than the one active
  screen are decorative (clickable but inert, or simply visual).
- No persistence (values reset to defaults on reload) — acceptable for a demo.

## 3. Stack

Plain static site: `index.html`, `css/*.css`, `js/*.js` (ES modules,
`type="module"`, no bundler). Three.js loaded via a pinned `importmap`
from jsdelivr/cdnjs (ESM build, so `OrbitControls` and `CSS2DRenderer`
addons are available). No `package.json`, no dev server requirement
(any static file server works; `file://` may fail due to ES module CORS
rules on some browsers, so document `python3 -m http.server` as the run
command).

## 4. Directory Structure

```
courtier-console-demo/
  index.html
  css/
    style.css          # console chrome: topbar, sidebar, form, right rail, modal
  js/
    app.js              # entry point: wires form inputs <-> shared state <-> both diagram views
    state.js            # single params object + simple pub-sub (subscribe/notify)
    dimensions.js        # the dimension-record table (see §6) — shared by 2D and 3D renderers
    diagram3d.js         # Three.js scene: box geometry, pipe path, dashed witness lines, CSS2D labels
    diagram2d.js          # SVG-based 2D elevation view, built from the same dimension records
    modal.js             # enlarge/collapse: moves the live 3D canvas + overlay into modal container
  docs/superpowers/specs/2026-09-05-courtier-console-design.md
```

## 5. Layout (mirrors screenshot)

- **Top bar**: product name/logo placeholder, decorative icons, user menu.
- **Left sidebar**: static list of module names (icons + labels), one
  marked active — no routing.
- **Main column**: form grouped into labelled sections ("Cadre",
  "Poteau", "Plaque d'appui", etc. — cosmetic French labels matching the
  domain), each a small grid of number inputs with unit suffixes (m).
- **Right rail**: green "OK" validation chips per section, a diagram
  thumbnail panel with a 2D/3D toggle and an "Agrandir" (expand) button,
  a yellow warning callout (static demo text), and a few static result
  rows below.
- **Modal**: "Agrandir le diagramme" — same 2D/3D toggle, larger canvas.
  Opening it moves the live Three.js canvas + label-overlay DOM node
  into the modal's container and resizes; closing moves them back to
  the thumbnail panel. Only one WebGL context exists at any time.

## 6. Data Model

### 6.1 Params (single source of truth, in `state.js`)

A flat object, all values in meters unless noted:

```js
{
  A: 0.3, B: 0.3,           // block plan dimensions
  H1: 0.4, H2: 0.35,        // block heights (two sections)
  Hv: 0.4,                  // vertical run height
  Ec: 0.15,                 // Ac in screenshot — cap thickness
  Ep: 0.03,                 // insulation/wall thickness
  Fee: 0.1,                 // stub length
  PhiM: 0.1,                // pipe/duct diameter
  Uh: 0.04, Ub: 0.04,       // top/bottom offsets
  HsD: 0                    // secondary height offset
}
```

`state.js` exposes `getParams()`, `setParam(key, value)`, and
`subscribe(fn)`. Every `setParam` call notifies all subscribers
synchronously with the full params object — both diagram renderers and
the right-rail result rows subscribe.

### 6.2 Dimension records (`dimensions.js`)

This is the core reusable artifact both renderers consume — one array,
not duplicated per view:

```js
// each record describes ONE annotated dimension
{
  id: 'H1',
  from: (p) => new Vector3(...),   // 3D anchor start, fn of current params
  to:   (p) => new Vector3(...),   // 3D anchor end
  offsetDir: new Vector3(...),      // which way the witness line jogs out
  label: (p) => `H1 = ${p.H1.toFixed(2)}`
}
```

- **3D renderer** (`diagram3d.js`): for each record, builds a dashed
  `LineSegments` witness/extension line from `from`->`to` (offset by
  `offsetDir`), and a `CSS2DObject` label positioned at the line's
  midpoint, containing `label(params)` text. Re-run this per-record
  build whenever params change (geometry + lines are cheap to rebuild
  wholesale for a demo of this size — no need for incremental diffing).
- **2D renderer** (`diagram2d.js`): projects the same `from`/`to`
  anchors onto a fixed elevation plane (drop one axis) to draw SVG
  `<line>` + `<text>` — reusing the identical record list keeps the two
  views from drifting apart.

### 6.3 Scale handling

Real values span roughly 0.03-0.4 m; rendering literal values makes
insulation/pipe thickness (Ep, Uh, Ub, PhiM) invisible next to block
dimensions (A, B, H1, H2). Rule: a `visualScale(key, value)` helper in
`dimensions.js` clamps thin members to a visible floor for **rendering
only** (e.g. `Math.max(value, 0.06)` after a global scene scale) — the
label text always shows the true `value`, never the clamped one.

## 7. Rendering Pipeline

1. User edits a number input -> `input` event -> `setParam(key, parsedValue)`.
2. `state.js` notifies subscribers.
3. `diagram3d.js` subscriber: rebuilds box mesh + pipe path + dimension
   lines/labels from current params; renderer re-draws on next
   `requestAnimationFrame` (loop runs continuously for `OrbitControls`
   damping; geometry rebuild is only triggered on change, not every frame).
4. `diagram2d.js` subscriber: re-renders the SVG (clear + redraw, no
   virtual-dom diffing needed at this scale).
5. Right-rail result rows subscribe directly and re-render text.

## 8. Modal Behavior

- Modal starts closed; thumbnail panel holds the live canvas + overlay div.
- "Agrandir" click: `modal.js` re-parents the canvas + overlay DOM node
  into the modal's diagram container, calls `renderer.setSize(...)` and
  updates camera aspect, shows the modal.
- View mode (2D vs 3D) is a closure-local `viewMode` variable in
  `js/app.js` (not a field on the `state.js` params object — it isn't a
  diagram parameter, it's UI state, so pub-sub notification would be
  overkill). `app.js` exposes it via `window.__courtierApp.getViewMode()`
  / `setViewMode(mode)`; `js/modal.js` calls `getApp().setViewMode(...)`
  on its own toggle buttons rather than keeping a second copy of the
  mode. Both the thumbnail's toggle and the modal's toggle end up
  driving the exact same variable through the same setter, which is the
  property this section actually cares about: the two toggles cannot
  disagree, because there is only ever one source of truth for which
  view is showing.
- Close (`x` or backdrop click): re-parent canvas + overlay back to the
  thumbnail container, resize back down.

## 9. Input Validation / Error Handling

- Each number input has `min="0"` and a reasonable `max` per field to
  prevent nonsensical geometry (e.g. negative thickness).
- On invalid/empty input, `setParam` is not called — the input reverts
  visually to the last valid value on blur (demo-grade, not
  production-grade validation).
- No network calls, so no async error states to handle.

## 10. Testing / Verification Plan

`state.js` and `dimensions.js` have no DOM/WebGL dependency and are
covered by automated tests under `tests/` (`node:test` +
`node:assert/strict`; run with `node --test tests/*.mjs` — see the
README). Everything DOM/WebGL-dependent (`diagram2d.js`, `diagram3d.js`,
`app.js`, `modal.js`) is verified manually in-browser:

1. Serve via `python3 -m http.server` in the project root, open in
   browser (a plain `file://` open fails — the ES module imports and the
   pinned Three.js importmap are subject to browser CORS restrictions
   on the `file:` scheme). Confirm the console is free of errors and
   404s (including the favicon, which is an inline `data:` URI in
   `index.html` specifically so it doesn't 404).
2. Verify `THREE.REVISION` logs, `OrbitControls` and `CSS2DRenderer`
   both instantiate without console errors (first implementation step,
   before writing scene code — addon import paths shift across
   pinned Three.js versions).
3. Change each numeric input one at a time; confirm both the 3D scene
   and (after toggling) the 2D SVG update their geometry and labels
   immediately, and that the two views agree numerically. The 2D
   view's SVG `viewBox` is derived from the actual projected extent of
   the current `dimensionRecords` (see `diagram2d.js`), not a fixed
   constant, so also confirm that extreme param values (very small or
   very large) don't clip witness lines or labels. In 3D, confirm the
   camera keeps the whole model (including the offset dimension labels)
   framed after a param change — `diagram3d.js` recomputes a bounding
   box of the rebuilt geometry each time and re-fits the camera distance
   to it (preserving the current orbit direction) rather than resetting
   to a fixed camera position.
4. Open the enlarge modal from both 2D and 3D mode; confirm the same
   live view (not a stale duplicate) appears enlarged, orbit controls
   still work, closing returns it correctly to the thumbnail. Only one
   WebGL context exists throughout — `modal.js` re-parents the existing
   canvas/overlay/svg DOM nodes between the thumbnail and modal
   containers rather than creating a second renderer, and `diagram3d.js`
   disposes the previous frame's geometries/materials on every rebuild
   (`disposeGroup`) so switching params or view modes repeatedly does
   not leak GPU resources or stray CSS2D label DOM nodes.
5. Resize the browser window with the modal open and closed; confirm
   canvas/labels stay aligned (no drift between SVG lines and DOM
   labels vs the WebGL canvas). `diagram3d.js`'s `resize()` reads the
   canvas's *current* parent element (not a captured reference to the
   original thumbnail container), so this must hold both immediately
   after opening/closing the modal and after a plain window resize
   while the modal is open.

## 11. Out of Scope / Future Ideas (not building now)

- Persisting param state (localStorage) across reloads.
- Real structural/thermal calculations behind the result rows.
- Mobile-responsive layout (screenshot itself is desktop-only console UI).
