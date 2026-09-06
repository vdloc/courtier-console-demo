import { AnimationMixer, LoopOnce } from 'three';
import type { AnimationClip, Object3D } from 'three';

/**
 * Playback controller for the single scene-level construction clip.
 *
 * The Blender export deliberately produces ONE clip covering every object
 * (`export_animation_mode="SCENE"`), so start/pause/reset are three calls on
 * one action rather than an orchestration problem across 3000 of them.
 *
 * `clampWhenFinished` plus `LoopOnce` is what leaves the finished structure
 * standing at the end. The default loop behaviour would snap the whole frame
 * back to its parked state the instant it completed, which reads as the model
 * collapsing.
 */
export class ConstructionSequence {
  readonly mixer: AnimationMixer;
  private readonly action;
  readonly duration: number;

  constructor(root: Object3D, clips: AnimationClip[]) {
    this.mixer = new AnimationMixer(root);
    const clip = clips[0];
    this.action = this.mixer.clipAction(clip);
    this.action.setLoop(LoopOnce, 1);
    this.action.clampWhenFinished = true;
    this.duration = clip.duration;
  }

  start() {
    this.action.paused = false;
    if (!this.action.isRunning()) {
      this.action.play();
    }
  }

  pause() {
    this.action.paused = true;
  }

  /** Rewind to the parked state and hold there. */
  reset() {
    this.action.stop();
    this.action.reset();
    this.action.play();
    this.seek(0);
    this.action.paused = true;
  }

  /** Jump to a normalised 0-1 position without changing play state. */
  seek(normalised: number) {
    const time = Math.max(0, Math.min(1, normalised)) * this.duration;
    const wasPaused = this.action.paused;

    if (!this.action.isRunning()) this.action.play();

    // The action has to be unpaused across the evaluation: the mixer skips
    // paused actions, so setting `time` on a paused action moves the playhead
    // without ever writing the transforms - the timeline updates and nothing
    // on screen moves.
    this.action.paused = false;
    this.action.time = time;
    this.mixer.update(0);
    this.action.paused = wasPaused;
  }

  /** Normalised 0-1 playback position. */
  get progress(): number {
    return this.duration > 0 ? this.action.time / this.duration : 0;
  }

  update(delta: number) {
    this.mixer.update(delta);
  }

  dispose() {
    this.mixer.stopAllAction();
    this.mixer.uncacheRoot(this.mixer.getRoot() as Object3D);
  }
}
