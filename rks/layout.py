from __future__ import annotations

from dataclasses import dataclass
from .model import Project, Line

SINGLE = 'single'
DOUBLE = 'double'
STAGGER_LEFT = 'stagger_left'
STAGGER_RIGHT = 'stagger_right'
LAYOUT_MODES = (SINGLE, DOUBLE, STAGGER_LEFT, STAGGER_RIGHT)


@dataclass(frozen=True)
class Placement:
    line: Line
    start: float
    end: float
    x: int
    y: int
    alignment: int
    karaoke: bool = True


def _position(project: Project, slot: str) -> tuple[int, int, int]:
    style = project.style
    bottom_margin = round(style.margin_bottom * project.height / 1080)
    if slot == 'center':
        return project.width // 2, project.height - bottom_margin, 2
    if slot == 'upper':
        return round(project.width * .055), round(project.height * .73), 1
    if slot == 'lower':
        return round(project.width * .945), project.height - bottom_margin, 3
    raise ValueError(slot)


def placements(project: Project) -> list[Placement]:
    lines = sorted(project.lines, key=lambda line: line.start)
    mode = project.layout_mode if project.layout_mode in LAYOUT_MODES else DOUBLE
    result: list[Placement] = []
    if mode in (SINGLE, DOUBLE):
        for line in lines:
            x, y, align = _position(project, 'center')
            if mode == DOUBLE and line.lane == 0:
                y -= round(project.style.size * 1.35)
            result.append(Placement(line, max(0, line.start), max(0, line.end), x, y, align))
        return [item for item in result if item.end > item.start]

    current_slot, upcoming_slot = ('upper', 'lower') if mode == STAGGER_LEFT else ('lower', 'upper')
    for index, line in enumerate(lines):
        next_line = lines[index + 1] if index + 1 < len(lines) else None
        end = max(line.start, min(project.duration or float('inf'), next_line.start if next_line else line.end))
        x, y, align = _position(project, current_slot)
        if end > line.start:
            result.append(Placement(line, max(0, line.start), end, x, y, align, True))
        if next_line and end > line.start:
            nx, ny, na = _position(project, upcoming_slot)
            result.append(Placement(next_line, max(0, line.start), end, nx, ny, na, False))
    return result


def visible_at(project: Project, seconds: float) -> list[Placement]:
    return [item for item in placements(project) if item.start <= seconds < item.end]
