import * as THREE from "three";

function createSeededRand(seed = 1337) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function createCanvas(size = 256) {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  return { canvas, ctx: canvas.getContext("2d") };
}

function makeCanvasTexture(canvas, { srgb = true, repeat = 1 } = {}) {
  const tex = new THREE.CanvasTexture(canvas);
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(repeat, repeat);
  tex.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  tex.needsUpdate = true;
  return tex;
}

function createSteelMaps() {
  const size = 256;
  const rand = createSeededRand(404);
  const albedo = createCanvas(size);
  const rough = createCanvas(size);
  const bump = createCanvas(size);

  // Dark mottled gunmetal base
  albedo.ctx.fillStyle = "#5c6268";
  albedo.ctx.fillRect(0, 0, size, size);
  rough.ctx.fillStyle = "#868686";
  rough.ctx.fillRect(0, 0, size, size);
  bump.ctx.fillStyle = "#808080";
  bump.ctx.fillRect(0, 0, size, size);

  // Oxidation & grime patches
  for (let i = 0; i < 420; i++) {
    const x = rand() * size;
    const y = rand() * size;
    const r = 4 + rand() * 18;
    const dark = rand() < 0.65;
    albedo.ctx.fillStyle = dark
      ? `rgba(34, 38, 42, ${0.08 + rand() * 0.14})`
      : `rgba(110, 118, 124, ${0.06 + rand() * 0.1})`;
    albedo.ctx.beginPath();
    albedo.ctx.arc(x, y, r, 0, Math.PI * 2);
    albedo.ctx.fill();

    const rv = dark ? 175 + Math.floor(rand() * 55) : 95 + Math.floor(rand() * 45);
    rough.ctx.fillStyle = `rgba(${rv}, ${rv}, ${rv}, 0.24)`;
    rough.ctx.beginPath();
    rough.ctx.arc(x, y, r, 0, Math.PI * 2);
    rough.ctx.fill();
  }

  // Subtle rust specks
  for (let i = 0; i < 160; i++) {
    const x = rand() * size;
    const y = rand() * size;
    const r = 1.5 + rand() * 6;
    albedo.ctx.fillStyle = `rgba(98, 52, 28, ${0.14 + rand() * 0.22})`;
    albedo.ctx.beginPath();
    albedo.ctx.arc(x, y, r, 0, Math.PI * 2);
    albedo.ctx.fill();
  }

  // Battle scratches & worn edge glints
  for (let i = 0; i < 260; i++) {
    const x = rand() * size;
    const y = rand() * size;
    const len = 8 + rand() * 34;
    const ang = (rand() - 0.5) * 1.4;
    const x2 = x + Math.cos(ang) * len;
    const y2 = y + Math.sin(ang) * len;

    albedo.ctx.strokeStyle = `rgba(176, 184, 190, ${0.14 + rand() * 0.22})`;
    albedo.ctx.lineWidth = 0.7 + rand() * 0.9;
    albedo.ctx.beginPath();
    albedo.ctx.moveTo(x, y);
    albedo.ctx.lineTo(x2, y2);
    albedo.ctx.stroke();

    rough.ctx.strokeStyle = "rgba(68, 68, 68, 0.35)";
    rough.ctx.lineWidth = 1.0;
    rough.ctx.beginPath();
    rough.ctx.moveTo(x, y);
    rough.ctx.lineTo(x2, y2);
    rough.ctx.stroke();

    bump.ctx.strokeStyle = "rgba(42, 42, 42, 0.45)";
    bump.ctx.lineWidth = 1.1;
    bump.ctx.beginPath();
    bump.ctx.moveTo(x, y);
    bump.ctx.lineTo(x2, y2);
    bump.ctx.stroke();
  }

  // Fine corrosion pitting
  for (let i = 0; i < 600; i++) {
    const x = rand() * size;
    const y = rand() * size;
    const r = 0.6 + rand() * 1.6;
    bump.ctx.fillStyle = `rgba(28, 28, 28, ${0.25 + rand() * 0.35})`;
    bump.ctx.beginPath();
    bump.ctx.arc(x, y, r, 0, Math.PI * 2);
    bump.ctx.fill();
  }

  return {
    map: makeCanvasTexture(albedo.canvas, { srgb: true, repeat: 2 }),
    roughnessMap: makeCanvasTexture(rough.canvas, { srgb: false, repeat: 2 }),
    bumpMap: makeCanvasTexture(bump.canvas, { srgb: false, repeat: 2 }),
  };
}

function createFabricCanvas(size = 256) {
  const rand = createSeededRand(717);
  const { canvas, ctx } = createCanvas(size);

  // Deep desaturated pine-forest green medieval wool
  ctx.fillStyle = "#22362c";
  ctx.fillRect(0, 0, size, size);

  // Organic weathered grime & faded moss tones
  for (let i = 0; i < 360; i++) {
    const x = rand() * size;
    const y = rand() * size;
    const r = 4 + rand() * 18;
    const shade = rand();
    if (shade < 0.45) {
      ctx.fillStyle = `rgba(18, 30, 24, ${0.14 + rand() * 0.16})`;
    } else if (shade < 0.8) {
      ctx.fillStyle = `rgba(48, 72, 58, ${0.08 + rand() * 0.12})`;
    } else {
      ctx.fillStyle = `rgba(46, 44, 34, ${0.1 + rand() * 0.14})`;
    }
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
  }

  // Woven twill warp/weft grain
  const step = 4;
  for (let p = 0; p < size; p += step) {
    ctx.fillStyle = p % (step * 2) === 0 ? "rgba(255,255,255,0.035)" : "rgba(0,0,0,0.06)";
    ctx.fillRect(p, 0, 1.5, size);
    ctx.fillRect(0, p, size, 1.5);
  }

  return canvas;
}

function createFabricBumpMap() {
  const size = 256;
  const { canvas, ctx } = createCanvas(size);
  ctx.fillStyle = "#808080";
  ctx.fillRect(0, 0, size, size);
  for (let y = 0; y < size; y += 4) {
    ctx.fillStyle = y % 8 === 0 ? "rgba(215,215,215,0.28)" : "rgba(50,50,50,0.28)";
    ctx.fillRect(0, y, size, 2);
  }
  for (let x = 0; x < size; x += 4) {
    ctx.fillStyle = x % 8 === 0 ? "rgba(215,215,215,0.24)" : "rgba(50,50,50,0.24)";
    ctx.fillRect(x, 0, 2, size);
  }
  return makeCanvasTexture(canvas, { srgb: false, repeat: 6 });
}

function createChainmailMaps() {
  const size = 128;
  const albedo = createCanvas(size);
  const bump = createCanvas(size);

  albedo.ctx.fillStyle = "#26292d";
  albedo.ctx.fillRect(0, 0, size, size);
  bump.ctx.fillStyle = "#303030";
  bump.ctx.fillRect(0, 0, size, size);

  const step = 16;
  for (let row = 0; row * step < size + step; row++) {
    for (let col = 0; col * step < size + step; col++) {
      const cx = col * step + (row % 2 === 1 ? step * 0.5 : 0);
      const cy = row * step * 0.85;
      albedo.ctx.strokeStyle = "#6c737a";
      albedo.ctx.lineWidth = 2.6;
      albedo.ctx.beginPath();
      albedo.ctx.arc(cx, cy, 6.2, 0, Math.PI * 2);
      albedo.ctx.stroke();

      bump.ctx.strokeStyle = "#dcdcdc";
      bump.ctx.lineWidth = 2.8;
      bump.ctx.beginPath();
      bump.ctx.arc(cx, cy, 6.2, 0, Math.PI * 2);
      bump.ctx.stroke();
    }
  }

  return {
    map: makeCanvasTexture(albedo.canvas, { srgb: true, repeat: 7 }),
    bumpMap: makeCanvasTexture(bump.canvas, { srgb: false, repeat: 7 }),
  };
}

function createLeatherMaps() {
  const size = 256;
  const rand = createSeededRand(991);
  const albedo = createCanvas(size);
  const bump = createCanvas(size);

  albedo.ctx.fillStyle = "#5c493b";
  albedo.ctx.fillRect(0, 0, size, size);
  bump.ctx.fillStyle = "#808080";
  bump.ctx.fillRect(0, 0, size, size);

  for (let i = 0; i < 380; i++) {
    const x = rand() * size;
    const y = rand() * size;
    const r = 3 + rand() * 14;
    albedo.ctx.fillStyle =
      rand() < 0.55 ? `rgba(38, 28, 22, ${0.12 + rand() * 0.16})` : `rgba(116, 86, 62, ${0.08 + rand() * 0.12})`;
    albedo.ctx.beginPath();
    albedo.ctx.arc(x, y, r, 0, Math.PI * 2);
    albedo.ctx.fill();
  }

  for (let i = 0; i < 240; i++) {
    const x = rand() * size;
    const y = rand() * size;
    const len = 6 + rand() * 20;
    const ang = rand() * Math.PI * 2;
    const x2 = x + Math.cos(ang) * len;
    const y2 = y + Math.sin(ang) * len;
    albedo.ctx.strokeStyle = "rgba(130, 100, 74, 0.22)";
    albedo.ctx.lineWidth = 0.8;
    albedo.ctx.beginPath();
    albedo.ctx.moveTo(x, y);
    albedo.ctx.lineTo(x2, y2);
    albedo.ctx.stroke();

    bump.ctx.strokeStyle = "rgba(40, 40, 40, 0.45)";
    bump.ctx.lineWidth = 1.0;
    bump.ctx.beginPath();
    bump.ctx.moveTo(x, y);
    bump.ctx.lineTo(x2, y2);
    bump.ctx.stroke();
  }

  return {
    map: makeCanvasTexture(albedo.canvas, { srgb: true, repeat: 3 }),
    bumpMap: makeCanvasTexture(bump.canvas, { srgb: false, repeat: 3 }),
  };
}

function buildCompositeTabardTexture(woolCanvas, crestTexture) {
  if (!crestTexture || !crestTexture.image) return null;
  const size = 256;
  const { canvas, ctx } = createCanvas(size);

  // Tile pine-green wool smoothly across tabard UVs
  ctx.drawImage(woolCanvas, 0, 0, size, size);
  // Overlay faded heraldic shield crest texture (respecting its alpha channel)
  ctx.drawImage(crestTexture.image, 0, 0, size, size);

  const tex = makeCanvasTexture(canvas, { srgb: true, repeat: 1 });
  tex.wrapS = THREE.ClampToEdgeWrapping;
  tex.wrapT = THREE.ClampToEdgeWrapping;
  tex.flipY = crestTexture.flipY;
  tex.needsUpdate = true;
  return tex;
}

export function createKnightMaterialLibrary() {
  const steel = createSteelMaps();
  const woolCanvas = createFabricCanvas(256);
  const fabricMap = makeCanvasTexture(woolCanvas, { srgb: true, repeat: 3 });
  const fabricBump = createFabricBumpMap();
  const chainmail = createChainmailMaps();
  const leather = createLeatherMaps();
  const extraTextures = [];

  function applyToMaterial(mat) {
    if (!mat || !mat.isMeshStandardMaterial) return;
    const mname = mat.name || "";

    if (mname === "MAT_Steel_Worn") {
      mat.color.set(0xd2d7dc);
      mat.map = steel.map;
      mat.roughnessMap = steel.roughnessMap;
      mat.bumpMap = steel.bumpMap;
      mat.bumpScale = 0.012;
      mat.metalness = 0.85;
      mat.roughness = 0.55;
      mat.envMapIntensity = 1.25;
    } else if (mname === "MAT_Steel_Oxidized") {
      mat.color.set(0xaab2ba);
      mat.map = steel.map;
      mat.roughnessMap = steel.roughnessMap;
      mat.bumpMap = steel.bumpMap;
      mat.bumpScale = 0.014;
      mat.metalness = 0.82;
      mat.roughness = 0.62;
      mat.envMapIntensity = 1.1;
    } else if (mname === "MAT_Steel_Dark") {
      mat.color.set(0x7c848c);
      mat.map = steel.map;
      mat.roughnessMap = steel.roughnessMap;
      mat.bumpMap = steel.bumpMap;
      mat.bumpScale = 0.014;
      mat.metalness = 0.84;
      mat.roughness = 0.66;
      mat.envMapIntensity = 1.0;
    } else if (mname === "MAT_Brass_Aged") {
      mat.color.set(0xc99c4e);
      mat.map = steel.map;
      mat.roughnessMap = steel.roughnessMap;
      mat.bumpMap = steel.bumpMap;
      mat.bumpScale = 0.01;
      mat.metalness = 0.84;
      mat.roughness = 0.52;
      mat.envMapIntensity = 1.25;
    } else if (mname === "MAT_Chainmail") {
      mat.color.set(0x9ca3ab);
      mat.map = chainmail.map;
      mat.bumpMap = chainmail.bumpMap;
      mat.bumpScale = 0.018;
      mat.metalness = 0.84;
      mat.roughness = 0.56;
      mat.envMapIntensity = 1.1;
    } else if (mname === "MAT_Rust") {
      mat.color.set(0x6e3a20);
      mat.map = steel.map;
      mat.bumpMap = steel.bumpMap;
      mat.bumpScale = 0.018;
      mat.metalness = 0.22;
      mat.roughness = 0.9;
      mat.envMapIntensity = 0.5;
    } else if (mname === "MAT_Fabric_Cape" || mname === "MAT_Fabric_ForestGreen") {
      mat.color.set(mname === "MAT_Fabric_Cape" ? 0xdde5dc : 0xeaf0e8);
      mat.map = fabricMap;
      mat.bumpMap = fabricBump;
      mat.bumpScale = 0.01;
      mat.metalness = 0.0;
      mat.roughness = 0.94;
      mat.side = THREE.DoubleSide;
      mat.envMapIntensity = 0.45;
      if ("sheen" in mat) mat.sheen = 0.2;
    } else if (mname === "MAT_Fabric_Tabard") {
      const composite = buildCompositeTabardTexture(woolCanvas, mat.map);
      if (composite) {
        extraTextures.push(composite);
        mat.map = composite;
        mat.color.set(0xedf2ea);
      } else {
        mat.map = fabricMap;
        mat.color.set(0xe4ece2);
      }
      mat.bumpMap = fabricBump;
      mat.bumpScale = 0.01;
      mat.metalness = 0.0;
      mat.roughness = 0.94;
      mat.side = THREE.DoubleSide;
      mat.envMapIntensity = 0.45;
    } else if (mname === "MAT_Leather_Dark") {
      mat.color.set(0x52453b);
      mat.map = leather.map;
      mat.bumpMap = leather.bumpMap;
      mat.bumpScale = 0.012;
      mat.metalness = 0.04;
      mat.roughness = 0.64;
      mat.envMapIntensity = 0.65;
    } else if (mname === "MAT_Leather_Brown") {
      mat.color.set(0x9b6d4c);
      mat.map = leather.map;
      mat.bumpMap = leather.bumpMap;
      mat.bumpScale = 0.012;
      mat.metalness = 0.04;
      mat.roughness = 0.58;
      mat.envMapIntensity = 0.7;
    } else if (mname === "MAT_Helm_Void") {
      mat.color.set(0x040506);
      mat.metalness = 0.0;
      mat.roughness = 0.98;
    } else if (mname === "MAT_Lantern_Flame") {
      mat.color.set(0xffb45c);
      mat.emissive = new THREE.Color(0xff922c);
      mat.emissiveIntensity = 3.2;
      mat.roughness = 0.35;
    }

    mat.needsUpdate = true;
  }

  return {
    applyToMaterial,
    dispose() {
      steel.map.dispose();
      steel.roughnessMap.dispose();
      steel.bumpMap.dispose();
      fabricMap.dispose();
      fabricBump.dispose();
      chainmail.map.dispose();
      chainmail.bumpMap.dispose();
      leather.map.dispose();
      leather.bumpMap.dispose();
      for (const tex of extraTextures) tex.dispose();
    },
  };
}
