// js/modal.js
function getApp() {
  // app.js runs first (script tag order in index.html), so this is defined by the time
  // any click handler below fires.
  return window.__courtierApp;
}

const overlayEl = document.getElementById('modal-overlay');
const thumbnailContainer = document.getElementById('diagram-thumbnail');
const modalContainer = document.getElementById('modal-diagram-container');
const expandBtn = document.getElementById('expand-diagram-btn');
const closeBtn = document.getElementById('modal-close-btn');
const modalToggle2d = document.getElementById('modal-view-toggle-2d');
const modalToggle3d = document.getElementById('modal-view-toggle-3d');

function moveDiagramInto(targetContainer) {
  const app = getApp();
  // The svg can currently live in either container (thumbnail normally, modal
  // while open), so look in both rather than assuming thumbnailContainer.
  const svgEl = thumbnailContainer.querySelector('svg') || modalContainer.querySelector('svg');
  if (svgEl) targetContainer.appendChild(svgEl);
  targetContainer.appendChild(app.view3d.canvas);
  targetContainer.appendChild(app.view3d.overlay);
  app.view3d.resize();
  // The 2D view's label visibility and text scale are both derived from
  // the container size, so it has to redraw for the new container too.
  if (app.view2d.resize) app.view2d.resize();
}

function openModal() {
  overlayEl.classList.remove('hidden');
  moveDiagramInto(modalContainer);
}

function closeModal() {
  overlayEl.classList.add('hidden');
  moveDiagramInto(thumbnailContainer);
}

expandBtn.addEventListener('click', openModal);
closeBtn.addEventListener('click', closeModal);
overlayEl.addEventListener('click', (e) => {
  if (e.target === overlayEl) closeModal();
});
modalToggle2d.addEventListener('click', () => getApp().setViewMode('2d'));
modalToggle3d.addEventListener('click', () => getApp().setViewMode('3d'));

// The overlay declares role="dialog" aria-modal="true", which promises
// dialog semantics; Escape-to-close is the part users actually reach for.
// Asserting the ARIA attribute without honouring it is worse than not
// asserting it at all.
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !overlayEl.classList.contains('hidden')) {
    closeModal();
  }
});
