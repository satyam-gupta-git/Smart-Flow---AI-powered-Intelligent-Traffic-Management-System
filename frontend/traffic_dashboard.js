// =====================================================================
// Smart Flow – AI Traffic Management System
// Frontend Logic v3 – Clean multi-page SPA
// =====================================================================

const apiBase = "";

function $(id) { return document.getElementById(id); }

async function postJSON(path, body) {
  const res = await fetch(apiBase + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Request failed: " + res.status);
  return res.json();
}

function directionLabel(dir) {
  return { north:"North", south:"South", east:"East", west:"West" }[dir] || dir;
}

// =====================================================================
// STATE
// =====================================================================
let latestState = null;
let selectedIntersectionId = null;
let paused = false;

// =====================================================================
// PAGE ROUTING
// =====================================================================
const PAGE_META = {
  "dashboard":      "Dashboard",
  "traffic-control":"Traffic Control",
  "ai-video":       "AI Video Processing",
  "simulator":      "Intersection Simulator",
  "police":         "Traffic Police",
  "anpr":           "Number Plate Detection",
  "analytics":      "AI Analytics",
};

function showPage(name) {
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));

  const page = $("page-" + name);
  if (page) page.classList.add("active");

  const navItem = $("nav-" + name);
  if (navItem) navItem.classList.add("active");

  const bc = $("breadcrumb-current");
  if (bc && PAGE_META[name]) bc.textContent = PAGE_META[name];

  if (latestState) updateSignalUI(latestState);
}

// =====================================================================
// INTERSECTION UI
// =====================================================================
function updateIntersectionDetail(intersection) {
  if (!intersection) return;
  const { vehicles, green_times, signals, active_direction, remaining_time, congestion_level, emergency } = intersection;

  ["north","south","east","west"].forEach((dir) => {
    const signalEl = $("signal-" + dir);
    if (!signalEl) return;
    const laneSignals = signals?.[dir];
    const color = laneSignals?.color || "RED";
    const timer = laneSignals?.timer || 0;

    const lights = { red: signalEl.querySelector(".light.red"), yellow: signalEl.querySelector(".light.yellow"), green: signalEl.querySelector(".light.green") };
    Object.values(lights).forEach(l => l && l.classList.remove("on"));
    if (color === "GREEN" && lights.green)       lights.green.classList.add("on");
    else if (color === "YELLOW" && lights.yellow) lights.yellow.classList.add("on");
    else if (lights.red)                          lights.red.classList.add("on");

    const timerEl = $("timer-" + dir);
    if (timerEl) timerEl.textContent = timer + "s";

    const count = vehicles?.[dir] || 0;
    const vEl = $("vehicles-" + dir);
    if (vEl) vEl.textContent = count + " vehicles";

    const streamEl = $("stream-" + dir);
    if (streamEl) streamEl.classList.toggle("moving", color === "GREEN" && count > 0);
  });

  // Dashboard stat cards
  setText("dashboard-active",    directionLabel(active_direction));
  setText("dashboard-timer",     (remaining_time || 0) + "s");
  setText("priority-active-dash",directionLabel(active_direction));
  setText("summary-north",       vehicles?.north || 0);
  setText("summary-south",       vehicles?.south || 0);
  setText("summary-east",        vehicles?.east  || 0);
  setText("summary-west",        vehicles?.west  || 0);

  // Traffic control page
  setText("ctrl-north", vehicles?.north || 0);
  setText("ctrl-south", vehicles?.south || 0);
  setText("ctrl-east",  vehicles?.east  || 0);
  setText("ctrl-west",  vehicles?.west  || 0);
  setText("green-north", (green_times?.north || 0) + "s");
  setText("green-south", (green_times?.south || 0) + "s");
  setText("green-east",  (green_times?.east  || 0) + "s");
  setText("green-west",  (green_times?.west  || 0) + "s");

  // Simulator side cards
  setText("sim-active", directionLabel(active_direction));
  setText("sim-timer",  (remaining_time || 0) + "s");
  setClassCongestion("sim-congestion", congestion_level);
  setText("sim-green-north", (green_times?.north || 0) + "s");
  setText("sim-green-south", (green_times?.south || 0) + "s");
  setText("sim-green-east",  (green_times?.east  || 0) + "s");
  setText("sim-green-west",  (green_times?.west  || 0) + "s");

  // Congestion indicator
  setClassCongestion("congestion-indicator", congestion_level);

  // Intersection view title
  const t = $("intersection-view-title");
  if (t && selectedIntersectionId) t.textContent = selectedIntersectionId;

  // Center status
  const cs = $("center-status");
  if (cs) {
    if (emergency?.active && emergency?.direction) {
      cs.textContent = "EMERGENCY: " + directionLabel(emergency.direction) + " has priority";
      cs.classList.add("emergency");
    } else {
      cs.textContent = "Normal: " + directionLabel(active_direction) + " is GREEN";
      cs.classList.remove("emergency");
    }
  }
}

function setText(id, val) {
  const el = $(id);
  if (el) el.textContent = val;
}

function setClassCongestion(id, level) {
  const el = $(id);
  if (!el) return;
  el.textContent = level || "Low";
  el.classList.remove("congestion-low","congestion-medium","congestion-high");
  el.classList.add("congestion-" + (level || "Low").toLowerCase());
}

// =====================================================================
// CITY MAP
// =====================================================================
const MAP_POSITIONS = {
  I1:[120,85],  I2:[230,85],  I3:[350,85],  I4:[480,85],  I5:[580,85],
  I6:[120,200], I7:[230,200], I8:[350,200], I9:[480,200], I10:[580,200],
  I11:[120,315],I12:[230,315],I13:[350,315],I14:[480,315],I15:[580,315],
};

function renderCityMap(intersections) {
  const g = $("map-intersection-nodes");
  if (!g) return;
  g.innerHTML = "";
  Object.keys(intersections).forEach(iid => {
    const pos = MAP_POSITIONS[iid];
    if (!pos) return;
    const [cx, cy] = pos;
    const isel = intersections[iid];
    const congClass = isel.congestion_level === "High" ? "congestion-high"
      : isel.congestion_level === "Medium" ? "congestion-medium" : "congestion-low";

    const node = document.createElementNS("http://www.w3.org/2000/svg","g");
    node.setAttribute("class", "map-intersection-node" + (selectedIntersectionId === iid ? " selected" : ""));
    node.setAttribute("transform", `translate(${cx},${cy})`);
    node.style.cursor = "pointer";

    const circle = document.createElementNS("http://www.w3.org/2000/svg","circle");
    circle.setAttribute("r", 18);
    circle.setAttribute("class","map-node-circle");

    const label = document.createElementNS("http://www.w3.org/2000/svg","text");
    label.setAttribute("text-anchor","middle");
    label.setAttribute("dy","0.35em");
    label.setAttribute("class","map-node-label");
    label.textContent = iid;

    const dot = document.createElementNS("http://www.w3.org/2000/svg","circle");
    dot.setAttribute("r", 4);
    dot.setAttribute("cy", -11);
    dot.setAttribute("class", "map-node-dot " + congClass);

    node.appendChild(circle);
    node.appendChild(label);
    node.appendChild(dot);
    node.addEventListener("click", () => selectIntersection(iid, intersections));
    g.appendChild(node);
  });
}

// =====================================================================
// INTERSECTION SELECT
// =====================================================================
function selectIntersection(iid, intersections) {
  selectedIntersectionId = iid;
  ["intersection-select","intersection-select-sim"].forEach(sid => {
    const s = $(sid); if (s) s.value = iid;
  });

  const lbl = $("selected-intersection-label");
  if (lbl) { const s = lbl.querySelector("strong"); if (s) s.textContent = iid; }
  const t = $("intersection-view-title");
  if (t) t.textContent = iid;

  const isel = intersections[iid];
  if (isel) {
    const inN = $("input-north"), inS = $("input-south"), inE = $("input-east"), inW = $("input-west");
    if (inN) inN.value = isel.vehicles?.north || 0;
    if (inS) inS.value = isel.vehicles?.south || 0;
    if (inE) inE.value = isel.vehicles?.east  || 0;
    if (inW) inW.value = isel.vehicles?.west  || 0;
    if (!paused) updateIntersectionDetail(isel);
  }
  renderCityMap(intersections);
}

function syncSelects(intersections) {
  const ids = Object.keys(intersections);
  ["intersection-select","intersection-select-sim"].forEach(sid => {
    const sel = $(sid);
    if (!sel) return;
    const cur = sel.value;
    sel.innerHTML = "";
    ids.forEach(iid => {
      const opt = document.createElement("option");
      opt.value = iid; opt.textContent = iid;
      sel.appendChild(opt);
    });
    sel.value = selectedIntersectionId || ids[0] || "";
  });
  if (!selectedIntersectionId && ids.length) selectedIntersectionId = ids[0];
}

// =====================================================================
// POLICE / DASHBOARD UI
// =====================================================================
function updatePoliceDashboard(fullState) {
  const intersections = fullState.intersections || {};
  const accidents     = fullState.accidents || [];
  const citySpeed     = fullState.city_average_speed_kmh;
  const ids           = Object.keys(intersections);
  const maxVehicles   = Math.max(1, ...ids.map(iid => intersections[iid].total_vehicles || 0));

  // Congestion maps
  ["congestion-map","dash-congestion-map"].forEach(cid => {
    const el = $(cid);
    if (!el) return;
    el.innerHTML = "";
    ids.forEach(iid => {
      const level = intersections[iid].congestion_level || "Low";
      const cell = document.createElement("div");
      cell.className = "congestion-cell congestion-" + level.toLowerCase();
      cell.textContent = iid;
      el.appendChild(cell);
    });
  });

  // Accident alerts
  const alertsEl = $("accident-alerts");
  if (alertsEl) {
    alertsEl.innerHTML = accidents.length === 0
      ? `<p class="no-alerts">No active accidents</p>`
      : accidents.map(a => `
          <div class="accident-item">
            <span>${a.intersection_id} &mdash; <strong style="color:${a.severity==='high'?'#ef4444':a.severity==='medium'?'#f97316':'#eab308'}">${a.severity}</strong></span>
            <button class="btn btn-sm btn-secondary clear-accident" data-id="${a.id}">Clear</button>
          </div>`).join("");
    alertsEl.querySelectorAll(".clear-accident").forEach(btn =>
      btn.addEventListener("click", () => postJSON("/accidents/clear", { id: +btn.dataset.id }).catch(()=>{}))
    );
  }

  // Density heatmap
  const heatEl = $("density-heatmap");
  if (heatEl) {
    heatEl.innerHTML = "";
    ids.forEach(iid => {
      const total = intersections[iid].total_vehicles || 0;
      const intensity = maxVehicles > 0 ? total / maxVehicles : 0;
      const cell = document.createElement("div");
      cell.className = "density-cell";
      cell.style.background = `rgba(239,68,68,${0.15 + 0.8 * intensity})`;
      cell.textContent = total;
      cell.title = `${iid}: ${total} vehicles`;
      heatEl.appendChild(cell);
    });
  }

  // Speed
  const speedStr = citySpeed != null ? `${citySpeed} km/h` : "— km/h";
  setText("city-average-speed",       speedStr);
  setText("city-average-speed-police",speedStr);
  setText("stat-city-speed",          speedStr);

  const buildSpeedList = (containerId) => {
    const el = $(containerId);
    if (!el) return;
    el.innerHTML = "";
    ids.forEach(iid => {
      const speed = intersections[iid].average_speed_kmh;
      const row = document.createElement("div");
      row.className = "speed-row";
      row.innerHTML = `<span>${iid}</span><strong>${speed != null ? speed + " km/h" : "—"}</strong>`;
      el.appendChild(row);
    });
  };
  buildSpeedList("speed-by-intersection");
  buildSpeedList("speed-by-intersection-police");

  // Accident selector
  const accSel = $("accident-intersection");
  if (accSel && accSel.options.length !== ids.length) {
    accSel.innerHTML = ids.map(iid => `<option value="${iid}">${iid}</option>`).join("");
  }

  // Dashboard stat cards
  setText("stat-intersections",  ids.length);
  setText("stat-accidents",      accidents.length);
  const totalVehicles = ids.reduce((s,id) => s + (intersections[id].total_vehicles||0), 0);
  setText("stat-total-vehicles", totalVehicles);

  // Analytics stat cards
  setText("analytics-stat-intersections", ids.length);
  setText("analytics-stat-vehicles",       totalVehicles);
  setText("analytics-stat-accidents",      accidents.length);

  // Analytics speed list
  const aSpeedList = $("analytics-speed-list");
  if (aSpeedList) {
    aSpeedList.innerHTML = "";
    ids.forEach(iid => {
      const isel = intersections[iid];
      const cong = isel.congestion_level || "Low";
      const tClass = cong==="High"?"trend-down":cong==="Medium"?"trend-flat":"trend-up";
      const row = document.createElement("div");
      row.className = "trend-row";
      row.innerHTML = `
        <span><strong>${iid}</strong> — ${isel.average_speed_kmh != null ? isel.average_speed_kmh + " km/h" : "—"}</span>
        <span class="trend-badge ${tClass}">${cong}</span>`;
      aSpeedList.appendChild(row);
    });
  }

  // Analytics incidents
  const aInc = $("analytics-incidents");
  if (aInc) {
    if (accidents.length === 0) {
      aInc.innerHTML = `<p style="font-size:0.85rem;color:var(--text-muted);">No incidents recorded in current session.</p>`;
    } else {
      aInc.innerHTML = accidents.map(a => {
        const col = a.severity==="high"?"var(--neon-red)":a.severity==="medium"?"#f97316":"var(--neon-yellow)";
        return `<div class="trend-row">
          <span>Accident at <strong>${a.intersection_id}</strong></span>
          <span class="trend-badge" style="color:${col};border-color:${col};background:transparent;">${a.severity}</span>
        </div>`;
      }).join("");
    }
  }
}

// =====================================================================
// MAIN STATE UPDATE
// =====================================================================
function updateSignalUI(fullState) {
  if (paused) return;
  latestState = fullState;
  const intersections = fullState.intersections || {};
  if (!Object.keys(intersections).length) return;

  syncSelects(intersections);
  renderCityMap(intersections);

  const isel = intersections[selectedIntersectionId];
  if (isel) updateIntersectionDetail(isel);

  updatePoliceDashboard(fullState);
}

// =====================================================================
// WEBSOCKET
// =====================================================================
function setupWebSocket() {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${proto}//${window.location.host}/ws`);

  ws.onopen = () => {
    const dot   = $("ws-dot");
    const label = $("ws-status-label");
    if (dot)   dot.style.background = "var(--neon-green)";
    if (label) label.textContent = "Connected";
  };
  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === "state" && msg.data) updateSignalUI(msg.data);
    } catch {}
  };
  ws.onclose = () => {
    const dot   = $("ws-dot");
    const label = $("ws-status-label");
    if (dot)   dot.style.background = "var(--neon-red)";
    if (label) label.textContent = "Reconnecting…";
    setTimeout(setupWebSocket, 3000);
  };
  ws.onerror = () => ws.close();
}

// =====================================================================
// ANPR POLLING
// =====================================================================
function getStatusPill(reason) {
  if (reason.includes("STOLEN"))                                          return ["status-stolen",   reason];
  if (reason.includes("REPEAT") || reason.includes("Violator") || reason.includes("Collision")) return ["status-violator", reason];
  if (reason.includes("Fair"))                                            return ["status-fair",     "Fair / Compliant"];
  return ["status-other", reason];
}

async function fetchChallans() {
  try {
    const res = await fetch(apiBase + "/challans");
    if (!res.ok) return;
    const data = await res.json();
    const challans = data.challans || [];

    // Analytics plate count
    setText("analytics-stat-plates", challans.length);

    // Analytics ANPR summary
    const aSumm = $("analytics-anpr-summary");
    if (aSumm) {
      const stolen   = challans.filter(c => c.reason.includes("STOLEN")).length;
      const violator = challans.filter(c => c.reason.includes("REPEAT")||c.reason.includes("Violator")||c.reason.includes("Collision")).length;
      const fair     = challans.filter(c => c.reason.includes("Fair")).length;
      aSumm.innerHTML = `
        <div class="trend-row"><span>Stolen Vehicles Flagged</span><span class="trend-badge trend-down">${stolen}</span></div>
        <div class="trend-row"><span>Rule Violators</span>        <span class="trend-badge trend-flat">${violator}</span></div>
        <div class="trend-row"><span>Fair / Compliant</span>      <span class="trend-badge trend-up">${fair}</span></div>
        <div class="trend-row"><span>Total Plates Scanned</span>  <span class="trend-badge trend-info">${challans.length}</span></div>`;
    }

    const tbody = $("anpr-logs-body");
    if (!tbody) return;

    if (challans.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="table-empty">No plates detected yet. Process a video to begin.</td></tr>`;
      return;
    }

    tbody.innerHTML = "";
    challans.slice().reverse().forEach(c => {
      const tr = document.createElement("tr");
      const time = new Date(c.timestamp * 1000).toLocaleTimeString();
      const [pillClass, pillLabel] = getStatusPill(c.reason);
      tr.innerHTML = `
        <td style="color:var(--text-dim);">#${c.id}</td>
        <td style="color:var(--text-muted);font-size:0.82rem;">${time}</td>
        <td><span class="plate-badge">${c.plate}</span></td>
        <td style="color:var(--text-muted);font-size:0.85rem;">${c.reason}</td>
        <td style="color:var(--text-muted);">${c.intersection_id}</td>
        <td><span class="status-pill ${pillClass}">${pillLabel}</span></td>`;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("ANPR fetch failed:", err);
  }
}

// =====================================================================
// CONTROLS
// =====================================================================
function setupControls() {

  // Sidebar nav
  document.querySelectorAll(".nav-item[data-page]").forEach(item => {
    item.addEventListener("click", () => showPage(item.dataset.page));
    item.addEventListener("keydown", e => {
      if (e.key === "Enter" || e.key === " ") showPage(item.dataset.page);
    });
  });

  // Sidebar toggle
  const sidebar = $("sidebar");
  const toggle  = $("sidebar-toggle");
  if (sidebar && toggle) {
    toggle.addEventListener("click", () => sidebar.classList.toggle("collapsed"));
  }

  // Intersection selects
  ["intersection-select","intersection-select-sim"].forEach(sid => {
    const sel = $(sid);
    if (sel) sel.addEventListener("change", () => {
      if (latestState?.intersections) selectIntersection(sel.value, latestState.intersections);
    });
  });

  // Update traffic
  const btnCalc = $("btn-calculate");
  if (btnCalc) btnCalc.addEventListener("click", async () => {
    const iid = $("intersection-select")?.value || selectedIntersectionId || "I1";
    try { await postJSON("/traffic-input", { intersection_id: iid,
      north: +($("input-north")?.value||0), south: +($("input-south")?.value||0),
      east:  +($("input-east")?.value||0),  west:  +($("input-west")?.value||0) });
    } catch(e) { alert("Failed: " + e.message); }
  });

  // Reset
  const btnReset = $("btn-reset");
  if (btnReset) btnReset.addEventListener("click", async () => {
    ["input-north","input-south","input-east","input-west"].forEach(id=>{const el=$(id);if(el)el.value=0;});
    const iid = $("intersection-select")?.value || selectedIntersectionId || "I1";
    try { await postJSON("/traffic-input", { intersection_id: iid, north:0, south:0, east:0, west:0 }); }
    catch(e) { alert("Reset failed: " + e.message); }
  });

  // Stop
  const btnStop = $("btn-stop");
  if (btnStop) btnStop.addEventListener("click", () => {
    paused = !paused;
    btnStop.textContent = paused ? "Resume" : "Stop";
    btnStop.className = paused ? "btn btn-secondary" : "btn btn-warning";
    if (!paused && latestState) updateSignalUI(latestState);
  });

  // Emergency
  const btnEmgOn = $("btn-emergency-on");
  if (btnEmgOn) btnEmgOn.addEventListener("click", async () => {
    const dir = $("emergency-direction")?.value;
    const iid = $("intersection-select")?.value || selectedIntersectionId || "I1";
    try { await postJSON("/emergency", { intersection_id: iid, direction: dir, active: true }); }
    catch(e) { alert("Failed: " + e.message); }
  });

  const btnEmgOff = $("btn-emergency-off");
  if (btnEmgOff) btnEmgOff.addEventListener("click", async () => {
    const dir = $("emergency-direction")?.value;
    const iid = $("intersection-select")?.value || selectedIntersectionId || "I1";
    try { await postJSON("/emergency", { intersection_id: iid, direction: dir, active: false }); }
    catch(e) { alert("Failed: " + e.message); }
  });

  // Map count
  const btnMap = $("btn-apply-map");
  if (btnMap) btnMap.addEventListener("click", async () => {
    const count = +($("map-count")?.value||1);
    try { await postJSON("/configure-map", { count }); }
    catch(e) { alert("Failed: " + e.message); }
  });

  // Report accident
  const btnReport = $("btn-report-accident");
  if (btnReport) btnReport.addEventListener("click", async () => {
    const iid  = $("accident-intersection")?.value || "I1";
    const sev  = $("accident-severity")?.value || "medium";
    try { await postJSON("/accidents", { intersection_id: iid, severity: sev }); }
    catch(e) { alert("Failed: " + e.message); }
  });

  // AI Video Processing
  const btnProcess = $("btn-process-video");
  if (btnProcess) btnProcess.addEventListener("click", async () => {
    const files = {
      north: $("video-north")?.files[0],
      south: $("video-south")?.files[0],
      east:  $("video-east")?.files[0],
      west:  $("video-west")?.files[0],
    };
    const formData = new FormData();
    formData.append("intersection_id", $("intersection-select")?.value || selectedIntersectionId || "I1");
    let hasFile = false;
    for (const [dir,file] of Object.entries(files)) {
      if (file) { formData.append(`video_${dir}`, file); hasFile = true; }
    }
    if (!hasFile) { alert("Please select at least one video to process."); return; }

    const status = $("ai-processing-status");
    const btn    = $("btn-process-video");
    if (status) { status.style.display = "block"; status.textContent = "Analyzing videos… Please wait. This may take a while."; status.style.color = "var(--neon-blue)"; }
    if (btn) btn.disabled = true;

    try {
      const res = await fetch(apiBase + "/process-videos", { method: "POST", body: formData });
      if (!res.ok) throw new Error("Processing failed: " + res.status);
      if (status) { status.textContent = "✅ Processing complete! Data has been updated."; status.style.color = "var(--neon-green)"; }
      setTimeout(() => { if (status) status.style.display = "none"; }, 5000);
    } catch(e) {
      if (status) { status.textContent = "❌ Error: " + e.message; status.style.color = "var(--neon-red)"; }
    } finally {
      if (btn) btn.disabled = false;
    }
  });
}

// =====================================================================
// INIT
// =====================================================================
window.addEventListener("DOMContentLoaded", () => {
  setupControls();
  setupWebSocket();
  showPage("dashboard");
  fetchChallans();
  setInterval(fetchChallans, 3000);
});
