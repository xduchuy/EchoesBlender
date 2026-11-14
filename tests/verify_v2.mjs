import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { CAMERA_PRESETS, LIGHTING_MOODS } from "../src/scene/config.js";
import {
  QUALITY_ORDER,
  QUALITY_PRESETS,
  createPerfMonitor,
  detectDefaultQuality,
  getNextQualityId,
  getQualityPreset,
} from "../src/scene/quality.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function parseGlb(relPath) {
  const fullPath = path.join(ROOT, relPath);
  assert.ok(fs.existsSync(fullPath), `Missing GLB asset: ${relPath}`);
  const buf = fs.readFileSync(fullPath);
  assert.ok(buf.length >= 20, `GLB too small: ${relPath}`);

  const magic = buf.readUInt32LE(0);
  const version = buf.readUInt32LE(4);
  const totalLength = buf.readUInt32LE(8);
  assert.equal(magic, 0x46546c67, `Invalid glTF magic header in ${relPath}`);
  assert.equal(version, 2, `Expected glTF 2.0 in ${relPath}`);
  assert.equal(totalLength, buf.length, `Truncated GLB length in ${relPath}`);

  const jsonChunkLen = buf.readUInt32LE(12);
  const jsonChunkType = buf.readUInt32LE(16);
  assert.equal(jsonChunkType, 0x4e4f534a, `First chunk must be JSON in ${relPath}`);

  const jsonStr = buf.subarray(20, 20 + jsonChunkLen).toString("utf8");
  return {
    bytes: buf.length,
    gltf: JSON.parse(jsonStr),
  };
}

test("Sanctuary V2 GLB preserves node contract, Draco, WebP textures, and PBR bakes", () => {
  const { bytes, gltf } = parseGlb("public/models/drowned_sanctuary.glb");
  assert.ok(bytes < 20 * 1024 * 1024, `Sanctuary GLB too large for web delivery: ${bytes} bytes`);
  assert.ok(
    (gltf.extensionsRequired || []).includes("KHR_draco_mesh_compression"),
    "Sanctuary GLB must use Draco compression",
  );

  const images = gltf.images || [];
  assert.ok(images.length >= 10, `Expected baked texture images, got ${images.length}`);
  for (const img of images) {
    assert.equal(img.mimeType, "image/webp", `Expected WebP image in Sanctuary GLB, got ${img.mimeType}`);
  }

  const nodeNames = new Set((gltf.nodes || []).map((n) => n.name));
  for (const reqNode of ["Causeway_Scale_Figure", "Water_Flooded_Basin", "Terrain_Seabed"]) {
    assert.ok(nodeNames.has(reqNode), `Missing required Sanctuary node: ${reqNode}`);
  }

  const mats = new Map((gltf.materials || []).map((m) => [m.name, m]));
  assert.ok(mats.has("MAT_Water_Dark"), "Missing MAT_Water_Dark material");

  const expectedBaked = [
    "MAT_Baked_Sanctuary_HeroArch",
    "MAT_Baked_Sanctuary_Statue",
    "MAT_Baked_Sanctuary_Cliffs",
    "MAT_Baked_Sanctuary_RootsRubble",
    "MAT_Baked_Sanctuary_SecondaryTrim",
  ];
  for (const matName of expectedBaked) {
    const mat = mats.get(matName);
    assert.ok(mat, `Missing baked material: ${matName}`);
    assert.ok(mat.pbrMetallicRoughness?.baseColorTexture, `${matName} missing baseColorTexture`);
    assert.ok(mat.pbrMetallicRoughness?.metallicRoughnessTexture, `${matName} missing metallicRoughnessTexture`);
    assert.ok(mat.normalTexture, `${matName} missing normalTexture`);
    assert.ok(mat.occlusionTexture, `${matName} missing occlusionTexture`);
  }
});

test("Forgotten Knight V2 GLB includes rig, 9 animations, lantern/helm nodes, and baked PBR atlases", () => {
  const { bytes, gltf } = parseGlb("public/models/forgotten_knight.glb");
  assert.ok(bytes < 20 * 1024 * 1024, `Knight GLB too large for web delivery: ${bytes} bytes`);
  assert.ok(
    (gltf.extensionsRequired || []).includes("KHR_draco_mesh_compression"),
    "Knight GLB must use Draco compression",
  );

  const images = gltf.images || [];
  assert.ok(images.length >= 8, `Expected baked Knight texture images, got ${images.length}`);
  for (const img of images) {
    assert.equal(img.mimeType, "image/webp", `Expected WebP image in Knight GLB, got ${img.mimeType}`);
  }

  assert.ok((gltf.skins || []).length >= 1, "Knight GLB missing armature skin");

  const animNames = new Set((gltf.animations || []).map((a) => a.name));
  const expectedAnims = [
    "Idle",
    "Walk",
    "Run",
    "Jump_Start",
    "Airborne",
    "Land",
    "Turn_Left",
    "Turn_Right",
    "Sword_Ready",
  ];
  for (const anim of expectedAnims) {
    assert.ok(animNames.has(anim), `Missing Knight animation clip: ${anim}`);
  }

  const nodeNames = (gltf.nodes || []).map((n) => n.name || "");
  assert.ok(nodeNames.includes("Lantern_Inner_Chamber"), "Missing Lantern_Inner_Chamber node");
  assert.ok(nodeNames.includes("Lantern_Swing"), "Missing Lantern_Swing node");
  assert.ok(
    nodeNames.some((n) => n.startsWith("Pedestal_")),
    "Missing Pedestal_* node(s)",
  );

  const matNames = new Set((gltf.materials || []).map((m) => m.name));
  assert.ok(matNames.has("MAT_Helm_Void"), "Missing MAT_Helm_Void material");
  assert.ok(matNames.has("MAT_Lantern_Flame"), "Missing MAT_Lantern_Flame material");
  assert.ok(matNames.has("MAT_Glass_Lantern"), "Missing MAT_Glass_Lantern material");

  const bakedMats = (gltf.materials || []).filter((m) => String(m.name).startsWith("MAT_Baked_"));
  assert.ok(bakedMats.length >= 4, `Expected >=4 baked Knight atlas materials, got ${bakedMats.length}`);
  for (const mat of bakedMats) {
    assert.ok(mat.pbrMetallicRoughness?.baseColorTexture, `${mat.name} missing baseColorTexture`);
    assert.ok(mat.pbrMetallicRoughness?.metallicRoughnessTexture, `${mat.name} missing metallicRoughnessTexture`);
    assert.ok(mat.normalTexture, `${mat.name} missing normalTexture`);
    assert.ok(mat.occlusionTexture, `${mat.name} missing occlusionTexture`);
  }
});

test("Quality presets, GPU tier detection, and PerfMonitor behave deterministically", () => {
  assert.deepEqual(QUALITY_ORDER, ["low", "medium", "high", "ultra"]);
  assert.equal(getNextQualityId("low"), "medium");
  assert.equal(getNextQualityId("ultra"), "low");
  assert.equal(getQualityPreset("nonexistent").id, QUALITY_PRESETS.high.id);

  assert.equal(
    detectDefaultQuality({ isMobile: false, gpuRenderer: "Google SwiftShader" }),
    "low",
  );
  assert.equal(
    detectDefaultQuality({ isMobile: true, gpuRenderer: "Apple GPU" }),
    "medium",
  );

  const monitor = createPerfMonitor();
  const mockRenderer = {
    info: {
      render: { calls: 52, triangles: 145000 },
      memory: { geometries: 48, textures: 31 },
    },
  };
  let updated = false;
  for (let i = 0; i < 20; i++) {
    updated = monitor.record(1 / 60, mockRenderer) || updated;
  }
  assert.equal(updated, true);
  assert.equal(monitor.fps, 60);
  assert.ok(Math.abs(monitor.frameMs - 16.7) < 0.2);
  assert.equal(monitor.calls, 52);
  assert.equal(monitor.triangles, 145000);
});

test("Viewer config preserves all camera presets and lighting moods", () => {
  for (const camId of ["hero", "knight", "arch", "statue", "causeway"]) {
    assert.ok(CAMERA_PRESETS[camId], `Missing camera preset: ${camId}`);
  }
  const moodIds = new Set(LIGHTING_MOODS.map((m) => m.id));
  for (const moodId of ["afternoon", "moonlight", "dawn"]) {
    assert.ok(moodIds.has(moodId), `Missing lighting mood: ${moodId}`);
  }
});

test("Web deployment assets and Vite entrypoints are present", () => {
  for (const rel of [
    "index.html",
    "package.json",
    "vercel.json",
    "public/images/drowned_sanctuary_final.png",
    "public/images/sanctuary_reference.png",
  ]) {
    assert.ok(fs.existsSync(path.join(ROOT, rel)), `Missing web asset/config: ${rel}`);
  }
});
