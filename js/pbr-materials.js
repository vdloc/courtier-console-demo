// Three.js side of the PBR material set defined in blender/materials.py.
//
// The scalar values below are transcribed from that file's MATERIALS table,
// converted from Blender's linear Base Color to the sRGB hex that Three's
// Color constructor expects. They are duplicated here rather than fetched so
// the viewer renders correctly with no network round-trip and no build step,
// matching how the rest of this repo works. `loadManifest()` overrides them
// from textures/materials.json when a bake exists, so the bake stays the
// source of truth without becoming a hard dependency.
//
// Baked maps are optional throughout. With no textures present every material
// still resolves to correct scalars, just without surface detail -- the right
// failure mode for a demo that has to open from a bare static directory.

import * as THREE from 'three';

// Values mirror blender/materials.py MATERIALS. `color` is sRGB.
export const MATERIAL_SPECS = {
  MAT_Steel_Painted: {
    color: '#8b8f96',
    metalness: 0.92,
    roughness: 0.38,
    normalScale: 0.6,
    envMapIntensity: 1.15,
    // The bake is one texture per metre of surface, so `repeat` is just the
    // surface size in metres. A 7.2 m beam gets 7.2 tiles and never looks
    // like a stretched decal beside a 0.4 m column.
    texelsPerMetre: 1.0,
    maps: {
      map: 'steel_painted_basecolor.png',
      roughnessMap: 'steel_painted_roughness.png',
      normalMap: 'steel_painted_normal.png',
    },
  },
  MAT_Steel_Bolt: {
    color: '#5e6167',
    metalness: 1.0,
    roughness: 0.3,
    normalScale: 0.45,
    envMapIntensity: 1.35,
    texelsPerMetre: 6.0,
    maps: {
      map: 'steel_bolt_basecolor.png',
      roughnessMap: 'steel_bolt_roughness.png',
      normalMap: 'steel_bolt_normal.png',
    },
  },
  MAT_Steel_Galvanised: {
    color: '#c8ccd0',
    metalness: 0.95,
    roughness: 0.34,
    normalScale: 0.5,
    envMapIntensity: 1.25,
    texelsPerMetre: 2.0,
    maps: {
      map: 'steel_galvanised_basecolor.png',
      roughnessMap: 'steel_galvanised_roughness.png',
      normalMap: 'steel_galvanised_normal.png',
    },
  },
  MAT_Weld_Bead: {
    color: '#837c76',
    metalness: 0.85,
    roughness: 0.62,
    normalScale: 1.0,
    envMapIntensity: 0.9,
    texelsPerMetre: 12.0,
    maps: {
      map: 'weld_bead_basecolor.png',
      roughnessMap: 'weld_bead_roughness.png',
      normalMap: 'weld_bead_normal.png',
    },
  },
  MAT_Rail_Safety: {
    color: '#f0cf46',
    metalness: 0.3,
    roughness: 0.52,
    normalScale: 0.7,
    envMapIntensity: 1.0,
    texelsPerMetre: 2.0,
    maps: {
      map: 'rail_safety_basecolor.png',
      roughnessMap: 'rail_safety_roughness.png',
      normalMap: 'rail_safety_normal.png',
    },
  },
  MAT_Pipe_CHW: {
    color: '#659bcd',
    metalness: 0.7,
    roughness: 0.36,
    normalScale: 0.5,
    envMapIntensity: 1.1,
    texelsPerMetre: 3.0,
    maps: {
      map: 'pipe_chw_basecolor.png',
      roughnessMap: 'pipe_chw_roughness.png',
      normalMap: 'pipe_chw_normal.png',
    },
  },
  MAT_Pipe_LTHW: {
    color: '#cd6973',
    metalness: 0.7,
    roughness: 0.36,
    normalScale: 0.5,
    envMapIntensity: 1.1,
    texelsPerMetre: 3.0,
    maps: {
      map: 'pipe_lthw_basecolor.png',
      roughnessMap: 'pipe_lthw_roughness.png',
      normalMap: 'pipe_lthw_normal.png',
    },
  },
  MAT_Concrete: {
    color: '#b8b7b3',
    metalness: 0.0,
    roughness: 0.88,
    normalScale: 1.0,
    envMapIntensity: 0.85,
    texelsPerMetre: 1.0,
    // Dust is applied in the shader, not baked -- see applyDustLayer.
    dust: { color: '#cfc9bd', amount: 0.55, fromY: 0.35, toY: 0.95 },
    maps: {
      map: 'concrete_basecolor.png',
      roughnessMap: 'concrete_roughness.png',
      normalMap: 'concrete_normal.png',
      // A displacement map is baked too, but MeshStandardMaterial
      // displacement needs dense geometry to show anything. Left out on
      // purpose: the normal map carries the same relief far more cheaply.
    },
  },
};

// Texture keys that carry colour and therefore need the sRGB transfer
// function. Everything else is data and must stay linear -- tagging a
// roughness map as sRGB silently changes the values the shader reads.
const COLOR_MAPS = new Set(['map', 'emissiveMap']);

/**
 * Load one texture with the right colour space, wrapping and filtering.
 * Resolves to null rather than throwing when a file is missing, so a partial
 * bake degrades to scalars instead of a blank screen.
 */
function loadTexture(loader, url, key, anisotropy) {
  return new Promise((resolve) => {
    loader.load(
      url,
      (texture) => {
        texture.colorSpace = COLOR_MAPS.has(key)
          ? THREE.SRGBColorSpace
          : THREE.NoColorSpace;
        texture.wrapS = THREE.RepeatWrapping;
        texture.wrapT = THREE.RepeatWrapping;
        texture.anisotropy = anisotropy;
        resolve(texture);
      },
      undefined,
      () => resolve(null),
    );
  });
}

/**
 * Build every MeshStandardMaterial in the set.
 *
 * @param {object} options
 * @param {string} [options.texturePath]  Directory holding the baked PNGs.
 *   Omit for scalar-only materials.
 * @param {number} [options.anisotropy]   From renderer.capabilities.
 * @param {THREE.Texture} [options.envMap] IBL environment, applied to all.
 * @returns {Promise<Record<string, THREE.MeshStandardMaterial>>}
 */
export async function createMaterials(options = {}) {
  const { texturePath = null, anisotropy = 4, envMap = null } = options;
  const loader = texturePath ? new THREE.TextureLoader() : null;
  const out = {};

  for (const [name, spec] of Object.entries(MATERIAL_SPECS)) {
    const material = new THREE.MeshStandardMaterial({
      name,
      color: new THREE.Color(spec.color),
      metalness: spec.metalness,
      roughness: spec.roughness,
      envMapIntensity: spec.envMapIntensity,
      flatShading: false,
    });

    if (envMap) material.envMap = envMap;

    if (loader && spec.maps) {
      const entries = Object.entries(spec.maps);
      const textures = await Promise.all(
        entries.map(([key, file]) =>
          loadTexture(loader, `${texturePath}/${file}`, key, anisotropy)),
      );
      entries.forEach(([key], i) => {
        if (textures[i]) material[key] = textures[i];
      });

      if (material.normalMap) {
        material.normalScale = new THREE.Vector2(
          spec.normalScale, spec.normalScale,
        );
      }
      // A roughness map multiplies the scalar, so leaving roughness at the
      // authored value would apply it twice. The bake already encodes the
      // full value.
      if (material.roughnessMap) material.roughness = 1.0;
      material.needsUpdate = true;
    }

    if (spec.dust) applyDustLayer(material, spec.dust);
    out[name] = material;
  }

  return out;
}

/**
 * Reproduce the Blender dust layer, which is driven by the world normal and
 * therefore cannot be baked into a flat texture: only upward-facing surfaces
 * collect dust. It is the cheapest single thing that makes concrete read as
 * cast in place rather than as a grey box.
 *
 * Injected via onBeforeCompile so it rides on the standard material and keeps
 * shadows, IBL and tone mapping intact.
 */
export function applyDustLayer(material, dust) {
  const dustColor = new THREE.Color(dust.color);

  material.onBeforeCompile = (shader) => {
    shader.uniforms.uDustColor = { value: dustColor };
    shader.uniforms.uDustAmount = { value: dust.amount };
    shader.uniforms.uDustRange = {
      value: new THREE.Vector2(dust.fromY, dust.toY),
    };

    shader.fragmentShader = shader.fragmentShader
      .replace(
        '#include <common>',
        `#include <common>
        uniform vec3 uDustColor;
        uniform float uDustAmount;
        uniform vec2 uDustRange;`,
      )
      .replace(
        '#include <roughnessmap_fragment>',
        `#include <roughnessmap_fragment>
        // The normal here is view space; rotating it back to world space is
        // what keeps the dust on the up-faces as the camera orbits, rather
        // than having it swim across the surface.
        vec3 dustWorldNormal = normalize(
          mat3(viewMatrix[0].xyz, viewMatrix[1].xyz, viewMatrix[2].xyz)
          * normal);
        float dustMask =
          smoothstep(uDustRange.x, uDustRange.y, dustWorldNormal.y)
          * uDustAmount;
        diffuseColor.rgb = mix(diffuseColor.rgb, uDustColor, dustMask);
        roughnessFactor = mix(roughnessFactor, 1.0, dustMask);`,
      );
  };

  // Two materials compiling different shaders must not share a cache key.
  material.customProgramCacheKey = () => `dust-${dust.amount}-${dust.color}`;
}

/**
 * Scale a material's texture repeat to a mesh's real size, so texel density
 * stays constant across a 0.4 m column and a 7.2 m beam.
 *
 * Returns a clone, which costs an extra draw-call group -- use it only where
 * the size difference is actually visible.
 */
export function fitTextureScale(mesh, material, spec) {
  if (!material.map || !spec) return material;

  mesh.geometry.computeBoundingBox();
  const size = new THREE.Vector3();
  mesh.geometry.boundingBox.getSize(size);

  const clone = material.clone();
  const density = spec.texelsPerMetre ?? 1.0;
  const repeatX = Math.max(1, size.x * density);
  const repeatY = Math.max(1, Math.max(size.y, size.z) * density);

  for (const key of ['map', 'roughnessMap', 'normalMap']) {
    if (!clone[key]) continue;
    clone[key] = clone[key].clone();
    clone[key].repeat.set(repeatX, repeatY);
    clone[key].needsUpdate = true;
  }
  return clone;
}

/**
 * Swap the materials in a loaded GLB for this set.
 *
 * The Blender export writes each material's name into the glTF, so matching
 * on `material.name` is enough. Meshes whose material has no counterpart here
 * keep whatever the GLB carried.
 */
export function applyMaterials(root, materials, { fitScale = false } = {}) {
  root.traverse((node) => {
    if (!node.isMesh || !node.material) return;

    const current = Array.isArray(node.material) ? node.material : [node.material];
    const swapped = current.map((mat) => {
      const replacement = materials[mat.name];
      if (!replacement) return mat;
      return fitScale
        ? fitTextureScale(node, replacement, MATERIAL_SPECS[mat.name])
        : replacement;
    });

    node.material = swapped.length === 1 ? swapped[0] : swapped;
    node.castShadow = true;
    node.receiveShadow = true;
  });
}

/**
 * Override the built-in scalars from a bake manifest, when one is served.
 * Keeps the built-ins if the file is absent, so the demo still runs from a
 * bare static directory.
 */
export async function loadManifest(url) {
  try {
    const response = await fetch(url);
    if (!response.ok) return MATERIAL_SPECS;

    const manifest = await response.json();
    for (const [name, entry] of Object.entries(manifest)) {
      if (!MATERIAL_SPECS[name]) continue;
      Object.assign(MATERIAL_SPECS[name], {
        color: entry.color,
        metalness: entry.metalness,
        roughness: entry.roughness,
        normalScale: entry.normalScale,
        envMapIntensity: entry.envMapIntensity,
      });
      if (entry.maps) MATERIAL_SPECS[name].maps = entry.maps;
    }
  } catch {
    // Offline, or opened over file:// -- built-in scalars stand.
  }
  return MATERIAL_SPECS;
}
