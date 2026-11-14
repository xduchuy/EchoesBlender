import * as THREE from "three";

const SKY_VERTEX_SHADER = /* glsl */ `
  varying vec3 vWorldDir;
  void main() {
    vec4 wp = modelMatrix * vec4(position, 1.0);
    vWorldDir = normalize(position);
    gl_Position = projectionMatrix * viewMatrix * wp;
  }
`;

const SKY_FRAGMENT_SHADER = /* glsl */ `
  uniform vec3 uSkyLeft;
  uniform vec3 uSkyRight;
  uniform vec3 uSkyZenith;
  uniform vec3 uSkyHorizon;
  uniform vec3 uSunDir;
  uniform vec3 uSunColor;
  varying vec3 vWorldDir;

  void main() {
    vec3 dir = normalize(vWorldDir);
    float h = clamp(dir.y * 1.4 + 0.08, 0.0, 1.0);
    float lr = smoothstep(-0.65, 0.75, dir.x);
    vec3 horizCol = mix(uSkyLeft, uSkyRight, lr);
    vec3 baseSky = mix(mix(uSkyHorizon, horizCol, 0.55), uSkyZenith, pow(h, 0.72));

    float sunDot = max(dot(dir, normalize(uSunDir)), 0.0);
    float glow = pow(sunDot, 10.0) * 0.42 + pow(sunDot, 72.0) * 0.75;
    vec3 col = baseSky + uSunColor * glow;
    gl_FragColor = vec4(col, 1.0);
  }
`;

function createSoftMistTexture(size = 256) {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  const grad = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  grad.addColorStop(0.0, "rgba(255, 255, 255, 0.58)");
  grad.addColorStop(0.38, "rgba(242, 246, 240, 0.24)");
  grad.addColorStop(0.75, "rgba(220, 228, 222, 0.06)");
  grad.addColorStop(1.0, "rgba(220, 228, 222, 0.0)");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);

  const tex = new THREE.CanvasTexture(canvas);
  tex.needsUpdate = true;
  return tex;
}

export function createAtmosphereSystem(scene, renderer) {
  const skyUniforms = {
    uSkyLeft: { value: new THREE.Color("#273337") },
    uSkyRight: { value: new THREE.Color("#ded3b8") },
    uSkyZenith: { value: new THREE.Color("#4c595c") },
    uSkyHorizon: { value: new THREE.Color("#a8aba1") },
    uSunDir: { value: new THREE.Vector3(0.925, 0.366, -0.097).normalize() },
    uSunColor: { value: new THREE.Color(0xffcc84) },
  };

  const skyGeo = new THREE.SphereGeometry(720, 32, 24);
  const skyMat = new THREE.ShaderMaterial({
    uniforms: skyUniforms,
    vertexShader: SKY_VERTEX_SHADER,
    fragmentShader: SKY_FRAGMENT_SHADER,
    side: THREE.BackSide,
    depthWrite: false,
    fog: false,
  });
  const skyMesh = new THREE.Mesh(skyGeo, skyMat);
  skyMesh.frustumCulled = false;
  scene.add(skyMesh);

  // Separate minimal scene for fast PMREM environment reflections
  const pmremGenerator = new THREE.PMREMGenerator(renderer);
  pmremGenerator.compileEquirectangularShader();
  const envScene = new THREE.Scene();
  const envSky = new THREE.Mesh(new THREE.SphereGeometry(40, 24, 16), skyMat);
  envScene.add(envSky);
  let currentEnvRT = null;

  // Low-lying volumetric-style drifting mist sprites matching 10_ATMOSPHERE regions (Y-up)
  const mistTex = createSoftMistTexture(256);
  const mistGroup = new THREE.Group();
  const mistBanks = [
    // Right channel pocket (Blender X=26..56, Y=-50..+12, Z=2..6 -> Three X=26..56, Y=2..6, Z=-12..+50)
    { center: [38, 3.2, 20], spread: [28, 3.0, 44], count: 14, scale: [34, 14] },
    // Courtyard & statue base mist
    { center: [0, 1.8, -2], spread: [26, 1.6, 26], count: 10, scale: [24, 9] },
    // Left rear channel mist
    { center: [-42, 3.0, -14], spread: [26, 2.2, 36], count: 10, scale: [30, 12] },
    // Distant right spire horizon mist
    { center: [38, 12.0, -135], spread: [120, 12.0, 50], count: 12, scale: [88, 34] },
  ];

  const mistSprites = [];
  let seed = 42;
  const rand = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 4294967296;
  };

  for (const bank of mistBanks) {
    for (let i = 0; i < bank.count; i++) {
      const mat = new THREE.SpriteMaterial({
        map: mistTex,
        color: 0xcbd1c7,
        transparent: true,
        opacity: 0.22,
        depthWrite: false,
      });
      const sp = new THREE.Sprite(mat);
      const bx = bank.center[0] + (rand() - 0.5) * bank.spread[0];
      const by = bank.center[1] + (rand() - 0.5) * bank.spread[1];
      const bz = bank.center[2] + (rand() - 0.5) * bank.spread[2];
      sp.position.set(bx, by, bz);
      const sx = bank.scale[0] * (0.75 + rand() * 0.55);
      const sy = bank.scale[1] * (0.75 + rand() * 0.5);
      sp.scale.set(sx, sy, 1);
      sp.userData = {
        baseX: bx,
        baseY: by,
        phase: rand() * Math.PI * 2,
        speed: 0.14 + rand() * 0.16,
      };
      mistGroup.add(sp);
      mistSprites.push(sp);
    }
  }
  scene.add(mistGroup);

  // Subtle floating dust motes across the sunlit sanctuary
  const dustCount = 260;
  const dustPos = new Float32Array(dustCount * 3);
  for (let i = 0; i < dustCount; i++) {
    dustPos[i * 3] = (rand() - 0.5) * 90;
    dustPos[i * 3 + 1] = 1.0 + rand() * 30;
    dustPos[i * 3 + 2] = (rand() - 0.5) * 110;
  }
  const dustGeo = new THREE.BufferGeometry();
  dustGeo.setAttribute("position", new THREE.BufferAttribute(dustPos, 3));
  const dustMat = new THREE.PointsMaterial({
    color: 0xf4e3b8,
    size: 0.24,
    transparent: true,
    opacity: 0.42,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const dustPoints = new THREE.Points(dustGeo, dustMat);
  scene.add(dustPoints);

  function applyMood(mood) {
    skyUniforms.uSkyLeft.value.set(mood.skyLeft);
    skyUniforms.uSkyRight.value.set(mood.skyRight);
    skyUniforms.uSkyZenith.value.set(mood.skyZenith);
    skyUniforms.uSkyHorizon.value.set(mood.skyHorizon);
    skyUniforms.uSunDir.value.set(...mood.sunDirection).normalize();
    skyUniforms.uSunColor.value.setHex(mood.sunColor);

    scene.fog = new THREE.FogExp2(mood.fogColor, mood.fogDensity);
    for (const sp of mistSprites) {
      sp.material.color.setHex(mood.mistTint);
      sp.material.opacity = mood.mistOpacity;
    }

    if (currentEnvRT) currentEnvRT.dispose();
    currentEnvRT = pmremGenerator.fromScene(envScene, 0.04);
    scene.environment = currentEnvRT.texture;
  }

  function update(elapsed) {
    for (const sp of mistSprites) {
      const u = sp.userData;
      sp.position.x = u.baseX + Math.sin(elapsed * u.speed + u.phase) * 2.6;
      sp.position.y = u.baseY + Math.cos(elapsed * u.speed * 0.8 + u.phase) * 0.35;
    }
    dustPoints.rotation.y = elapsed * 0.008;
  }

  function dispose() {
    if (currentEnvRT) currentEnvRT.dispose();
    pmremGenerator.dispose();
    skyGeo.dispose();
    skyMat.dispose();
    mistTex.dispose();
    dustGeo.dispose();
    dustMat.dispose();
  }

  return { applyMood, update, dispose };
}
