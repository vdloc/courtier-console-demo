import { Inspector } from './Inspector';
import { Layers } from './Layers';
import { Timeline } from './Timeline';
import { Toolbar } from './Toolbar';
import { useViewerStore } from '../store/useViewerStore';

/** Panel layout. The canvas owns the middle; panels float over the edges. */
export function Dashboard() {
  const ready = useViewerStore((s) => s.ready);
  if (!ready) return null;

  return (
    <>
      <div className="panel panel-left">
        <div className="brand">
          <div className="brand-name">Structural Digital Twin</div>
          <div className="brand-sub">STEEL FRAME · 4 × 3 BAYS · G+3</div>
        </div>
        <Layers />
        <Toolbar />
      </div>

      <div className="panel panel-right">
        <Inspector />
      </div>

      <Timeline />
    </>
  );
}
