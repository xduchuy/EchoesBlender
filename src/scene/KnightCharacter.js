import * as THREE from "three";
import { createKnightMaterialLibrary } from "./knightMaterials.js";

const DEFAULT_SPAWN = {
  x: -0.15,
  y: 0.41,
  z: 42.5,
  yaw: Math.PI, // +Z glTF front rotated by PI faces -Z along the Causeway toward the Sanctuary Statue
};

const PLAYABLE_BOUNDS = {
  minX: -52,
  maxX: 52,
  minZ: -36,
  maxZ: 68,
};

const WADING_FLOOR_Y = -0.2;
const WATER_SURFACE_Y = 0.0;

const CHAR_RIGHT = new THREE.Vector3(1, 0, 0);
const CHAR_UP = new THREE.Vector3(0, 1, 0);
const CHAR_FWD = new THREE.Vector3(0, 0, 1);

function damp(current, target, lambda, dt) {
  return THREE.MathUtils.lerp(current, target, 1 - Math.exp(-lambda * dt));
}

function shortestAngleDiff(from, to) {
  let diff = ((to - from + Math.PI) % (Math.PI * 2)) - Math.PI;
  if (diff < -Math.PI) diff += Math.PI * 2;
  return diff;
}

export class KnightCharacter {
  constructor() {
    this.root = new THREE.Group();
    this.root.name = "ForgottenKnight_Player";
    this.model = null;
    this.ready = false;

    this.position = new THREE.Vector3(DEFAULT_SPAWN.x, DEFAULT_SPAWN.y, DEFAULT_SPAWN.z);
    this.yaw = DEFAULT_SPAWN.yaw;
    this.velocityY = 0;
    this.isGrounded = true;
    this.isWading = false;

    this.moveBlend = 0;
    this.sprintBlend = 0;
    this.walkPhase = 0;
    this.landingDip = 0;
    this.currentSpeed = 0;

    this.bones = new Map();
    this.materialLib = createKnightMaterialLibrary();
    this.lanternLight = null;
    this.lanternBaseIntensity = 2.4;

    this.groundMeshes = [];
    this.solidMeshes = [];
    this.raycaster = new THREE.Raycaster();
    this.raycaster.firstHitOnly = false;

    this._tmpQuat = new THREE.Quaternion();
    this._tmpQuat2 = new THREE.Quaternion();
    this._tmpVecA = new THREE.Vector3();
    this._tmpVecB = new THREE.Vector3();
    this._tmpDir = new THREE.Vector3();
    this._upVec = new THREE.Vector3(0, 1, 0);
    this._downVec = new THREE.Vector3(0, -1, 0);
  }

  attachFromGLTF(gltf, scene) {
    this.model = gltf.scene;
    this.model.name = "ForgottenKnight_Asset";

    let lanternAnchor = null;
    let lanternChamberCenter = null;
    const styledMaterials = new Set();

    this.model.traverse((child) => {
      if (child.name.startsWith("Pedestal_")) {
        child.visible = false;
        return;
      }

      if (child.isBone) {
        if (child.name === "Lantern_Swing") {
          lanternAnchor = child;
        }
      }

      if (child.isMesh) {
        child.castShadow = true;
        child.receiveShadow = true;

        if (child.name === "Lantern_Inner_Chamber") {
          const box = new THREE.Box3().setFromObject(child);
          lanternChamberCenter = box.getCenter(new THREE.Vector3());
        }

        const mats = Array.isArray(child.material) ? child.material : [child.material];
        for (const mat of mats) {
          if (!mat || styledMaterials.has(mat)) continue;
          styledMaterials.add(mat);
          this.materialLib.applyToMaterial(mat);
        }
      }
    });

    this.root.position.set(0, 0, 0);
    this.root.rotation.set(0, 0, 0);
    this.root.scale.set(1, 1, 1);
    this.root.add(this.model);
    scene.add(this.root);

    this.root.updateMatrixWorld(true);
    this._cacheBones();
    this._attachLanternLight(lanternAnchor, lanternChamberCenter);

    this.root.position.copy(this.position);
    this.root.rotation.y = this.yaw;
    this.ready = true;
  }

  _cacheBones() {
    this.bones.clear();
    const invWorld = new THREE.Quaternion();
    const worldQuat = new THREE.Quaternion();

    this.model.traverse((node) => {
      if (!node.isBone) return;
      node.getWorldQuaternion(worldQuat);
      invWorld.copy(worldQuat).invert();

      this.bones.set(node.name, {
        bone: node,
        restQuat: node.quaternion.clone(),
        restPos: node.position.clone(),
        axisRight: CHAR_RIGHT.clone().applyQuaternion(invWorld).normalize(),
        axisUp: CHAR_UP.clone().applyQuaternion(invWorld).normalize(),
        axisFwd: CHAR_FWD.clone().applyQuaternion(invWorld).normalize(),
      });
    });
  }

  _attachLanternLight(lanternBone, chamberWorldCenter) {
    if (this.lanternLight) {
      this.lanternLight.parent?.remove(this.lanternLight);
      this.lanternLight.dispose();
    }

    const light = new THREE.PointLight(0xff9d42, this.lanternBaseIntensity, 10.5, 1.65);
    light.castShadow = false;

    if (lanternBone && chamberWorldCenter) {
      const localPos = lanternBone.worldToLocal(chamberWorldCenter.clone());
      light.position.copy(localPos);
      lanternBone.add(light);
    } else {
      light.position.set(-0.28, 0.7, -0.02);
      this.root.add(light);
    }

    this.lanternLight = light;
  }

  setMoodProfile(moodId) {
    if (moodId === "moonlight") {
      this.lanternBaseIntensity = 4.2;
    } else if (moodId === "dawn") {
      this.lanternBaseIntensity = 2.9;
    } else {
      this.lanternBaseIntensity = 2.1;
    }
  }

  setSanctuaryRoot(sanctuaryRoot) {
    this.groundMeshes = [];
    this.solidMeshes = [];

    sanctuaryRoot.traverse((child) => {
      if (!child.isMesh) return;
      const name = child.name || "";

      if (name === "Causeway_Scale_Figure") {
        child.visible = false;
        return;
      }

      if (name.includes("Mountains_Distant") || name.includes("Reed_Tuft")) {
        return;
      }

      if (name === "Water_Flooded_Basin" || name === "Terrain_Seabed") {
        return;
      }

      this.groundMeshes.push(child);
      this.solidMeshes.push(child);
    });

    this.snapToGround();
  }

  resetToSpawn() {
    this.position.set(DEFAULT_SPAWN.x, DEFAULT_SPAWN.y, DEFAULT_SPAWN.z);
    this.yaw = DEFAULT_SPAWN.yaw;
    this.velocityY = 0;
    this.isGrounded = true;
    this.isWading = false;
    this.snapToGround();
  }

  snapToGround() {
    const stoneY = this._probeGroundHeight(this.position.x, this.position.z, this.position.y);
    if (stoneY !== null) {
      this.position.y = stoneY;
    } else {
      this.position.y = Math.max(WADING_FLOOR_Y, this.position.y);
    }
    this.isWading = this.position.y < WATER_SURFACE_Y - 0.02;
    this.root.position.copy(this.position);
    this.root.rotation.y = this.yaw;
  }

  _probeGroundHeight(x, z, referenceY) {
    if (this.groundMeshes.length === 0) return null;

    this._tmpVecA.set(x, referenceY + 1.35, z);
    this.raycaster.set(this._tmpVecA, this._downVec);
    this.raycaster.far = 4.2;

    const hits = this.raycaster.intersectObjects(this.groundMeshes, false);
    let bestY = null;

    for (const hit of hits) {
      if (!hit.face) continue;
      // Ignore steep walls/arches; keep walkable tops & slopes
      const worldNormal = hit.face.normal
        .clone()
        .transformDirection(hit.object.matrixWorld);
      if (worldNormal.y < 0.45) continue;

      const hy = hit.point.y;
      if (hy > referenceY + 1.05 || hy < WADING_FLOOR_Y - 0.3) continue;

      if (bestY === null || hy > bestY) {
        bestY = hy;
      }
    }

    return bestY;
  }

  _resolveHorizontalMove(dx, dz) {
    if (Math.abs(dx) < 1e-6 && Math.abs(dz) < 1e-6) return { dx: 0, dz: 0 };

    let stepX = dx;
    let stepZ = dz;
    const moveLen = Math.hypot(stepX, stepZ);
    const radius = 0.48;

    if (this.solidMeshes.length > 0 && moveLen > 1e-5) {
      const dirX = stepX / moveLen;
      const dirZ = stepZ / moveLen;
      const whiskerAngles = [0, -0.58, 0.58];
      const probeHeights = [0.65, 1.25];

      for (const hOff of probeHeights) {
        for (const ang of whiskerAngles) {
          const ca = Math.cos(ang);
          const sa = Math.sin(ang);
          const rx = dirX * ca - dirZ * sa;
          const rz = dirX * sa + dirZ * ca;

          this._tmpVecA.set(this.position.x, this.position.y + hOff, this.position.z);
          this._tmpDir.set(rx, 0, rz).normalize();
          this.raycaster.set(this._tmpVecA, this._tmpDir);
          this.raycaster.far = radius + moveLen;

          const hits = this.raycaster.intersectObjects(this.solidMeshes, false);
          for (const hit of hits) {
            if (!hit.face) continue;
            const n = hit.face.normal
              .clone()
              .transformDirection(hit.object.matrixWorld);
            n.y = 0;
            const nLen = n.length();
            if (nLen < 0.35) continue; // Low curb/step we can walk over
            n.divideScalar(nLen);

            const intoWall = stepX * n.x + stepZ * n.z;
            if (intoWall < 0) {
              stepX -= intoWall * n.x;
              stepZ -= intoWall * n.z;
            }
          }
        }
      }
    }

    const nextX = THREE.MathUtils.clamp(
      this.position.x + stepX,
      PLAYABLE_BOUNDS.minX,
      PLAYABLE_BOUNDS.maxX
    );
    const nextZ = THREE.MathUtils.clamp(
      this.position.z + stepZ,
      PLAYABLE_BOUNDS.minZ,
      PLAYABLE_BOUNDS.maxZ
    );

    return {
      dx: nextX - this.position.x,
      dz: nextZ - this.position.z,
    };
  }

  getFocusTarget(out = new THREE.Vector3()) {
    return out.set(this.position.x, this.position.y + 1.48, this.position.z);
  }

  getShowcaseCameraPose() {
    const fwdX = Math.sin(this.yaw);
    const fwdZ = Math.cos(this.yaw);
    const rightX = -Math.cos(this.yaw);
    const rightZ = Math.sin(this.yaw);

    // Three-quarter rear hero framing showing Knight silhouette + Sanctuary ahead
    const camPos = [
      this.position.x - fwdX * 3.05 - rightX * 1.15,
      this.position.y + 1.72,
      this.position.z - fwdZ * 3.05 - rightZ * 1.15,
    ];
    const target = [
      this.position.x + fwdX * 4.5,
      this.position.y + 1.58,
      this.position.z + fwdZ * 4.5,
    ];
    return { position: camPos, target, fov: 42 };
  }

  _setBoneCharEuler(name, pitch = 0, yaw = 0, roll = 0, posOffsetY = 0) {
    const entry = this.bones.get(name);
    if (!entry) return;

    const q = entry.bone.quaternion;
    q.copy(entry.restQuat);

    if (Math.abs(yaw) > 1e-5) {
      this._tmpQuat.setFromAxisAngle(entry.axisUp, yaw);
      q.multiply(this._tmpQuat);
    }
    if (Math.abs(pitch) > 1e-5) {
      this._tmpQuat.setFromAxisAngle(entry.axisRight, pitch);
      q.multiply(this._tmpQuat);
    }
    if (Math.abs(roll) > 1e-5) {
      this._tmpQuat.setFromAxisAngle(entry.axisFwd, roll);
      q.multiply(this._tmpQuat);
    }

    if (posOffsetY !== 0) {
      this._tmpVecB.copy(entry.axisUp).multiplyScalar(posOffsetY);
      entry.bone.position.copy(entry.restPos).add(this._tmpVecB);
    } else {
      entry.bone.position.copy(entry.restPos);
    }
  }

  update(dt, elapsed, controls = null) {
    if (!this.ready) return;

    let moveX = 0;
    let moveZ = 0;
    let isSprinting = false;
    let wantsJump = false;

    if (controls && controls.active) {
      const fwdInput = (controls.forward ? 1 : 0) - (controls.backward ? 1 : 0);
      const sideInput = (controls.right ? 1 : 0) - (controls.left ? 1 : 0);
      isSprinting = Boolean(controls.sprint);
      wantsJump = Boolean(controls.jump);

      if (fwdInput !== 0 || sideInput !== 0) {
        // Camera look vector in XZ plane
        const camFwdX = Math.sin(controls.cameraYaw);
        const camFwdZ = Math.cos(controls.cameraYaw);
        const camRightX = -camFwdZ;
        const camRightZ = camFwdX;

        moveX = camFwdX * fwdInput + camRightX * sideInput;
        moveZ = camFwdZ * fwdInput + camRightZ * sideInput;
        const len = Math.hypot(moveX, moveZ);
        if (len > 1e-5) {
          moveX /= len;
          moveZ /= len;
        }
      }
    }

    const hasMove = Math.hypot(moveX, moveZ) > 0.05;
    const wadeFactor = this.isWading ? 0.8 : 1.0;
    const targetSpeed = hasMove ? (isSprinting ? 4.8 : 2.35) * wadeFactor : 0;
    this.currentSpeed = damp(this.currentSpeed, targetSpeed, hasMove ? 10 : 12, dt);

    if (hasMove) {
      const targetYaw = Math.atan2(moveX, moveZ);
      const diff = shortestAngleDiff(this.yaw, targetYaw);
      this.yaw += diff * Math.min(1, dt * 9.5);
    }

    let actualMoveDist = 0;
    if (this.currentSpeed > 0.02) {
      const wantDx = moveX * this.currentSpeed * dt;
      const wantDz = moveZ * this.currentSpeed * dt;
      const { dx, dz } = this._resolveHorizontalMove(wantDx, wantDz);
      this.position.x += dx;
      this.position.z += dz;
      actualMoveDist = Math.hypot(dx, dz);
    }

    // Vertical gravity & terrain surface tracking
    const stoneGroundY = this._probeGroundHeight(this.position.x, this.position.z, this.position.y);
    const floorY = stoneGroundY !== null ? Math.max(WADING_FLOOR_Y, stoneGroundY) : WADING_FLOOR_Y;

    if (wantsJump && this.isGrounded) {
      this.velocityY = 4.55;
      this.isGrounded = false;
    }

    if (!this.isGrounded || this.position.y > floorY + 0.04) {
      this.velocityY -= 13.5 * dt;
      this.position.y += this.velocityY * dt;
      if (this.position.y <= floorY) {
        if (this.velocityY < -2.4) {
          this.landingDip = Math.min(0.11, -this.velocityY * 0.015);
        }
        this.position.y = floorY;
        this.velocityY = 0;
        this.isGrounded = true;
      }
    } else {
      this.position.y = damp(this.position.y, floorY, 16, dt);
      this.velocityY = 0;
      this.isGrounded = true;
    }

    this.isWading = this.position.y < WATER_SURFACE_Y - 0.02;
    this.landingDip = damp(this.landingDip, 0, 11, dt);

    this.root.position.copy(this.position);
    this.root.rotation.y = this.yaw;

    // Advance stride phase linearly with true ground distance traveled
    const effSpeed = dt > 1e-5 ? actualMoveDist / dt : 0;
    const isMoving = effSpeed > 0.15;
    this.moveBlend = damp(this.moveBlend, isMoving ? 1 : 0, 10, dt);
    this.sprintBlend = damp(this.sprintBlend, isMoving && isSprinting ? 1 : 0, 8, dt);

    if (isMoving && this.isGrounded) {
      this.walkPhase = (this.walkPhase + effSpeed * dt * 2.25) % (Math.PI * 2);
    }

    this._animateBones(elapsed);
    this._updateLanternLight(elapsed);
  }

  _animateBones(elapsed) {
    const m = this.moveBlend;
    const s = this.sprintBlend;
    const p = this.walkPhase;

    // Idle breathing + moody lookout motion
    const breath = Math.sin(elapsed * 1.45);
    const idleHeadYaw = Math.sin(elapsed * 0.42) * 0.08;
    const idleHeadPitch = 0.02 + Math.sin(elapsed * 0.72) * 0.025;
    const wind = Math.sin(elapsed * 2.1) * 0.04 + Math.sin(elapsed * 3.7) * 0.02;

    // Heavy medieval stride values (scaled when blending from idle -> walk -> sprint)
    const strideAmp = THREE.MathUtils.lerp(0.46, 0.66, s);
    const kneeAmp = THREE.MathUtils.lerp(0.58, 0.85, s);
    const sinP = Math.sin(p);
    const cosP = Math.cos(p);

    const thighL = -sinP * strideAmp * m;
    const thighR = sinP * strideAmp * m;
    const shinL = Math.max(0, cosP * kneeAmp) * m + (this.isGrounded ? 0 : 0.35);
    const shinR = Math.max(0, -cosP * kneeAmp) * m + (this.isGrounded ? 0 : 0.2);
    const footL = -thighL * 0.35 - shinL * 0.25;
    const footR = -thighR * 0.35 - shinR * 0.25;

    const stepBob = -Math.abs(sinP) * THREE.MathUtils.lerp(0.025, 0.048, s) * m - this.landingDip;
    const pelvisYaw = cosP * 0.055 * m;
    const pelvisRoll = sinP * 0.035 * m;

    const chestLean = breath * 0.015 + THREE.MathUtils.lerp(0.09, 0.17, s) * m;
    const chestTwist = -pelvisYaw * 1.25;
    const headPitch = idleHeadPitch * (1 - m * 0.6) - chestLean * 0.35;
    const headYaw = idleHeadYaw * (1 - m * 0.75) + pelvisYaw * 0.55;

    // Left arm swings naturally opposite left thigh; right arm holds heavy longsword steadily
    const armSwingL = sinP * THREE.MathUtils.lerp(0.32, 0.52, s) * m;
    const forearmFlexL = -0.18 * m - Math.max(0, -sinP) * 0.22 * m;
    const armSwingR = -sinP * THREE.MathUtils.lerp(0.11, 0.19, s) * m;
    const forearmFlexR = -0.06 * m;

    // Layered cloak + hip lantern secondary motion
    const capeDrag = THREE.MathUtils.lerp(0.24, 0.46, s) * m + Math.abs(wind) * 0.7;
    const capeWave1 = wind + Math.sin(p - 0.5) * 0.08 * m;
    const capeWave2 = Math.sin(elapsed * 2.5 - 0.9) * 0.06 + Math.sin(p - 1.2) * 0.14 * m;
    const capeWave3 = Math.sin(elapsed * 2.5 - 1.7) * 0.08 + Math.sin(p - 1.9) * 0.18 * m;

    const lanternPitch = Math.sin(elapsed * 1.9) * 0.045 + cosP * 0.14 * m;
    const lanternRoll = Math.cos(elapsed * 1.3) * 0.03 + sinP * 0.09 * m;

    this._setBoneCharEuler("Pelvis", 0.0, pelvisYaw, pelvisRoll, stepBob);
    this._setBoneCharEuler("Spine", chestLean * 0.55, chestTwist * 0.5, -pelvisRoll * 0.5);
    this._setBoneCharEuler("Chest", chestLean * 0.45, chestTwist * 0.5, 0);
    this._setBoneCharEuler("Neck", -chestLean * 0.25, headYaw * 0.35, 0);
    this._setBoneCharEuler("Head", headPitch, headYaw * 0.65, 0);

    this._setBoneCharEuler("Thigh_L", thighL, 0, -0.02 * m);
    this._setBoneCharEuler("Shin_L", shinL, 0, 0);
    this._setBoneCharEuler("Foot_L", footL, 0, 0);

    this._setBoneCharEuler("Thigh_R", thighR, 0, 0.02 * m);
    this._setBoneCharEuler("Shin_R", shinR, 0, 0);
    this._setBoneCharEuler("Foot_R", footR, 0, 0);

    this._setBoneCharEuler("UpperArm_L", armSwingL, 0, -0.04 * breath);
    this._setBoneCharEuler("Forearm_L", forearmFlexL, 0, 0);
    this._setBoneCharEuler("UpperArm_R", armSwingR, 0, 0.03 * breath);
    this._setBoneCharEuler("Forearm_R", forearmFlexR, 0, 0);

    this._setBoneCharEuler("Cape_Upper", capeDrag * 0.45 + capeWave1 * 0.5, 0, capeWave1 * 0.25);
    this._setBoneCharEuler("Cape_Mid", capeDrag * 0.4 + capeWave2, 0, capeWave2 * 0.35);
    this._setBoneCharEuler("Cape_Lower", capeDrag * 0.35 + capeWave3, 0, capeWave3 * 0.45);

    this._setBoneCharEuler("Lantern_Swing", lanternPitch, 0, lanternRoll);
  }

  _updateLanternLight(elapsed) {
    if (!this.lanternLight) return;
    const flicker =
      Math.sin(elapsed * 7.3) * 0.12 +
      Math.sin(elapsed * 13.7) * 0.07 +
      Math.cos(elapsed * 4.1) * 0.09;
    this.lanternLight.intensity = Math.max(0.6, this.lanternBaseIntensity * (1.0 + flicker));
  }

  dispose() {
    if (this.lanternLight) {
      this.lanternLight.dispose();
    }
    this.materialLib.dispose();
  }
}
