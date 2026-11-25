"""Disposition -> Plan JSON commun (pièces, murs, portes, fenêtres), en mètres.

Conventions de common/schema.py : les pièces sont les sols utiles, les murs sont
décrits par leur axe. Une façade (0,20 m) est à 0,10 m de la pièce, une cloison
(0,12 m) à 0,06 m. Tous les calculs se font en unités entières de 2 cm.
"""
from __future__ import annotations

from .solver import EXT_WALL, PARTITION, UNIT, Layout

X0 = Y0 = 50                      # axes des façades sud et ouest (1,00 m)
OX = X0 + EXT_WALL // 2           # coin intérieur sud-ouest (1,10 m)
OY = Y0 + EXT_WALL // 2
HALF_PARTITION = PARTITION // 2
WALL_HEIGHT = 2.7

LABELS = {"living": "Séjour", "kitchen": "Cuisine", "corridor": "Couloir",
          "bedroom": "Chambre", "bathroom": "Salle de bain"}


def _m(units: float) -> float:
    return round(units * UNIT, 4)


def _wall(id, x1, y1, x2, y2, thickness, exterior, adjacent):
    return {"id": id, "x1": _m(x1), "y1": _m(y1), "x2": _m(x2), "y2": _m(y2),
            "thickness": thickness, "exterior": exterior, "adjacent_room_ids": list(adjacent)}


def _opening(id, kind, wall_id, offset, width, height, sill, rooms):
    return {"id": id, "kind": kind, "wall_id": wall_id, "offset": _m(offset),
            "width": _m(width), "height": height, "sill": sill,
            "connected_room_ids": list(rooms)}


def _names(layout: Layout) -> dict[str, str]:
    counts: dict[str, int] = {}
    for t in layout.types.values():
        counts[t] = counts.get(t, 0) + 1
    seen: dict[str, int] = {}
    names = {}
    for rid, t in layout.types.items():
        seen[t] = seen.get(t, 0) + 1
        label = LABELS.get(t, t.capitalize())
        names[rid] = f"{label} {seen[t]}" if counts[t] > 1 else label
    return names


def build_plan(layout: Layout) -> dict:
    bands, rects = layout.bands, layout.rects
    hall_index = next(i for i, b in enumerate(bands) if b.is_hall)
    names = _names(layout)

    def absolute(r):  # (x, y, w, h) du sol utile, en unités absolues
        return OX + r.x, OY + r.y, r.w, r.h

    east = OX + layout.width + EXT_WALL // 2
    north = OY + layout.depth + EXT_WALL // 2

    rooms = []
    for band in bands:
        for rid in band.ids:
            x, y, w, h = absolute(rects[rid])
            rooms.append({"id": rid, "name": names[rid], "type": layout.types[rid],
                          "x": _m(x), "y": _m(y), "w": _m(w), "h": _m(h)})

    # ---- murs ----
    walls = []
    walls.append(_wall("south", X0, Y0, east, Y0, 0.2, True, bands[0].ids))
    walls.append(_wall("east", east, Y0, east, north, 0.2, True, [b.ids[-1] for b in bands]))
    walls.append(_wall("north", X0, north, east, north, 0.2, True, bands[-1].ids))
    walls.append(_wall("west", X0, Y0, X0, north, 0.2, True, [b.ids[0] for b in bands]))

    h_axis = {}                   # index de cloison horizontale -> (id, y de l'axe)
    for j in range(len(bands) - 1):
        lower = bands[j]
        axis = OY + lower.y + lower.depth + HALF_PARTITION
        wid = "hall-south" if j + 1 == hall_index else "hall-north"
        h_axis[j] = (wid, axis)
        walls.append(_wall(wid, X0, axis, east, axis, 0.12, False, lower.ids + bands[j + 1].ids))

    pair_wall = {}                # {a, b} -> (id, y1 de la cloison verticale)
    for i, band in enumerate(bands):
        if band.is_hall:
            continue
        y_low = Y0 if i == 0 else h_axis[i - 1][1]
        y_high = north if i == len(bands) - 1 else h_axis[i][1]
        for k, (a, b) in enumerate(zip(band.ids, band.ids[1:])):
            ra = rects[a]
            x = OX + ra.x + ra.w + HALF_PARTITION
            wid = f"part-{i}-{k}"
            pair_wall[frozenset((a, b))] = (wid, y_low)
            walls.append(_wall(wid, x, y_low, x, y_high, 0.12, False, [a, b]))

    # ---- ouvertures ----
    openings = []
    hall = rects[layout.hall_id]
    hx, hy, hw, hh = absolute(hall)

    dw = min(48, hh - 6)
    openings.append(_opening("entrance", "door", "west", hy - Y0 + (hh - dw) // 2, dw,
                             2.1, 0, [layout.hall_id]))

    for i, band in enumerate(bands):
        if band.is_hall:
            continue
        wall_id = h_axis[i][0] if i < hall_index else h_axis[i - 1][0]
        for rid in band.ids:
            x, _, w, _ = absolute(rects[rid])
            dw = 40 if layout.types[rid] == "bathroom" else 45
            dw = min(dw, w - 20)
            openings.append(_opening(f"door-{rid}", "door", wall_id, x - X0 + (w - dw) // 2,
                                     dw, 2.1, 0, [rid, layout.hall_id]))

    for a, b in layout.passages:
        wid, y1 = pair_wall[frozenset((a, b))]
        _, y, _, h = absolute(rects[a])
        pw = min(65, h - 20)
        openings.append(_opening(f"passage-{a}-{b}", "opening", wid, y - y1 + (h - pw) // 2,
                                 pw, 2.1, 0, [a, b]))

    for band, wall_id in ((bands[0], "south"), (bands[-1], "north")):
        if band.is_hall:
            continue
        for rid in band.ids:
            x, _, w, _ = absolute(rects[rid])
            if layout.types[rid] == "bathroom":
                ww, height, sill = 40, 1.0, 1.2
            else:
                ww, height, sill = min(75, w - 30), 1.2, 0.9
            if ww < 30:
                continue
            openings.append(_opening(f"window-{rid}", "window", wall_id, x - X0 + (w - ww) // 2,
                                     ww, height, sill, [rid]))

    return {
        "schema_version": "1.0.0",
        "plan_id": "generated",
        "unit": "m",
        "north_angle_deg": 0,
        "orientation_status": "assumed",
        "wall_height": WALL_HEIGHT,
        "site": {"width": _m(east + 50), "depth": _m(north + 50)},
        "rooms": rooms,
        "walls": walls,
        "openings": openings,
    }