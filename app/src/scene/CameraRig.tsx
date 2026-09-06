import { useEffect, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import { PerspectiveCamera, Vector3 } from 'three';
import gsap from 'gsap';
import { useViewerStore } from '../store/useViewerStore';
import { CameraManager, SHOTS } from './CameraManager';

// GSAP's lag smoothing freezes its clock whenever a frame takes longer than
// half a second and then advances it by a nominal 33 ms. That is right for a
// DOM animation catching up after a stall and wrong here: on a weak GPU this
// scene renders at one or two frames a second, and an eight-second camera move
// stretched to 33 ms per frame would take several minutes. Cinematic moves
// should take the time they say they take, however slowly the scene draws.
gsap.ticker.lagSmoothing(0);

/**
 * Wiring between the store and the camera manager.
 *
 * Deliberately thin: everything about how the camera actually moves lives in
 * CameraManager, which knows nothing about React or about this application's
 * store. The component's whole job is to own the OrbitControls instance, turn
 * store intent into manager calls, and drive `update` once per frame.
 */
export function CameraRig() {
  const controls = useRef<OrbitControlsImpl>(null);
  const manager = useRef<CameraManager | null>(null);
  const { camera } = useThree();

  const shot = useViewerStore((s) => s.shot);
  const shotNonce = useViewerStore((s) => s.shotNonce);
  const selected = useViewerStore((s) => s.selected);
  const touring = useViewerStore((s) => s.touring);
  const stopTour = useViewerStore((s) => s.stopTour);
  const setTourShot = useViewerStore((s) => s.setTourShot);

  // --- manager lifecycle -------------------------------------------------
  useEffect(() => {
    if (!controls.current || !(camera instanceof PerspectiveCamera)) return;
    // The model's centre of mass, in the Y-up coordinates the exporter wrote.
    // Every orbital path is built around it, so a wrong value here shows up as
    // paths that clip the building rather than arcing round it.
    const instance = new CameraManager(
      camera,
      controls.current,
      new Vector3(14.4, 6, -9),
    );
    manager.current = instance;

    // Test and profiling surface, alongside the renderer handle in Viewer.
    const viewer = (window as unknown as { __viewer?: Record<string, unknown> })
      .__viewer;
    if (viewer) viewer.cameraManager = instance;

    return () => {
      instance.dispose();
      manager.current = null;
      if (viewer) viewer.cameraManager = undefined;
    };
  }, [camera]);

  // --- named shots -------------------------------------------------------
  useEffect(() => {
    if (useViewerStore.getState().touring) return; // the tour owns the camera
    manager.current?.playShot(shot);
  }, [shot, shotNonce]);

  // --- focus the selected component --------------------------------------
  useEffect(() => {
    if (!selected || useViewerStore.getState().touring) return;
    manager.current?.focusObject(selected.object);
  }, [selected]);

  // --- the four-shot showcase --------------------------------------------
  useEffect(() => {
    const instance = manager.current;
    if (!instance) return;

    if (!touring) {
      // Only tear down a tour that is actually running: this effect also fires
      // on the initial false, and stopping there would cancel the opening
      // shot before it started.
      if (instance.isCinematic) {
        instance.stopSequence();
        instance.enableOrbit();
      }
      return;
    }

    instance.playSequence({
      onShot: (_, leg) => setTourShot(leg.name, leg.shallowFocus ?? false),
      onComplete: () => stopTour(),
    });

    return () => {
      instance.stopSequence();
      instance.enableOrbit();
    };
  }, [touring, setTourShot, stopTour]);

  // Frame order matters, and it is why this is split in two.
  //
  // drei's OrbitControls calls `controls.update()` from its own useFrame at
  // priority -1. If the breathing offset were still on the camera at that
  // moment, OrbitControls would read the wobbled position into its spherical
  // state and integrate it - the offset would compound into a slow wander
  // instead of staying a fixed few millimetres. So the offset comes off at
  // priority -2, before OrbitControls looks, and goes back on at 0, after.
  //
  // Priorities stay negative-or-zero deliberately: in R3F a positive priority
  // takes over the render loop entirely.
  useFrame(() => manager.current?.beginFrame(), -2);
  useFrame((_, delta) => manager.current?.update(delta), 0);

  return (
    <OrbitControls
      ref={controls}
      makeDefault
      enableDamping
      // Heavier than the drei default. This is a survey instrument on a gimbal,
      // not a game camera: the extra weight is most of what separates the two.
      dampingFactor={0.045}
      rotateSpeed={0.55}
      zoomSpeed={0.7}
      panSpeed={0.6}
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
