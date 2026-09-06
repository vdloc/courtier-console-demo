// Shared source of truth for BOTH renderers.
//
// The object described here is a reinforced-concrete corbel: a base block
// with a raised back wall, and a set of bent reinforcing bars whose top run
// sits under the base's top surface, turns down the front face, and ends in
// a hook below the underside.
//
// Layout convention: X = width (A axis), Y = height, Z = depth (B axis).
// The base footprint sits at X in [0, A], Z in [0, B], Y in [0, H1]. The
// raised block stands on the back of it. Bar hooks reach BELOW Y = 0, so
// consumers must not assume the geometry starts at zero height -- see
// sceneBounds() below, which is the supported way to ask.
//
// Both js/diagram2d.js and js/diagram3d.js build their geometry from the
// functions here. That is the whole point: it is the only way the 2D and 3D
// views can be shown to depict the same object rather than two drifting
// interpretations of one spec.

// Members whose true size is too small to see in the drawing. These are
// clamped to a visible floor for ANNOTATION GEOMETRY ONLY -- the label text
// always reports the true value. Bar diameter is deliberately absent from
// the geometry path: clamping the bars themselves would draw a corbel with
// the wrong steel in it.
const THIN_MEMBERS = new Set(['Db', 'Cb', 'Lt']);
const VISUAL_FLOOR = 0.06;

export function visualScale(key, value) {
  if (THIN_MEMBERS.has(key)) return Math.max(value, VISUAL_FLOOR);
  return value;
}

// --- the object --------------------------------------------------------

// The two concrete masses, as plain rectangles in the X/Y plane, listed
// bottom to top. The 3D renderer extrudes each along Z by its own depth.
export function elevationShapes(p) {
  return [
    { id: 'base', x: 0, y: 0, w: p.A, h: p.H1, depth: p.B, kind: 'solid' },
    // The raised block stands on the BACK of the base (the +X end), which
    // is what makes this a corbel rather than a plain plinth.
    { id: 'raised', x: p.A - p.A2, y: p.H1, w: p.A2, h: p.H2, depth: p.B, kind: 'solid' }
  ];
}

export function rebarRadius(p) {
  return p.Db / 2;
}

// The bar centreline, as an open polyline in the X/Y plane. Every bar is
// this same profile at a different Z, so the elevation shows one path no
// matter how many bars there are.
//
// Five named control points rather than a baked point cloud: the shape has
// exactly five decisions in it, and naming them is what lets the bars track
// the params instead of being a fixed mesh. (The original transcription
// from Blender carried 83 baked points including two small kinks in the
// source curve; those are gone -- they were absolute coordinates and could
// not survive A, H1 or the cover changing.)
export function rebarProfile(p) {
  const runY = p.H1 - p.Cb;      // top run, one cover depth below the surface
  const legX = p.Cb;             // vertical leg, one cover in from the front face
  const hookY = -p.Lh;           // hook turns below the base underside
  return [
    { x: p.A - p.A2, y: p.H1 + p.Db },  // anchored up into the raised block
    { x: p.A - p.A2, y: runY },         // down to the top run
    { x: legX, y: runY },               // the top run itself, toward the front
    { x: legX, y: hookY },              // down the front face and past the base
    { x: legX + p.Lt, y: hookY }        // hook tail
  ];
}

// Bar positions along the depth axis. Nb is a COUNT, not a length -- it is
// the one param here that is not in metres.
export function rebarDepths(p) {
  const n = Math.max(0, Math.round(p.Nb));
  const first = p.Cb + p.Db / 2;
  const out = [];
  for (let i = 0; i < n; i++) out.push(first + i * p.Sb);
  return out;
}

// The full extent of the drawn object, INCLUDING the bar hooks that reach
// below Y = 0. Renderers must size their viewport from this rather than
// from elevationShapes() alone: the hooks are the reason a naive
// "height = max(y + h)" starting at zero clips the bottom of the drawing.
export function sceneBounds(p) {
  let minY = 0;
  let maxY = 0;
  let minX = 0;
  let maxX = 0;
  for (const s of elevationShapes(p)) {
    minX = Math.min(minX, s.x);
    maxX = Math.max(maxX, s.x + s.w);
    minY = Math.min(minY, s.y);
    maxY = Math.max(maxY, s.y + s.h);
  }
  const r = rebarRadius(p);
  for (const pt of rebarProfile(p)) {
    minX = Math.min(minX, pt.x - r);
    maxX = Math.max(maxX, pt.x + r);
    minY = Math.min(minY, pt.y - r);
    maxY = Math.max(maxY, pt.y + r);
  }
  return { minX, maxX, minY, maxY };
}

// --- annotations -------------------------------------------------------

// Some records anchor in the same crowded corner as their neighbours, and
// at one uniform standoff their labels land on the same pixels. `offsetScale`
// multiplies a record's witness-line standoff so those few can be fanned
// out. It lives on the record because the record is what knows where it
// sits; both renderers honour it, so the two views fan out identically.
// Absent means 1.
export const dimensionRecords = [
  {
    id: 'A',
    from: () => ({ x: 0, y: 0, z: 0 }),
    to: (p) => ({ x: p.A, y: 0, z: 0 }),
    offsetDir: { x: 0, y: -1, z: 0 },
    label: (p) => `A = ${p.A.toFixed(2)}`
  },
  {
    // Runs along Z, which an elevation drops. diagram2d.js draws it as a
    // depth tick rather than a zero-length line.
    id: 'B',
    from: () => ({ x: 0, y: 0, z: 0 }),
    to: (p) => ({ x: 0, y: 0, z: p.B }),
    offsetDir: { x: -1, y: 0, z: 0 },
    // Shares the origin AND the -X side with H1; pushed further out so the
    // two labels stop colliding.
    offsetScale: 2.2,
    label: (p) => `B = ${p.B.toFixed(2)}`
  },
  {
    id: 'H1',
    from: () => ({ x: 0, y: 0, z: 0 }),
    to: (p) => ({ x: 0, y: p.H1, z: 0 }),
    offsetDir: { x: -1, y: 0, z: 0 },
    label: (p) => `H1 = ${p.H1.toFixed(2)}`
  },
  {
    id: 'H2',
    from: (p) => ({ x: p.A, y: p.H1, z: 0 }),
    to: (p) => ({ x: p.A, y: p.H1 + p.H2, z: 0 }),
    offsetDir: { x: 1, y: 0, z: 0 },
    label: (p) => `H2 = ${p.H2.toFixed(2)}`
  },
  {
    id: 'A2',
    from: (p) => ({ x: p.A - p.A2, y: p.H1 + p.H2, z: 0 }),
    to: (p) => ({ x: p.A, y: p.H1 + p.H2, z: 0 }),
    offsetDir: { x: 0, y: 1, z: 0 },
    label: (p) => `A2 = ${p.A2.toFixed(2)}`
  },
  {
    // Concrete cover: face of the concrete to the centre of the bar.
    id: 'Cb',
    from: (p) => ({ x: 0, y: p.H1 - p.Cb, z: 0 }),
    to: (p) => ({ x: visualScale('Cb', p.Cb), y: p.H1 - p.Cb, z: 0 }),
    offsetDir: { x: 0, y: 1, z: 0 },
    label: (p) => `Cb = ${p.Cb.toFixed(3)}`
  },
  {
    // Measured across the bar at mid-leg height. It used to sit at the hook
    // alongside Lt, where the two shared an anchor AND an offset direction,
    // so their labels landed on the same pixel and overprinted into mush.
    id: 'Db',
    // At H1/2 this collided with H1's own label, which a dimension line
    // always places at its midpoint -- the same height. A quarter of the
    // way up the leg is still unambiguously "across the bar" and clears it.
    from: (p) => ({ x: p.Cb, y: p.H1 / 4, z: 0 }),
    to: (p) => ({ x: p.Cb + visualScale('Db', p.Db), y: p.H1 / 4, z: 0 }),
    offsetDir: { x: -1, y: 0, z: 0 },
    offsetScale: 1.6,
    label: (p) => `Db = ${p.Db.toFixed(3)}`
  },
  {
    // Hook depth below the base underside. Offset to the +X side: the -X
    // side at this height already carries the B depth tick, and the two
    // labels collided there.
    id: 'Lh',
    from: (p) => ({ x: p.Cb, y: 0, z: 0 }),
    to: (p) => ({ x: p.Cb, y: -p.Lh, z: 0 }),
    offsetDir: { x: 1, y: 0, z: 0 },
    // Sits on the same short stretch of bar as Db once projected.
    offsetScale: 2.0,
    label: (p) => `Lh = ${p.Lh.toFixed(3)}`
  },
  {
    id: 'Lt',
    from: (p) => ({ x: p.Cb, y: -p.Lh, z: 0 }),
    to: (p) => ({ x: p.Cb + visualScale('Lt', p.Lt), y: -p.Lh, z: 0 }),
    offsetDir: { x: 0, y: -1, z: 0 },
    label: (p) => `Lt = ${p.Lt.toFixed(3)}`
  },
  {
    // Bar pitch runs along Z like B does, so it is also degenerate in
    // elevation and also renders as a depth tick.
    id: 'Sb',
    from: (p) => ({ x: p.A, y: p.H1, z: 0 }),
    to: (p) => ({ x: p.A, y: p.H1, z: p.Sb }),
    offsetDir: { x: 1, y: 0, z: 0 },
    label: (p) => `Sb = ${p.Sb.toFixed(3)}`
  }
];

// The container width below which dimension labels are dropped. The labels
// are fixed-size text, so they do not shrink with the panel: in a
// thumbnail-sized container they overlap into unreadable mush and bury the
// object they annotate. Both renderers use this one threshold so the two
// views behave identically at the same size. The thumbnail is a preview;
// "Enlarge diagram" is how you read values.
export const LABEL_MIN_CONTAINER_WIDTH = 420;
