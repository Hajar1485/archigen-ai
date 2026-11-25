import { preparePlan } from "./geometry.js";

export function connectViewer(root) {
  const host = root.querySelector(".scene-host");
  const message = root.querySelector("[role=status]");
  const retry = root.querySelector("[data-retry]");
  const roomInfo = root.querySelector("[data-room]");
  const controls = root.querySelector("fieldset");
  const signal = new AbortController();
  let scene, latest, revision = 0;
  const state = { exterior: true, interior: true, floors: true, grid: true, cut: false };
  function fail(text) {
    scene?.dispose();
    scene = null;
    root.dataset.state = "error";
    message.textContent = text;
    controls.disabled = true;
    retry.hidden = false;
  }
  async function load(plan) {
    const id = ++revision;
    latest = plan;
    roomInfo.textContent = "";
    root.dataset.state = "loading";
    message.textContent = "Construction de la maquette…";
    controls.disabled = true;
    retry.hidden = true;
    try {
      const geometry = preparePlan(plan);
      const {PlanScene} = await import("./scene.js");
      if (id !== revision) return;
      scene ??= new PlanScene(host, room => {
        roomInfo.textContent = room ? room.name + " · " + room.area.toLocaleString("fr-FR",{maximumFractionDigits:2}) + " m²" : "";
      }, () => fail("Le contexte graphique a été interrompu. Vous pouvez relancer la vue 3D."));
      scene.load(geometry,state);
      root.dataset.state = "ready";
      message.textContent = geometry.walls.length ? "" : "Ce plan décrit uniquement les sols. Aucun mur fourni.";
      controls.disabled = false;
    } catch (e) {
      if (id !== revision) return;
      const text = /webgl/i.test(e.message) ? "WebGL 2 est indisponible. Vérifiez l’accélération graphique du navigateur." :
        /module|fetch|import/i.test(e.message) ? "Ressources 3D indisponibles. Préparez les fichiers locaux avec le lanceur." : e.message;
      fail(text + " L’aperçu 2D reste disponible.");
    }
  }
  document.addEventListener("plan-changed", e => load(e.detail), {signal:signal.signal});
  root.addEventListener("click",e => {
    if (e.target.closest("[data-retry]")) load(latest);
    const preset = e.target.closest("[data-view]")?.dataset.view;
    if (scene && preset) scene.view(preset === "reset" ? "iso" : preset);
  },{signal:signal.signal});
  root.addEventListener("change", e => {
    const key = e.target.dataset.layer;
    if (!Object.hasOwn(state,key)) return;
    state[key] = e.target.checked;
    roomInfo.textContent = "";
    scene?.display(state);
  },{signal:signal.signal});
  return () => { revision++; signal.abort(); scene?.dispose(); };
}
