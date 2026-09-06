import { useViewerStore } from '../store/useViewerStore';
import type { CameraShot } from '../types';

const SHOTS: { id: CameraShot; label: string }[] = [
  { id: 'hero', label: 'Hero' },
  { id: 'corner', label: 'Corner' },
  { id: 'detail', label: 'Joint' },
  { id: 'elevation', label: 'Elevation' },
];

/** View controls: camera shots, exploded view, measurement, quality. */
export function Toolbar() {
  const shot = useViewerStore((s) => s.shot);
  const setShot = useViewerStore((s) => s.setShot);
  const exploded = useViewerStore((s) => s.exploded);
  const toggleExplode = useViewerStore((s) => s.toggleExplode);
  const measuring = useViewerStore((s) => s.measuring);
  const toggleMeasuring = useViewerStore((s) => s.toggleMeasuring);
  const measurePoints = useViewerStore((s) => s.measurePoints);
  const clearMeasurement = useViewerStore((s) => s.clearMeasurement);
  const quality = useViewerStore((s) => s.quality);
  const setQuality = useViewerStore((s) => s.setQuality);
  const resetView = useViewerStore((s) => s.resetView);

  return (
    <>
      <section className="panel-section">
        <div className="panel-header">
          <span className="panel-title">Camera</span>
        </div>
        <div className="panel-body">
          <div className="button-row">
            {SHOTS.map((entry) => (
              <button
                key={entry.id}
                data-active={shot === entry.id}
                onClick={() => setShot(entry.id)}
              >
                {entry.label}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="panel-section">
        <div className="panel-header">
          <span className="panel-title">Tools</span>
        </div>
        <div className="panel-body">
          <div className="button-row">
            <button
              className="wide"
              data-active={exploded}
              onClick={toggleExplode}
            >
              Explode View
            </button>
            <button
              className="wide"
              data-active={measuring}
              onClick={toggleMeasuring}
            >
              Measure
            </button>
          </div>
          {measurePoints.length > 0 && (
            <div className="button-row" style={{ marginTop: 6 }}>
              <button className="wide" onClick={clearMeasurement}>
                Clear measurement
              </button>
            </div>
          )}
          {measuring && (
            <div className="hint">
              Click two points on the structure. The distance is measured
              between the surfaces you pick, not between object centres.
            </div>
          )}

          <div className="button-row" style={{ marginTop: 10 }}>
            {(['high', 'balanced', 'performance'] as const).map((level) => (
              <button
                key={level}
                data-active={quality === level}
                onClick={() => setQuality(level)}
              >
                {level}
              </button>
            ))}
          </div>

          <div className="button-row" style={{ marginTop: 10 }}>
            <button className="wide" onClick={resetView}>
              Reset View
            </button>
          </div>
        </div>
      </section>
    </>
  );
}
