"""
Render scene for the structural frame: camera, HDRI sky, sun, shadows,
ambient occlusion and colour management. Blender 5.x.

No .hdr file is downloaded or shipped. The environment is Blender's built-in
Nishita sky, which is a physical atmosphere model - it produces a real HDR
gradient, correct sun colour for a given elevation, and the blue sky bounce
that makes steel look like steel. A single sourced HDRI would be one lighting
condition; this is a dial.

Camera work follows architectural convention rather than game convention: a
long lens from far back (less perspective distortion on tall columns) and a
vertical shift instead of a tilt, so column lines stay parallel and the frame
reads as a survey photograph rather than a hero shot.

Render a hero still:

    blender -b -P blender/scene_setup.py -- --render out/hero.png

Build the frame and render in one pass:

    blender -b -P blender/generate_structure.py -P blender/scene_setup.py \\
        -- --render out/hero.png --shot hero
"""

import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

SCENE = {
    # --- camera -------------------------------------------------------------
    # Focal length in mm. 50 is the architectural default: wide enough to hold
    # a 29 m frame from a sane distance, long enough that the columns do not
    # splay. Anything under 28 makes engineering geometry look like a game.
    "focal_length": 50.0,
    "sensor_width": 36.0,
    "shift_y": 0.07,                # vertical shift, not tilt - keeps verticals
    "f_stop": 8.0,                  # deep enough to hold the whole frame sharp
    "use_dof": True,

    # Named camera positions, in metres, in the model's own coordinates.
    # `target` is what the camera looks at.
    "shots": {
        "hero": {"loc": (58.0, -46.0, 22.0), "target": (14.4, 9.0, 6.0),
                 "focal": 50.0},
        "corner": {"loc": (34.0, -22.0, 4.2), "target": (10.0, 4.0, 5.5),
                   "focal": 35.0},
        "detail": {"loc": (4.2, -3.4, 4.6), "target": (0.2, 0.0, 3.4),
                   "focal": 85.0},          # a single beam-to-column joint
        "elevation": {"loc": (14.4, -120.0, 6.8), "target": (14.4, 9.0, 6.8),
                      "focal": 200.0},      # near-orthographic front elevation
        # Straight down from far enough up that the columns barely splay -
        # a QC view for grid spacing and symmetry, not a photograph.
        "plan": {"loc": (14.4, 9.0, 190.0), "target": (14.4, 9.001, 0.0),
                 "focal": 200.0},
    },

    # --- sky ----------------------------------------------------------------
    # 18 deg sun elevation is late afternoon: long shadows that describe the
    # frame's depth, without the colour cast of a sunset.
    "sun_elevation": 18.0,
    "sun_rotation": 235.0,          # from the south-west, across the long face
    # Irradiance in W/m2. Blender's sky texture is not on a physical scale: at
    # strength 1.0 it delivers roughly as much ambient as a 30 W/m2 sun, so a
    # "physically plausible" 2.4 left the sun an order of magnitude below the
    # sky and the frame rendered shadowless. This is a measured ratio against
    # `sky_light`, not a physical constant - move one and the shadows move.
    "sun_strength": 12.0,
    "sun_angle": 1.5,               # apparent size in degrees; softens shadows

    # Nishita's aerosol term. The 4.x property was `dust_density`; Blender 5's
    # MULTIPLE_SCATTERING model renames it and splits ozone out, so the old
    # name set nothing and the sky carried no haze at all.
    "sky_aerosol": 2.0,             # atmospheric haze; adds aerial perspective
    "sky_ozone": 1.0,
    "sky_ground_albedo": 0.12,      # bounce off a site, not off snow

    # The sky is two numbers because one cannot do both jobs. Bright enough to
    # photograph as a sky and its ambient washes out every shadow; dim enough
    # for shadows and the background renders near-black. `sky_light` lights
    # the frame, `sky_view` is what the camera sees.
    "sky_light": 0.30,
    "sky_view": 1.60,

    # --- ground -------------------------------------------------------------
    "ground_size": 400.0,
    "ground_color": (0.055, 0.052, 0.048, 1.0),   # damp site, not a white void

    # --- render -------------------------------------------------------------
    "engine": "CYCLES",         # "BLENDER_EEVEE_NEXT" for seconds, not minutes
    "samples": 128,
    "eevee_samples": 64,
    "resolution": (1920, 1080),
    "view_transform": "AgX",        # holds highlights on metal; Filmic's heir
    "look": "AgX - Medium High Contrast",
    # Set against the sun/sky pair above, not chosen for its own sake: RAL
    # 7016 steel at 0.055 albedo has to land as dark grey, not as the mid grey
    # a generous exposure turns it into.
    "exposure": -0.8,
    "film_transparent": False,
}


# ---------------------------------------------------------------------------
# World: Nishita sky as the HDRI
# ---------------------------------------------------------------------------

def setup_world():
    """Physical sky environment. The key light and the fill in one node.

    A Sky Texture in Nishita mode is a real HDR environment: the sun carries
    thousands of nits while the sky sits several stops down, so metal picks up
    a bright specular and a cool blue ambient with no extra lights. Faking
    this with a flat grey world is what makes CAD renders look dead.
    """
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    if not world.node_tree:
        world.use_nodes = True

    nodes, links = world.node_tree.nodes, world.node_tree.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputWorld")
    out.location = (900, 0)

    # Two Background nodes off one sky, mixed on Is Camera Ray.
    #
    # A single strength cannot serve both purposes. The Nishita sky is a very
    # efficient ambient source - at strength 1.0 it fills every shadow the sun
    # casts, and the frame renders as flat as a product shot on a lightbox.
    # Dropping it far enough for the sun to read then takes the *background*
    # down with it, and the demo gains a night sky over a sunlit building.
    #
    # So: `sky_light` is the environment that lights the frame, `sky_view` is
    # the one the camera photographs. Both come off the same Sky texture, so
    # the horizon the viewer sees is still the horizon that lit the steel -
    # only its exposure differs. This is a lighting-department convention, not
    # a cheat: it is what a neutral-density gel on a window achieves.
    light_bg = nodes.new("ShaderNodeBackground")
    light_bg.location = (350, 120)
    light_bg.inputs["Strength"].default_value = SCENE["sky_light"]

    view_bg = nodes.new("ShaderNodeBackground")
    view_bg.location = (350, -120)
    view_bg.inputs["Strength"].default_value = SCENE["sky_view"]

    light_path = nodes.new("ShaderNodeLightPath")
    light_path.location = (350, 380)

    mix = nodes.new("ShaderNodeMixShader")
    mix.location = (650, 0)

    sky = nodes.new("ShaderNodeTexSky")
    sky.location = (0, 0)

    # Blender 5 renamed the Nishita model: the enum is now
    # MULTIPLE_SCATTERING, with SINGLE_SCATTERING as the cheaper sibling. 4.x
    # still calls it NISHITA. Pick whichever this build actually offers,
    # preferring the physical models over the older analytic ones.
    available = sky.bl_rna.properties["sky_type"].enum_items.keys()
    for candidate in ("MULTIPLE_SCATTERING", "NISHITA", "HOSEK_WILKIE"):
        if candidate in available:
            sky.sky_type = candidate
            break

    # Attribute names vary with the model, so set what exists rather than
    # assuming a generation. sun_disc goes off because the sun lives in the
    # Sun lamp, where shadow softness is controllable.
    for attr, value in (
        ("sun_elevation", math.radians(SCENE["sun_elevation"])),
        ("sun_rotation", math.radians(SCENE["sun_rotation"])),
        ("sun_intensity", 1.0),
        ("sun_size", math.radians(SCENE["sun_angle"])),
        # 4.x spelling, kept so this still runs on Blender 4.2.
        ("dust_density", SCENE["sky_aerosol"]),
        # Blender 5 MULTIPLE_SCATTERING spellings.
        ("aerosol_density", SCENE["sky_aerosol"]),
        ("ozone_density", SCENE["sky_ozone"]),
        ("ground_albedo", SCENE["sky_ground_albedo"]),
        ("air_density", 1.0),
        ("altitude", 20.0),
        ("sun_disc", False),
    ):
        if hasattr(sky, attr):
            setattr(sky, attr, value)

    links.new(sky.outputs["Color"], light_bg.inputs["Color"])
    links.new(sky.outputs["Color"], view_bg.inputs["Color"])
    # Camera rays take the bright sky; every bounce that lights the frame
    # takes the dim one.
    links.new(light_path.outputs["Is Camera Ray"], mix.inputs["Fac"])
    links.new(light_bg.outputs["Background"], mix.inputs[1])
    links.new(view_bg.outputs["Background"], mix.inputs[2])
    links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return world


def setup_sun():
    """Directional key light, matched to the sky's sun position.

    `angle` is the sun's apparent diameter. The real sun is 0.53 deg; opening
    it to ~1.5 deg softens the shadow edge just enough to read as a hazy day
    and hides sampling noise at low sample counts.
    """
    existing = bpy.data.objects.get("Sun_Key")
    if existing:
        bpy.data.objects.remove(existing, do_unlink=True)

    data = bpy.data.lights.new("Sun_Key", type="SUN")
    data.energy = SCENE["sun_strength"]
    data.angle = math.radians(SCENE["sun_angle"])
    data.use_shadow = True

    sun = bpy.data.objects.new("Sun_Key", data)
    bpy.context.scene.collection.objects.link(sun)

    # Point the lamp along the same vector the sky texture uses.
    elevation = math.radians(SCENE["sun_elevation"])
    rotation = math.radians(SCENE["sun_rotation"])
    direction = Vector((
        math.cos(elevation) * math.cos(rotation),
        math.cos(elevation) * math.sin(rotation),
        math.sin(elevation),
    ))
    sun.location = direction * 100.0
    sun.rotation_mode = "QUATERNION"
    sun.rotation_quaternion = (-direction).to_track_quat("-Z", "Y")
    return sun


def setup_ground():
    """A large dark ground plane.

    Two jobs: it catches the frame's shadow, which is what visually plants the
    columns instead of leaving them floating, and it darkens the lower
    hemisphere so the underside of every beam gets a natural falloff. A white
    ground would bounce light up into the soffits and flatten them.
    """
    existing = bpy.data.objects.get("Ground_Plane")
    if existing:
        bpy.data.objects.remove(existing, do_unlink=True)

    bpy.ops.mesh.primitive_plane_add(size=SCENE["ground_size"],
                                     location=(14.4, 9.0, -0.80))
    ground = bpy.context.active_object
    ground.name = "Ground_Plane"

    mat = (bpy.data.materials.get("MAT_Ground")
           or bpy.data.materials.new("MAT_Ground"))
    mat.use_nodes = True
    build_ground_material(mat)
    ground.data.materials.clear()
    ground.data.materials.append(mat)
    return ground


def _reset(mat):
    """Empty a material's node tree and hand back (nodes, links).

    Local rather than imported from materials.py: scene_setup is documented as
    runnable on its own (`blender -b -P blender/scene_setup.py`), and the
    material library is not on sys.path in that case.
    """
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    return tree.nodes, tree.links


def _rgba(rgb, alpha=1.0):
    return (rgb[0], rgb[1], rgb[2], alpha)


def _ramp(node, stops):
    """Set a ColorRamp's stops from ((position, rgba), ...)."""
    elements = node.color_ramp.elements
    while len(elements) > len(stops):
        elements.remove(elements[-1])
    for index, (position, colour) in enumerate(stops):
        element = (elements[index] if index < len(elements)
                   else elements.new(position))
        element.position = position
        element.color = colour
    return node


def build_ground_material(mat):
    """Procedural site surface: damp hardstanding, not a grey card.

    A single flat colour over 400 m is the second-loudest CG tell in the wide
    shot, after untextured concrete. Real ground is never uniform - it has
    tracked mud, patches that dried at different rates, and a scale of
    variation large enough to read from 60 m away. Two noise octaves are
    enough: a metre-scale one for wet/dry patching and a decimetre-scale one
    for grain, mixed into both colour and roughness so the patches change how
    the surface reflects, not only what shade it is. Roughness variation is
    what sells damp; colour variation alone reads as a painted floor.

    Deliberately no bump: at grazing incidence from 60 m a normal on a ground
    plane this large buys nothing but sampling noise.
    """
    nodes, links = _reset(mat)

    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (350, 0)
    bsdf.inputs["Metallic"].default_value = 0.0

    coords = nodes.new("ShaderNodeTexCoord")
    coords.location = (-800, 0)

    # Object coordinates on this plane are metres, and the plane is 400 m
    # across, so Noise `Scale` is (roughly) features per metre: the scales
    # below are chosen for how large the patches read from the hero camera at
    # 60 m, not for how they look zoomed in. Anything above ~1.0 here is
    # sub-metre, lands under a pixel at that distance, and renders as grain
    # rather than as ground.
    patch = nodes.new("ShaderNodeTexNoise")
    patch.location = (-600, 150)
    patch.inputs["Scale"].default_value = 0.05      # ~20 m wet/dry patches
    patch.inputs["Detail"].default_value = 6.0
    patch.inputs["Roughness"].default_value = 0.65

    grain = nodes.new("ShaderNodeTexNoise")
    grain.location = (-600, -150)
    grain.inputs["Scale"].default_value = 0.7       # ~1.5 m tracked grit
    grain.inputs["Detail"].default_value = 4.0

    mix_noise = nodes.new("ShaderNodeMix")
    mix_noise.data_type = "FLOAT"
    mix_noise.location = (-380, 0)
    mix_noise.inputs["Factor"].default_value = 0.35

    colour = nodes.new("ShaderNodeValToRGB")
    colour.location = (-150, 120)
    base = SCENE["ground_color"]
    wet = tuple(c * 0.55 for c in base[:3])
    dry = tuple(min(1.0, c * 2.4) for c in base[:3])
    _ramp(colour, ((0.30, _rgba(wet)), (0.72, _rgba(dry))))

    rough = nodes.new("ShaderNodeMapRange")
    rough.location = (-150, -180)
    rough.inputs["To Min"].default_value = 0.62   # damp, still reflective
    rough.inputs["To Max"].default_value = 0.98   # dried out, fully matte

    links.new(coords.outputs["Object"], patch.inputs["Vector"])
    links.new(coords.outputs["Object"], grain.inputs["Vector"])
    links.new(patch.outputs["Fac"], mix_noise.inputs[2])
    links.new(grain.outputs["Fac"], mix_noise.inputs[3])
    links.new(mix_noise.outputs[0], colour.inputs["Fac"])
    links.new(mix_noise.outputs[0], rough.inputs["Value"])
    links.new(colour.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(rough.outputs["Result"], bsdf.inputs["Roughness"])
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


# ---------------------------------------------------------------------------
# Site context
# ---------------------------------------------------------------------------

# Everything here is at its real dimension, because that is the entire point.
# A viewer who has stood on a site knows how big a shipping container is, how
# tall a hoarding panel comes on a person, and how long a bundle of sections
# is. Those known objects are what give the frame its scale - the structure
# cannot do it alone, because the viewer has no prior for "four-storey steel
# frame" the way they do for "skip". Get one of these dimensions wrong and it
# reads worse than having nothing there at all.
SITE = {
    # Hoarding: 2.0 m ply panels, the UK site standard.
    "hoard_height": 2.0,
    "hoard_panel": 3.5,
    "hoard_gap": 0.04,             # panels butt, they do not weld
    "hoard_offset": 14.0,          # from the frame's footprint
    "hoard_colour": (0.030, 0.075, 0.115),   # site blue, weathered

    # ISO shipping container, to the millimetre. The most recognisable
    # yardstick on any site.
    "cabin": (6.058, 2.438, 2.591),
    "cabin_colour": (0.215, 0.205, 0.185),

    # Bundled sections on timber bearers, cut to the 7.2 m grid because that
    # is what they are for.
    "bundle": (7.2, 0.90, 0.55),
    "bearer": (0.15, 1.10, 0.15),

    # Jersey barrier, 3.0 m unit.
    "barrier": (3.0, 0.60, 0.82),

    # Builder's skip, 8-yard.
    "skip": (3.55, 1.75, 1.30),
    "skip_colour": (0.180, 0.055, 0.020),    # oxide red, scuffed

    "aggregate_colour": (0.075, 0.068, 0.058),
}


def _flat_material(name, rgb, roughness=0.85, metallic=0.0):
    """One-BSDF material. Site props do not need the procedural library.

    Deliberately not added to materials.py: that table is walked by
    optimize_export.flatten_materials_for_web to write the GLB's material set,
    and site dressing has no business in the structural model's materials.
    """
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    nodes, links = _reset(mat)
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (300, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)
    bsdf.inputs["Base Color"].default_value = _rgba(rgb)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def _site_box(name, size, location, collection, material, rotation_z=0.0):
    """An axis-aligned box of a given real size, placed by its centre."""
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    bm.to_mesh(mesh)
    bm.free()

    obj.location = location
    obj.rotation_euler = (0.0, 0.0, rotation_z)
    obj.data.materials.append(material)
    collection.objects.link(obj)
    return obj


def build_site_context(rng_seed=7):
    """A working site around the frame: hoarding, compound, laydown, spoil.

    This is the largest single step from "technical 3D model" to "construction
    visualization", and it is not a rendering trick - it is the difference
    between a structure photographed somewhere and a structure photographed
    nowhere. An empty 400 m plane tells the viewer the frame is a CAD export.
    A hoarding line, a container compound and a laydown area tell them it is a
    job, and every one of those objects is also a scale reference.

    Kept in its own `SiteContext` collection, outside the `VF_Structure`
    hierarchy, for two reasons: the web viewer's layer filtering and selection
    walk that hierarchy and must not see site dressing as structure, and this
    function is only ever called from scene_setup, which the export pipeline
    does not run. The GLB is unaffected.

    Everything is placed with a seeded RNG. Site objects are never square to
    the grid - a container dropped by a HIAB lands a few degrees off, and a
    perfectly aligned site is the tell that gives away a generated one.
    """
    existing = bpy.data.collections.get("SiteContext")
    if existing:
        for obj in list(existing.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(existing)

    site = bpy.data.collections.new("SiteContext")
    bpy.context.scene.collection.children.link(site)

    rng = random.Random(rng_seed)
    jitter = lambda spread: math.radians(rng.uniform(-spread, spread))

    hoard_mat = _flat_material("MAT_Site_Hoarding", SITE["hoard_colour"], 0.78)
    cabin_mat = _flat_material("MAT_Site_Cabin", SITE["cabin_colour"], 0.62,
                               metallic=0.35)
    steel_mat = _flat_material("MAT_Site_Bundle", (0.048, 0.052, 0.058), 0.58,
                               metallic=0.25)
    timber_mat = _flat_material("MAT_Site_Timber", (0.105, 0.072, 0.042), 0.92)
    skip_mat = _flat_material("MAT_Site_Skip", SITE["skip_colour"], 0.72,
                              metallic=0.20)
    agg_mat = _flat_material("MAT_Site_Aggregate",
                             SITE["aggregate_colour"], 0.96)
    conc_mat = (bpy.data.materials.get("MAT_Concrete")
                or _flat_material("MAT_Site_Concrete", (0.30, 0.294, 0.28)))

    ground_z = -0.80
    off = SITE["hoard_offset"]
    x0, x1 = 0.0 - off, 28.8 + off
    y0, y1 = 0.0 - off, 18.0 + off

    # --- hoarding ----------------------------------------------------------
    # A continuous line with one gap for the gate. The gap matters: an
    # unbroken perimeter has no way in, and a site with no way in is a fence
    # around a model rather than a site.
    panel = SITE["hoard_panel"]
    height = SITE["hoard_height"]
    thickness = 0.045
    gate_centre = (x0 + x1) / 2.0 + 6.0
    gate_half = 5.0

    def run(start, end, axis, fixed, tag, gated=False):
        length = end - start
        count = max(1, int(length // (panel + SITE["hoard_gap"])))
        step = length / count
        for i in range(count):
            centre = start + step * (i + 0.5)
            if gated and abs(centre - gate_centre) < gate_half:
                continue                       # the gate opening
            size = ((step - SITE["hoard_gap"], thickness, height) if axis == "x"
                    else (thickness, step - SITE["hoard_gap"], height))
            location = ((centre, fixed, ground_z + height / 2.0) if axis == "x"
                        else (fixed, centre, ground_z + height / 2.0))
            _site_box("Site_Hoarding_%s_%02d" % (tag, i), size,
                      location, site, hoard_mat, jitter(0.5))

    # All four sides. The far runs are the ones that matter most: they are
    # what the camera sees *behind* the frame, and a boundary behind the
    # subject is what stops the ground reading as an infinite plane. The near
    # run is mostly below the frame edge from the hero camera and earns its
    # keep on the lower shots instead.
    run(x0, x1, "x", y0, "NEAR", gated=True)
    run(x0, x1, "x", y1, "FAR")
    run(y0, y1, "y", x1, "RIGHT")
    run(y0, y1, "y", x0, "LEFT")

    # --- compound: three containers, two down and one stacked --------------
    # Beyond the frame's far-right corner, inside the hoarding.
    #
    # Position here is a sight-line problem, not a site-planning one. The hero
    # camera sits at +X/-Y, so anything placed off the frame's *left* is seen
    # through four storeys of steel and disappears - a compound on the far
    # left rendered as nothing at all. The clear ground from this camera is
    # right of x=28.8 and the near foreground, so the middle distance has to
    # be built there.
    base = Vector((x1 - 7.0, y1 - 10.0, 0.0))
    cabin = SITE["cabin"]
    for index, (dx, dy, dz) in enumerate(((0.0, 0.0, 0.0),
                                          (0.0, 2.72, 0.0),
                                          (0.35, 1.36, cabin[2]))):
        _site_box("Site_Cabin_%02d" % index, cabin,
                  (base.x + dx, base.y + dy,
                   ground_z + cabin[2] / 2.0 + dz),
                  site, cabin_mat, jitter(1.6))

    # --- laydown: bundled sections on bearers ------------------------------
    bundle, bearer = SITE["bundle"], SITE["bearer"]
    for index in range(4):
        y = y0 + 6.4 + index * 1.45
        x = 4.0 + rng.uniform(-0.35, 0.35)
        yaw = jitter(1.2)
        for end in (-1, 1):
            _site_box("Site_Bearer_%02d_%s" % (index, "AB"[end > 0]), bearer,
                      (x + end * bundle[0] * 0.34, y,
                       ground_z + bearer[2] / 2.0), site, timber_mat, yaw)
        _site_box("Site_Bundle_%02d" % index, bundle,
                  (x, y, ground_z + bearer[2] + bundle[2] / 2.0),
                  site, steel_mat, yaw)

    # --- jersey barriers, guiding the haul route to the gate ---------------
    barrier = SITE["barrier"]
    for index in range(7):
        _site_box("Site_Barrier_%02d" % index, barrier,
                  (gate_centre - 9.0 + index * (barrier[0] + 0.12),
                   y0 + 7.5 + rng.uniform(-0.2, 0.2),
                   ground_z + barrier[2] / 2.0),
                  site, conc_mat, jitter(1.0))

    # --- skip --------------------------------------------------------------
    _site_box("Site_Skip", SITE["skip"],
              (x1 - 20.0, y0 + 4.2, ground_z + SITE["skip"][2] / 2.0),
              site, skip_mat, jitter(4.0))

    # --- spoil heaps -------------------------------------------------------
    # Cones, not spheres: excavated material stands at its angle of repose,
    # about 34 degrees for damp granular fill, and a dome reads as a bin bag.
    for index, (cx, cy, radius) in enumerate(((x1 - 6.0, y1 - 19.0, 3.4),
                                              (x1 - 10.5, y1 - 24.0, 2.5))):
        depth = radius * math.tan(math.radians(34.0))
        bpy.ops.mesh.primitive_cone_add(
            vertices=24, radius1=radius, radius2=radius * 0.12, depth=depth,
            location=(cx, cy, ground_z + depth / 2.0))
        heap = bpy.context.active_object
        heap.name = "Site_Spoil_%02d" % index
        heap.data.materials.append(agg_mat)
        for coll in list(heap.users_collection):
            coll.objects.unlink(heap)
        site.objects.link(heap)

    # --- context beyond the hoarding ---------------------------------------
    # The reason the first two attempts at this still read as empty: a fence
    # in a void is a void with a fence in it. What makes a site look like a
    # place is what is happening *outside* its boundary - the neighbouring
    # sheds, the treeline, the fact that the horizon is occupied. Massing
    # blocks at 110-190 m do that for almost nothing: at that distance they
    # are silhouettes, so their shape budget is a box, and the sky's aerosol
    # term greys them into aerial perspective on its own.
    #
    # They also give the hard sky/ground horizon something to break against,
    # which was a separate item on the audit.
    context = bpy.data.collections.new("SiteSurrounds")
    site.children.link(context)
    mass_mat = _flat_material("MAT_Site_Surrounds", (0.052, 0.055, 0.058), 0.94)

    centre = Vector(((x0 + x1) / 2.0, (y0 + y1) / 2.0, 0.0))
    # Blocks up to 46 m wide dropped on 24 slots around a 150 m circle sit
    # about 39 m apart, so drawn blind they grew into each other - two of
    # them shared 7000 cubic metres. Reject a placement that lands inside
    # one already standing, and shrink the footprint as the attempts run
    # out so a crowded slot still gets a building.
    placed = []
    for index in range(24):
        for attempt in range(24):
            angle = (index / 24.0) * math.tau + rng.uniform(-0.05, 0.05)
            radius = rng.uniform(110.0, 190.0)
            shrink = 1.0 - 0.03 * attempt
            width = rng.uniform(16.0, 46.0) * shrink
            depth = rng.uniform(14.0, 38.0) * shrink
            yaw = jitter(28.0)
            cx = centre.x + math.cos(angle) * radius
            cy = centre.y + math.sin(angle) * radius
            # Half-extents of the footprint once it is turned on the spot.
            c, s = abs(math.cos(yaw)), abs(math.sin(yaw))
            hx = (width * c + depth * s) / 2.0
            hy = (width * s + depth * c) / 2.0
            if all(abs(cx - px) > hx + phx or abs(cy - py) > hy + phy
                   for px, py, phx, phy in placed):
                break
        placed.append((cx, cy, hx, hy))

        tall = rng.uniform(5.0, 16.0)
        _site_box("Site_Surround_%02d" % index, (width, depth, tall),
                  (cx, cy, ground_z + tall / 2.0),
                  context, mass_mat, yaw)

    total = len(site.objects) + len(context.objects)
    print("[scene_setup] site context: %d objects (%d surrounds)"
          % (total, len(context.objects)))
    return site


# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------

def setup_camera(shot="hero"):
    """Architectural camera: long lens, far back, shifted rather than tilted.

    Tilting a camera up at a building makes verticals converge - the classic
    amateur building photograph. Shifting the sensor instead keeps every
    column line parallel, which is what an architectural photographer does
    with a tilt-shift lens and what a client expects to see.
    """
    config = SCENE["shots"][shot]
    existing = bpy.data.objects.get("Camera_Main")
    if existing:
        bpy.data.objects.remove(existing, do_unlink=True)

    data = bpy.data.cameras.new("Camera_Main")
    data.lens = config.get("focal", SCENE["focal_length"])
    data.sensor_width = SCENE["sensor_width"]
    data.shift_y = SCENE["shift_y"]
    data.clip_start = 0.1
    data.clip_end = 1000.0

    camera = bpy.data.objects.new("Camera_Main", data)
    bpy.context.scene.collection.objects.link(camera)

    location = Vector(config["loc"])
    target = Vector(config["target"])
    camera.location = location
    camera.rotation_mode = "QUATERNION"
    camera.rotation_quaternion = (target - location).to_track_quat("-Z", "Y")

    if SCENE["use_dof"]:
        data.dof.use_dof = True
        data.dof.focus_distance = (target - location).length
        data.dof.aperture_fstop = SCENE["f_stop"]

    bpy.context.scene.camera = camera
    return camera


# ---------------------------------------------------------------------------
# Render settings
# ---------------------------------------------------------------------------

def setup_render(engine=None):
    """Engine, sampling, ambient occlusion and colour management.

    On Cycles, AO is not a separate pass - the path tracer produces contact
    shadow for free and a fast GI approximation would only fight it. On EEVEE,
    ambient occlusion is a real setting and has to be switched on explicitly
    or every internal corner renders flat.
    """
    scene = bpy.context.scene

    # Engine identifiers moved twice: 4.1 renamed EEVEE to BLENDER_EEVEE_NEXT,
    # 5.x folded it back to BLENDER_EEVEE. Accept either spelling and fall
    # back to whatever this build offers.
    requested = engine or SCENE["engine"]
    available = scene.render.bl_rna.properties["engine"].enum_items.keys()
    if requested not in available:
        aliases = {
            "BLENDER_EEVEE_NEXT": ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"),
            "BLENDER_EEVEE": ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"),
            "EEVEE": ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"),
        }
        requested = next(
            (name for name in aliases.get(requested, ()) if name in available),
            "CYCLES")
    scene.render.engine = requested
    scene.render.resolution_x, scene.render.resolution_y = SCENE["resolution"]
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = SCENE["film_transparent"]
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.compression = 15

    if scene.render.engine == "CYCLES":
        scene.cycles.samples = SCENE["samples"]
        scene.cycles.preview_samples = 32
        scene.cycles.use_denoising = True
        scene.cycles.use_adaptive_sampling = True
        scene.cycles.adaptive_threshold = 0.01
        # Two diffuse bounces are plenty for an open frame and cost far less
        # than the default: light has nowhere to get trapped here.
        scene.cycles.max_bounces = 8
        scene.cycles.diffuse_bounces = 2
        scene.cycles.glossy_bounces = 4
        scene.cycles.transmission_bounces = 2
        scene.cycles.caustics_reflective = False
        scene.cycles.caustics_refractive = False
    else:
        eevee = scene.eevee
        eevee.taa_render_samples = SCENE["eevee_samples"]
        # EEVEE Next replaced the old AO panel with ray-traced GI, so set
        # whichever attributes this build actually has.
        for attr, value in (("use_gtao", True),
                            ("gtao_distance", 0.6),
                            ("gtao_factor", 1.0),
                            ("use_raytracing", True),
                            ("use_soft_shadows", True)):
            if hasattr(eevee, attr):
                setattr(eevee, attr, value)

    # Colour management. AgX is the reason bright metal keeps its shape
    # instead of clipping to a white blob under a sun this strong.
    view = scene.view_settings
    view.view_transform = SCENE["view_transform"]
    view.exposure = SCENE["exposure"]
    try:
        view.look = SCENE["look"]
    except TypeError:
        view.look = "None"           # look names differ between builds

    return scene


def enable_shadow_catching(objects=None):
    """Make sure every structural object casts and receives shadow.

    Cycles has this on by default, but anything imported or generated with
    visibility flags touched can quietly stop casting - and a beam that casts
    no shadow is the fastest way to make a render look composited.
    """
    for obj in (objects or bpy.context.scene.objects):
        if obj.type != "MESH":
            continue
        obj.visible_shadow = True
        obj.visible_diffuse = True
        obj.visible_glossy = True


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def setup(shot="hero", engine=None):
    """Build the whole render scene. Safe to call once the frame exists."""
    setup_world()
    setup_sun()
    setup_ground()
    build_site_context()
    camera = setup_camera(shot)
    setup_render(engine)
    enable_shadow_catching()
    print("[scene_setup] shot=%s engine=%s"
          % (shot, bpy.context.scene.render.engine))
    return camera


def render(filepath, shot="hero", engine=None, samples=None):
    directory = os.path.dirname(os.path.abspath(filepath))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory, exist_ok=True)

    setup(shot, engine)
    if samples:
        scene = bpy.context.scene
        if scene.render.engine == "CYCLES":
            scene.cycles.samples = samples
        else:
            scene.eevee.taa_render_samples = samples

    bpy.context.scene.render.filepath = filepath
    bpy.ops.render.render(write_still=True)
    print("[scene_setup] rendered %s" % filepath)


def parse_args():
    argv = sys.argv
    args = {"render": None, "shot": "hero", "engine": None, "samples": None,
            "res": None}
    if "--" not in argv:
        return args
    argv = argv[argv.index("--") + 1:]

    i = 0
    while i < len(argv):
        if argv[i] == "--render" and i + 1 < len(argv):
            args["render"] = argv[i + 1]
            i += 1
        elif argv[i] == "--shot" and i + 1 < len(argv):
            args["shot"] = argv[i + 1]
            i += 1
        elif argv[i] == "--engine" and i + 1 < len(argv):
            args["engine"] = argv[i + 1]
            i += 1
        elif argv[i] in ("--samples", "--res") and i + 1 < len(argv):
            args[argv[i].lstrip("-")] = int(argv[i + 1])
            i += 1
        i += 1
    return args


def main():
    args = parse_args()
    if args["res"]:
        SCENE["resolution"] = (args["res"], int(args["res"] * 9 / 16))

    if args["render"]:
        render(args["render"], args["shot"], args["engine"], args["samples"])
    else:
        setup(args["shot"], args["engine"])


if __name__ == "__main__":
    main()
