import { useEffect, useRef } from 'react';
import { useThree } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import { Box3, Vector3 } from 'three';
import gsap from 'gsap';
import { useViewerStore } from '../store/useViewerStore';
import type { CameraShot } from '../types';

/**
 * Camera shots in model coordinates, Y-up (the glTF exporter converted the
 * Blender Z-up scene on the way out, so height is +Y and the footprint lies
 * in XZ). These mirror blender/scene_setup.py so a still and the web view
 * frame the building the same way.
 */
const SHOTS: Record<CameraShot, { position: Vector3; target: Vector3 }> = {
  hero: {
    position: new Vector3(58, 22, 46),
    target: new Vector3(14.4, 6, -9),
  },
  // Every eye here sits above its own target. OrbitControls clamps the polar
  // angle to keep the camera out of the ground, so a shot authored level with
  // or below its target is silently unreachable: the controls pull it back up
  // and the move ends somewhere other than where it was written.
  corner: {
    position: new Vector3(34, 7.0, 22),
    target: new Vector3(10, 5.5, -4),
  },
  detail: {
    position: new Vector3(4.2, 4.6, 3.4),
    target: new Vector3(0.2, 3.4, 0),
  },
  elevation: {
    position: new Vector3(14.4, 7.2, 120),
    target: new Vector3(14.4, 6.8, -9),
  },
};

// GSAP's lag smoothing freezes its clock whenever a frame takes longer than
// half a second and then advances it by a nominal 33 ms. That is right for a
// DOM animation catching up after a stall, and wrong here: on a weak GPU this
// scene renders at 1-2 fps, and a 1.6 s camera move stretched to 33 ms per
// frame takes most of a minute. Camera moves should take the time they say
// they take, however slowly the scene draws.
gsap.ticker.lagSmoothing(0);

/**
 * Orbit controls plus GSAP-driven camera moves.
 *
 * GSAP animates the controls' *target* alongside the camera position. Moving
 * the camera alone makes the building swing wildly through frame, because
 * OrbitControls keeps looking at wherever the old target was.
 */
export function CameraRig() {
  const controls = useRef<OrbitControlsImpl>(null);
  const { camera } = useThree();
  const shot = useViewerStore((s) => s.shot);
  const shotNonce = useViewerStore((s) => s.shotNonce);
  const selected = useViewerStore((s) => s.selected);

  // --- named shots -------------------------------------------------------
  useEffect(() => {
    const config = SHOTS[shot];
    if (!config || !controls.current) return;

    const target = controls.current.target;
    gsap.killTweensOf([camera.position, target]);
    gsap.to(camera.position, {
      x: config.position.x,
      y: config.position.y,
      z: config.position.z,
      duration: 1.6,
      ease: 'power3.inOut',
      onUpdate: () => controls.current?.update(),
    });
    gsap.to(target, {
      x: config.target.x,
      y: config.target.y,
      z: config.target.z,
      duration: 1.6,
      ease: 'power3.inOut',
      onUpdate: () => controls.current?.update(),
    });
  }, [shot, shotNonce, camera]);

  // --- frame the selected component --------------------------------------
  useEffect(() => {
    if (!selected || !controls.current) return;

    const box = new Box3().setFromObject(selected.object);
    const centre = box.getCenter(new Vector3());
    const radius = Math.max(box.getSize(new Vector3()).length() * 0.5, 0.5);

    // Approach along the existing view direction rather than a fixed vector,
    // so selecting a component feels like moving closer to what you are
    // already looking at instead of being teleported to the far side.
    const direction = camera.position
      .clone()
      .sub(controls.current.target)
      .normalize();
    const distance = Math.max(radius * 4.5, 3);
    const destination = centre.clone().addScaledVector(direction, distance);

    const target = controls.current.target;
    gsap.killTweensOf([camera.position, target]);
    gsap.to(camera.position, {
      x: destination.x,
      y: destination.y,
      z: destination.z,
      duration: 1.1,
      ease: 'power2.inOut',
      onUpdate: () => controls.current?.update(),
    });
    gsap.to(target, {
      x: centre.x,
      y: centre.y,
      z: centre.z,
      duration: 1.1,
      ease: 'power2.inOut',
      onUpdate: () => controls.current?.update(),
    });
  }, [selected, camera]);

  return (
    <OrbitControls
      ref={controls}
      makeDefault
      enableDamping
      dampingFactor={0.08}
      minDistance={2}
      maxDistance={220}
      // Stop the camera going under its target, which for targets 3-7 m up
      // keeps it well clear of the ground plane: looking up at a building
      // through its own foundations is the classic broken-orbit look. The
      // limit is exactly a right angle rather than just under it so a level
      // elevation shot is reachable.
      maxPolarAngle={Math.PI / 2}
      target={SHOTS.hero.target.clone()}
    />
  );
}
