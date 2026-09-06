import { useEffect } from 'react';
import { Viewer } from './scene/Viewer';
import { Dashboard } from './ui/Dashboard';
import { useViewerStore } from './store/useViewerStore';
import type { TimelineManifest } from './types';
import './ui/theme.css';

export default function App() {
  const ready = useViewerStore((s) => s.ready);
  const setTimeline = useViewerStore((s) => s.setTimeline);

  // The phase breakdown is authored once, in assembly_animation.py, and
  // shipped beside the GLB. Fetching it keeps the UI honest if the timeline
  // is re-cut without touching this code.
  useEffect(() => {
    let cancelled = false;
    fetch('/timeline.json')
      .then((response) => (response.ok ? response.json() : null))
      .then((data: TimelineManifest | null) => {
        if (data && !cancelled) setTimeline(data);
      })
      .catch(() => {
        /* The viewer still works without phase labels. */
      });
    return () => {
      cancelled = true;
    };
  }, [setTimeline]);

  return (
    <div className="app">
      <div className="canvas-host">
        <Viewer />
      </div>
      {!ready && <LoadingOverlay />}
      <Dashboard />
    </div>
  );
}

function LoadingOverlay() {
  const progress = useViewerStore((s) => s.loadProgress);
  return (
    <div className="loading">
      <div className="loading-inner">
        <div className="brand-name">Structural Digital Twin</div>
        <div className="brand-sub">LOADING MODEL</div>
        <div className="loading-bar">
          <div className="loading-fill" style={{ width: `${progress * 100}%` }} />
        </div>
      </div>
    </div>
  );
}
