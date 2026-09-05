// js/app.js
import { getParams, setParam, subscribe } from './state.js';
import { mountDiagram2D } from './diagram2d.js';
import { mountDiagram3D } from './diagram3d.js';

const PARAM_KEYS = ['A', 'B', 'H1', 'H2', 'Hv', 'Ec', 'Ep', 'Fee', 'PhiM', 'Uh', 'Ub', 'HsD'];

let viewMode = '2d'; // '2d' | '3d'

const thumbnailContainer = document.getElementById('diagram-thumbnail');
const view2d = mountDiagram2D(thumbnailContainer);
const view3d = mountDiagram3D(thumbnailContainer);

function applyViewModeVisibility() {
  // Both views are mounted into the same container; only one is visible/interactive at a time.
  view3d.canvas.style.display = viewMode === '3d' ? 'block' : 'none';
  view3d.overlay.style.display = viewMode === '3d' ? 'block' : 'none';
  // Container-agnostic lookup: modal.js re-parents the svg into
  // #modal-diagram-container while the modal is open, so
  // thumbnailContainer.querySelector('svg') would return null then and this
  // function could never un-hide it again (e.g. switching 3d -> 2d inside
  // the open modal).
  const svgEl = document.querySelector('#diagram-thumbnail svg, #modal-diagram-container svg');
  if (svgEl) svgEl.style.display = viewMode === '2d' ? 'block' : 'none';
}

function setViewMode(mode) {
  viewMode = mode;
  // Both toggle pairs (thumbnail and modal) derive from this one call, so
  // they can never disagree. `aria-pressed` is set alongside the `active`
  // class rather than in the markup: these are toggle buttons, and a
  // screen reader otherwise gets no signal about which view is selected.
  for (const [id, active] of [
    ['view-toggle-2d', mode === '2d'],
    ['view-toggle-3d', mode === '3d'],
    ['modal-view-toggle-2d', mode === '2d'],
    ['modal-view-toggle-3d', mode === '3d']
  ]) {
    const btn = document.getElementById(id);
    if (!btn) continue;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-pressed', String(active));
  }
  applyViewModeVisibility();
}

function renderResultRows(params) {
  const container = document.getElementById('result-rows');
  container.innerHTML = '';
  for (const key of PARAM_KEYS) {
    const row = document.createElement('div');
    row.className = 'row';
    row.innerHTML = `<span>${key}</span><span>${params[key].toFixed(3)} m</span>`;
    container.appendChild(row);
  }
}

function renderAll(params) {
  view2d.render(params);
  view3d.render(params);
  renderResultRows(params);
}

function setupFormInputs() {
  const params = getParams();
  for (const key of PARAM_KEYS) {
    const input = document.getElementById(`input-${key}`);
    input.value = params[key];
    input.addEventListener('input', () => {
      const value = parseFloat(input.value);
      // The markup's min/max are only advisory: a browser lets you type
      // past them, and typing 50 into a field capped at 2 produced a
      // hairline diagram. Enforce the declared range here so the geometry
      // stays sane, and reject anything non-finite.
      const min = input.hasAttribute('min') ? parseFloat(input.min) : 0;
      const max = input.hasAttribute('max') ? parseFloat(input.max) : Infinity;
      if (Number.isFinite(value) && value >= min && value <= max) {
        input.classList.remove('invalid');
        setParam(key, value);
      } else {
        input.classList.add('invalid');
      }
    });
    input.addEventListener('blur', () => {
      // Revert to the last accepted value. Only rewrite the field when it
      // actually disagrees, so a valid "0.30" is not rewritten to "0.3"
      // under the user's cursor on every blur.
      const current = getParams()[key];
      if (parseFloat(input.value) !== current) input.value = current;
      input.classList.remove('invalid');
    });
  }
}

document.getElementById('view-toggle-2d').addEventListener('click', () => setViewMode('2d'));
document.getElementById('view-toggle-3d').addEventListener('click', () => setViewMode('3d'));

setupFormInputs();
subscribe(renderAll);
renderAll(getParams());
setViewMode(viewMode);

window.__courtierApp = { view2d, view3d, getViewMode: () => viewMode, setViewMode };
