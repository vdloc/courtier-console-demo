import { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import {
  AdaptiveDpr,
  AdaptiveEvents,
  BakeShadows,
  ContactShadows,
  Environment,
  Grid,
  Preload,
} from '@react-three/drei';
import { ACESFilmicToneMapping, PCFSoftShadowMap } from 'three';
import { Structure } from './Structure';
import { CameraRig } from './CameraRig';
import { Effects } from './Effects';
import { Measure } from './Measure';
import { SelectionBox } from './SelectionBox';
import { DetailCulling } from './DetailCulling';
import { ShadowController } from './ShadowController';
import { useViewerStore } from '../store/useViewerStore';

/**
 * Scene shell: renderer configuration, lighting, ground, and the effect
 * stack.
 *
 * `Environment preset="warehouse"` supplies the IBL. An HDRI is doing the
 * real work here - painted steel is mostly a reflection of its surroundings,
 * so a flat ambient light makes every member look like grey plastic no matter
 * what the material values say.
 */
export function Viewer() {
  const quality = useViewerStore((s) => s.quality);

  return (
    <Canvas
      shadows={{ type: PCFSoftShadowMap }}
      dpr={quality === 'high' ? [1, 2] : [1, 1.5]}
      camera={{ position: [58, 22, 46], fov: 38, near: 0.1, far: 800 }}
      onCreated={({ gl }) => {
        // Exposed for profiling in the browser console; harmless in prod and
        // the only way to see draw-call counts from outside React.
        (window as unknown as { __gl?: unknown }).__gl = gl;
      }}
      gl={{
        antialias: false,           // SMAA in the composer handles this
        toneMapping: ACESFilmicToneMapping,
        toneMappingExposure: 1.05,
        powerPreference: 'high-performance',
      }}
    >
      <color attach="background" args={['#0b0e13']} />
      <fog attach="fog" args={['#0b0e13', 120, 400]} />

      {/* Key light matched to the Blender sun: south-west, low, warm. */}
      <directionalLight
        castShadow
        position={[-60, 48, -40]}
        intensity={2.6}
        color="#fff4e2"
        shadow-mapSize={quality === 'high' ? [2048, 2048] : [1024, 1024]}
        shadow-bias={-0.0004}
        shadow-camera-left={-60}
        shadow-camera-right={60}
        shadow-camera-top={60}
        shadow-camera-bottom={-60}
        shadow-camera-far={220}
      />
      <ambientLight intensity={0.15} color="#9fb4d0" />

      <Suspense fallback={null}>
        <group>
          <Structure />
          <Measure />

          <Environment preset="warehouse" environmentIntensity={0.85} />
          {quality === 'high' && (
          <ContactShadows
            position={[14.4, -0.79, -9]}
            scale={90}
            resolution={1024}
            far={20}
            blur={2.5}
            opacity={0.55}
            color="#000000"
          />
          )}
          <Grid
            position={[14.4, -0.8, -9]}
            args={[200, 200]}
            cellSize={1}
            cellThickness={0.5}
            cellColor="#1b2430"
            sectionSize={7.2}          /* the structural bay, not a round number */
            sectionThickness={1}
            sectionColor="#2b3a4d"
            fadeDistance={180}
            fadeStrength={1.5}
            infiniteGrid
          />

          <DetailCulling />
          <ShadowController />
          <SelectionBox />
          <Effects />
        </group>

        <Preload all />
        {quality === 'performance' && <BakeShadows />}
      </Suspense>

      <CameraRig />
      <AdaptiveDpr pixelated />
      <AdaptiveEvents />
    </Canvas>
  );
}
