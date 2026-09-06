import { useViewerStore } from '../store/useViewerStore';
import { LAYERS } from '../types';

/**
 * Layer visibility. The list is the GLB's own top-level group names, so the
 * panel cannot drift out of step with the model - adding a discipline in
 * Blender surfaces here without a code change.
 */
export function Layers() {
  const layers = useViewerStore((s) => s.layers);
  const toggleLayer = useViewerStore((s) => s.toggleLayer);
  const setAllLayers = useViewerStore((s) => s.setAllLayers);

  const allOn = LAYERS.every((layer) => layers[layer]);

  return (
    <section className="panel-section">
      <div className="panel-header">
        <span className="panel-title">Structure Layers</span>
        <button onClick={() => setAllLayers(!allOn)}>
          {allOn ? 'Hide all' : 'Show all'}
        </button>
      </div>
      <div className="panel-body">
        {LAYERS.map((layer) => (
          <div
            key={layer}
            className="layer-row"
            onClick={() => toggleLayer(layer)}
            role="checkbox"
            aria-checked={layers[layer]}
            tabIndex={0}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') toggleLayer(layer);
            }}
          >
            <span className="checkbox" data-on={layers[layer]}>
              {layers[layer] ? '✓' : ''}
            </span>
            <span className="layer-name">{layer}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
