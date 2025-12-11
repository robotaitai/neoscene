// neoscene/app/static/app.js

let currentSessionId = null;

function appendMessage(role, text) {
  const log = document.getElementById("chat-log");
  const div = document.createElement("div");
  div.className = "msg " + (role === "user" ? "msg-user" : "msg-assistant");
  div.textContent = text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

async function sendMessage() {
  const input = document.getElementById("chat-message");
  const msg = input.value.trim();
  if (!msg) return;

  appendMessage("user", msg);
  input.value = "";

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

    const status = document.getElementById("scene-status");
    const s = data.scene_summary;
    if (s && s.has_scene) {
      status.innerHTML =
        "<p><strong>Scene:</strong> " +
        (s.scene_name || "unnamed") +
        "</p>" +
        "<p><strong>Environment:</strong> " +
        (s.environment_asset_id || "-") +
        "</p>" +
        "<p><strong>Objects:</strong> " +
        (s.object_count ?? 0) +
        "</p>" +
        "<p><strong>Cameras:</strong> " +
        (s.camera_count ?? 0) +
        "</p>";
    } else {
      status.textContent = "No scene yet.";
    }
  } catch (e) {
    appendMessage("assistant", "Network error: " + e);
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
