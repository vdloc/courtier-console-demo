import { useEffect } from 'react';
import { useThree } from '@react-three/fiber';
import { useViewerStore } from '../store/useViewerStore';

/**
 * Shadow map update policy.
 *
 * A shadow map re-renders every caster from the light's point of view. With
 * ~3100 casters that is a second full pass over the whole model on every
 * frame - and the model is completely static except while the construction
 * sequence or the explode transition is running.
 *
 * So the map is refreshed on demand: once after load, and continuously only
 * while something is actually moving. Measured on an integrated GPU this was
 * the single largest frame-time cost in the scene, ahead of both SSAO and the
 * draw-call count.
 */
export function ShadowController() {
  const { gl } = useThree();
  const playback = useViewerStore((s) => s.playback);
  const explodeFactor = useViewerStore((s) => s.explodeFactor);
  const layers = useViewerStore((s) => s.layers);
  const quality = useViewerStore((s) => s.quality);

  const moving = playback === 'playing';

  useEffect(() => {
    gl.shadowMap.autoUpdate = moving;
    gl.shadowMap.needsUpdate = true;
  }, [gl, moving]);

  // Anything that changes what is visible, or where it sits, invalidates the
  // cached map exactly once.
  useEffect(() => {
    gl.shadowMap.needsUpdate = true;
  }, [gl, explodeFactor, layers, quality]);

  return null;
}
