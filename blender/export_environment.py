"""Drop the render-only scenery, so the site can be exported for the web.

Runs between scene_setup.py and optimize_export.py:

    blender -b -P blender/generate_structure.py \
            -P blender/validation_metadata.py \
            -P blender/scene_setup.py \
            -P blender/export_environment.py \
            -P blender/optimize_export.py \
            -- --out dist/structure_environment.glb --no-animation

optimize_export exports the whole scene, so once scene_setup has run the
site comes along for free. Most of it should not: the environment exists
to make a *render* believable, and a viewer who can orbit and zoom has
different needs from a camera on a fixed track.

Three things are cut, all for the same reason - the viewer can never get
near them, so they are pure weight:

  Site_Surround_*   24 massing blocks at 110-190 m. Background only.
  Ground_Plane      400 m across. The viewer's own grid does this job.
  Site_Atmosphere   900 m haze volume. Meaningless outside Cycles.

What stays is everything at human range: hoarding, cabins, skip,
laydown, barriers, spoil, scrub, workers, van and crane. Those are the
objects that carry scale, which a web viewer needs more than a render
does - there is no photographer framing the shot for the user.
"""

import bpy

CUT_PREFIX = ("Site_Surround_",)
CUT_EXACT = ("Ground_Plane", "Site_Atmosphere")


def prune():
    doomed = [o for o in bpy.data.objects
              if o.name in CUT_EXACT or o.name.startswith(CUT_PREFIX)]
    for obj in doomed:
        bpy.data.objects.remove(obj, do_unlink=True)

    kept = len([o for o in bpy.data.objects if o.type == 'MESH'])
    print("[environment] cut %d render-only objects, %d meshes remain"
          % (len(doomed), kept))


prune()
