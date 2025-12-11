// Keep session_id across messages
let currentSessionId = null;

function appendMessage(role, text) {
  const log = document.getElementById("chat-log");
  const div = document.createElement("div");
  div.className = `msg msg-${role}`;
  div.textContent = `${role === "user" ? "You" : "Neoscene"}: ${text}`;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

async function sendMessage() {
  const input = document.getElementById("chat-message");
  const btn = document.getElementById("chat-send");
  const msg = input.value.trim();
  if (!msg) return;

  appendMessage("user", msg);
  input.value = "";

  // Disable button while processing
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
      appendMessage("assistant", `Error: ${err.detail || "Unknown error"}`);
      return;
    }

    const data = await res.json();
    currentSessionId = data.session_id;

    appendMessage("assistant", data.assistant_message);

    // Update scene status pane
    const statusEl = document.getElementById("scene-status");
    const s = data.scene_summary;
    if (s.has_scene) {
      statusEl.innerHTML = `
        <p><strong>Scene:</strong> ${s.scene_name}</p>
        <p><strong>Environment:</strong> ${s.environment_asset_id}</p>
        <p><strong>Objects:</strong> ${s.object_count}</p>
        <p><strong>Cameras:</strong> ${s.camera_count}</p>
        <p class="session-id"><strong>Session:</strong> ${currentSessionId}</p>
      `;
    } else {
      statusEl.textContent = "No scene yet.";
    }
  } catch (err) {
    appendMessage("assistant", `Error: ${err.message}`);
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

