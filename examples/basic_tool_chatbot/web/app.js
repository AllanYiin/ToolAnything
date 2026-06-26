const form = document.getElementById("composer");
const input = document.getElementById("messageInput");
const messages = document.getElementById("messages");
const transcriptOutput = document.getElementById("transcriptOutput");
const toolCount = document.getElementById("toolCount");

const starters = [
  "讀取 notes/intro.txt",
  '解析 JSON {"city":"Taipei","count":2}',
  "搜尋 ToolAnything standard tools",
];

function appendMessage(role, text) {
  const item = document.createElement("article");
  item.className = `message ${role}`;
  const label = document.createElement("span");
  label.textContent = role === "user" ? "User" : "Assistant";
  const body = document.createElement("pre");
  body.textContent = text;
  item.append(label, body);
  messages.append(item);
  messages.scrollTop = messages.scrollHeight;
}

function renderStarters() {
  const row = document.createElement("div");
  row.className = "starters";
  for (const starter of starters) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = starter;
    button.addEventListener("click", () => {
      input.value = starter;
      input.focus();
    });
    row.append(button);
  }
  messages.append(row);
}

async function sendMessage(message) {
  appendMessage("user", message);
  input.value = "";
  input.disabled = true;
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const payload = await response.json();
    if (!response.ok || payload.error) {
      throw new Error(payload.error || `HTTP ${response.status}`);
    }
    appendMessage("assistant", payload.reply);
    toolCount.textContent = `tools: ${payload.tools_count}`;
    transcriptOutput.textContent = JSON.stringify(payload.transcript, null, 2);
  } catch (error) {
    appendMessage("assistant", `錯誤：${error.message}`);
  } finally {
    input.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (message) {
    sendMessage(message);
  }
});

renderStarters();
input.focus();
