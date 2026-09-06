// js/diagram3d.js
//
// Three.js view of the reinforced-concrete corbel. Geometry comes entirely
// from js/dimensions.js -- the same tables js/diagram2d.js draws -- so the
// two views cannot depict different objects, and both track the form inputs.
//
// Blender is Z-up and three.js is Y-up. The shared tables are authored in
// the three.js convention (X = width, Y = height, Z = depth), so no axis
// swap happens here; the swap was done once when the corbel was transcribed
// out of Blender and into dimensions.js.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import {
  dimensionRecords,
  elevationShapes,
  rebarProfile,
  rebarDepths,
  rebarRadius,
  LABEL_MIN_CONTAINER_WIDTH
} from './dimensions.js';

// Blender light rig, converted to Y-up: Key (-1.30, 0.60, 1.70) Z-up,
// Fill (1.21, -0.44, 0.82), Rim (0.15, 1.21, 1.06). Blender watt values do
// not transfer to three.js intensities; the RATIOS between the three lights
// are what was preserved, then scaled to a sane exposure.
const KEY_POS = new THREE.Vector3(-1.30, 1.70, 0.60);
const FILL_POS = new THREE.Vector3(1.21, 0.82, -0.44);
const RIM_POS = new THREE.Vector3(0.15, 1.06, 1.21);
// Blender camera at (-1.03, -1.03, 1.12), Z-up.
const CAMERA_DIR = new THREE.Vector3(-1.03, 1.12, -1.03);

// Camera fit padding. Labels sit OUTSIDE the geometry's bounding box and
// are DOM elements with their own pixel footprint, so they need angular
// margin; with labels hidden there is nothing outside the box to leave room
// for and the fit can tighten so the model fills the panel.
const FIT_PADDING = 1.15;
const FIT_PADDING_NO_LABELS = 1.02;

// Procedural textures, generated on a canvas. Everything here is built in
// code rather than fetched: this is a no-build static site with no asset
// pipeline, and a failed texture request would fail silently.
// The raw noise FIELD, separate from any texture built out of it. Colour,
// roughness and bump all have to come from the same field: if the colour
// blotches and the bump dimples are two different random fields, the eye
// reads two overlaid patterns instead of one surface.
function makeNoiseField(size, contrast, octaves = 3, baseLattice = 4) {
  const out = new Float32Array(size * size);
  // Value noise. Per-pixel random reads as television static; the octaves
  // give the grain a size. `baseLattice` sets the COARSEST feature, so it
  // is what decides whether the result reads as fine grain or as blotches.
  const lattice = [];
  for (let o = 0; o < octaves; o++) {
    const n = baseLattice << o;
    const grid = new Float32Array(n * n);
    for (let i = 0; i < grid.length; i++) grid[i] = Math.random();
    lattice.push({ n, grid });
  }
  const sample = (layer, x, y) => {
    const { n, grid } = layer;
    const fx = x * n;
    const fy = y * n;
    const x0 = Math.floor(fx) % n;
    const y0 = Math.floor(fy) % n;
    const x1 = (x0 + 1) % n;
    const y1 = (y0 + 1) % n;
    const tx = fx - Math.floor(fx);
    const ty = fy - Math.floor(fy);
    const sx = tx * tx * (3 - 2 * tx);
    const sy = ty * ty * (3 - 2 * ty);
    const a = grid[y0 * n + x0];
    const b = grid[y0 * n + x1];
    const cc = grid[y1 * n + x0];
    const d = grid[y1 * n + x1];
    return (a * (1 - sx) + b * sx) * (1 - sy) + (cc * (1 - sx) + d * sx) * sy;
  };
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const u = x / size;
      const v = y / size;
      let n = 0;
      let amp = 1;
      let total = 0;
      for (let o = 0; o < octaves; o++) {
        n += sample(lattice[o], u, v) * amp;
        total += amp;
        amp *= 0.5;
      }
      n = 0.5 + (n / total - 0.5) * contrast;
      out[y * size + x] = Math.max(0, Math.min(1, n));
    }
  }
  return out;
}

// Paint a field into a texture. `paint(n, i)` returns [r, g, b] in 0..255;
// `i` is the pixel index, so a paint function can read a second field at the
// same pixel -- concrete needs a coarse mottle and a fine grain at once, and
// blending them in the painter keeps them registered to the same surface.
// `srgb` must be true for a colour map and false for data maps (roughness,
// bump): tagging a data map as sRGB puts it through the transfer function
// and silently changes the values the shader reads.
function textureFromField(field, size, paint, srgb) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const ctx = c.getContext('2d');
  const img = ctx.createImageData(size, size);
  for (let i = 0; i < field.length; i++) {
    const [r, g, b] = paint(field[i], i);
    const j = i * 4;
    img.data[j] = r;
    img.data[j + 1] = g;
    img.data[j + 2] = b;
    img.data[j + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  if (srgb) tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function makeNoiseTexture(size, contrast) {
  const field = makeNoiseField(size, contrast);
  const grey = (n) => {
    const g = Math.round(n * 255);
    return [g, g, g];
  };
  return textureFromField(field, size, grey, false);
}

// Deformed-bar ribs. TubeGeometry lays u along the bar's length and v around
// its circumference, so a stripe repeating in u becomes transverse ribs --
// the one feature that separates rebar from a smooth rod.
function makeRibTexture() {
  const w = 256;
  const h = 8;
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  const ctx = c.getContext('2d');
  const img = ctx.createImageData(w, h);
  for (let x = 0; x < w; x++) {
    // Sharpened sine: a flat bar surface with raised ribs, not a wave.
    const s = Math.sin((x / w) * Math.PI * 2 * 8);
    const v = Math.pow(Math.max(0, s), 0.6);
    const g = Math.round(60 + v * 195);
    for (let y = 0; y < h; y++) {
      const i = (y * w + x) * 4;
      img.data[i] = img.data[i + 1] = img.data[i + 2] = g;
      img.data[i + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(90, 1);
  return tex;
}

// A CatmullRom curve through only the profile's corner points bulges badly
// along what should be dead-straight runs. Sampling extra points along each
// straight segment pins the curve to the line and leaves it free to round
// only at the corners -- which is what a real bent bar does anyway.
function densify(points, perSegment) {
  const out = [];
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i];
    const b = points[i + 1];
    for (let s = 0; s < perSegment; s++) {
      const t = s / perSegment;
      out.push({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t });
    }
  }
  out.push(points[points.length - 1]);
  return out;
}

export function mountDiagram3D(container) {
  // WebGPURenderer, not WebGLRenderer -- and note the WebGPU build does not
  // export WebGLRenderer at all, so this class IS the fallback story: its
  // constructor installs a getFallback() that swaps in a WebGL2 backend if
  // the adapter request fails. One renderer class, one code path, and the
  // page still runs everywhere WebGL2 runs.
  const renderer = new THREE.WebGPURenderer({ antialias: true });
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  // Blender renders this scene through AgX at a fairly dark key. Matching
  // that needs exposure well under 1: at 1.0+ the concrete blows out to
  // paper-white and the dark backdrop washes to light grey.
  renderer.toneMappingExposure = 0.78;
  renderer.shadowMap.enabled = true;
  // PCFShadowMap, NOT PCFSoftShadowMap: `light.shadow.radius` is only
  // honoured by PCFShadowMap. Under PCFSoft it is ignored outright and the
  // shadow comes out hard-edged, reading as a second grey object. This
  // still holds on the WebGPU backend: shadowMap.type indexes a filter
  // library, and only the PCF entry reads shadow.radius (as a 17-tap
  // kernel scale). The constant values are unchanged.
  renderer.shadowMap.type = THREE.PCFShadowMap;
  const canvas = renderer.domElement;
  container.appendChild(canvas);

  const labelRenderer = new CSS2DRenderer();
  labelRenderer.domElement.style.position = 'absolute';
  labelRenderer.domElement.style.top = '0';
  labelRenderer.domElement.style.left = '0';
  labelRenderer.domElement.style.pointerEvents = 'none';
  const overlay = labelRenderer.domElement;
  container.appendChild(overlay);
  container.style.position = 'relative';

  const scene = new THREE.Scene();
  // Blender world background: (0.05, 0.06, 0.08) at strength 0.6.
  scene.background = new THREE.Color(0x23282f);

  const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 100);
  camera.position.copy(CAMERA_DIR);

  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  // The ground is single-sided from above; orbiting under it puts the
  // viewer beneath the floor, which hides the model and destroys the sense
  // that it is standing on something.
  controls.maxPolarAngle = Math.PI / 2 - 0.02;

  // RoomEnvironment is a bright white interior. At full strength it acts as
  // a large ambient fill and flattens the directional key the Blender rig
  // depends on, so it is dialled back to a reflection source, not a light.
  scene.environmentIntensity = 0.3;

  // The backend is initialised ASYNCHRONOUSLY -- it has to request a GPU
  // adapter, and may fall back to WebGL2 partway through. Two consequences:
  //
  //  1. PMREMGenerator renders into a target, so it cannot run until the
  //     backend exists. Environment setup lives inside the init callback.
  //  2. renderer.render() before init logs a warning and silently defers to
  //     renderAsync(), so the animation loop is gated on `ready` rather
  //     than being left to spam the console on every frame until init lands.
  let ready = false;
  renderer
    .init()
    .then(() => {
      const pmrem = new THREE.PMREMGenerator(renderer);
      scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
      pmrem.dispose();
      ready = true;
    })
    .catch((err) => {
      // Neither a WebGPU adapter nor a WebGL2 context. Nothing can be drawn,
      // so say why in the console rather than leaving a silent black panel.
      console.error('3D view unavailable: renderer failed to initialise.', err);
    });

  // --- materials ---------------------------------------------------------
  // Built ONCE at mount, never inside buildScene(). Each of these owns a
  // procedurally generated canvas texture, and regenerating three noise
  // fields on every keystroke would turn a param edit into a visible stall.
  // The corollary is that disposeGroup() below must dispose geometries only
  // -- disposing a shared material on the first rebuild would leave every
  // later frame drawing against a dead material.
  // Concrete is near-uniform in VALUE with structure at two very different
  // scales: a broad, low-amplitude mottle from the pour, and a fine grain of
  // aggregate and sand. A single mid-frequency field gives neither -- it
  // reads as camouflage blotching. So: two fields, both driving colour,
  // roughness and bump together so the eye reads one surface.
  const CONCRETE_SIZE = 512;
  // Coarse: lattice 3, 2 octaves. At repeat 2 over a ~0.3 m face this is a
  // ~5 cm patch -- pour variation, not a pattern.
  const mottle = makeNoiseField(CONCRETE_SIZE, 1.0, 2, 3);
  // Fine: lattice 32 up to 128. The top octave is 4 px per cell at 512, just
  // above where bilinear value noise starts to alias.
  const grain = makeNoiseField(CONCRETE_SIZE, 1.0, 3, 32);
  const base = new THREE.Color(0xdad7d0);
  // Air voids. Real cast faces are pocked with sparse blowholes, and they are
  // the detail that most reads as "concrete" rather than "grey plastic".
  // Thresholding the fine field puts them at its minima -- sparse, irregular,
  // and already registered to the grain.
  const VOID_T = 0.3;
  const voidAt = (i) => {
    const g = grain[i];
    return g < VOID_T ? Math.min(1, (VOID_T - g) / VOID_T) : 0;
  };
  const concreteColor = textureFromField(
    grain,
    CONCRETE_SIZE,
    (g, i) => {
      // Cast concrete varies in value, not hue: pour lines, aggregate and
      // damp patches all read as lighter or darker grey. +-8% total, an
      // order below the previous +-21% -- at that amplitude it was reading
      // as pattern rather than as material.
      let k = 1 + (mottle[i] - 0.5) * 0.09 + (g - 0.5) * 0.07;
      k *= 1 - voidAt(i) * 0.55;
      return [
        Math.max(0, Math.min(255, Math.round(base.r * 255 * k))),
        Math.max(0, Math.min(255, Math.round(base.g * 255 * k))),
        Math.max(0, Math.min(255, Math.round(base.b * 255 * k)))
      ];
    },
    true
  );
  // Height: grain dominates, mottle only tilts it, voids cut in hard. Dark
  // is low, so subtracting the void term recesses the pinholes.
  const concreteBump = textureFromField(
    grain,
    CONCRETE_SIZE,
    (g, i) => {
      const h = Math.max(0, g * 0.8 + mottle[i] * 0.2 - voidAt(i) * 0.9);
      const v = Math.round(h * 255);
      return [v, v, v];
    },
    false
  );
  // Roughness: mostly flat and high, nudged by the grain, with the voids
  // fully rough. Wide roughness swings read as wet patches, not texture.
  const concreteRough = textureFromField(
    grain,
    CONCRETE_SIZE,
    (g, i) => {
      const r = Math.min(1, 0.88 + (g - 0.5) * 0.1 + voidAt(i) * 0.12);
      const v = Math.round(r * 255);
      return [v, v, v];
    },
    false
  );
  for (const t of [concreteColor, concreteBump, concreteRough]) t.repeat.set(2, 2);
  const concreteMat = new THREE.MeshStandardMaterial({
    // `map` carries the tint, so `color` stays white -- leaving it at
    // 0xdad7d0 would multiply the tint in twice and darken the surface.
    color: 0xffffff,
    roughness: 1.0,
    metalness: 0.0,
    map: concreteColor,
    roughnessMap: concreteRough,
    // Fine grain needs a SMALL bumpScale. 0.04 on millimetre-scale detail
    // perturbs the normal far past what the height implies and the surface
    // starts to sparkle under the key light.
    bumpMap: concreteBump,
    bumpScale: 0.012
  });

  const ribTex = makeRibTexture();
  const rustNoise = makeNoiseTexture(128, 0.7);
  rustNoise.repeat.set(6, 2);
  const rebarMat = new THREE.MeshStandardMaterial({
    // Oxidised steel is DARK and desaturated toward red-brown. A light,
    // saturated orange reads as varnished pine.
    color: 0x4a2317,
    roughness: 0.88,
    // Rust is an oxide, not a metal. Any metalness here puts a sheen on it
    // that reads as polished bronze.
    metalness: 0.0,
    roughnessMap: rustNoise,
    bumpMap: ribTex,
    bumpScale: 0.004
  });

  // Blender's BackdropMat base colour is a dark (0.12, 0.13, 0.15), but it
  // is lit by three area lights a metre away and renders as mid grey-blue.
  // three.js drives this with DIRECTIONAL lights, which do not fall off
  // with distance and deliver far less energy to a large floor at grazing
  // incidence. Compensating in the albedo matches the rendered result
  // rather than the source number.
  const groundMat = new THREE.MeshStandardMaterial({
    color: 0x545b64,
    roughness: 0.9,
    metalness: 0.0
  });

  const lineMat = new THREE.LineDashedMaterial({
    color: 0xe0a878,
    dashSize: 0.02,
    gapSize: 0.01
  });
  const extMat = new THREE.LineBasicMaterial({ color: 0x8b939d });

  // --- static scene furniture --------------------------------------------
  // The ground is seated at y = 0 so the corbel's underside rests on it.
  // That contact is what produces a contact shadow; in the original Blender
  // scene the plane sat 5cm low and the whole assembly floated, which is
  // exactly why it had no shadow at all. 6x6 rather than infinite, matching
  // Blender's backdrop: the finite edge is what gives the horizon line.
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(6, 6), groundMat);
  ground.rotation.x = -Math.PI / 2;
  ground.position.set(0.15, 0, 0.15);
  ground.receiveShadow = true;
  scene.add(ground);

  scene.add(new THREE.HemisphereLight(0x8899aa, 0x1a1d22, 0.25));

  const key = new THREE.DirectionalLight(0xfff4e8, 2.6);
  key.position.copy(KEY_POS);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  // Softens the shadow edge. Only honoured under PCFShadowMap (see above).
  key.shadow.radius = 5;
  key.shadow.bias = -0.0012;
  scene.add(key);
  scene.add(key.target);

  const fill = new THREE.DirectionalLight(0xdfe8f5, 0.45);
  fill.position.copy(FILL_POS);
  scene.add(fill);

  const rim = new THREE.DirectionalLight(0xffffff, 0.7);
  rim.position.copy(RIM_POS);
  scene.add(rim);

  // --- dynamic geometry --------------------------------------------------
  let dynamicGroup = new THREE.Group();
  scene.add(dynamicGroup);
  let currentBox = new THREE.Box3();
  let labelsVisible = true;

  // Disposes GEOMETRY only, and detaches CSS2D label DOM nodes. Materials
  // are mount-scoped and shared across rebuilds (see above), so they must
  // not be touched here. CSS2DRenderer appends elements but never removes
  // them, so a CSS2DObject's node leaks into the overlay on every rebuild
  // unless it is detached explicitly.
  function disposeGroup(group) {
    group.traverse((obj) => {
      if (obj.geometry) obj.geometry.dispose();
      if (obj.isCSS2DObject && obj.element && obj.element.parentNode) {
        obj.element.parentNode.removeChild(obj.element);
      }
    });
  }

  function computeFit(box) {
    if (box.isEmpty()) return null;
    const sphere = new THREE.Sphere();
    box.getBoundingSphere(sphere);
    if (!(sphere.radius > 0)) return null;
    const vHalf = THREE.MathUtils.degToRad(camera.fov) / 2;
    const hHalf = Math.atan(Math.tan(vHalf) * camera.aspect);
    // Fit the bounding SPHERE, not the box: the sphere's silhouette is the
    // same from every angle, so the fit stays correct wherever the user has
    // orbited to, without needing to know the view direction.
    const limiting = Math.min(vHalf, hHalf);
    const padding = labelsVisible ? FIT_PADDING : FIT_PADDING_NO_LABELS;
    return { distance: (sphere.radius / Math.sin(limiting)) * padding, sphere };
  }

  // Re-fits while PRESERVING the user's current orbit direction. Snapping
  // back to a default angle every time a param changed would fight a manual
  // drag and feel broken, so only the distance and target move.
  function fitCameraToBox(box) {
    const fit = computeFit(box);
    if (!fit) return;
    const dir = new THREE.Vector3().subVectors(camera.position, controls.target);
    if (!(dir.lengthSq() > 1e-8)) dir.copy(CAMERA_DIR);
    dir.normalize();
    controls.target.copy(fit.sphere.center);
    camera.position.copy(fit.sphere.center).addScaledVector(dir, fit.distance);
    camera.near = Math.max(0.01, fit.distance / 100);
    camera.far = Math.max(100, fit.distance * 10);
    camera.updateProjectionMatrix();

    // Size the shadow camera to the model that actually exists. A, H1, H2
    // and the rest are user inputs with a wide declared range, so a fixed
    // orthographic extent would clip the shadow once the params moved off
    // their defaults.
    const r = Math.max(fit.sphere.radius, 0.01) * 1.8;
    const c = key.shadow.camera;
    c.left = -r;
    c.right = r;
    c.top = r;
    c.bottom = -r;
    c.near = 0.01;
    c.far = r * 10;
    c.updateProjectionMatrix();
    key.target.position.copy(fit.sphere.center);
    key.target.updateMatrixWorld();
    key.position.copy(fit.sphere.center).addScaledVector(
      KEY_POS.clone().normalize(),
      r * 3
    );

    controls.update();
  }

  function buildScene(params) {
    disposeGroup(dynamicGroup);
    scene.remove(dynamicGroup);
    dynamicGroup = new THREE.Group();

    // Concrete masses, extruded from the shared elevation table.
    for (const s of elevationShapes(params)) {
      if (!(s.w > 0) || !(s.h > 0) || !(s.depth > 0)) continue;
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(s.w, s.h, s.depth),
        concreteMat
      );
      mesh.position.set(s.x + s.w / 2, s.y + s.h / 2, s.depth / 2);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      dynamicGroup.add(mesh);
    }

    // Reinforcement: one shared profile swept at each bar depth.
    const radius = rebarRadius(params);
    const profile = densify(rebarProfile(params), 8);
    if (radius > 0 && profile.length > 1) {
      for (const depth of rebarDepths(params)) {
        const pts = profile.map((pt) => new THREE.Vector3(pt.x, pt.y, depth));
        // Centripetal parameterisation: the densified profile clusters
        // points at the bends, and the default curve type overshoots there.
        const curve = new THREE.CatmullRomCurve3(pts, false, 'centripetal', 0.5);
        const bar = new THREE.Mesh(
          new THREE.TubeGeometry(curve, Math.max(64, profile.length * 4), radius, 16, false),
          rebarMat
        );
        bar.castShadow = true;
        bar.receiveShadow = true;
        dynamicGroup.add(bar);
      }
    }

    // Dimension annotations, from the same records the 2D view draws.
    dimensionRecords.forEach((rec) => {
      const from = rec.from(params);
      const to = rec.to(params);
      // The witness line is offset along offsetDir so it sits BESIDE the
      // object. Without this every vertical record collapses onto the same
      // axis and the dashed line runs through the model. Records that share
      // a crowded corner carry their own offsetScale to fan out (see
      // dimensions.js) -- the 2D view applies the same factor, so the two
      // views fan out identically.
      const OFF = 0.09 * (rec.offsetScale ?? 1);
      const off = new THREE.Vector3(
        rec.offsetDir.x * OFF,
        rec.offsetDir.y * OFF,
        rec.offsetDir.z * OFF
      );
      const a = new THREE.Vector3(from.x, from.y, from.z).add(off);
      const b = new THREE.Vector3(to.x, to.y, to.z).add(off);
      const line = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([a, b]),
        lineMat
      );
      line.computeLineDistances();
      dynamicGroup.add(line);

      for (const [p, q] of [[from, a], [to, b]]) {
        dynamicGroup.add(
          new THREE.Line(
            new THREE.BufferGeometry().setFromPoints([
              new THREE.Vector3(p.x, p.y, p.z),
              q.clone().add(off.clone().multiplyScalar(0.25))
            ]),
            extMat
          )
        );
      }

      const div = document.createElement('div');
      div.textContent = rec.label(params);
      div.style.fontSize = '11px';
      // Light on dark: the 3D scene sits on a dark studio backdrop, so the
      // 2D view's dark-on-white chip would be unreadable here.
      div.style.color = '#f2f5f8';
      div.style.background = 'rgba(20,24,29,0.72)';
      div.style.padding = '1px 4px';
      div.style.borderRadius = '3px';
      div.style.whiteSpace = 'nowrap';
      const labelObj = new CSS2DObject(div);
      labelObj.position.set(
        (a.x + b.x) / 2 + rec.offsetDir.x * 0.04,
        (a.y + b.y) / 2 + rec.offsetDir.y * 0.04,
        (a.z + b.z) / 2 + rec.offsetDir.z * 0.04
      );
      dynamicGroup.add(labelObj);
    });

    scene.add(dynamicGroup);
    // CSS2DObjects have no geometry and are skipped by Box3.setFromObject;
    // the labels' own offset is covered by FIT_PADDING rather than by
    // growing the box.
    currentBox = new THREE.Box3().setFromObject(dynamicGroup);
    fitCameraToBox(currentBox);
  }

  function resize() {
    // Size from the canvas's CURRENT parent, not the container captured in
    // this closure: modal.js re-parents the canvas, and the original
    // container is a different size (or empty) once that has happened.
    const sizingEl = canvas.parentElement || container;
    const w = sizingEl.clientWidth || 1;
    const h = sizingEl.clientHeight || 1;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(w, h);
    labelRenderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    // `visibility`, not `display`: app.js owns the overlay's `display` for
    // the 2D/3D toggle, and two writers on one property would fight.
    labelsVisible = w >= LABEL_MIN_CONTAINER_WIDTH;
    overlay.style.visibility = labelsVisible ? 'visible' : 'hidden';
    fitCameraToBox(currentBox);
  }

  function render(params) {
    buildScene(params);
  }

  // 2D is the default view, so without this guard the 3D renderer would
  // keep issuing draw calls from page load onward for a viewer who never
  // opens the 3D view. The rAF loop keeps ticking so OrbitControls damping
  // resumes cleanly, but it does no GPU work while the canvas is hidden.
  function isVisible() {
    return canvas.style.display !== 'none' && canvas.isConnected;
  }

  function animate() {
    requestAnimationFrame(animate);
    if (!isVisible()) return;
    controls.update();
    // Gated, not skipped wholesale: OrbitControls damping keeps integrating
    // while the backend comes up, so the first drawn frame matches wherever
    // the user has already dragged to.
    if (!ready) return;
    renderer.render(scene, camera);
    labelRenderer.render(scene, camera);
  }

  window.addEventListener('resize', resize);
  resize();
  animate();

  return { render, canvas, overlay, resize };
}
