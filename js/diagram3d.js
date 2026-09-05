// js/diagram3d.js
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';
import { dimensionRecords, visualScale } from './dimensions.js';

export function mountDiagram3D(container) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
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
  const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 100);
  camera.position.set(1.2, 1.0, 1.5);

  const controls = new OrbitControls(camera, canvas);
  controls.target.set(0, 0.4, 0);
  controls.enableDamping = true;

  scene.add(new THREE.AmbientLight(0xffffff, 0.7));
  const dirLight = new THREE.DirectionalLight(0xffffff, 0.6);
  dirLight.position.set(2, 3, 2);
  scene.add(dirLight);

  let dynamicGroup = new THREE.Group();
  scene.add(dynamicGroup);

  function resize() {
    // Size from the canvas's CURRENT parent, not the container captured in
    // this closure: after modal.js re-parents `canvas` into the modal (or
    // back into the thumbnail), the original `container` may be empty or a
    // different size, and sizing from it would fight the modal's own layout.
    // Falls back to the original container if the canvas is (momentarily)
    // detached from any parent.
    const sizingEl = canvas.parentElement || container;
    const w = sizingEl.clientWidth || 1;
    const h = sizingEl.clientHeight || 1;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    // The brief's `setSize(w, h, false)` skips updating canvas.style, which
    // is fine at pixelRatio 1 but not once setPixelRatio(2) is added above:
    // on a HiDPI display the canvas's width/height attributes would exceed
    // its CSS box, overflowing the container and desyncing the CSS2D labels
    // from the geometry they annotate. Passing no third arg (default true)
    // lets setSize also set canvas.style.width/height so the canvas's CSS
    // box always matches the container regardless of device pixel ratio.
    renderer.setSize(w, h);
    labelRenderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }

  // Dispose every geometry/material owned by the group, and detach CSS2D
  // label DOM elements from the overlay, before the group is discarded.
  // CSS2DRenderer only appends elements for objects it currently traverses
  // in the scene graph — it never removes an element on its own, so a
  // CSS2DObject's DOM node must be removed explicitly or it leaks into the
  // overlay on every rebuild.
  function disposeGroup(group) {
    group.traverse((obj) => {
      if (obj.geometry) {
        obj.geometry.dispose();
      }
      if (obj.material) {
        if (Array.isArray(obj.material)) {
          obj.material.forEach((m) => m.dispose());
        } else {
          obj.material.dispose();
        }
      }
      if (obj.isCSS2DObject && obj.element && obj.element.parentNode) {
        obj.element.parentNode.removeChild(obj.element);
      }
    });
  }

  function buildScene(params) {
    disposeGroup(dynamicGroup);
    scene.remove(dynamicGroup);
    dynamicGroup = new THREE.Group();

    const blockHeight = params.H1 + params.H2;
    const blockGeo = new THREE.BoxGeometry(params.A, blockHeight, params.B);
    const blockMat = new THREE.MeshStandardMaterial({ color: 0xcfd8e3, transparent: true, opacity: 0.5 });
    const blockMesh = new THREE.Mesh(blockGeo, blockMat);
    blockMesh.position.set(params.A / 2, blockHeight / 2, params.B / 2);
    dynamicGroup.add(blockMesh);

    const pipeStart = { x: 0, y: params.H1 + params.H2 + params.Hv, z: 0 };
    const pipeEnd = { x: params.A, y: params.H1 + params.H2 + params.Hv, z: 0 };
    const pipeRadius = visualScale('PhiM', params.PhiM) / 2;
    const pipeLen = Math.hypot(pipeEnd.x - pipeStart.x, pipeEnd.z - pipeStart.z) || params.A;
    const pipeGeo = new THREE.CylinderGeometry(pipeRadius, pipeRadius, pipeLen, 16);
    const pipeMat = new THREE.MeshStandardMaterial({ color: 0xe07a2c });
    const pipeMesh = new THREE.Mesh(pipeGeo, pipeMat);
    pipeMesh.rotation.z = Math.PI / 2;
    pipeMesh.position.set(params.A / 2, pipeStart.y, 0);
    dynamicGroup.add(pipeMesh);

    for (const rec of dimensionRecords) {
      const from = rec.from(params);
      const to = rec.to(params);
      const lineGeo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(from.x, from.y, from.z),
        new THREE.Vector3(to.x, to.y, to.z)
      ]);
      const lineMat = new THREE.LineDashedMaterial({ color: 0x1a2b4c, dashSize: 0.02, gapSize: 0.01 });
      const line = new THREE.Line(lineGeo, lineMat);
      line.computeLineDistances();
      dynamicGroup.add(line);

      const labelDiv = document.createElement('div');
      labelDiv.textContent = rec.label(params);
      labelDiv.style.fontSize = '11px';
      labelDiv.style.color = '#1a2b4c';
      labelDiv.style.background = 'rgba(255,255,255,0.8)';
      labelDiv.style.padding = '1px 4px';
      labelDiv.style.borderRadius = '3px';
      labelDiv.style.whiteSpace = 'nowrap';
      const labelObj = new CSS2DObject(labelDiv);
      labelObj.position.set(
        (from.x + to.x) / 2 + rec.offsetDir.x * 0.05,
        (from.y + to.y) / 2 + rec.offsetDir.y * 0.05,
        (from.z + to.z) / 2 + rec.offsetDir.z * 0.05
      );
      dynamicGroup.add(labelObj);
    }

    scene.add(dynamicGroup);
  }

  function render(params) {
    buildScene(params);
  }

  function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
    labelRenderer.render(scene, camera);
  }
  window.addEventListener('resize', resize);
  resize();
  animate();

  return { render, canvas, overlay, resize };
}
