import assert from 'node:assert/strict';
import { test } from 'node:test';
import { getParams, setParam, subscribe } from '../js/state.js';

test('getParams returns the documented defaults', () => {
  const p = getParams();
  assert.equal(p.A, 0.3);
  assert.equal(p.H1, 0.35);
  assert.equal(p.A2, 0.15);
  assert.equal(p.Nb, 4);
  assert.equal(p.Db, 0.04);
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
