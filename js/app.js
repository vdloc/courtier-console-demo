import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DRenderer } from 'three/addons/renderers/CSS2DRenderer.js';

console.log('THREE.REVISION:', THREE.REVISION);
console.log('OrbitControls loaded:', typeof OrbitControls === 'function');
console.log('CSS2DRenderer loaded:', typeof CSS2DRenderer === 'function');

document.getElementById('app').textContent =
  `Three.js r${THREE.REVISION} — OrbitControls and CSS2DRenderer both loaded OK.`;
