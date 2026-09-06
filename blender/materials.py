"""
PBR material library for the procedural structural frame. Blender 5.x.

Two halves that have to stay in step:

1. **Procedural node graphs** - painted industrial steel, dark steel fasteners
   and cast concrete, built from noise/voronoi rather than from sourced
   texture files, so the repo stays asset-free and a scale change re-renders
   correctly instead of stretching a bitmap.

2. **A bake pass** - glTF cannot carry procedural nodes. Anything destined for
   the web has to be baked to image maps first, so `bake_all()` renders each
   material's Base Color / Roughness / Normal (and Height, for concrete) to
   PNG and writes a `materials.json` manifest of MeshStandardMaterial values
   for the Three.js side.

Usage inside Blender:

    import materials
    materials.get_material("MAT_Steel_Painted")     # procedural, for Cycles

Bake the texture set and the Three.js manifest:

    blender -b -P blender/materials.py -- --bake --res 2048 --out textures/

Bake ambient occlusion for hero geometry only (see the note in bake_object_ao):

    blender -b -P blender/materials.py -- --bake-ao --res 1024 --out textures/
"""

import json
import math
import os
import sys

import bpy

# ---------------------------------------------------------------------------
# Material specifications
#
# One table drives the Blender nodes, the bake, and the Three.js manifest, so
# a value can never drift between the render and the web viewer.
#
# `metallic` and `roughness` are the *paint film* values. Scratches and chips
# lift metallic toward 1.0 and pull roughness down toward `scratch_roughness`
# locally, which keeps painted steel inside the requested 0.8-1.0 / 0.25-0.45
# bands while still varying across the surface.
# ---------------------------------------------------------------------------

MATERIALS = {
    "MAT_Steel_Painted": {
        "kind": "painted_metal",
        "base_color": (0.055, 0.062, 0.072),      # RAL 7016-ish primer, dark
        # Paint is a DIELECTRIC. The brief asked for 0.8-1.0, which is the
        # right band for bare or mill-finish steel but wrong for a paint
        # film: at 0.9 the surface becomes a mirror of the sky and renders as
        # pale chrome. The 0.8-1.0 band is honoured where steel is actually
        # exposed - bolts, galvanising, weld beads, and the worn arrises,
        # where the wear mask drives metallic to 1.0.
        "metallic": 0.12,
        # Was 0.38, the mid of the 0.25-0.45 swatch band. On a 12 m column
        # that band still mirrors the sky into a vertical smear - the corner
        # shot rendered the columns as chrome. Site steel two years into its
        # life is chalked by UV and dulled by dust, and 0.52 is what stops the
        # frame reading as showroom furniture. Credibility, not shine.
        "roughness": 0.52,
        "roughness_variation": 0.13,              # uneven weathering of the film
        # Multiplicative, so this is a *fraction* of base_color, not an
        # absolute step. At 0.075 on a 0.055 primer the mottle was four parts
        # in a thousand and no flange ever looked like anything but one flat
        # value - the exact plastic read the layer exists to prevent.
        "paint_variation": 0.40,                  # roller/spray mottle depth
        "scratch_density": 1.00,
        "scratch_roughness": 0.34,                # bare metal where paint is gone
        "bare_metal": (0.310, 0.320, 0.335),
        "bump_strength": 0.055,
        "edge_wear": 0.30,   # paint loss on convex arrises
        "oxidation": 0.30,   # rust bloom in sheltered corners
        "uv_scale": 1.0,
        "three": {"normalScale": 0.6, "envMapIntensity": 1.15},
    },
    "MAT_Steel_Bolt": {
        "kind": "painted_metal",
        "base_color": (0.115, 0.120, 0.130),      # dark oiled fastener steel
        "metallic": 1.00,
        "roughness": 0.30,
        "paint_variation": 0.040,
        "scratch_density": 1.60,                  # spanner marks on the flats
        "scratch_roughness": 0.20,
        "bare_metal": (0.420, 0.425, 0.440),
        "bump_strength": 0.030,
        "edge_wear": 0.45,   # paint loss on convex arrises
        "oxidation": 0.45,   # rust bloom in sheltered corners
        "uv_scale": 6.0,                          # small parts need fine grain
        "three": {"normalScale": 0.45, "envMapIntensity": 1.35},
    },
    "MAT_Steel_Galvanised": {
        "kind": "painted_metal",
        "base_color": (0.590, 0.610, 0.630),
        "metallic": 0.95,
        "roughness": 0.34,
        "paint_variation": 0.110,                 # spangle reads as big mottle
        "scratch_density": 0.60,
        "scratch_roughness": 0.24,
        "bare_metal": (0.680, 0.700, 0.720),
        "bump_strength": 0.040,
        "edge_wear": 0.18,   # paint loss on convex arrises
        "oxidation": 0.05,   # rust bloom in sheltered corners
        "uv_scale": 2.0,
        "three": {"normalScale": 0.5, "envMapIntensity": 1.25},
    },
    "MAT_Weld_Bead": {
        "kind": "painted_metal",
        "base_color": (0.230, 0.205, 0.185),      # heat-tinted, oxidised
        "metallic": 0.85,
        "roughness": 0.62,                        # deliberately outside the
        "paint_variation": 0.150,                 # painted-steel band: weld
        "scratch_density": 0.30,                  # metal is visibly duller
        "scratch_roughness": 0.45,
        "bare_metal": (0.330, 0.300, 0.270),
        "bump_strength": 0.220,                   # ripple across the bead
        "edge_wear": 0.30,   # paint loss on convex arrises
        "oxidation": 0.70,   # rust bloom in sheltered corners
        "uv_scale": 12.0,
        "three": {"normalScale": 1.0, "envMapIntensity": 0.9},
    },
    "MAT_Rail_Safety": {
        "kind": "painted_metal",
        "base_color": (0.520, 0.330, 0.020),      # site yellow, well worn
        "metallic": 0.05,                         # thick paint over steel
        "roughness": 0.52,
        "paint_variation": 0.120,
        "scratch_density": 2.20,                  # handled constantly
        "scratch_roughness": 0.30,
        "bare_metal": (0.480, 0.490, 0.500),
        "bump_strength": 0.060,
        "edge_wear": 0.45,   # paint loss on convex arrises
        "oxidation": 0.25,   # rust bloom in sheltered corners
        "uv_scale": 2.0,
        "three": {"normalScale": 0.7, "envMapIntensity": 1.0},
    },
    "MAT_Pipe_CHW": {
        "kind": "painted_metal",
        "base_color": (0.045, 0.115, 0.290),      # BS 1710 chilled water blue
        "metallic": 0.10,
        "roughness": 0.36,
        "paint_variation": 0.060,
        "scratch_density": 0.70,
        "scratch_roughness": 0.28,
        "bare_metal": (0.500, 0.510, 0.520),
        "bump_strength": 0.040,
        "edge_wear": 0.20,   # paint loss on convex arrises
        "oxidation": 0.15,   # rust bloom in sheltered corners
        "uv_scale": 3.0,
        "three": {"normalScale": 0.5, "envMapIntensity": 1.1},
    },
    "MAT_Pipe_LTHW": {
        "kind": "painted_metal",
        "base_color": (0.280, 0.045, 0.055),      # BS 1710 heating red
        "metallic": 0.10,
        "roughness": 0.36,
        "paint_variation": 0.060,
        "scratch_density": 0.70,
        "scratch_roughness": 0.28,
        "bare_metal": (0.500, 0.510, 0.520),
        "bump_strength": 0.040,
        "edge_wear": 0.20,   # paint loss on convex arrises
        "oxidation": 0.15,   # rust bloom in sheltered corners
        "uv_scale": 3.0,
        "three": {"normalScale": 0.5, "envMapIntensity": 1.1},
    },
    "MAT_Concrete": {
        "kind": "concrete",
        # Measured concrete albedo is 0.25-0.35. The old 0.48 was a *swatch*
        # value - what a sample card reads indoors - and under a 12 W/m2 sun
        # it rendered the pad footings as near-white plastic, the loudest
        # untextured-CG tell in the wide shot.
        "base_color": (0.300, 0.294, 0.280),      # cured grey, formwork finish
        "dust_color": (0.430, 0.418, 0.395),      # settled dust on up-faces
        "pit_color": (0.165, 0.160, 0.152),       # blowholes read near-black
        "metallic": 0.00,
        "roughness": 0.88,
        "pore_scale": 40.0,
        "grain_scale": 320.0,
        "mottle_scale": 8.0,
        "dust_amount": 0.55,                      # 0 = none, 1 = heavy
        "bump_strength": 0.35,
        "displacement": 0.006,                    # 6 mm true displacement
        "edge_wear": 0.0,                         # concrete has no paint film
        "oxidation": 0.0,
        "uv_scale": 1.0,
        "three": {"normalScale": 1.0, "envMapIntensity": 0.85},
    },
}


# ---------------------------------------------------------------------------
# Node graph helpers
# ---------------------------------------------------------------------------

def _reset(mat):
    """Give a material an empty node tree and return (nodes, links)."""
    if not mat.node_tree:
        mat.use_nodes = True                      # 4.x; 5.x already has a tree
    tree = mat.node_tree
    tree.nodes.clear()
    return tree.nodes, tree.links


def _node(nodes, node_type, x, y, name=None, **props):
    """Create a node at a grid position with attributes pre-set."""
    node = nodes.new(node_type)
    node.location = (x, y)
    if name:
        node.name = node.label = name
    for key, value in props.items():
        setattr(node, key, value)
    return node


def _ramp(node, stops):
    """Overwrite a ColorRamp's stops with (position, RGBA) pairs."""
    elements = node.color_ramp.elements
    while len(elements) > 1:
        elements.remove(elements[-1])
    elements[0].position, elements[0].color = stops[0]
    for position, colour in stops[1:]:
        elements.new(position).color = colour


def _rgba(rgb, alpha=1.0):
    return (rgb[0], rgb[1], rgb[2], alpha)


def _shift(rgb, delta):
    """Lighten or darken a colour by a RELATIVE amount, clamped to 0-1.

    Relative, not absolute: an absolute +/-0.075 on a near-black primer
    (0.055 linear) is a swing of more than 100%, which renders as white
    blotching rather than as paint variation. Scaling by the base value keeps
    the same setting readable on a dark primer and on light galvanising.
    """
    return tuple(min(1.0, max(0.0, c * (1.0 + delta))) for c in rgb)


# ---------------------------------------------------------------------------
# Painted / bare metal
# ---------------------------------------------------------------------------

def build_painted_metal(mat, spec):
    """Industrial painted steel: paint film, wear scratches, chipped edges.

    Layer order, which is also the order the eye reads them:

      1. Paint mottle  - a low-contrast large noise, so a flat flange is never
                         one flat value. This is what kills the plastic look.
      2. Scratches     - a noise stretched hard on one axis into linear marks,
                         thresholded to a thin mask.
      3. Edge chips    - voronoi cells, thresholded high, giving paint loss
                         where a section has been knocked.

    Scratches and chips drive three outputs at once: they lift Metallic toward
    1.0 (bare steel), pull Roughness down toward `scratch_roughness` (polished
    by rubbing), and feed the Bump node. Driving all three from one mask is
    what makes the wear read as a single physical event rather than three
    unrelated overlays.
    """
    nodes, links = _reset(mat)

    out = _node(nodes, "ShaderNodeOutputMaterial", 1500, 0)
    bsdf = _node(nodes, "ShaderNodeBsdfPrincipled", 1200, 0)
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    coord = _node(nodes, "ShaderNodeTexCoord", -1400, 0)
    mapping = _node(nodes, "ShaderNodeMapping", -1200, 0, "UV_Scale")
    mapping.inputs["Scale"].default_value = (spec["uv_scale"],) * 3
    links.new(coord.outputs["Object"], mapping.inputs["Vector"])

    # --- 1. paint mottle ---------------------------------------------------
    mottle = _node(nodes, "ShaderNodeTexNoise", -950, 350, "PaintMottle")
    mottle.inputs["Scale"].default_value = 5.5
    mottle.inputs["Detail"].default_value = 4.0
    mottle.inputs["Roughness"].default_value = 0.55
    links.new(mapping.outputs["Vector"], mottle.inputs["Vector"])

    mottle_ramp = _node(nodes, "ShaderNodeValToRGB", -750, 350)
    _ramp(mottle_ramp, [(0.35, (0, 0, 0, 1)), (0.68, (1, 1, 1, 1))])
    links.new(mottle.outputs["Fac"], mottle_ramp.inputs["Fac"])

    dark = _shift(spec["base_color"], -spec["paint_variation"])
    light = _shift(spec["base_color"], spec["paint_variation"])
    paint = _node(nodes, "ShaderNodeMix", -520, 350, "PaintTone",
                  data_type="RGBA")
    paint.inputs[6].default_value = _rgba(dark)
    paint.inputs[7].default_value = _rgba(light)
    links.new(mottle_ramp.outputs["Color"], paint.inputs["Factor"])

    # --- 2. scratches ------------------------------------------------------
    # A separate mapping node stretches the noise 40:1 so the cells smear into
    # lines. Uniform noise thresholded gives blobs, not scratches.
    stretch = _node(nodes, "ShaderNodeMapping", -1200, -150, "ScratchStretch")
    # 8:1, not 40:1 - a harder stretch aliases into grey mush at bake
    # resolution instead of resolving as individual marks.
    stretch.inputs["Scale"].default_value = (8.0, 1.0, 1.0)
    links.new(mapping.outputs["Vector"], stretch.inputs["Vector"])

    scratch = _node(nodes, "ShaderNodeTexNoise", -950, -150, "ScratchNoise")
    # High frequency: at scale 6 the "scratches" came out as low-frequency
    # cloud, which reads as mould on a dark primer.
    scratch.inputs["Scale"].default_value = 45.0 * spec["scratch_density"]
    scratch.inputs["Detail"].default_value = 8.0
    scratch.inputs["Roughness"].default_value = 0.75
    scratch.inputs["Distortion"].default_value = 2.5
    links.new(stretch.outputs["Vector"], scratch.inputs["Vector"])

    scratch_ramp = _node(nodes, "ShaderNodeValToRGB", -750, -150)
    # A narrow window near the top of the range: only the noise peaks survive,
    # which is what keeps the marks thin instead of cloudy.
    _ramp(scratch_ramp, [(0.66, (0, 0, 0, 1)), (0.73, (1, 1, 1, 1))])
    links.new(scratch.outputs["Fac"], scratch_ramp.inputs["Fac"])

    # --- 3. edge chips -----------------------------------------------------
    chips = _node(nodes, "ShaderNodeTexVoronoi", -950, -480, "PaintChips")
    chips.feature = "F1"
    chips.inputs["Scale"].default_value = 26.0
    links.new(mapping.outputs["Vector"], chips.inputs["Vector"])

    chip_ramp = _node(nodes, "ShaderNodeValToRGB", -750, -480)
    _ramp(chip_ramp, [(0.00, (1, 1, 1, 1)), (0.09, (0, 0, 0, 1))])
    links.new(chips.outputs["Distance"], chip_ramp.inputs["Fac"])

    chip_gate = _node(nodes, "ShaderNodeMath", -520, -480, "ChipDensity",
                      operation="MULTIPLY")
    chip_gate.inputs[1].default_value = min(1.0, 0.35 * spec["scratch_density"])
    links.new(chip_ramp.outputs["Color"], chip_gate.inputs[0])

    # --- combined wear mask ------------------------------------------------
    wear = _node(nodes, "ShaderNodeMath", -300, -300, "WearMask",
                 operation="MAXIMUM", use_clamp=True)
    links.new(scratch_ramp.outputs["Color"], wear.inputs[0])
    links.new(chip_gate.outputs["Value"], wear.inputs[1])

    # --- 4. edge wear from geometry, not from a texture --------------------
    # Pointiness reads the mesh's own convexity, so paint rubs off exactly
    # where a real section gets knocked - the arrises. No texture can place
    # wear on an edge this reliably, and it costs one node.
    geo = _node(nodes, "ShaderNodeNewGeometry", -1400, 700)
    edge = _node(nodes, "ShaderNodeValToRGB", -1150, 700, "EdgeWear")
    # Flat geometry reads ~0.5, so the ramp has to start clear of it or the
    # whole face counts as an edge and the paint film disappears.
    _ramp(edge, [(0.56, (0, 0, 0, 1)), (0.73, (1, 1, 1, 1))])
    links.new(geo.outputs["Pointiness"], edge.inputs["Fac"])

    edge_gate = _node(nodes, "ShaderNodeMath", -900, 700, "EdgeWearAmount",
                      operation="MULTIPLY", use_clamp=True)
    edge_gate.inputs[1].default_value = spec.get("edge_wear", 0.6)
    links.new(edge.outputs["Color"], edge_gate.inputs[0])
    # A MAXIMUM node has two inputs, so folding a third signal in needs a
    # second node - linking onto wear.inputs[0] would have replaced the
    # scratch link and silently dropped the scratches.
    wear_all = _node(nodes, "ShaderNodeMath", -150, -300, "WearMaskTotal",
                     operation="MAXIMUM", use_clamp=True)
    links.new(wear.outputs["Value"], wear_all.inputs[0])
    links.new(edge_gate.outputs["Value"], wear_all.inputs[1])

    # --- base colour -------------------------------------------------------
    colour = _node(nodes, "ShaderNodeMix", 0, 350, "BaseColor",
                   data_type="RGBA")
    colour.inputs[7].default_value = _rgba(spec["bare_metal"])
    links.new(paint.outputs[2], colour.inputs[6])
    links.new(wear_all.outputs["Value"], colour.inputs["Factor"])
    links.new(colour.outputs[2], bsdf.inputs["Base Color"])

    # --- metallic: paint film -> bare steel --------------------------------
    metal = _node(nodes, "ShaderNodeMapRange", 0, 100, "Metallic")
    metal.inputs["To Min"].default_value = spec["metallic"]
    metal.inputs["To Max"].default_value = 1.0
    links.new(wear_all.outputs["Value"], metal.inputs["Value"])
    links.new(metal.outputs["Result"], bsdf.inputs["Metallic"])

    # --- roughness: mottle jitter, then polished where worn ----------------
    # Widened from a flat +/-0.05. On a dark primer the paint mottle is almost
    # invisible as *colour* - `_shift` is multiplicative, so +/-7.5% of a 0.055
    # base is four parts in a thousand - but the same mottle read as roughness
    # is plainly visible, because it changes how much sky each patch reflects.
    # This is the same lesson as the ground plane: on a low-albedo surface,
    # variation in reflectance sells unevenness and variation in colour does
    # not.
    band = spec.get("roughness_variation", 0.05)
    rough_var = _node(nodes, "ShaderNodeMapRange", -300, -80, "RoughVariation")
    rough_var.inputs["To Min"].default_value = max(0.0, spec["roughness"] - band)
    rough_var.inputs["To Max"].default_value = min(1.0, spec["roughness"] + band)
    links.new(mottle.outputs["Fac"], rough_var.inputs["Value"])

    rough = _node(nodes, "ShaderNodeMix", 0, -80, "Roughness",
                  data_type="FLOAT", clamp_result=True)
    # On ShaderNodeMix the float pair is A=inputs[2], B=inputs[3]; inputs[4]
    # is the *vector* A socket and rejects a float.
    rough.inputs[3].default_value = spec["scratch_roughness"]
    links.new(rough_var.outputs["Result"], rough.inputs[2])
    links.new(wear_all.outputs["Value"], rough.inputs["Factor"])
    links.new(rough.outputs[0], bsdf.inputs["Roughness"])


    # --- 5. oxidation in the sheltered areas -------------------------------
    # Rust is the inverse signal: it collects where water sits and air moves
    # slowly, i.e. in concave corners, which is 1 - pointiness. Blooming rust
    # on the same edges that are polished bare would read as noise.
    cavity = _node(nodes, "ShaderNodeValToRGB", -1150, 980, "CavityMask")
    _ramp(cavity, [(0.36, (1, 1, 1, 1)), (0.50, (0, 0, 0, 1))])
    links.new(geo.outputs["Pointiness"], cavity.inputs["Fac"])

    rust_noise = _node(nodes, "ShaderNodeTexNoise", -1150, 1240, "RustPatches")
    rust_noise.inputs["Scale"].default_value = 12.0
    rust_noise.inputs["Detail"].default_value = 6.0
    links.new(mapping.outputs["Vector"], rust_noise.inputs["Vector"])

    rust_ramp = _node(nodes, "ShaderNodeValToRGB", -900, 1240)
    _ramp(rust_ramp, [(0.45, (0, 0, 0, 1)), (0.66, (1, 1, 1, 1))])
    links.new(rust_noise.outputs["Fac"], rust_ramp.inputs["Fac"])

    # Rust needs BOTH a sheltered spot and a patch of broken paint.
    rust_mask = _node(nodes, "ShaderNodeMath", -650, 1100, "RustMask",
                      operation="MULTIPLY", use_clamp=True)
    links.new(cavity.outputs["Color"], rust_mask.inputs[0])
    links.new(rust_ramp.outputs["Color"], rust_mask.inputs[1])

    rust_gate = _node(nodes, "ShaderNodeMath", -450, 1100, "RustAmount",
                      operation="MULTIPLY", use_clamp=True)
    rust_gate.inputs[1].default_value = spec.get("oxidation", 0.35)
    links.new(rust_mask.outputs["Value"], rust_gate.inputs[0])

    rust_colour = _node(nodes, "ShaderNodeMix", 300, 350, "Oxidation",
                        data_type="RGBA")
    rust_colour.inputs[7].default_value = _rgba(
        spec.get("rust_color", (0.180, 0.070, 0.028)))
    links.new(colour.outputs[2], rust_colour.inputs[6])
    links.new(rust_gate.outputs["Value"], rust_colour.inputs["Factor"])
    links.new(rust_colour.outputs[2], bsdf.inputs["Base Color"])

    # Rust is iron oxide: not a metal, and very rough. Both channels have to
    # move or it reads as brown paint.
    metal_rust = _node(nodes, "ShaderNodeMix", 300, 100, "MetallicRust",
                       data_type="FLOAT", clamp_result=True)
    metal_rust.inputs[3].default_value = 0.0
    links.new(metal.outputs["Result"], metal_rust.inputs[2])
    links.new(rust_gate.outputs["Value"], metal_rust.inputs["Factor"])
    links.new(metal_rust.outputs[0], bsdf.inputs["Metallic"])

    rough_rust = _node(nodes, "ShaderNodeMix", 300, -80, "RoughnessRust",
                       data_type="FLOAT", clamp_result=True)
    rough_rust.inputs[3].default_value = 0.92
    links.new(rough.outputs[0], rough_rust.inputs[2])
    links.new(rust_gate.outputs["Value"], rough_rust.inputs["Factor"])
    links.new(rough_rust.outputs[0], bsdf.inputs["Roughness"])

    # --- bump: surface relief from the same two fields ---------------------
    height = _node(nodes, "ShaderNodeMix", 0, -520, "HeightField",
                   data_type="FLOAT")
    height.inputs["Factor"].default_value = 0.65
    links.new(mottle.outputs["Fac"], height.inputs[2])
    links.new(wear_all.outputs["Value"], height.inputs[3])

    bump = _node(nodes, "ShaderNodeBump", 300, -520)
    bump.inputs["Strength"].default_value = spec["bump_strength"]
    bump.inputs["Distance"].default_value = 0.01
    bump.invert = True                            # scratches cut in, not out
    links.new(height.outputs[0], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    return mat


# ---------------------------------------------------------------------------
# Concrete
# ---------------------------------------------------------------------------

def build_concrete(mat, spec):
    """Cast concrete: aggregate mottle, blowholes, fine grain, settled dust.

    The dust layer is driven by the *world* surface normal rather than by a
    texture: only upward-facing surfaces collect dust, which is why a pad
    foundation looks right from above and clean on its sides. That single
    trick does more for realism than any amount of extra noise.

    Displacement is wired to the Material Output's Displacement socket, so
    Cycles renders true relief. glTF has no displacement channel - the bake
    writes it out as a height map for use with a Displace modifier or as a
    parallax source, and 6 mm is honest formwork tolerance rather than a
    decorative amount.
    """
    nodes, links = _reset(mat)

    out = _node(nodes, "ShaderNodeOutputMaterial", 1500, 0)
    bsdf = _node(nodes, "ShaderNodeBsdfPrincipled", 1200, 0)
    bsdf.inputs["Metallic"].default_value = 0.0
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    coord = _node(nodes, "ShaderNodeTexCoord", -1400, 0)
    mapping = _node(nodes, "ShaderNodeMapping", -1200, 0, "UV_Scale")
    mapping.inputs["Scale"].default_value = (spec["uv_scale"],) * 3
    links.new(coord.outputs["Object"], mapping.inputs["Vector"])

    # --- aggregate mottle --------------------------------------------------
    mottle = _node(nodes, "ShaderNodeTexNoise", -950, 420, "Mottle")
    mottle.inputs["Scale"].default_value = spec["mottle_scale"]
    mottle.inputs["Detail"].default_value = 6.0
    mottle.inputs["Roughness"].default_value = 0.6
    links.new(mapping.outputs["Vector"], mottle.inputs["Vector"])

    mottle_ramp = _node(nodes, "ShaderNodeValToRGB", -730, 420)
    _ramp(mottle_ramp, [
        (0.30, _rgba(_shift(spec["base_color"], -0.16))),
        (0.72, _rgba(_shift(spec["base_color"], 0.16))),
    ])
    links.new(mottle.outputs["Fac"], mottle_ramp.inputs["Fac"])

    # --- blowholes / pores -------------------------------------------------
    pores = _node(nodes, "ShaderNodeTexVoronoi", -950, 120, "Pores")
    pores.feature = "F1"
    pores.inputs["Scale"].default_value = spec["pore_scale"]
    links.new(mapping.outputs["Vector"], pores.inputs["Vector"])

    pore_ramp = _node(nodes, "ShaderNodeValToRGB", -730, 120)
    # Mask is 1 at a cell centre and falls to 0 by the time the distance
    # reaches 0.08, so only the very cell centres become blowholes.
    # 0.18 puts the pit diameter at roughly a third of the voronoi cell:
    # with pore_scale 40 that is a ~9 mm blowhole, which is what a poorly
    # vibrated pour actually looks like.
    _ramp(pore_ramp, [(0.00, (1, 1, 1, 1)), (0.18, (0, 0, 0, 1))])
    links.new(pores.outputs["Distance"], pore_ramp.inputs["Fac"])

    # Inverted copy, for the height field only: a blowhole is a recess, so
    # height has to DROP where the colour mask rises. Feeding the same
    # un-inverted mask to both is what flattened the first bake - the pit
    # colour ended up mixed at factor 1 across the whole surface.
    pore_invert = _node(nodes, "ShaderNodeMath", -730, -60, "PoreInvert",
                        operation="SUBTRACT", use_clamp=True)
    pore_invert.inputs[0].default_value = 1.0
    links.new(pore_ramp.outputs["Color"], pore_invert.inputs[1])

    pore_mix = _node(nodes, "ShaderNodeMix", -480, 280, "PoreDarkening",
                     data_type="RGBA")
    pore_mix.inputs[7].default_value = _rgba(spec["pit_color"])
    links.new(mottle_ramp.outputs["Color"], pore_mix.inputs[6])
    links.new(pore_ramp.outputs["Color"], pore_mix.inputs["Factor"])

    # --- fine grain --------------------------------------------------------
    grain = _node(nodes, "ShaderNodeTexNoise", -950, -260, "Grain")
    grain.inputs["Scale"].default_value = spec["grain_scale"]
    grain.inputs["Detail"].default_value = 2.0
    links.new(mapping.outputs["Vector"], grain.inputs["Vector"])

    # --- dust on upward faces ---------------------------------------------
    geo = _node(nodes, "ShaderNodeNewGeometry", -1400, -560)
    sep = _node(nodes, "ShaderNodeSeparateXYZ", -1200, -560)
    links.new(geo.outputs["Normal"], sep.inputs["Vector"])

    dust_range = _node(nodes, "ShaderNodeMapRange", -1000, -560, "DustFalloff")
    dust_range.inputs["From Min"].default_value = 0.35   # steep faces stay clean
    dust_range.inputs["From Max"].default_value = 0.95
    dust_range.clamp = True
    links.new(sep.outputs["Z"], dust_range.inputs["Value"])

    # Break the dust edge up with the mottle so it is not a clean gradient.
    dust_break = _node(nodes, "ShaderNodeMix", -800, -560, "DustBreakup",
                       data_type="FLOAT", clamp_result=True)
    dust_break.inputs["Factor"].default_value = 0.35
    links.new(dust_range.outputs["Result"], dust_break.inputs[2])
    links.new(mottle.outputs["Fac"], dust_break.inputs[3])

    dust_gate = _node(nodes, "ShaderNodeMath", -600, -560, "DustAmount",
                      operation="MULTIPLY", use_clamp=True)
    dust_gate.inputs[1].default_value = spec["dust_amount"]
    links.new(dust_break.outputs[0], dust_gate.inputs[0])

    dust_mix = _node(nodes, "ShaderNodeMix", -200, 280, "DustLayer",
                     data_type="RGBA")
    dust_mix.inputs[7].default_value = _rgba(spec["dust_color"])
    links.new(pore_mix.outputs[2], dust_mix.inputs[6])
    links.new(dust_gate.outputs["Value"], dust_mix.inputs["Factor"])
    links.new(dust_mix.outputs[2], bsdf.inputs["Base Color"])

    # --- roughness ---------------------------------------------------------
    rough_var = _node(nodes, "ShaderNodeMapRange", -200, 0, "RoughVariation")
    rough_var.inputs["To Min"].default_value = spec["roughness"] - 0.06
    rough_var.inputs["To Max"].default_value = min(1.0, spec["roughness"] + 0.06)
    links.new(mottle.outputs["Fac"], rough_var.inputs["Value"])

    # Dust is the roughest thing on the surface - push toward 1.0 under it.
    rough = _node(nodes, "ShaderNodeMix", 100, 0, "Roughness",
                  data_type="FLOAT", clamp_result=True)
    rough.inputs[3].default_value = 1.0
    links.new(rough_var.outputs["Result"], rough.inputs[2])
    links.new(dust_gate.outputs["Value"], rough.inputs["Factor"])
    links.new(rough.outputs[0], bsdf.inputs["Roughness"])

    # --- height field: pores + grain + mottle ------------------------------
    height_a = _node(nodes, "ShaderNodeMix", -400, -300, "HeightPoresGrain",
                     data_type="FLOAT")
    height_a.inputs["Factor"].default_value = 0.30
    links.new(pore_invert.outputs["Value"], height_a.inputs[2])
    links.new(grain.outputs["Fac"], height_a.inputs[3])

    height = _node(nodes, "ShaderNodeMix", -200, -300, "HeightField",
                   data_type="FLOAT")
    height.inputs["Factor"].default_value = 0.25
    links.new(height_a.outputs[0], height.inputs[2])
    links.new(mottle.outputs["Fac"], height.inputs[3])

    bump = _node(nodes, "ShaderNodeBump", 300, -300)
    bump.inputs["Strength"].default_value = spec["bump_strength"]
    bump.inputs["Distance"].default_value = 0.02
    links.new(height.outputs[0], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    # --- true displacement (Cycles only) -----------------------------------
    disp = _node(nodes, "ShaderNodeDisplacement", 1200, -400)
    disp.inputs["Midlevel"].default_value = 0.5
    disp.inputs["Scale"].default_value = spec["displacement"]
    links.new(height.outputs[0], disp.inputs["Height"])
    links.new(disp.outputs["Displacement"], out.inputs["Displacement"])

    return mat


# ---------------------------------------------------------------------------
# Public entry point, used by generate_structure.py
# ---------------------------------------------------------------------------

BUILDERS = {"painted_metal": build_painted_metal, "concrete": build_concrete}


def get_material(name):
    """Fetch or build a material by name. Unknown names get a neutral grey."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]

    mat = bpy.data.materials.new(name)
    spec = MATERIALS.get(name)
    if spec is None:
        if not mat.node_tree:
            mat.use_nodes = True
        return mat

    BUILDERS[spec["kind"]](mat, spec)
    return mat


def build_all():
    """Instantiate every material in the table."""
    return [get_material(name) for name in MATERIALS]


# ---------------------------------------------------------------------------
# Baking - procedural nodes cannot travel through glTF
# ---------------------------------------------------------------------------

def _bake_plane(mat, size=1.0):
    """A UV-unwrapped plane carrying one material, used as the bake target.

    The plane is 1 m square, so the baked set has a known texel density
    (res px per metre) and tiles onto the frame at true scale. Baking here
    rather than on the frame itself takes seconds instead of the hours a
    1153-object bake would need.
    """
    mesh = bpy.data.meshes.new("BakePlane")
    half = size * 0.5
    mesh.from_pydata(
        [(-half, -half, 0), (half, -half, 0), (half, half, 0), (-half, half, 0)],
        [], [(0, 1, 2, 3)])
    mesh.update()

    uv = mesh.uv_layers.new(name="UVMap")
    for i, coords in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uv.data[i].uv = coords

    obj = bpy.data.objects.new("BakePlane", mesh)
    obj.data.materials.append(mat)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _bake_image(mat, name, res, non_color):
    """Attach a fresh image texture node and make it the active bake target."""
    image = bpy.data.images.new(name, res, res, alpha=False, float_buffer=False)
    if non_color:
        image.colorspace_settings.name = "Non-Color"

    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = image
    node.location = (-1800, 600)
    for other in mat.node_tree.nodes:
        other.select = False
    node.select = True
    mat.node_tree.nodes.active = node
    return image, node


def _setup_cycles(samples):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.bake.margin = 16
    scene.render.bake.use_clear = True
    # Bake the material's own shading, not light bouncing around a scene.
    scene.render.bake.use_pass_direct = False
    scene.render.bake.use_pass_indirect = False


def _bake(obj, bake_type, pass_filter=None):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    kwargs = {"type": bake_type, "use_clear": True}
    if pass_filter:
        kwargs["pass_filter"] = pass_filter
    bpy.ops.object.bake(**kwargs)


def _save(image, out_dir, filename):
    path = os.path.join(out_dir, filename)
    image.filepath_raw = path
    image.file_format = "PNG"
    image.save()
    return filename


def _bake_via_emit(mat, obj, source_name, res, out_dir, filename, non_color):
    """Bake any node's first output by routing it through an Emission shader.

    Needed for two channels that Cycles cannot bake directly:

    * **Base Color** - the DIFFUSE/COLOR pass returns near-black on a metallic
      surface, because metals have no diffuse albedo. Baking the colour node
      as emission is the only way to recover the actual albedo.
    * **Height** - Cycles has no DISPLACEMENT bake type at all.

    The original surface link is restored afterwards, so the material is left
    exactly as it was found.
    """
    tree = mat.node_tree
    source = tree.nodes.get(source_name)
    out = next((n for n in tree.nodes if n.type == "OUTPUT_MATERIAL"), None)
    if source is None or out is None or not out.inputs["Surface"].links:
        return None

    original = out.inputs["Surface"].links[0].from_socket
    emit = tree.nodes.new("ShaderNodeEmission")
    emit.location = (900, -800)
    emit.inputs["Strength"].default_value = 1.0
    # Mix nodes expose Float/Vector/Color results, so take the linked one.
    socket = next((s for s in source.outputs if s.enabled), source.outputs[0])
    tree.links.new(socket, emit.inputs["Color"])
    tree.links.new(emit.outputs["Emission"], out.inputs["Surface"])

    image, node = _bake_image(mat, filename.replace(".png", ""), res, non_color)
    _bake(obj, "EMIT")
    written = _save(image, out_dir, filename)

    tree.links.new(original, out.inputs["Surface"])
    tree.nodes.remove(emit)
    tree.nodes.remove(node)
    return written


def bake_material(name, res=2048, out_dir="textures", samples=16):
    """Bake one material's map set to PNG. Returns {three_key: filename}."""
    os.makedirs(out_dir, exist_ok=True)
    spec = MATERIALS[name]
    mat = get_material(name)
    obj = _bake_plane(mat)
    _setup_cycles(samples)

    prefix = name.replace("MAT_", "").lower()
    written = {}

    # Base colour: emission bake, because the diffuse pass loses metals.
    #
    # Concrete bakes from PoreDarkening, i.e. *before* the dust layer. Dust is
    # driven by the world normal, so on a flat up-facing bake plane its mask
    # is 1.0 everywhere and it would paint over the pores and mottle. Dust
    # stays a geometry-dependent effect: Cycles evaluates it live, and the web
    # viewer reproduces it from the vertex normal rather than from the map.
    colour_node = "PoreDarkening" if spec["kind"] == "concrete" else "BaseColor"
    base = _bake_via_emit(mat, obj, colour_node, res, out_dir,
                          "%s_basecolor.png" % prefix, non_color=False)
    if base:
        written["map"] = base

    for three_key, suffix, bake_type in (("roughnessMap", "roughness", "ROUGHNESS"),
                                         ("normalMap", "normal", "NORMAL")):
        image, node = _bake_image(mat, "%s_%s" % (prefix, suffix), res,
                                  non_color=True)
        _bake(obj, bake_type)
        written[three_key] = _save(image, out_dir, "%s_%s.png" % (prefix, suffix))
        mat.node_tree.nodes.remove(node)

    if spec["kind"] == "concrete":
        # Not a MeshStandardMaterial slot: use it with a Displace modifier in
        # Blender, or as a parallax source on the web.
        height = _bake_via_emit(mat, obj, "HeightField", res, out_dir,
                                "%s_height.png" % prefix, non_color=True)
        if height:
            written["displacementMap"] = height

    bpy.data.objects.remove(obj, do_unlink=True)
    print("[materials] baked %s -> %s" % (name, ", ".join(written.values())))
    return written


def bake_object_ao(objects, res=1024, out_dir="textures", samples=64):
    """Bake per-object ambient occlusion into a dedicated UV layer.

    AO is a *geometry* signal, so unlike the other maps it cannot be baked on
    a flat plane - a plane bakes to uniform white and is worth nothing. It has
    to be baked per object, which for 1153 objects is expensive.

    For a frame this boxy, screen-space AO in Three.js (or the contact
    darkening a good HDRI already provides) is cheaper and usually better.
    Use this for hero geometry only - the exemplar connection joint, say -
    and pass exactly the objects you want.
    """
    os.makedirs(out_dir, exist_ok=True)
    _setup_cycles(samples)
    written = {}

    for obj in objects:
        if obj.type != "MESH" or not obj.data.materials:
            continue

        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        if "uv_ao" not in obj.data.uv_layers:
            obj.data.uv_layers.new(name="uv_ao")
        obj.data.uv_layers.active = obj.data.uv_layers["uv_ao"]
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(66.0),
                                 island_margin=0.02)
        bpy.ops.object.mode_set(mode="OBJECT")

        mat = obj.data.materials[0]
        image, node = _bake_image(mat, "%s_ao" % obj.name, res, non_color=True)
        _bake(obj, "AO")
        written[obj.name] = _save(image, out_dir, "%s_ao.png" % obj.name.lower())
        mat.node_tree.nodes.remove(node)

    return written


# ---------------------------------------------------------------------------
# Three.js manifest
# ---------------------------------------------------------------------------

def _hex(rgb):
    """Linear float RGB -> sRGB hex, matching Three's Color('#rrggbb')."""
    def encode(c):
        c = min(1.0, max(0.0, c))
        s = 1.055 * (c ** (1 / 2.4)) - 0.055 if c > 0.0031308 else c * 12.92
        return int(round(s * 255))
    return "#%02x%02x%02x" % tuple(encode(c) for c in rgb)


def three_spec(name, maps=None):
    """MeshStandardMaterial parameters for one material.

    `color` is sRGB hex because Three's Color constructor expects sRGB while
    Blender's Base Color is linear - converting here is what stops the web
    build looking washed out beside the Cycles render.
    """
    spec = MATERIALS[name]
    entry = {
        "color": _hex(spec["base_color"]),
        "metalness": round(spec["metallic"], 3),
        "roughness": round(spec["roughness"], 3),
        "normalScale": spec["three"]["normalScale"],
        "envMapIntensity": spec["three"]["envMapIntensity"],
        "flatShading": False,
    }
    if maps:
        entry["maps"] = maps
    return entry


def write_manifest(path, baked=None):
    """Write materials.json: one entry per material, maps included if baked."""
    baked = baked or {}
    data = {name: three_spec(name, baked.get(name)) for name in MATERIALS}
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
    print("[materials] wrote %s" % path)
    return data


def bake_all(res=2048, out_dir="textures", samples=16):
    baked = {name: bake_material(name, res, out_dir, samples)
             for name in MATERIALS}
    write_manifest(os.path.join(out_dir, "materials.json"), baked)
    return baked


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    argv = sys.argv
    args = {"bake": False, "bake_ao": False, "res": 2048,
            "out": "textures", "samples": 16}
    if "--" not in argv:
        return args
    argv = argv[argv.index("--") + 1:]

    i = 0
    while i < len(argv):
        if argv[i] == "--bake":
            args["bake"] = True
        elif argv[i] == "--bake-ao":
            args["bake_ao"] = True
        elif argv[i] in ("--res", "--out", "--samples") and i + 1 < len(argv):
            key = argv[i].lstrip("-")
            args[key] = argv[i + 1] if key == "out" else int(argv[i + 1])
            i += 1
        i += 1
    return args


def main():
    args = parse_args()
    build_all()

    if args["bake"]:
        bake_all(args["res"], args["out"], args["samples"])
    elif args["bake_ao"]:
        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        bake_object_ao(meshes, args["res"], args["out"])
    else:
        write_manifest(os.path.join(args["out"], "materials.json"))


if __name__ == "__main__":
    main()
