from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Literal

Direction = Literal["north", "south", "east", "west"]


@dataclass
class EmergencyState:
    active: bool = False
    direction: Optional[Direction] = None


def activate_emergency(state: EmergencyState, direction: Direction) -> None:
    state.active = True
    state.direction = direction


def deactivate_emergency(state: EmergencyState) -> None:
    state.active = False
    state.direction = None

