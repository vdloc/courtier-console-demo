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

// Where focus was before the modal opened, so it can be handed back on
// close rather than dumped on <body>.
let lastFocused = null;

function focusableInModal() {
  return [...overlayEl.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')]
    .filter((el) => !el.hasAttribute('disabled') && el.offsetParent !== null);
}

function openModal() {
  lastFocused = document.activeElement;
  overlayEl.classList.remove('hidden');
  moveDiagramInto(modalContainer);
  // aria-modal="true" tells assistive tech that everything outside is
  // inert; that is only true if focus actually moves in and stays in.
  const first = focusableInModal()[0];
  if (first) first.focus();
}

function closeModal() {
  overlayEl.classList.add('hidden');
  moveDiagramInto(thumbnailContainer);
  // Hand focus back to whatever opened the dialog. If that is gone (or was
  // never a focusable element), the expand button is the control the modal
  // belongs to, so it is the sane landing spot -- never <body>.
  const target =
    lastFocused && lastFocused.isConnected && lastFocused !== document.body
      ? lastFocused
      : expandBtn;
  target.focus();
  lastFocused = null;
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
  if (overlayEl.classList.contains('hidden')) return;
  if (e.key === 'Escape') {
    closeModal();
    return;
  }
  // Keep Tab inside the dialog: without this, tabbing walks out into the
  // form behind the overlay, which aria-modal claims is inert.
  if (e.key !== 'Tab') return;
  const items = focusableInModal();
  if (items.length === 0) return;
  const first = items[0];
  const last = items[items.length - 1];
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault();
    first.focus();
  }
});
