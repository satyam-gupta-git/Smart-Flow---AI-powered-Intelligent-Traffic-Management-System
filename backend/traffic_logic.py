from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal


Direction = Literal["north", "south", "east", "west"]


# Realistic fixed yellow (amber) phase duration in seconds (clearance before red)
YELLOW_DURATION = 4

@dataclass
class TrafficState:
    vehicles: Dict[Direction, int]
    green_times: Dict[Direction, int]
    active_direction: Direction
    remaining_time: int  # seconds left for current green
    yellow_remaining: int = 0  # seconds left in yellow phase; 0 = not in yellow


def _normalize_counts(vehicles: Dict[Direction, int]) -> Dict[Direction, int]:
    """Clamp negative inputs to zero."""
    return {d: max(0, int(v)) for d, v in vehicles.items()}


def compute_green_times(
    vehicles_raw: Dict[Direction, int],
    *,
    min_green: int = 10,
    max_green: int = 50,
) -> Dict[Direction, int]:
    """
    Compute green time in seconds for each direction based on vehicle counts.

    Realistic bounds (typical real-world ranges): min_green 10s, max_green 50s.
    - Lane with highest vehicles gets the longest green time (up to max_green).
    - Other lanes get at least min_green seconds.
    - More vehicles -> proportionally more green time.
    """
    vehicles = _normalize_counts(vehicles_raw)

    total = sum(vehicles.values())
    if total == 0:
        # No vehicles anywhere: give everyone same small green time
        return {d: min_green for d in vehicles}

    # Target: keep total cycle around 4 * max_green seconds in heavy traffic.
    # We scale times proportionally to vehicle share, but clamp to [min_green, max_green].
    base_cycle = 4 * max_green
    raw_times: Dict[Direction, float] = {}
    for d, count in vehicles.items():
        share = count / total
        raw = share * base_cycle
        raw_times[d] = raw

    # Clamp and round
    green_times: Dict[Direction, int] = {}
    for d, raw in raw_times.items():
        t = int(round(raw))
        t = max(min_green, min(max_green, t))
        green_times[d] = t

    # Ensure the direction with the maximum vehicles gets the maximum green time
    max_dir = max(vehicles, key=lambda k: vehicles[k])
    green_times[max_dir] = max_green

    return green_times


def compute_congestion_level(vehicles_raw: Dict[Direction, int]) -> str:
    """
    Compute a simple congestion indicator:
    - Low:   total vehicles < 20
    - Medium: 20 <= total < 60
    - High:  total >= 60
    """
    vehicles = _normalize_counts(vehicles_raw)
    total = sum(vehicles.values())
    if total < 20:
        return "Low"
    if total < 60:
        return "Medium"
    return "High"


def create_initial_state() -> TrafficState:
    vehicles: Dict[Direction, int] = {
        "north": 0,
        "south": 0,
        "east": 0,
        "west": 0,
    }
    green_times = compute_green_times(vehicles)
    # Start with north as active direction
    active_direction: Direction = "north"
    remaining_time = green_times[active_direction]
    return TrafficState(
        vehicles=vehicles,
        green_times=green_times,
        active_direction=active_direction,
        remaining_time=remaining_time,
        yellow_remaining=0,
    )

