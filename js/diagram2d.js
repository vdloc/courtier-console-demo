import {
  dimensionRecords,
  elevationShapes,
  rebarProfile,
  rebarRadius,
  sceneBounds,
  LABEL_MIN_CONTAINER_WIDTH
} from './dimensions.js';

const PX_PER_METER = 300;
const MARGIN = 40;
// How far a dimension line is drawn out from the geometry it measures,
// in px. Drafting practice: the dimension line sits beside the object,
// with short extension lines tying it back to the measured points, so
// the annotation never runs through the drawing.
const WITNESS_OFFSET = 26;
const EXTENSION_OVERSHOOT = 5;
// Gap between a dimension line and its label.
const LABEL_GAP = 6;
const SVG_NS = 'http://www.w3.org/2000/svg';

function el(name, attrs) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
}

export function mountDiagram2D(container) {
  const svg = el('svg', {
    width: '100%',
    height: '100%',
    viewBox: '0 0 600 500',
    preserveAspectRatio: 'xMidYMid meet'
  });
  container.appendChild(svg);

  // Model -> screen. Y is flipped (SVG grows downward) against the scene's
  // TOP, not its height: the rebar hooks reach below y = 0, so measuring
  // down from a fixed top is the only mapping that keeps negative-y
  // geometry on the canvas instead of above it.
  function toScreen(pt, top) {
    return {
      x: MARGIN + pt.x * PX_PER_METER,
      y: MARGIN + (top - pt.y) * PX_PER_METER
    };
  }

  // Last params rendered, so the view can redraw itself for a new
  // container size without the caller having to thread state back in.
  let lastParams = null;

  // Size from the svg's CURRENT parent, not the container captured in
  // this closure: after modal.js re-parents the svg, the original
  // container is a different size (or empty), and reading it would make
  // the enlarged view keep the thumbnail's label decision.
  function sizingEl() {
    return svg.parentElement || container;
  }

  function render(params) {
    lastParams = params;
    while (svg.firstChild) svg.removeChild(svg.firstChild);

    const shapes = elevationShapes(params);
    // sceneBounds() covers the rebar hooks, which reach BELOW y = 0. Sizing
    // from elevationShapes() alone (the old `max(y + h)` starting at zero)
    // silently clips them off the bottom of the drawing.
    const bounds = sceneBounds(params);
    const top = bounds.maxY + 0.05;
    const sceneHeight = top - bounds.minY + 0.05;
    // Labels are fixed-size text and do not shrink with the panel, so in a
    // small container they would overlap into unreadable mush over the
    // object. Same threshold and same reasoning as the 3D renderer.
    const showLabels = (sizingEl().clientWidth || 0) >= LABEL_MIN_CONTAINER_WIDTH;

    const projected = dimensionRecords.map((rec) => ({
      rec,
      from: toScreen(rec.from(params), top),
      to: toScreen(rec.to(params), top)
    }));

    // --- the object itself -------------------------------------------------
    // Drawn first so the annotation layer sits on top of it.
    const objectGroup = el('g', {});
    for (const s of shapes) {
      const topLeft = toScreen({ x: s.x, y: s.y + s.h }, top);
      const w = s.w * PX_PER_METER;
      const h = s.h * PX_PER_METER;
      if (w <= 0 || h <= 0) continue;
      objectGroup.appendChild(el('rect', {
        x: topLeft.x,
        y: topLeft.y,
        width: w,
        height: h,
        fill: '#dbe2ec',
        stroke: '#8a97a8',
        'stroke-width': 1.5
      }));
    }

    // Reinforcement. All Nb bars share one profile at different depths, and
    // an elevation drops the depth axis -- so they project onto each other
    // and the correct drawing is ONE path, not Nb overlapping copies.
    // Stroked at the true bar diameter so the steel reads at its real size
    // (visualScale deliberately does not touch bar geometry).
    const profile = rebarProfile(params);
    if (profile.length > 1) {
      const d = profile
        .map((pt, i) => {
          const s = toScreen(pt, top);
          return `${i === 0 ? 'M' : 'L'}${s.x.toFixed(2)} ${s.y.toFixed(2)}`;
        })
        .join(' ');
      objectGroup.appendChild(el('path', {
        d,
        fill: 'none',
        stroke: '#7a3b26',
        'stroke-width': Math.max(rebarRadius(params) * 2 * PX_PER_METER, 1.5),
        'stroke-linejoin': 'round',
        'stroke-linecap': 'round',
        opacity: 0.9
      }));
    }
    svg.appendChild(objectGroup);

    // --- dimension annotations --------------------------------------------
    // Each dimension line is pushed out along offsetDir (spec 6.2) so it
    // sits beside the object rather than through it, with extension lines
    // tying it back to the two measured points.
    const annotations = el('g', {});
    const labelPositions = [];
    for (const { rec, from, to } of projected) {
      // Records that share a crowded corner carry their own offsetScale so
      // their labels fan out instead of overprinting (see dimensions.js).
      // The 3D view applies the same factor, so both views fan out alike.
      const witness = WITNESS_OFFSET * (rec.offsetScale ?? 1);
      const ox = rec.offsetDir.x * witness;
      // offsetDir.y is +up in model space; SVG y grows downward.
      const oy = -rec.offsetDir.y * witness;
      const a = { x: from.x + ox, y: from.y + oy };
      const b = { x: to.x + ox, y: to.y + oy };

      // Degenerate in this projection (the B dimension runs along Z, which
      // an elevation drops). Mark it with a depth tick rather than drawing
      // a zero-length line that renders as nothing.
      const degenerate = Math.hypot(b.x - a.x, b.y - a.y) < 1;
      if (degenerate) {
        const tick = 14;
        annotations.appendChild(el('line', {
          x1: a.x, y1: a.y, x2: a.x - tick, y2: a.y + tick,
          stroke: '#e07a2c', 'stroke-width': 1.5, 'stroke-dasharray': '4,3'
        }));
        labelPositions.push({ rec, x: a.x - tick - LABEL_GAP, y: a.y + tick, anchor: 'end' });
        continue;
      }

      annotations.appendChild(el('line', {
        x1: a.x, y1: a.y, x2: b.x, y2: b.y,
        stroke: '#e07a2c', 'stroke-width': 1.5, 'stroke-dasharray': '4,3'
      }));
      // Extension lines: measured point -> just past the dimension line.
      const ext = EXTENSION_OVERSHOOT;
      const ux = ox === 0 ? 0 : Math.sign(ox);
      const uy = oy === 0 ? 0 : Math.sign(oy);
      for (const [p, q] of [[from, a], [to, b]]) {
        annotations.appendChild(el('line', {
          x1: p.x + ux * 3, y1: p.y + uy * 3,
          x2: q.x + ux * ext, y2: q.y + uy * ext,
          stroke: '#e0a878', 'stroke-width': 1
        }));
      }

      const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
      const vertical = Math.abs(b.y - a.y) > Math.abs(b.x - a.x);
      labelPositions.push({
        rec,
        x: mid.x + (vertical ? (ox < 0 ? -LABEL_GAP : LABEL_GAP) : 0),
        y: mid.y + (vertical ? 0 : (oy < 0 ? -LABEL_GAP : LABEL_GAP + 9)),
        anchor: vertical ? (ox < 0 ? 'end' : 'start') : 'middle'
      });
    }
    svg.appendChild(annotations);

    // --- viewBox ----------------------------------------------------------
    // Derived from what was actually drawn (object + annotations), so the
    // diagram never clips regardless of params.
    let minX = 0;
    let maxX = (bounds.maxX + 0.1) * PX_PER_METER + MARGIN;
    for (const { x, anchor, rec } of labelPositions) {
      // Reserve room for the label text itself. Estimated from the string
      // rather than measured, since getBBox is unreliable before layout.
      // 7.5px/char is a deliberate over-estimate: labels are counter-scaled
      // up in small viewBoxes, so a tight estimate clips the outermost one.
      const textW = rec.label(params).length * 7.5;
      minX = Math.min(minX, anchor === 'end' ? x - textW : x);
      maxX = Math.max(maxX, anchor === 'end' ? x : x + textW);
    }
    for (const { from, to, rec } of projected) {
      const ox = rec.offsetDir.x * WITNESS_OFFSET * (rec.offsetScale ?? 1);
      minX = Math.min(minX, from.x + ox, to.x + ox);
      maxX = Math.max(maxX, from.x + ox, to.x + ox);
    }
    minX -= MARGIN;
    maxX += MARGIN;
    const viewWidth = Math.max(maxX - minX, 1);
    // Baseline records (A, Ub) are offset DOWNWARD past the object's foot,
    // then their labels sit a further gap below that, so the drawing needs
    // more room under the baseline than the top margin alone provides.
    const viewHeight =
      sceneHeight * PX_PER_METER + 2 * MARGIN + WITNESS_OFFSET + LABEL_GAP + 18;
    svg.setAttribute('viewBox', `${minX} 0 ${viewWidth} ${viewHeight}`);

    // --- labels -----------------------------------------------------------
    if (!showLabels) return;
    // The SVG is scaled to fit the panel, which scales text with it. Undo
    // that so the rendered glyphs are a constant size no matter how the
    // viewBox grew.
    const cw = sizingEl().clientWidth || viewWidth;
    const ch = sizingEl().clientHeight || viewHeight;
    const scale = Math.min(cw / viewWidth, ch / viewHeight) || 1;
    const fontSize = 11 / scale;
    for (const { rec, x, y, anchor } of labelPositions) {
      const text = el('text', {
        x,
        y,
        'font-size': fontSize,
        'text-anchor': anchor,
        fill: '#1a2b4c',
        'font-family': 'system-ui, sans-serif'
      });
      text.textContent = rec.label(params);
      svg.appendChild(text);
    }
  }

  // Whether labels are shown, and the font counter-scale, both depend on
  // the CONTAINER size -- which changes when modal.js re-parents the svg
  // and when the window resizes. Neither of those changes params, so
  // without an explicit redraw the svg would keep the thumbnail's
  // label decision after being enlarged.
  function resize() {
    if (lastParams) render(lastParams);
  }

  window.addEventListener('resize', resize);

  return { render, resize, svg };
}
