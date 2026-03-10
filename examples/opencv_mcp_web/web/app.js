const STORAGE_KEY = "toolanything.opencv_mcp_web.v2";

const serverUrlInput = document.getElementById("serverUrl");
const connectionStatus = document.getElementById("connectionStatus");
const connectionBadge = document.getElementById("connectionBadge");
const toolsList = document.getElementById("tools");
const toolCount = document.getElementById("toolCount");
const footerToolCount = document.getElementById("footerToolCount");
const checkConnectionButton = document.getElementById("checkConnection");
const useLocalServerButton = document.getElementById("useLocalServer");
const useDemoImageButton = document.getElementById("useDemoImage");
const uploadDrop = document.getElementById("uploadDrop");
const fileInput = document.getElementById("fileInput");
const previewImage = document.getElementById("previewImage");
const resultImage = document.getElementById("resultImage");
const resultPlaceholder = document.getElementById("resultPlaceholder");
const toolSelect = document.getElementById("toolSelect");
const toolDescription = document.getElementById("toolDescription");
const resizeSettings = document.getElementById("resizeSettings");
const cannySettings = document.getElementById("cannySettings");
const claheSettings = document.getElementById("claheSettings");
const colorSettings = document.getElementById("colorSettings");
const resizeWidthInput = document.getElementById("resizeWidth");
const resizeHeightInput = document.getElementById("resizeHeight");
const threshold1Input = document.getElementById("threshold1");
const threshold2Input = document.getElementById("threshold2");
const clipLimitInput = document.getElementById("clipLimit");
const tileGridSizeInput = document.getElementById("tileGridSize");
const brightnessInput = document.getElementById("brightness");
const saturationInput = document.getElementById("saturation");
const hueShiftInput = document.getElementById("hueShift");
const runToolButton = document.getElementById("runTool");
const progressBar = document.getElementById("progressBar");
const resultOutput = document.getElementById("resultOutput");
const resultRecords = document.getElementById("resultRecords");
const recordsEmpty = document.getElementById("recordsEmpty");
const tabButtons = document.querySelectorAll(".tab-button");
const tabPanels = document.querySelectorAll(".tab-panel");
const zoomOutButton = document.getElementById("zoomOut");
const zoomInButton = document.getElementById("zoomIn");
const zoomResetButton = document.getElementById("zoomReset");
const zoomLevelLabel = document.getElementById("zoomLevel");
const downloadResultButton = document.getElementById("downloadResult");
const toast = document.getElementById("toast");

let currentImageBase64 = "";
let progressTimer = null;
let zoomLevel = 1;
let availableTools = [];
const recordEntries = [];

class SseNotSupportedError extends Error {
  constructor(payload) {
    super(payload?.reason || "SSE 不支援，已改用替代方案");
    this.name = "SseNotSupportedError";
    this.payload = payload;
  }
}

function saveSettings() {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      serverUrl: serverUrlInput.value.trim(),
      selectedTool: toolSelect.value,
    }),
  );
}

function restoreSettings() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return;
  }
  try {
    const payload = JSON.parse(raw);
    if (payload.serverUrl) {
      serverUrlInput.value = payload.serverUrl;
    }
  } catch {
    localStorage.removeItem(STORAGE_KEY);
  }
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  setTimeout(() => {
    toast.classList.remove("show");
  }, 9000);
}

function setBusyState(isBusy) {
  checkConnectionButton.disabled = isBusy;
  useLocalServerButton.disabled = isBusy;
  runToolButton.disabled = isBusy;
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
  return serverUrlInput.value.trim().replace(/\/$/, "");
}

function setConnectionBadge(state, label) {
  connectionBadge.textContent = label;
  connectionBadge.classList.remove("badge-offline", "badge-online", "badge-checking");
  if (state === "online") {
    connectionBadge.classList.add("badge-online");
  } else if (state === "checking") {
    connectionBadge.classList.add("badge-checking");
  } else {
    connectionBadge.classList.add("badge-offline");
  }
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
    const errorMessage =
      data?.error?.message ||
      data?.error ||
      "連線失敗，請稍後再試";
    throw new Error(errorMessage);
  }
  return data;
}

function parseSseChunk(chunk) {
  const lines = chunk.split("\n");
  let eventName = "message";
  const dataLines = [];
  lines.forEach((line) => {
    if (line.startsWith("event:")) {
      eventName = line.replace("event:", "").trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.replace("data:", "").trim());
    }
  });
  return {
    event: eventName,
    data: dataLines.join("\n"),
  };
}

async function invokeToolSse(baseUrl, payload, handlers) {
  const response = await fetch(`${baseUrl}/invoke/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    if (data?.error === "sse_not_supported") {
      throw new SseNotSupportedError(data);
    }
    const errorMessage = data?.error?.message || "連線失敗，請稍後再試";
    throw new Error(errorMessage);
  }

  const contentType = response.headers.get("Content-Type") || "";
  if (!contentType.includes("text/event-stream")) {
    throw new Error("SSE 連線失敗，請確認伺服器是否支援串流回應");
  }

  if (!response.body) {
    throw new Error("無法取得串流回應");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let streamCompleted = false;

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";

    chunks.forEach((chunk) => {
      const { event, data } = parseSseChunk(chunk);
      if (!data) {
        return;
      }

      try {
        const parsedData = JSON.parse(data);
        if (handlers[event]) {
          handlers[event](parsedData);
        }
        if (event === "done") {
          streamCompleted = true;
        }
      } catch (error) {
        console.warn("無法解析 SSE 資料", error);
      }
    });

    if (streamCompleted) {
      try {
        await reader.cancel();
      } catch (error) {
        console.warn("結束 SSE reader 時發生問題", error);
      }
      break;
    }
  }
}

async function invokeToolJson(baseUrl, payload) {
  const response = await fetch(`${baseUrl}/invoke`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const errorMessage = data?.error?.message || "連線失敗，請稍後再試";
    throw new Error(errorMessage);
  }

  return data;
}

function getToolDefinition(name) {
  return availableTools.find((tool) => tool.name === name) || null;
}

function renderTools(tools) {
  availableTools = tools;
  toolsList.innerHTML = "";
  toolSelect.innerHTML = "";

  if (!tools.length) {
    toolsList.innerHTML = "<li>server 已接通，但目前沒有暴露任何工具</li>";
    toolSelect.innerHTML = '<option value="">沒有可用工具</option>';
    toolCount.textContent = "0";
    footerToolCount.textContent = "0";
    toolDescription.textContent = "目前 server 沒有回傳工具，請確認是用 examples.opencv_mcp_web.server 啟動。";
    toggleSettings();
    return;
  }

  const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  const preferredTool = stored.selectedTool || tools[0].name;

  toolCount.textContent = String(tools.length);
  footerToolCount.textContent = String(tools.length);
  tools.forEach((tool) => {
    const li = document.createElement("li");
    li.textContent = `${tool.name} - ${tool.description || "沒有描述"}`;
    toolsList.appendChild(li);

    const option = document.createElement("option");
    option.value = tool.name;
    option.textContent = tool.name;
    toolSelect.appendChild(option);
  });

  toolSelect.value = tools.some((tool) => tool.name === preferredTool)
    ? preferredTool
    : tools[0].name;
  toggleSettings();
}

function updateToolDescription() {
  const tool = getToolDefinition(toolSelect.value);
  toolDescription.textContent = tool?.description || "請先檢查連線並取得工具。";
}

function toggleSettings() {
  const toolName = toolSelect.value;
  resizeSettings.style.display = toolName === "opencv.resize" ? "block" : "none";
  cannySettings.style.display = toolName === "opencv.canny" ? "block" : "none";
  claheSettings.style.display = toolName === "opencv.clahe" ? "block" : "none";
  colorSettings.style.display = toolName === "opencv.adjust_color" ? "block" : "none";
  updateToolDescription();
  saveSettings();
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
    resultPlaceholder.style.display = "grid";
    resultOutput.textContent = "";
  };
  reader.onerror = () => {
    showToast("圖片讀取失敗，請重新選擇檔案");
  };
  reader.readAsDataURL(file);
}

function createDemoImage() {
  const canvas = document.createElement("canvas");
  canvas.width = 320;
  canvas.height = 200;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("瀏覽器無法建立示範圖片");
  }

  const gradient = ctx.createLinearGradient(0, 0, 320, 200);
  gradient.addColorStop(0, "#1d4ed8");
  gradient.addColorStop(1, "#f97316");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 320, 200);

  ctx.strokeStyle = "rgba(255,255,255,0.92)";
  ctx.lineWidth = 4;
  ctx.strokeRect(18, 18, 284, 164);

  ctx.fillStyle = "rgba(255,255,255,0.9)";
  ctx.font = "bold 28px 'Microsoft JhengHei', sans-serif";
  ctx.fillText("ToolAnything", 26, 110);
  ctx.font = "16px 'Microsoft JhengHei', sans-serif";
  ctx.fillText("OpenCV MCP Demo", 28, 138);

  ctx.beginPath();
  ctx.arc(250, 78, 34, 0, Math.PI * 2);
  ctx.stroke();

  currentImageBase64 = canvas.toDataURL("image/png");
  previewImage.src = currentImageBase64;
  resultImage.src = "";
  resultPlaceholder.style.display = "grid";
  resultOutput.textContent = "";
  showToast("已載入示範圖片，可直接執行工具");
}

function applyResult(payload) {
  resultOutput.textContent = JSON.stringify(
    payload.raw_result || payload.result,
    null,
    2,
  );
  if (payload.raw_result?.image_base64) {
    resultImage.src = payload.raw_result.image_base64;
    resultPlaceholder.style.display = "none";
  } else {
    resultImage.src = "";
    resultPlaceholder.style.display = "grid";
  }
}

function appendRecord({ toolName, status, message }) {
  const timestamp = new Date().toLocaleTimeString("zh-Hant", {
    hour: "2-digit",
    minute: "2-digit",
  });
  recordEntries.unshift({ toolName, status, message, timestamp });
  if (recordEntries.length > 6) {
    recordEntries.pop();
  }

  resultRecords.innerHTML = "";
  recordEntries.forEach((entry) => {
    const li = document.createElement("li");
    li.innerHTML = `
      <strong>${entry.toolName}</strong>
      <div>狀態：${entry.status}</div>
      <div>${entry.message}</div>
      <div class="record-time">${entry.timestamp}</div>
    `;
    resultRecords.appendChild(li);
  });
  recordsEmpty.style.display = recordEntries.length ? "none" : "block";
}

function updateZoom(level) {
  zoomLevel = Math.min(2, Math.max(0.5, level));
  resultImage.style.transform = `scale(${zoomLevel})`;
  zoomLevelLabel.textContent = `${Math.round(zoomLevel * 100)}%`;
}

function switchTab(tabName) {
  tabButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === tabName);
  });
  tabPanels.forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.panel === tabName);
  });
}

async function checkConnection() {
  const baseUrl = getServerUrl();
  if (!baseUrl) {
    showToast("請輸入 MCP Server URL");
    return;
  }

  connectionStatus.textContent = "連線中...";
  setConnectionBadge("checking", "連線中");
  saveSettings();
  setBusyState(true);
  try {
    const health = await fetchJson(`${baseUrl}/health`);
    connectionStatus.textContent = `連線成功：${health.status}`;
    const tools = await fetchJson(`${baseUrl}/tools`);
    const toolEntries = tools.tools || [];
    renderTools(toolEntries);
    setConnectionBadge("online", "已連線");
    if (toolEntries.length) {
      connectionStatus.textContent = `連線成功：${health.status}，共 ${toolEntries.length} 個工具`;
      showToast(`MCP Server 已接通，已取得 ${toolEntries.length} 個工具`);
    } else {
      connectionStatus.textContent = `連線成功：${health.status}，但 tools/list 為 0`;
      showToast("MCP Server 已接通，但目前沒有取得任何工具；請確認 server 啟動模組是否正確");
    }
  } catch (error) {
    connectionStatus.textContent = "連線失敗";
    showToast(error.message);
    setConnectionBadge("offline", "未連線");
  } finally {
    setBusyState(false);
  }
}

async function runTool() {
  if (!currentImageBase64) {
    showToast("請先上傳圖片或點擊「使用示範圖片」");
    return;
  }

  const baseUrl = getServerUrl();
  if (!baseUrl) {
    showToast("請輸入 MCP Server URL");
    return;
  }

  const toolName = toolSelect.value;
  if (!toolName) {
    showToast("請先檢查連線並選擇工具");
    return;
  }

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

  if (toolName === "opencv.clahe") {
    argumentsPayload.clip_limit = Number(clipLimitInput.value);
    argumentsPayload.tile_grid_size = Number(tileGridSizeInput.value);
  }

  if (toolName === "opencv.adjust_color") {
    argumentsPayload.brightness = Number(brightnessInput.value);
    argumentsPayload.saturation = Number(saturationInput.value);
    argumentsPayload.hue_shift = Number(hueShiftInput.value);
  }

  try {
    startProgress();
    runToolButton.disabled = true;
    await invokeToolSse(
      baseUrl,
      { name: toolName, arguments: argumentsPayload },
      {
        progress: (payload) => {
          const progressValue = Math.min(100, Math.max(0, payload.progress || 0));
          setProgress(progressValue);
        },
        result: (payload) => {
          applyResult(payload);
          appendRecord({
            toolName,
            status: "完成",
            message: "工具處理完成",
          });
        },
        error: (payload) => {
          const errorMessage =
            payload?.payload?.error?.message ||
            payload?.payload?.error?.type ||
            "工具執行失敗";
          showToast(errorMessage);
          appendRecord({
            toolName,
            status: "失敗",
            message: errorMessage,
          });
        },
        done: () => {
          stopProgress();
        },
      },
    );
  } catch (error) {
    if (error instanceof SseNotSupportedError) {
      const warning = error.payload?.warning
        ? `提醒：${error.payload.warning}`
        : "已切換相容模式";
      showToast(`偵測到部署環境不支援 inbound SSE，${warning}`);
      try {
        startProgress();
        const response = await invokeToolJson(baseUrl, {
          name: toolName,
          arguments: argumentsPayload,
        });
        applyResult(response);
        appendRecord({
          toolName,
          status: "完成",
          message: "工具處理完成",
        });
      } catch (fallbackError) {
        showToast(fallbackError.message);
        appendRecord({
          toolName,
          status: "失敗",
          message: fallbackError.message,
        });
      } finally {
        stopProgress();
      }
      return;
    }
    stopProgress();
    showToast(error.message);
    appendRecord({
      toolName,
      status: "失敗",
      message: error.message,
    });
  } finally {
    runToolButton.disabled = false;
  }
}

function init() {
  const queryServer = new URLSearchParams(window.location.search).get("server");
  serverUrlInput.value = queryServer || window.location.origin;
  restoreSettings();
  toggleSettings();
  setConnectionBadge("offline", "未連線");

  checkConnectionButton.addEventListener("click", checkConnection);
  useLocalServerButton.addEventListener("click", async () => {
    serverUrlInput.value = "http://127.0.0.1:9091";
    saveSettings();
    await checkConnection();
  });
  useDemoImageButton.addEventListener("click", createDemoImage);
  serverUrlInput.addEventListener("change", saveSettings);
  fileInput.addEventListener("change", handleFileChange);
  toolSelect.addEventListener("change", toggleSettings);
  runToolButton.addEventListener("click", runTool);
  tabButtons.forEach((button) => {
    button.addEventListener("click", () => switchTab(button.dataset.tab));
  });
  zoomOutButton.addEventListener("click", () => updateZoom(zoomLevel - 0.1));
  zoomInButton.addEventListener("click", () => updateZoom(zoomLevel + 0.1));
  zoomResetButton.addEventListener("click", () => updateZoom(1));
  downloadResultButton.addEventListener("click", () => {
    if (!resultImage.src) {
      showToast("目前沒有可下載的結果圖片");
      return;
    }
    const link = document.createElement("a");
    link.href = resultImage.src;
    link.download = "opencv-result.png";
    link.click();
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    uploadDrop.addEventListener(eventName, (event) => {
      event.preventDefault();
      uploadDrop.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach((eventName) => {
    uploadDrop.addEventListener(eventName, (event) => {
      event.preventDefault();
      uploadDrop.classList.remove("dragover");
    });
  });
  uploadDrop.addEventListener("drop", (event) => {
    const file = event.dataTransfer?.files?.[0];
    if (!file) {
      return;
    }
    fileInput.files = event.dataTransfer.files;
    handleFileChange({ target: { files: [file] } });
  });

  updateZoom(1);
}

init();
