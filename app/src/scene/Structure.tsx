import { useEffect, useMemo, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { useGLTF } from '@react-three/drei';
import { Box3, MathUtils, Mesh, Object3D, Vector3 } from 'three';
import type { ThreeEvent } from '@react-three/fiber';
import { useViewerStore } from '../store/useViewerStore';
import { ConstructionSequence } from './Sequence';
import type { ComponentData, ComponentInfo, LayerName } from '../types';
import { LAYERS } from '../types';

const MODEL_URL = '/structure_demo.glb';

/**
 * Drei's loader is pointed at local decoders rather than a CDN so the viewer
 * keeps working on an air-gapped client network. The GLB is Draco-compressed
 * by the Blender pipeline, so without a reachable decoder nothing loads at
 * all - this is a hard dependency, not an optimisation.
 */
const DRACO_PATH = '/draco/';

useGLTF.preload(MODEL_URL, DRACO_PATH);

interface ExplodeRecord {
  object: Object3D;
  /**
   * Where the member sits when it is not exploded.
   *
   * Captured when an explode STARTS, never at mount. At mount every node
   * still holds the construction clip's parked transform, so a home recorded
   * there would send the whole frame back underground the moment the user
   * collapsed the exploded view.
   */
  home: Vector3;
  offset: Vector3;
}

/** Read the Blender custom properties the exporter wrote into glTF extras. */
function componentData(object: Object3D): ComponentData | null {
  const extras = object.userData as Partial<ComponentData>;
  if (!extras || !extras.element_type) return null;
  return {
    discipline: extras.discipline ?? 'STR',
    element_type: extras.element_type,
    level: extras.level ?? 'L00',
    grid_ref: extras.grid_ref ?? '',
    section: extras.section ?? '',
    material_spec: extras.material_spec ?? '',
  };
}

/** Longest bounding-box dimension: for a structural member, its length. */
function memberLength(object: Object3D): number {
  const box = new Box3().setFromObject(object);
  const size = box.getSize(new Vector3());
  return Math.max(size.x, size.y, size.z);
}

/** Walk up to the layer group the object belongs to. */
function layerOf(object: Object3D): LayerName | null {
  let node: Object3D | null = object;
  while (node) {
    if ((LAYERS as readonly string[]).includes(node.name)) {
      return node.name as LayerName;
    }
    node = node.parent;
  }
  return null;
}

export function Structure() {
  // The decoder path is required, not optional: optimize_export.py writes a
  // Draco-compressed GLB, so without it the model fails to parse entirely.
  const { scene, animations } = useGLTF(MODEL_URL, DRACO_PATH);
  const { camera } = useThree();
  const sequenceRef = useRef<ConstructionSequence | null>(null);
  const explodeRef = useRef<ExplodeRecord[]>([]);
  const appliedExplode = useRef(0);
  /** Whether `record.home` currently holds a valid rest pose. */
  const explodeHome = useRef(false);

  const setReady = useViewerStore((s) => s.setReady);
  const select = useViewerStore((s) => s.select);
  const hover = useViewerStore((s) => s.hover);
  const setProgress = useViewerStore((s) => s.setProgress);
  const clearSeek = useViewerStore((s) => s.clearSeek);

  // --- one-time model preparation ---------------------------------------
  useEffect(() => {
    const records: ExplodeRecord[] = [];
    const centre = new Box3().setFromObject(scene).getCenter(new Vector3());

    scene.traverse((object) => {
      if (!(object instanceof Mesh)) return;
      object.castShadow = true;
      object.receiveShadow = true;
      // Frustum culling is the single biggest win on a 3000-object scene and
      // is only safe because every member is a separate node with its own
      // bounds - which is exactly what the export preserved.
      object.frustumCulled = true;

      // Explode direction: radially outward from the model centre, scaled by
      // height so upper storeys separate further and the frame opens like a
      // drawing rather than a shattering.
      const position = object.getWorldPosition(new Vector3());
      const offset = position.clone().sub(centre);
      offset.y *= 1.6;
      offset.multiplyScalar(0.35);
      records.push({ object, home: object.position.clone(), offset });
      // `home` is re-read when an explode begins; the value stored here is a
      // placeholder so the field is never undefined.
    });

    explodeRef.current = records;

    if (animations.length > 0) {
      const sequence = new ConstructionSequence(scene, animations);
      sequenceRef.current = sequence;

      // Open on the FINISHED structure, not an empty site.
      //
      // The GLB's node transforms are the parked state - scale 0.001, offset
      // below ground - because the exporter samples the scene animation and
      // writes each node from the first frame. Setting the Blender scene to
      // the last frame before export does not survive that sampling, so the
      // deterministic fix is here: seek the clip to its end on load, which
      // applies the final transform to every node.
      sequence.seek(1);
      setProgress(1);
    }
    setReady(true);

    return () => {
      sequenceRef.current?.dispose();
      sequenceRef.current = null;
    };
  }, [scene, animations, setReady, setProgress]);

  // --- layer visibility --------------------------------------------------
  const layers = useViewerStore((s) => s.layers);
  useEffect(() => {
    scene.traverse((object) => {
      const layer = layerOf(object);
      if (layer && (LAYERS as readonly string[]).includes(object.name)) {
        object.visible = layers[layer];
      }
    });
  }, [scene, layers]);

  // --- per-frame: animation, explode, progress reporting -----------------
  useFrame((_, delta) => {
    const store = useViewerStore.getState();
    const sequence = sequenceRef.current;

    if (sequence) {
      if (store.seekRequest !== null) {
        sequence.seek(store.seekRequest);
        clearSeek();
        // Report the new position immediately. The mixer only reports through
        // the `playing` branch below, so a scrub while idle or paused moved
        // the model without the readout, the fill bar or the phase label ever
        // catching up.
        setProgress(sequence.progress);
        // The clip owns every node transform, so an explode measured against
        // the old pose is stale the moment the playhead moves.
        explodeHome.current = false;
      }
      if (store.playback === 'playing') {
        sequence.start();
        sequence.update(delta);
        setProgress(sequence.progress);
      } else if (store.playback === 'paused') {
        sequence.pause();
      }
    }

    // Explode is eased here rather than with a tween per object: 3000 GSAP
    // tweens would cost more than the render itself.
    const target = store.explodeFactor;

    // Snapshot the rest pose the moment an explode leaves zero. Doing it here
    // rather than at mount is what makes the offsets relative to whatever the
    // construction clip last wrote, instead of to its parked first frame.
    if (target > 0 && !explodeHome.current) {
      for (const record of explodeRef.current) {
        record.home.copy(record.object.position);
      }
      explodeHome.current = true;
    }

    if (Math.abs(appliedExplode.current - target) > 0.001) {
      appliedExplode.current = MathUtils.damp(
        appliedExplode.current,
        target,
        4,
        delta,
      );
      // Damping is asymptotic; snap the last fraction so a collapsed explode
      // leaves the members exactly where they started rather than a few
      // millimetres out, which would accumulate over repeated toggles.
      if (Math.abs(appliedExplode.current - target) <= 0.002) {
        appliedExplode.current = target;
      }
      for (const record of explodeRef.current) {
        record.object.position
          .copy(record.home)
          .addScaledVector(record.offset, appliedExplode.current);
      }
      if (appliedExplode.current === 0) explodeHome.current = false;
    }
  });

  // --- interaction -------------------------------------------------------
  const onClick = useMemo(
    () => (event: ThreeEvent<MouseEvent>) => {
      const store = useViewerStore.getState();
      if (store.measuring) return;          // the measure tool owns clicks

      event.stopPropagation();
      const object = event.object;
      const data = componentData(object);
      if (!data) return;

      const info: ComponentInfo = {
        ...data,
        name: object.name,
        length: memberLength(object),
        // Status comes from the timeline, not the model: anything already
        // placed at the current playback position counts as installed.
        status:
          store.progress >= 0.999 || store.playback === 'idle'
            ? 'Installed'
            : store.progress > 0
              ? 'In progress'
              : 'Not started',
        object,
      };
      select(info);
    },
    [select],
  );

  /**
   * Measurement picking.
   *
   * The measure tool draws its own result but cannot capture its own input:
   * an invisible catcher plane large enough to sit in front of the frame
   * would swallow every selection click. So the model itself is the capture
   * surface, and the hit point comes from the raycast rather than from the
   * object's origin - a site dimension is between the faces you pointed at,
   * not between centroids half a section depth away.
   */
  const onPointerDown = useMemo(
    () => (event: ThreeEvent<PointerEvent>) => {
      const store = useViewerStore.getState();
      if (!store.measuring) return;
      event.stopPropagation();
      store.addMeasurePoint({
        position: [event.point.x, event.point.y, event.point.z],
        objectName: event.object.name,
      });
    },
    [],
  );

  const onPointerOver = useMemo(
    () => (event: ThreeEvent<PointerEvent>) => {
      event.stopPropagation();
      hover(event.object.name);
      document.body.style.cursor = 'pointer';
    },
    [hover],
  );

  const onPointerOut = useMemo(
    () => () => {
      hover(null);
      document.body.style.cursor = 'auto';
    },
    [hover],
  );

  // Keep the camera's far plane honest for a 30 m model seen from 80 m.
  useEffect(() => {
    if ('far' in camera) {
      camera.far = 800;
      camera.updateProjectionMatrix();
    }
  }, [camera]);

  return (
    <primitive
      object={scene}
      onClick={onClick}
      onPointerDown={onPointerDown}
      onPointerOver={onPointerOver}
      onPointerOut={onPointerOut}
    />
  );
}
