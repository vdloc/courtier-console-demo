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
  document.getElementById('view-toggle-2d').classList.toggle('active', mode === '2d');
  document.getElementById('view-toggle-3d').classList.toggle('active', mode === '3d');
  const modalToggle2d = document.getElementById('modal-view-toggle-2d');
  const modalToggle3d = document.getElementById('modal-view-toggle-3d');
  if (modalToggle2d) modalToggle2d.classList.toggle('active', mode === '2d');
  if (modalToggle3d) modalToggle3d.classList.toggle('active', mode === '3d');
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
      if (Number.isFinite(value) && value >= 0) {
        setParam(key, value);
      }
    });
    input.addEventListener('blur', () => {
      input.value = getParams()[key];
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
