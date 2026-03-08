const STORAGE_KEY = "toolanything.inspect.settings.v1";

const state = {
  tools: [],
  selectedTool: null,
  lastTrace: [],
  traceFilter: "",
  toolFilter: "",
};

const elements = {
  transportMode: document.getElementById("transportMode"),
  httpFields: document.getElementById("httpFields"),
  stdioFields: document.getElementById("stdioFields"),
  serverUrl: document.getElementById("serverUrl"),
  serverCommand: document.getElementById("serverCommand"),
  userId: document.getElementById("userId"),
  timeoutSeconds: document.getElementById("timeoutSeconds"),
  connectionBadge: document.getElementById("connectionBadge"),
  testConnectionButton: document.getElementById("testConnectionButton"),
  loadToolsButton: document.getElementById("loadToolsButton"),
  reportSummary: document.getElementById("reportSummary"),
  reportSteps: document.getElementById("reportSteps"),
  capabilityServer: document.getElementById("capabilityServer"),
  capabilityGrid: document.getElementById("capabilityGrid"),
  toolSummary: document.getElementById("toolSummary"),
  toolFilterInput: document.getElementById("toolFilterInput"),
  toolSelect: document.getElementById("toolSelect"),
  toolDescription: document.getElementById("toolDescription"),
  schemaForm: document.getElementById("schemaForm"),
  callToolButton: document.getElementById("callToolButton"),
  resultViewer: document.getElementById("resultViewer"),
  toolList: document.getElementById("toolList"),
  traceTimeline: document.getElementById("traceTimeline"),
  traceFilterInput: document.getElementById("traceFilterInput"),
  copyTraceButton: document.getElementById("copyTraceButton"),
  exportTraceButton: document.getElementById("exportTraceButton"),
  apiKey: document.getElementById("apiKey"),
  modelName: document.getElementById("modelName"),
  temperature: document.getElementById("temperature"),
  systemPrompt: document.getElementById("systemPrompt"),
  userPrompt: document.getElementById("userPrompt"),
  runLlmButton: document.getElementById("runLlmButton"),
  llmTimeline: document.getElementById("llmTimeline"),
  resetStateButton: document.getElementById("resetStateButton"),
  reportStepTemplate: document.getElementById("reportStepTemplate"),
  schemaFieldTemplate: document.getElementById("schemaFieldTemplate"),
};

function setBadge(kind, text) {
  elements.connectionBadge.textContent = text;
  elements.connectionBadge.className = `badge badge-${kind}`;
}

function saveSettings() {
  const payload = {
    mode: elements.transportMode.value,
    url: elements.serverUrl.value,
    command: elements.serverCommand.value,
    user_id: elements.userId.value,
    timeout: elements.timeoutSeconds.value,
    model: elements.modelName.value,
    temperature: elements.temperature.value,
    system_prompt: elements.systemPrompt.value,
    user_prompt: elements.userPrompt.value,
    tool_filter: elements.toolFilterInput.value,
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

function restoreSettings() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return;
  }
  try {
    const payload = JSON.parse(raw);
    elements.transportMode.value = payload.mode || "http";
    elements.serverUrl.value = payload.url || "";
    elements.serverCommand.value = payload.command || "";
    elements.userId.value = payload.user_id || "";
    elements.timeoutSeconds.value = payload.timeout || "8";
    elements.modelName.value = payload.model || "";
    elements.temperature.value = payload.temperature || "0.2";
    elements.systemPrompt.value = payload.system_prompt || "";
    elements.userPrompt.value = payload.user_prompt || "";
    elements.toolFilterInput.value = payload.tool_filter || "";
  } catch {
    localStorage.removeItem(STORAGE_KEY);
  }
}

function resetState() {
  localStorage.removeItem(STORAGE_KEY);
  window.location.reload();
}

function getConnectionPayload() {
  return {
    mode: elements.transportMode.value,
    url: elements.serverUrl.value.trim(),
    command: elements.serverCommand.value.trim(),
    user_id: elements.userId.value.trim(),
    timeout: Number(elements.timeoutSeconds.value || 8),
  };
}

function updateTransportFields() {
  const isHttp = elements.transportMode.value === "http";
  elements.httpFields.classList.toggle("hidden", !isHttp);
  elements.stdioFields.classList.toggle("hidden", isHttp);
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const errorMessage = data?.error?.message || "請求失敗";
    const detailText = data?.error?.details ? `\n${JSON.stringify(data.error.details, null, 2)}` : "";
    throw new Error(`${errorMessage}${detailText}`);
  }
  return data;
}

function renderJson(target, payload) {
  target.textContent = JSON.stringify(payload, null, 2);
}

function renderTrace(trace) {
  state.lastTrace = trace || [];
  const filteredTrace = getFilteredTrace();
  if (!filteredTrace.length) {
    elements.traceTimeline.className = "trace-list empty-state";
    elements.traceTimeline.textContent = state.lastTrace.length
      ? "目前的篩選條件沒有符合的 trace。"
      : "最近一次互動沒有可顯示的 trace。";
    return;
  }
  elements.traceTimeline.className = "trace-list";
  elements.traceTimeline.innerHTML = "";
  filteredTrace.forEach((entry, index) => {
    const article = document.createElement("article");
    article.className = `trace-entry ${entry.direction}`;
    article.innerHTML = `
      <strong>#${index + 1} ${entry.direction} / ${entry.kind}</strong>
      <p class="entry-meta">${entry.transport} · ${entry.at_ms}ms</p>
      <pre>${JSON.stringify(entry.payload, null, 2)}</pre>
    `;
    elements.traceTimeline.appendChild(article);
  });
}

function getFilteredTrace() {
  const keyword = state.traceFilter.trim().toLowerCase();
  if (!keyword) {
    return state.lastTrace;
  }
  return state.lastTrace.filter((entry) =>
    JSON.stringify(entry).toLowerCase().includes(keyword)
  );
}

async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "absolute";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}

async function handleCopyTrace() {
  const filteredTrace = getFilteredTrace();
  if (!filteredTrace.length) {
    throw new Error("目前沒有可複製的 trace");
  }
  await copyText(JSON.stringify(filteredTrace, null, 2));
}

function handleExportTrace() {
  const filteredTrace = getFilteredTrace();
  if (!filteredTrace.length) {
    throw new Error("目前沒有可匯出的 trace");
  }
  const blob = new Blob([JSON.stringify(filteredTrace, null, 2)], {
    type: "application/json;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `toolanything-trace-${Date.now()}.json`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function renderCapabilities(initializePayload) {
  if (!initializePayload || typeof initializePayload !== "object") {
    elements.capabilityServer.textContent = "尚未取得 initialize 資訊";
    elements.capabilityGrid.className = "capability-grid empty-state";
    elements.capabilityGrid.textContent = "載入工具或完成連線檢查後，這裡會顯示 server capabilities。";
    return;
  }

  const capabilities = initializePayload.capabilities || {};
  const serverInfo = initializePayload.serverInfo || {};
  const protocolVersion = initializePayload.protocolVersion || "unknown";
  const dependencies = initializePayload.dependencies || {};
  const rows = [
    { key: "tools", title: "Tools", supported: !!capabilities.tools, detail: capabilities.tools || "未提供" },
    { key: "resources", title: "Resources", supported: !!capabilities.resources, detail: capabilities.resources || "未提供" },
    { key: "prompts", title: "Prompts", supported: !!capabilities.prompts, detail: capabilities.prompts || "未提供" },
    { key: "logging", title: "Logging", supported: !!capabilities.logging, detail: capabilities.logging || "未提供" },
    { key: "completions", title: "Completions", supported: !!capabilities.completions, detail: capabilities.completions || "未提供" },
    {
      key: "dependencies",
      title: "Dependencies",
      supported: true,
      detail: {
        runtime_count: (dependencies.runtime || []).length,
        tool_count: (dependencies.tools || []).length,
      },
    },
  ];

  elements.capabilityServer.textContent = `${serverInfo.name || "Unknown Server"} ${serverInfo.version || ""} · protocol ${protocolVersion}`.trim();
  elements.capabilityGrid.className = "capability-grid";
  elements.capabilityGrid.innerHTML = "";

  rows.forEach((row) => {
    const article = document.createElement("article");
    article.className = "capability-card";
    article.innerHTML = `
      <strong>${row.title}</strong>
      <div class="capability-state ${row.supported ? "supported" : "unsupported"}">
        ${row.supported ? "已提供" : "未提供"}
      </div>
      <pre>${JSON.stringify(row.detail, null, 2)}</pre>
    `;
    elements.capabilityGrid.appendChild(article);
  });
}

function renderReport(report) {
  elements.reportSummary.textContent = `${report.ok ? "成功" : "失敗"}，總耗時 ${report.duration_ms}ms`;
  elements.reportSteps.innerHTML = "";
  const initializeStep = report.steps.find((step) => step.name === "initialize" && step.status === "PASS");
  renderCapabilities(initializeStep?.details || null);
  report.steps.forEach((step) => {
    const fragment = elements.reportStepTemplate.content.cloneNode(true);
    fragment.querySelector(".step-name").textContent = step.name;
    const statusEl = fragment.querySelector(".step-status");
    statusEl.textContent = step.status;
    statusEl.classList.add(step.status === "PASS" ? "status-pass" : "status-fail");
    fragment.querySelector(".step-meta").textContent = `${step.duration_ms}ms`;
    const detailEl = fragment.querySelector(".step-detail");
    const details = {};
    if (step.error) {
      details.error = step.error;
    }
    if (step.suggestion) {
      details.suggestion = step.suggestion;
    }
    if (step.details && Object.keys(step.details).length) {
      details.details = step.details;
    }
    if (Object.keys(details).length) {
      detailEl.textContent = JSON.stringify(details, null, 2);
      detailEl.classList.remove("hidden");
    }
    elements.reportSteps.appendChild(fragment);
  });
}

function renderToolList(tools) {
  if (!tools.length) {
    elements.toolList.innerHTML = state.tools.length
      ? '<div class="empty-state">目前的篩選條件沒有符合的工具。</div>'
      : '<div class="empty-state">目標 server 沒有回傳任何工具。</div>';
    return;
  }
  elements.toolList.innerHTML = "";
  tools.forEach((tool) => {
    const article = document.createElement("article");
    article.className = "tool-card";
    const description = tool.description || "沒有描述";
    article.innerHTML = `
      <div class="tool-card-head">
        <strong>${tool.name}</strong>
        <span>${(tool.input_schema?.required || []).length} required</span>
      </div>
      <p class="entry-meta">${description}</p>
      <pre>${JSON.stringify(tool.input_schema || {}, null, 2)}</pre>
    `;
    elements.toolList.appendChild(article);
  });
}

function populateToolSelect(tools) {
  elements.toolSelect.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = tools.length ? "請選擇工具" : "沒有符合篩選的工具";
  elements.toolSelect.appendChild(placeholder);

  tools.forEach((tool) => {
    const option = document.createElement("option");
    option.value = tool.name;
    option.textContent = tool.name;
    elements.toolSelect.appendChild(option);
  });
}

function getToolByName(name) {
  return state.tools.find((tool) => tool.name === name) || null;
}

function getFilteredTools() {
  const keyword = state.toolFilter.trim().toLowerCase();
  if (!keyword) {
    return state.tools;
  }
  return state.tools.filter((tool) => {
    const haystack = JSON.stringify({
      name: tool.name,
      description: tool.description || "",
      schema: tool.input_schema || {},
    }).toLowerCase();
    return haystack.includes(keyword);
  });
}

function applyToolFilter() {
  const filteredTools = getFilteredTools();
  populateToolSelect(filteredTools);
  renderToolList(filteredTools);

  if (state.selectedTool && !filteredTools.some((tool) => tool.name === state.selectedTool.name)) {
    elements.toolSelect.value = "";
    renderSchemaForm(null);
  } else if (state.selectedTool) {
    elements.toolSelect.value = state.selectedTool.name;
  }

  if (!state.tools.length) {
    elements.toolSummary.textContent = "尚未載入工具";
    return;
  }
  elements.toolSummary.textContent = state.toolFilter.trim()
    ? `顯示 ${filteredTools.length} / ${state.tools.length} 個工具`
    : `共 ${state.tools.length} 個工具`;
}

function createSchemaField(name, schema, requiredNames) {
  const fragment = elements.schemaFieldTemplate.content.cloneNode(true);
  const label = fragment.querySelector(".schema-label");
  const input = fragment.querySelector(".schema-input");
  const textarea = fragment.querySelector(".schema-textarea");
  const hint = fragment.querySelector(".schema-hint");

  const fieldType = schema.type || "string";
  const required = requiredNames.includes(name);
  label.textContent = `${name}${required ? " *" : ""}`;

  if (fieldType === "boolean") {
    input.type = "checkbox";
    input.dataset.fieldType = "boolean";
    input.value = "true";
  } else if (fieldType === "integer" || fieldType === "number") {
    input.type = "number";
    input.dataset.fieldType = fieldType;
  } else if (fieldType === "object" || fieldType === "array") {
    input.classList.add("hidden");
    textarea.classList.remove("hidden");
    textarea.dataset.fieldType = fieldType;
    textarea.placeholder = '請輸入合法 JSON，例如 {"key":"value"}';
  } else {
    input.type = "text";
    input.dataset.fieldType = "string";
  }

  if (schema.description) {
    hint.textContent = schema.description;
  } else if (fieldType === "object" || fieldType === "array") {
    hint.textContent = "複合型別請輸入 JSON。";
  } else {
    hint.textContent = `型別: ${fieldType}`;
  }

  fragment.firstElementChild.dataset.fieldName = name;
  return fragment;
}

function renderSchemaForm(tool) {
  state.selectedTool = tool;
  elements.toolDescription.textContent = tool?.description || "";
  elements.schemaForm.innerHTML = "";
  if (!tool) {
    elements.schemaForm.textContent = "選定工具後會根據 schema 產生輸入欄位。";
    elements.schemaForm.classList.add("empty-state");
    return;
  }
  const schema = tool.input_schema || {};
  const properties = schema.properties || {};
  const propertyNames = Object.keys(properties);
  if (!propertyNames.length) {
    elements.schemaForm.textContent = "這個工具沒有必填輸入，可直接執行。";
    elements.schemaForm.classList.add("empty-state");
    return;
  }
  elements.schemaForm.classList.remove("empty-state");
  const requiredNames = schema.required || [];
  propertyNames.forEach((name) => {
    elements.schemaForm.appendChild(createSchemaField(name, properties[name], requiredNames));
  });
}

function collectArguments() {
  const tool = state.selectedTool;
  if (!tool) {
    return {};
  }
  const schema = tool.input_schema || {};
  const requiredNames = schema.required || [];
  const result = {};
  const fieldNodes = elements.schemaForm.querySelectorAll("[data-field-name]");
  fieldNodes.forEach((node) => {
    const fieldName = node.dataset.fieldName;
    const input = node.querySelector(".schema-input");
    const textarea = node.querySelector(".schema-textarea");
    const type = textarea && !textarea.classList.contains("hidden")
      ? textarea.dataset.fieldType
      : input.dataset.fieldType;

    let value;
    if (type === "boolean") {
      value = input.checked;
    } else if (textarea && !textarea.classList.contains("hidden")) {
      const raw = textarea.value.trim();
      if (!raw) {
        value = undefined;
      } else {
        value = JSON.parse(raw);
      }
    } else {
      const raw = input.value.trim();
      if (!raw) {
        value = undefined;
      } else if (type === "integer") {
        value = Number.parseInt(raw, 10);
      } else if (type === "number") {
        value = Number(raw);
      } else {
        value = raw;
      }
    }
    if (value !== undefined && value !== "") {
      result[fieldName] = value;
    }
  });

  requiredNames.forEach((fieldName) => {
    if (!(fieldName in result)) {
      throw new Error(`缺少必填欄位：${fieldName}`);
    }
  });
  return result;
}

function appendTimelineEntry(kind, title, payload) {
  if (elements.llmTimeline.classList.contains("empty-state")) {
    elements.llmTimeline.classList.remove("empty-state");
    elements.llmTimeline.innerHTML = "";
  }
  const article = document.createElement("article");
  article.className = `timeline-entry ${kind}`;
  article.innerHTML = `
    <strong>${title}</strong>
    <p class="entry-meta">${new Date().toLocaleTimeString("zh-TW", { hour12: false })}</p>
    <pre>${JSON.stringify(payload, null, 2)}</pre>
  `;
  elements.llmTimeline.appendChild(article);
}

function activateTab(tabName) {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("is-active", tab.dataset.tab === tabName);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.panel === tabName);
  });
}

function parseSseChunk(chunk) {
  const lines = chunk.split("\n");
  let event = "message";
  const dataLines = [];
  lines.forEach((line) => {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  });
  return {
    event,
    data: dataLines.join("\n"),
  };
}

async function streamLlmTest(payload) {
  const response = await fetch("/api/llm/openai/test/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data?.error?.message || "LLM 測試失敗");
  }
  if (!response.body) {
    throw new Error("瀏覽器不支援串流回應");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";

    chunks.forEach((chunk) => {
      const parsed = parseSseChunk(chunk);
      if (!parsed.data) {
        return;
      }
      const payloadData = JSON.parse(parsed.data);
      if (parsed.event === "status") {
        appendTimelineEntry("assistant", "狀態更新", payloadData);
      } else if (parsed.event === "tool") {
        appendTimelineEntry("tool", `工具：${payloadData.name}`, payloadData);
      } else if (parsed.event === "assistant") {
        appendTimelineEntry("assistant", "Assistant", payloadData);
      } else if (parsed.event === "complete") {
        appendTimelineEntry("assistant", "完成", payloadData);
        renderJson(elements.resultViewer, payloadData);
        renderTrace(payloadData.trace || []);
      } else if (parsed.event === "error") {
        appendTimelineEntry("error", "錯誤", payloadData);
      }
    });
  }
}

async function handleConnectionTest() {
  saveSettings();
  setBadge("running", "檢查中");
  try {
    const report = await postJson("/api/connection/test", { connection: getConnectionPayload() });
    renderReport(report);
    setBadge(report.ok ? "success" : "failed", report.ok ? "已接通" : "檢查失敗");
  } catch (error) {
    elements.reportSummary.textContent = "檢查失敗";
    elements.reportSteps.innerHTML = `<div class="empty-state">${error.message}</div>`;
    setBadge("failed", "檢查失敗");
  }
}

async function handleLoadTools() {
  saveSettings();
  setBadge("running", "載入中");
  try {
    const payload = await postJson("/api/tools/list", { connection: getConnectionPayload() });
    state.tools = payload.tools || [];
    applyToolFilter();
    renderTrace(payload.trace || []);
    renderCapabilities(payload.initialize || null);
    setBadge("success", "工具已載入");
    activateTab("tools");
  } catch (error) {
    elements.toolSummary.textContent = "工具載入失敗";
    elements.toolList.innerHTML = `<div class="empty-state">${error.message}</div>`;
    setBadge("failed", "載入失敗");
  }
}

async function handleToolCall() {
  if (!state.selectedTool) {
    throw new Error("請先選擇工具");
  }
  saveSettings();
  setBadge("running", "執行中");
  const argumentsPayload = collectArguments();
  const payload = await postJson("/api/tools/call", {
    connection: getConnectionPayload(),
    name: state.selectedTool.name,
    arguments: argumentsPayload,
  });
  renderJson(elements.resultViewer, payload);
  renderTrace(payload.trace || []);
  activateTab("result");
  setBadge("success", "工具執行完成");
}

async function handleLlmRun() {
  saveSettings();
  elements.llmTimeline.className = "timeline empty-state";
  elements.llmTimeline.textContent = "開始執行...";
  activateTab("llm");
  setBadge("running", "LLM 測試中");
  const payload = {
    connection: getConnectionPayload(),
    api_key: elements.apiKey.value.trim(),
    model: elements.modelName.value.trim(),
    temperature: Number(elements.temperature.value || 0.2),
    system_prompt: elements.systemPrompt.value.trim(),
    prompt: elements.userPrompt.value.trim(),
  };
  await streamLlmTest(payload);
  setBadge("success", "LLM 測試完成");
}

function bindEvents() {
  elements.transportMode.addEventListener("change", () => {
    updateTransportFields();
    saveSettings();
  });
  [
    elements.serverUrl,
    elements.serverCommand,
    elements.userId,
    elements.timeoutSeconds,
    elements.modelName,
    elements.temperature,
    elements.systemPrompt,
    elements.userPrompt,
    elements.toolFilterInput,
  ].forEach((el) => {
    el.addEventListener("change", saveSettings);
    el.addEventListener("blur", saveSettings);
  });

  elements.testConnectionButton.addEventListener("click", () => {
    handleConnectionTest().catch((error) => {
      setBadge("failed", "檢查失敗");
      elements.reportSteps.innerHTML = `<div class="empty-state">${error.message}</div>`;
    });
  });

  elements.loadToolsButton.addEventListener("click", () => {
    handleLoadTools().catch((error) => {
      setBadge("failed", "載入失敗");
      elements.toolList.innerHTML = `<div class="empty-state">${error.message}</div>`;
    });
  });

  elements.toolSelect.addEventListener("change", (event) => {
    renderSchemaForm(getToolByName(event.target.value));
  });
  elements.toolFilterInput.addEventListener("input", (event) => {
    state.toolFilter = event.target.value || "";
    applyToolFilter();
    saveSettings();
  });

  elements.callToolButton.addEventListener("click", () => {
    handleToolCall().catch((error) => {
      setBadge("failed", "工具執行失敗");
      elements.resultViewer.textContent = error.message;
      activateTab("result");
    });
  });

  elements.runLlmButton.addEventListener("click", () => {
    handleLlmRun().catch((error) => {
      setBadge("failed", "LLM 測試失敗");
      appendTimelineEntry("error", "錯誤", { message: error.message });
    });
  });

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => activateTab(tab.dataset.tab));
  });
  elements.traceFilterInput.addEventListener("input", (event) => {
    state.traceFilter = event.target.value || "";
    renderTrace(state.lastTrace);
  });
  elements.copyTraceButton.addEventListener("click", () => {
    handleCopyTrace()
      .then(() => appendTimelineEntry("assistant", "Trace 已複製", { count: getFilteredTrace().length }))
      .catch((error) => appendTimelineEntry("error", "Trace 複製失敗", { message: error.message }));
  });
  elements.exportTraceButton.addEventListener("click", () => {
    try {
      handleExportTrace();
      appendTimelineEntry("assistant", "Trace 已匯出", { count: getFilteredTrace().length });
    } catch (error) {
      appendTimelineEntry("error", "Trace 匯出失敗", { message: error.message });
    }
  });
  elements.resetStateButton.addEventListener("click", resetState);
}

function init() {
  restoreSettings();
  updateTransportFields();
  bindEvents();
  elements.traceFilterInput.value = "";
  state.toolFilter = elements.toolFilterInput.value || "";
  renderJson(elements.resultViewer, { status: "idle" });
  renderTrace([]);
  renderCapabilities(null);
  renderSchemaForm(null);
}

init();
