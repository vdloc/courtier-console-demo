// Reinforced-concrete corbel. All values in metres EXCEPT Nb, which is a
// bar count. Defaults are the configuration the 3D scene was modelled at.
const params = {
  // Concrete
  A: 0.3,    // overall width
  B: 0.3,    // depth
  H1: 0.35,  // base block height
  A2: 0.15,  // raised back-wall width
  H2: 0.4,   // raised back-wall height
  // Reinforcement
  Nb: 4,     // number of bars (a count, not a length)
  Db: 0.04,  // bar diameter
  Sb: 0.07,  // bar pitch along the depth axis
  Cb: 0.02,  // concrete cover, face to bar centre
  Lh: 0.05,  // hook depth below the base underside
  Lt: 0.04   // hook tail length
};

const subscribers = new Set();

// Returns the live params object BY REFERENCE, not a copy. Treat it as
// read-only: mutating it would change state without notifying subscribers,
// so the diagrams and the result rows would silently drift out of sync
// with each other. Always go through setParam(), which notifies.
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
