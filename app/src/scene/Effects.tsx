import {
  Bloom,
  DepthOfField,
  EffectComposer,
  SMAA,
  SSAO,
  Vignette,
} from '@react-three/postprocessing';
import { BlendFunction } from 'postprocessing';
import { useViewerStore } from '../store/useViewerStore';

/**
 * Post-processing stack.
 *
 * SSAO rather than baked ambient occlusion, deliberately: AO is a geometry
 * signal, and baking it per object across ~3000 members would mean thousands
 * of texture bakes and a second UV set on every mesh. Screen-space AO gets
 * the contact darkening that makes beams sit *in* the frame instead of
 * floating over it, at one full-screen pass.
 *
 * Order matters: SSAO before depth of field, so the occlusion is computed on
 * sharp depth; SMAA last, so it antialiases the finished image.
 *
 * There is deliberately no Outline effect here. Combined with SSAO's normal
 * pass on postprocessing 6.36 / three r169 it produces a framebuffer feedback
 * loop - the browser logs `GL_INVALID_OPERATION: Feedback loop formed between
 * Framebuffer and active Texture` on every frame. Selection is drawn as
 * geometry instead, in scene/SelectionBox.tsx.
 */
export function Effects() {
  const quality = useViewerStore((s) => s.quality);
  const selected = useViewerStore((s) => s.selected);

  // SSAO needs the composer's normal pass, which is a second full-scene
  // render. On an integrated GPU with ~3000 draw calls that is the difference
  // between a usable viewer and a slideshow, so it is reserved for 'high'.
  if (quality !== 'high') {
    return (
      <EffectComposer enableNormalPass={false} multisampling={4}>
        <Bloom
          intensity={0.22}
          luminanceThreshold={0.85}
          luminanceSmoothing={0.3}
          mipmapBlur
        />
        <Vignette eskil={false} offset={0.25} darkness={0.55} />
        <SMAA />
      </EffectComposer>
    );
  }

  const high = true;

  return (
    // enableNormalPass is required by SSAO - without it the effect silently
    // renders nothing, which looks like a configuration that "did not work".
    <EffectComposer enableNormalPass multisampling={0}>
      <SSAO
        intensity={2.0}
        radius={0.5}
        distanceThreshold={0.2}
        distanceFalloff={0.05}
        rangeThreshold={0.001}
        rangeFalloff={0.01}
        luminanceInfluence={0.6}
        samples={high ? 24 : 12}
        rings={high ? 6 : 4}
        worldDistanceThreshold={40}
        worldDistanceFalloff={8}
        worldProximityThreshold={4}
        worldProximityFalloff={1}
        color={undefined}
        blendFunction={BlendFunction.MULTIPLY}
      />
      {high && selected ? (
        // Depth of field only once something is selected: a shallow focus
        // plane on an overview shot just blurs the building.
        <DepthOfField
          focusDistance={0.012}
          focalLength={0.05}
          bokehScale={2.5}
          height={480}
        />
      ) : (
        <></>
      )}
      <Bloom
        intensity={0.25}
        luminanceThreshold={0.85}
        luminanceSmoothing={0.3}
        mipmapBlur
      />
      <Vignette eskil={false} offset={0.25} darkness={0.55} />
      <SMAA />
    </EffectComposer>
  );
}
