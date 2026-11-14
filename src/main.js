import "./styles/main.css";
import { SanctuaryViewer } from "./scene/SanctuaryViewer.js";

const canvas = document.getElementById("sanctuary-canvas");
const loaderEl = document.getElementById("loader");
const loaderFill = document.getElementById("loader-fill");
const loaderStatus = document.getElementById("loader-status");
const sceneStats = document.getElementById("scene-stats");

const camButtons = Array.from(document.querySelectorAll("#camera-buttons [data-cam]"));
const btnKnight = document.getElementById("btn-knight");
const btnMood = document.getElementById("btn-mood");
const btnOrbit = document.getElementById("btn-orbit");
const btnWalk = document.getElementById("btn-walk");
const walkHint = document.getElementById("walk-hint");
const btnHideHud = document.getElementById("btn-hide-hud");
const btnShowHud = document.getElementById("btn-show-hud");

const btnCompare = document.getElementById("btn-compare");
const compareModal = document.getElementById("compare-modal");
const btnCloseModal = document.getElementById("btn-close-modal");
const modalBackdrop = document.getElementById("modal-backdrop");

const EXPLORE_HINT =
  "WASD / Arrow keys to move · Q/E down/up · Shift sprint · Drag mouse to look · Press Explore or Esc to exit";
const KNIGHT_HINT =
  "WASD / Arrows: Move Knight · Shift: Sprint · Space: Leap · Drag: Orbit Camera · Scroll: Zoom · K / Esc: Exit";

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
  onLoaded: ({ meshes, triangles }) => {
    loaderFill.style.width = "100%";
    loaderStatus.textContent = "Sanctuary Ready";
    sceneStats.textContent = `${meshes} meshes · ${(triangles / 1000).toFixed(0)}k tris · Drag to orbit · K to play Knight`;
    setTimeout(() => loaderEl.classList.add("gone"), 240);
  },
  onWalkChange: setWalkUI,
  onKnightChange: setKnightUI,
});

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
  const hide = typeof forceHidden === "boolean" ? forceHidden : !document.body.classList.contains("hud-hidden");
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
  } else if (e.key === "Escape" && !compareModal.hidden) {
    openModal(false);
  }
});

viewer.loadModel("/models/drowned_sanctuary.glb").catch((err) => {
  console.error("Failed to load sanctuary GLB:", err);
  loaderStatus.textContent = `Error loading 3D model: ${err?.message || "Unknown error"}`;
});
