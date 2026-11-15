import "./styles/main.css";
import { SanctuaryViewer } from "./scene/SanctuaryViewer.js";
import { MODEL_URLS } from "./scene/config.js";

const canvas = document.getElementById("sanctuary-canvas");
const loaderEl = document.getElementById("loader");
const loaderFill = document.getElementById("loader-fill");
const loaderStatus = document.getElementById("loader-status");
const sceneStats = document.getElementById("scene-stats");
const perfStats = document.getElementById("perf-stats");

const camButtons = Array.from(document.querySelectorAll("#camera-buttons [data-cam]"));
const btnKnight = document.getElementById("btn-knight");
const btnMood = document.getElementById("btn-mood");
const btnQuality = document.getElementById("btn-quality");
const btnOrbit = document.getElementById("btn-orbit");
const btnWalk = document.getElementById("btn-walk");
const walkHint = document.getElementById("walk-hint");
const btnHideHud = document.getElementById("btn-hide-hud");
const btnShowHud = document.getElementById("btn-show-hud");

const mobileControls = document.getElementById("mobile-controls");
const touchJoystick = document.getElementById("touch-joystick");
const touchKnob = document.getElementById("touch-knob");
const touchBtnJump = document.getElementById("touch-btn-jump");
const touchBtnSprint = document.getElementById("touch-btn-sprint");
const touchBtnSword = document.getElementById("touch-btn-sword");

const btnCompare = document.getElementById("btn-compare");
const compareModal = document.getElementById("compare-modal");
const btnCloseModal = document.getElementById("btn-close-modal");
const modalBackdrop = document.getElementById("modal-backdrop");

const EXPLORE_HINT =
  "WASD / Arrow keys to move · Q/E down/up · Shift sprint · Drag mouse to look · Press Explore or Esc to exit";
const KNIGHT_HINT =
  "WASD / Arrows: Move · Shift: Sprint · Space: Leap · E: Guard Stance · Drag: Orbit · Scroll: Zoom · K / Esc: Exit";

function updateTouchModeClass() {
  const coarse = window.matchMedia?.("(pointer: coarse)")?.matches || "ontouchstart" in window;
  document.body.classList.toggle("touch-ui", Boolean(coarse || window.innerWidth <= 820));
}
updateTouchModeClass();
window.addEventListener("resize", updateTouchModeClass);

function setWalkUI(active) {
  btnWalk.classList.toggle("active", active);
  btnWalk.textContent = active ? "Exit Explore" : "Explore";
  if (active) {
    walkHint.textContent = EXPLORE_HINT;
  }
  walkHint.hidden = !(active || viewer?.knightMode);
}

function setKnightUI(active) {
  btnKnight.classList.toggle("active", active);
  btnKnight.textContent = active ? "Exit Knight" : "Play Knight";
  document.body.classList.toggle("knight-active", active);
  if (mobileControls) {
    mobileControls.hidden = !active;
  }
  if (!active) {
    viewer?.setVirtualInput({ moveX: 0, moveY: 0, jump: false, swordReady: false });
  }
  if (active) {
    walkHint.textContent = KNIGHT_HINT;
  }
  walkHint.hidden = !(active || viewer?.walkMode);
}

const viewer = new SanctuaryViewer(canvas, {
  onProgress: (ratio) => {
    const pct = Math.round(ratio * 100);
    loaderFill.style.width = `${pct}%`;
    loaderStatus.textContent = `Streaming Sanctuary Geometry… ${pct}%`;
  },
  onLoaded: ({ meshes, triangles, quality }) => {
    loaderFill.style.width = "100%";
    loaderStatus.textContent = "Sanctuary Ready";
    sceneStats.textContent = `${meshes} meshes · ${(triangles / 1000).toFixed(0)}k tris · Drag to orbit · K to play Knight`;
    if (quality && btnQuality) {
      btnQuality.textContent = `Quality: ${quality.label}`;
    }
    setTimeout(() => loaderEl.classList.add("gone"), 240);
  },
  onQualityChange: (preset) => {
    if (btnQuality && preset) {
      btnQuality.textContent = `Quality: ${preset.label}`;
    }
  },
  onPerfStats: (perf) => {
    if (!perfStats) return;
    const qLabel = viewer.getQualityPreset().label;
    perfStats.textContent = `AgX · ${qLabel} · ${perf.fps} FPS (${perf.frameMs}ms) · ${perf.calls} draws`;
  },
  onWalkChange: setWalkUI,
  onKnightChange: setKnightUI,
});

const initialPreset = viewer.getQualityPreset();
if (btnQuality && initialPreset) {
  btnQuality.textContent = `Quality: ${initialPreset.label}`;
}

for (const btn of camButtons) {
  btn.addEventListener("click", () => {
    camButtons.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    viewer.flyToPreset(btn.dataset.cam);
  });
}

btnKnight.addEventListener("click", () => {
  const next = !viewer.knightMode;
  viewer.setKnightMode(next);
  setKnightUI(next);
});

btnMood.addEventListener("click", () => {
  const mood = viewer.cycleMood();
  btnMood.textContent = mood.label;
});

btnQuality?.addEventListener("click", () => {
  const preset = viewer.cycleQuality();
  btnQuality.textContent = `Quality: ${preset.label}`;
});

let orbitOn = false;
btnOrbit.addEventListener("click", () => {
  orbitOn = !orbitOn;
  viewer.setAutoOrbit(orbitOn);
  btnOrbit.classList.toggle("active", orbitOn);
  btnOrbit.textContent = orbitOn ? "Orbit: On" : "Orbit: Off";
});

btnWalk.addEventListener("click", () => {
  const next = !viewer.walkMode;
  viewer.setWalkMode(next);
  setWalkUI(next);
});

function toggleHud(forceHidden) {
  const hide =
    typeof forceHidden === "boolean" ? forceHidden : !document.body.classList.contains("hud-hidden");
  document.body.classList.toggle("hud-hidden", hide);
}

btnHideHud.addEventListener("click", () => toggleHud(true));
btnShowHud.addEventListener("click", () => toggleHud(false));

function openModal(open) {
  compareModal.hidden = !open;
}
btnCompare.addEventListener("click", () => openModal(true));
btnCloseModal.addEventListener("click", () => openModal(false));
modalBackdrop.addEventListener("click", () => openModal(false));

window.addEventListener("keydown", (e) => {
  if (e.key === "h" || e.key === "H") {
    toggleHud();
  } else if (e.key === "k" || e.key === "K") {
    if (!compareModal.hidden) return;
    const next = !viewer.knightMode;
    viewer.setKnightMode(next);
    setKnightUI(next);
  } else if ((e.key === "q" || e.key === "Q") && !viewer.walkMode) {
    if (!compareModal.hidden) return;
    const preset = viewer.cycleQuality();
    if (btnQuality) btnQuality.textContent = `Quality: ${preset.label}`;
  } else if (e.key === "Escape" && !compareModal.hidden) {
    openModal(false);
  }
});

// Touch virtual joystick + Knight action buttons
if (touchJoystick && touchKnob) {
  let stickPointerId = null;
  const maxRadius = 38;

  const updateStick = (clientX, clientY) => {
    const rect = touchJoystick.getBoundingClientRect();
    const cx = rect.left + rect.width * 0.5;
    const cy = rect.top + rect.height * 0.5;
    let dx = clientX - cx;
    let dy = clientY - cy;
    const dist = Math.hypot(dx, dy);
    if (dist > maxRadius) {
      dx = (dx / dist) * maxRadius;
      dy = (dy / dist) * maxRadius;
    }
    touchKnob.style.transform = `translate3d(${dx.toFixed(1)}px, ${dy.toFixed(1)}px, 0)`;
    viewer.setVirtualInput({
      moveX: Math.abs(dx) < 5 ? 0 : dx / maxRadius,
      moveY: Math.abs(dy) < 5 ? 0 : dy / maxRadius,
    });
  };

  const resetStick = () => {
    stickPointerId = null;
    touchKnob.style.transform = "translate3d(0px, 0px, 0)";
    viewer.setVirtualInput({ moveX: 0, moveY: 0 });
  };

  touchJoystick.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    stickPointerId = e.pointerId;
    touchJoystick.setPointerCapture?.(e.pointerId);
    updateStick(e.clientX, e.clientY);
  });
  touchJoystick.addEventListener("pointermove", (e) => {
    if (e.pointerId === stickPointerId) {
      updateStick(e.clientX, e.clientY);
    }
  });
  touchJoystick.addEventListener("pointerup", (e) => {
    if (e.pointerId === stickPointerId) resetStick();
  });
  touchJoystick.addEventListener("pointercancel", (e) => {
    if (e.pointerId === stickPointerId) resetStick();
  });
}

if (touchBtnJump) {
  touchBtnJump.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    viewer.setVirtualInput({ jump: true });
    touchBtnJump.classList.add("active");
  });
  const endJump = () => {
    viewer.setVirtualInput({ jump: false });
    touchBtnJump.classList.remove("active");
  };
  touchBtnJump.addEventListener("pointerup", endJump);
  touchBtnJump.addEventListener("pointercancel", endJump);
}

if (touchBtnSword) {
  touchBtnSword.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    viewer.setVirtualInput({ swordReady: true });
    touchBtnSword.classList.add("active");
  });
  const endSword = () => {
    viewer.setVirtualInput({ swordReady: false });
    touchBtnSword.classList.remove("active");
  };
  touchBtnSword.addEventListener("pointerup", endSword);
  touchBtnSword.addEventListener("pointercancel", endSword);
}

if (touchBtnSprint) {
  let mobileSprint = false;
  touchBtnSprint.addEventListener("click", () => {
    mobileSprint = !mobileSprint;
    touchBtnSprint.classList.toggle("active", mobileSprint);
    viewer.setVirtualInput({ sprint: mobileSprint });
  });
}

viewer.loadModel(MODEL_URLS.sanctuary, MODEL_URLS.knight).catch((err) => {
  console.error("Failed to load sanctuary GLB:", err);
  loaderStatus.textContent = `Error loading 3D model: ${err?.message || "Unknown error"}`;
});
