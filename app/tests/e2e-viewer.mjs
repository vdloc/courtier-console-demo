// End-to-end suite for the structural digital-twin viewer.
//
//   npm run dev            # or: npm run build && npm run preview
//   node tests/e2e-viewer.mjs
//   BASE=http://localhost:4173 node tests/e2e-viewer.mjs
//
// Playwright is resolved from the global install first, matching the sibling
// suite in ../../tests/e2e.mjs: this repo has two independent front ends and
// only one of them has a node_modules tree.
//
// The suite asserts against the scene graph, not against the DOM alone. A
// layer toggle that flips `data-active` while the geometry stays on screen is
// a passing button and a broken feature, so every UI action is checked
// through `window.__viewer` (installed in scene/Viewer.tsx) for the effect it
// is supposed to have on the model.
import { execSync } from 'node:child_process';

async function loadPlaywright() {
  try {
    return await import('playwright');
  } catch {
    const root =
      process.env.PLAYWRIGHT_ROOT || execSync('npm root -g').toString().trim();
    return await import(`${root}/playwright/index.mjs`);
  }
}
const { chromium } = await loadPlaywright();

const BASE = process.env.BASE || 'http://localhost:5173';

let pass = 0;
const failures = [];
function check(name, cond, detail = '') {
  if (cond) {
    pass++;
    console.log(`  ok   ${name}`);
  } else {
    failures.push(`${name}${detail ? ' -- ' + detail : ''}`);
    console.log(`  FAIL ${name}${detail ? ' -- ' + detail : ''}`);
  }
}

const near = (a, b, tol) => Math.abs(a - b) <= tol;

// ---------------------------------------------------------------------------
// Browser
//
// SwiftShader rather than a real GPU: this has to run headless and over SSH.
// It renders a 3137-object scene correctly but slowly, which is why every wait
// below is a condition poll rather than a fixed delay.
// ---------------------------------------------------------------------------
const browser = await chromium.launch({
  args: [
    '--use-gl=angle',
    '--use-angle=swiftshader',
    '--enable-unsafe-swiftshader',
    '--ignore-gpu-blocklist',
  ],
});
const context = await browser.newContext({
  viewport: { width: 1600, height: 900 },
  deviceScaleFactor: 1,
});
const page = await context.newPage();

const consoleErrors = [];
page.on('console', (message) => {
  if (message.type() === 'error') consoleErrors.push(message.text());
});
page.on('pageerror', (error) =>
  consoleErrors.push(`pageerror: ${error.message}`),
);

// ---------------------------------------------------------------------------
// In-page helpers
// ---------------------------------------------------------------------------

/** Current Zustand state, structured-cloneable (the `object` ref is dropped). */
const state = () =>
  page.evaluate(() => {
    const s = window.__viewer.store.getState();
    return {
      ready: s.ready,
      layers: s.layers,
      playback: s.playback,
      progress: s.progress,
      exploded: s.exploded,
      explodeFactor: s.explodeFactor,
      shot: s.shot,
      measuring: s.measuring,
      measurePoints: s.measurePoints,
      quality: s.quality,
      selected: s.selected
        ? {
            name: s.selected.name,
            element_type: s.selected.element_type,
            section: s.selected.section,
            length: s.selected.length,
            grid_ref: s.selected.grid_ref,
            level: s.selected.level,
            status: s.selected.status,
            material_spec: s.selected.material_spec,
          }
        : null,
    };
  });

/** Camera world position. */
const cameraPosition = () =>
  page.evaluate(() => {
    const c = window.__viewer.camera;
    return [c.position.x, c.position.y, c.position.z];
  });

/**
 * Model extent and mean node scale.
 *
 * Both are needed to tell the finished structure from the parked one: the
 * construction clip parks every node at scale 0.001 *and* drops it below
 * ground, so scale alone could be fooled by a half-played clip and extent
 * alone by a model that is merely hidden.
 */
const modelMetrics = () =>
  page.evaluate(() => {
    const scene = window.__viewer.scene;
    scene.updateMatrixWorld(true);
    let n = 0;
    let scaleSum = 0;
    const min = [Infinity, Infinity, Infinity];
    const max = [-Infinity, -Infinity, -Infinity];
    scene.traverse((o) => {
      if (!o.isMesh) return;
      n += 1;
      scaleSum += (o.scale.x + o.scale.y + o.scale.z) / 3;
      const e = o.matrixWorld.elements;
      const p = [e[12], e[13], e[14]];
      for (let i = 0; i < 3; i += 1) {
        if (p[i] < min[i]) min[i] = p[i];
        if (p[i] > max[i]) max[i] = p[i];
      }
    });
    return {
      meshes: n,
      meanScale: n ? scaleSum / n : 0,
      extent: [max[0] - min[0], max[1] - min[1], max[2] - min[2]],
    };
  });

/** Visibility of a top-level layer group, read off the graph itself. */
const layerVisible = (name) =>
  page.evaluate((n) => {
    const group = window.__viewer.scene.getObjectByName(n);
    return group ? group.visible : null;
  }, name);

/**
 * Screen coordinates of a pickable member.
 *
 * Clicking the middle of the canvas is a coin flip - it may land on sky. This
 * projects real member origins and returns the one nearest the centre of the
 * viewport that is actually on screen, so a pick is deterministic.
 */
const pickPoint = (opts = {}) =>
  page.evaluate((o) => {
    const { scene, camera, gl } = window.__viewer;
    scene.updateMatrixWorld(true);
    camera.updateMatrixWorld(true);
    const rect = gl.domElement.getBoundingClientRect();
    const V = camera.position.constructor;
    const candidates = [];

    scene.traverse((obj) => {
      if (!obj.isMesh || !obj.visible) return;
      const data = obj.userData || {};
      if (!data.element_type) return;
      if (o.type && data.element_type !== o.type) return;

      // An invisible ancestor still leaves obj.visible true, so walk up.
      for (let p = obj.parent; p; p = p.parent) if (!p.visible) return;

      const v = new V().setFromMatrixPosition(obj.matrixWorld);
      const world = v.clone();
      v.project(camera);
      if (v.z < -1 || v.z > 1) return;
      const x = (v.x * 0.5 + 0.5) * rect.width;
      const y = (-v.y * 0.5 + 0.5) * rect.height;
      if (x < 40 || y < 40 || x > rect.width - 40 || y > rect.height - 40) return;

      const dx = x - rect.width / 2;
      const dy = y - rect.height / 2;
      candidates.push({
        x: Math.round(rect.left + x),
        y: Math.round(rect.top + y),
        name: obj.name,
        element_type: data.element_type,
        world: [world.x, world.y, world.z],
        d: dx * dx + dy * dy,
      });
    });

    candidates.sort((a, b) => a.d - b.d);
    const wanted = Math.min(o.index || 0, Math.max(candidates.length - 1, 0));
    return candidates[wanted] || null;
  }, opts);

/**
 * Wait until the camera arrives at an expected position.
 *
 * Deliberately NOT "wait until it stops": the camera manager keeps a slow idle
 * drift and a sub-centimetre breathing offset running, so it is never
 * completely still and a stillness poll would either spin or trip on the first
 * frame that has not rendered yet. Arrival is the property under test anyway.
 */
async function cameraReaches(expected, tolerance = 1.5, timeout = 40000) {
  const started = Date.now();
  let last = await cameraPosition();
  while (Date.now() - started < timeout) {
    last = await cameraPosition();
    if (expected.every((v, i) => near(last[i], v, tolerance))) {
      return { ok: true, position: last };
    }
    await page.waitForTimeout(250);
  }
  return { ok: false, position: last };
}

/** Wait for the camera manager to report that no move is running. */
async function moveFinished(timeout = 40000) {
  try {
    await page.waitForFunction(
      () => window.__viewer.cameraManager?.isMoving === false,
      null,
      { timeout },
    );
    return true;
  } catch {
    return false;
  }
}

/**
 * Wait until the damped explode easing in Structure's useFrame converges.
 *
 * `MathUtils.damp` advances once per rendered frame, so how long this takes in
 * wall-clock terms is a function of frame rate, not of the easing constant.
 * Poll the geometry until it stops moving rather than guessing a duration.
 */
async function explodeSettled(timeout = 40000) {
  const started = Date.now();
  const initial = (await modelMetrics()).extent[0];
  let previous = initial;
  let stable = 0;
  let moved = false;
  while (Date.now() - started < timeout) {
    await page.waitForTimeout(400);
    const current = (await modelMetrics()).extent[0];
    if (Math.abs(current - initial) > 0.05) moved = true;
    stable = Math.abs(current - previous) < 0.005 ? stable + 1 : 0;
    previous = current;
    // Stability alone is not arrival: the easing is started by a React effect
    // and driven by rendered frames, so the first samples after a click are
    // still the OLD value sitting perfectly still. Wait until something has
    // actually moved before believing the stillness.
    if (moved && stable >= 3) return true;
  }
  return false;
}

// ===========================================================================
console.log(`\nStructural viewer E2E against ${BASE}`);

// --- 1. Load ---------------------------------------------------------------
console.log('\n1. Model load');
await page.goto(BASE, { waitUntil: 'domcontentloaded' });

// SwiftShader parsing a Draco-compressed 2.8 MB GLB with 3137 nodes is the
// slowest thing in the suite by an order of magnitude.
await page.waitForFunction(
  () => window.__viewer?.store?.getState().ready,
  null,
  { timeout: 180000 },
);

check('loading overlay is gone', (await page.locator('.loading').count()) === 0);
check('dashboard rendered', await page.locator('.panel-left').isVisible());

const loaded = await modelMetrics();
check(
  'model has its full node count',
  loaded.meshes > 3000,
  `${loaded.meshes} meshes`,
);
check(
  'opens on the finished structure, not the parked state',
  loaded.meanScale > 0.9,
  `mean node scale ${loaded.meanScale.toFixed(4)}`,
);
check(
  'model spans the 28.8 x 18.0 m footprint',
  loaded.extent[0] > 20 && loaded.extent[2] > 12,
  `extent ${loaded.extent.map((v) => v.toFixed(1)).join(' x ')}`,
);

const timelineText = await page.locator('.timeline-time').textContent();
check('timeline manifest loaded', /\/ 18s/.test(timelineText), timelineText);
check(
  'phase marks come from timeline.json',
  (await page.locator('.phase-mark').count()) === 5,
);

// --- 2. Layers -------------------------------------------------------------
console.log('\n2. Layer visibility');
const LAYERS = [
  'Foundation',
  'Columns',
  'Beams',
  'Pipes',
  'Connections',
  'Accessories',
];
check(
  'six layer rows',
  (await page.locator('.layer-row').count()) === LAYERS.length,
);

for (const layer of LAYERS) {
  const row = page.locator('.layer-row', { hasText: layer }).first();
  await row.click();
  await page.waitForTimeout(150);
  const off = await layerVisible(layer);
  const aria = await row.getAttribute('aria-checked');
  check(`${layer}: hidden in the scene graph`, off === false, `visible=${off}`);
  check(`${layer}: aria-checked follows`, aria === 'false', `aria-checked=${aria}`);

  await row.click();
  await page.waitForTimeout(150);
  check(`${layer}: restored`, (await layerVisible(layer)) === true);
}

await page.getByRole('button', { name: 'Hide all' }).click();
await page.waitForTimeout(200);
const allHidden = await Promise.all(LAYERS.map(layerVisible));
check('Hide all hides every layer', allHidden.every((v) => v === false));

await page.getByRole('button', { name: 'Show all' }).click();
await page.waitForTimeout(200);
const allShown = await Promise.all(LAYERS.map(layerVisible));
check('Show all restores every layer', allShown.every((v) => v === true));

// --- 3. Selection and inspector -------------------------------------------
console.log('\n3. Selection and inspector');
const target = await pickPoint();
check('a pickable member was found', target !== null);

if (target) {
  await page.mouse.click(target.x, target.y);
  try {
    await page.waitForFunction(
      () => window.__viewer.store.getState().selected !== null,
      null,
      { timeout: 8000 },
    );
  } catch {
    /* reported by the next check */
  }
  const selected = (await state()).selected;
  check('selection populated', selected !== null);

  if (selected) {
    check('component has a name', !!selected.name, selected.name);
    check(
      'component has an element type',
      !!selected.element_type,
      selected.element_type,
    );
    check(
      'component has a material spec',
      !!selected.material_spec,
      selected.material_spec,
    );
    check(
      'length measured off the geometry',
      selected.length > 0.05,
      `${selected.length}`,
    );
    check('status derived from the timeline', !!selected.status, selected.status);

    const fields = await page.locator('.panel-right .field').count();
    check('inspector shows all nine fields', fields === 9, `${fields} fields`);

    const idValue = await page
      .locator('.panel-right .field', { hasText: 'Object ID' })
      .locator('.field-value')
      .textContent();
    check(
      'inspector object id matches the picked node',
      idValue.trim() === selected.name,
      `${idValue} vs ${selected.name}`,
    );

    await page
      .locator('.panel-right')
      .getByRole('button', { name: 'Clear' })
      .click();
    await page.waitForTimeout(200);
    check('Clear empties the inspector', (await state()).selected === null);
    check(
      'empty state shown',
      await page.locator('.panel-right .empty').isVisible(),
    );
  }
}

// --- 4. Camera shots -------------------------------------------------------
console.log('\n4. Camera shots');
const EXPECTED = {
  Hero: [58, 22, 46],
  Corner: [34, 7.0, 22],
  Joint: [4.2, 4.6, 3.4],
  Elevation: [14.4, 7.2, 120],
};
for (const [label, expected] of Object.entries(EXPECTED)) {
  const button = page
    .locator('.panel-left')
    .getByRole('button', { name: label, exact: true });
  await button.click();
  // Sample at the moment the move reports finished. Polling "eventually near"
  // is the wrong test here: the camera lands exactly on the shot and the idle
  // drift then walks it slowly away, so a late sample measures the drift
  // rather than the arrival.
  await page
    .waitForFunction(
      () => window.__viewer.cameraManager?.isMoving === true,
      null,
      { timeout: 15000 },
    )
    .catch(() => {});
  await moveFinished();
  // The tween completing and the frame that applies its final transform are
  // two different events, and under SwiftShader they can be a second apart.
  // 1.2 s covers that and still sits well inside the 3.5 s the manager waits
  // before the idle drift starts, so this measures arrival, not drift.
  await page.waitForTimeout(1200);
  const arrived = await cameraPosition();
  check(
    `${label}: button marked active`,
    (await button.getAttribute('data-active')) === 'true',
  );
  check(
    `${label}: camera reached the shot`,
    expected.every((v, i) => near(arrived[i], v, 1.5)),
    `${arrived.map((v) => v.toFixed(1))} vs ${expected}`,
  );
}

// The whole point of the polar spline is that a move arcs AROUND the building
// instead of taking the chord through it. Sample the path from the far
// elevation shot to the interior joint - the one transition whose straight
// line would pass clean through the frame - and check it keeps its distance.
console.log('\n4b. Path shape');
await page
  .locator('.panel-left')
  .getByRole('button', { name: 'Elevation', exact: true })
  .click();
await cameraReaches([14.4, 7.2, 120]);

const CENTRE = [14.4, 6, -9];
const radial = (p) => Math.hypot(p[0] - CENTRE[0], p[2] - CENTRE[2]);
await page
  .locator('.panel-left')
  .getByRole('button', { name: 'Joint', exact: true })
  .click();

// The move is started by a React effect, so it is not running the instant the
// click returns; sampling immediately would capture one frame and stop.
await page.waitForFunction(
  () => window.__viewer.cameraManager?.isMoving === true,
  null,
  { timeout: 15000 },
);
const samples = [];
for (let i = 0; i < 40; i += 1) {
  samples.push(await cameraPosition());
  await page.waitForTimeout(250);
  // Only allow an early exit once there is enough of a trace to judge: at one
  // or two frames a second a single `isMoving === false` reading proves
  // nothing about whether the move happened.
  if (
    samples.length >= 8 &&
    (await page.evaluate(
      () => window.__viewer.cameraManager?.isMoving === false,
    ))
  ) {
    break;
  }
}
check('transition samples were captured', samples.length >= 5, `${samples.length} samples`);

// Deviation from the straight line between the endpoints is the frame-rate
// independent way to tell an arc from a chord: consecutive-sample deltas are
// useless here, because at one or two frames a second a legitimate move
// covers tens of metres between samples.
const first = samples[0];
const last = samples[samples.length - 1];
const axis = [last[0] - first[0], last[1] - first[1], last[2] - first[2]];
const axisLength = Math.hypot(...axis) || 1;
const unit = axis.map((v) => v / axisLength);

let maxDeviation = 0;
for (const p of samples) {
  const rel = [p[0] - first[0], p[1] - first[1], p[2] - first[2]];
  const along = rel[0] * unit[0] + rel[1] * unit[1] + rel[2] * unit[2];
  const perpendicular = Math.hypot(
    rel[0] - unit[0] * along,
    rel[1] - unit[1] * along,
    rel[2] - unit[2] * along,
  );
  maxDeviation = Math.max(maxDeviation, perpendicular);
}
check(
  'the path arcs around the model instead of taking the chord',
  maxDeviation > 2,
  `max deviation from the straight line ${maxDeviation.toFixed(2)} m`,
);
check(
  'the path keeps its distance from the structure',
  Math.min(...samples.map(radial)) > 3,
  `closest radial approach ${Math.min(...samples.map(radial)).toFixed(1)} m`,
);

// --- 5. Explode ------------------------------------------------------------
console.log('\n5. Exploded view');
await page
  .locator('.panel-left')
  .getByRole('button', { name: 'Hero', exact: true })
  .click();
await cameraReaches([58, 22, 46]);
await moveFinished();
const compact = await modelMetrics();

const explodeButton = page.getByRole('button', { name: 'Explode View' });
await explodeButton.click();
await explodeSettled();
const exploded = await modelMetrics();
check(
  'explode separates the model',
  exploded.extent[0] > compact.extent[0] * 1.1,
  `${compact.extent[0].toFixed(1)} -> ${exploded.extent[0].toFixed(1)}`,
);
check(
  'explode button marked active',
  (await explodeButton.getAttribute('data-active')) === 'true',
);

await explodeButton.click();
await explodeSettled();
const recollapsed = await modelMetrics();
check(
  'explode reverses cleanly',
  near(recollapsed.extent[0], compact.extent[0], 0.5),
  `${recollapsed.extent[0].toFixed(2)} vs ${compact.extent[0].toFixed(2)}`,
);

// --- 6. Measurement tool ---------------------------------------------------
console.log('\n6. Measurement tool');
const measureButton = page.getByRole('button', { name: 'Measure', exact: true });
await measureButton.click();
await page.waitForTimeout(200);
check('measuring engaged', (await state()).measuring === true);
check(
  'hint shown',
  await page.locator('.hint', { hasText: 'Click two points' }).isVisible(),
);

const a = await pickPoint({ index: 0 });
const b = await pickPoint({ index: 8 });
check('two distinct measurement targets found', !!(a && b && a.name !== b.name));

if (a && b) {
  await page.mouse.click(a.x, a.y);
  await page.waitForTimeout(400);
  const first = (await state()).measurePoints;
  check(
    'first measurement point recorded',
    first.length === 1,
    `${first.length} points`,
  );

  await page.mouse.click(b.x, b.y);
  await page.waitForTimeout(500);
  const points = (await state()).measurePoints;
  check(
    'second measurement point recorded',
    points.length === 2,
    `${points.length} points`,
  );

  if (points.length === 2) {
    const label = await page.locator('.measure-label').first().textContent();
    check('distance label rendered', /\d/.test(label || ''), label);

    const dx = points[0].position[0] - points[1].position[0];
    const dy = points[0].position[1] - points[1].position[1];
    const dz = points[0].position[2] - points[1].position[2];
    const expected = Math.sqrt(dx * dx + dy * dy + dz * dz);
    const shown = parseFloat(String(label).replace(/[^\d.]/g, ''));
    check(
      'label matches the point separation',
      near(shown, expected, 0.06),
      `label ${shown} vs computed ${expected.toFixed(3)}`,
    );
  }

  check(
    'selection is not stolen while measuring',
    (await state()).selected === null,
  );

  const clearMeasure = page.getByRole('button', { name: 'Clear measurement' });
  check('Clear measurement offered', (await clearMeasure.count()) === 1);
  if ((await clearMeasure.count()) === 1) {
    await clearMeasure.click();
    await page.waitForTimeout(200);
    check(
      'Clear measurement empties the points',
      (await state()).measurePoints.length === 0,
    );
  }
}

await measureButton.click();
await page.waitForTimeout(200);
check('measuring disengaged', (await state()).measuring === false);

// --- 7. Quality presets ----------------------------------------------------
console.log('\n7. Quality presets');
for (const level of ['high', 'performance', 'balanced']) {
  const button = page.getByRole('button', { name: level, exact: true });
  await button.click();
  await page.waitForTimeout(600);
  check(`${level}: store updated`, (await state()).quality === level);
  check(
    `${level}: button marked active`,
    (await button.getAttribute('data-active')) === 'true',
  );
  check(`${level}: scene still rendering`, (await modelMetrics()).meshes > 3000);
}

// --- 8. Construction sequence ---------------------------------------------
console.log('\n8. Construction sequence');
const play = page.getByRole('button', { name: 'Construction Sequence' });
await play.click();
await page.waitForFunction(
  () => window.__viewer.store.getState().playback === 'playing',
  null,
  { timeout: 5000 },
);
check('playback started', (await state()).playback === 'playing');
check(
  'button becomes Pause',
  await page.getByRole('button', { name: 'Pause' }).isVisible(),
);

// Early in the clip most members are still parked at one-thousandth scale,
// so the mean node scale must be well below the finished model's. This is
// what proves the transforms are being written rather than only the progress
// number moving. Extent is deliberately not used: parked members sit below
// ground, which makes a half-built frame measure TALLER than a finished one.
// The rewind to frame zero is applied by the scene's own frame loop, one
// frame after the click. Waiting only for `progress > 0.12` would be
// satisfied instantly by the progress of 1 left over from the finished
// structure, and would measure the completed model.
// The threshold cannot be tight: the same frame that applies the rewind also
// advances the mixer by a full delta, and at 1 fps that is already 1/18th of
// the clip. Anything below the finished value proves the rewind happened.
await page.waitForFunction(
  () => window.__viewer.store.getState().progress < 0.5,
  null,
  { timeout: 30000 },
);
await page.waitForFunction(
  () => window.__viewer.store.getState().progress > 0.12,
  null,
  { timeout: 60000 },
);
const midBuild = await modelMetrics();
check(
  'partially built frame has members still parked',
  midBuild.meanScale < loaded.meanScale * 0.9,
  `mean node scale ${midBuild.meanScale.toFixed(3)} vs ${loaded.meanScale.toFixed(3)}`,
);

await page.getByRole('button', { name: 'Pause' }).click();
await page.waitForTimeout(700);
const pausedA = (await state()).progress;
await page.waitForTimeout(900);
const pausedB = (await state()).progress;
check(
  'pause freezes the clock',
  near(pausedA, pausedB, 0.001),
  `${pausedA} -> ${pausedB}`,
);
check('playback state is paused', (await state()).playback === 'paused');

await play.click();
// One rendered frame is what advances the mixer, and under SwiftShader that
// can take most of a second - poll for the advance instead of assuming one.
let resumed = pausedB;
try {
  await page.waitForFunction(
    (from) => window.__viewer.store.getState().progress > from,
    pausedB,
    { timeout: 20000 },
  );
  resumed = (await state()).progress;
} catch {
  /* reported by the check below */
}
check(
  'resume continues from where it paused',
  resumed > pausedB,
  `${pausedB} -> ${resumed}`,
);

await page.locator('.timeline').getByRole('button', { name: 'Reset' }).click();
await page.waitForTimeout(900);
const afterTimelineReset = (await state()).progress;
check(
  'reset returns to zero',
  afterTimelineReset < 0.02,
  `${afterTimelineReset}`,
);
const parked = await modelMetrics();
check(
  'reset parks the structure',
  parked.meanScale < 0.5,
  `mean node scale ${parked.meanScale.toFixed(4)}`,
);

// Scrub to the end: the finished structure must come back.
const track = page.locator('.track');
const box = await track.boundingBox();
await page.mouse.click(box.x + box.width * 0.985, box.y + box.height / 2);
await page.waitForTimeout(1000);
const scrubbed = await state();
check(
  'scrubbing moves the playhead',
  scrubbed.progress > 0.9,
  `${scrubbed.progress}`,
);
const rebuilt = await modelMetrics();
check(
  'scrubbing to the end rebuilds the structure',
  rebuilt.meanScale > 0.9,
  `mean node scale ${rebuilt.meanScale.toFixed(4)}`,
);

await page.mouse.click(box.x + box.width * 0.5, box.y + box.height / 2);
await page.waitForTimeout(800);
const half = (await state()).progress;
check('scrub lands where it was clicked', near(half, 0.5, 0.06), `${half}`);
const phaseText = await page.locator('.timeline-time').textContent();
check('active phase named at the halfway point', /·\s*\S/.test(phaseText), phaseText);
check(
  'active phase mark highlighted',
  (await page.locator('.phase-mark[data-active="true"]').count()) === 1,
);

// --- 9. Reset View ---------------------------------------------------------
console.log('\n9. Reset View');
const pick2 = await pickPoint();
if (pick2) {
  await page.mouse.click(pick2.x, pick2.y);
  await page.waitForTimeout(500);
}
await page.locator('.layer-row', { hasText: 'Pipes' }).first().click();
await explodeButton.click();
await page.waitForTimeout(500);

await page.getByRole('button', { name: 'Reset View' }).click();
const resetArrival = await cameraReaches([58, 22, 46]);
await page.waitForTimeout(1600);

const afterReset = await state();
check('reset clears the selection', afterReset.selected === null);
check(
  'reset restores every layer',
  Object.values(afterReset.layers).every(Boolean),
);
check('reset collapses the explode', afterReset.explodeFactor === 0);
check('reset returns to the hero shot', afterReset.shot === 'hero');
check(
  'reset moves the camera home',
  resetArrival.ok,
  `${resetArrival.position.map((v) => v.toFixed(1))}`,
);

const afterResetModel = await modelMetrics();
check(
  'reset leaves the structure standing, not parked',
  afterResetModel.meanScale > 0.9,
  `mean node scale ${afterResetModel.meanScale.toFixed(4)}`,
);

// --- 10. Cinematic tour ----------------------------------------------------
console.log('\n10. Cinematic tour');
const tourButton = page.getByRole('button', { name: 'Cinematic Tour' });
const beforeTour = await cameraPosition();
await tourButton.click();
await page.waitForTimeout(400);

check('tour engaged', (await page.evaluate(() =>
  window.__viewer.store.getState().touring)) === true);
check(
  'orbit input is taken away while the tour runs',
  await page.evaluate(() => window.__viewer.cameraManager.isCinematic === true),
);

// The caption names the leg on screen, which is also proof the sequence is
// stepping rather than running one long move.
await page.waitForFunction(
  () => window.__viewer.store.getState().tourShot !== null,
  null,
  { timeout: 20000 },
);
const firstLeg = await page.evaluate(
  () => window.__viewer.store.getState().tourShot,
);
check('first leg is the hero introduction', firstLeg === 'Hero introduction', firstLeg);

// The opening leg accelerates slowly on purpose - `power2.inOut` over eight
// seconds has barely left the mark at three - so give it time to be moving
// before asking whether it moved.
let duringTour = beforeTour;
const travelStarted = Date.now();
while (Date.now() - travelStarted < 30000) {
  await page.waitForTimeout(500);
  duringTour = await cameraPosition();
  const travelled = Math.hypot(
    duringTour[0] - beforeTour[0],
    duringTour[1] - beforeTour[1],
    duringTour[2] - beforeTour[2],
  );
  if (travelled > 4) break;
}
check(
  'the tour actually flies the camera',
  Math.hypot(
    duringTour[0] - beforeTour[0],
    duringTour[1] - beforeTour[1],
    duringTour[2] - beforeTour[2],
  ) > 4,
  `${beforeTour.map((v) => v.toFixed(1))} -> ${duringTour.map((v) => v.toFixed(1))}`,
);

// Handover is where a jump normally shows. The property that matters is not
// the raw position delta - under SwiftShader the camera legitimately travels
// several metres in the last frame before the click lands, which no assertion
// can separate from a jump. What must hold is that OrbitControls adopts the
// view the animation ended on: its target has to sit on the camera's own
// forward axis, or its first update swings the view to look somewhere else.
await page.getByRole('button', { name: 'Stop Tour' }).click();
await page.waitForTimeout(900);
check(
  'tour stopped',
  (await page.evaluate(() => window.__viewer.store.getState().touring)) ===
    false,
);
check(
  'orbit control is handed back',
  await page.evaluate(
    () => window.__viewer.cameraManager.isCinematic === false,
  ),
);

const handover = await page.evaluate(() => {
  const { camera, cameraManager } = window.__viewer;
  const controls = cameraManager.controls;
  const forward = camera.position.clone();
  forward.set(0, 0, -1).applyQuaternion(camera.quaternion).normalize();
  const toTarget = controls.target.clone().sub(camera.position);
  const distance = toTarget.length();
  return {
    distance,
    // Degrees between where the camera looks and where the controls think it
    // looks. Anything but ~0 is a visible snap the moment input goes live.
    error: (Math.acos(
      Math.min(1, Math.max(-1, forward.dot(toTarget.normalize()))),
    ) * 180) / Math.PI,
    enabled: controls.enabled,
  };
});
check('controls are live again', handover.enabled === true);
check(
  'controls adopt the camera view without a snap',
  handover.error < 2,
  `${handover.error.toFixed(2)} degrees off, target ${handover.distance.toFixed(1)} m ahead`,
);

// --- 11. Console -----------------------------------------------------------
console.log('\n11. Console');
const unique = [...new Set(consoleErrors)];
check(
  'no console errors over the whole run',
  unique.length === 0,
  unique
    .map((e) => `${e} (x${consoleErrors.filter((x) => x === e).length})`)
    .join(' | '),
);

await browser.close();

console.log(`\n${pass} passed, ${failures.length} failed`);
if (failures.length) {
  console.log('\nFailures:');
  for (const failure of failures) console.log(`  - ${failure}`);
  process.exit(1);
}
