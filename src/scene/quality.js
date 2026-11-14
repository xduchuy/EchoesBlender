export const QUALITY_ORDER = ["low", "medium", "high", "ultra"];

export const QUALITY_PRESETS = {
  low: {
    id: "low",
    label: "Low",
    maxPixelRatio: 1.0,
    shadowMapSize: 1024,
    shadowsEnabled: true,
    smaa: false,
    bloomScale: 0.55,
    fogCount: 24,
    fireflyCount: 45,
    waterQuality: 0,
    envIntensityScale: 0.92,
  },
  medium: {
    id: "medium",
    label: "Medium",
    maxPixelRatio: 1.35,
    shadowMapSize: 2048,
    shadowsEnabled: true,
    smaa: false,
    bloomScale: 0.85,
    fogCount: 44,
    fireflyCount: 95,
    waterQuality: 1,
    envIntensityScale: 1.0,
  },
  high: {
    id: "high",
    label: "High",
    maxPixelRatio: 1.75,
    shadowMapSize: 2048,
    shadowsEnabled: true,
    smaa: true,
    bloomScale: 1.0,
    fogCount: 68,
    fireflyCount: 150,
    waterQuality: 2,
    envIntensityScale: 1.0,
  },
  ultra: {
    id: "ultra",
    label: "Ultra",
    maxPixelRatio: 2.0,
    shadowMapSize: 4096,
    shadowsEnabled: true,
    smaa: true,
    bloomScale: 1.08,
    fogCount: 84,
    fireflyCount: 210,
    waterQuality: 3,
    envIntensityScale: 1.05,
  },
};

export function getQualityPreset(name) {
  const key = String(name || "").toLowerCase();
  return QUALITY_PRESETS[key] || QUALITY_PRESETS.high;
}

export function getNextQualityId(currentId) {
  const idx = QUALITY_ORDER.indexOf(String(currentId || "").toLowerCase());
  return QUALITY_ORDER[(idx + 1) % QUALITY_ORDER.length];
}

export function detectDefaultQuality({ isMobile = false, gpuRenderer = "" } = {}) {
  const rendererStr = String(gpuRenderer || "");
  if (/swiftshader|llvmpipe|software|adreno\s*[34]\d\d|mali-4/i.test(rendererStr)) {
    return "low";
  }

  const nav = typeof navigator !== "undefined" ? navigator : null;
  const cores = Number(nav?.hardwareConcurrency || 0);
  const mem = Number(nav?.deviceMemory || 0);

  if (isMobile) {
    if ((mem > 0 && mem <= 3) || (cores > 0 && cores <= 4)) {
      return "low";
    }
    return "medium";
  }

  if ((cores > 0 && cores <= 4) || (mem > 0 && mem <= 4)) {
    return "medium";
  }

  return "high";
}

export function createPerfMonitor() {
  const samples = new Float32Array(32);
  let cursor = 0;
  let filled = 0;
  let accumTime = 0;

  return {
    fps: 60,
    frameMs: 16.7,
    calls: 0,
    triangles: 0,
    geometries: 0,
    textures: 0,

    record(dt, renderer) {
      const clampedDt = Math.min(Math.max(dt, 0.0005), 0.5);
      samples[cursor] = clampedDt;
      cursor = (cursor + 1) % samples.length;
      if (filled < samples.length) filled++;
      accumTime += clampedDt;

      if (accumTime < 0.25 && filled > 4) return false;
      accumTime = 0;

      let total = 0;
      for (let i = 0; i < filled; i++) total += samples[i];
      const avgDt = total / filled;
      this.fps = Math.round(1 / avgDt);
      this.frameMs = Number((avgDt * 1000).toFixed(1));

      if (renderer?.info) {
        this.calls = renderer.info.render.calls;
        this.triangles = renderer.info.render.triangles;
        this.geometries = renderer.info.memory.geometries;
        this.textures = renderer.info.memory.textures;
      }
      return true;
    },
  };
}
