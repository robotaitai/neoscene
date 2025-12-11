// neoscene console - app.js

let currentSessionId = null;
let jsonExpanded = true;

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
// JSON Display
// ============================================

function syntaxHighlight(json) {
  if (typeof json !== "string") {
    json = JSON.stringify(json, null, 2);
  }
  
  json = json.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  
  return json.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
    function (match) {
      let cls = "json-number";
      if (/^"/.test(match)) {
        if (/:$/.test(match)) {
          cls = "json-key";
        } else {
          cls = "json-string";
        }
      } else if (/true|false/.test(match)) {
        cls = "json-boolean";
      } else if (/null/.test(match)) {
        cls = "json-null";
      }
      return '<span class="' + cls + '">' + match + "</span>";
    }
  );
}

function updateJsonDisplay(sceneSpec) {
  const jsonDisplay = document.getElementById("json-display");
  if (sceneSpec) {
    const formatted = JSON.stringify(sceneSpec, null, 2);
    jsonDisplay.innerHTML = syntaxHighlight(formatted);
  } else {
    jsonDisplay.innerHTML = '<span style="color: #6b7280;">// No scene generated yet</span>';
  }
}

function toggleJson() {
  const content = document.getElementById("json-content");
  const toggleText = document.getElementById("json-toggle-text");
  
  jsonExpanded = !jsonExpanded;
  
  if (jsonExpanded) {
    content.classList.remove("collapsed");
    toggleText.textContent = "▲";
  } else {
    content.classList.add("collapsed");
    toggleText.textContent = "▼";
  }
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
    updateJsonDisplay(data.scene_spec);

  } catch (e) {
    appendMessage("assistant", "Network error: " + e, true);
    appendOp("NETWORK ERROR", "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Send";
  }
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
});
