import { create } from 'zustand';
import type {
  CameraShot,
  ComponentInfo,
  LayerName,
  MeasurementPoint,
  TimelineManifest,
} from '../types';
import { LAYERS } from '../types';

/**
 * Single source of truth for everything the UI and the scene must agree on.
 *
 * The rule that keeps this manageable: the store holds *intent* - which
 * layers are on, whether the sequence is playing, what is selected - and
 * never owns the lifecycle of a Three.js object. The one exception is
 * `selected.object`, a borrowed reference used to frame the camera and draw
 * the outline, cleared whenever the model reloads.
 */

export type PlaybackState = 'idle' | 'playing' | 'paused' | 'finished';

interface ViewerState {
  // --- model ------------------------------------------------------------
  ready: boolean;
  loadProgress: number;
  timeline: TimelineManifest | null;

  // --- selection --------------------------------------------------------
  selected: ComponentInfo | null;
  hovered: string | null;

  // --- layers -----------------------------------------------------------
  layers: Record<LayerName, boolean>;

  // --- construction sequence -------------------------------------------
  playback: PlaybackState;
  /** Normalised 0-1 position in the clip, driven by the mixer each frame. */
  progress: number;
  /** Set when the user scrubs; consumed and cleared by the scene. */
  seekRequest: number | null;

  // --- presentation -----------------------------------------------------
  exploded: boolean;
  explodeFactor: number;
  shot: CameraShot;
  /** Bumped to re-trigger a camera move even when the shot is unchanged. */
  shotNonce: number;
  measuring: boolean;
  measurePoints: MeasurementPoint[];
  quality: 'high' | 'balanced' | 'performance';

  // --- cinematic tour ----------------------------------------------------
  /** Whether the four-shot showcase is running. */
  touring: boolean;
  /** Name of the leg currently on screen, for the caption. */
  tourShot: string | null;
  /**
   * Whether the current leg calls for the shallow-focus look. Held here
   * rather than read from the camera so the post stack does not have to reach
   * into the scene graph for it.
   */
  shallowFocus: boolean;

  // --- actions ----------------------------------------------------------
  setReady: (ready: boolean) => void;
  setLoadProgress: (value: number) => void;
  setTimeline: (timeline: TimelineManifest) => void;

  select: (info: ComponentInfo | null) => void;
  hover: (name: string | null) => void;

  toggleLayer: (layer: LayerName) => void;
  setAllLayers: (visible: boolean) => void;

  startConstruction: () => void;
  pauseConstruction: () => void;
  resetConstruction: () => void;
  setProgress: (value: number) => void;
  requestSeek: (value: number) => void;
  clearSeek: () => void;

  toggleExplode: () => void;
  setExplodeFactor: (value: number) => void;
  setShot: (shot: CameraShot) => void;
  toggleMeasuring: () => void;
  addMeasurePoint: (point: MeasurementPoint) => void;
  clearMeasurement: () => void;
  setQuality: (quality: ViewerState['quality']) => void;
  startTour: () => void;
  stopTour: () => void;
  setTourShot: (name: string | null, shallowFocus: boolean) => void;
  resetView: () => void;
}

const allLayersVisible = () =>
  Object.fromEntries(LAYERS.map((layer) => [layer, true])) as Record<
    LayerName,
    boolean
  >;

export const useViewerStore = create<ViewerState>((set) => ({
  ready: false,
  loadProgress: 0,
  timeline: null,

  selected: null,
  hovered: null,

  layers: allLayersVisible(),

  playback: 'idle',
  progress: 0,
  seekRequest: null,

  exploded: false,
  explodeFactor: 0,
  shot: 'hero',
  shotNonce: 0,
  measuring: false,
  measurePoints: [],
  // Balanced by default: 'high' turns on contact shadows and the widest LOD
  // distances, which is a deliberate choice rather than a starting point.
  quality: 'balanced',

  touring: false,
  tourShot: null,
  shallowFocus: false,

  setReady: (ready) => set({ ready }),
  setLoadProgress: (loadProgress) => set({ loadProgress }),
  setTimeline: (timeline) => set({ timeline }),

  select: (selected) => set({ selected }),
  hover: (hovered) => set({ hovered }),

  toggleLayer: (layer) =>
    set((state) => ({
      layers: { ...state.layers, [layer]: !state.layers[layer] },
    })),
  setAllLayers: (visible) =>
    set({
      layers: Object.fromEntries(
        LAYERS.map((layer) => [layer, visible]),
      ) as Record<LayerName, boolean>,
    }),

  // Start from the beginning when idle or finished, resume when paused.
  // Without that distinction, pressing play after a completed run leaves the
  // sequence parked on the last frame doing nothing.
  startConstruction: () =>
    set((state) => ({
      playback: 'playing',
      seekRequest: state.playback === 'paused' ? state.seekRequest : 0,
      // A half-assembled exploded model reads as a bug, not a feature.
      exploded: false,
      explodeFactor: 0,
    })),
  pauseConstruction: () =>
    set((state) => ({
      playback: state.playback === 'playing' ? 'paused' : state.playback,
    })),
  resetConstruction: () =>
    set({ playback: 'idle', progress: 0, seekRequest: 0 }),
  setProgress: (progress) =>
    set((state) => ({
      progress,
      playback:
        progress >= 1 && state.playback === 'playing'
          ? 'finished'
          : state.playback,
    })),
  requestSeek: (seekRequest) => set({ seekRequest }),
  clearSeek: () => set({ seekRequest: null }),

  toggleExplode: () =>
    set((state) => {
      const exploded = !state.exploded;
      return {
        exploded,
        explodeFactor: exploded ? 1 : 0,
        // Explode and the construction clip both write object positions, so
        // only one of them can own the transform at a time.
        playback: exploded ? 'idle' : state.playback,
      };
    }),
  setExplodeFactor: (explodeFactor) => set({ explodeFactor }),
  setShot: (shot) => set((state) => ({ shot, shotNonce: state.shotNonce + 1 })),
  toggleMeasuring: () =>
    set((state) => ({
      measuring: !state.measuring,
      measurePoints: state.measuring ? [] : state.measurePoints,
    })),
  addMeasurePoint: (point) =>
    set((state) => ({
      // Two points make a measurement; a third starts a new one.
      measurePoints:
        state.measurePoints.length >= 2
          ? [point]
          : [...state.measurePoints, point],
    })),
  clearMeasurement: () => set({ measurePoints: [] }),
  setQuality: (quality) => set({ quality }),

  // The tour drives the camera and takes the controls away while it runs, so
  // it clears anything that would fight it for the frame.
  startTour: () =>
    set({
      touring: true,
      selected: null,
      exploded: false,
      explodeFactor: 0,
      measuring: false,
      measurePoints: [],
    }),
  stopTour: () => set({ touring: false, tourShot: null, shallowFocus: false }),
  setTourShot: (tourShot, shallowFocus) => set({ tourShot, shallowFocus }),

  resetView: () =>
    set((state) => ({
      selected: null,
      hovered: null,
      exploded: false,
      explodeFactor: 0,
      measuring: false,
      measurePoints: [],
      touring: false,
      tourShot: null,
      shallowFocus: false,
      layers: allLayersVisible(),
      // Reset the VIEW, not the building. Seeking to 0 here would park every
      // member at the construction clip's first frame - underground and at
      // one-thousandth scale - so "Reset View" would empty the site, which is
      // the opposite of the state the viewer deliberately opens in. Rewinding
      // the sequence is what the timeline's own Reset is for.
      playback: 'idle',
      progress: 1,
      seekRequest: 1,
      shot: 'hero',
      shotNonce: state.shotNonce + 1,
    })),
}));
