import {
  Box3,
  CatmullRomCurve3,
  Euler,
  MathUtils,
  Matrix4,
  Object3D,
  PerspectiveCamera,
  Quaternion,
  Vector3,
} from 'three';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import gsap from 'gsap';

/**
 * Camera manager: cinematic shots, object focus and user orbit in one place.
 *
 * WHAT THIS REPLACES, AND WHY THE OLD RIG LOOKED ROBOTIC
 *
 * The previous implementation tweened `camera.position.x/y/z` as three
 * independent scalars. Three problems follow from that, and between them they
 * are the whole reason the movement read as a developer demo:
 *
 * 1. Independent Cartesian tweens move the camera along the straight chord
 *    between two points. The shortest route from a wide hero angle to a joint
 *    close-up therefore passes THROUGH the building, and the distance to the
 *    subject dips in the middle of every move - an accidental dolly zoom.
 *
 * 2. Rotation was never animated at all. OrbitControls derives the look
 *    direction from position minus target, so angular velocity peaked at
 *    exactly the moment linear velocity did: a whip-pan through the middle of
 *    every transition, with no way to shape it.
 *
 * 3. Every shot used the same 1.6 s duration regardless of distance. A 30 m
 *    reframe and an 80 m pull-back travelled at wildly different speeds, which
 *    is the loudest "interpolated by a computer" tell of the three.
 *
 * HOW THIS WORKS INSTEAD
 *
 * - Paths are `CatmullRomCurve3` splines built in POLAR space about the model
 *   centre - azimuth, radius and height are interpolated, never x/y/z - so
 *   every move arcs around the structure and holds its distance to the
 *   subject.
 * - Curves are sampled with `getPointAt`, which is arc-length parameterised.
 *   One eased scalar then gives constant screen speed; raw `getPoint` would
 *   reintroduce the uneven pacing the spline exists to remove.
 * - Orientation is animated independently of position, by slerping the camera
 *   quaternion toward a look-at built from a SMOOTHED target, so rotation lags
 *   position slightly - which is what a real operator does.
 * - The target is lerped, never assigned, on its own curve and its own
 *   duration, landing before the camera so the subject is framed on arrival.
 * - Duration derives from path length and sweep, clamped to a slow, heavy
 *   range: this is an industrial inspection drone, not a racing drone.
 * - Momentum carries a settling move past its end and decays exponentially,
 *   so nothing ever stops dead.
 * - A breathing layer adds sub-centimetre position drift and a couple of
 *   thousandths of a radian of rotation variation. Deliberately below the
 *   threshold of "shaky": it should be felt, not seen.
 *
 * ORBITCONTROLS INTEGRATION
 *
 * The controls are switched OFF for the duration of a cinematic move, so user
 * input and the animation never write the camera in the same frame. Handing
 * control back re-derives `controls.target` from where the camera is actually
 * looking, which is what makes the transfer jump-free: OrbitControls' first
 * update then reproduces the exact orientation the animation ended on.
 */

export type ShotId = 'hero' | 'corner' | 'detail' | 'elevation';

export interface Shot {
  position: Vector3;
  target: Vector3;
}

/**
 * Named shots in model coordinates, Y-up (the glTF exporter converted the
 * Blender Z-up scene on export, so height is +Y and the footprint lies in XZ).
 * These mirror blender/scene_setup.py so a still and the web view frame the
 * building the same way.
 *
 * Every eye sits above its own target. OrbitControls clamps the polar angle to
 * keep the camera out of the ground, so a shot authored level with or below
 * its target is silently unreachable - the clamp drags it back up and the move
 * ends somewhere other than where it was written.
 */
export const SHOTS: Record<ShotId, Shot> = {
  hero: {
    position: new Vector3(58, 22, 46),
    target: new Vector3(14.4, 6, -9),
  },
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

export interface SequenceShot {
  name: string;
  /** Seconds of travel for this leg. */
  duration: number;
  shot: Shot;
  /** Extra azimuth swept on the way, in radians. Positive is clockwise. */
  orbit?: number;
  /** Seconds held at the end before the next leg begins. */
  hold?: number;
  /** Whether the shallow-focus look is on for this leg. */
  shallowFocus?: boolean;
}

/**
 * The four-shot engineering showcase.
 *
 * Paced as an industrial documentary rather than a product trailer: each leg
 * ends on a short hold, which is what gives the sequence its beats. The holds
 * are not dead air - the breathing layer is still running underneath them - so
 * it reads as one continuously flown take with pauses, not as four cuts.
 */
export const SEQUENCE: SequenceShot[] = [
  {
    name: 'Hero introduction',
    duration: 8,
    // Wide and high, easing forward into the frame rather than sitting still.
    shot: {
      position: new Vector3(52, 26, 44),
      target: new Vector3(14.4, 7.5, -9),
    },
    orbit: -0.32,
    hold: 0.6,
  },
  {
    name: 'Structural inspection',
    duration: 10,
    // Down to working height and round the frame, past the column line.
    shot: {
      position: new Vector3(20, 10.5, 15),
      target: new Vector3(8, 6.5, -5),
    },
    orbit: -1.15,
    hold: 0.8,
  },
  {
    name: 'Connection detail',
    duration: 8,
    // In on a beam-to-column joint at first-floor level.
    shot: {
      position: new Vector3(5.4, 5.0, 4.0),
      target: new Vector3(0.4, 3.6, 0.1),
    },
    hold: 1.4,
    shallowFocus: true,
  },
  {
    name: 'Full structure reveal',
    duration: 10,
    // Pull back and up, opening out to the complete frame.
    shot: {
      position: new Vector3(64, 27, 52),
      target: new Vector3(14.4, 6.5, -9),
    },
    orbit: 0.5,
    hold: 0,
  },
];

type Polar = { azimuth: number; radius: number; height: number };

function toPolar(point: Vector3, centre: Vector3): Polar {
  const dx = point.x - centre.x;
  const dz = point.z - centre.z;
  return {
    azimuth: Math.atan2(dx, dz),
    radius: Math.hypot(dx, dz),
    height: point.y,
  };
}

function fromPolar(polar: Polar, centre: Vector3): Vector3 {
  return new Vector3(
    centre.x + Math.sin(polar.azimuth) * polar.radius,
    polar.height,
    centre.z + Math.cos(polar.azimuth) * polar.radius,
  );
}

/** Shortest signed angular distance, so an arc never takes the long way. */
function shortestAngle(from: number, to: number): number {
  let delta = (to - from) % (Math.PI * 2);
  if (delta > Math.PI) delta -= Math.PI * 2;
  if (delta < -Math.PI) delta += Math.PI * 2;
  return delta;
}

export interface MoveOptions {
  /** Overrides the length-derived duration, in seconds. */
  duration?: number;
  /** Holds the drift off for a beat after arrival - an inspection moment. */
  dwell?: number;
  /** Easing override; defaults to the length-appropriate cinematic curve. */
  ease?: string;
  /** Extra azimuth swept on the way, in radians. Positive is clockwise. */
  orbit?: number;
  /** Hands control back to the user once the move settles. */
  releaseControl?: boolean;
  onArrive?: () => void;
}

export class CameraManager {
  private readonly camera: PerspectiveCamera;
  private readonly controls: OrbitControlsImpl;
  private readonly centre: Vector3;

  /** Where the path says the camera is, before drift and breathing. */
  private readonly basePosition = new Vector3();
  /** The offset currently added on top, removed again before each update. */
  private readonly appliedOffset = new Vector3();

  /** Authoritative aim point. `smoothTarget` chases it; nothing snaps. */
  private readonly desiredTarget = new Vector3();
  private readonly smoothTarget = new Vector3();

  /** Residual velocity carried past the end of a move, in metres/second. */
  private readonly momentum = new Vector3();

  private positionTween: gsap.core.Tween | null = null;
  private targetTween: gsap.core.Tween | null = null;
  private timeline: gsap.core.Timeline | null = null;

  /**
   * The path being flown and the eased scalar along it.
   *
   * GSAP owns the scalar; the curve is sampled here, during the frame, rather
   * than in the tween's own `onUpdate`. GSAP ticks on its own rAF callback, so
   * sampling there would leave the camera rendering one frame behind the path
   * - imperceptible at 60 fps, and a visible lurch on a slow client, most
   * obviously at the moment a move is interrupted and control is handed back.
   */
  private activePath: CatmullRomCurve3 | null = null;
  private activeDriver: { t: number } | null = null;
  private activeTargetPath: CatmullRomCurve3 | null = null;
  private activeTargetDriver: { t: number } | null = null;

  private cinematic = false;
  private userHasControl = false;
  private idleFor = 0;
  private driftMix = 0;
  private phase = 0;
  private dwellFor = 0;

  /** Seconds of stillness before the idle drift eases in. */
  private readonly driftDelay = 3.5;
  /** Radians per second of idle orbit at full mix - about half a degree. */
  private readonly driftRate = 0.0085;

  private readonly scratchMatrix = new Matrix4();
  private readonly scratchQuaternion = new Quaternion();
  private readonly wobbleQuaternion = new Quaternion();
  private readonly wobbleEuler = new Euler();
  private readonly scratchVector = new Vector3();
  private readonly lastPosition = new Vector3();

  private readonly onControlStart = () => {
    // A hand on the controls outranks anything the manager is doing.
    this.userHasControl = true;
    this.stop();
  };
  private readonly onControlEnd = () => {
    this.userHasControl = false;
    this.idleFor = 0;
    this.desiredTarget.copy(this.controls.target);
    this.smoothTarget.copy(this.controls.target);
  };

  constructor(
    camera: PerspectiveCamera,
    controls: OrbitControlsImpl,
    centre: Vector3,
  ) {
    this.camera = camera;
    this.controls = controls;
    this.centre = centre.clone();
    this.basePosition.copy(camera.position);
    this.lastPosition.copy(camera.position);
    this.desiredTarget.copy(controls.target);
    this.smoothTarget.copy(controls.target);
    this.controls.addEventListener('start', this.onControlStart);
    this.controls.addEventListener('end', this.onControlEnd);
  }

  get isMoving(): boolean {
    return (
      (this.timeline?.isActive() ?? false) ||
      (this.positionTween?.isActive() ?? false) ||
      (this.targetTween?.isActive() ?? false)
    );
  }

  get isCinematic(): boolean {
    return this.cinematic;
  }

  /** Distance from the camera to what it is aiming at, for the focus plane. */
  get focusDistance(): number {
    return this.camera.position.distanceTo(this.smoothTarget);
  }

  // -----------------------------------------------------------------------
  // Public API
  // -----------------------------------------------------------------------

  /** Fly to a named shot, or to an explicit one. */
  playShot(shot: ShotId | Shot, options: MoveOptions = {}): number {
    const resolved = typeof shot === 'string' ? SHOTS[shot] : shot;
    return this.moveTo(resolved, { releaseControl: true, ...options });
  }

  /**
   * Frame a component and hold on it.
   *
   * Distance comes from the object's own bounding sphere and the camera's
   * field of view, so a 300 mm bolt and an 8.5 m beam both end up filling a
   * comparable share of frame instead of one being a speck and the other
   * overflowing.
   *
   * The approach angle is nudged off-axis rather than taken straight from
   * wherever the viewer happened to be: a member seen dead-on reads as a flat
   * rectangle, and the point of focusing it is to show it is a fabricated
   * section.
   */
  focusObject(object: Object3D, options: MoveOptions = {}): number {
    const box = new Box3().setFromObject(object);
    if (box.isEmpty()) return 0;

    const centre = box.getCenter(new Vector3());
    const radius = Math.max(box.getSize(new Vector3()).length() * 0.5, 0.25);

    // Fit the bounding sphere to the narrower of the two frame axes, with
    // headroom so the member is not jammed against the edge.
    const vFov = MathUtils.degToRad(this.camera.fov);
    const hFov = 2 * Math.atan(Math.tan(vFov / 2) * this.camera.aspect);
    const fit = radius / Math.sin(Math.min(vFov, hFov) / 2);
    const distance = MathUtils.clamp(fit * 1.35, 2.4, 70);

    // Start from the current view direction so the move feels like stepping
    // closer to what is already in front of you, then rotate it off-axis and
    // lift it: the standard three-quarter inspection view.
    const direction = this.camera.position
      .clone()
      .sub(this.smoothTarget)
      .setY(0);
    if (direction.lengthSq() < 1e-6) direction.set(0.6, 0, 0.8);
    direction.normalize().applyAxisAngle(new Vector3(0, 1, 0), 0.42);
    direction.y = 0.38;
    direction.normalize();

    return this.moveTo(
      {
        position: centre.clone().addScaledVector(direction, distance),
        target: centre,
      },
      {
        // Slow and deliberate: an inspection, not a snap-to.
        duration: MathUtils.clamp(2.4 + radius * 0.22, 2.4, 4.2),
        dwell: 3,
        releaseControl: true,
        ...options,
      },
    );
  }

  /**
   * Hand control back to the user without a jump.
   *
   * The target is re-derived from where the camera is actually looking, at the
   * distance it is actually looking from. OrbitControls' next update then
   * reproduces the current orientation exactly, so nothing snaps at the moment
   * input goes live.
   */
  enableOrbit() {
    this.cinematic = false;
    this.syncControlsToCamera();
    this.controls.enabled = true;
  }

  /** Take input away for the duration of an animation. */
  disableOrbit() {
    this.cinematic = true;
    this.controls.enabled = false;
  }

  /** Return to the hero shot and give the controls back. */
  reset(): number {
    this.stopSequence();
    return this.playShot('hero');
  }

  /**
   * Play the four-shot showcase as one continuous take.
   *
   * Built as a GSAP timeline of legs rather than four independent moves, so
   * the whole thing can be killed as a unit and each leg starts from exactly
   * where the previous one settled. There is no cut anywhere in it.
   */
  playSequence(
    callbacks: {
      onShot?: (index: number, shot: SequenceShot) => void;
      onComplete?: () => void;
    } = {},
  ): number {
    this.stopSequence();
    this.disableOrbit();

    const timeline = gsap.timeline({
      onComplete: () => {
        this.timeline = null;
        this.enableOrbit();
        callbacks.onComplete?.();
      },
    });

    let cursor = 0;
    for (const [index, leg] of SEQUENCE.entries()) {
      timeline.call(
        () => {
          callbacks.onShot?.(index, leg);
          this.moveTo(leg.shot, {
            duration: leg.duration,
            orbit: leg.orbit,
            dwell: leg.hold,
            // Long legs need the deep settle of power2; the detail push is
            // short enough that power3's harder shoulders read as deliberate.
            ease: leg.duration >= 9 ? 'power2.inOut' : 'power3.inOut',
          });
        },
        undefined,
        cursor,
      );
      cursor += leg.duration + (leg.hold ?? 0);
    }

    // Hold the timeline open for the final leg's travel.
    timeline.to({}, { duration: cursor });
    this.timeline = timeline;
    return cursor;
  }

  stopSequence() {
    this.timeline?.kill();
    this.timeline = null;
    this.stop();
  }

  /** Kill any running move and clear the drift. */
  stop() {
    this.positionTween?.kill();
    this.targetTween?.kill();
    this.positionTween = null;
    this.targetTween = null;
    this.activePath = null;
    this.activeDriver = null;
    this.activeTargetPath = null;
    this.activeTargetDriver = null;
    this.driftMix = 0;
    this.dwellFor = 0;
    this.idleFor = 0;
    // Momentum deliberately survives: interrupting a move mid-flight should
    // coast to a stop, not stop dead. It is cleared on natural completion and
    // ignored entirely while the user is driving.
  }

  // -----------------------------------------------------------------------
  // Movement
  // -----------------------------------------------------------------------

  private moveTo(shot: Shot, options: MoveOptions = {}): number {
    this.stop();
    this.disableOrbit();
    this.userHasControl = false;

    const from = this.camera.position.clone();
    const to = shot.position.clone();
    const targetFrom = this.smoothTarget.clone();
    const targetTo = shot.target.clone();

    const path = this.buildPath(from, to, options.orbit);
    const sweep =
      options.orbit !== undefined
        ? Math.abs(options.orbit)
        : Math.abs(
            shortestAngle(
              toPolar(from, this.centre).azimuth,
              toPolar(to, this.centre).azimuth,
            ),
          );
    const length = path.getLength();

    // Heavy and slow by design. The floor stops a nudge from snapping, the
    // ceiling stops a long pull-back becoming a screensaver, and the
    // coefficients are tuned for an inspection drone carrying a real payload.
    const duration =
      options.duration ??
      MathUtils.clamp(2.0 + length * 0.055 + sweep * 0.9, 2.6, 7.5);

    const driver = { t: 0 };
    this.activePath = path;
    this.activeDriver = driver;

    this.positionTween = gsap.to(driver, {
      t: 1,
      duration,
      ease: options.ease ?? (length > 14 ? 'power2.inOut' : 'sine.inOut'),
      onComplete: () => {
        this.basePosition.copy(to);
        this.activePath = null;
        this.activeDriver = null;
        // A move that ran to completion has already decelerated to rest - the
        // easing did that. Coasting on from here would overshoot the shot it
        // just landed. Momentum is for INTERRUPTED moves only.
        this.momentum.set(0, 0, 0);
        this.idleFor = 0;
        this.dwellFor = options.dwell ?? 0;
        if (options.releaseControl) this.enableOrbit();
        options.onArrive?.();
      },
    });

    // The target takes a shallower arc of its own - lifted a little at the
    // midpoint so the framing rises through the move rather than tracking a
    // dead straight line - and it lands before the camera does.
    const targetPath = new CatmullRomCurve3(
      [
        targetFrom,
        targetFrom
          .clone()
          .lerp(targetTo, 0.5)
          .add(new Vector3(0, targetFrom.distanceTo(targetTo) * 0.08, 0)),
        targetTo,
      ],
      false,
      'centripetal',
      0.5,
    );
    const targetDriver = { t: 0 };
    this.activeTargetPath = targetPath;
    this.activeTargetDriver = targetDriver;

    this.targetTween = gsap.to(targetDriver, {
      t: 1,
      duration: duration * 0.86,
      ease: 'sine.inOut',
      onComplete: () => {
        this.desiredTarget.copy(targetTo);
        this.activeTargetPath = null;
        this.activeTargetDriver = null;
      },
    });

    return duration;
  }

  /**
   * Spline through polar space.
   *
   * Interior control points sit a third and two thirds of the way round,
   * pushed outward and lifted by an amount that scales with how much azimuth
   * the move covers. A move that barely turns stays nearly straight; one that
   * swings past two faces of the building takes a wide, high road around them.
   */
  private buildPath(from: Vector3, to: Vector3, orbit?: number) {
    const a = toPolar(from, this.centre);
    const b = toPolar(to, this.centre);
    const control: Vector3[] = [];

    if (orbit) {
      // An explicit orbit needs waypoints the whole way round, or the spline
      // shortcuts across the chord and the reveal never actually travels.
      const steps = Math.max(3, Math.ceil(Math.abs(orbit) / 0.4));
      for (let i = 1; i < steps; i += 1) {
        const t = i / steps;
        control.push(
          fromPolar(
            {
              azimuth: a.azimuth + orbit * t,
              radius: MathUtils.lerp(a.radius, b.radius, t),
              height: MathUtils.lerp(a.height, b.height, t),
            },
            this.centre,
          ),
        );
      }
    } else {
      const sweep = shortestAngle(a.azimuth, b.azimuth);
      const bulge = 0.06 + 0.3 * Math.abs(sweep / Math.PI);
      const lift = Math.min(from.distanceTo(to) * 0.12, 9);
      for (const t of [0.34, 0.68]) {
        const shape = Math.sin(Math.PI * t); // zero at the ends, peak mid-path
        control.push(
          fromPolar(
            {
              azimuth: a.azimuth + sweep * t,
              radius:
                MathUtils.lerp(a.radius, b.radius, t) * (1 + bulge * shape),
              height: MathUtils.lerp(a.height, b.height, t) + lift * shape,
            },
            this.centre,
          ),
        );
      }
    }

    // Centripetal parameterisation: with outward-bulged control points the
    // uniform variant overshoots into visible cusps at the corners.
    return new CatmullRomCurve3(
      [from, ...control, to],
      false,
      'centripetal',
      0.5,
    );
  }

  // -----------------------------------------------------------------------
  // Per-frame
  // -----------------------------------------------------------------------

  /**
   * Strip the breathing offset before anything else reads the camera.
   *
   * Called at the very start of the frame, ahead of OrbitControls' own update.
   * If the offset were still applied when OrbitControls read the position, it
   * would be integrated into the controls' spherical state and compound into a
   * slow wander - the offset has to be a pure per-frame decoration, never part
   * of the camera's persistent state.
   */
  beginFrame() {
    this.camera.position.sub(this.appliedOffset);
    this.appliedOffset.set(0, 0, 0);
  }

  /**
   * Called once per rendered frame from the render loop, not from GSAP, so the
   * drift and the imperfection layer compose with OrbitControls' damping
   * instead of fighting it.
   */
  update(delta: number) {
    const step = Math.min(delta, 0.1); // a stalled tab must not teleport it
    const moving = this.isMoving;

    // Sample the curves for THIS frame, from the scalars GSAP has advanced.
    // getPointAt, not getPoint: arc-length parameterised sampling is what
    // turns one eased scalar into constant speed along the spline.
    if (this.activePath && this.activeDriver) {
      this.activePath.getPointAt(this.activeDriver.t, this.basePosition);
    }
    if (this.activeTargetPath && this.activeTargetDriver) {
      this.activeTargetPath.getPointAt(
        this.activeTargetDriver.t,
        this.desiredTarget,
      );
    }

    if (!this.cinematic && !moving) {
      // User mode: OrbitControls owns position and orientation, so the
      // manager's idea of both follows the controls rather than leading them.
      this.basePosition.copy(this.camera.position);
      this.desiredTarget.copy(this.controls.target);
    }

    // The aim point always chases; it is never assigned outright. This is what
    // keeps rotation smooth when the target jumps between components.
    this.smoothTarget.lerp(
      this.desiredTarget,
      1 - Math.exp(-3.5 * step), // frame-rate independent damping
    );

    if (moving) {
      this.idleFor = 0;
      this.driftMix = 0;
      // Momentum is sampled from the path itself, so whatever the easing was
      // doing when it ended is what carries through afterwards.
      this.momentum
        .copy(this.basePosition)
        .sub(this.lastPosition)
        .divideScalar(Math.max(step, 1e-4));
      // On a slow client one frame can span several metres of path, and the
      // average velocity across it is not the instantaneous velocity at the
      // end. Cap it, or an interruption at 1 fps flings the camera.
      if (this.momentum.length() > 12) this.momentum.setLength(12);
    } else {
      this.idleFor = this.userHasControl ? 0 : this.idleFor + step;

      // Inertia: the camera coasts to rest instead of stopping dead. 2.6 is
      // roughly a third of a second of visible follow-through - enough to feel
      // the mass, short enough never to look like drifting.
      if (!this.userHasControl && this.momentum.lengthSq() > 1e-5) {
        this.basePosition.addScaledVector(this.momentum, step);
        this.momentum.multiplyScalar(Math.exp(-2.6 * step));
      } else {
        this.momentum.set(0, 0, 0);
      }

      if (this.dwellFor > 0) {
        this.dwellFor = Math.max(0, this.dwellFor - step);
      } else if (this.idleFor > this.driftDelay && !this.userHasControl) {
        // Ease the drift in rather than switching it on. A camera that starts
        // moving at full rate the instant a timer fires is the same robotic
        // tell as a linear tween.
        this.driftMix = Math.min(1, this.driftMix + step * 0.35);
      }

      if (this.driftMix > 0) {
        const polar = toPolar(this.basePosition, this.smoothTarget);
        polar.azimuth += this.driftRate * this.driftMix * step;
        this.basePosition.copy(fromPolar(polar, this.smoothTarget));
      }
    }

    this.lastPosition.copy(this.basePosition);
    this.phase += step;

    if (this.cinematic) {
      // Cinematic mode owns the camera outright: OrbitControls is disabled, so
      // position and orientation are written here and nothing contends.
      this.camera.position.copy(this.basePosition);
      this.applyBreathing();
      this.applyLook(step);
    } else {
      // Orbit mode: OrbitControls has already run its own update this frame,
      // at priority -1. Calling it again here would integrate the damping
      // twice, so all that is left to do is lay the breathing on top.
      this.applyBreathing();
    }
  }

  /**
   * Sub-centimetre position drift and a slow vertical breath.
   *
   * Three sine terms on periods that do not divide into each other, so the
   * pattern never visibly repeats. The amplitudes are the point: 8 mm and 5 mm
   * on a building 29 m across is a fraction of a pixel at hero distance. It is
   * felt as "held by someone" rather than seen as shake, and it fades out
   * entirely while the user is driving.
   */
  private applyBreathing() {
    if (this.userHasControl) return;

    // Scale with distance to subject: a wobble invisible on a wide shot would
    // be seasickness in a close-up, so it shrinks as the camera closes in.
    const scale = MathUtils.clamp(this.focusDistance / 45, 0.25, 1);

    this.appliedOffset.set(
      Math.sin(this.phase * 0.37) * 0.008 * scale,
      Math.sin(this.phase * 0.23 + 1.7) * 0.005 * scale +
        Math.sin(this.phase * 0.11) * 0.003 * scale,
      Math.cos(this.phase * 0.31 + 0.6) * 0.008 * scale,
    );
    this.camera.position.add(this.appliedOffset);
  }

  /**
   * Orientation, animated independently of position.
   *
   * A look-at matrix gives the ideal quaternion for the smoothed target; the
   * camera slerps toward it rather than adopting it. That lag is what stops
   * rotation spiking at the same instant linear speed does - the whip-pan the
   * old rig produced on every move - and it lets a small rotation variation
   * ride on top without touching the path.
   */
  private applyLook(step: number) {
    this.scratchMatrix.lookAt(
      this.camera.position,
      this.smoothTarget,
      this.camera.up,
    );
    this.scratchQuaternion.setFromRotationMatrix(this.scratchMatrix);

    // A whisper of rotation variation, a couple of thousandths of a radian.
    this.wobbleEuler.set(
      Math.sin(this.phase * 0.29 + 2.1) * 0.0016,
      Math.sin(this.phase * 0.19) * 0.0022,
      0,
    );
    this.scratchQuaternion.multiply(
      this.wobbleQuaternion.setFromEuler(this.wobbleEuler),
    );

    // 6.5 gives roughly a sixth of a second of rotational catch-up: enough to
    // read as a heavy head, not enough to feel like lag.
    this.camera.quaternion.slerp(
      this.scratchQuaternion,
      1 - Math.exp(-6.5 * step),
    );
  }

  /**
   * Re-derive `controls.target` from the camera's actual orientation.
   *
   * Without this, re-enabling OrbitControls snaps the view: its first update
   * recomputes the quaternion from a target the animation never used, and the
   * discrepancy shows as a jump exactly when input goes live.
   */
  private syncControlsToCamera() {
    const distance = Math.max(
      this.camera.position.distanceTo(this.smoothTarget),
      this.controls.minDistance + 0.01,
    );
    const forward = this.scratchVector
      .set(0, 0, -1)
      .applyQuaternion(this.camera.quaternion);
    this.controls.target
      .copy(this.camera.position)
      .addScaledVector(forward, distance);
    this.desiredTarget.copy(this.controls.target);
    this.smoothTarget.copy(this.controls.target);
    this.basePosition.copy(this.camera.position);
    this.controls.update();
  }

  dispose() {
    this.stopSequence();
    this.controls.removeEventListener('start', this.onControlStart);
    this.controls.removeEventListener('end', this.onControlEnd);
  }
}
