// neoscene console - app.js

let currentSessionId = null;
let worldRevisions = [];  // list of scene_spec snapshots for this tab

// ============================================
// Message Handling
// ============================================

function appendMessage(role, text, isError = false) {
  const log = document.getElementById("chat-log");
  const div = document.createElement("div");
  
  let className = "msg msg-" + role;
  if (isError) className += " msg-error";
  div.className = className;
  
  const content = document.createElement("div");
  content.textContent = text;
  div.appendChild(content);
  
  const timestamp = document.createElement("div");
  timestamp.className = "msg-timestamp";
  timestamp.textContent = new Date().toLocaleTimeString();
  div.appendChild(timestamp);
  
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

// ============================================
// Ops Log
// ============================================

function appendOp(text, type = "info") {
  const ops = document.getElementById("ops-log");
  const line = document.createElement("div");
  line.className = "op-line";
  
  const now = new Date();
  const ts = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  
  const timeSpan = document.createElement("span");
  timeSpan.className = "op-time";
  timeSpan.textContent = ts;
  
  const textSpan = document.createElement("span");
  textSpan.className = "op-text" + (type === "success" ? " op-success" : type === "error" ? " op-error" : "");
  textSpan.textContent = text;
  
  line.appendChild(timeSpan);
  line.appendChild(textSpan);
  ops.appendChild(line);
  ops.scrollTop = ops.scrollHeight;
}

// ============================================
// Scene Status
// ============================================

function updateSceneStatus(summary) {
  const status = document.getElementById("scene-status");
  
  if (summary && summary.has_scene) {
    status.innerHTML = `
      <div class="status-row">
        <span class="status-label">Name</span>
        <span class="status-value">${summary.scene_name || "unnamed"}</span>
      </div>
      <div class="status-row">
        <span class="status-label">Environment</span>
        <span class="status-value">${summary.environment_asset_id || "-"}</span>
      </div>
      <div class="status-row">
        <span class="status-label">Objects</span>
        <span class="status-value">${summary.object_count ?? 0}</span>
      </div>
      <div class="status-row">
        <span class="status-label">Cameras</span>
        <span class="status-value">${summary.camera_count ?? 0}</span>
      </div>
    `;
  } else {
    status.innerHTML = '<span style="color: #6b7280;">No scene loaded.</span>';
  }
}

// ============================================
// World Model Inspector
// ============================================

function updateWorldModel(scene) {
  const summaryEl = document.getElementById("world-summary");
  const jsonEl = document.getElementById("world-json");
  const historyEl = document.getElementById("world-history");

  if (!summaryEl || !jsonEl || !historyEl) return;

  if (!scene) {
    summaryEl.textContent = "No scene yet.";
    jsonEl.textContent = "// No scene generated";
    historyEl.innerHTML = "";
    worldRevisions = [];
    return;
  }

  // --- build a compact summary of the scene ---
  const envId = scene.environment?.asset_id || "unknown";
  const timestep = scene.physics?.timestep ?? "?";
  const solver = scene.physics?.solver || "?";

  // aggregate objects by asset_id
  const counts = {};
  (scene.objects || []).forEach((obj) => {
    const id = obj.asset_id || "unknown_asset";
    let c = 0;

    if (typeof obj.count === "number") {
      c = obj.count;
    } else if (Array.isArray(obj.instances)) {
      c = obj.instances.length;
    } else if (obj.layout) {
      // Estimate count from layout
      if (obj.layout.type === "grid") {
        c = (obj.layout.rows || 1) * (obj.layout.cols || 1);
      } else if (obj.layout.count) {
        c = obj.layout.count;
      } else {
        c = 1;
      }
    } else {
      c = 1;
    }

    counts[id] = (counts[id] || 0) + c;
  });

  let html =
    `<div><strong>Environment:</strong> <code>${envId}</code></div>` +
    `<div><strong>Physics:</strong> dt=${timestep}, solver=${solver}</div>` +
    `<div style="margin-top:6px;"><strong>Objects:</strong></div>`;

  if (Object.keys(counts).length === 0) {
    html += `<div class="world-object-row" style="color:#6b7280;">none</div>`;
  } else {
    Object.entries(counts).forEach(([id, c]) => {
      html += `<div class="world-object-row"><code>${id}</code> × ${c}</div>`;
    });
  }

  const camCount = Array.isArray(scene.cameras) ? scene.cameras.length : 0;
  html += `<div style="margin-top:6px;"><strong>Cameras:</strong> ${camCount}</div>`;

  summaryEl.innerHTML = html;

  // raw JSON
  jsonEl.textContent = JSON.stringify(scene, null, 2);

  // --- history (this tab only) ---
  worldRevisions.push(scene);

  historyEl.innerHTML = "";
  const startIdx = Math.max(0, worldRevisions.length - 20); // last 20
  for (let i = startIdx; i < worldRevisions.length; i++) {
    const s = worldRevisions[i];
    const name = s.name || "unnamed";
    const objLen = Array.isArray(s.objects) ? s.objects.length : 0;
    const camLen = Array.isArray(s.cameras) ? s.cameras.length : 0;

    const row = document.createElement("div");
    row.className = "history-entry";
    row.innerHTML = `<span class="rev-num">#${i}</span> – <span class="rev-name">${name}</span> – ${objLen} obj, ${camLen} cam`;
    historyEl.appendChild(row);
  }
  
  // Scroll to bottom of history
  historyEl.scrollTop = historyEl.scrollHeight;
}

// ============================================
// Send Message
// ============================================

async function sendMessage() {
  const input = document.getElementById("chat-message");
  const btn = document.getElementById("chat-send");
  const msg = input.value.trim();
  if (!msg) return;

  appendMessage("user", msg);
  appendOp(`> ${msg.substring(0, 50)}${msg.length > 50 ? "..." : ""}`);
  input.value = "";

  btn.disabled = true;
  btn.textContent = "...";

  const payload = {
    session_id: currentSessionId,
    message: msg,
  };

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      const errorMsg = err.detail || "Unknown error from server";
      appendMessage("assistant", "Error: " + errorMsg, true);
      appendOp("ERROR: " + errorMsg.substring(0, 40), "error");
      return;
    }

    const data = await res.json();
    currentSessionId = data.session_id;

    appendMessage("assistant", data.assistant_message);
    appendOp(data.assistant_message, "success");

    updateSceneStatus(data.scene_summary);
    
    // Update world model panel with scene spec
    if (data.scene_spec) {
      updateWorldModel(data.scene_spec);
    }

  } catch (e) {
    appendMessage("assistant", "Network error: " + e, true);
    appendOp("NETWORK ERROR", "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Send";
  }
}

// ============================================
// Sensor Polling
// ============================================

function updateSensors() {
  if (!currentSessionId) return;
  
  fetch("/sensors/" + currentSessionId)
    .then((r) => r.json())
    .then((data) => {
      const el = document.getElementById("sensor-panel");
      if (!data.ok || Object.keys(data.sensors).length === 0) {
        el.innerHTML = '<span class="no-data">No sensors available</span>';
        return;
      }
      
      const sensors = data.sensors || {};
      const lines = Object.entries(sensors).map(([name, val]) => {
        let displayVal;
        if (Array.isArray(val)) {
          displayVal = val.map(v => v.toFixed(2)).join(", ");
        } else {
          displayVal = val.toFixed(3);
        }
        return `<div class="sensor-row"><span class="sensor-name">${name}</span><span class="sensor-value">${displayVal}</span></div>`;
      });
      el.innerHTML = lines.join("");
    })
    .catch(() => {});
}

// ============================================
// Camera Polling
// ============================================

function updateCamera() {
  if (!currentSessionId) return;
  
  const img = document.getElementById("camera-view");
  const placeholder = document.getElementById("camera-placeholder");
  
  // Simple cache-buster to force reload
  const newSrc = "/camera/" + currentSessionId + "?t=" + Date.now();
  
  // Create a temporary image to test if camera is available
  const testImg = new Image();
  testImg.onload = function() {
    img.src = newSrc;
    img.style.display = "block";
    placeholder.style.display = "none";
  };
  testImg.onerror = function() {
    img.style.display = "none";
    placeholder.style.display = "block";
  };
  testImg.src = newSrc;
}

// ============================================
// Initialize
// ============================================

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("chat-send");
  const input = document.getElementById("chat-message");

  btn.addEventListener("click", sendMessage);
  input.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") sendMessage();
  });

  // Initial ops log entry
  appendOp("Console initialized", "info");
  appendOp("Waiting for commands...", "info");
  
  // Start polling for sensors and camera
  setInterval(updateSensors, 500);  // 2 Hz
  setInterval(updateCamera, 1000);  // 1 Hz
});
