"""Placement des pièces par programmation par contraintes (OR-Tools CP-SAT).

Disposition « couloir au milieu » (comme data/examples/residential_floorplan.json) :

    bande B (nord)   chambres, salle de bain...
    couloir          pleine largeur
    bande A (sud)    séjour, cuisine...

Toutes les longueurs du solveur sont des entiers en unités de 2 cm
(0,20 m de façade = 10 unités, 0,12 m de cloison = 6 unités).
Les coordonnées renvoyées ont pour origine le coin sud-ouest de l'intérieur.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from itertools import permutations
from math import sqrt

from ortools.sat.python import cp_model

from common.requirements_schema import Requirements, RoomRequirement

UNIT = 0.02                    # m par unité
EXT_WALL = 10                  # façade 0,20 m
PARTITION = 6                  # cloison 0,12 m
AREA_UNIT = 1 / UNIT ** 2      # unités² par m²
AREA_TOLERANCE = 0.10          # ±10 % autour de target_area
MAX_ASPECT = 3                 # rapport largeur/profondeur maximal d'une pièce

# type: (min_area, target_area, max_area, côté minimal) en m² et m
DEFAULTS = {
    "living": (16, 22, 35, 3.0),
    "kitchen": (8, 13, 20, 2.2),
    "bedroom": (9, 12, 16, 2.6),
    "bathroom": (3.5, 6, 10, 1.6),
}
OTHER_DEFAULT = (6, 10, 20, 2.0)
NIGHT_TYPES = {"bedroom", "bathroom", "wc", "toilet", "dressing", "closet", "suite"}


def u(meters: float) -> int:
    return round(meters / UNIT)


class PlanningError(RuntimeError):
    """Aucune disposition faisable pour ce programme."""


@dataclass
class Spec:
    id: str
    type: str
    min_area: float
    target: float
    max_area: float
    min_w: float
    min_d: float
    pref: str | None = None


@dataclass
class HallSpec:
    id: str
    min_d: float = 1.2
    min_area: float | None = None
    target: float | None = None
    max_area: float | None = None


@dataclass
class Rect:
    id: str
    x: int
    y: int
    w: int
    h: int


@dataclass
class Band:
    y: int
    depth: int
    ids: list[str]
    is_hall: bool = False


@dataclass
class Layout:
    rects: dict[str, Rect]
    bands: list[Band]            # du sud au nord
    width: int
    depth: int
    hall_id: str
    types: dict[str, str]        # ordre = ordre du programme, couloir inclus
    passages: list[tuple[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    status: str = ""
    seconds: float = 0.0


# ---------- programme -> spécifications ----------

def _spec(r: RoomRequirement) -> Spec:
    lo, mid, hi, side = DEFAULTS.get(r.type.lower(), OTHER_DEFAULT)
    min_a = r.min_area or (r.target_area * 0.75 if r.target_area else lo)
    max_a = r.max_area or (r.target_area * 1.3 if r.target_area else hi)
    max_a = max(max_a, min_a)
    min_a = min(min_a, max_a)
    target = r.target_area or min(max(mid, min_a), max_a)
    # Un LLM écrit souvent min = max = cible : surface exacte, rarement réalisable
    # avec des murs. On tolère ±TOLERANCE autour de la cible (on ne resserre jamais).
    min_a = min(min_a, target * (1 - AREA_TOLERANCE))
    max_a = max(max_a, target * (1 + AREA_TOLERANCE))
    side = min(side, 0.8 * sqrt(max_a))
    return Spec(r.id, r.type.lower(), min_a, target, max_a,
                r.min_width or side, r.min_depth or side, r.orientation_preference)


def _specs(req: Requirements) -> tuple[list[Spec], HallSpec]:
    hall: HallSpec | None = None
    specs: list[Spec] = []
    for r in req.rooms:
        if hall is None and r.type.lower() == "corridor":
            hall = HallSpec(r.id, r.min_depth or 1.2, r.min_area, r.target_area, r.max_area)
        else:
            specs.append(_spec(r))
    if not specs:
        raise PlanningError("Le programme ne contient que un couloir.")
    if hall is None:
        hall_id = "hall"
        while hall_id in {r.id for r in req.rooms}:
            hall_id += "_"
        hall = HallSpec(hall_id)
    return specs, hall


# ---------- répartition en bandes et ordre ----------

def _assignments(specs: list[Spec]):
    south, north = [], []
    for s in specs:
        if s.pref in ("S", "SE", "SW"):
            south.append(s)
        elif s.pref in ("N", "NE", "NW"):
            north.append(s)
        elif s.type in NIGHT_TYPES:
            north.append(s)
        else:
            south.append(s)
    if not south and len(north) >= 2:
        south, north = north[: len(north) // 2], north[len(north) // 2:]
    elif not north and len(south) >= 2:
        south, north = south[: len(south) // 2], south[len(south) // 2:]
    primary = (south, north)
    yield primary

    # Variante équilibrée par surface cible, en gardant l'ordre du programme.
    order = {s.id: i for i, s in enumerate(specs)}
    a, b = [], []
    ta = tb = 0.0
    for s in sorted(specs, key=lambda s: -s.target):
        if ta <= tb:
            a.append(s)
            ta += s.target
        else:
            b.append(s)
            tb += s.target
    balanced = (sorted(a, key=lambda s: order[s.id]), sorted(b, key=lambda s: order[s.id]))
    if {s.id for s in balanced[0]} not in ({s.id for s in primary[0]}, {s.id for s in primary[1]}):
        yield balanced


def _weights(req: Requirements) -> dict[frozenset, int]:
    w: dict[frozenset, int] = {}
    for rel in req.relationships:
        key = frozenset(rel.room_ids)
        w[key] = w.get(key, 0) + (10 if rel.strength == "mandatory" else 1)
    return w


def _order(band: list[Spec], weights: dict[frozenset, int]) -> list[Spec]:
    """Ordre gauche-droite qui rapproche le plus de pièces liées par une relation."""
    if len(band) < 2 or len(band) > 7:
        return list(band)
    best, best_score = list(band), -1
    for perm in permutations(band):
        score = sum(weights.get(frozenset((a.id, b.id)), 0) for a, b in zip(perm, perm[1:]))
        if score > best_score:
            best, best_score = list(perm), score
    return best


# ---------- modèle CP-SAT ----------

def _var(model: cp_model.CpModel, lo: int, hi: int, name: str):
    if lo > hi:
        raise PlanningError(f"Contraintes incompatibles pour {name} ({lo} > {hi} unités).")
    return model.NewIntVar(lo, hi, name)


def _solve_once(bands: list[list[Spec]], hall: HallSpec, req: Requirements,
                aspect: bool, timeout: float) -> Layout | None:
    bands = [b for b in bands if b]
    m = cp_model.CpModel()
    max_w = u(req.max_building_width - 2 * EXT_WALL * UNIT) if req.max_building_width else u(18)
    max_d = u(req.max_building_depth - 2 * EXT_WALL * UNIT) if req.max_building_depth else u(14)
    if max_w < u(3) or max_d < u(3):
        raise PlanningError("Enveloppe maximale trop petite.")

    W = m.NewIntVar(u(3), max_w, "W")
    depths, rooms, devs = [], {}, []
    big = 3_000_000

    def deviation(expr, target: int, name: str):
        diff = m.NewIntVar(-big, big, f"diff_{name}")
        m.Add(diff == expr - target)
        dev = m.NewIntVar(0, big, f"dev_{name}")
        m.AddAbsEquality(dev, diff)
        return dev

    for bi, specs in enumerate(bands):
        d = _var(m, u(max(s.min_d for s in specs)), max_d, f"d{bi}")
        depths.append(d)
        widths = []
        for s in specs:
            w = _var(m, u(s.min_w), max_w, f"w_{s.id}")
            a = _var(m, round(s.min_area * AREA_UNIT), round(s.max_area * AREA_UNIT), f"a_{s.id}")
            m.AddMultiplicationEquality(a, [w, d])
            if aspect:
                m.Add(w <= MAX_ASPECT * d)
                m.Add(d <= MAX_ASPECT * w)
            devs.append(deviation(a, round(s.target * AREA_UNIT), s.id))
            widths.append(w)
            rooms[s.id] = w
        m.Add(sum(widths) + PARTITION * (len(widths) - 1) == W)

    dh_lo = u(hall.min_d)
    dH = _var(m, dh_lo, max(u(2.0), dh_lo), "dH")
    a_lo = round(hall.min_area * AREA_UNIT) if hall.min_area else 0
    a_hi = round(hall.max_area * AREA_UNIT) if hall.max_area else max_w * max(u(2.0), dh_lo)
    ah = _var(m, a_lo, a_hi, "a_hall")
    m.AddMultiplicationEquality(ah, [W, dH])
    if hall.target:
        devs.append(deviation(ah, round(hall.target * AREA_UNIT), "hall"))

    D = m.NewIntVar(0, max_d, "D")
    m.Add(D == sum(depths) + dH + PARTITION * len(bands))   # len(bands)+1 bandes -> len(bands) cloisons
    ow = m.NewIntVar(0, max_w + 2 * EXT_WALL, "ow")
    od = m.NewIntVar(0, max_d + 2 * EXT_WALL, "od")
    m.Add(ow == W + 2 * EXT_WALL)
    m.Add(od == D + 2 * EXT_WALL)
    gross = m.NewIntVar(0, (max_w + 2 * EXT_WALL) * (max_d + 2 * EXT_WALL), "gross")
    m.AddMultiplicationEquality(gross, [ow, od])
    gross_dev = deviation(gross, round(req.target_total_area * AREA_UNIT), "gross")

    m.Minimize(sum(devs) + 2 * gross_dev)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timeout
    solver.parameters.num_workers = 4
    solver.parameters.random_seed = 1
    status = solver.Solve(m)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    # Bandes du sud au nord : pièces A, couloir, pièces B.
    rects: dict[str, Rect] = {}
    stack: list[Band] = []
    y = 0
    sequence: list[tuple[str, int]] = []
    if len(bands) >= 1:
        sequence.append(("rooms", 0))
    sequence.append(("hall", -1))
    if len(bands) >= 2:
        sequence.append(("rooms", 1))
    for i, (kind, bi) in enumerate(sequence):
        if kind == "hall":
            depth = solver.Value(dH)
            rects[hall.id] = Rect(hall.id, 0, y, solver.Value(W), depth)
            stack.append(Band(y, depth, [hall.id], True))
        else:
            depth = solver.Value(depths[bi])
            x = 0
            for s in bands[bi]:
                w = solver.Value(rooms[s.id])
                rects[s.id] = Rect(s.id, x, y, w, depth)
                x += w + PARTITION
            stack.append(Band(y, depth, [s.id for s in bands[bi]]))
        y += depth + PARTITION
    name = "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE"
    return Layout(rects, stack, solver.Value(W), solver.Value(D), hall.id, {},
                  status=name, seconds=round(solver.WallTime(), 3))


def solve(req: Requirements, timeout: float | None = None) -> Layout:
    """Programme -> disposition. Lève PlanningError si rien de faisable."""
    timeout = timeout or float(os.getenv("ARCHIGEN_SOLVER_TIMEOUT", "10"))
    specs, hall = _specs(req)
    weights = _weights(req)
    layout = None
    for south, north in _assignments(specs):
        bands = [_order(south, weights), _order(north, weights)]
        for aspect in (True, False):
            layout = _solve_once(bands, hall, req, aspect, timeout)
            if layout:
                break
        if layout:
            break
    if layout is None:
        raise PlanningError(
            "Aucune disposition faisable : assouplir les surfaces, les dimensions "
            "minimales ou la taille maximale du bâtiment.")

    layout.types = {r.id: r.type.lower() for r in req.rooms}
    if hall.id not in layout.types:
        layout.types[hall.id] = "corridor"
    _relations(layout, req)
    return layout


def _relations(layout: Layout, req: Requirements) -> None:
    """Passages entre voisins (open_space) et relations impossibles à satisfaire."""
    neighbours: set[frozenset] = set()
    for band in layout.bands:
        if not band.is_hall:
            neighbours.update(frozenset(p) for p in zip(band.ids, band.ids[1:]))
    for rel in req.relationships:
        a, b = rel.room_ids
        if layout.hall_id in (a, b):
            continue
        if frozenset((a, b)) in neighbours:
            if rel.kind == "open_space" and (a, b) not in layout.passages and (b, a) not in layout.passages:
                layout.passages.append((a, b))
        else:
            layout.notes.append(f"Relation {rel.kind} {a}-{b} non satisfaite ({rel.strength}).")