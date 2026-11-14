import "./styles/main.css";
import { SanctuaryViewer } from "./scene/SanctuaryViewer.js";

const canvas = document.getElementById("sanctuary-canvas");
const loaderEl = document.getElementById("loader");
const loaderFill = document.getElementById("loader-fill");
const loaderStatus = document.getElementById("loader-status");
const sceneStats = document.getElementById("scene-stats");

const camButtons = Array.from(document.querySelectorAll("#camera-buttons [data-cam]"));
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

function setWalkUI(active) {
  btnWalk.classList.toggle("active", active);
  btnWalk.textContent = active ? "Exit Explore" : "Explore";
  walkHint.hidden = !active;
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
    sceneStats.textContent = `${meshes} meshes · ${(triangles / 1000).toFixed(0)}k tris · Drag to orbit · Scroll to zoom`;
    setTimeout(() => loaderEl.classList.add("gone"), 240);
  },
  onWalkChange: setWalkUI,
});

for (const btn of camButtons) {
  btn.addEventListener("click", () => {
    camButtons.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    viewer.flyToPreset(btn.dataset.cam);
  });
}

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
  } else if (e.key === "Escape" && !compareModal.hidden) {
    openModal(false);
  }
});

viewer.loadModel("/models/drowned_sanctuary.glb").catch((err) => {
  console.error("Failed to load sanctuary GLB:", err);
  loaderStatus.textContent = `Error loading 3D model: ${err?.message || "Unknown error"}`;
});
