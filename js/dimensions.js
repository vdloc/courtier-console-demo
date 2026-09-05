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

// The elevation object itself, as plain rectangles in the X/Y plane
// (X = width, Y = height), listed bottom to top. Both renderers build
// their geometry from THIS, for the same reason they both consume
// dimensionRecords: it is the only way the 2D and 3D views can be shown
// to depict the same object rather than two drifting interpretations.
// The 3D renderer extrudes each rect along Z by the depth given here.
//
// The stack mirrors the dimension records exactly: the block spans
// H1+H2, the post (poteau) rises through Hv, the bearing plate (plaque
// d'appui) is Ec thick, and the stub adds Fee. The pipe sits at the
// block top (y = H1+H2), which is where the PhiM record anchors it.
//
// Thin members go through visualScale so they stay visible; labels are
// built from dimensionRecords and always report the TRUE value (§6.3).
export function elevationShapes(p) {
  const blockTop = p.H1 + p.H2;
  const postW = visualScale('Ep', p.Ep);
  const postX = (p.A - postW) / 2;
  const capY = blockTop + p.Hv;
  const pipeH = visualScale('PhiM', p.PhiM);
  return [
    { id: 'block', x: 0, y: 0, w: p.A, h: blockTop, depth: p.B, kind: 'solid' },
    { id: 'pipe', x: 0, y: blockTop - pipeH / 2, w: p.A, h: pipeH, depth: pipeH, kind: 'pipe' },
    { id: 'post', x: postX, y: blockTop, w: postW, h: p.Hv, depth: postW, kind: 'solid' },
    { id: 'cap', x: 0, y: capY, w: p.A, h: p.Ec, depth: p.B, kind: 'solid' },
    { id: 'stub', x: postX, y: capY + p.Ec, w: postW, h: p.Fee, depth: postW, kind: 'solid' }
  ];
}

// The container width below which dimension labels are dropped. The
// labels are fixed-size text, so they do not shrink with the panel: in a
// thumbnail-sized container they overlap into unreadable mush and bury
// the object they annotate. Both renderers use this one threshold so the
// two views behave identically at the same size. The thumbnail is a
// preview; "Agrandir le diagramme" is how you read values.
export const LABEL_MIN_CONTAINER_WIDTH = 420;
