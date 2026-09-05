const params = {
  A: 0.3, B: 0.3,
  H1: 0.4, H2: 0.35,
  Hv: 0.4,
  Ec: 0.15,
  Ep: 0.03,
  Fee: 0.1,
  PhiM: 0.1,
  Uh: 0.04, Ub: 0.04,
  HsD: 0
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
