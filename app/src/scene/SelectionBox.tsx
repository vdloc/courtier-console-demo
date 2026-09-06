import { useMemo } from 'react';
import { Box3, BoxGeometry, EdgesGeometry, Vector3 } from 'three';
import { Html } from '@react-three/drei';
import { useViewerStore } from '../store/useViewerStore';
import { componentCode, elementLabel } from '../lib/format';

/**
 * Selection highlight, drawn as geometry rather than as a post-process
 * outline.
 *
 * The obvious implementation - the Outline effect - cannot be used alongside
 * SSAO here: SSAO needs the composer's normal pass, and the two together
 * produce a framebuffer feedback loop on this three/postprocessing pairing.
 * A bounding box is also the more honest engineering read: it shows the
 * member's extents, which is what a CAD selection does.
 */
export function SelectionBox() {
  const selected = useViewerStore((s) => s.selected);

  const geometry = useMemo(() => {
    if (!selected) return null;
    const box = new Box3().setFromObject(selected.object);
    const size = box.getSize(new Vector3());
    const centre = box.getCenter(new Vector3());
    // A hair of padding keeps the outline off the surface it wraps, which
    // stops it z-fighting with the member's own faces.
    const source = new BoxGeometry(
      size.x + 0.02,
      size.y + 0.02,
      size.z + 0.02,
    );
    const edges = new EdgesGeometry(source);
    source.dispose();
    return { edges, centre, size };
  }, [selected]);

  if (!selected || !geometry) return null;

  return (
    <group position={geometry.centre}>
      <lineSegments geometry={geometry.edges}>
        <lineBasicMaterial
          color="#38bdf8"
          transparent
          opacity={0.95}
          depthTest={false}
        />
      </lineSegments>

      <Html
        position={[0, geometry.size.y * 0.5 + 0.35, 0]}
        center
        distanceFactor={14}
        zIndexRange={[10, 0]}
      >
        <div className="measure-label">
          {elementLabel(selected.element_type)}{' '}
          {componentCode(selected.element_type, selected.grid_ref)}
        </div>
      </Html>
    </group>
  );
}
