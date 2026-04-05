## AI Traffic Control System Simulator

This project simulates a **smart city traffic management system** for a 4‑way intersection using:

- **Backend**: FastAPI (Python)
- **Frontend**: HTML + JavaScript + WebSocket
- **Communication**: WebSocket for real‑time traffic signal updates
- **Storage**: No database or persistent storage (in‑memory only)

The system allows manual entry of vehicle counts for each direction and uses a simple AI‑style algorithm to assign green signal times dynamically. It also includes an **Emergency Vehicle Mode** that immediately prioritizes a selected lane.

### Project Structure

- **backend/**
  - `main.py` – FastAPI app, WebSocket handling, state management
  - `traffic_logic.py` – traffic timing and congestion logic
  - `emergency_mode.py` – emergency mode state and helpers
- **frontend/**
  - `index.html` – main dashboard UI
  - `traffic_dashboard.js` – WebSocket client and UI logic
  - `traffic_styles.css` – basic styling and animations
- `requirements.txt` – Python dependencies

### 1. Backend Setup

1. Make sure you have **Python 3.9+** installed.
2. Open a terminal in the project root:

```bash
cd "d:\Downloads\Traffic Contrroller"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

3. Start the FastAPI server:

```bash
uvicorn backend.main:app --reload
```

The backend will run on `http://127.0.0.1:8000`.

### 2. Frontend

The backend serves the static frontend files directly. After starting the server, open:

- `http://127.0.0.1:8000/` in your browser.

You will see:

- A visual 4‑way intersection with signals (N/S/E/W).
- Input fields for vehicle counts.
- Buttons for **Calculate Traffic** and **Emergency Vehicle Detected**.
- Live updating dashboard: signal colors, countdown timers, congestion levels, and simple vehicle movement animation.

### 3. API Endpoints

- `POST /traffic-input`
  - Body: JSON `{ "north": int, "south": int, "east": int, "west": int }`
  - Purpose: Update vehicle counts and recompute green times.

- `POST /emergency`
  - Body: JSON `{ "direction": "north" | "south" | "east" | "west", "active": bool }`
  - Purpose: Activate or deactivate emergency mode for a direction.

- `GET /signal-status`
  - Purpose: Get the current signal state, remaining timer, vehicle counts, and congestion level.

- `GET /` (root)
  - Serves the frontend dashboard.

- `GET /static/*`
  - Serves static assets (JS/CSS) from the `frontend` directory.

- `WebSocket /ws`
  - Pushes live updates to the UI whenever:
    - Signal colors change
    - Countdown timers tick
    - Vehicle counts or congestion levels change
    - Emergency mode is activated/deactivated

### 4. Running the Simulator

1. Start the backend as described above.
2. Open `http://127.0.0.1:8000/` in your browser.
3. Enter vehicle counts for each direction and click **Calculate Traffic**.
4. Watch the signals and timers update in real‑time based on the computed green times.
5. Click **Emergency Vehicle Detected**, select a direction, and activate it to force that lane to GREEN and others to RED. Deactivate to return to normal logic.

### 5. Notes

- Everything runs in memory – restarting the server resets all state.
- No real cameras or sensors are used; **all vehicle data is manually entered**.
- The traffic algorithm is intentionally simple and is meant for educational/demo purposes, not for production traffic engineering.

