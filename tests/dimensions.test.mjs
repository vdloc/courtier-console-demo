import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  dimensionRecords,
  visualScale,
  elevationShapes,
  rebarProfile,
  rebarDepths,
  rebarRadius,
  sceneBounds
} from '../js/dimensions.js';

// The corbel at its default configuration.
const sampleParams = {
  A: 0.3, B: 0.3,
  H1: 0.35, A2: 0.15, H2: 0.4,
  Db: 0.04, Nb: 4, Sb: 0.07,
  Cb: 0.02, Lh: 0.05, Lt: 0.04
};

// Derived values here are sums and differences of decimal fractions, which
// are not exactly representable in binary floating point (0.35 - 0.02 is
// 0.32999999999999996). Comparing to a tolerance is correct; asserting
// exact equality would make these tests fail on arithmetic that is right.
const EPS = 1e-9;
function approx(actual, expected, msg) {
  assert.ok(
    Math.abs(actual - expected) < EPS,
    `${msg}: expected ~${expected}, got ${actual}`
  );
}

function getRecord(id) {
  const rec = dimensionRecords.find((r) => r.id === id);
  assert.ok(rec, `expected a dimension record with id "${id}"`);
  return rec;
}

function assertPoint(actual, expected, msg) {
  approx(actual.x, expected.x, `${msg}: x`);
  approx(actual.y, expected.y, `${msg}: y`);
  approx(actual.z, expected.z, `${msg}: z`);
}

// --- record contract ---------------------------------------------------

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
  // This is what lets this module be imported into bare Node with no
  // three.js dependency, which is why it is testable at all.
  const p = getRecord('H1').from(sampleParams);
  assert.equal(typeof p.x, 'number');
  assert.equal(typeof p.y, 'number');
  assert.equal(typeof p.z, 'number');
  assert.equal(p.constructor, Object);
});

test('label reflects the live param value', () => {
  const rec = getRecord('H1');
  assert.equal(rec.label(sampleParams), 'H1 = 0.35');
  assert.equal(rec.label({ ...sampleParams, H1: 0.55 }), 'H1 = 0.55');
});

test('visualScale clamps thin members but leaves the label value untouched', () => {
  assert.equal(visualScale('Cb', 0.02), 0.06);
  assert.equal(visualScale('Db', 0.04), 0.06);
  assert.equal(visualScale('Lt', 0.04), 0.06);
  assert.equal(visualScale('Cb', 0.09), 0.09); // already above the floor
  assert.equal(visualScale('A', 0.3), 0.3); // not a thin member, unchanged
  // The label is built from the raw param, never from the clamped value.
  assert.equal(getRecord('Db').label(sampleParams), 'Db = 0.040');
});

// --- the object --------------------------------------------------------

test('elevationShapes: base block spans the full footprint', () => {
  const base = elevationShapes(sampleParams).find((s) => s.id === 'base');
  approx(base.x, 0, 'base x');
  approx(base.y, 0, 'base y');
  approx(base.w, 0.3, 'base w');
  approx(base.h, 0.35, 'base h');
  approx(base.depth, 0.3, 'base depth');
});

test('elevationShapes: raised block sits on the BACK of the base, on top of it', () => {
  // A corbel, not a plinth: the raised mass is flush with the +X end and
  // starts where the base stops. Getting this the wrong way round would
  // silently mirror the object.
  const raised = elevationShapes(sampleParams).find((s) => s.id === 'raised');
  approx(raised.x, 0.15, 'raised x');
  approx(raised.x + raised.w, sampleParams.A, 'raised right edge flush with A');
  approx(raised.y, sampleParams.H1, 'raised sits on the base top');
  approx(raised.h, 0.4, 'raised h');
});

test('rebarProfile: five control points tracing anchor -> run -> leg -> hook', () => {
  const pts = rebarProfile(sampleParams);
  assert.equal(pts.length, 5);
  assertPoint({ ...pts[0], z: 0 }, { x: 0.15, y: 0.39, z: 0 }, 'anchor into raised block');
  assertPoint({ ...pts[1], z: 0 }, { x: 0.15, y: 0.33, z: 0 }, 'top of the run');
  assertPoint({ ...pts[2], z: 0 }, { x: 0.02, y: 0.33, z: 0 }, 'front end of the run');
  assertPoint({ ...pts[3], z: 0 }, { x: 0.02, y: -0.05, z: 0 }, 'bottom of the leg');
  assertPoint({ ...pts[4], z: 0 }, { x: 0.06, y: -0.05, z: 0 }, 'hook tail');
});

test('rebarProfile: the top run sits one cover depth below the base surface', () => {
  const pts = rebarProfile({ ...sampleParams, Cb: 0.05 });
  approx(pts[1].y, 0.3, 'run height follows the cover');
  approx(pts[2].x, 0.05, 'leg position follows the cover');
});

test('rebarProfile: the hook reaches BELOW zero', () => {
  // The whole reason sceneBounds() exists. If this ever stops being true,
  // the renderers can go back to assuming the drawing starts at y = 0.
  const pts = rebarProfile(sampleParams);
  assert.ok(pts[3].y < 0, 'leg bottom must be below the base underside');
  assert.ok(pts[4].y < 0, 'hook tail must be below the base underside');
});

test('rebarDepths: Nb bars at Sb pitch, starting one cover plus one radius in', () => {
  const d = rebarDepths(sampleParams);
  assert.equal(d.length, 4);
  approx(d[0], 0.04, 'first bar');
  approx(d[1], 0.11, 'second bar');
  approx(d[2], 0.18, 'third bar');
  approx(d[3], 0.25, 'fourth bar');
  // Every bar must still be inside the block's depth.
  for (const z of d) assert.ok(z > 0 && z < sampleParams.B, `bar at ${z} inside B`);
});

test('rebarDepths: Nb is a count, so it is rounded and never negative', () => {
  assert.equal(rebarDepths({ ...sampleParams, Nb: 0 }).length, 0);
  assert.equal(rebarDepths({ ...sampleParams, Nb: 2.4 }).length, 2);
  assert.equal(rebarDepths({ ...sampleParams, Nb: 2.6 }).length, 3);
  assert.equal(rebarDepths({ ...sampleParams, Nb: -5 }).length, 0);
});

test('rebarRadius is half the diameter', () => {
  approx(rebarRadius(sampleParams), 0.02, 'radius');
});

test('sceneBounds covers the hook below y=0, not just the concrete', () => {
  // Sizing a viewport from elevationShapes() alone clips the hooks. This is
  // the regression guard for exactly that.
  const b = sceneBounds(sampleParams);
  approx(b.minY, -0.07, 'minY includes the hook and the bar radius');
  approx(b.maxY, 0.75, 'maxY is the top of the raised block');
  approx(b.minX, 0, 'minX');
  approx(b.maxX, 0.3, 'maxX');
  assert.ok(b.minY < 0, 'bounds must extend below zero');
});

test('sceneBounds tracks the params rather than being fixed', () => {
  const b = sceneBounds({ ...sampleParams, Lh: 0.2, H2: 1.0 });
  approx(b.minY, -0.22, 'deeper hook lowers minY');
  approx(b.maxY, 1.35, 'taller back wall raises maxY');
});

// --- annotation geometry -----------------------------------------------
// offsetDir is checked for sign as well as position: a flipped side puts
// the dimension line through the object, which is the bug class these
// records exist to prevent.

test('A: overall width along the base', () => {
  const rec = getRecord('A');
  assertPoint(rec.from(sampleParams), { x: 0, y: 0, z: 0 }, 'A from');
  assertPoint(rec.to(sampleParams), { x: 0.3, y: 0, z: 0 }, 'A to');
  assert.equal(rec.offsetDir.y, -1, 'A sits below the object');
});

test('B: runs along Z, degenerate in elevation', () => {
  const rec = getRecord('B');
  const from = rec.from(sampleParams);
  const to = rec.to(sampleParams);
  approx(to.z - from.z, 0.3, 'B length is along z');
  approx(to.x - from.x, 0, 'B has no x extent');
  approx(to.y - from.y, 0, 'B has no y extent');
});

test('H1: base height, from the ground up', () => {
  const rec = getRecord('H1');
  assertPoint(rec.from(sampleParams), { x: 0, y: 0, z: 0 }, 'H1 from');
  assertPoint(rec.to(sampleParams), { x: 0, y: 0.35, z: 0 }, 'H1 to');
  assert.equal(rec.offsetDir.x, -1, 'H1 sits to the left');
});

test('H2: raised block height, stacked on H1 at the back face', () => {
  const rec = getRecord('H2');
  assertPoint(rec.from(sampleParams), { x: 0.3, y: 0.35, z: 0 }, 'H2 from');
  assertPoint(rec.to(sampleParams), { x: 0.3, y: 0.75, z: 0 }, 'H2 to');
  assert.equal(rec.offsetDir.x, 1, 'H2 sits to the right');
});

test('A2: raised block width, measured back from the +X end', () => {
  const rec = getRecord('A2');
  assertPoint(rec.from(sampleParams), { x: 0.15, y: 0.75, z: 0 }, 'A2 from');
  assertPoint(rec.to(sampleParams), { x: 0.3, y: 0.75, z: 0 }, 'A2 to');
});

test('Lh: hook depth measured downward from the base underside', () => {
  const rec = getRecord('Lh');
  const from = rec.from(sampleParams);
  const to = rec.to(sampleParams);
  approx(from.y, 0, 'Lh starts at the underside');
  approx(to.y, -0.05, 'Lh ends below zero');
  assert.ok(to.y < from.y, 'Lh must measure downward');
});

test('thin records use the clamped length for geometry', () => {
  // Cb is 0.02 but the floor is 0.06: the drawn extent is the clamped one
  // so the annotation stays visible, while the label still says 0.020.
  const rec = getRecord('Cb');
  const len = rec.to(sampleParams).x - rec.from(sampleParams).x;
  approx(len, 0.06, 'Cb drawn at the visual floor');
  assert.equal(rec.label(sampleParams), 'Cb = 0.020');
});

test('records track params rather than baking the defaults', () => {
  const wide = { ...sampleParams, A: 0.9, H1: 0.8 };
  approx(getRecord('A').to(wide).x, 0.9, 'A follows the param');
  approx(getRecord('H1').to(wide).y, 0.8, 'H1 follows the param');
  approx(getRecord('H2').from(wide).y, 0.8, 'H2 starts at the new H1');
});
