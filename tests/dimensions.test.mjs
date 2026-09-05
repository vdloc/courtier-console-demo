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

// --- Numeric geometry checks for every record, derived from the stated
// coordinate convention: X = width (A axis), Y = height, Z = depth (B axis).
// The block stacks H1, then H2, then Hv, then Ec, then Fee, each continuing
// up +Y from the origin. Horizontal-offset records (Ep, PhiM, Uh, Ub) extend
// in +X from the footprint edge at x = A, using the visualScale-clamped
// length. offsetDir is checked for sign since a flipped side is exactly the
// bug class this guards against.

function getRecord(id) {
  const rec = dimensionRecords.find((r) => r.id === id);
  assert.ok(rec, `expected a dimension record with id "${id}"`);
  return rec;
}

function assertPoint(actual, expected, msg) {
  assert.equal(actual.x, expected.x, `${msg}: x`);
  assert.equal(actual.y, expected.y, `${msg}: y`);
  assert.equal(actual.z, expected.z, `${msg}: z`);
}

test('A: full width along X at the base', () => {
  const rec = getRecord('A');
  assertPoint(rec.from(sampleParams), { x: 0, y: 0, z: 0 }, 'A.from');
  assertPoint(rec.to(sampleParams), { x: 0.3, y: 0, z: 0 }, 'A.to');
  assert.equal(rec.offsetDir.x, 0);
  assert.equal(rec.offsetDir.y, -1); // drawn below the block
  assert.equal(rec.offsetDir.z, 0);
});

test('B: full depth along Z at the base', () => {
  const rec = getRecord('B');
  assertPoint(rec.from(sampleParams), { x: 0, y: 0, z: 0 }, 'B.from');
  assertPoint(rec.to(sampleParams), { x: 0, y: 0, z: 0.3 }, 'B.to');
  assert.equal(rec.offsetDir.x, -1); // drawn to the left of the block
  assert.equal(rec.offsetDir.y, 0);
  assert.equal(rec.offsetDir.z, 0);
});

test('H2: stacks on top of H1', () => {
  const rec = getRecord('H2');
  assertPoint(rec.from(sampleParams), { x: 0, y: 0.4, z: 0 }, 'H2.from'); // H1
  assertPoint(rec.to(sampleParams), { x: 0, y: 0.75, z: 0 }, 'H2.to'); // H1+H2
  assert.equal(rec.offsetDir.x, -1);
  assert.equal(rec.offsetDir.y, 0);
});

test('Hv: stacks on top of H1+H2', () => {
  const rec = getRecord('Hv');
  assertPoint(rec.from(sampleParams), { x: 0, y: 0.75, z: 0 }, 'Hv.from'); // H1+H2
  assertPoint(rec.to(sampleParams), { x: 0, y: 1.15, z: 0 }, 'Hv.to'); // H1+H2+Hv
  assert.equal(rec.offsetDir.x, 1); // drawn on the opposite side from the others
  assert.equal(rec.offsetDir.y, 0);
});

test('Ec: stacks on top of H1+H2+Hv', () => {
  const rec = getRecord('Ec');
  const { H1, H2, Hv, Ec } = sampleParams;
  assertPoint(rec.from(sampleParams), { x: 0, y: H1 + H2 + Hv, z: 0 }, 'Ec.from');
  assertPoint(rec.to(sampleParams), { x: 0, y: H1 + H2 + Hv + Ec, z: 0 }, 'Ec.to');
  assert.equal(rec.offsetDir.x, -1);
  assert.equal(rec.offsetDir.y, 0);
});

test('Fee: stacks on top of H1+H2+Hv+Ec', () => {
  const rec = getRecord('Fee');
  const { H1, H2, Hv, Ec, Fee } = sampleParams;
  assertPoint(rec.from(sampleParams), { x: 0, y: H1 + H2 + Hv + Ec, z: 0 }, 'Fee.from');
  assertPoint(rec.to(sampleParams), { x: 0, y: H1 + H2 + Hv + Ec + Fee, z: 0 }, 'Fee.to');
  assert.equal(rec.offsetDir.x, -1);
  assert.equal(rec.offsetDir.y, 0);
});

test('Ep: horizontal offset at height H1, clamped by visualScale', () => {
  const rec = getRecord('Ep');
  assertPoint(rec.from(sampleParams), { x: 0.3, y: 0.4, z: 0 }, 'Ep.from'); // A, H1
  // Ep=0.03 is below the 0.06 visual floor, so the drawn length is clamped.
  assertPoint(rec.to(sampleParams), { x: 0.36, y: 0.4, z: 0 }, 'Ep.to');
  assert.equal(rec.offsetDir.x, 0);
  assert.equal(rec.offsetDir.y, 1);
});

test('PhiM: horizontal offset at height H1+H2, above visual floor unchanged', () => {
  const rec = getRecord('PhiM');
  assertPoint(rec.from(sampleParams), { x: 0.3, y: 0.75, z: 0 }, 'PhiM.from'); // A, H1+H2
  // PhiM=0.1 is already above the 0.06 floor, so the drawn length is unclamped.
  assertPoint(rec.to(sampleParams), { x: 0.4, y: 0.75, z: 0 }, 'PhiM.to');
  assert.equal(rec.offsetDir.x, 0);
  assert.equal(rec.offsetDir.y, 1);
});

test('Uh: horizontal offset at height H1+H2+Hv, clamped by visualScale', () => {
  const rec = getRecord('Uh');
  assertPoint(rec.from(sampleParams), { x: 0.3, y: 1.15, z: 0 }, 'Uh.from'); // A, H1+H2+Hv
  // Uh=0.04 is below the 0.06 visual floor, so the drawn length is clamped.
  assertPoint(rec.to(sampleParams), { x: 0.36, y: 1.15, z: 0 }, 'Uh.to');
  assert.equal(rec.offsetDir.x, 0);
  assert.equal(rec.offsetDir.y, 1);
});

test('Ub: horizontal offset at the base, clamped by visualScale', () => {
  const rec = getRecord('Ub');
  assertPoint(rec.from(sampleParams), { x: 0.3, y: 0, z: 0 }, 'Ub.from'); // A, base
  // Ub=0.04 is below the 0.06 visual floor, so the drawn length is clamped.
  assertPoint(rec.to(sampleParams), { x: 0.36, y: 0, z: 0 }, 'Ub.to');
  assert.equal(rec.offsetDir.x, 0);
  assert.equal(rec.offsetDir.y, -1); // drawn below the block, like A and Ub's base
});
