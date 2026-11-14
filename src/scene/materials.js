import * as THREE from "three";

/**
 * Compute tileable periodic height value in [0, 1] for seamless procedural canvas textures.
 */
function periodicNoise(u, v, seed) {
  const tau = Math.PI * 2.0;
  const x = u * tau;
  const y = v * tau;
  const n1 = Math.sin(x * 2 + seed) * Math.cos(y * 2 - seed * 0.7);
  const n2 = 0.5 * Math.sin(x * 5 - y * 3 + seed * 1.9);
  const n3 = 0.25 * Math.cos(x * 9 + y * 7 - seed * 2.3);
  const n4 = 0.14 * Math.sin(x * 15 - y * 13 + seed * 3.1);
  return 0.5 + 0.5 * ((n1 + n2 + n3 + n4) / 1.89);
}

/**
 * Generate a seamless tileable tangent-space normal map CanvasTexture from periodic height harmonics.
 */
export function createProceduralNormalMap(size = 256, scaleStrength = 2.0, seed = 1.3, repeat = 1) {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  const img = ctx.createImageData(size, size);
  const heights = new Float32Array(size * size);

  for (let y = 0; y < size; y++) {
    const v = y / size;
    for (let x = 0; x < size; x++) {
      const u = x / size;
      // Add deterministic high-frequency speckle
      const hash = Math.sin(x * 12.9898 + y * 78.233 + seed * 37.719) * 43758.5453;
      const rand = hash - Math.floor(hash);
      heights[y * size + x] = periodicNoise(u, v, seed) * 0.8 + rand * 0.2;
    }
  }

  for (let y = 0; y < size; y++) {
    const yPrev = (y - 1 + size) % size;
    const yNext = (y + 1) % size;
    for (let x = 0; x < size; x++) {
      const xPrev = (x - 1 + size) % size;
      const xNext = (x + 1) % size;

      const dx = (heights[y * size + xNext] - heights[y * size + xPrev]) * scaleStrength;
      const dy = (heights[yNext * size + x] - heights[yPrev * size + x]) * scaleStrength;

      const len = Math.hypot(-dx, -dy, 1.0);
      const nx = (-dx / len) * 0.5 + 0.5;
      const ny = (-dy / len) * 0.5 + 0.5;
      const nz = (1.0 / len) * 0.5 + 0.5;

      const idx = (y * size + x) * 4;
      img.data[idx] = Math.round(nx * 255);
      img.data[idx + 1] = Math.round(ny * 255);
      img.data[idx + 2] = Math.round(nz * 255);
      img.data[idx + 3] = 255;
    }
  }

  ctx.putImageData(img, 0, 0);
  const tex = new THREE.CanvasTexture(canvas);
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(repeat, repeat);
  tex.needsUpdate = true;
  return tex;
}

/**
 * Generate seamless ashlar stone block normal map for Gothic architectural limestone.
 */
function createStoneBlockNormalMap(size = 256) {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  const img = ctx.createImageData(size, size);
  const heights = new Float32Array(size * size);

  const rows = 6;
  const cols = 4;

  for (let y = 0; y < size; y++) {
    const v = y / size;
    const rowF = v * rows;
    const rowIdx = Math.floor(rowF);
    const rowFrac = rowF - rowIdx;
    const offset = (rowIdx % 2) * 0.5;

    for (let x = 0; x < size; x++) {
      const u = x / size;
      const colF = u * cols + offset;
      const colFrac = colF - Math.floor(colF);

      const mortarY = Math.min(rowFrac, 1.0 - rowFrac) * rows;
      const mortarX = Math.min(colFrac, 1.0 - colFrac) * cols;
      const groove = Math.min(mortarX, mortarY) < 0.085 ? 0.35 : 1.0;

      const grain = periodicNoise(u, v, 4.7) * 0.35;
      heights[y * size + x] = groove * 0.65 + grain;
    }
  }

  for (let y = 0; y < size; y++) {
    const yPrev = (y - 1 + size) % size;
    const yNext = (y + 1) % size;
    for (let x = 0; x < size; x++) {
      const xPrev = (x - 1 + size) % size;
      const xNext = (x + 1) % size;

      const dx = (heights[y * size + xNext] - heights[y * size + xPrev]) * 2.2;
      const dy = (heights[yNext * size + x] - heights[yPrev * size + x]) * 2.2;
      const len = Math.hypot(-dx, -dy, 1.0);

      const idx = (y * size + x) * 4;
      img.data[idx] = Math.round(((-dx / len) * 0.5 + 0.5) * 255);
      img.data[idx + 1] = Math.round(((-dy / len) * 0.5 + 0.5) * 255);
      img.data[idx + 2] = Math.round(((1.0 / len) * 0.5 + 0.5) * 255);
      img.data[idx + 3] = 255;
    }
  }

  ctx.putImageData(img, 0, 0);
  const tex = new THREE.CanvasTexture(canvas);
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  tex.needsUpdate = true;
  return tex;
}

/**
 * Ensure UV-less procedural Blender BMesh geometry receives clean world-scale triplanar UVs.
 */
export function ensureTriplanarUVs(geometry, uvScale = 0.22) {
  if (!geometry || !geometry.attributes?.position) return;
  if (!geometry.attributes.normal) {
    geometry.computeVertexNormals();
  }
  const pos = geometry.attributes.position;
  const nrm = geometry.attributes.normal;
  const uvArr = new Float32Array(pos.count * 2);

  for (let i = 0; i < pos.count; i++) {
    const px = pos.getX(i);
    const py = pos.getY(i);
    const pz = pos.getZ(i);
    const nx = Math.abs(nrm.getX(i));
    const ny = Math.abs(nrm.getY(i));
    const nz = Math.abs(nrm.getZ(i));

    let u = 0;
    let v = 0;
    if (ny >= nx && ny >= nz) {
      // Horizontal surfaces & water plane (Y-up in Three.js)
      u = px * uvScale;
      v = pz * uvScale;
    } else if (nx >= nz) {
      u = pz * uvScale;
      v = py * uvScale;
    } else {
      u = px * uvScale;
      v = py * uvScale;
    }
    uvArr[i * 2] = u;
    uvArr[i * 2 + 1] = v;
  }

  geometry.setAttribute("uv", new THREE.BufferAttribute(uvArr, 2));
}

export function createSanctuaryMaterialEnhancer() {
  const stoneNormal = createStoneBlockNormalMap(256);
  const cliffNormal = createProceduralNormalMap(256, 3.0, 2.7, 1);
  const barkNormal = createProceduralNormalMap(256, 2.4, 7.1, 1);
  const waterNormal = createProceduralNormalMap(256, 1.35, 9.4, 1);

  return {
    waterNormal,
    enhanceMesh(mesh) {
      if (!mesh.isMesh || !mesh.material) return;
      const mat = mesh.material;
      const mname = mat.name || "";
      const oname = mesh.name || "";

      const isWater = mname === "MAT_Water_Dark" || oname.includes("Water");
      const isCliff = mname === "MAT_Rock_Cliff" || mname === "MAT_Rock_Dark";
      const isBark = mname === "MAT_Bark_Ancient";
      const isDistant = oname.includes("Mountains_Distant");

      ensureTriplanarUVs(mesh.geometry, isWater ? 0.045 : isCliff ? 0.09 : 0.24);

      if (isWater) {
        mesh.castShadow = false;
        mesh.receiveShadow = true;
        mesh.material = new THREE.MeshStandardMaterial({
          name: mname,
          color: new THREE.Color(0x051311),
          roughness: 0.11,
          metalness: 0.18,
          envMapIntensity: 1.55,
          normalMap: waterNormal,
          normalScale: new THREE.Vector2(0.16, 0.16),
        });
        return;
      }

      mesh.castShadow = !isDistant;
      mesh.receiveShadow = true;

      const hasVertexColors = Boolean(mesh.geometry.attributes.color);
      const nextMat = new THREE.MeshStandardMaterial({
        name: mname,
        color: hasVertexColors ? 0xffffff : mat.color ? mat.color.clone() : 0x8b8676,
        vertexColors: hasVertexColors,
        roughness: mat.roughness ?? 0.86,
        metalness: 0.0,
        envMapIntensity: mname.includes("Wet") || mname.includes("Submerged") ? 0.95 : 0.55,
      });

      if (isCliff) {
        nextMat.normalMap = cliffNormal;
        nextMat.normalScale = new THREE.Vector2(0.55, 0.55);
        nextMat.roughness = 0.89;
      } else if (isBark) {
        nextMat.normalMap = barkNormal;
        nextMat.normalScale = new THREE.Vector2(0.45, 0.45);
        nextMat.roughness = 0.91;
      } else if (mname.startsWith("MAT_Limestone") || mname === "MAT_Statue_Weathered") {
        nextMat.normalMap = stoneNormal;
        nextMat.normalScale = new THREE.Vector2(0.28, 0.28);
        nextMat.roughness = mname.includes("Wet") ? 0.42 : 0.84;
      }

      mesh.material = nextMat;
    },
    update(dt) {
      waterNormal.offset.x = (waterNormal.offset.x + dt * 0.012) % 1.0;
      waterNormal.offset.y = (waterNormal.offset.y + dt * 0.008) % 1.0;
    },
    dispose() {
      stoneNormal.dispose();
      cliffNormal.dispose();
      barkNormal.dispose();
      waterNormal.dispose();
    },
  };
}
