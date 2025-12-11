// neoscene/app/static/app.js

let currentSessionId = null;
let jsonExpanded = false;

function appendMessage(role, text) {
  const log = document.getElementById("chat-log");
  const div = document.createElement("div");
  div.className = "msg " + (role === "user" ? "msg-user" : "msg-assistant");
  div.textContent = text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function syntaxHighlight(json) {
  // Add syntax highlighting to JSON
  if (typeof json !== "string") {
    json = JSON.stringify(json, null, 2);
  }
  
  // Escape HTML
  json = json.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  
  // Add color spans
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
    jsonDisplay.textContent = "No scene generated yet.";
  }
}

function toggleJson() {
  const content = document.getElementById("json-content");
  const toggleText = document.getElementById("json-toggle-text");
  
  jsonExpanded = !jsonExpanded;
  
  if (jsonExpanded) {
    content.classList.remove("collapsed");
    toggleText.textContent = "▲ Hide";
  } else {
    content.classList.add("collapsed");
    toggleText.textContent = "▼ Show";
  }
}

async function sendMessage() {
  const input = document.getElementById("chat-message");
  const btn = document.getElementById("chat-send");
  const msg = input.value.trim();
  if (!msg) return;

  appendMessage("user", msg);
  input.value = "";

  btn.disabled = true;
  btn.textContent = "Generating...";

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
      appendMessage(
        "assistant",
        "Error: " + (err.detail || "unknown error from server")
      );
      return;
    }

    const data = await res.json();
    currentSessionId = data.session_id;

    appendMessage("assistant", data.assistant_message);

    // Update scene status
    const status = document.getElementById("scene-status");
    const s = data.scene_summary;
    if (s && s.has_scene) {
      status.innerHTML =
        "<p><strong>Name:</strong> " + (s.scene_name || "unnamed") + "</p>" +
        "<p><strong>Environment:</strong> " + (s.environment_asset_id || "-") + "</p>" +
        "<p><strong>Objects:</strong> " + (s.object_count ?? 0) + "</p>" +
        "<p><strong>Cameras:</strong> " + (s.camera_count ?? 0) + "</p>";
    } else {
      status.textContent = "No scene yet.";
    }

    // Update JSON display
    updateJsonDisplay(data.scene_spec);
    
    // Auto-expand JSON on first scene
    if (!jsonExpanded && data.scene_spec) {
      toggleJson();
    }

  } catch (e) {
    appendMessage("assistant", "Network error: " + e);
  } finally {
    btn.disabled = false;
    btn.textContent = "Send";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("chat-send");
  const input = document.getElementById("chat-message");

  btn.addEventListener("click", sendMessage);
  input.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") sendMessage();
  });
});
