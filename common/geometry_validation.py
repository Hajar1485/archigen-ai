"""Contrôles métriques après la lecture structurelle par Plan.model_validate."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from math import dist, hypot

from .schema import Opening, Plan, Room, Wall

TOLERANCE = 1e-6  # mètres


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def raise_for_errors(self) -> None:
        if self.errors:
            raise ValueError("\n".join(self.errors))


def _same_segment(a: Wall, b: Wall) -> bool:
    start, end = (a.x1, a.y1), (a.x2, a.y2)
    other_start, other_end = (b.x1, b.y1), (b.x2, b.y2)
    return any(
        dist(start, p) <= TOLERANCE and dist(end, q) <= TOLERANCE
        for p, q in ((other_start, other_end), (other_end, other_start))
    )


def _check_rooms(plan: Plan, report: ValidationReport) -> None:
    for room in plan.rooms:
        site = plan.site
        if site and (room.x < -TOLERANCE or room.y < -TOLERANCE
                     or room.x + room.w > site.width + TOLERANCE
                     or room.y + room.h > site.depth + TOLERANCE):
            report.errors.append(f"{room.id}: rectangle hors du terrain")
    for a, b in combinations(plan.rooms, 2):
        overlap_x = min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
        overlap_y = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
        if min(overlap_x, overlap_y) > TOLERANCE:
            report.errors.append(f"{a.id}, {b.id}: intérieurs des pièces superposés")


def _check_refs(owner: str, refs: list[str], ids: set[str], report: ValidationReport) -> None:
    for ref, count in Counter(refs).items():
        if ref not in ids:
            report.errors.append(f"{owner}: pièce inconnue {ref}")
        if count > 1:
            report.errors.append(f"{owner}: référence répétée à {ref}")


def _face_span(wall: Wall, room: Room) -> tuple[float, float] | None:
    """Intervalle de la face de pièce, projeté depuis le début d'un mur orthogonal."""
    if abs(wall.y2 - wall.y1) <= TOLERANCE:
        axis, end = wall.x1, wall.x2
        near, far = room.x, room.x + room.w
        gaps = (room.y - wall.y1, wall.y1 - (room.y + room.h))
    else:
        axis, end = wall.y1, wall.y2
        near, far = room.y, room.y + room.h
        gaps = (room.x - wall.x1, wall.x1 - (room.x + room.w))
    if min(abs(gap - wall.thickness / 2) for gap in gaps) > TOLERANCE:
        return None
    return (near - axis, far - axis) if end >= axis else (axis - far, axis - near)


def _check_openings(plan: Plan, rooms: dict[str, Room], completed: bool, report: ValidationReport) -> None:
    walls = {wall.id: wall for wall in plan.walls}
    by_wall: dict[str, list[Opening]] = defaultdict(list)
    for op in plan.openings:
        wall = walls.get(op.wall_id)
        if wall is None:  # Le plan peut avoir été édité après sa lecture.
            report.errors.append(f"{op.id}: mur inconnu {op.wall_id}")
            continue
        length = hypot(wall.x2 - wall.x1, wall.y2 - wall.y1)
        if op.offset + op.width > length + TOLERANCE:
            report.errors.append(f"{op.id}: offset + width dépasse la longueur de {wall.id}")
        if op.sill + op.height > plan.wall_height + TOLERANCE:
            report.errors.append(f"{op.id}: sill + height dépasse wall_height")
        if op.kind != "window" and op.sill > TOLERANCE:
            diagnostics = report.errors if completed else report.warnings
            diagnostics.append(f"{op.id}: une porte ou un passage au niveau du sol exige sill=0")
        refs = op.connected_room_ids
        _check_refs(op.id, refs, set(rooms), report)
        if refs and len(refs) != (1 if wall.exterior else 2):
            report.errors.append(f"{op.id}: indiquer une pièce sur une façade, deux sur une cloison")
        if wall.adjacent_room_ids and set(refs) - set(wall.adjacent_room_ids):
            report.errors.append(f"{op.id}: connexion hors des pièces adjacentes à {wall.id}")
        orthogonal = min(abs(wall.x2 - wall.x1), abs(wall.y2 - wall.y1)) <= TOLERANCE
        if completed and orthogonal:
            for ref in refs:
                if ref in rooms:
                    span = _face_span(wall, rooms[ref])
                    if span is None or op.offset < span[0] - TOLERANCE or op.offset + op.width > span[1] + TOLERANCE:
                        report.errors.append(f"{op.id}: la baie ne donne pas entièrement sur {ref}")
        by_wall[wall.id].append(op)

    for wall_id, openings in by_wall.items():
        for a, b in combinations(openings, 2):
            along = min(a.offset + a.width, b.offset + b.width) - max(a.offset, b.offset)
            vertical = min(a.sill + a.height, b.sill + b.height) - max(a.sill, b.sill)
            if min(along, vertical) > TOLERANCE:
                report.errors.append(f"{a.id}, {b.id}: baies superposées sur {wall_id}")


def _check_access(plan: Plan, report: ValidationReport) -> None:
    graph: dict[str, set[str]] = defaultdict(set)
    entrances: set[str] = set()
    facades = {w.id for w in plan.walls if w.exterior}
    for op in plan.openings:
        refs = op.connected_room_ids
        if op.kind == "window":
            continue
        if op.wall_id in facades and len(refs) == 1:
            entrances.update(refs)
        elif len(refs) == 2:
            a, b = refs
            graph[a].add(b)
            graph[b].add(a)
    reached = set(entrances)
    queue = list(entrances)
    while queue:
        for neighbor in graph[queue.pop()] - reached:
            reached.add(neighbor)
            queue.append(neighbor)
    missing = sorted({r.id for r in plan.rooms} - reached)
    if missing:
        report.warnings.append("Accès depuis l'extérieur à vérifier : " + ", ".join(missing))


def validate_geometry(plan: Plan, *, completed: bool = False) -> ValidationReport:
    """Retourne tous les diagnostics. completed=True ajoute les contrôles d'intégration."""
    report = ValidationReport()
    for label, entities in (("pièce", plan.rooms), ("mur", plan.walls), ("ouverture", plan.openings)):
        for identifier, count in Counter(item.id for item in entities).items():
            if count > 1:
                report.errors.append(f"{label} {identifier}: id dupliqué")
    rooms = {room.id: room for room in plan.rooms}
    _check_rooms(plan, report)
    for wall in plan.walls:
        if hypot(wall.x2 - wall.x1, wall.y2 - wall.y1) <= TOLERANCE:
            report.errors.append(f"{wall.id}: mur de longueur nulle")
        _check_refs(wall.id, wall.adjacent_room_ids, set(rooms), report)
        length = hypot(wall.x2 - wall.x1, wall.y2 - wall.y1)
        orthogonal = min(abs(wall.x2 - wall.x1), abs(wall.y2 - wall.y1)) <= TOLERANCE
        if not orthogonal:
            diagnostics = report.errors if completed else report.warnings
            diagnostics.append(f"{wall.id}: orientation oblique hors du profil orthogonal V1")
        if completed and orthogonal:
            for ref in wall.adjacent_room_ids:
                if ref in rooms:
                    span = _face_span(wall, rooms[ref])
                    if span is None or min(span[1], length) - max(span[0], 0) <= TOLERANCE:
                        report.errors.append(f"{wall.id}: aucune face adjacente à {ref}")
    for a, b in combinations(plan.walls, 2):
        if _same_segment(a, b):
            report.errors.append(f"{a.id}, {b.id}: segment de mur dupliqué")
    _check_openings(plan, rooms, completed, report)
    if completed:
        if not any(w.exterior for w in plan.walls):
            report.errors.append("Un plan terminé doit comporter des murs extérieurs")
        _check_access(plan, report)
    return report
