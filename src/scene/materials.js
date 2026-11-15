import * as THREE from "three";

/**
 * Compute tileable periodic height value in [0, 1] for seamless procedural fallback textures.
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
 * Generate seamless ashlar stone block normal map for fallback unbaked stone geometry.
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
 * Ensure UV-less procedural geometry receives clean world-scale triplanar UVs.
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

function createLagoonWaterMaterial(waterNormal, uniforms) {
  const waterMat = new THREE.MeshPhysicalMaterial({
    name: "MAT_Water_Dark",
    color: new THREE.Color(0x061918),
    roughness: 0.085,
    metalness: 0.08,
    ior: 1.333,
    reflectivity: 0.9,
    envMapIntensity: 1.4,
    normalMap: waterNormal,
    normalScale: new THREE.Vector2(0.08, 0.08),
  });

  waterMat.customProgramCacheKey = () => "sanctuary-lagoon-water-v2";
  waterMat.onBeforeCompile = (shader) => {
    shader.uniforms.uTime = uniforms.uTime;
    shader.uniforms.uWaterQuality = uniforms.uWaterQuality;
    shader.uniforms.uKnightPos = uniforms.uKnightPos;
    shader.uniforms.uKnightWade = uniforms.uKnightWade;
    shader.uniforms.uDeepColor = uniforms.uDeepColor;
    shader.uniforms.uShallowColor = uniforms.uShallowColor;

    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        `#include <common>
varying vec3 vWaterWorldPos;`
      )
      .replace(
        "#include <worldpos_vertex>",
        `#include <worldpos_vertex>
vWaterWorldPos = (modelMatrix * vec4(transformed, 1.0)).xyz;`
      );

    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>
uniform float uTime;
uniform float uWaterQuality;
uniform vec3 uKnightPos;
uniform float uKnightWade;
uniform vec3 uDeepColor;
uniform vec3 uShallowColor;
varying vec3 vWaterWorldPos;

vec2 sanctuaryWaveGrad(vec2 p, float t, float q) {
  vec2 g = vec2(0.0);
  float w1 = dot(p, vec2(0.68, 0.73)) * 1.35 - t * 1.02;
  g += vec2(0.68, 0.73) * cos(w1) * 0.030;
  float w2 = dot(p, vec2(-0.82, 0.57)) * 2.45 + t * 1.38;
  g += vec2(-0.82, 0.57) * cos(w2) * 0.022;
  if (q >= 1.0) {
    float w3 = dot(p, vec2(0.31, -0.95)) * 4.6 - t * 1.88;
    g += vec2(0.31, -0.95) * cos(w3) * 0.015;
    float w4 = dot(p, vec2(-0.44, -0.89)) * 7.8 + t * 2.35;
    g += vec2(-0.44, -0.89) * cos(w4) * 0.010;
  }
  if (q >= 2.0) {
    float w5 = dot(p, vec2(0.91, -0.41)) * 13.2 - t * 3.05;
    g += vec2(0.91, -0.41) * cos(w5) * 0.006;
  }
  if (uKnightWade > 0.004) {
    vec2 d = p - uKnightPos.xz;
    float r = length(d);
    if (r < 9.0) {
      float ring = cos(r * 7.8 - t * 5.8) * exp(-r * 0.52) * smoothstep(0.18, 0.45, r);
      vec2 dir = r > 0.001 ? d / r : vec2(0.0);
      g += dir * ring * 0.09 * uKnightWade;
    }
  }
  return g;
}`
      )
      .replace(
        "#include <color_fragment>",
        `#include <color_fragment>
float rCenter = length(vWaterWorldPos.xz);
float statueShore = 1.0 - smoothstep(4.2, 13.5, rCenter);
float causewayDist = length(vec2(max(abs(vWaterWorldPos.x) - 3.2, 0.0), max(12.0 - vWaterWorldPos.z, 0.0) + max(vWaterWorldPos.z - 64.0, 0.0)));
float causewayShore = 1.0 - smoothstep(0.0, 7.5, causewayDist);
float outerShore = smoothstep(22.0, 56.0, rCenter);
float shallow = clamp(max(max(statueShore, causewayShore), outerShore * 0.65), 0.0, 1.0);
diffuseColor.rgb = mix(uDeepColor, uShallowColor, shallow);`
      )
      .replace(
        "#include <normal_fragment_maps>",
        `#include <normal_fragment_maps>
vec2 wg = sanctuaryWaveGrad(vWaterWorldPos.xz, uTime, uWaterQuality);
vec3 worldRippleN = normalize(vec3(-wg.x, 1.0, -wg.y));
vec3 viewRippleN = normalize((viewMatrix * vec4(worldRippleN, 0.0)).xyz);
normal = normalize(mix(normal, viewRippleN, 0.85));`
      );
  };

  return waterMat;
}

export function createSanctuaryMaterialEnhancer() {
  const stoneNormal = createStoneBlockNormalMap(256);
  const cliffNormal = createProceduralNormalMap(256, 3.0, 2.7, 1);
  const barkNormal = createProceduralNormalMap(256, 2.4, 7.1, 1);
  const waterNormal = createProceduralNormalMap(256, 1.15, 9.4, 1);

  const waterUniforms = {
    uTime: { value: 0 },
    uWaterQuality: { value: 2 },
    uKnightPos: { value: new THREE.Vector3(0, 0, 42.5) },
    uKnightWade: { value: 0 },
    uDeepColor: { value: new THREE.Color(0x041514) },
    uShallowColor: { value: new THREE.Color(0x0e2824) },
  };
  const waterMaterial = createLagoonWaterMaterial(waterNormal, waterUniforms);

  return {
    waterNormal,
    waterUniforms,

    setWaterQuality(level) {
      waterUniforms.uWaterQuality.value = Number(level ?? 2);
    },

    setWaterMood(moodId) {
      if (moodId === "moonlight") {
        waterUniforms.uDeepColor.value.setHex(0x030c12);
        waterUniforms.uShallowColor.value.setHex(0x081a24);
      } else if (moodId === "dawn") {
        waterUniforms.uDeepColor.value.setHex(0x061315);
        waterUniforms.uShallowColor.value.setHex(0x112423);
      } else {
        waterUniforms.uDeepColor.value.setHex(0x041514);
        waterUniforms.uShallowColor.value.setHex(0x0e2824);
      }
    },

    setKnightRipple(x, z, strength) {
      waterUniforms.uKnightPos.value.set(x, 0, z);
      waterUniforms.uKnightWade.value = strength;
    },

    enhanceMesh(mesh) {
      if (!mesh.isMesh || !mesh.material) return;
      const mat = mesh.material;
      const mname = mat.name || "";
      const oname = mesh.name || "";

      if (oname.startsWith("Collision_")) {
        mesh.visible = false;
        mesh.castShadow = false;
        mesh.receiveShadow = false;
        return;
      }

      const isWater = mname === "MAT_Water_Dark" || oname.includes("Water");
      const isDistant = oname.includes("Mountains_Distant") || mname === "MAT_Dark_Silhouette";
      const hasBakedAtlas = mname.startsWith("MAT_Baked_") || Boolean(mat.map);

      if (isWater) {
        ensureTriplanarUVs(mesh.geometry, 0.045);
        mesh.castShadow = false;
        mesh.receiveShadow = true;
        mesh.material = waterMaterial;
        return;
      }

      mesh.castShadow = !isDistant;
      mesh.receiveShadow = true;

      if (hasBakedAtlas) {
        if (mat.map) mat.map.colorSpace = THREE.SRGBColorSpace;
        if (mat.normalMap && mat.normalScale) {
          mat.normalScale.set(1.08, 1.08);
        }
        if (mat.aoMap) {
          mat.aoMapIntensity = 0.85;
        }
        mat.envMapIntensity =
          mname.includes("RootboundSaint") || mname.includes("Statue")
            ? 0.68
            : mname.includes("HeroArch")
              ? 0.62
              : 0.54;
        mat.needsUpdate = true;
        return;
      }

      if (mname === "MAT_Dark_Silhouette" || isDistant) {
        mat.metalness = 0.0;
        mat.roughness = 0.96;
        mat.envMapIntensity = 0.25;
        mat.needsUpdate = true;
        return;
      }

      // Procedural fallback if an unbaked material is ever encountered
      const isCliff = mname === "MAT_Rock_Cliff" || mname === "MAT_Rock_Dark";
      const isBark = mname === "MAT_Bark_Ancient";
      ensureTriplanarUVs(mesh.geometry, isCliff ? 0.09 : 0.24);

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

    update(dt, elapsed = null) {
      waterNormal.offset.x = (waterNormal.offset.x + dt * 0.01) % 1.0;
      waterNormal.offset.y = (waterNormal.offset.y + dt * 0.007) % 1.0;
      if (typeof elapsed === "number") {
        waterUniforms.uTime.value = elapsed;
      } else {
        waterUniforms.uTime.value += dt;
      }
    },

    dispose() {
      stoneNormal.dispose();
      cliffNormal.dispose();
      barkNormal.dispose();
      waterNormal.dispose();
      waterMaterial.dispose();
    },
  };
}
