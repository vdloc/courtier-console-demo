import { dimensionRecords } from './dimensions.js';

const PX_PER_METER = 300;
const MARGIN = 40;

function toScreen(pt, height) {
  return {
    x: MARGIN + pt.x * PX_PER_METER,
    y: MARGIN + (height - pt.y) * PX_PER_METER
  };
}

export function mountDiagram2D(container) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('width', '100%');
  svg.setAttribute('height', '100%');
  svg.setAttribute('viewBox', '0 0 600 500');
  container.appendChild(svg);

  function render(params) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    const sceneHeight = (params.H1 + params.H2 + params.Hv + params.Ec + params.Fee) + 0.3;

    for (const rec of dimensionRecords) {
      const from = toScreen(rec.from(params), sceneHeight);
      const to = toScreen(rec.to(params), sceneHeight);

      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', from.x);
      line.setAttribute('y1', from.y);
      line.setAttribute('x2', to.x);
      line.setAttribute('y2', to.y);
      line.setAttribute('stroke', '#e07a2c');
      line.setAttribute('stroke-width', '2');
      line.setAttribute('stroke-dasharray', '4,3');
      svg.appendChild(line);

      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      const midX = (from.x + to.x) / 2 + rec.offsetDir.x * 14;
      const midY = (from.y + to.y) / 2 + rec.offsetDir.y * 14;
      text.setAttribute('x', midX);
      text.setAttribute('y', midY);
      text.setAttribute('font-size', '11');
      text.setAttribute('fill', '#1a2b4c');
      text.textContent = rec.label(params);
      svg.appendChild(text);
    }
  }

  return { render };
}
