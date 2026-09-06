import { useCallback, useRef } from 'react';
import { useViewerStore } from '../store/useViewerStore';

/**
 * Construction timeline: transport controls plus a scrubbable track marked
 * with the phase boundaries the Blender pipeline exported.
 *
 * The phase marks come from timeline.json rather than being hardcoded, so the
 * 0-3-6-10-14-18 second breakdown is defined once, in assembly_animation.py.
 */
export function Timeline() {
  const timeline = useViewerStore((s) => s.timeline);
  const playback = useViewerStore((s) => s.playback);
  const progress = useViewerStore((s) => s.progress);
  const start = useViewerStore((s) => s.startConstruction);
  const pause = useViewerStore((s) => s.pauseConstruction);
  const reset = useViewerStore((s) => s.resetConstruction);
  const requestSeek = useViewerStore((s) => s.requestSeek);
  const trackRef = useRef<HTMLDivElement>(null);

  const duration = timeline?.duration ?? 18;
  const seconds = progress * duration;

  const scrub = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      const rect = trackRef.current?.getBoundingClientRect();
      if (!rect) return;
      const ratio = (event.clientX - rect.left) / rect.width;
      requestSeek(Math.max(0, Math.min(1, ratio)));
    },
    [requestSeek],
  );

  const activePhase = timeline?.phases.find(
    (phase) => seconds >= phase.start && seconds < phase.end,
  );

  return (
    <div className="timeline">
      <div className="timeline-head">
        <div className="button-row">
          <button
            className="primary"
            onClick={playback === 'playing' ? pause : start}
          >
            {playback === 'playing' ? 'Pause' : 'Construction Sequence'}
          </button>
          <button onClick={reset}>Reset</button>
        </div>
        <span className="timeline-time">
          {seconds.toFixed(1)}s / {duration.toFixed(0)}s
          {activePhase ? ` · ${activePhase.name}` : ''}
        </span>
      </div>

      <div className="track" ref={trackRef} onClick={scrub}>
        <div className="track-rail">
          <div className="track-fill" style={{ width: `${progress * 100}%` }} />
        </div>

        <div className="phase-marks">
          {timeline?.phases.map((phase) => (
            <span
              key={phase.name}
              className="phase-mark"
              data-active={phase === activePhase}
              style={{ left: `${(phase.start / duration) * 100}%` }}
            >
              {phase.name}
            </span>
          ))}
        </div>

        <div className="scrub-handle" style={{ left: `${progress * 100}%` }} />
      </div>
    </div>
  );
}
