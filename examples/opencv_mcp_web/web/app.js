const serverUrlInput = document.getElementById("serverUrl");
const connectionStatus = document.getElementById("connectionStatus");
const toolsList = document.getElementById("tools");
const checkConnectionButton = document.getElementById("checkConnection");
const fileInput = document.getElementById("fileInput");
const previewImage = document.getElementById("previewImage");
const resultImage = document.getElementById("resultImage");
const toolSelect = document.getElementById("toolSelect");
const resizeSettings = document.getElementById("resizeSettings");
const cannySettings = document.getElementById("cannySettings");
const resizeWidthInput = document.getElementById("resizeWidth");
const resizeHeightInput = document.getElementById("resizeHeight");
const threshold1Input = document.getElementById("threshold1");
const threshold2Input = document.getElementById("threshold2");
const runToolButton = document.getElementById("runTool");
const progressBar = document.getElementById("progressBar");
const resultOutput = document.getElementById("resultOutput");
const toast = document.getElementById("toast");

let currentImageBase64 = "";
let progressTimer = null;

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  setTimeout(() => {
    toast.classList.remove("show");
  }, 8000);
}

function setProgress(value) {
  progressBar.value = value;
}

function startProgress() {
  setProgress(10);
  clearInterval(progressTimer);
  progressTimer = setInterval(() => {
    if (progressBar.value < 90) {
      progressBar.value += 5;
    }
  }, 300);
}

function stopProgress() {
  clearInterval(progressTimer);
  setProgress(100);
  setTimeout(() => setProgress(0), 500);
}

function getServerUrl() {
  return serverUrlInput.value.trim();
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const errorMessage = data?.error?.message || "連線失敗，請稍後再試";
    throw new Error(errorMessage);
  }
  return data;
}

async function checkConnection() {
  const baseUrl = getServerUrl();
  if (!baseUrl) {
    showToast("請輸入 MCP Server URL");
    return;
  }

  connectionStatus.textContent = "連線中...";
  try {
    const health = await fetchJson(`${baseUrl}/health`);
    connectionStatus.textContent = `連線成功：${health.status}`;
    const tools = await fetchJson(`${baseUrl}/tools`);
    renderTools(tools.tools || []);
  } catch (error) {
    connectionStatus.textContent = "連線失敗";
    showToast(error.message);
  }
}

function renderTools(tools) {
  toolsList.innerHTML = "";
  if (!tools.length) {
    toolsList.innerHTML = "<li>尚未取得工具</li>";
    return;
  }

  tools.forEach((tool) => {
    const li = document.createElement("li");
    li.textContent = `${tool.name} - ${tool.description}`;
    toolsList.appendChild(li);
  });
}

function handleFileChange(event) {
  const file = event.target.files?.[0];
  if (!file) {
    return;
  }

  const reader = new FileReader();
  reader.onload = () => {
    currentImageBase64 = reader.result;
    previewImage.src = currentImageBase64;
    resultImage.src = "";
    resultOutput.textContent = "";
  };
  reader.onerror = () => {
    showToast("圖片讀取失敗，請重新選擇檔案");
  };
  reader.readAsDataURL(file);
}

function toggleSettings() {
  const toolName = toolSelect.value;
  resizeSettings.style.display = toolName === "opencv.resize" ? "block" : "none";
  cannySettings.style.display = toolName === "opencv.canny" ? "block" : "none";
}

async function runTool() {
  if (!currentImageBase64) {
    showToast("請先上傳圖片");
    return;
  }

  const baseUrl = getServerUrl();
  if (!baseUrl) {
    showToast("請輸入 MCP Server URL");
    return;
  }

  const toolName = toolSelect.value;
  const argumentsPayload = { image_base64: currentImageBase64 };

  if (toolName === "opencv.resize") {
    const width = resizeWidthInput.value ? Number(resizeWidthInput.value) : null;
    const height = resizeHeightInput.value ? Number(resizeHeightInput.value) : null;
    argumentsPayload.target_width = width;
    argumentsPayload.target_height = height;
  }

  if (toolName === "opencv.canny") {
    argumentsPayload.threshold1 = Number(threshold1Input.value);
    argumentsPayload.threshold2 = Number(threshold2Input.value);
  }

  try {
    startProgress();
    runToolButton.disabled = true;
    const result = await fetchJson(`${baseUrl}/invoke`, {
      method: "POST",
      body: JSON.stringify({
        name: toolName,
        arguments: argumentsPayload,
      }),
    });

    resultOutput.textContent = JSON.stringify(result.raw_result || result.result, null, 2);

    if (result.raw_result?.image_base64) {
      resultImage.src = result.raw_result.image_base64;
    } else {
      resultImage.src = "";
    }
  } catch (error) {
    showToast(error.message);
  } finally {
    stopProgress();
    runToolButton.disabled = false;
  }
}

function init() {
  serverUrlInput.value = window.location.origin;
  toggleSettings();
  checkConnectionButton.addEventListener("click", checkConnection);
  fileInput.addEventListener("change", handleFileChange);
  toolSelect.addEventListener("change", toggleSettings);
  runToolButton.addEventListener("click", runTool);
}

init();
