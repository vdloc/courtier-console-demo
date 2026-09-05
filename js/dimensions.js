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
