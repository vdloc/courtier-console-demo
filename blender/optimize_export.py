"""
Web optimisation and GLB export for the structural frame. Blender 5.x.

Produces `structure_demo.glb`: a file a Three.js viewer can select objects in,
toggle by layer, play the construction sequence from, and read component data
out of.

The governing trade-off, stated up front because it decides everything else:
**per-object selection and per-object animation forbid mesh joining.** Joining
by material would cut this from ~2800 draw calls to 8, but every element would
become one un-clickable blob and the assembly animation would die with it. So
the optimisation here reduces bytes and triangles per object, not object count:

  1. hidden geometry removed - the inner skin of every hollow section, which
     no camera can ever see, is close to a third of the column triangles
  2. small parts simplified - bolts and welds are 20 mm objects carrying the
     same bevel budget as a 7 m beam
  3. modifiers applied, then mesh data deduplicated - thousands of meshes
     collapse to a few hundred unique ones, and each duplicate then costs a
     node rather than its own vertex buffer
  4. Draco compression on the geometry that remains

Run the full pipeline:

    blender -b -P blender/generate_structure.py -P blender/assembly_animation.py \\
        -P blender/optimize_export.py -- --out dist/structure_demo.glb

Static asset, no animation:

    blender -b -P blender/generate_structure.py -P blender/optimize_export.py \\
        -- --out dist/structure_static.glb --no-animation
"""

import json
import os
import sys

import bmesh
import bpy

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

OPTIMISE = {
    # Element types whose hollow interior can never be seen.
    "hollow_types": ("column", "brace"),

    # Elements small enough that nobody counts their polygons, mapped to a
    # decimate ratio. A bolt is 24 mm across in a 29 m building.
    "simplify": {
        "bolt": 0.5,
        "weld": 0.6,
        "guard_post": 0.7,
        "toe_board": 0.9,
    },

    # Bevel segments drop to 1 on these before the modifiers are applied: a
    # 4 mm arris on a bolt head never survives to a pixel, but it multiplies
    # that object's triangle count.
    "cheap_bevel_types": ("bolt", "weld", "guard_post", "guard_rail",
                          "toe_board", "splice_plate", "stiffener"),

    "dedupe_meshes": True,
    "dedupe_precision": 5,            # decimal places when hashing vertices
    "draco": True,
    "draco_level": 6,                 # 0-10; 6 is the usual sweet spot
    "draco_position_bits": 14,        # 14 bits over a 30 m model is ~2 mm
    "draco_normal_bits": 10,
    "draco_uv_bits": 12,

    # Sample the scene animation every N frames. SCENE mode always samples -
    # that is how it merges thousands of object actions into one clip - so
    # the only lever on animation size is how often it samples. At 30 fps a
    # step of 2 is 15 samples/second, which is indistinguishable for motion
    # this slow and halves the animation payload.
    "frame_step": 2,

    # gltf-transform post-pass. `resample` is the one that matters here:
    # every object is stationary for ~17 of the 18 seconds, and resample
    # collapses those constant runs that per-frame sampling wrote out in full.
    "postprocess": True,
    "postprocess_texture_compress": "webp",   # "ktx2" needs toktx installed
}


# ---------------------------------------------------------------------------
# 1. Hidden geometry
# ---------------------------------------------------------------------------

def strip_hidden_geometry(objects=None):
    """Delete the inner skin of hollow sections.

    A hollow section is modelled as an outer loop and an inner loop joined by
    quad end caps. The inner skin is sealed inside the tube: unreachable from
    any camera outside the member, and on a 400 mm SHS very nearly as many
    triangles as the outer skin.

    Detection is geometric rather than by name - a face is inward-facing when
    its normal points back toward the member's own axis. That holds for the
    square columns and the round braces alike, and never fires on a solid
    I-section, whose faces all point away from the centre.
    """
    pool = objects if objects is not None else list(bpy.context.scene.objects)
    removed = 0
    touched = 0

    for obj in pool:
        if obj.type != "MESH":
            continue
        if obj.get("element_type") not in OPTIMISE["hollow_types"]:
            continue

        mesh = obj.data
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()

        # Members are extruded along local X, so the axis runs through the
        # centroid at each X. Comparing each face against the axis point at
        # its own X keeps this valid along the whole length.
        inward = []
        for face in bm.faces:
            centre = face.calc_center_median()
            outward = centre.copy()
            outward.x = 0.0                   # radial component only
            if outward.length < 1e-6:
                continue                      # on the axis: an end cap, keep
            if face.normal.dot(outward.normalized()) < -0.25:
                inward.append(face)

        if inward:
            bmesh.ops.delete(bm, geom=inward, context="FACES")
            bm.to_mesh(mesh)
            removed += len(inward)
            touched += 1
        bm.free()

    print("[optimise] removed %d hidden faces from %d hollow members"
          % (removed, touched))
    return removed


# ---------------------------------------------------------------------------
# 2. Polygon budget
# ---------------------------------------------------------------------------

def cheapen_bevels(objects=None):
    """Drop small parts to a single bevel segment before modifiers apply."""
    pool = objects if objects is not None else list(bpy.context.scene.objects)
    count = 0
    for obj in pool:
        if obj.type != "MESH":
            continue
        if obj.get("element_type") not in OPTIMISE["cheap_bevel_types"]:
            continue
        for mod in obj.modifiers:
            if mod.type == "BEVEL" and mod.segments > 1:
                mod.segments = 1
                count += 1
    print("[optimise] reduced bevel segments on %d objects" % count)
    return count


def simplify_small_parts(objects=None):
    """Decimate the elements nobody inspects at close range."""
    pool = objects if objects is not None else list(bpy.context.scene.objects)
    count = 0
    for obj in pool:
        if obj.type != "MESH":
            continue
        ratio = OPTIMISE["simplify"].get(obj.get("element_type"))
        if not ratio:
            continue
        mod = obj.modifiers.new(name="Decimate", type="DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = ratio
        count += 1
    print("[optimise] queued decimation on %d small parts" % count)
    return count


def _modifier_signature(obj):
    """Fingerprint of an object's modifier stack, for grouping."""
    parts = []
    for mod in obj.modifiers:
        if mod.type == "BEVEL":
            parts.append(("BEVEL", round(mod.width, 6), mod.segments,
                          mod.limit_method, round(mod.angle_limit, 4)))
        elif mod.type == "WEIGHTED_NORMAL":
            parts.append(("WN", mod.mode, mod.weight, mod.keep_sharp))
        elif mod.type == "DECIMATE":
            parts.append(("DEC", round(mod.ratio, 4)))
        else:
            parts.append((mod.type,))
    return tuple(parts)


def bake_and_dedupe(objects=None):
    """Apply modifiers and share the results, in one pass.

    Two things forced this to be a single function rather than the obvious
    apply-then-dedupe pair:

    * `bpy.ops.object.modifier_apply` is an operator, and driving it 3137
      times takes longer than the whole rest of the pipeline - it times out.
      `evaluated_get(depsgraph)` + `meshes.new_from_object` does the same job
      without the operator overhead.
    * Applying first and deduplicating after means evaluating thousands of
      meshes that are about to be thrown away. Grouping first by (raw
      geometry + modifier stack) means each *distinct* result is evaluated
      exactly once, and every object sharing that signature points at it.

    The result: one vertex buffer per unique part, and a node per instance -
    which keeps every element independently selectable and animated.
    """
    pool = objects if objects is not None else list(bpy.context.scene.objects)
    precision = OPTIMISE["dedupe_precision"]
    depsgraph = bpy.context.evaluated_depsgraph_get()

    groups = {}
    for obj in pool:
        if obj.type != "MESH" or obj.data is None:
            continue
        signature = (_mesh_signature(obj.data, precision),
                     _modifier_signature(obj))
        groups.setdefault(signature, []).append(obj)

    baked = 0
    for members in groups.values():
        representative = members[0]
        evaluated = representative.evaluated_get(depsgraph)
        mesh = bpy.data.meshes.new_from_object(evaluated)
        mesh.name = representative.data.name + "_baked"

        for obj in members:
            obj.modifiers.clear()
            obj.data = mesh
        baked += 1

    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)

    print("[optimise] baked %d unique meshes for %d objects"
          % (baked, sum(len(m) for m in groups.values())))
    return baked


# ---------------------------------------------------------------------------
# 3. Deduplication
# ---------------------------------------------------------------------------

def _mesh_signature(mesh, precision):
    """A hashable fingerprint of a mesh's geometry."""
    verts = tuple(
        (round(v.co.x, precision), round(v.co.y, precision),
         round(v.co.z, precision))
        for v in mesh.vertices
    )
    polys = tuple(tuple(p.vertices) for p in mesh.polygons)
    materials = tuple(m.name if m else "" for m in mesh.materials)
    return hash((verts, polys, materials))


def dedupe_meshes(objects=None):
    """Point objects with identical geometry at one shared mesh datablock.

    Nearly a thousand identical bolts become one vertex buffer plus a node
    each. The exporter writes the glTF mesh once and references it from every
    node, so the geometry is paid for once - and each node stays
    independently selectable and independently animated.
    """
    if not OPTIMISE["dedupe_meshes"]:
        return 0

    pool = objects if objects is not None else list(bpy.context.scene.objects)
    precision = OPTIMISE["dedupe_precision"]
    canonical = {}
    merged = 0

    for obj in pool:
        if obj.type != "MESH" or obj.data is None:
            continue
        signature = _mesh_signature(obj.data, precision)
        if signature in canonical:
            if obj.data is not canonical[signature]:
                obj.data = canonical[signature]
                merged += 1
        else:
            canonical[signature] = obj.data

    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)

    print("[optimise] deduplicated %d meshes -> %d unique"
          % (merged, len(canonical)))
    return merged


def flatten_materials_for_web():
    """Replace each procedural node tree with a plain Principled BSDF.

    glTF has no concept of a noise node, so the exporter reduces a procedural
    material to whatever it can read off the Principled inputs - and when
    those inputs are driven by node links it falls back to defaults. Every
    material then exports looking identical, and a post-pass dedup collapses
    seven materials into two, taking the viewer's name-based material lookup
    with it.

    Writing explicit base colour, metallic and roughness factors here keeps
    the GLB's materials distinct and correct. The web viewer layers the baked
    texture maps on top by name; Cycles keeps the full procedural version,
    because this only runs in the export pipeline.
    """
    try:
        import materials as material_lib
    except ImportError:
        print("[optimise] materials.py unavailable, leaving materials as-is")
        return 0

    flattened = 0
    for name, spec in material_lib.MATERIALS.items():
        mat = bpy.data.materials.get(name)
        if mat is None:
            continue

        nodes, links = material_lib._reset(mat)
        out = nodes.new("ShaderNodeOutputMaterial")
        out.location = (300, 0)
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.location = (0, 0)
        bsdf.inputs["Base Color"].default_value = material_lib._rgba(
            spec["base_color"])
        bsdf.inputs["Metallic"].default_value = spec["metallic"]
        bsdf.inputs["Roughness"].default_value = spec["roughness"]
        links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
        flattened += 1

    print("[optimise] flattened %d materials to PBR factors" % flattened)
    return flattened


def merge_materials():
    """Collapse duplicate material datablocks (Material.001 and friends)."""
    merged = 0
    for mat in list(bpy.data.materials):
        base = mat.name.rsplit(".", 1)[0]
        if base == mat.name or base not in bpy.data.materials:
            continue
        target = bpy.data.materials[base]
        for obj in bpy.data.objects:
            if obj.type != "MESH":
                continue
            for slot in obj.material_slots:
                if slot.material is mat:
                    slot.material = target
        merged += 1

    for mat in list(bpy.data.materials):
        if mat.users == 0:
            bpy.data.materials.remove(mat)

    print("[optimise] merged %d duplicate materials, %d remain"
          % (merged, len(bpy.data.materials)))
    return merged


# ---------------------------------------------------------------------------
# 4. Stats and export
# ---------------------------------------------------------------------------

def scene_stats():
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    tris = 0
    for obj in meshes:
        for poly in obj.data.polygons:
            tris += max(1, len(poly.vertices) - 2)
    return {
        "objects": len(meshes),
        "unique_meshes": len({o.data.name for o in meshes}),
        "triangles": tris,
        "materials": len(bpy.data.materials),
    }


def export(filepath, animation=True):
    """Write the GLB.

    Everything the viewer needs is preserved explicitly:
      - hierarchy: the empties parenting each discipline group
      - names:     every object keeps its grid-addressed name
      - metadata:  export_extras carries custom properties into userData
      - animation: the single scene-level construction clip
    """
    directory = os.path.dirname(os.path.abspath(filepath))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory, exist_ok=True)

    # Export from the LAST frame, not the first.
    #
    # glTF writes each node's transform from the scene's current frame, and
    # freeze_before_start() parks every object at scale 0.001 on frame 1.
    # Exporting there produces a file whose default state is an empty site:
    # the viewer loads 3137 invisible objects and shows bare ground until
    # something plays the clip. The animation keys are unaffected either way,
    # so the file should default to the finished structure.
    if animation:
        scene = bpy.context.scene
        scene.frame_set(scene.frame_end)

    kwargs = dict(
        filepath=filepath,
        export_format="GLB",
        export_apply=False,          # already applied, above
        export_yup=True,
        export_extras=True,          # component metadata -> userData
        export_cameras=animation,
        export_lights=False,
        export_materials="EXPORT",
        export_normals=True,
        export_texcoords=True,
        export_tangents=False,
        export_animations=animation,
        use_selection=False,
        use_visible=False,
    )
    if animation:
        kwargs.update(
            export_frame_range=True,
            export_animation_mode="SCENE",
            export_anim_scene_split_object=False,
            # Baking samples every channel at every frame: 6276 channels x
            # 541 frames dominated the file and pushed it past 21 MB, while
            # the actual animation is 3-4 sparse keys per object. Sparse keys
            # export correctly here because every channel is plain object TRS.
            export_bake_animation=False,
            export_optimize_animation_size=True,
        )
    if animation and OPTIMISE["frame_step"] > 1:
        kwargs["export_frame_step"] = OPTIMISE["frame_step"]

    # When the post-pass runs, leave the geometry uncompressed here: Draco
    # cannot be applied twice, and gltf-transform compresses after it has
    # pruned and resampled, which compresses less data.
    if OPTIMISE["draco"] and not OPTIMISE["postprocess"]:
        kwargs.update(
            export_draco_mesh_compression_enable=True,
            export_draco_mesh_compression_level=OPTIMISE["draco_level"],
            export_draco_position_quantization=OPTIMISE["draco_position_bits"],
            export_draco_normal_quantization=OPTIMISE["draco_normal_bits"],
            export_draco_texcoord_quantization=OPTIMISE["draco_uv_bits"],
        )

    try:
        bpy.ops.export_scene.gltf(**kwargs)
    except TypeError:
        # Drop whatever this build does not recognise rather than failing.
        for key in ("export_animation_mode", "export_anim_scene_split_object",
                    "export_bake_animation", "export_optimize_animation_size",
                    "export_frame_step",
                    "export_draco_position_quantization",
                    "export_draco_normal_quantization",
                    "export_draco_texcoord_quantization"):
            kwargs.pop(key, None)
        bpy.ops.export_scene.gltf(**kwargs)

    size = os.path.getsize(filepath) / (1024 * 1024)
    print("[optimise] exported %s (%.1f MB)" % (filepath, size))
    return filepath


def postprocess(filepath):
    """Run gltf-transform over the exported file, in place.

    Blender's exporter cannot resample animation, prune unused data, or write
    KTX2/WebP textures. gltf-transform does all three, and `optimize` bundles
    the passes in the right order: prune -> dedup -> resample -> compress.

    Skipped silently when the CLI is unavailable, because the pipeline has to
    work on a machine with no Node toolchain - the file is simply larger.
    """
    if not OPTIMISE["postprocess"]:
        return None

    import shutil
    import subprocess
    import tempfile

    if shutil.which("npx") is None:
        print("[optimise] npx not found, skipping the gltf-transform pass")
        return None

    staged = os.path.join(tempfile.gettempdir(),
                          "pre_" + os.path.basename(filepath))
    shutil.copy2(filepath, staged)

    command = [
        "npx", "--yes", "@gltf-transform/cli", "optimize", staged, filepath,
        "--compress", "draco",
        "--texture-compress", OPTIMISE["postprocess_texture_compress"],
        # `optimize` defaults both of these to true. --join merges meshes,
        # which would destroy per-object selection outright; --flatten
        # collapses the scene graph, which strips the VF_Structure root and
        # the discipline empties the layer toggles traverse.
        "--join", "false",
        "--flatten", "false",
        # GPU instancing would be a large draw-call win, but instanced nodes
        # cannot carry independent animation - and every element here is
        # independently animated.
        "--instance", "false",
        # The palette pass merges distinct materials into an atlas and
        # renames them PaletteMaterial001/002. That is a real draw-call win
        # for a static asset, but it destroys the material names the viewer
        # matches on to attach the baked PBR maps.
        "--palette", "false",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=900, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        print("[optimise] gltf-transform pass failed (%s); keeping the "
              "Blender export" % error)
        shutil.copy2(staged, filepath)
        return None

    if result.returncode != 0:
        print("[optimise] gltf-transform returned %d; keeping the Blender "
              "export" % result.returncode)
        print(result.stderr.strip()[-600:])
        shutil.copy2(staged, filepath)
        return None

    before = os.path.getsize(staged) / (1024 * 1024)
    after = os.path.getsize(filepath) / (1024 * 1024)
    print("[optimise] gltf-transform: %.1f MB -> %.1f MB" % (before, after))
    os.remove(staged)
    return after


def write_report(path, before, after, filepath):
    report = {
        "file": os.path.basename(filepath),
        "sizeMB": round(os.path.getsize(filepath) / (1024 * 1024), 2),
        "before": before,
        "after": after,
        "draco": OPTIMISE["draco"],
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    print("[optimise] wrote %s" % path)
    return report


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(filepath="dist/structure_demo.glb", animation=True, report=None):
    before = scene_stats()
    print("[optimise] before: %s" % before)

    strip_hidden_geometry()
    cheapen_bevels()
    simplify_small_parts()
    merge_materials()
    flatten_materials_for_web()
    bake_and_dedupe()

    after = scene_stats()
    print("[optimise] after:  %s" % after)

    export(filepath, animation=animation)
    postprocess(filepath)
    if report:
        write_report(report, before, after, filepath)
    return after


def parse_args():
    argv = sys.argv
    args = {"out": "dist/structure_demo.glb", "animation": True,
            "report": None}
    if "--" not in argv:
        return args
    argv = argv[argv.index("--") + 1:]

    i = 0
    while i < len(argv):
        if argv[i] in ("--out", "--report") and i + 1 < len(argv):
            args[argv[i].lstrip("-")] = argv[i + 1]
            i += 1
        elif argv[i] == "--no-animation":
            args["animation"] = False
        i += 1
    return args


def main():
    args = parse_args()
    run(args["out"], args["animation"], args["report"])


if __name__ == "__main__":
    main()
