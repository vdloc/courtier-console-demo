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
