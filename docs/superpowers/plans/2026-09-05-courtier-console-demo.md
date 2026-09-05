# Courtier Console Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a static, no-build-step web demo that mirrors the "Console Courtier" screenshot: an admin-console shell with a config form whose numeric inputs drive a live parametric diagram, in both 2D (SVG) and 3D (Three.js), enlargeable via a modal.

**Architecture:** A single shared `params` object (`js/state.js`) with pub-sub notifies two independent renderers — `js/diagram2d.js` (SVG) and `js/diagram3d.js` (Three.js scene + CSS2D labels) — both driven by one shared dimension-record table (`js/dimensions.js`) so the two views can never numerically drift apart. `js/modal.js` re-parents the single live 3D canvas + label-overlay DOM node into the modal container on open and back on close, so there is only ever one WebGL context. `js/app.js` wires form `<input>` elements to `state.js` and mounts everything.

**Tech Stack:** Plain HTML/CSS/JS (ES modules, `type="module"`, no bundler). Three.js r169 (`three@0.169.0`) loaded via a pinned `<script type="importmap">` from jsdelivr, including the `OrbitControls` and `CSS2DRenderer` addons. Pure-logic modules (`state.js`, `dimensions.js`) have no DOM or Three.js dependency and are unit-tested directly with Node's built-in `assert` module (no test framework, no `npm install`) — this is possible only because those two files never import `THREE`; dimension records return plain `{x, y, z}` objects, and `diagram3d.js` alone is responsible for wrapping them into `THREE.Vector3` when building geometry. DOM/Three.js-dependent modules are verified manually in-browser per the spec's §10 checklist.

**Spec:** `/home/vdloc/Projects/courtier-console-demo/docs/superpowers/specs/2026-09-05-courtier-console-design.md`

## Global Constraints

- No bundler, no `npm install`, no TypeScript compiler, no `package.json` (spec §3).
- No backend, no auth, no persistence across reloads (spec §1, §2).
- No routing — sidebar items other than the active screen are decorative (spec §2).
- Run command for manual verification: `python3 -m http.server` from the project root, then open `http://localhost:8000/` (spec §3, §10).
- Three.js pinned to `three@0.169.0` on jsdelivr (`https://cdn.jsdelivr.net/npm/three@0.169.0/...`), confirmed reachable: `build/three.module.min.js`, `examples/jsm/controls/OrbitControls.js`, `examples/jsm/renderers/CSS2DRenderer.js` all return HTTP 200.
- Dimension records are the single shared source between the 2D and 3D renderers (spec §6.2) — never duplicate dimension math in `diagram2d.js` or `diagram3d.js`.
- Real values span ~0.03-0.4 m; thin members (`Ep`, `Uh`, `Ub`, `PhiM`) must be visually clamped for rendering only, never in the displayed label text (spec §6.3).
- Git commits: end messages with the standard attribution trailer used elsewhere in this session (`Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` + `Claude-Session:` line) — copy the exact trailer from the most recent commit in this repo (`git log -1`) rather than retyping it.

---

### Task 1: Project scaffold + Three.js importmap smoke test

**Files:**
- Create: `index.html`
- Create: `css/style.css` (empty placeholder with a single comment for now — populated in Task 6)
- Create: `js/app.js` (temporary smoke-test body — replaced in Task 7)

**Interfaces:**
- Consumes: nothing (first task).
- Produces: a working `<script type="importmap">` + `type="module"` entry point that every later browser-side task loads from. Later tasks assume `index.html` already has the importmap block shown below and a `<script type="module" src="js/app.js">` tag.

- [ ] **Step 1: Create `index.html` with the importmap and a temporary smoke-test module**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Courtier Console Demo</title>
  <link rel="stylesheet" href="css/style.css">
  <script type="importmap">
  {
    "imports": {
      "three": "https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.min.js",
      "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/"
    }
  }
  </script>
</head>
<body>
  <div id="app">Loading&hellip;</div>
  <script type="module" src="js/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create `css/style.css` placeholder**

```css
/* Populated in Task 6 (console chrome layout) */
```

- [ ] **Step 3: Create `js/app.js` with a temporary smoke test**

```js
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DRenderer } from 'three/addons/renderers/CSS2DRenderer.js';

console.log('THREE.REVISION:', THREE.REVISION);
console.log('OrbitControls loaded:', typeof OrbitControls === 'function');
console.log('CSS2DRenderer loaded:', typeof CSS2DRenderer === 'function');

document.getElementById('app').textContent =
  `Three.js r${THREE.REVISION} — OrbitControls and CSS2DRenderer both loaded OK.`;
```

- [ ] **Step 4: Serve and verify in browser**

Run: `python3 -m http.server` from `/home/vdloc/Projects/courtier-console-demo`, open `http://localhost:8000/`.

Expected: page shows `Three.js r169 — OrbitControls and CSS2DRenderer both loaded OK.` with no red errors in the browser console. If the importmap paths 404 or the addons fail to resolve, stop and fix the version/paths before continuing to any later task — every subsequent task depends on this loading correctly.

- [ ] **Step 5: Commit**

```bash
git add index.html css/style.css js/app.js
git commit -m "feat: scaffold project with Three.js importmap smoke test"
```

---

### Task 2: `state.js` — shared params store with pub-sub

**Files:**
- Create: `js/state.js`
- Test: `tests/state.test.mjs`

**Interfaces:**
- Consumes: nothing.
- Produces: `getParams()` returning the current params object; `setParam(key, value)` which mutates and notifies; `subscribe(fn)` which registers `fn(params)` to be called on every `setParam`, and returns an `unsubscribe()` function. Default params object (spec §6.1):
  `{ A: 0.3, B: 0.3, H1: 0.4, H2: 0.35, Hv: 0.4, Ec: 0.15, Ep: 0.03, Fee: 0.1, PhiM: 0.1, Uh: 0.04, Ub: 0.04, HsD: 0 }`.
  Later tasks (`dimensions.js` consumers, `app.js`, right-rail rendering) rely on exactly these three exported function names and this exact key set.

- [ ] **Step 1: Write the failing test**

```js
// tests/state.test.mjs
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { getParams, setParam, subscribe } from '../js/state.js';

test('getParams returns the documented defaults', () => {
  const p = getParams();
  assert.equal(p.A, 0.3);
  assert.equal(p.H1, 0.4);
  assert.equal(p.PhiM, 0.1);
});

test('setParam mutates the value returned by getParams', () => {
  setParam('A', 0.5);
  assert.equal(getParams().A, 0.5);
});

test('subscribe is called with the full params object on every setParam', () => {
  const seen = [];
  const unsubscribe = subscribe((params) => seen.push(params.B));
  setParam('B', 0.42);
  assert.deepEqual(seen, [0.42]);
  unsubscribe();
  setParam('B', 0.7);
  assert.deepEqual(seen, [0.42]); // no further calls after unsubscribe
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/state.test.mjs`
Expected: FAIL — `js/state.js` does not exist yet (module not found).

- [ ] **Step 3: Write the implementation**

```js
// js/state.js
const params = {
  A: 0.3, B: 0.3,
  H1: 0.4, H2: 0.35,
  Hv: 0.4,
  Ec: 0.15,
  Ep: 0.03,
  Fee: 0.1,
  PhiM: 0.1,
  Uh: 0.04, Ub: 0.04,
  HsD: 0
};

const subscribers = new Set();

export function getParams() {
  return params;
}

export function setParam(key, value) {
  params[key] = value;
  for (const fn of subscribers) fn(params);
}

export function subscribe(fn) {
  subscribers.add(fn);
  return () => subscribers.delete(fn);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/state.test.mjs`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add js/state.js tests/state.test.mjs
git commit -m "feat: add state.js params store with pub-sub"
```

---

### Task 3: `dimensions.js` — shared dimension-record table

**Files:**
- Create: `js/dimensions.js`
- Test: `tests/dimensions.test.mjs`

**Interfaces:**
- Consumes: `getParams()`-shaped param objects (does NOT import `state.js` directly — each function takes `params` as an argument, so it is testable with a plain literal and reusable by both renderers without coupling to the live store).
- Produces:
  - `dimensionRecords`: an array of records `{ id, from(params), to(params), offsetDir, label(params) }` where `from`/`to` return plain `{x, y, z}` objects (NOT `THREE.Vector3` — kept dependency-free so this file needs no Three.js import and can be tested in plain Node). `offsetDir` is a static `{x, y, z}`.
  - `visualScale(key, value)`: returns `Math.max(value, 0.06)` for the "thin member" keys (`Ep`, `Uh`, `Ub`, `PhiM`), and returns `value` unchanged for every other key.
  - Later tasks: `diagram3d.js` imports `dimensionRecords` and `visualScale`, wraps `{x,y,z}` returns in `new THREE.Vector3(x, y, z)` itself. `diagram2d.js` imports the same two exports and projects `{x, y, z}` onto 2D by dropping one axis (documented as dropping `z` for the elevation view).

- [ ] **Step 1: Write the failing test**

```js
// tests/dimensions.test.mjs
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { dimensionRecords, visualScale } from '../js/dimensions.js';

const sampleParams = {
  A: 0.3, B: 0.3, H1: 0.4, H2: 0.35, Hv: 0.4,
  Ec: 0.15, Ep: 0.03, Fee: 0.1, PhiM: 0.1,
  Uh: 0.04, Ub: 0.04, HsD: 0
};

test('every record has the required shape', () => {
  assert.ok(dimensionRecords.length > 0);
  for (const rec of dimensionRecords) {
    assert.equal(typeof rec.id, 'string');
    assert.equal(typeof rec.from, 'function');
    assert.equal(typeof rec.to, 'function');
    assert.equal(typeof rec.label, 'function');
    assert.equal(typeof rec.offsetDir.x, 'number');
  }
});

test('from/to return plain {x,y,z} points, not class instances', () => {
  const rec = dimensionRecords.find((r) => r.id === 'H1');
  const p = rec.from(sampleParams);
  assert.equal(typeof p.x, 'number');
  assert.equal(typeof p.y, 'number');
  assert.equal(typeof p.z, 'number');
  assert.equal(p.constructor, Object);
});

test('label reflects the live param value', () => {
  const rec = dimensionRecords.find((r) => r.id === 'H1');
  assert.equal(rec.label(sampleParams), 'H1 = 0.40');
  assert.equal(rec.label({ ...sampleParams, H1: 0.55 }), 'H1 = 0.55');
});

test('visualScale clamps thin members but leaves the label value untouched', () => {
  assert.equal(visualScale('Ep', 0.03), 0.06);
  assert.equal(visualScale('Uh', 0.04), 0.06);
  assert.equal(visualScale('PhiM', 0.1), 0.1); // already above floor
  assert.equal(visualScale('A', 0.3), 0.3); // not a thin member, unchanged
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/dimensions.test.mjs`
Expected: FAIL — `js/dimensions.js` does not exist yet.

- [ ] **Step 3: Write the implementation**

```js
// js/dimensions.js

// Layout convention: X = width (A axis), Y = height, Z = depth (B axis).
// Block footprint sits at X in [0, A], Z in [0, B]; H1 is the lower
// section height, H2 the upper section height stacked on top of H1.

const THIN_MEMBERS = new Set(['Ep', 'Uh', 'Ub', 'PhiM']);
const VISUAL_FLOOR = 0.06;

export function visualScale(key, value) {
  if (THIN_MEMBERS.has(key)) return Math.max(value, VISUAL_FLOOR);
  return value;
}

export const dimensionRecords = [
  {
    id: 'A',
    from: (p) => ({ x: 0, y: 0, z: 0 }),
    to: (p) => ({ x: p.A, y: 0, z: 0 }),
    offsetDir: { x: 0, y: -1, z: 0 },
    label: (p) => `A = ${p.A.toFixed(2)}`
  },
  {
    id: 'B',
    from: (p) => ({ x: 0, y: 0, z: 0 }),
    to: (p) => ({ x: 0, y: 0, z: p.B }),
    offsetDir: { x: -1, y: 0, z: 0 },
    label: (p) => `B = ${p.B.toFixed(2)}`
  },
  {
    id: 'H1',
    from: (p) => ({ x: 0, y: 0, z: 0 }),
    to: (p) => ({ x: 0, y: p.H1, z: 0 }),
    offsetDir: { x: -1, y: 0, z: 0 },
    label: (p) => `H1 = ${p.H1.toFixed(2)}`
  },
  {
    id: 'H2',
    from: (p) => ({ x: 0, y: p.H1, z: 0 }),
    to: (p) => ({ x: 0, y: p.H1 + p.H2, z: 0 }),
    offsetDir: { x: -1, y: 0, z: 0 },
    label: (p) => `H2 = ${p.H2.toFixed(2)}`
  },
  {
    id: 'Hv',
    from: (p) => ({ x: 0, y: p.H1 + p.H2, z: 0 }),
    to: (p) => ({ x: 0, y: p.H1 + p.H2 + p.Hv, z: 0 }),
    offsetDir: { x: 1, y: 0, z: 0 },
    label: (p) => `Hv = ${p.Hv.toFixed(2)}`
  },
  {
    id: 'Ec',
    from: (p) => ({ x: 0, y: p.H1 + p.H2 + p.Hv, z: 0 }),
    to: (p) => ({ x: 0, y: p.H1 + p.H2 + p.Hv + p.Ec, z: 0 }),
    offsetDir: { x: -1, y: 0, z: 0 },
    label: (p) => `Ec = ${p.Ec.toFixed(2)}`
  },
  {
    id: 'Ep',
    from: (p) => ({ x: p.A, y: p.H1, z: 0 }),
    to: (p) => ({ x: p.A + visualScale('Ep', p.Ep), y: p.H1, z: 0 }),
    offsetDir: { x: 0, y: 1, z: 0 },
    label: (p) => `Ep = ${p.Ep.toFixed(2)}`
  },
  {
    id: 'Fee',
    from: (p) => ({ x: 0, y: p.H1 + p.H2 + p.Hv + p.Ec, z: 0 }),
    to: (p) => ({ x: 0, y: p.H1 + p.H2 + p.Hv + p.Ec + p.Fee, z: 0 }),
    offsetDir: { x: -1, y: 0, z: 0 },
    label: (p) => `Fee = ${p.Fee.toFixed(2)}`
  },
  {
    id: 'PhiM',
    from: (p) => ({ x: p.A, y: p.H1 + p.H2, z: 0 }),
    to: (p) => ({ x: p.A + visualScale('PhiM', p.PhiM), y: p.H1 + p.H2, z: 0 }),
    offsetDir: { x: 0, y: 1, z: 0 },
    label: (p) => `Φm = ${p.PhiM.toFixed(2)}`
  },
  {
    id: 'Uh',
    from: (p) => ({ x: p.A, y: p.H1 + p.H2 + p.Hv, z: 0 }),
    to: (p) => ({ x: p.A + visualScale('Uh', p.Uh), y: p.H1 + p.H2 + p.Hv, z: 0 }),
    offsetDir: { x: 0, y: 1, z: 0 },
    label: (p) => `Uh = ${p.Uh.toFixed(2)}`
  },
  {
    id: 'Ub',
    from: (p) => ({ x: p.A, y: 0, z: 0 }),
    to: (p) => ({ x: p.A + visualScale('Ub', p.Ub), y: 0, z: 0 }),
    offsetDir: { x: 0, y: -1, z: 0 },
    label: (p) => `Ub = ${p.Ub.toFixed(2)}`
  }
];
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/dimensions.test.mjs`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add js/dimensions.js tests/dimensions.test.mjs
git commit -m "feat: add shared dimension-record table with visual scale clamping"
```

---

### Task 4: `diagram2d.js` — SVG elevation view

**Files:**
- Create: `js/diagram2d.js`

**Interfaces:**
- Consumes: `dimensionRecords`, `visualScale` from `js/dimensions.js` (Task 3); a params object shaped like `state.js`'s (Task 2).
- Produces: `export function mountDiagram2D(container)` which creates and appends an `<svg>` into `container`, and returns `{ render(params) }`. `render(params)` clears and redraws the SVG's witness lines + labels from `dimensionRecords`. Later tasks (`app.js` Task 7, `modal.js` Task 8) call `mountDiagram2D` once and then call the returned `render(params)` on every state change.

- [ ] **Step 1: Write the implementation**

Projection convention: drop the `z` axis (elevation view looking down `-Z`), map 3D `x -> SVG x`, 3D `y -> SVG y` (flipped, since SVG y grows downward), scaled by a fixed `PX_PER_METER` and offset so the diagram sits inside the container with margin.

```js
// js/diagram2d.js
import { dimensionRecords } from './dimensions.js';

const PX_PER_METER = 300;
const MARGIN = 40;

function toScreen(pt, height) {
  return {
    x: MARGIN + pt.x * PX_PER_METER,
    y: MARGIN + (height - pt.y) * PX_PER_METER
  };
}

export function mountDiagram2D(container) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('width', '100%');
  svg.setAttribute('height', '100%');
  svg.setAttribute('viewBox', '0 0 600 500');
  container.appendChild(svg);

  function render(params) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    const sceneHeight = (params.H1 + params.H2 + params.Hv + params.Ec + params.Fee) + 0.3;

    for (const rec of dimensionRecords) {
      const from = toScreen(rec.from(params), sceneHeight);
      const to = toScreen(rec.to(params), sceneHeight);

      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', from.x);
      line.setAttribute('y1', from.y);
      line.setAttribute('x2', to.x);
      line.setAttribute('y2', to.y);
      line.setAttribute('stroke', '#e07a2c');
      line.setAttribute('stroke-width', '2');
      line.setAttribute('stroke-dasharray', '4,3');
      svg.appendChild(line);

      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      const midX = (from.x + to.x) / 2 + rec.offsetDir.x * 14;
      const midY = (from.y + to.y) / 2 + rec.offsetDir.y * 14;
      text.setAttribute('x', midX);
      text.setAttribute('y', midY);
      text.setAttribute('font-size', '11');
      text.setAttribute('fill', '#1a2b4c');
      text.textContent = rec.label(params);
      svg.appendChild(text);
    }
  }

  return { render };
}
```

- [ ] **Step 2: Manual browser verification**

Temporarily add to `js/app.js` (will be replaced in Task 7, so this is throwaway wiring, not a permanent addition):

```js
import { mountDiagram2D } from './diagram2d.js';
import { getParams } from './state.js';
const testDiv = document.createElement('div');
testDiv.style.width = '600px';
testDiv.style.height = '500px';
document.body.appendChild(testDiv);
const view2d = mountDiagram2D(testDiv);
view2d.render(getParams());
```

Run: `python3 -m http.server`, open `http://localhost:8000/`.
Expected: an SVG showing dashed orange lines with labels like `A = 0.30`, `H1 = 0.40` etc., roughly forming an elevation of a stepped block with a stub at top. No console errors.

Revert this temporary snippet from `js/app.js` before committing (Task 7 replaces `app.js` for real; this task's `app.js` diff should be empty — only `js/diagram2d.js` is new).

- [ ] **Step 3: Commit**

```bash
git add js/diagram2d.js
git commit -m "feat: add SVG 2D elevation diagram renderer"
```

---

### Task 5: `diagram3d.js` — Three.js scene with witness lines and CSS2D labels

**Files:**
- Create: `js/diagram3d.js`

**Interfaces:**
- Consumes: `dimensionRecords`, `visualScale` from `js/dimensions.js` (Task 3); `three` and `three/addons/controls/OrbitControls.js`, `three/addons/renderers/CSS2DRenderer.js` (Task 1's importmap).
- Produces: `export function mountDiagram3D(container)` which creates a `<canvas>` + a CSS2D overlay `<div>`, both appended into `container`, starts a render loop, and returns `{ render(params), canvas, overlay, resize() }`. `render(params)` rebuilds the box/pipe geometry and dimension lines/labels from the given params (full rebuild each call — acceptable at this scale per spec §7). `resize()` re-reads the container's current size and updates the renderer/camera — Task 8 (`modal.js`) calls this after re-parenting `canvas`/`overlay` into the modal. Exposing `canvas` and `overlay` as properties (not just appending them internally) is what lets `modal.js` move them without needing to know internals of `diagram3d.js`.

- [ ] **Step 1: Write the implementation**

```js
// js/diagram3d.js
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';
import { dimensionRecords, visualScale } from './dimensions.js';

export function mountDiagram3D(container) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  const canvas = renderer.domElement;
  container.appendChild(canvas);

  const labelRenderer = new CSS2DRenderer();
  labelRenderer.domElement.style.position = 'absolute';
  labelRenderer.domElement.style.top = '0';
  labelRenderer.domElement.style.left = '0';
  labelRenderer.domElement.style.pointerEvents = 'none';
  const overlay = labelRenderer.domElement;
  container.appendChild(overlay);
  container.style.position = 'relative';

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 100);
  camera.position.set(1.2, 1.0, 1.5);

  const controls = new OrbitControls(camera, canvas);
  controls.target.set(0, 0.4, 0);
  controls.enableDamping = true;

  scene.add(new THREE.AmbientLight(0xffffff, 0.7));
  const dirLight = new THREE.DirectionalLight(0xffffff, 0.6);
  dirLight.position.set(2, 3, 2);
  scene.add(dirLight);

  let dynamicGroup = new THREE.Group();
  scene.add(dynamicGroup);

  function resize() {
    const w = container.clientWidth || 1;
    const h = container.clientHeight || 1;
    renderer.setSize(w, h, false);
    labelRenderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }

  function buildScene(params) {
    scene.remove(dynamicGroup);
    dynamicGroup = new THREE.Group();

    const blockHeight = params.H1 + params.H2;
    const blockGeo = new THREE.BoxGeometry(params.A, blockHeight, params.B);
    const blockMat = new THREE.MeshStandardMaterial({ color: 0xcfd8e3, transparent: true, opacity: 0.5 });
    const blockMesh = new THREE.Mesh(blockGeo, blockMat);
    blockMesh.position.set(params.A / 2, blockHeight / 2, params.B / 2);
    dynamicGroup.add(blockMesh);

    const pipeStart = { x: 0, y: params.H1 + params.H2 + params.Hv, z: 0 };
    const pipeEnd = { x: params.A, y: params.H1 + params.H2 + params.Hv, z: 0 };
    const pipeRadius = visualScale('PhiM', params.PhiM) / 2;
    const pipeLen = Math.hypot(pipeEnd.x - pipeStart.x, pipeEnd.z - pipeStart.z) || params.A;
    const pipeGeo = new THREE.CylinderGeometry(pipeRadius, pipeRadius, pipeLen, 16);
    const pipeMat = new THREE.MeshStandardMaterial({ color: 0xe07a2c });
    const pipeMesh = new THREE.Mesh(pipeGeo, pipeMat);
    pipeMesh.rotation.z = Math.PI / 2;
    pipeMesh.position.set(params.A / 2, pipeStart.y, 0);
    dynamicGroup.add(pipeMesh);

    for (const rec of dimensionRecords) {
      const from = rec.from(params);
      const to = rec.to(params);
      const lineGeo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(from.x, from.y, from.z),
        new THREE.Vector3(to.x, to.y, to.z)
      ]);
      const lineMat = new THREE.LineDashedMaterial({ color: 0x1a2b4c, dashSize: 0.02, gapSize: 0.01 });
      const line = new THREE.Line(lineGeo, lineMat);
      line.computeLineDistances();
      dynamicGroup.add(line);

      const labelDiv = document.createElement('div');
      labelDiv.textContent = rec.label(params);
      labelDiv.style.fontSize = '11px';
      labelDiv.style.color = '#1a2b4c';
      labelDiv.style.background = 'rgba(255,255,255,0.8)';
      labelDiv.style.padding = '1px 4px';
      labelDiv.style.borderRadius = '3px';
      labelDiv.style.whiteSpace = 'nowrap';
      const labelObj = new CSS2DObject(labelDiv);
      labelObj.position.set(
        (from.x + to.x) / 2 + rec.offsetDir.x * 0.05,
        (from.y + to.y) / 2 + rec.offsetDir.y * 0.05,
        (from.z + to.z) / 2 + rec.offsetDir.z * 0.05
      );
      dynamicGroup.add(labelObj);
    }

    scene.add(dynamicGroup);
  }

  function render(params) {
    buildScene(params);
  }

  function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
    labelRenderer.render(scene, camera);
  }
  resize();
  animate();

  return { render, canvas, overlay, resize };
}
```

- [ ] **Step 2: Manual browser verification**

Temporarily add to `js/app.js` (throwaway wiring, revert before committing — same pattern as Task 4):

```js
import { mountDiagram3D } from './diagram3d.js';
import { getParams } from './state.js';
const testDiv3d = document.createElement('div');
testDiv3d.style.width = '600px';
testDiv3d.style.height = '500px';
document.body.appendChild(testDiv3d);
const view3d = mountDiagram3D(testDiv3d);
view3d.render(getParams());
```

Run: `python3 -m http.server`, open `http://localhost:8000/`.
Expected: a translucent gray box with an orange cylindrical pipe crossing near its top, dashed navy witness lines with small text labels (`A = 0.30`, `H1 = 0.40`, etc.) that stay upright and readable while dragging to orbit the camera (left-drag to rotate via `OrbitControls`). No console errors.

Revert the temporary snippet from `js/app.js` before committing.

- [ ] **Step 3: Commit**

```bash
git add js/diagram3d.js
git commit -m "feat: add Three.js 3D diagram renderer with CSS2D dimension labels"
```

---

### Task 6: Console chrome layout (topbar, sidebar, form, right rail) — static markup + CSS

**Files:**
- Create: `css/style.css` (replaces Task 1's placeholder)
- Modify: `index.html` (replaces the temporary `<div id="app">Loading&hellip;</div>` body with the full static layout)

**Interfaces:**
- Consumes: nothing new — pure markup/CSS.
- Produces: the DOM structure Task 7 wires up. Specific element `id`s Task 7 depends on:
  - Form inputs: one `<input type="number">` per param key, each with `id="input-<key>"` (e.g. `id="input-A"`, `id="input-H1"`), matching every key in `state.js`'s params object exactly.
  - `id="diagram-thumbnail"` — container div where `diagram2d.js`/`diagram3d.js` get mounted (thumbnail size).
  - `id="view-toggle-2d"` / `id="view-toggle-3d"` — thumbnail's 2D/3D toggle buttons.
  - `id="expand-diagram-btn"` — "Agrandir" button.
  - `id="result-rows"` — container div where right-rail static result text gets rendered per param change.
  - `id="modal-overlay"` (whole modal, hidden via a CSS class, not `display:none` inline, so Task 8 can toggle a single class), `id="modal-diagram-container"` (where the canvas/overlay get re-parented), `id="modal-view-toggle-2d"` / `id="modal-view-toggle-3d"`, `id="modal-close-btn"`.

- [ ] **Step 1: Write `index.html`'s full body markup**

Replace the `<body>` contents (keep the existing `<head>` importmap block from Task 1 untouched):

```html
<body>
  <header class="topbar">
    <div class="topbar-brand">Courtier Console</div>
    <div class="topbar-actions">
      <span class="icon-btn" title="Notifications">&#128276;</span>
      <span class="user-menu">Loïc Dupont &#9662;</span>
    </div>
  </header>

  <div class="layout">
    <nav class="sidebar">
      <ul>
        <li>Plans tarifaires</li>
        <li>Prime commerciale</li>
        <li>Dispositifs d&rsquo;incitation</li>
        <li>Fiches</li>
        <li>Photos</li>
        <li>Chiffrage détaillé</li>
        <li>Formulaires</li>
        <li>Suivi</li>
        <li class="active">Diagnostic étude</li>
        <li>Contrôles</li>
        <li>Attestation</li>
      </ul>
    </nav>

    <main class="main-column">
      <h1>Données</h1>

      <section class="form-section">
        <h2>Cadre</h2>
        <div class="field-grid">
          <label>A (m) <input type="number" id="input-A" min="0" max="2" step="0.01"></label>
          <label>B (m) <input type="number" id="input-B" min="0" max="2" step="0.01"></label>
          <label>H1 (m) <input type="number" id="input-H1" min="0" max="2" step="0.01"></label>
          <label>H2 (m) <input type="number" id="input-H2" min="0" max="2" step="0.01"></label>
        </div>
      </section>

      <section class="form-section">
        <h2>Poteau</h2>
        <div class="field-grid">
          <label>Hv (m) <input type="number" id="input-Hv" min="0" max="2" step="0.01"></label>
          <label>Ec (m) <input type="number" id="input-Ec" min="0" max="1" step="0.01"></label>
          <label>Fee (m) <input type="number" id="input-Fee" min="0" max="1" step="0.01"></label>
        </div>
      </section>

      <section class="form-section">
        <h2>Plaque d&rsquo;appui</h2>
        <div class="field-grid">
          <label>Ep (m) <input type="number" id="input-Ep" min="0" max="0.5" step="0.005"></label>
          <label>&Phi;m (m) <input type="number" id="input-PhiM" min="0" max="0.5" step="0.005"></label>
          <label>Uh (m) <input type="number" id="input-Uh" min="0" max="0.5" step="0.005"></label>
          <label>Ub (m) <input type="number" id="input-Ub" min="0" max="0.5" step="0.005"></label>
          <label>HsD (m) <input type="number" id="input-HsD" min="0" max="1" step="0.01"></label>
        </div>
      </section>
    </main>

    <aside class="right-rail">
      <div class="validation-chips">
        <span class="chip chip-ok">Cadre &#10003;</span>
        <span class="chip chip-ok">Poteau &#10003;</span>
      </div>

      <div class="diagram-panel">
        <div class="diagram-toggle">
          <button id="view-toggle-2d" class="toggle-btn active">2D</button>
          <button id="view-toggle-3d" class="toggle-btn">3D</button>
        </div>
        <div id="diagram-thumbnail" class="diagram-container"></div>
        <button id="expand-diagram-btn" class="expand-btn">Agrandir le diagramme</button>
      </div>

      <div class="warning-callout">
        Vérifiez les paramètres avant validation finale.
      </div>

      <div id="result-rows" class="result-rows"></div>
    </aside>
  </div>

  <div id="modal-overlay" class="modal-overlay hidden">
    <div class="modal">
      <div class="modal-header">
        <h2>Agrandir le diagramme</h2>
        <button id="modal-close-btn" class="close-btn">&times;</button>
      </div>
      <div class="diagram-toggle">
        <button id="modal-view-toggle-2d" class="toggle-btn active">2D</button>
        <button id="modal-view-toggle-3d" class="toggle-btn">3D</button>
      </div>
      <div id="modal-diagram-container" class="diagram-container modal-diagram-container"></div>
    </div>
  </div>

  <script type="module" src="js/app.js"></script>
</body>
```

- [ ] **Step 2: Write `css/style.css`**

```css
:root {
  --navy: #1a2b4c;
  --orange: #e07a2c;
  --bg: #f4f6f9;
  --panel-bg: #ffffff;
  --border: #d8dee6;
}

* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, sans-serif; background: var(--bg); color: var(--navy); }

.topbar {
  background: var(--navy);
  color: white;
  padding: 0.75rem 1.5rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.layout {
  display: grid;
  grid-template-columns: 220px 1fr 320px;
  gap: 1rem;
  padding: 1rem;
  align-items: start;
}

.sidebar ul { list-style: none; padding: 0; margin: 0; }
.sidebar li {
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  cursor: default;
  color: #55606f;
  font-size: 0.9rem;
}
.sidebar li.active { background: var(--navy); color: white; }

.main-column { background: var(--panel-bg); border-radius: 6px; padding: 1.5rem; }
.form-section { margin-bottom: 1.5rem; }
.form-section h2 { font-size: 1rem; border-bottom: 1px solid var(--border); padding-bottom: 0.25rem; }
.field-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.75rem; margin-top: 0.75rem; }
.field-grid label { display: flex; flex-direction: column; font-size: 0.8rem; gap: 0.25rem; }
.field-grid input { padding: 0.4rem; border: 1px solid var(--border); border-radius: 4px; }

.right-rail { display: flex; flex-direction: column; gap: 1rem; }
.validation-chips { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.chip { padding: 0.25rem 0.6rem; border-radius: 999px; font-size: 0.75rem; }
.chip-ok { background: #dff3e3; color: #1c7a3a; }

.diagram-panel { background: var(--panel-bg); border-radius: 6px; padding: 1rem; }
.diagram-toggle { display: flex; gap: 0.25rem; margin-bottom: 0.5rem; }
.toggle-btn { flex: 1; padding: 0.3rem; border: 1px solid var(--border); background: white; border-radius: 4px; cursor: pointer; }
.toggle-btn.active { background: var(--navy); color: white; }
.diagram-container { width: 100%; height: 220px; position: relative; overflow: hidden; }
.expand-btn { width: 100%; margin-top: 0.5rem; padding: 0.5rem; border: none; background: var(--orange); color: white; border-radius: 4px; cursor: pointer; }

.warning-callout { background: #fdf3d9; color: #8a6116; padding: 0.75rem; border-radius: 6px; font-size: 0.85rem; }
.result-rows { background: var(--panel-bg); border-radius: 6px; padding: 1rem; font-size: 0.85rem; }
.result-rows .row { display: flex; justify-content: space-between; padding: 0.25rem 0; border-bottom: 1px solid var(--border); }

.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center;
}
.modal-overlay.hidden { display: none; }
.modal { background: white; border-radius: 8px; padding: 1.5rem; width: min(90vw, 900px); }
.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
.close-btn { border: none; background: none; font-size: 1.5rem; cursor: pointer; }
.modal-diagram-container { height: 60vh; }
```

- [ ] **Step 3: Manual browser verification**

Run: `python3 -m http.server`, open `http://localhost:8000/`.
Expected: full console chrome renders — dark navy topbar, sidebar with "Diagnostic étude" highlighted, form sections with number inputs, right rail with green chips/empty diagram panel/orange button/yellow callout. Modal is present in the DOM but hidden (`.modal-overlay.hidden` has `display:none`). No console errors (note: `js/app.js` still only has Task 1's smoke-test code at this point, so the diagram panel will be empty until Task 7 — that's expected here).

- [ ] **Step 4: Commit**

```bash
git add index.html css/style.css
git commit -m "feat: add static console chrome layout (topbar, sidebar, form, right rail, modal)"
```

---

### Task 7: `app.js` — wire form inputs to state and mount both diagram views

**Files:**
- Modify: `js/app.js` (replaces Task 1's smoke-test body entirely)

**Interfaces:**
- Consumes: `getParams`, `setParam`, `subscribe` from `js/state.js` (Task 2); `mountDiagram2D` from `js/diagram2d.js` (Task 4); `mountDiagram3D` from `js/diagram3d.js` (Task 5); the DOM `id`s defined in Task 6.
- Produces: on load, populates every `#input-<key>` with its current param value, attaches `input` listeners that call `setParam`, mounts both diagram views into `#diagram-thumbnail` (only one visible at a time based on `viewMode`, both kept mounted so switching is instant — see note below), and renders `#result-rows`. Exposes `window.__courtierApp = { view2d, view3d, getViewMode, setViewMode }` — this is how `js/modal.js` (Task 8) accesses the same live view instances without a circular import; `modal.js` reads from `window.__courtierApp` rather than `app.js` importing `modal.js` (avoids a cycle since `app.js` must run first to mount the diagrams).

- [ ] **Step 1: Replace `js/app.js`**

```js
// js/app.js
import { getParams, setParam, subscribe } from './state.js';
import { mountDiagram2D } from './diagram2d.js';
import { mountDiagram3D } from './diagram3d.js';

const PARAM_KEYS = ['A', 'B', 'H1', 'H2', 'Hv', 'Ec', 'Ep', 'Fee', 'PhiM', 'Uh', 'Ub', 'HsD'];

let viewMode = '2d'; // '2d' | '3d'

const thumbnailContainer = document.getElementById('diagram-thumbnail');
const view2d = mountDiagram2D(thumbnailContainer);
const view3d = mountDiagram3D(thumbnailContainer);

function applyViewModeVisibility() {
  // Both views are mounted into the same container; only one is visible/interactive at a time.
  view3d.canvas.style.display = viewMode === '3d' ? 'block' : 'none';
  view3d.overlay.style.display = viewMode === '3d' ? 'block' : 'none';
  const svgEl = thumbnailContainer.querySelector('svg');
  if (svgEl) svgEl.style.display = viewMode === '2d' ? 'block' : 'none';
}

function setViewMode(mode) {
  viewMode = mode;
  document.getElementById('view-toggle-2d').classList.toggle('active', mode === '2d');
  document.getElementById('view-toggle-3d').classList.toggle('active', mode === '3d');
  const modalToggle2d = document.getElementById('modal-view-toggle-2d');
  const modalToggle3d = document.getElementById('modal-view-toggle-3d');
  if (modalToggle2d) modalToggle2d.classList.toggle('active', mode === '2d');
  if (modalToggle3d) modalToggle3d.classList.toggle('active', mode === '3d');
  applyViewModeVisibility();
}

function renderResultRows(params) {
  const container = document.getElementById('result-rows');
  container.innerHTML = '';
  for (const key of PARAM_KEYS) {
    const row = document.createElement('div');
    row.className = 'row';
    row.innerHTML = `<span>${key}</span><span>${params[key].toFixed(3)} m</span>`;
    container.appendChild(row);
  }
}

function renderAll(params) {
  view2d.render(params);
  view3d.render(params);
  renderResultRows(params);
}

function setupFormInputs() {
  const params = getParams();
  for (const key of PARAM_KEYS) {
    const input = document.getElementById(`input-${key}`);
    input.value = params[key];
    input.addEventListener('input', () => {
      const value = parseFloat(input.value);
      if (Number.isFinite(value) && value >= 0) {
        setParam(key, value);
      }
    });
    input.addEventListener('blur', () => {
      input.value = getParams()[key];
    });
  }
}

document.getElementById('view-toggle-2d').addEventListener('click', () => setViewMode('2d'));
document.getElementById('view-toggle-3d').addEventListener('click', () => setViewMode('3d'));

setupFormInputs();
subscribe(renderAll);
renderAll(getParams());
applyViewModeVisibility();

window.__courtierApp = { view2d, view3d, getViewMode: () => viewMode, setViewMode };
```

- [ ] **Step 2: Manual browser verification**

Run: `python3 -m http.server`, open `http://localhost:8000/`.
Expected:
1. Every form input is pre-filled with its default value (e.g. `input-A` shows `0.3`).
2. The right rail's diagram panel shows the 2D SVG view by default (toggle button "2D" highlighted).
3. Changing any input (e.g. type `0.5` into `input-H1`) immediately updates: the SVG lines/labels in the thumbnail, AND the corresponding row in `#result-rows` below the warning callout.
4. Clicking the "3D" toggle button switches the thumbnail to the Three.js view (orbit-draggable), hiding the SVG; clicking "2D" switches back. No console errors either time.
5. Typing a negative number or clearing the field does not crash and the value reverts to the last valid one on blur (per spec §9).

- [ ] **Step 3: Commit**

```bash
git add js/app.js
git commit -m "feat: wire form inputs to shared state and mount both diagram views"
```

---

### Task 8: `modal.js` — enlarge/collapse with canvas re-parenting

**Files:**
- Create: `js/modal.js`
- Modify: `index.html` (add `<script type="module" src="js/modal.js"></script>` after the `app.js` script tag, so `modal.js` runs after `window.__courtierApp` exists)

**Interfaces:**
- Consumes: `window.__courtierApp` (set by Task 7's `app.js`); DOM ids `#expand-diagram-btn`, `#modal-overlay`, `#modal-close-btn`, `#modal-diagram-container`, `#diagram-thumbnail`, `#modal-view-toggle-2d`, `#modal-view-toggle-3d` (all from Task 6).
- Produces: clicking "Agrandir" moves `view3d.canvas` and `view3d.overlay` (and the thumbnail's `<svg>` element, so the 2D view also enlarges) into `#modal-diagram-container`, shows the modal, calls `view3d.resize()`. Closing (via `#modal-close-btn` or clicking the overlay backdrop) moves both back into `#diagram-thumbnail` and resizes again. Wires the modal's own 2D/3D toggle buttons to the same `setViewMode` used by the thumbnail's toggle (via `window.__courtierApp.setViewMode`), so both toggles always agree.

- [ ] **Step 1: Add the script tag to `index.html`**

Add directly after the existing `<script type="module" src="js/app.js"></script>` line:

```html
<script type="module" src="js/modal.js"></script>
```

- [ ] **Step 2: Write `js/modal.js`**

```js
// js/modal.js
function getApp() {
  // app.js runs first (script tag order in index.html), so this is defined by the time
  // any click handler below fires.
  return window.__courtierApp;
}

const overlayEl = document.getElementById('modal-overlay');
const thumbnailContainer = document.getElementById('diagram-thumbnail');
const modalContainer = document.getElementById('modal-diagram-container');
const expandBtn = document.getElementById('expand-diagram-btn');
const closeBtn = document.getElementById('modal-close-btn');
const modalToggle2d = document.getElementById('modal-view-toggle-2d');
const modalToggle3d = document.getElementById('modal-view-toggle-3d');

function moveDiagramInto(targetContainer) {
  const app = getApp();
  const svgEl = thumbnailContainer.querySelector('svg') || modalContainer.querySelector('svg');
  if (svgEl) targetContainer.appendChild(svgEl);
  targetContainer.appendChild(app.view3d.canvas);
  targetContainer.appendChild(app.view3d.overlay);
  app.view3d.resize();
}

function openModal() {
  overlayEl.classList.remove('hidden');
  moveDiagramInto(modalContainer);
}

function closeModal() {
  overlayEl.classList.add('hidden');
  moveDiagramInto(thumbnailContainer);
}

expandBtn.addEventListener('click', openModal);
closeBtn.addEventListener('click', closeModal);
overlayEl.addEventListener('click', (e) => {
  if (e.target === overlayEl) closeModal();
});
modalToggle2d.addEventListener('click', () => getApp().setViewMode('2d'));
modalToggle3d.addEventListener('click', () => getApp().setViewMode('3d'));
```

- [ ] **Step 3: Manual browser verification (full spec §10 checklist)**

Run: `python3 -m http.server`, open `http://localhost:8000/`.

1. Click "Agrandir le diagramme" while in 2D mode: modal opens, the same SVG diagram (not a duplicate) now fills the larger modal container, values match the thumbnail's last state.
2. Click "3D" inside the modal: it switches to the Three.js view inside the modal, orbit-draggable; the thumbnail's toggle button also shows "3D" as active (shared state).
3. Change a form input while the modal is open: confirm the modal's diagram updates live (same `subscribe` callback re-renders whichever view is currently mounted, regardless of which container it's in).
4. Close the modal (`×` button, then re-open and close via backdrop click): confirm the diagram moves back to the thumbnail correctly both times, with no duplicate canvases left behind (inspect DOM via browser devtools — there should be exactly one `<canvas>` element on the page at all times).
5. Resize the browser window with the modal open, then with it closed: confirm the diagram redraws at the new size with no cut-off or misaligned labels (drag-resize or use devtools device toolbar).

If any step fails, fix `modal.js` or `diagram3d.js`'s `resize()` before proceeding — this is the last functional task.

- [ ] **Step 4: Commit**

```bash
git add index.html js/modal.js
git commit -m "feat: add enlarge modal with single-canvas re-parenting"
```

---

### Task 9: README + final full verification pass

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: nothing.
- Produces: documented run instructions for anyone opening this repo cold.

- [ ] **Step 1: Write `README.md`**

```markdown
# Courtier Console Demo

Portfolio demo: an admin-console-style config form whose numeric inputs
drive a live parametric diagram, rendered in both 2D (SVG) and 3D
(Three.js), with a modal to enlarge the diagram. Static site, no build
step, no backend.

## Run it

    python3 -m http.server

Then open http://localhost:8000/ in a browser.

## Run the unit tests (pure-logic modules only)

    node --test tests/

`state.js` and `dimensions.js` have no DOM or Three.js dependency and
are tested directly with Node's built-in test runner. Everything else
(`diagram2d.js`, `diagram3d.js`, `app.js`, `modal.js`) is DOM/WebGL-
dependent and is verified manually in-browser — see
`docs/superpowers/specs/2026-09-05-courtier-console-design.md` §10 for
the manual verification checklist.

## Design docs

- Spec: `docs/superpowers/specs/2026-09-05-courtier-console-design.md`
- Plan: `docs/superpowers/plans/2026-09-05-courtier-console-demo.md`
```

- [ ] **Step 2: Run the full automated test suite one more time**

Run: `node --test tests/`
Expected: PASS (7 tests total across `state.test.mjs` and `dimensions.test.mjs`).

- [ ] **Step 3: Run through the spec's full §10 manual checklist one final time end-to-end**

Serve, open in browser, and confirm every one of the spec's 5 verification steps still holds now that all pieces are integrated together (not just per-task in isolation): importmap smoke test, per-field live update in both views, modal open/close from both view modes, and window-resize correctness.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add README with run and test instructions"
```
