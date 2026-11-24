"""Calcule les 8 variables UCI à partir du JSON commun (Plan)."""
from __future__ import annotations

import math

from shapely.geometry import box
from shapely.ops import unary_union

from common.schema import Plan
from .data import FEATURES

# UCI : 2 = nord, 3 = est, 4 = sud, 5 = ouest ; répartition du vitrage : 0 aucun, 1 uniforme, 2..5 = N/E/S/O
CARDINAL_CODE = {"N": 2, "E": 3, "S": 4, "W": 5}


def _cardinal(dx: float, dy: float, north_angle_deg: float) -> str:
    """Point cardinal réel de la normale sortante (dx, dy) exprimée dans le repère du plan."""
    bearing = (math.degrees(math.atan2(dx, dy)) + north_angle_deg) % 360  # +y -> 0°, +x -> 90°
    return "NESW"[int(((bearing + 45) % 360) // 90)]


def _normal(x1, y1, x2, y2, mx, my) -> tuple[float, float]:
    """Normale sortante d'un segment axial, par rapport au centroïde (mx, my relatifs)."""
    if abs(x2 - x1) >= abs(y2 - y1):
        return 0.0, (1.0 if my >= 0 else -1.0)
    return (1.0 if mx >= 0 else -1.0), 0.0


def features_from_plan(plan: Plan) -> tuple[dict[str, float], dict]:
    """Renvoie (features UCI, détails du calcul pour affichage/traçabilité)."""
    footprint = unary_union([box(r.x, r.y, r.x + r.w, r.y + r.h) for r in plan.rooms])
    if footprint.geom_type != "Polygon":
        footprint = footprint.convex_hull  # pièces disjointes : enveloppe (approximation)
    roof = footprint.area
    perimeter = footprint.exterior.length
    H = plan.wall_height
    wall_area = perimeter * H
    surface = wall_area + 2 * roof          # convention UCI : murs + 2 x toit
    volume = roof * H
    compactness = 6 * volume ** (2 / 3) / surface
    cx, cy = footprint.centroid.x, footprint.centroid.y

    facade_len = {"N": 0.0, "E": 0.0, "S": 0.0, "W": 0.0}
    coords = list(footprint.exterior.coords)
    for (x1, y1), (x2, y2) in zip(coords, coords[1:]):
        nx, ny = _normal(x1, y1, x2, y2, (x1 + x2) / 2 - cx, (y1 + y2) / 2 - cy)
        facade_len[_cardinal(nx, ny, plan.north_angle_deg)] += math.hypot(x2 - x1, y2 - y1)

    walls = {w.id: w for w in plan.walls}
    glazing_by_facade = {"N": 0.0, "E": 0.0, "S": 0.0, "W": 0.0}
    for o in plan.openings:
        if o.kind != "window":
            continue
        w = walls[o.wall_id]
        L = math.hypot(w.x2 - w.x1, w.y2 - w.y1) or 1.0
        t = (o.offset + o.width / 2) / L
        mx, my = w.x1 + t * (w.x2 - w.x1) - cx, w.y1 + t * (w.y2 - w.y1) - cy
        nx, ny = _normal(w.x1, w.y1, w.x2, w.y2, mx, my)
        glazing_by_facade[_cardinal(nx, ny, plan.north_angle_deg)] += o.width * o.height
    glazing_total = sum(glazing_by_facade.values())
    glazing_ratio = glazing_total / roof if roof else 0.0

    if glazing_total == 0:
        distribution = 0
    else:
        top = max(glazing_by_facade, key=glazing_by_facade.get)
        share = glazing_by_facade[top] / glazing_total
        distribution = 1 if share < 0.45 else CARDINAL_CODE[top]

    main_facade = max(facade_len, key=facade_len.get)
    feats = {
        "Relative_Compactness": round(compactness, 4),
        "Surface_Area": round(surface, 2),
        "Wall_Area": round(wall_area, 2),
        "Roof_Area": round(roof, 2),
        "Overall_Height": H,
        "Orientation": CARDINAL_CODE[main_facade],
        "Glazing_Area": round(glazing_ratio, 3),
        "Glazing_Area_Distribution": distribution,
    }
    assert list(feats) == FEATURES
    details = {"footprint_m2": round(roof, 2), "perimeter_m": round(perimeter, 2),
               "volume_m3": round(volume, 2),
               "facade_length_m": {k: round(v, 2) for k, v in facade_len.items()},
               "glazing_m2_by_facade": {k: round(v, 2) for k, v in glazing_by_facade.items()}}
    return feats, details
