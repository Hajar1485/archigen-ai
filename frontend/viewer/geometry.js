// Géométrie métrique indépendante de Three.js. Les intervalles sont mesurés depuis (x1,y1).
export const EPS = 1e-6;
export const SLAB = 0.08; // support graphique sous le sol fini
export const toWorld = (x, y, height) => [x, height, -y];

function requireGeometry(ok, message) {
  if (!ok) throw new Error(message);
}
const positive = n => Number.isFinite(n) && n > 0;

export function wallFrame(wall) {
  const dx = wall.x2 - wall.x1, dy = wall.y2 - wall.y1;
  const length = Math.hypot(dx, dy);
  requireGeometry([wall.x1, wall.x2, wall.y1, wall.y2].every(Number.isFinite) && length > EPS,
    "Axe de mur invalide : " + wall.id);
  return { length, ux: dx / length, uy: dy / length, angle: Math.atan2(dy, dx) };
}

// Partition du rectangle [start,end] × [0,height]. Deux fenêtres superposées
// en plan peuvent être disjointes en altitude.
export function solidBands(start, end, height, openings) {
  const cuts = new Set([start, end]);
  for (const o of openings) {
    cuts.add(Math.max(start, Math.min(end, o.offset)));
    cuts.add(Math.max(start, Math.min(end, o.offset + o.width)));
  }
  const edges = [...cuts].sort((a, b) => a - b);
  const solids = [];
  for (let i = 1; i < edges.length; i++) {
    const a = edges[i - 1], b = edges[i], mid = (a + b) / 2;
    if (b <= a) continue;
    const holes = openings.filter(o => o.offset < mid && mid < o.offset + o.width)
      .sort((u, v) => u.sill - v.sill);
    let bottom = 0;
    for (const hole of holes) {
      const sill = Math.min(height, hole.sill);
      if (sill > bottom) solids.push({ a, b, bottom, top: sill });
      bottom = Math.max(bottom, hole.sill + hole.height);
    }
    if (bottom < height) solids.push({ a, b, bottom, top: height });
  }
  return solids;
}

function axisOf(w) {
  if (Math.abs(w.y2 - w.y1) <= EPS) return "x";
  if (Math.abs(w.x2 - w.x1) <= EPS) return "y";
  return null;
}

// Raccord bout à face : en L, le mur X ferme l'angle et le mur Y s'y arrête.
// En T, la paroi traversante garde sa longueur. Les cotes des baies restent
// mesurées depuis les extrémités contractuelles, même si le parement déborde.
function endAllowance(wall, walls, x, y, atStart) {
  const axis = axisOf(wall);
  if (!axis) return 0;
  for (const other of walls) {
    const otherAxis = axisOf(other);
    if (!otherAxis || otherAxis === axis) continue;
    const rx = x - other.x1, ry = y - other.y1;
    const s = rx * other.ux + ry * other.uy;
    if (Math.abs(rx * other.uy - ry * other.ux) > EPS || s < -EPS || s > other.length + EPS) continue;
    const nearEnd = s <= EPS || s >= other.length - EPS;
    const half = other.thickness / 2;
    const intersectsBay = wall.openings.some(o => atStart ? o.offset < half :
      o.offset + o.width > wall.length - half);
    if (intersectsBay || other.openings.some(o => s + wall.thickness / 2 > o.offset &&
        s - wall.thickness / 2 < o.offset + o.width)) return 0;
    return nearEnd && axis === "x" ? half : -half;
  }
  return 0;
}

export function preparePlan(plan) {
  requireGeometry(plan && (plan.unit ?? "m") === "m" && Array.isArray(plan.rooms) && plan.rooms.length,
    "Un plan métrique contenant au moins une pièce est requis.");
  if (plan.source === "imported") {
    requireGeometry(plan.import_metadata?.scale_status === "calibrated" &&
      positive(plan.import_metadata.meters_per_pixel) && plan.import_metadata.scale_provenance?.trim(),
    "Calibrez l’image avant de construire la maquette métrique.");
  }
  const height = plan.wall_height ?? 2.7;
  requireGeometry(positive(height), "Hauteur des murs invalide.");
  const floors = plan.rooms.map(r => {
    requireGeometry([r.x, r.y].every(Number.isFinite) && positive(r.w) && positive(r.h), "Pièce invalide : " + r.id);
    return { id: r.id, name: r.name || r.id, type: r.type, area: r.w * r.h,
      position: toWorld(r.x + r.w / 2, r.y + r.h / 2, -SLAB / 2), size: [r.w, SLAB, r.h] };
  });
  const walls = (plan.walls ?? []).map(w => {
    const thickness = w.thickness ?? 0.2;
    requireGeometry(positive(thickness), "Épaisseur invalide : " + w.id);
    return { ...w, ...wallFrame(w), thickness, openings: [] };
  });
  const byId = new Map(walls.map(w => [w.id, w]));
  requireGeometry(byId.size === walls.length, "Identifiants de murs dupliqués.");
  for (const raw of plan.openings ?? []) {
    const wall = byId.get(raw.wall_id);
    const window = raw.kind === "window";
    const o = { ...raw, height: raw.height ?? (window ? 1.2 : 2.1), sill: raw.sill ?? (window ? 0.9 : 0) };
    requireGeometry(wall && Number.isFinite(o.offset) && o.offset >= 0 && positive(o.width) &&
      Number.isFinite(o.sill) && o.sill >= 0 && positive(o.height) && o.offset + o.width <= wall.length + EPS &&
      o.sill + o.height <= height + EPS, "Baie incompatible avec son mur : " + o.id);
    wall.openings.push(o);
  }
  for (const w of walls) {
    w.start = -endAllowance(w, walls, w.x1, w.y1, true);
    w.end = w.length + endAllowance(w, walls, w.x2, w.y2, false);
    if (w.end <= w.start) { w.start = 0; w.end = w.length; }
  }
  return { floors, walls, height };
}

export function boxOnWall(wall, a, b, bottom, top, depth = wall.thickness) {
  const s = (a + b) / 2;
  return { size: [b - a, top - bottom, depth], angle: wall.angle,
    position: toWorld(wall.x1 + s * wall.ux, wall.y1 + s * wall.uy, (bottom + top) / 2) };
}
