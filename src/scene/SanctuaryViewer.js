import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { DRACOLoader } from "three/examples/jsm/loaders/DRACOLoader.js";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";

import { CAMERA_PRESETS, LIGHTING_MOODS } from "./config.js";
import { createSanctuaryMaterialEnhancer } from "./materials.js";
import { createAtmosphereSystem } from "./atmosphere.js";
import { KnightCharacter } from "./KnightCharacter.js";

export class SanctuaryViewer {
  constructor(canvas, callbacks = {}) {
    this.canvas = canvas;
    this.callbacks = callbacks;
    this.moodIndex = 0;
    this.walkMode = false;
    this.knightMode = false;
    this.autoOrbit = false;
    this.keys = new Set();
    this.transition = null;
    this.rafId = 0;
    this.clock = new THREE.Clock();
    this.isDraggingLook = false;
    this.lastPointer = { x: 0, y: 0 };
    this.euler = new THREE.Euler(0, 0, 0, "YXZ");

    this.knight = new KnightCharacter();
    this.knightOrbit = { yaw: 0.24, pitch: 0.24, distance: 4.35 };
    this._knightCamGoal = new THREE.Vector3();
    this._knightLookPos = new THREE.Vector3();
    this._camDirTmp = new THREE.Vector3();
    this._camRaycaster = new THREE.Raycaster();

    this._initRenderer();
    this._initScene();
    this._initLighting();
    this._initControls();
    this._initPostProcessing();
    this._bindEvents();
  }

  _initRenderer() {
    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      antialias: true,
      powerPreference: "high-performance",
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = LIGHTING_MOODS[0].exposure;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
  }

  _initScene() {
    this.scene = new THREE.Scene();
    const hero = CAMERA_PRESETS.hero;
    this.camera = new THREE.PerspectiveCamera(
      hero.fov,
      window.innerWidth / window.innerHeight,
      0.3,
      950
    );
    this.camera.position.set(...hero.position);

    this.materialEnhancer = createSanctuaryMaterialEnhancer();
    this.atmosphere = createAtmosphereSystem(this.scene, this.renderer);
  }

  _initLighting() {
    this.sunLight = new THREE.DirectionalLight(0xffcc84, 3.4);
    this.sunLight.castShadow = true;
    this.sunLight.shadow.mapSize.set(2048, 2048);
    this.sunLight.shadow.camera.left = -85;
    this.sunLight.shadow.camera.right = 85;
    this.sunLight.shadow.camera.top = 85;
    this.sunLight.shadow.camera.bottom = -85;
    this.sunLight.shadow.camera.near = 10;
    this.sunLight.shadow.camera.far = 360;
    this.sunLight.shadow.bias = -0.0005;
    this.sunLight.shadow.normalBias = 0.06;
    this.scene.add(this.sunLight);
    this.scene.add(this.sunLight.target);
    this.sunLight.target.position.set(0, 4, -5);

    this.fillLight = new THREE.DirectionalLight(0x7a96a8, 0.72);
    this.scene.add(this.fillLight);

    this.hemiLight = new THREE.HemisphereLight(0x9aa9ae, 0x161c1a, 0.95);
    this.scene.add(this.hemiLight);
  }

  _initControls() {
    this.controls = new OrbitControls(this.camera, this.canvas);
    this.controls.target.set(...CAMERA_PRESETS.hero.target);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.06;
    this.controls.maxDistance = 260;
    this.controls.minDistance = 1.6;
    this.controls.maxPolarAngle = Math.PI * 0.495;
    this.controls.autoRotate = false;
    this.controls.autoRotateSpeed = 0.45;
    this.controls.update();
  }

  _initPostProcessing() {
    this.composer = new EffectComposer(this.renderer);
    this.renderPass = new RenderPass(this.scene, this.camera);
    this.composer.addPass(this.renderPass);

    this.bloomPass = new UnrealBloomPass(
      new THREE.Vector2(window.innerWidth, window.innerHeight),
      LIGHTING_MOODS[0].bloomStrength,
      0.55,
      0.88
    );
    this.composer.addPass(this.bloomPass);
    this.composer.addPass(new OutputPass());
  }

  _bindEvents() {
    this._onResize = () => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(w, h);
      this.composer.setSize(w, h);
    };

    this._onKeyDown = (e) => {
      if (e.key === "Escape") {
        if (this.walkMode) {
          this.setWalkMode(false);
          this.callbacks.onWalkChange?.(false);
          return;
        }
        if (this.knightMode) {
          this.setKnightMode(false);
          this.callbacks.onKnightChange?.(false);
          return;
        }
      }
      this.keys.add(e.code);
    };

    this._onKeyUp = (e) => {
      this.keys.delete(e.code);
    };

    this._onPointerDown = (e) => {
      this.transition = null;
      if ((this.walkMode || this.knightMode) && e.button === 0) {
        this.isDraggingLook = true;
        this.lastPointer = { x: e.clientX, y: e.clientY };
      }
    };

    this._onPointerMove = (e) => {
      if (!this.isDraggingLook) return;
      const dx = e.clientX - this.lastPointer.x;
      const dy = e.clientY - this.lastPointer.y;
      this.lastPointer = { x: e.clientX, y: e.clientY };

      if (this.walkMode) {
        this.euler.setFromQuaternion(this.camera.quaternion);
        this.euler.y -= dx * 0.0032;
        this.euler.x = Math.max(-1.45, Math.min(1.45, this.euler.x - dy * 0.0032));
        this.camera.quaternion.setFromEuler(this.euler);
      } else if (this.knightMode) {
        this.knightOrbit.yaw -= dx * 0.0046;
        this.knightOrbit.pitch = THREE.MathUtils.clamp(
          this.knightOrbit.pitch + dy * 0.004,
          -0.12,
          1.05
        );
      }
    };

    this._onPointerUp = () => {
      this.isDraggingLook = false;
    };

    this._onWheel = (e) => {
      if (!this.knightMode) return;
      this.knightOrbit.distance = THREE.MathUtils.clamp(
        this.knightOrbit.distance + e.deltaY * 0.0028,
        2.3,
        9.5
      );
    };

    window.addEventListener("resize", this._onResize);
    window.addEventListener("keydown", this._onKeyDown);
    window.addEventListener("keyup", this._onKeyUp);
    this.canvas.addEventListener("pointerdown", this._onPointerDown);
    this.canvas.addEventListener("wheel", this._onWheel, { passive: true });
    window.addEventListener("pointermove", this._onPointerMove);
    window.addEventListener("pointerup", this._onPointerUp);
  }

  async loadModel(url = "/models/drowned_sanctuary.glb", knightUrl = "/models/forgotten_knight.glb") {
    this.applyMood(0);

    const dracoLoader = new DRACOLoader();
    dracoLoader.setDecoderPath("/draco/");

    const loader = new GLTFLoader();
    loader.setDRACOLoader(dracoLoader);

    let sanctuaryRatio = 0;
    let knightRatio = 0;
    const emitProgress = () => {
      const combined = Math.min(0.95, sanctuaryRatio * 0.78 + knightRatio * 0.22);
      this.callbacks.onProgress?.(combined);
    };

    const loadGLTF = (assetUrl, onRatio) =>
      new Promise((resolve, reject) => {
        loader.load(
          assetUrl,
          resolve,
          (xhr) => {
            if (xhr.total > 0) {
              onRatio(Math.min(1, xhr.loaded / xhr.total));
              emitProgress();
            }
          },
          reject
        );
      });

    const [sanctuaryGLTF, knightGLTF] = await Promise.all([
      loadGLTF(url, (r) => {
        sanctuaryRatio = r;
      }),
      loadGLTF(knightUrl, (r) => {
        knightRatio = r;
      }).catch((err) => {
        console.warn("Optional Knight GLB unavailable:", err);
        knightRatio = 1;
        return null;
      }),
    ]);

    let meshCount = 0;
    let triCount = 0;
    sanctuaryGLTF.scene.traverse((child) => {
      if (child.isMesh) {
        if (child.name === "Causeway_Scale_Figure" && knightGLTF) {
          child.visible = false;
          return;
        }
        this.materialEnhancer.enhanceMesh(child);
        meshCount += 1;
        const geom = child.geometry;
        triCount += geom.index ? geom.index.count / 3 : geom.attributes.position.count / 3;
      }
    });

    this.scene.add(sanctuaryGLTF.scene);

    if (knightGLTF) {
      knightGLTF.scene.traverse((child) => {
        if (child.isMesh && !child.name.startsWith("Pedestal_")) {
          meshCount += 1;
          const geom = child.geometry;
          triCount += geom.index ? geom.index.count / 3 : geom.attributes.position.count / 3;
        }
      });
      this.knight.attachFromGLTF(knightGLTF, this.scene);
      this.knight.setSanctuaryRoot(sanctuaryGLTF.scene);
      this.knight.setMoodProfile(LIGHTING_MOODS[this.moodIndex].id);
    }

    dracoLoader.dispose();

    this.callbacks.onProgress?.(1.0);
    this.callbacks.onLoaded?.({
      meshes: meshCount,
      triangles: Math.round(triCount),
    });

    this._startLoop();
  }

  applyMood(index) {
    this.moodIndex = index % LIGHTING_MOODS.length;
    const mood = LIGHTING_MOODS[this.moodIndex];

    const sDir = new THREE.Vector3(...mood.sunDirection).normalize();
    this.sunLight.position.copy(sDir).multiplyScalar(160);
    this.sunLight.color.setHex(mood.sunColor);
    this.sunLight.intensity = mood.sunIntensity;

    const fDir = new THREE.Vector3(...mood.fillDirection).normalize();
    this.fillLight.position.copy(fDir).multiplyScalar(120);
    this.fillLight.color.setHex(mood.fillColor);
    this.fillLight.intensity = mood.fillIntensity;

    this.hemiLight.color.setHex(mood.hemiSky);
    this.hemiLight.groundColor.setHex(mood.hemiGround);
    this.hemiLight.intensity = mood.hemiIntensity;

    this.renderer.toneMappingExposure = mood.exposure;
    if (this.bloomPass) {
      this.bloomPass.strength = mood.bloomStrength;
    }

    this.atmosphere.applyMood(mood);
    this.knight.setMoodProfile(mood.id);
    return mood;
  }

  cycleMood() {
    return this.applyMood((this.moodIndex + 1) % LIGHTING_MOODS.length);
  }

  flyToPreset(key) {
    let preset = CAMERA_PRESETS[key];
    if (!preset) return;
    if (key === "knight" && this.knight.ready) {
      preset = this.knight.getShowcaseCameraPose();
    }
    if (this.walkMode) {
      this.setWalkMode(false);
      this.callbacks.onWalkChange?.(false);
    }
    if (this.knightMode) {
      this.setKnightMode(false);
      this.callbacks.onKnightChange?.(false);
    }

    this.transition = {
      startTime: performance.now(),
      duration: 1100,
      fromPos: this.camera.position.clone(),
      toPos: new THREE.Vector3(...preset.position),
      fromTarget: this.controls.target.clone(),
      toTarget: new THREE.Vector3(...preset.target),
      fromFov: this.camera.fov,
      toFov: preset.fov,
    };
  }

  setAutoOrbit(enabled) {
    this.autoOrbit = Boolean(enabled);
    this.controls.autoRotate = this.autoOrbit && !this.walkMode && !this.knightMode;
  }

  setWalkMode(enabled) {
    const next = Boolean(enabled);
    if (next && this.knightMode) {
      this.setKnightMode(false);
      this.callbacks.onKnightChange?.(false);
    }

    this.walkMode = next;
    this.transition = null;
    this.controls.enabled = !this.walkMode && !this.knightMode;
    this.controls.autoRotate = this.autoOrbit && !this.walkMode && !this.knightMode;

    if (!this.walkMode) {
      const forward = new THREE.Vector3(0, 0, -1).applyQuaternion(this.camera.quaternion);
      this.controls.target.copy(this.camera.position).addScaledVector(forward, 18);
      this.controls.update();
    }
  }

  setKnightMode(enabled) {
    const next = Boolean(enabled) && this.knight.ready;
    if (next && this.walkMode) {
      this.walkMode = false;
      this.callbacks.onWalkChange?.(false);
    }

    this.knightMode = next;
    this.transition = null;
    this.controls.enabled = !this.knightMode && !this.walkMode;
    this.controls.autoRotate = this.autoOrbit && !this.knightMode && !this.walkMode;

    if (this.knightMode) {
      this.knightOrbit.yaw = this.knight.yaw + Math.PI + 0.16;
      this.knightOrbit.pitch = 0.24;
      this.camera.fov = 46;
      this.camera.updateProjectionMatrix();
      this.knight.getFocusTarget(this._knightLookPos);
      this._updateKnightCamera(0.016, true);
    } else if (!this.walkMode && this.knight.ready) {
      this.knight.getFocusTarget(this.controls.target);
      this.controls.update();
    }
  }

  _updateKnightCamera(dt, snap = false) {
    if (!this.knightMode || !this.knight.ready) return;

    const target = this.knight.getFocusTarget(this._knightLookPos);
    const { yaw, pitch, distance } = this.knightOrbit;
    const horizDist = Math.cos(pitch) * distance;

    this._knightCamGoal.set(
      target.x + Math.sin(yaw) * horizDist,
      target.y + Math.sin(pitch) * distance,
      target.z + Math.cos(yaw) * horizDist
    );

    // Prevent camera from clipping behind stone columns/cliffs or dropping under water
    if (this.knight.solidMeshes.length > 0) {
      this._camDirTmp.subVectors(this._knightCamGoal, target);
      const wantDist = this._camDirTmp.length();
      if (wantDist > 0.2) {
        this._camDirTmp.divideScalar(wantDist);
        this._camRaycaster.set(target, this._camDirTmp);
        this._camRaycaster.far = wantDist;
        const hits = this._camRaycaster.intersectObjects(this.knight.solidMeshes, false);
        if (hits.length > 0 && hits[0].distance < wantDist) {
          const safeDist = Math.max(1.15, hits[0].distance - 0.35);
          this._knightCamGoal.copy(target).addScaledVector(this._camDirTmp, safeDist);
        }
      }
    }
    this._knightCamGoal.y = Math.max(0.45, this._knightCamGoal.y);

    if (snap) {
      this.camera.position.copy(this._knightCamGoal);
    } else {
      const alpha = 1 - Math.exp(-14 * dt);
      this.camera.position.lerp(this._knightCamGoal, alpha);
    }
    this.camera.lookAt(target);
  }

  _updateWalkMovement(dt) {
    if (!this.walkMode) return;
    const sprint = this.keys.has("ShiftLeft") || this.keys.has("ShiftRight") ? 2.4 : 1.0;
    const speed = 16.0 * sprint * dt;

    const forward = new THREE.Vector3(0, 0, -1).applyQuaternion(this.camera.quaternion);
    const right = new THREE.Vector3(1, 0, 0).applyQuaternion(this.camera.quaternion);

    if (this.keys.has("KeyW") || this.keys.has("ArrowUp")) {
      this.camera.position.addScaledVector(forward, speed);
    }
    if (this.keys.has("KeyS") || this.keys.has("ArrowDown")) {
      this.camera.position.addScaledVector(forward, -speed);
    }
    if (this.keys.has("KeyD") || this.keys.has("ArrowRight")) {
      this.camera.position.addScaledVector(right, speed);
    }
    if (this.keys.has("KeyA") || this.keys.has("ArrowLeft")) {
      this.camera.position.addScaledVector(right, -speed);
    }
    if (this.keys.has("KeyE") || this.keys.has("Space")) {
      this.camera.position.y += speed * 0.7;
    }
    if (this.keys.has("KeyQ") || this.keys.has("ControlLeft")) {
      this.camera.position.y = Math.max(1.2, this.camera.position.y - speed * 0.7);
    }
  }

  _updateTransition(nowMs) {
    if (!this.transition) return;
    const tr = this.transition;
    const t = Math.min(1, (nowMs - tr.startTime) / tr.duration);
    const ease = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

    this.camera.position.lerpVectors(tr.fromPos, tr.toPos, ease);
    this.controls.target.lerpVectors(tr.fromTarget, tr.toTarget, ease);
    this.camera.fov = tr.fromFov + (tr.toFov - tr.fromFov) * ease;
    this.camera.updateProjectionMatrix();

    if (t >= 1) {
      this.transition = null;
    }
  }

  _startLoop() {
    const tick = () => {
      this.rafId = requestAnimationFrame(tick);
      const dt = Math.min(0.05, this.clock.getDelta());
      const elapsed = this.clock.elapsedTime;

      this._updateTransition(performance.now());
      this._updateWalkMovement(dt);

      let knightControls = null;
      if (this.knightMode) {
        this.camera.getWorldDirection(this._camDirTmp);
        const camYaw = Math.atan2(this._camDirTmp.x, this._camDirTmp.z);
        knightControls = {
          active: true,
          forward: this.keys.has("KeyW") || this.keys.has("ArrowUp"),
          backward: this.keys.has("KeyS") || this.keys.has("ArrowDown"),
          left: this.keys.has("KeyA") || this.keys.has("ArrowLeft"),
          right: this.keys.has("KeyD") || this.keys.has("ArrowRight"),
          sprint: this.keys.has("ShiftLeft") || this.keys.has("ShiftRight"),
          jump: this.keys.has("Space"),
          cameraYaw: camYaw,
        };
      }

      this.knight.update(dt, elapsed, knightControls);
      this._updateKnightCamera(dt, false);

      this.materialEnhancer.update(dt);
      this.atmosphere.update(elapsed);

      if (!this.walkMode && !this.knightMode) {
        this.controls.update();
      }

      this.composer.render();
    };
    tick();
  }

  dispose() {
    cancelAnimationFrame(this.rafId);
    window.removeEventListener("resize", this._onResize);
    window.removeEventListener("keydown", this._onKeyDown);
    window.removeEventListener("keyup", this._onKeyUp);
    this.canvas.removeEventListener("pointerdown", this._onPointerDown);
    this.canvas.removeEventListener("wheel", this._onWheel);
    window.removeEventListener("pointermove", this._onPointerMove);
    window.removeEventListener("pointerup", this._onPointerUp);
    this.controls.dispose();
    this.knight.dispose();
    this.materialEnhancer.dispose();
    this.atmosphere.dispose();
    this.composer.dispose();
    this.renderer.dispose();
  }
}
