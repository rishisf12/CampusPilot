/**
 * Logo3D – animated 3D version of the CampusPilot logomark.
 *
 * @param size Rendered diameter in px (default 64).
 */

import { useRef, useEffect } from 'react';
import * as THREE from 'three';

const TEAL = 0x0f766e;
const TEAL_DARK = 0x0b4f59;
const DARK = 0x1a1a2e;

const RING_R = 48;
const RING_TUBE = 4;
const EYE_R = 10;

export default function Logo3D({ size = 64 }: { size?: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setSize(size, Math.round(size * (150 / 420)));
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    const camera = new THREE.PerspectiveCamera(45, size / (size * (150 / 420)), 0.1, 1000);
    camera.position.set(0, 0, 200);

    const scene = new THREE.Group();

    // Outer thick ring
    const ringGeo = new THREE.TorusGeometry(RING_R, RING_TUBE, 32, 100);
    const ringMat = new THREE.MeshStandardMaterial({ color: TEAL, metalness: 0.4, roughness: 0.2 });
    const ringMesh = new THREE.Mesh(ringGeo, ringMat);
    scene.add(ringMesh);

    // Outer ring top rim highlight
    const rimGeo = new THREE.TorusGeometry(RING_R - 1, RING_TUBE * 0.6, 32, 64);
    const rimMat = new THREE.MeshStandardMaterial({
      color: '#ffffff',
      metalness: 0,
      roughness: 0,
      transparent: true,
      opacity: 0.35,
    });
    const rimMesh = new THREE.Mesh(rimGeo, rimMat);
    scene.add(rimMesh);

    // Inner white face disc
    const faceGeo = new THREE.SphereGeometry(40, 32, 32);
    const faceMat = new THREE.MeshStandardMaterial({
      color: '#ffffff',
      metalness: 0.1,
      roughness: 0.4,
    });
    const faceMesh = new THREE.Mesh(faceGeo, faceMat);
    faceMesh.position.set(0, -4, 2);
    scene.add(faceMesh);

    // Left Circle: 9
    const leftGeo = new THREE.SphereGeometry(EYE_R, 32, 32);
    const leftMat = new THREE.MeshStandardMaterial({ color: DARK, metalness: 0.2, roughness: 0.4 });
    const leftMesh = new THREE.Mesh(leftGeo, leftMat);
    leftMesh.position.set(-22, -8, 4);
    scene.add(leftMesh);

    // Right Circle: 2
    const rightGeo = new THREE.SphereGeometry(10, 32, 32);
    const rightMat = new THREE.MeshStandardMaterial({
      color: DARK,
      metalness: 0.2,
      roughness: 0.4,
    });
    const rightMesh = new THREE.Mesh(rightGeo, rightMat);
    rightMesh.position.set(22, -8, 4);
    scene.add(rightMesh);

    // Center Circle: 11
    const centerGeo = new THREE.SphereGeometry(12, 32, 32);
    const centerMat = new THREE.MeshStandardMaterial({
      color: TEAL,
      metalness: 0.3,
      roughness: 0.3,
    });
    const centerMesh = new THREE.Mesh(centerGeo, centerMat);
    centerMesh.position.set(0, -4, 4);
    scene.add(centerMesh);

    // Smile Curve
    const smileGeo = new THREE.TorusGeometry(0, 12, 8, 20, 0, Math.PI);
    const smileMat = new THREE.MeshStandardMaterial({
      color: TEAL,
      metalness: 0.3,
      roughness: 0.3,
    });
    const smileMesh = new THREE.Mesh(smileGeo, smileMat);
    smileMesh.position.set(0, 12, 2);
    scene.add(smileMesh);

    // Bottom Base Bar
    const baseGeo = new THREE.BoxGeometry(40, 10, 10);
    const baseMat = new THREE.MeshStandardMaterial({ color: TEAL, metalness: 0.3, roughness: 0.3 });
    const baseMesh = new THREE.Mesh(baseGeo, baseMat);
    baseMesh.position.set(0, 90, -5);
    scene.add(baseMesh);

    // Bottom oval base
    const baseOvalGeo = new THREE.CylinderGeometry(50, 50, 8, 32);
    const baseOvalMat = new THREE.MeshStandardMaterial({
      color: TEAL_DARK,
      metalness: 0.3,
      roughness: 0.3,
    });
    const baseOvalMesh = new THREE.Mesh(baseOvalGeo, baseOvalMat);
    baseOvalMesh.position.set(0, 88, -8);
    scene.add(baseOvalMesh);

    renderer.render(scene, camera);
  }, [size]);

  return (
    <div
      style={{
        width: size,
        height: Math.round(size * (150 / 420)),
        touchAction: 'pan-y',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />
    </div>
  );
}
