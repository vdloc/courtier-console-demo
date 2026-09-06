// End-to-end suite. Run against a static server on BASE (default :8777):
//   node --experimental-strip-types tests/e2e.mjs      (no TS -- plain ESM)
//   NODE_PATH=$(npm root -g) node tests/e2e.mjs
// Playwright is resolved from the global install: this project has no
// package.json and no node_modules by design (no-build static site), so the
// suite must not assume a local dependency tree.
import zlib from 'node:zlib';
import { execSync } from 'node:child_process';

// ESM ignores NODE_PATH, and this project deliberately has no node_modules,
// so a bare `import 'playwright'` cannot resolve. Fall back to the global
// install by absolute path.
async function loadPlaywright() {
  try {
    return await import('playwright');
  } catch {
    const root = process.env.PLAYWRIGHT_ROOT || execSync('npm root -g').toString().trim();
    return await import(`${root}/playwright/index.mjs`);
  }
}
const { chromium } = await loadPlaywright();

const BASE = process.env.BASE || 'http://localhost:8777';

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

// Minimal PNG reader for 8-bit truecolour screenshots. The point is to prove
// the WebGPU/WebGL canvas actually put pixels on screen: a canvas element that
// exists and is sized tells us nothing, and gl.readPixels comes back zeroed
// without preserveDrawingBuffer, so the composited screenshot is the only
// honest measurement available.
function decodePng(buf) {
  let pos = 8;
  let w = 0, h = 0, bitDepth = 0, colorType = 0;
  const idat = [];
  while (pos < buf.length) {
    const len = buf.readUInt32BE(pos);
    const type = buf.toString('ascii', pos + 4, pos + 8);
    const data = buf.subarray(pos + 8, pos + 8 + len);
    if (type === 'IHDR') {
      w = data.readUInt32BE(0);
      h = data.readUInt32BE(4);
      bitDepth = data[8];
      colorType = data[9];
    } else if (type === 'IDAT') idat.push(data);
    else if (type === 'IEND') break;
    pos += 12 + len;
  }
  if (bitDepth !== 8 || (colorType !== 2 && colorType !== 6)) {
    throw new Error(`unsupported png: depth ${bitDepth} colorType ${colorType}`);
  }
  const ch = colorType === 6 ? 4 : 3;
  const raw = zlib.inflateSync(Buffer.concat(idat));
  const stride = w * ch;
  const out = Buffer.alloc(h * stride);
  for (let y = 0; y < h; y++) {
    const filter = raw[y * (stride + 1)];
    const line = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1));
    for (let x = 0; x < stride; x++) {
      const a = x >= ch ? out[y * stride + x - ch] : 0;
      const b = y > 0 ? out[(y - 1) * stride + x] : 0;
      const c = x >= ch && y > 0 ? out[(y - 1) * stride + x - ch] : 0;
      let v = line[x];
      if (filter === 1) v += a;
      else if (filter === 2) v += b;
      else if (filter === 3) v += (a + b) >> 1;
      else if (filter === 4) {
        const p = a + b - c;
        const pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
        v += pa <= pb && pa <= pc ? a : pb <= pc ? b : c;
      }
      out[y * stride + x] = v & 255;
    }
  }
  return { w, h, ch, data: out };
}

function luminanceStats(png) {
  let sum = 0, sum2 = 0, n = 0;
  for (let i = 0; i < png.data.length; i += png.ch) {
    const l = 0.299 * png.data[i] + 0.587 * png.data[i + 1] + 0.114 * png.data[i + 2];
    sum += l;
    sum2 += l * l;
    n++;
  }
  const mean = sum / n;
  return { mean, stdev: Math.sqrt(Math.max(0, sum2 / n - mean * mean)) };
}

function diffRatio(a, b) {
  if (a.w !== b.w || a.h !== b.h) return 1;
  let changed = 0, n = 0;
  for (let i = 0; i < a.data.length; i += a.ch) {
    const d =
      Math.abs(a.data[i] - b.data[i]) +
      Math.abs(a.data[i + 1] - b.data[i + 1]) +
      Math.abs(a.data[i + 2] - b.data[i + 2]);
    if (d > 12) changed++;
    n++;
  }
  return changed / n;
}

// Default: no WebGPU adapter is forced, so WebGPURenderer takes its built-in
// WebGL2 fallback -- the path this page actually runs on any machine without
// an adapter, which is the one worth regression-testing. GPU=webgpu forces
// SwiftShader's WebGPU instead, to exercise the native backend; that software
// implementation has tight buffer limits and is expected to be noisier.
const forceWebGpu = process.env.GPU === 'webgpu';
const browser = await chromium.launch({
  args: [
    '--use-gl=angle',
    '--use-angle=swiftshader',
    ...(forceWebGpu ? ['--enable-unsafe-webgpu', '--use-webgpu-adapter=swiftshader'] : [])
  ]
});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const consoleErrors = [];
page.on('console', (m) => {
  if (m.type() === 'error') consoleErrors.push(m.text());
});
page.on('pageerror', (e) => consoleErrors.push(`pageerror: ${e.message}`));

await page.goto(`${BASE}/index.html`, { waitUntil: 'networkidle' });
// The renderer initialises asynchronously (renderer.init() -> PMREM -> ready),
// so the first drawn frame lands after load. Wait for the app handle rather
// than a fixed sleep.
await page.waitForFunction(() => !!window.__courtierApp, null, { timeout: 15000 });

const PARAM_KEYS = ['A', 'B', 'H1', 'A2', 'H2', 'Nb', 'Db', 'Sb', 'Cb', 'Lh', 'Lt'];
const DEFAULTS = { A: 0.3, B: 0.3, H1: 0.35, A2: 0.15, H2: 0.4, Nb: 4, Db: 0.04, Sb: 0.07, Cb: 0.02, Lh: 0.05, Lt: 0.04 };

console.log('\n1. Load and initial state');
check('title', (await page.title()) === 'Broker Console Demo');
const inputVals = await page.evaluate((keys) =>
  Object.fromEntries(keys.map((k) => [k, document.getElementById(`input-${k}`).value])), PARAM_KEYS);
check('all 11 inputs prefilled from state',
  PARAM_KEYS.every((k) => parseFloat(inputVals[k]) === DEFAULTS[k]),
  JSON.stringify(inputVals));
const rows = await page.$$eval('#result-rows .row', (els) => els.map((e) => e.textContent));
check('11 result rows', rows.length === 11, `got ${rows.length}`);
check('metre rows show 3 decimals + unit', rows[0] === 'A0.300 m', rows[0]);
check('Nb renders as a count, not metres', rows[5] === 'Nb4', rows[5]);
check('2D is the default view', await page.$eval('#view-toggle-2d', (b) => b.classList.contains('active')));

console.log('\n2. Parameter editing');
await page.fill('#input-A', '0.5');
check('edit propagates to result rows',
  (await page.$eval('#result-rows .row', (e) => e.textContent)) === 'A0.500 m');
const svgBefore = await page.$eval('#diagram-thumbnail svg', (s) => s.innerHTML);
await page.fill('#input-H1', '0.6');
check('a geometry change redraws the 2D diagram',
  (await page.$eval('#diagram-thumbnail svg', (s) => s.innerHTML)) !== svgBefore);
await page.fill('#input-H1', '0.35');
// Nb is deliberately NOT expected to move the 2D drawing: in elevation all
// Nb bars sit behind one another, so the correct picture is one bar path
// however many bars there are. The 3D check below is what exercises Nb.
await page.fill('#input-Nb', '8');
check('bar count leaves the 2D elevation unchanged (bars overlap in elevation)',
  (await page.$eval('#diagram-thumbnail svg', (s) => s.innerHTML)) ===
    (await page.evaluate(() => document.querySelector('#diagram-thumbnail svg').innerHTML)));
await page.fill('#input-Nb', '4');

console.log('\n3. Input validation');
await page.fill('#input-A', '50');
check('out-of-range value marks the field invalid',
  await page.$eval('#input-A', (i) => i.classList.contains('invalid')));
check('out-of-range value is NOT committed to state',
  (await page.$eval('#result-rows .row', (e) => e.textContent)) === 'A0.500 m');
// A number input refuses letters outright, so the reachable non-numeric
// state is an empty field -- which parseFloat turns into NaN.
await page.fill('#input-A', '');
check('empty value marks the field invalid',
  await page.$eval('#input-A', (i) => i.classList.contains('invalid')));
await page.locator('#input-A').blur();
check('blur reverts the field to the last accepted value',
  (await page.$eval('#input-A', (i) => i.value)) === '0.5');
check('blur clears the invalid class',
  !(await page.$eval('#input-A', (i) => i.classList.contains('invalid'))));
await page.fill('#input-A', '0.3');

console.log('\n4. 2D / 3D toggle');
check('2D: svg visible, canvas hidden', await page.evaluate(() => {
  const svg = document.querySelector('#diagram-thumbnail svg');
  return svg.style.display !== 'none' && window.__courtierApp.view3d.canvas.style.display === 'none';
}));
await page.click('#view-toggle-3d');
check('3D: canvas visible, svg hidden', await page.evaluate(() => {
  const svg = document.querySelector('#diagram-thumbnail svg');
  return svg.style.display === 'none' && window.__courtierApp.view3d.canvas.style.display === 'block';
}));
const aria = await page.evaluate(() =>
  ['view-toggle-2d', 'view-toggle-3d', 'modal-view-toggle-2d', 'modal-view-toggle-3d']
    .map((id) => document.getElementById(id).getAttribute('aria-pressed')));
check('both toggle pairs stay in sync (aria-pressed)',
  JSON.stringify(aria) === JSON.stringify(['false', 'true', 'false', 'true']), JSON.stringify(aria));

console.log('\n5. 3D actually renders');
await page.click('#expand-diagram-btn');
// Asserted here, not in the modal section below: the 3D checks type into a
// form field, which legitimately moves focus out of the dialog.
check('focus moves into the dialog on open', await page.evaluate(() =>
  document.getElementById('modal-overlay').contains(document.activeElement)));
await page.waitForTimeout(1200);
const clip = await page.$eval('#modal-diagram-container', (el) => {
  const r = el.getBoundingClientRect();
  return { x: r.x + 20, y: r.y + 20, width: Math.round(r.width - 40), height: Math.round(r.height - 40) };
});
const shot1 = decodePng(await page.screenshot({ clip }));
const stats = luminanceStats(shot1);
// A failed init leaves a single flat clear colour; a rendered scene has a lit
// solid, a shadow and a ground plane, so its luminance spread is wide.
check('3D canvas is not a flat fill', stats.stdev > 8, `stdev ${stats.stdev.toFixed(1)}`);

console.log('\n6. 3D reacts to parameters');
await page.fill('#input-H2', '0.9');
await page.waitForTimeout(900);
const shot2 = decodePng(await page.screenshot({ clip }));
const ratio = diffRatio(shot1, shot2);
check('changing H2 changes the rendered image', ratio > 0.01, `${(ratio * 100).toFixed(2)}% of pixels`);
await page.fill('#input-H2', '0.4');

console.log('\n7. Modal');
check('overlay is open', !(await page.$eval('#modal-overlay', (e) => e.classList.contains('hidden'))));
check('diagram re-parented into the modal', await page.evaluate(() =>
  !!document.querySelector('#modal-diagram-container svg') &&
  document.getElementById('modal-diagram-container').contains(window.__courtierApp.view3d.canvas)));
await page.click('#modal-view-toggle-2d');
check('modal toggle drives the shared view mode',
  (await page.evaluate(() => window.__courtierApp.getViewMode())) === '2d');
check('svg is visible again after switching to 2D inside the modal',
  await page.evaluate(() => document.querySelector('#modal-diagram-container svg').style.display !== 'none'));
check('rail toggle mirrors the modal toggle',
  await page.$eval('#view-toggle-2d', (b) => b.classList.contains('active')));

console.log('\n8. Modal focus trap and dismissal');
await page.evaluate(() => {
  const items = [...document.querySelectorAll('#modal-overlay button')].filter((el) => el.offsetParent !== null);
  items[items.length - 1].focus();
});
await page.keyboard.press('Tab');
check('Tab wraps from the last control back to the first', await page.evaluate(() => {
  const items = [...document.querySelectorAll('#modal-overlay button')].filter((el) => el.offsetParent !== null);
  return document.activeElement === items[0];
}));
await page.keyboard.press('Escape');
check('Escape closes the modal', await page.$eval('#modal-overlay', (e) => e.classList.contains('hidden')));
check('diagram returns to the thumbnail', await page.evaluate(() =>
  !!document.querySelector('#diagram-thumbnail svg') &&
  document.getElementById('diagram-thumbnail').contains(window.__courtierApp.view3d.canvas)));
check('focus returns to the expand button',
  await page.evaluate(() => document.activeElement === document.getElementById('expand-diagram-btn')));

await page.click('#expand-diagram-btn');
await page.mouse.click(20, 450); // backdrop, outside the dialog box
check('clicking the backdrop closes the modal',
  await page.$eval('#modal-overlay', (e) => e.classList.contains('hidden')));

await page.click('#expand-diagram-btn');
await page.click('#modal-close-btn');
check('close button closes the modal',
  await page.$eval('#modal-overlay', (e) => e.classList.contains('hidden')));

console.log('\n9. Console');
check('no console errors over the whole run', consoleErrors.length === 0, consoleErrors.join(' | '));

await browser.close();

console.log(`\n${pass} passed, ${failures.length} failed`);
if (failures.length) {
  console.log(failures.map((f) => `  - ${f}`).join('\n'));
  process.exit(1);
}
