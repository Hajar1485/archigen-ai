// Interface ArchiGen AI : parcours plan -> thermique. Aucune donnée n'est injectée via innerHTML.
const $ = (id) => document.getElementById(id);
const SVGNS = "http://www.w3.org/2000/svg";
let currentPlan = null;

function el(tag, attrs = {}, text) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text !== undefined) e.textContent = text;
  return e;
}

// ---------- appels API & erreurs ----------
async function api(path, options = {}) {
  let resp;
  try {
    resp = await fetch(path, options);
  } catch {
    throw new Error("Serveur injoignable. Vérifiez que l'API est lancée.");
  }
  let body = null;
  try { body = await resp.json(); } catch { /* corps non JSON */ }
  if (!resp.ok) {
    const err = body?.error;
    let msg = err?.message || body?.detail || `Erreur ${resp.status}`;
    if (err?.details?.length) msg += " — " + err.details.map((d) => `${d.field || d.loc || ""} ${d.message || d.msg || ""}`).join("; ");
    if (err?.fallback) msg += " (" + err.fallback + ")";
    throw new Error(msg);
  }
  return body;
}

function showError(msg) { const b = $("error"); b.textContent = msg; b.hidden = !msg; }

async function guarded(button, fn) {
  showError("");
  if (button) button.disabled = true;
  try { await fn(); } catch (e) { showError(e.message); } finally { if (button) button.disabled = false; }
}

const postJSON = (path, data) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });

// ---------- onglets & statut ----------
$("tabs").addEventListener("click", (e) => {
  const tab = e.target.dataset?.tab;
  if (!tab) return;
  document.querySelectorAll("nav button").forEach((b) => b.classList.toggle("active", b === e.target));
  document.querySelectorAll(".tab").forEach((s) => (s.hidden = s.id !== "tab-" + tab));
  showError("");
  if (tab === "quality") loadMetrics();
});

async function loadStatus() {
  const box = $("status");
  box.replaceChildren();
  try {
    const h = await api("/api/health");
    const add = (label, ok) => box.append(el("span", { class: "pill " + (ok ? "ok" : "ko") }, `${label} : ${ok ? "OK" : "indisponible"}`));
    add("Thermique", h.thermal_model_trained);
    add("Génération", h.modules.planner.available);
    add("Import", h.modules.plan_import.available);
  } catch (e) { box.append(el("span", { class: "pill ko" }, "API hors ligne")); }
}

// ---------- plan : chargement et rendu 2D ----------
function setPlan(plan) {
  currentPlan = plan;
  $("plan-json").value = JSON.stringify(plan, null, 2);
  renderPlan(plan);
  const area = plan.rooms.reduce((s, r) => s + r.w * r.h, 0);
  $("plan-info").textContent = `${plan.rooms.length} pièces, ${plan.walls.length} murs, ${plan.openings.length} ouvertures — ${area.toFixed(1)} m² au total`;
  document.dispatchEvent(new CustomEvent("plan-changed", { detail: plan })); // point d'accroche pour la 3D (Personne 2)
}

function renderPlan(plan) {
  const xs = plan.rooms.flatMap((r) => [r.x, r.x + r.w]);
  const ys = plan.rooms.flatMap((r) => [r.y, r.y + r.h]);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const m = 1;
  const svg = document.createElementNS(SVGNS, "svg");
  svg.setAttribute("viewBox", `${x0 - m} ${-(y1 + m)} ${x1 - x0 + 2 * m} ${y1 - y0 + 2 * m}`); // y inversé : nord en haut
  const add = (tag, attrs, text) => {
    const n = document.createElementNS(SVGNS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (text !== undefined) n.textContent = text;
    svg.append(n);
  };
  for (const r of plan.rooms) {
    add("rect", { x: r.x, y: -(r.y + r.h), width: r.w, height: r.h, fill: "#e9f0fb", stroke: "#8aa0c4", "stroke-width": 0.05 });
    add("text", { x: r.x + r.w / 2, y: -(r.y + r.h / 2), "font-size": 0.45, "text-anchor": "middle" }, r.name || r.id);
  }
  const walls = Object.fromEntries(plan.walls.map((w) => [w.id, w]));
  for (const w of plan.walls)
    add("line", { x1: w.x1, y1: -w.y1, x2: w.x2, y2: -w.y2, stroke: "#1d2330", "stroke-width": w.thickness });
  for (const o of plan.openings) {
    const w = walls[o.wall_id]; if (!w) continue;
    const L = Math.hypot(w.x2 - w.x1, w.y2 - w.y1) || 1;
    const ux = (w.x2 - w.x1) / L, uy = (w.y2 - w.y1) / L;
    const a = [w.x1 + ux * o.offset, w.y1 + uy * o.offset];
    const b = [a[0] + ux * o.width, a[1] + uy * o.width];
    add("line", { x1: a[0], y1: -a[1], x2: b[0], y2: -b[1], stroke: o.kind === "window" ? "#2aa7e0" : "#d9822b", "stroke-width": w.thickness * 0.7 });
  }
  add("text", { x: x1 + m * 0.6, y: -(y1 + m * 0.4), "font-size": 0.6, "text-anchor": "end" }, "N ↑");
  $("plan-view").replaceChildren(svg);
}

function readPlanField() {
  try { return JSON.parse($("plan-json").value); }
  catch { throw new Error("JSON invalide : vérifiez la syntaxe du plan."); }
}

$("btn-example").onclick = (e) => guarded(e.target, async () => setPlan(await api("/api/plan/example")));
$("btn-validate").onclick = (e) => guarded(e.target, async () => {
  const plan = readPlanField();
  await postJSON("/api/plan/validate", plan);
  setPlan(plan);
});
$("btn-generate").onclick = (e) => guarded(e.target, async () => {
  const r = await postJSON("/api/plan/generate", { text: $("nl-text").value });
  setPlan(r.plan);
});
$("btn-import").onclick = (e) => guarded(e.target, async () => {
  const f = $("img-file").files[0];
  if (!f) throw new Error("Choisissez d'abord une image de plan.");
  const fd = new FormData();
  fd.append("image", f);
  if ($("img-dim").value) fd.append("known_dimension_m", $("img-dim").value);
  const r = await api("/api/plan/import", { method: "POST", body: fd });
  setPlan(r.plan);
});

// ---------- thermique ----------
const UNITS = { Relative_Compactness: "", Surface_Area: "m²", Wall_Area: "m²", Roof_Area: "m²", Overall_Height: "m", Glazing_Area: "ratio vitrage/sol" };

function renderThermal(target, r) {
  const wrap = el("div");
  const res = el("div", { class: "results" });
  for (const [label, v] of [["Chauffage", r.heating_load], ["Refroidissement", r.cooling_load]]) {
    const m = el("div", { class: "metric" });
    m.append(el("div", {}, label), el("div", { class: "v" }, v.toFixed(1)), el("div", { class: "u" }, r.unit));
    res.append(m);
  }
  wrap.append(res);
  if (r.warnings?.length) {
    const ul = el("ul", { class: "warnings" });
    r.warnings.forEach((w) => ul.append(el("li", {}, w)));
    wrap.append(ul);
  }
  const t = el("table");
  t.append(el("tr", {}, ""));
  t.firstChild.replaceChildren(el("th", {}, "Variable UCI"), el("th", {}, "Valeur"));
  for (const [k, v] of Object.entries(r.features)) {
    const tr = el("tr"); tr.append(el("td", {}, k), el("td", {}, String(v))); t.append(tr);
  }
  wrap.append(t, el("p", { class: "muted" }, r.disclaimer));
  $(target).replaceChildren(wrap);
}

$("btn-thermal-plan").onclick = (e) => guarded(e.target, async () => {
  if (!currentPlan) throw new Error("Chargez ou générez d'abord un plan (onglet 1).");
  renderThermal("thermal-result", await postJSON("/api/thermal/predict-plan", currentPlan));
});

const DEFAULTS = { Relative_Compactness: 0.76, Surface_Area: 661.5, Wall_Area: 416.5, Roof_Area: 122.5, Overall_Height: 7, Orientation: 3, Glazing_Area: 0.25, Glazing_Area_Distribution: 1 };
function buildManualForm() {
  const form = $("manual-form");
  for (const [k, v] of Object.entries(DEFAULTS)) {
    const wrap = el("div");
    wrap.append(el("label", { for: "f-" + k }, k + (UNITS[k] ? ` (${UNITS[k]})` : "")));
    const i = el("input", { id: "f-" + k, type: "number", step: "any", value: v, name: k });
    wrap.append(i); form.append(wrap);
  }
}
$("btn-manual").onclick = (e) => guarded(e.target, async () => {
  const data = {};
  for (const k of Object.keys(DEFAULTS)) {
    const v = $("f-" + k).value;
    if (v === "") throw new Error(`Champ vide : ${k}`);
    data[k] = Number(v);
  }
  renderThermal("manual-result", await postJSON("/api/thermal/predict", data));
});

// ---------- qualité du modèle ----------
async function loadMetrics() {
  await guarded(null, async () => {
    const m = await api("/api/thermal/metrics");
    const box = el("div");
    box.append(el("p", { class: "muted" }, `${m.dataset.rows_out} lignes utilisées, ${m.dataset.duplicates} doublons. Test : ${m.split.test_shapes} formes jamais vues (${m.split.test_rows} lignes).`));
    for (const [target, d] of Object.entries(m.targets)) {
      box.append(el("h2", {}, `${target} — modèle retenu : ${d.selected}`));
      const t = el("table");
      const head = el("tr"); ["Modèle", "MAE (CV par forme)", "R² (CV par forme)", "MAE (formes inconnues)", "MAE (split aléatoire)", "R² (split aléatoire)"].forEach((h) => head.append(el("th", {}, h)));
      t.append(head);
      for (const [name, r] of Object.entries(d.candidates)) {
        const tr = el("tr", name === d.selected ? { class: "sel" } : {});
        [name, r.cv_by_shape.mae, r.cv_by_shape.r2, r.test_unseen_shapes.mae, r.test_random_split.mae, r.test_random_split.r2]
          .forEach((v) => tr.append(el("td", {}, typeof v === "number" ? v.toFixed(2) : v)));
        t.append(tr);
      }
      box.append(t);
    }
    box.append(el("p", { class: "muted" }, m.note));
    $("metrics").replaceChildren(box);
  });
}

buildManualForm();
loadStatus();
