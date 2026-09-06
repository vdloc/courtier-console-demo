import { useEffect, useMemo, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { Mesh, Object3D, Vector3 } from 'three';
import { useViewerStore } from '../store/useViewerStore';

/**
 * Distance-based level of detail.
 *
 * The model carries ~2100 fasteners, welds and stiffener ribs. They are what
 * makes a close-up connection read as fabricated steel, and they are also
 * two thirds of the scene's draw calls - at 30 m they cover less than a pixel
 * each and cost exactly as much as they do at 2 m.
 *
 * So detail parts are switched off past a distance threshold rather than
 * being simplified: for a 24 mm bolt there is no meaningful lower LOD, only
 * present or absent. The thresholds are per element type because a 100 mm
 * gusset stays legible far longer than an M24 nut.
 *
 * This is visibility only. It never touches the transform, so the
 * construction animation and the explode offsets keep working underneath it.
 */

const LOD_DISTANCE: Record<string, number> = {
  bolt: 18,
  weld: 14,
  stiffener: 45,
  toe_board: 60,
  guard_post: 70,
  splice_plate: 60,
  gusset: 55,
  end_plate: 80,
};

interface DetailPart {
  object: Object3D;
  centre: Vector3;
  threshold: number;
}

export function DetailCulling() {
  const { scene, camera } = useThree();
  const parts = useRef<DetailPart[]>([]);
  const accumulator = useRef(0);
  const quality = useViewerStore((s) => s.quality);

  // Aggressive on the performance preset, generous on high - the user is
  // choosing between frame rate and fastener detail, so make that real.
  const scale = useMemo(
    () => (quality === 'high' ? 1.6 : quality === 'balanced' ? 1.0 : 0.6),
    [quality],
  );

  useEffect(() => {
    const found: DetailPart[] = [];
    scene.traverse((object) => {
      if (!(object instanceof Mesh)) return;
      const type = (object.userData as { element_type?: string }).element_type;
      const threshold = type ? LOD_DISTANCE[type] : undefined;
      if (!threshold) return;
      found.push({
        object,
        centre: object.getWorldPosition(new Vector3()),
        threshold,
      });
    });
    parts.current = found;

    return () => {
      // Leave everything visible on unmount, so a later screenshot or export
      // is never missing hardware because of a camera position.
      for (const part of found) part.object.visible = true;
    };
  }, [scene]);

  useFrame((_, delta) => {
    // Re-evaluating 2100 distances every frame would cost more than the draw
    // calls it saves. Six times a second is imperceptible while orbiting.
    accumulator.current += delta;
    if (accumulator.current < 0.16) return;
    accumulator.current = 0;

    const eye = camera.position;
    for (const part of parts.current) {
      const visible = eye.distanceTo(part.centre) < part.threshold * scale;
      if (part.object.visible !== visible) part.object.visible = visible;
    }
  });

  return null;
}
