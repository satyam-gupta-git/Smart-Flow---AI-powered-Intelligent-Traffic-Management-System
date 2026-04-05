from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import shutil
import tempfile
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .ai_processing import process_video, detect_emergency_vehicle
from .anpr import challans

from .traffic_logic import (
    Direction,
    TrafficState,
    YELLOW_DURATION,
    compute_congestion_level,
    compute_green_times,
    create_initial_state,
)
from .emergency_mode import EmergencyState, activate_emergency, deactivate_emergency


class TrafficInput(BaseModel):
    intersection_id: str = Field("I1")
    north: int = Field(0, ge=0)
    south: int = Field(0, ge=0)
    east: int = Field(0, ge=0)
    west: int = Field(0, ge=0)


class EmergencyInput(BaseModel):
    intersection_id: str = Field("I1")
    direction: Direction
    active: bool = True


class MapConfig(BaseModel):
    count: int = Field(1, ge=1, le=15)


class AccidentReport(BaseModel):
    intersection_id: str = Field("I1")
    direction: str | None = None
    severity: str = "medium"  # low | medium | high


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict) -> None:
        living: List[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
                living.append(connection)
            except Exception:
                continue
        self.active_connections = living


app = FastAPI(title="AI Traffic Control System Simulator")

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(
    "/static",
    StaticFiles(directory=str(FRONTEND_DIR), html=False),
    name="static",
)


manager = ConnectionManager()

# Multiple intersections and their neighbor relationships
intersections: Dict[str, TrafficState] = {}
emergencies: Dict[str, EmergencyState] = {}
neighbors: Dict[str, List[str]] = {}

# Accident alerts for police dashboard (in-memory, no DB)
_accident_id_counter: int = 0
accidents: List[Dict[str, Any]] = []  # { id, intersection_id, direction?, severity, reported_at, cleared }


def _congestion_to_speed_kmh(congestion: str) -> float:
    """Simulated average vehicle speed (km/h) from congestion level."""
    if congestion == "Low":
        return 45.0
    if congestion == "Medium":
        return 28.0
    return 12.0


def configure_map(count: int = 1) -> None:
    """
    Configure a city map with N intersections on a 3×5 grid of road crossings.
    Grid layout (row-major): row 0 = I1..I5, row 1 = I6..I10, row 2 = I11..I15.
    Each intersection's neighbors are the adjacent crossings (up/down/left/right).
    """
    global intersections, emergencies, neighbors, accidents

    ids = [f"I{i}" for i in range(1, count + 1)]
    intersections = {iid: create_initial_state() for iid in ids}
    emergencies = {iid: EmergencyState() for iid in ids}
    neighbors = {iid: [] for iid in ids}

    # 3 rows × 5 columns of crossings; index k = row*5 + col (0-based)
    rows, cols = 3, 5
    for idx, iid in enumerate(ids):
        row, col = idx // cols, idx % cols
        # neighbor above (same col, row-1)
        if row > 0:
            n_idx = (row - 1) * cols + col
            if n_idx < len(ids):
                neighbors[iid].append(ids[n_idx])
        # neighbor below (same col, row+1)
        if row < rows - 1:
            n_idx = (row + 1) * cols + col
            if n_idx < len(ids):
                neighbors[iid].append(ids[n_idx])
        # neighbor left (same row, col-1)
        if col > 0:
            n_idx = row * cols + (col - 1)
            if n_idx < len(ids):
                neighbors[iid].append(ids[n_idx])
        # neighbor right (same row, col+1)
        if col < cols - 1:
            n_idx = row * cols + (col + 1)
            if n_idx < len(ids):
                neighbors[iid].append(ids[n_idx])
    accidents.clear()


def _build_intersection_state(iid: str) -> Dict:
    t_state = intersections[iid]
    e_state = emergencies[iid]

    signals: Dict[Direction, Dict[str, int | str]] = {}

    if e_state.active and e_state.direction:
        for d in ["north", "south", "east", "west"]:
            color = "GREEN" if d == e_state.direction else "RED"
            signals[d] = {
                "color": color,
                "timer": t_state.remaining_time,
            }
    elif t_state.yellow_remaining > 0:
        for d in ["north", "south", "east", "west"]:
            color = "YELLOW" if d == t_state.active_direction else "RED"
            signals[d] = {
                "color": color,
                "timer": t_state.yellow_remaining,
            }
    else:
        for d in ["north", "south", "east", "west"]:
            color = "GREEN" if d == t_state.active_direction else "RED"
            signals[d] = {
                "color": color,
                "timer": t_state.remaining_time if d == t_state.active_direction else 0,
            }

    congestion = compute_congestion_level(t_state.vehicles)
    display_timer = t_state.yellow_remaining if t_state.yellow_remaining > 0 else t_state.remaining_time
    average_speed_kmh = _congestion_to_speed_kmh(congestion)
    total_vehicles = sum(t_state.vehicles.values())

    return {
        "id": iid,
        "vehicles": t_state.vehicles,
        "green_times": t_state.green_times,
        "signals": signals,
        "active_direction": e_state.direction if e_state.active else t_state.active_direction,
        "remaining_time": display_timer,
        "congestion_level": congestion,
        "average_speed_kmh": average_speed_kmh,
        "total_vehicles": total_vehicles,
        "emergency": {
            "active": e_state.active,
            "direction": e_state.direction,
        },
    }


def _build_full_state() -> Dict:
    states = {iid: _build_intersection_state(iid) for iid in intersections}
    active_accidents = [a for a in accidents if not a.get("cleared")]
    speeds = [s["average_speed_kmh"] for s in states.values()]
    city_average_speed = round(sum(speeds) / len(speeds), 1) if speeds else 0.0
    return {
        "intersections": states,
        "accidents": active_accidents,
        "city_average_speed_kmh": city_average_speed,
    }


async def _broadcast_state() -> None:
    await manager.broadcast({"type": "state", "data": _build_full_state()})


def _recompute_all_green_times_with_neighbors() -> None:
    """
    For each intersection, recompute green times using:
    - Its own vehicles
    - Plus a fraction of neighbor vehicles to model dependency.
    Does not reset the current phase: only caps remaining_time if the new green
    is shorter (realistic: don't extend or abruptly restart the current green).
    """
    for iid, t_state in intersections.items():
        combined = dict(t_state.vehicles)
        for nid in neighbors.get(iid, []):
            n_veh = intersections[nid].vehicles
            for d in combined:
                combined[d] += int(0.3 * n_veh[d])
        t_state.green_times = compute_green_times(combined)
        if t_state.active_direction not in t_state.green_times:
            t_state.active_direction = "north"
        new_green = t_state.green_times[t_state.active_direction]
        if t_state.yellow_remaining == 0:
            # Dynamically adjust current green to accommodate the new traffic count
            t_state.remaining_time = new_green


async def signal_cycle_loop() -> None:
    """
    Background loop: 1-second ticks. Realistic sequence per direction:
    Green (countdown) -> Yellow (fixed 4s) -> switch to next -> Green -> ...
    """
    directions_order: List[Direction] = ["north", "east", "south", "west"]

    while True:
        await asyncio.sleep(1)

        for iid, t_state in intersections.items():
            e_state = emergencies[iid]

            if e_state.active and e_state.direction:
                if e_state.timeout is not None:
                    if e_state.timeout > 0:
                        e_state.timeout -= 1
                    else:
                        print("Emergency cleared")
                        deactivate_emergency(e_state)
                        if t_state.active_direction not in t_state.green_times:
                            t_state.active_direction = "north"
                        t_state.remaining_time = t_state.green_times[t_state.active_direction]
                        t_state.yellow_remaining = 0
                        continue

                if t_state.remaining_time > 0:
                    t_state.remaining_time -= 1
                t_state.yellow_remaining = 0
                continue

            if t_state.yellow_remaining > 0:
                t_state.yellow_remaining -= 1
                if t_state.yellow_remaining == 0:
                    current_idx = directions_order.index(t_state.active_direction)
                    next_idx = (current_idx + 1) % len(directions_order)
                    next_dir = directions_order[next_idx]
                    t_state.active_direction = next_dir
                    t_state.remaining_time = t_state.green_times[next_dir]
                continue

            if t_state.remaining_time > 0:
                t_state.remaining_time -= 1
                continue

            # Green just ended: start yellow phase (don't switch direction yet)
            t_state.yellow_remaining = YELLOW_DURATION

        await _broadcast_state()


@app.on_event("startup")
async def startup_event() -> None:
    configure_map(1)
    asyncio.create_task(signal_cycle_loop())


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    index_path = FRONTEND_DIR / "index.html"
    with index_path.open("r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content)


@app.post("/configure-map")
async def configure_map_endpoint(cfg: MapConfig) -> Dict:
    configure_map(cfg.count)
    await _broadcast_state()
    return {"status": "ok", "state": _build_full_state()}


@app.post("/traffic-input")
async def update_traffic(input_data: TrafficInput) -> Dict:
    iid = input_data.intersection_id
    if iid not in intersections:
        return {"error": f"Unknown intersection '{iid}'"}

    t_state = intersections[iid]
    t_state.vehicles = {
        "north": input_data.north,
        "south": input_data.south,
        "east": input_data.east,
        "west": input_data.west,
    }

    _recompute_all_green_times_with_neighbors()
    await _broadcast_state()
    return {"status": "ok", "state": _build_full_state()}


@app.post("/emergency")
async def emergency(input_data: EmergencyInput) -> Dict:
    iid = input_data.intersection_id
    if iid not in intersections:
        return {"error": f"Unknown intersection '{iid}'"}

    t_state = intersections[iid]
    e_state = emergencies[iid]

    if input_data.active:
        activate_emergency(e_state, input_data.direction)
        t_state.active_direction = input_data.direction
        t_state.remaining_time = max(10, t_state.green_times.get(input_data.direction, 20))
        t_state.yellow_remaining = 0
    else:
        deactivate_emergency(e_state)
        if t_state.active_direction not in t_state.green_times:
            t_state.active_direction = "north"
        t_state.remaining_time = t_state.green_times[t_state.active_direction]
        t_state.yellow_remaining = 0

    await _broadcast_state()
    return {"status": "ok", "state": _build_full_state()}


@app.get("/signal-status")
async def signal_status() -> Dict:
    return _build_full_state()


@app.get("/challans")
async def list_challans() -> Dict:
    return {"status": "ok", "challans": challans}


@app.post("/accidents")
async def report_accident(body: AccidentReport) -> Dict:
    """Report an accident for the police dashboard."""
    global _accident_id_counter, accidents
    _accident_id_counter += 1
    accident = {
        "id": f"A{_accident_id_counter}",
        "intersection_id": body.intersection_id,
        "direction": body.direction,
        "severity": body.severity,
        "reported_at": round(time.time(), 1),
        "cleared": False,
    }
    accidents.append(accident)
    await _broadcast_state()
    return {"status": "ok", "accident": accident}


@app.post("/accidents/clear")
async def clear_accident(body: Dict[str, str]) -> Dict:
    """Mark an accident as cleared by id."""
    aid = body.get("id")
    for a in accidents:
        if a.get("id") == aid:
            a["cleared"] = True
            await _broadcast_state()
            return {"status": "ok", "cleared": aid}
    return {"error": f"Accident '{aid}' not found"}


@app.post("/process-videos")
async def process_videos(
    intersection_id: str = Form("I1"),
    video_north: Optional[UploadFile] = File(None),
    video_south: Optional[UploadFile] = File(None),
    video_east: Optional[UploadFile] = File(None),
    video_west: Optional[UploadFile] = File(None)
) -> Dict:
    iid = intersection_id
    if iid not in intersections:
        return {"error": f"Unknown intersection '{iid}'"}

    t_state = intersections[iid]
    e_state = emergencies[iid]
    
    videos = {
        "north": video_north,
        "south": video_south,
        "east": video_east,
        "west": video_west,
    }

    results = {}
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Process each uploaded video
        for d, v in videos.items():
            if v and v.filename:
                tmp_path = os.path.join(temp_dir, f"{d}_{v.filename}")
                with open(tmp_path, "wb") as buffer:
                    shutil.copyfileobj(v.file, buffer)
                
                # Run AI logic
                analysis = process_video(tmp_path, intersection_id, d)
                results[d] = analysis
                
                # Update vehicles
                if analysis["vehicle_count"] is not None:
                    t_state.vehicles[d] = max(0, analysis["vehicle_count"])

                # Handle incident detection (sudden stop or collision)
                if analysis.get("accident") or analysis.get("sudden_stop"):
                    # Activate emergency for this lane
                    activate_emergency(e_state, d, timeout=10)
                    t_state.active_direction = d
                    t_state.remaining_time = max(20, t_state.green_times.get(d, 30))
                    t_state.yellow_remaining = 0
                    
                    # Log accident
                    global _accident_id_counter, accidents
                    _accident_id_counter += 1
                    severity = "high" if analysis.get("accident") else "medium"
                    accident = {
                        "id": f"A{_accident_id_counter}",
                        "intersection_id": iid,
                        "direction": d,
                        "severity": severity,
                        "reported_at": round(time.time(), 1),
                        "cleared": False,
                    }
                    accidents.append(accident)
                else:
                    # Also check for emergency vehicles (ambulance, fire truck)
                    is_emerg = detect_emergency_vehicle(tmp_path)
                    if is_emerg:
                        print(f"Activating green corridor for {d}")
                        activate_emergency(e_state, d, timeout=10)
                        t_state.active_direction = d
                        t_state.remaining_time = max(20, t_state.green_times.get(d, 30))
                        t_state.yellow_remaining = 0
                    
        _recompute_all_green_times_with_neighbors()
        await _broadcast_state()
        return {"status": "ok", "message": "Videos processed", "results": results}
        
    finally:
        # Cleanup temporary files
        shutil.rmtree(temp_dir, ignore_errors=True)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    await websocket.send_json({"type": "state", "data": _build_full_state()})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

