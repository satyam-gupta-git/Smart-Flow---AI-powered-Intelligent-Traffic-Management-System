// Client-side logic for the AI Traffic Control System Simulator with multiple intersections.

const apiBase = "";

function $(id) {
  return document.getElementById(id);
}

function directionLabel(dir) {
  switch (dir) {
    case "north":
      return "North";
    case "south":
      return "South";
    case "east":
      return "East";
    case "west":
      return "West";
    default:
      return dir;
  }
}

async function postJSON(path, body) {
  const res = await fetch(apiBase + path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error("Request failed: " + res.status);
  }
  return res.json();
}

let latestState = null;
let selectedIntersectionId = null;
let paused = false;

function updateIntersectionDetail(intersection) {
  const { vehicles, green_times, signals, active_direction, remaining_time, congestion_level, emergency } =
    intersection;

  ["north", "south", "east", "west"].forEach((dir) => {
    const signalEl = $("signal-" + dir);
    if (!signalEl) return;
    const laneSignals = signals[dir];
    const color = laneSignals?.color || "RED";
    const timer = laneSignals?.timer || 0;

    const red = signalEl.querySelector(".light.red");
    const yellow = signalEl.querySelector(".light.yellow");
    const green = signalEl.querySelector(".light.green");

    red.classList.remove("on");
    yellow.classList.remove("on");
    green.classList.remove("on");

    if (color === "GREEN") {
      green.classList.add("on");
    } else if (color === "YELLOW") {
      yellow.classList.add("on");
    } else {
      red.classList.add("on");
    }

    const timerEl = $("timer-" + dir);
    if (timerEl) {
      timerEl.textContent = timer + "s";
    }

    const count = vehicles[dir] || 0;
    const vEl = $("vehicles-" + dir);
    if (vEl) {
      vEl.textContent = count + " vehicles";
    }

    const streamEl = $("stream-" + dir);
    if (streamEl) {
      if (color === "GREEN" && count > 0) {
        streamEl.classList.add("moving");
      } else {
        streamEl.classList.remove("moving");
      }
    }
  });

  $("summary-north").textContent = vehicles.north || 0;
  $("summary-south").textContent = vehicles.south || 0;
  $("summary-east").textContent = vehicles.east || 0;
  $("summary-west").textContent = vehicles.west || 0;

  $("green-north").textContent = green_times.north || 0;
  $("green-south").textContent = green_times.south || 0;
  $("green-east").textContent = green_times.east || 0;
  $("green-west").textContent = green_times.west || 0;

  $("dashboard-active").textContent = directionLabel(active_direction);
  $("dashboard-timer").textContent = remaining_time + "s";

  const congestionEl = $("congestion-indicator");
  congestionEl.textContent = congestion_level;
  congestionEl.classList.remove("congestion-low", "congestion-medium", "congestion-high");
  if (congestion_level === "Low") {
    congestionEl.classList.add("congestion-low");
  } else if (congestion_level === "Medium") {
    congestionEl.classList.add("congestion-medium");
  } else {
    congestionEl.classList.add("congestion-high");
  }

  const centerStatus = $("center-status");
  if (emergency.active && emergency.direction) {
    centerStatus.textContent =
      "EMERGENCY: " + directionLabel(emergency.direction) + " lane has priority";
    centerStatus.classList.add("emergency");
  } else if (signals[active_direction]?.color === "YELLOW") {
    centerStatus.textContent =
      "Yellow: " + directionLabel(active_direction) + " clearing for next phase";
    centerStatus.classList.remove("emergency");
  } else {
    centerStatus.textContent =
      "Normal mode: " + directionLabel(active_direction) + " is GREEN";
    centerStatus.classList.remove("emergency");
  }
}

// One intersection at each road crossing: 3 horizontal × 5 vertical (viewBox 0 0 700 400)
const MAP_INTERSECTION_POSITIONS = {
  I1: [120, 85], I2: [230, 85], I3: [350, 85], I4: [480, 85], I5: [580, 85],
  I6: [120, 200], I7: [230, 200], I8: [350, 200], I9: [480, 200], I10: [580, 200],
  I11: [120, 315], I12: [230, 315], I13: [350, 315], I14: [480, 315], I15: [580, 315],
};

function renderCityMap(intersections) {
  const nodesGroup = document.getElementById("map-intersection-nodes");
  if (!nodesGroup) return;
  nodesGroup.innerHTML = "";
  const ids = Object.keys(intersections);
  if (ids.length === 0) return;

  ids.forEach((iid) => {
    const pos = MAP_INTERSECTION_POSITIONS[iid];
    if (!pos) return;
    const [cx, cy] = pos;
    const isel = intersections[iid];
    const congestionClass =
      isel.congestion_level === "High"
        ? "congestion-high"
        : isel.congestion_level === "Medium"
          ? "congestion-medium"
          : "congestion-low";

    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.setAttribute("class", "map-intersection-node");
    g.setAttribute("data-id", iid);
    g.setAttribute("transform", `translate(${cx},${cy})`);
    g.style.cursor = "pointer";
    if (selectedIntersectionId === iid) g.classList.add("selected");

    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("r", 20);
    circle.setAttribute("class", "map-node-circle");

    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("text-anchor", "middle");
    label.setAttribute("dy", "0.35em");
    label.setAttribute("class", "map-node-label");
    label.textContent = iid;

    g.appendChild(circle);
    g.appendChild(label);

    const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    dot.setAttribute("r", 4);
    dot.setAttribute("cy", -12);
    dot.setAttribute("class", `map-node-dot ${congestionClass}`);
    g.appendChild(dot);

    g.addEventListener("click", () => selectIntersectionById(iid, intersections));
    g.setAttribute("title", `Select ${iid} for traffic control`);

    nodesGroup.appendChild(g);
  });
}

function selectIntersectionById(iid, intersections) {
  selectedIntersectionId = iid;
  const select = $("intersection-select");
  if (select) select.value = iid;
  const labelEl = $("selected-intersection-label");
  const titleEl = $("intersection-view-title");
  if (labelEl) {
    const strong = labelEl.querySelector("strong");
    if (strong) strong.textContent = iid;
  }
  if (titleEl) titleEl.textContent = `(${iid})`;
  // Update inputs to current vehicle counts for this intersection
  const isel = intersections[iid];
  if (isel) {
    $("input-north").value = isel.vehicles.north || 0;
    $("input-south").value = isel.vehicles.south || 0;
    $("input-east").value = isel.vehicles.east || 0;
    $("input-west").value = isel.vehicles.west || 0;
    if (!paused) updateIntersectionDetail(isel);
  }
  // Re-render map to update .selected on nodes
  renderCityMap(intersections);
}

function syncIntersectionSelect(intersections) {
  const select = $("intersection-select");
  const current = selectedIntersectionId;
  select.innerHTML = "";
  const ids = Object.keys(intersections);
  ids.forEach((iid) => {
    const opt = document.createElement("option");
    opt.value = iid;
    opt.textContent = iid;
    select.appendChild(opt);
  });
  if (current && intersections[current]) {
    selectedIntersectionId = current;
  } else {
    selectedIntersectionId = ids[0] || null;
  }
  if (selectedIntersectionId) {
    select.value = selectedIntersectionId;
  }
}

function updateSignalUI(fullState) {
  if (paused) return;
  latestState = fullState;
  const intersections = fullState.intersections || {};
  if (!Object.keys(intersections).length) return;

  syncIntersectionSelect(intersections);
  renderCityMap(intersections);

  const intersection = intersections[selectedIntersectionId];
  if (intersection) {
    updateIntersectionDetail(intersection);
  }
  const labelEl = $("selected-intersection-label");
  const titleEl = $("intersection-view-title");
  if (labelEl && selectedIntersectionId) {
    const strong = labelEl.querySelector("strong");
    if (strong) strong.textContent = selectedIntersectionId;
  }
  if (titleEl && selectedIntersectionId) titleEl.textContent = `(${selectedIntersectionId})`;
  updatePoliceDashboard(fullState);
}

function updatePoliceDashboard(fullState) {
  const intersections = fullState.intersections || {};
  const accidents = fullState.accidents || [];
  const citySpeed = fullState.city_average_speed_kmh;

  const ids = Object.keys(intersections);
  const maxVehicles = Math.max(1, ...ids.map((iid) => (intersections[iid].total_vehicles || 0)));

  const congestionEl = $("congestion-map");
  if (congestionEl) {
    congestionEl.innerHTML = "";
    ids.forEach((iid) => {
      const isel = intersections[iid];
      const level = isel.congestion_level || "Low";
      const cell = document.createElement("div");
      cell.className = `congestion-cell congestion-${level.toLowerCase()}`;
      cell.textContent = iid;
      cell.title = `${iid}: ${level}`;
      congestionEl.appendChild(cell);
    });
  }

  const alertsEl = $("accident-alerts");
  if (alertsEl) {
    alertsEl.innerHTML = "";
    if (accidents.length === 0) {
      alertsEl.innerHTML = "<p class=\"no-alerts\">No active accidents</p>";
    } else {
      accidents.forEach((a) => {
        const row = document.createElement("div");
        row.className = "accident-item";
        row.innerHTML = `
          <span class="accident-desc">${a.intersection_id} ${a.severity}</span>
          <button class="btn btn-small btn-secondary clear-accident" data-id="${a.id}">Clear</button>
        `;
        row.querySelector(".clear-accident").addEventListener("click", async () => {
          try {
            await postJSON("/accidents/clear", { id: a.id });
          } catch (err) {
            alert("Failed to clear: " + err.message);
          }
        });
        alertsEl.appendChild(row);
      });
    }
  }

  const heatmapEl = $("density-heatmap");
  if (heatmapEl) {
    heatmapEl.innerHTML = "";
    ids.forEach((iid) => {
      const isel = intersections[iid];
      const total = isel.total_vehicles || 0;
      const intensity = maxVehicles > 0 ? total / maxVehicles : 0;
      const cell = document.createElement("div");
      cell.className = "density-cell";
      cell.style.backgroundColor = `rgba(239, 68, 68, ${0.2 + 0.8 * intensity})`;
      cell.textContent = total;
      cell.title = `${iid}: ${total} vehicles`;
      heatmapEl.appendChild(cell);
    });
  }

  const citySpeedEl = $("city-average-speed");
  if (citySpeedEl) citySpeedEl.textContent = citySpeed != null ? `${citySpeed} km/h` : "— km/h";

  const speedListEl = $("speed-by-intersection");
  if (speedListEl) {
    speedListEl.innerHTML = "";
    ids.forEach((iid) => {
      const isel = intersections[iid];
      const speed = isel.average_speed_kmh != null ? isel.average_speed_kmh : "—";
      const p = document.createElement("p");
      p.className = "speed-row";
      p.innerHTML = `<span>${iid}</span><strong>${speed} km/h</strong>`;
      speedListEl.appendChild(p);
    });
  }

  const accSelect = $("accident-intersection");
  if (accSelect && accSelect.options.length !== ids.length) {
    accSelect.innerHTML = "";
    ids.forEach((iid) => {
      const opt = document.createElement("option");
      opt.value = iid;
      opt.textContent = iid;
      accSelect.appendChild(opt);
    });
  }
}

function setupWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = protocol + "//" + window.location.host + "/ws";
  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    console.log("WebSocket connected");
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === "state" && msg.data) {
        updateSignalUI(msg.data);
      }
    } catch (err) {
      console.error("Error parsing WS message", err);
    }
  };

  ws.onclose = () => {
    console.log("WebSocket closed, retrying in 3s...");
    setTimeout(setupWebSocket, 3000);
  };

  ws.onerror = () => {
    ws.close();
  };
}

function setupControls() {
  $("btn-calculate").addEventListener("click", async () => {
    const north = parseInt($("input-north").value || "0", 10);
    const south = parseInt($("input-south").value || "0", 10);
    const east = parseInt($("input-east").value || "0", 10);
    const west = parseInt($("input-west").value || "0", 10);
    const intersection_id = $("intersection-select").value || "I1";

    try {
      await postJSON("/traffic-input", { intersection_id, north, south, east, west });
    } catch (err) {
      alert("Failed to send traffic input: " + err.message);
    }
  });

  $("btn-reset").addEventListener("click", async () => {
    $("input-north").value = 0;
    $("input-south").value = 0;
    $("input-east").value = 0;
    $("input-west").value = 0;
    const intersection_id = $("intersection-select").value || "I1";
    try {
      await postJSON("/traffic-input", {
        intersection_id,
        north: 0,
        south: 0,
        east: 0,
        west: 0,
      });
    } catch (err) {
      alert("Failed to reset: " + err.message);
    }
  });

  $("btn-stop").addEventListener("click", () => {
    paused = !paused;
    $("btn-stop").textContent = paused ? "Resume" : "Stop";
    if (!paused && latestState) {
      updateSignalUI(latestState);
    }
  });

  $("btn-emergency-on").addEventListener("click", async () => {
    const direction = $("emergency-direction").value;
    const intersection_id = $("intersection-select").value || "I1";
    try {
      await postJSON("/emergency", { intersection_id, direction, active: true });
    } catch (err) {
      alert("Failed to activate emergency: " + err.message);
    }
  });

  $("btn-emergency-off").addEventListener("click", async () => {
    const direction = $("emergency-direction").value;
    const intersection_id = $("intersection-select").value || "I1";
    try {
      await postJSON("/emergency", { intersection_id, direction, active: false });
    } catch (err) {
      alert("Failed to end emergency: " + err.message);
    }
  });

  $("btn-apply-map").addEventListener("click", async () => {
    const count = parseInt($("map-count").value || "1", 10);
    try {
      await postJSON("/configure-map", { count });
    } catch (err) {
      alert("Failed to configure map: " + err.message);
    }
  });

  $("intersection-select").addEventListener("change", () => {
    const iid = $("intersection-select").value;
    if (!iid || !latestState || !latestState.intersections) return;
    selectIntersectionById(iid, latestState.intersections);
  });

  const btnReportAccident = $("btn-report-accident");
  if (btnReportAccident) {
    btnReportAccident.addEventListener("click", async () => {
      const intersection_id = $("accident-intersection").value || "I1";
      const severity = $("accident-severity").value || "medium";
      try {
        await postJSON("/accidents", { intersection_id, severity });
      } catch (err) {
        alert("Failed to report accident: " + err.message);
      }
    });
  }

  const btnProcessVideo = $("btn-process-video");
  if (btnProcessVideo) {
    btnProcessVideo.addEventListener("click", async () => {
      const files = {
        north: $("video-north").files[0],
        south: $("video-south").files[0],
        east: $("video-east").files[0],
        west: $("video-west").files[0]
      };

      const formData = new FormData();
      formData.append("intersection_id", $("intersection-select")?.value || "I1");
      
      let hasFile = false;
      for (const [dir, file] of Object.entries(files)) {
        if (file) {
          formData.append(`video_${dir}`, file);
          hasFile = true;
        }
      }

      if (!hasFile) {
        alert("Please select at least one video to process.");
        return;
      }

      const statusEl = $("ai-processing-status");
      statusEl.style.display = "block";
      statusEl.textContent = "Analyzing videos... Please wait. This may take a while.";
      btnProcessVideo.disabled = true;

      try {
        const res = await fetch(apiBase + "/process-videos", {
          method: "POST",
          body: formData
        });
        
        if (!res.ok) {
          throw new Error("Video processing failed: " + res.status);
        }
        
        const result = await res.json();
        statusEl.textContent = "Processing complete! Data updated.";
        setTimeout(() => {
          statusEl.style.display = "none";
        }, 5000);
      } catch (err) {
        statusEl.textContent = "Error: " + err.message;
        statusEl.style.color = "#ef4444";
      } finally {
        btnProcessVideo.disabled = false;
        // Optionally clear inputs
        // $("video-north").value = ""; $("video-south").value = "";
        // $("video-east").value = ""; $("video-west").value = "";
      }
    });
  }
}

window.addEventListener("DOMContentLoaded", () => {
  setupControls();
  setupWebSocket();
});

