"""
Construction assembly animation for the structural frame. Blender 5.x.

An 18-second erection sequence that survives glTF export and can be driven
from Three.js:

    0-3 s     foundations appear
    3-6 s     columns rise out of the foundations
    6-10 s    beams and their connections fly into position
    10-14 s   pipework connects
    14-18 s   edge protection goes on, camera settles on the finished frame

The one hard constraint shaping this file: **glTF animates only translation,
rotation, scale and morph weights.** Blender's `hide_viewport` / `hide_render`
keyframes do not export at all, so an object cannot "appear" by unhiding.
Every reveal here is therefore scale-driven, from near-zero to full size,
which does export and which Three.js plays back with a plain AnimationMixer.

This supersedes `build_erection_animation()` in generate_structure.py, which
used visibility keys and so produced a sequence that looked right in Blender
and did nothing in the browser.

Build and export:

    blender -b -P blender/generate_structure.py -P blender/assembly_animation.py \\
        -- --export dist/structure_demo.glb --manifest dist/timeline.json

Preview one frame:

    blender -b -P blender/generate_structure.py -P blender/assembly_animation.py \\
        -P blender/scene_setup.py -- --render out/f240.png --frame 240
"""

import json
import os
import sys

import bpy
from mathutils import Vector

# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

FPS = 30
TOTAL_SECONDS = 18.0

# Phases in seconds, keyed to the element_type tags that generate_structure
# writes onto every object. `rise` is how far below (or above) the final
# position an element starts; `drift` offsets it horizontally, so beams swing
# in on a crane rather than dropping vertically like a lift shaft.
PHASES = [
    {
        "name": "foundations",
        "start": 0.0, "end": 3.0,
        "types": ("foundation",),
        "rise": -1.2, "drift": (0.0, 0.0),
        "stagger": 0.55,        # share of the window spent staggering starts
    },
    {
        "name": "columns",
        "start": 3.0, "end": 6.0,
        "types": ("column", "base_plate", "splice_plate"),
        "rise": -3.0, "drift": (0.0, 0.0),
        "stagger": 0.55,
    },
    {
        "name": "beams",
        "start": 6.0, "end": 10.0,
        "types": ("beam_x", "beam_y", "brace", "end_plate", "gusset",
                  "stiffener", "bolt", "weld"),
        "rise": 4.5, "drift": (0.0, -6.0),    # craned in from the north
        "stagger": 0.65,
    },
    {
        "name": "services",
        "start": 10.0, "end": 14.0,
        "types": ("pipe",),
        "rise": 1.5, "drift": (-4.0, 0.0),    # threaded in along the run
        "stagger": 0.60,
    },
    {
        "name": "handover",
        "start": 14.0, "end": 18.0,
        "types": ("guard_rail", "guard_post", "toe_board"),
        "rise": 0.9, "drift": (0.0, 0.0),
        "stagger": 0.70,
    },
]

# Cinematic move: wide on the empty site, push in as the frame goes up, pull
# back for the reveal. Keyed in seconds.
CAMERA_PATH = [
    {"t": 0.0, "loc": (72.0, -58.0, 6.0), "target": (14.4, 9.0, 1.0)},
    {"t": 4.5, "loc": (52.0, -44.0, 9.0), "target": (14.4, 9.0, 5.0)},
    {"t": 9.0, "loc": (30.0, -30.0, 14.0), "target": (14.4, 9.0, 8.0)},
    {"t": 13.0, "loc": (22.0, -26.0, 10.0), "target": (14.4, 9.0, 7.0)},
    {"t": 18.0, "loc": (58.0, -46.0, 22.0), "target": (14.4, 9.0, 6.0)},
]


def _frame(seconds):
    return int(round(seconds * FPS)) + 1


def phase_markers():
    """Phase boundaries in both seconds and frames, for the web timeline."""
    return [{"name": p["name"],
             "start": p["start"],
             "end": p["end"],
             "startFrame": _frame(p["start"]),
             "endFrame": _frame(p["end"])}
            for p in PHASES]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _phase_for(obj):
    element = obj.get("element_type", "")
    for phase in PHASES:
        if element in phase["types"]:
            return phase
    return None


def _level_index(obj):
    """Sort key so the frame goes up storey by storey, not all at once."""
    level = obj.get("level", "L00")
    if level == "RF":
        return 99
    try:
        return int(level.lstrip("L"))
    except ValueError:
        return 0


def _object_fcurves(obj):
    """F-curves for one object across the 4.x and 5.x action layouts.

    Blender 4.4 introduced slotted actions and 5.x dropped Action.fcurves, so
    the curves now live in a channelbag under a layer's strip.
    """
    anim = obj.animation_data
    action = anim.action if anim else None
    if action is None:
        return []
    if hasattr(action, "fcurves"):
        return list(action.fcurves)

    slot = getattr(anim, "action_slot", None)
    curves = []
    for layer in action.layers:
        for strip in layer.strips:
            bag = strip.channelbag(slot) if slot else None
            if bag is None and getattr(strip, "channelbags", None):
                bag = strip.channelbags[0]
            if bag:
                curves.extend(bag.fcurves)
    return curves


def _ease(obj, easing="EASE_OUT"):
    """Clean interpolation on every curve of one object.

    EASE_OUT on a Bezier is the deceleration of a crane setting a member down:
    quick off the mark, slow into place. Linear motion is the clearest sign of
    a machine-generated animation.
    """
    for fcurve in _object_fcurves(obj):
        for keyframe in fcurve.keyframe_points:
            keyframe.interpolation = "BEZIER"
            keyframe.easing = easing
            keyframe.handle_left_type = "AUTO_CLAMPED"
            keyframe.handle_right_type = "AUTO_CLAMPED"


# ---------------------------------------------------------------------------
# Object animation
# ---------------------------------------------------------------------------

def animate_objects(objects=None, hold=0.35):
    """Key every tagged object into its phase.

    Each element gets:

      1. at `t0` - parked: offset in space, scaled to almost nothing
      2. shortly after `t0` - full scale, so it reads as a member flying in
         rather than a balloon inflating
      3. at `t1` - landed at its final position

    Scale is the reveal because it is the only "appear" channel glTF carries.
    Near-zero rather than exactly zero: a zero scale gives a degenerate normal
    matrix, which shades badly on the first frame and which some validators
    reject outright.
    """
    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = _frame(TOTAL_SECONDS)

    pool = objects if objects is not None else list(scene.objects)
    animated = 0

    for phase in PHASES:
        members = [o for o in pool
                   if o.type == "MESH" and _phase_for(o) is phase]
        if not members:
            continue

        # Storey first, then distance along the grid: the frame rises floor by
        # floor and each floor fills outward, which is how it is really built.
        members.sort(key=lambda o: (_level_index(o),
                                    o.location.x + o.location.y))

        window = phase["end"] - phase["start"]
        spread = window * phase["stagger"]
        move = window - spread          # time one element takes to land

        for i, obj in enumerate(members):
            fraction = i / max(1, len(members) - 1)
            t0 = phase["start"] + spread * fraction
            t1 = t0 + move * (1.0 - hold)

            final_loc = obj.location.copy()
            final_scale = obj.scale.copy()
            parked = final_loc + Vector((phase["drift"][0],
                                         phase["drift"][1],
                                         phase["rise"]))

            obj.location = parked
            obj.scale = final_scale * 0.001
            obj.keyframe_insert("location", frame=_frame(t0))
            obj.keyframe_insert("scale", frame=_frame(t0))

            obj.scale = final_scale
            obj.keyframe_insert("scale", frame=_frame(t0 + move * 0.25))

            obj.location = final_loc
            obj.keyframe_insert("location", frame=_frame(t1))

            _ease(obj)
            animated += 1

    print("[assembly] animated %d objects over %.0f s at %d fps"
          % (animated, TOTAL_SECONDS, FPS))
    return animated


def freeze_before_start(objects=None):
    """Hold every element parked from frame 1.

    Without a key at frame 1, an object sits at its final transform until its
    own first keyframe - so the whole finished frame flashes up before the
    sequence starts. A CONSTANT key at frame 1 pins it out of sight instead.
    """
    pool = objects if objects is not None else list(bpy.context.scene.objects)
    for obj in pool:
        if obj.type != "MESH" or _phase_for(obj) is None:
            continue
        for fcurve in _object_fcurves(obj):
            if not fcurve.keyframe_points:
                continue
            first = min(kp.co[0] for kp in fcurve.keyframe_points)
            if first <= 1:
                continue
            value = fcurve.evaluate(first)
            key = fcurve.keyframe_points.insert(1, value)
            key.interpolation = "CONSTANT"


# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------

def animate_camera(camera=None):
    """Cinematic move, baked onto the camera object.

    Keyed on location and rotation rather than parented to a path or given a
    Track To constraint: constraints do not export to glTF, baked TRS keys do.
    """
    camera = camera or bpy.context.scene.camera
    if camera is None:
        data = bpy.data.cameras.new("Camera_Assembly")
        data.lens = 40.0
        data.clip_end = 1000.0
        camera = bpy.data.objects.new("Camera_Assembly", data)
        bpy.context.scene.collection.objects.link(camera)
        bpy.context.scene.camera = camera

    camera.rotation_mode = "QUATERNION"
    for key in CAMERA_PATH:
        location = Vector(key["loc"])
        target = Vector(key["target"])
        camera.location = location
        camera.rotation_quaternion = (target - location).to_track_quat("-Z", "Y")
        frame = _frame(key["t"])
        camera.keyframe_insert("location", frame=frame)
        camera.keyframe_insert("rotation_quaternion", frame=frame)

    # A camera eases at both ends - it is a crane arm, not a dropped member -
    # so it overrides the EASE_OUT used on the structure.
    _ease(camera, easing="EASE_IN_OUT")
    return camera


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def write_timeline_manifest(path):
    """Phase boundaries for the web UI, so the timeline is defined once."""
    data = {
        "fps": FPS,
        "duration": TOTAL_SECONDS,
        "frameStart": 1,
        "frameEnd": _frame(TOTAL_SECONDS),
        "clipName": "ConstructionSequence",
        "phases": phase_markers(),
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    print("[assembly] wrote %s" % path)
    return data


def export_glb(filepath):
    """Export the animated scene.

    `export_apply` is False here, unlike the static export: applying modifiers
    evaluates the mesh and drops the object-level animation with it.
    """
    directory = os.path.dirname(os.path.abspath(filepath))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory, exist_ok=True)

    kwargs = dict(
        filepath=filepath,
        export_format="GLB",
        export_apply=False,
        export_yup=True,
        export_extras=True,
        export_cameras=True,          # the cinematic move ships with the file
        export_lights=False,
        export_animations=True,
        export_frame_range=True,
        # SCENE, not ACTIONS. In ACTIONS mode the exporter writes one clip per
        # animated object - 3138 of them here - and the viewer would have to
        # start, pause and reset every one in lockstep. SCENE mode emits a
        # single clip covering the whole timeline, which is what a
        # Start/Pause/Reset control set actually needs.
        export_animation_mode="SCENE",
        # SCENE mode still splits one clip per object unless this is off -
        # which is how the first export produced 3138 clips despite asking
        # for a scene animation.
        export_anim_scene_split_object=False,
        export_bake_animation=False,
        export_optimize_animation_size=True,
        use_selection=False,
        use_visible=False,
    )
    # Not every build knows every flag; drop what this one rejects rather
    # than failing the export outright.
    try:
        bpy.ops.export_scene.gltf(**kwargs)
    except TypeError:
        for key in ("export_animation_mode", "export_bake_animation",
                    "export_optimize_animation_size",
                    "export_anim_scene_split_object"):
            kwargs.pop(key, None)
        bpy.ops.export_scene.gltf(**kwargs)

    print("[assembly] exported %s" % filepath)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build(camera=True):
    animate_objects()
    freeze_before_start()
    if camera:
        animate_camera()
    return bpy.context.scene


def parse_args():
    argv = sys.argv
    args = {"export": None, "manifest": None, "frame": None, "no_camera": False}
    if "--" not in argv:
        return args
    argv = argv[argv.index("--") + 1:]

    i = 0
    while i < len(argv):
        if argv[i] in ("--export", "--manifest") and i + 1 < len(argv):
            args[argv[i].lstrip("-")] = argv[i + 1]
            i += 1
        elif argv[i] == "--frame" and i + 1 < len(argv):
            args["frame"] = int(argv[i + 1])
            i += 1
        elif argv[i] == "--no-camera":
            args["no_camera"] = True
        i += 1
    return args


def main():
    args = parse_args()
    build(camera=not args["no_camera"])

    if args["frame"]:
        bpy.context.scene.frame_set(args["frame"])
    if args["manifest"]:
        write_timeline_manifest(args["manifest"])
    if args["export"]:
        export_glb(args["export"])


if __name__ == "__main__":
    main()
