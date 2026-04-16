const STORAGE_KEY = "toolanything.inspect.settings.v1";

const state = {
  tools: [],
  selectedTool: null,
  lastTrace: [],
  traceFilter: "",
  toolFilter: "",
  llmImageDataUrl: "",
  llmImageName: "",
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
  resultPreview: document.getElementById("resultPreview"),
  resultViewer: document.getElementById("resultViewer"),
  toolList: document.getElementById("toolList"),
  traceTimeline: document.getElementById("traceTimeline"),
  traceFilterInput: document.getElementById("traceFilterInput"),
  copyTraceButton: document.getElementById("copyTraceButton"),
  exportTraceButton: document.getElementById("exportTraceButton"),
  modelName: document.getElementById("modelName"),
  temperature: document.getElementById("temperature"),
  systemPrompt: document.getElementById("systemPrompt"),
  userPrompt: document.getElementById("userPrompt"),
  llmStatusText: document.getElementById("llmStatusText"),
  llmResultViewer: document.getElementById("llmResultViewer"),
  useToolImageForLlm: document.getElementById("useToolImageForLlm"),
  llmImageSourceLabel: document.getElementById("llmImageSourceLabel"),
  llmImageFile: document.getElementById("llmImageFile"),
  llmImageUploadText: document.getElementById("llmImageUploadText"),
  llmImagePreview: document.getElementById("llmImagePreview"),
  clearLlmImageButton: document.getElementById("clearLlmImageButton"),
  runLlmButton: document.getElementById("runLlmButton"),
  llmTimeline: document.getElementById("llmTimeline"),
  resetStateButton: document.getElementById("resetStateButton"),
  reportStepTemplate: document.getElementById("reportStepTemplate"),
  schemaFieldTemplate: document.getElementById("schemaFieldTemplate"),
  statusTransport: document.getElementById("statusTransport"),
  statusCapabilities: document.getElementById("statusCapabilities"),
  statusTools: document.getElementById("statusTools"),
};

function setBadge(kind, text) {
  elements.connectionBadge.textContent = text;
  elements.connectionBadge.className = `badge badge-${kind}`;
}

function setOptionalText(element, text) {
  if (element) {
    element.textContent = text;
  }
}

function isImageBase64Field(name, schema) {
  const normalizedName = String(name || "").toLowerCase();
  const description = String(schema?.description || "").toLowerCase();
  return (
    normalizedName === "image_base64" ||
    (normalizedName.includes("image") && normalizedName.includes("base64")) ||
    (description.includes("image") && description.includes("base64")) ||
    description.includes("圖片")
  );
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("圖片讀取失敗"));
    reader.readAsDataURL(file);
  });
}

function isImageDataUrl(value) {
  return typeof value === "string" && /^data:image\/[a-z0-9.+-]+;base64,/i.test(value.trim());
}

function parseJsonSafely(text) {
  if (typeof text !== "string") {
    return null;
  }
  const trimmed = text.trim();
  if (!trimmed || (!trimmed.startsWith("{") && !trimmed.startsWith("["))) {
    return null;
  }
  try {
    return JSON.parse(trimmed);
  } catch {
    return null;
  }
}

function summarizeImageDataUrl(value) {
  if (!isImageDataUrl(value)) {
    return value;
  }
  const mimeMatch = value.match(/^data:([^;]+);base64,/i);
  const mime = mimeMatch ? mimeMatch[1] : "image";
  return `[${mime} data URL，長度 ${value.length} 字元]`;
}

function sanitizePayloadForDisplay(value) {
  if (isImageDataUrl(value)) {
    return summarizeImageDataUrl(value);
  }
  if (Array.isArray(value)) {
    return value.map((entry) => sanitizePayloadForDisplay(entry));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, entry]) => [key, sanitizePayloadForDisplay(entry)])
    );
  }
  return value;
}

function collectImagePreviews(value, location, previews, seen) {
  if (isImageDataUrl(value)) {
    const normalized = value.trim();
    if (!seen.has(normalized)) {
      seen.add(normalized);
      previews.push({ location, url: normalized });
    }
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((entry, index) => {
      collectImagePreviews(entry, `${location}[${index}]`, previews, seen);
    });
    return;
  }
  if (value && typeof value === "object") {
    Object.entries(value).forEach(([key, entry]) => {
      const nextLocation = location ? `${location}.${key}` : key;
      collectImagePreviews(entry, nextLocation, previews, seen);
    });
  }
}

function extractImagePreviews(payload) {
  const previews = [];
  const seen = new Set();
  collectImagePreviews(payload, "result", previews, seen);

  const content = payload?.result?.content;
  if (Array.isArray(content)) {
    content.forEach((entry, index) => {
      const parsed = parseJsonSafely(entry?.text);
      if (parsed !== null) {
        collectImagePreviews(parsed, `result.content[${index}]`, previews, seen);
      } else if (typeof entry?.text === "string") {
        collectImagePreviews(entry.text, `result.content[${index}]`, previews, seen);
      }
    });
  }
  return previews;
}

function renderResultPreviews(payload) {
  const previews = extractImagePreviews(payload);
  if (!previews.length) {
    elements.resultPreview.className = "result-preview empty-state";
    elements.resultPreview.textContent = "目前結果沒有可預覽的圖片。";
    return;
  }

  elements.resultPreview.className = "result-preview result-preview-grid";
  elements.resultPreview.innerHTML = "";
  previews.forEach((preview, index) => {
    const article = document.createElement("article");
    article.className = "result-preview-card";
    article.innerHTML = `
      <strong>圖片預覽 ${index + 1}</strong>
      <span>${preview.location}</span>
      <img src="${preview.url}" alt="工具回傳圖片預覽 ${index + 1}" />
    `;
    elements.resultPreview.appendChild(article);
  });
}

function normalizeSchema(schema) {
  if (!schema || typeof schema !== "object") {
    return {};
  }
  if (schema.type) {
    return schema;
  }
  if (Array.isArray(schema.oneOf)) {
    const preferred = schema.oneOf.find((entry) => entry && entry.type && entry.type !== "null");
    if (preferred && typeof preferred === "object") {
      return { ...schema, ...preferred };
    }
  }
  return schema;
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
    use_tool_image_for_llm: elements.useToolImageForLlm.checked,
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
    elements.useToolImageForLlm.checked = payload.use_tool_image_for_llm !== false;
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
  target.textContent = JSON.stringify(sanitizePayloadForDisplay(payload), null, 2);
}

function setLlmStatus(text) {
  setOptionalText(elements.llmStatusText, text);
}

function getActiveToolImageField() {
  return elements.schemaForm.querySelector('[data-field-type="image_base64"]');
}

function getActiveToolImageContext() {
  const field = getActiveToolImageField();
  const imageBase64 = field?.dataset?.encodedValue || "";
  if (!imageBase64) {
    return null;
  }
  const fileName = field.querySelector(".schema-file-input")?.files?.[0]?.name || "tool-form-image";
  return {
    image_base64: imageBase64,
    image_name: fileName,
    source: "tool_form",
    label: `工具區圖片：${fileName}`,
  };
}

function getLlmUploadImageContext() {
  if (!state.llmImageDataUrl) {
    return null;
  }
  return {
    image_base64: state.llmImageDataUrl,
    image_name: state.llmImageName || "llm-upload-image",
    source: "llm_upload",
    label: `LLM 區圖片：${state.llmImageName || "未命名圖片"}`,
  };
}

function getSelectedLlmImageContext() {
  const toolImage = getActiveToolImageContext();
  const llmImage = getLlmUploadImageContext();

  if (elements.useToolImageForLlm.checked && toolImage) {
    return toolImage;
  }
  return llmImage || toolImage || null;
}

function updateLlmImageSummary() {
  const selected = getSelectedLlmImageContext();
  if (!selected) {
    elements.llmImageSourceLabel.textContent = "目前沒有指定圖片";
    return;
  }
  elements.llmImageSourceLabel.textContent = selected.label;
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
    const title = entry.payload?.method || `${entry.direction} / ${entry.kind}`;
    article.innerHTML = `
      <strong>#${index + 1} ${title}</strong>
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
    elements.capabilityGrid.className = "cap-grid empty-state";
    elements.capabilityGrid.textContent = "載入工具或完成連線檢查後，這裡會顯示 server capabilities。";
    setOptionalText(elements.statusCapabilities, "尚未初始化");
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
  elements.capabilityGrid.className = "cap-grid";
  elements.capabilityGrid.innerHTML = "";
  setOptionalText(elements.statusCapabilities, `protocol ${protocolVersion}`);

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
  elements.reportSummary.style.color = report.ok ? "var(--green)" : "var(--red)";
  elements.reportSteps.innerHTML = "";
  elements.reportSteps.className = "diag-list";
  const initializeStep = report.steps.find((step) => step.name === "initialize" && step.status === "PASS");
  renderCapabilities(initializeStep?.details || null);
  report.steps.forEach((step) => {
    const fragment = elements.reportStepTemplate.content.cloneNode(true);
    const card = fragment.querySelector(".diag-card");
    const head = fragment.querySelector(".diag-head");
    const body = fragment.querySelector(".diag-body");
    fragment.querySelector(".diag-name").textContent = step.name;
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
      body.classList.remove("hidden");
      card.classList.add("open");
      head.addEventListener("click", () => {
        body.classList.toggle("hidden");
        card.classList.toggle("open", !body.classList.contains("hidden"));
      });
    } else {
      head.disabled = true;
      head.style.cursor = "default";
    }
    elements.reportSteps.appendChild(fragment);
  });
}

function renderToolList(tools) {
  if (!tools.length) {
    elements.toolList.className = "tools-grid empty-state";
    elements.toolList.innerHTML = state.tools.length
      ? '<div class="empty-state">目前的篩選條件沒有符合的工具。</div>'
      : '<div class="empty-state">目標 server 沒有回傳任何工具。</div>';
    return;
  }
  elements.toolList.className = "tools-grid";
  elements.toolList.innerHTML = "";
  tools.forEach((tool) => {
    const article = document.createElement("article");
    article.className = "tool-card";
    const description = tool.description || "沒有描述";
    const inputSchema = getToolInputSchema(tool);
    article.innerHTML = `
      <div class="tool-card-head">
        <strong>${tool.name}</strong>
        <span>${(inputSchema.required || []).length} required</span>
      </div>
      <p class="entry-meta">${description}</p>
      <pre>${JSON.stringify(inputSchema, null, 2)}</pre>
    `;
    article.addEventListener("click", () => {
      elements.toolSelect.value = tool.name;
      renderSchemaForm(tool);
      activateTab("result");
    });
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

function getToolInputSchema(tool) {
  return tool?.inputSchema || {};
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
      schema: getToolInputSchema(tool),
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
    setOptionalText(elements.statusTools, "0 工具已載入");
    return;
  }
  elements.toolSummary.textContent = state.toolFilter.trim()
    ? `顯示 ${filteredTools.length} / ${state.tools.length} 個工具`
    : `共 ${state.tools.length} 個工具`;
  setOptionalText(elements.statusTools, `${state.tools.length} 工具已載入`);
}

function formatSchemaDefault(defaultValue) {
  if (defaultValue === null) {
    return "null";
  }
  if (typeof defaultValue === "string") {
    return defaultValue;
  }
  return JSON.stringify(defaultValue);
}

function buildSchemaHint(resolvedSchema, fieldType, isImageField) {
  const noteParts = [];
  if (resolvedSchema.description) {
    noteParts.push(resolvedSchema.description);
  } else if (isImageField) {
    noteParts.push("支援直接上傳圖片，系統會自動轉成工具需要的字串格式。");
  } else if (fieldType === "object" || fieldType === "array") {
    noteParts.push("複合型別請輸入 JSON。");
  }

  const typeLabel = Array.isArray(resolvedSchema.oneOf)
    ? resolvedSchema.oneOf.map((entry) => entry?.type).filter(Boolean).join(" | ")
    : fieldType;
  noteParts.push(`型別: ${typeLabel}`);

  if (Object.prototype.hasOwnProperty.call(resolvedSchema, "default")) {
    noteParts.push(`預設值: ${formatSchemaDefault(resolvedSchema.default)}`);
  }
  if (Array.isArray(resolvedSchema.enum) && resolvedSchema.enum.length) {
    noteParts.push(`可用值: ${resolvedSchema.enum.join(", ")}`);
  }
  return noteParts.join(" · ");
}

function applySchemaDefaultValue(resolvedSchema, fieldType, input, textarea) {
  if (!Object.prototype.hasOwnProperty.call(resolvedSchema, "default")) {
    return;
  }
  const defaultValue = resolvedSchema.default;
  if (defaultValue === null || defaultValue === undefined) {
    return;
  }
  if (fieldType === "boolean") {
    input.checked = Boolean(defaultValue);
    return;
  }
  if (fieldType === "object" || fieldType === "array") {
    textarea.value = typeof defaultValue === "string"
      ? defaultValue
      : JSON.stringify(defaultValue, null, 2);
    return;
  }
  input.value = String(defaultValue);
}

function createSchemaField(name, schema, requiredNames) {
  const resolvedSchema = normalizeSchema(schema);
  const fragment = elements.schemaFieldTemplate.content.cloneNode(true);
  const field = fragment.querySelector(".schema-field");
  const label = fragment.querySelector(".schema-label");
  const input = fragment.querySelector(".schema-input");
  const textarea = fragment.querySelector(".schema-textarea");
  const imageUpload = fragment.querySelector(".schema-image-upload");
  const fileInput = fragment.querySelector(".schema-file-input");
  const preview = fragment.querySelector(".schema-image-preview");
  const clearButton = fragment.querySelector(".schema-clear-button");
  const uploadText = fragment.querySelector(".schema-upload-text");
  const hint = fragment.querySelector(".schema-hint");

  const fieldType = resolvedSchema.type || "string";
  const required = requiredNames.includes(name);
  const imageField = isImageBase64Field(name, resolvedSchema);
  label.textContent = `${name}${required ? " *" : ""}`;

  field.dataset.fieldName = name;

  if (imageField) {
    field.dataset.fieldType = "image_base64";
    input.classList.add("hidden");
    textarea.classList.add("hidden");
    imageUpload.classList.remove("hidden");
    uploadText.textContent = required
      ? "上傳圖片後會自動轉成 base64 / data URL，這是必填欄位。"
      : "上傳圖片後會自動轉成 base64 / data URL。";
    fileInput.addEventListener("change", async () => {
      const file = fileInput.files?.[0];
      if (!file) {
        return;
      }
      try {
        const encodedValue = await readFileAsDataUrl(file);
        field.dataset.encodedValue = encodedValue;
        preview.src = encodedValue;
        preview.classList.remove("hidden");
        clearButton.classList.remove("hidden");
        uploadText.textContent = `已載入 ${file.name}`;
        updateLlmImageSummary();
      } catch (error) {
        field.dataset.encodedValue = "";
        preview.removeAttribute("src");
        preview.classList.add("hidden");
        clearButton.classList.add("hidden");
        uploadText.textContent = error.message || "圖片讀取失敗";
        updateLlmImageSummary();
      }
    });
    clearButton.addEventListener("click", (event) => {
      event.preventDefault();
      fileInput.value = "";
      field.dataset.encodedValue = "";
      preview.removeAttribute("src");
      preview.classList.add("hidden");
      clearButton.classList.add("hidden");
      uploadText.textContent = required
        ? "上傳圖片後會自動轉成 base64 / data URL，這是必填欄位。"
        : "上傳圖片後會自動轉成 base64 / data URL。";
      updateLlmImageSummary();
    });
  } else if (fieldType === "boolean") {
    field.dataset.fieldType = "boolean";
    input.type = "checkbox";
    input.dataset.fieldType = "boolean";
    input.value = "true";
  } else if (fieldType === "integer" || fieldType === "number") {
    field.dataset.fieldType = fieldType;
    input.type = "number";
    input.dataset.fieldType = fieldType;
    input.step = fieldType === "integer" ? "1" : "any";
  } else if (fieldType === "object" || fieldType === "array") {
    field.dataset.fieldType = fieldType;
    input.classList.add("hidden");
    textarea.classList.remove("hidden");
    textarea.dataset.fieldType = fieldType;
    textarea.placeholder = '請輸入合法 JSON，例如 {"key":"value"}';
  } else {
    field.dataset.fieldType = "string";
    input.type = "text";
    input.dataset.fieldType = "string";
  }

  if (!imageField) {
    applySchemaDefaultValue(resolvedSchema, field.dataset.fieldType || fieldType, input, textarea);
  }
  hint.textContent = buildSchemaHint(resolvedSchema, field.dataset.fieldType || fieldType, imageField);

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
  const schema = getToolInputSchema(tool);
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
  const schema = getToolInputSchema(tool);
  const requiredNames = schema.required || [];
  const result = {};
  const fieldNodes = elements.schemaForm.querySelectorAll("[data-field-name]");
  fieldNodes.forEach((node) => {
    const fieldName = node.dataset.fieldName;
    const containerType = node.dataset.fieldType;
    const input = node.querySelector(".schema-input");
    const textarea = node.querySelector(".schema-textarea");
    const type = containerType || (textarea && !textarea.classList.contains("hidden")
      ? textarea.dataset.fieldType
      : input.dataset.fieldType);

    let value;
    if (type === "image_base64") {
      value = node.dataset.encodedValue || undefined;
    } else if (type === "boolean") {
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
    elements.llmTimeline.className = "llm-timeline";
    elements.llmTimeline.innerHTML = "";
  }
  const details = document.createElement("details");
  details.className = `timeline-entry ${kind}`;
  if (kind === "error" || kind === "tool") {
    details.open = true;
  }
  details.innerHTML = `
    <summary>
      <span class="timeline-entry-title">${title}</span>
      <span class="entry-meta">${new Date().toLocaleTimeString("zh-TW", { hour12: false })}</span>
      <span class="step-status">${kind}</span>
    </summary>
    <div class="timeline-entry-body">
      <pre>${JSON.stringify(sanitizePayloadForDisplay(payload), null, 2)}</pre>
    </div>
  `;
  elements.llmTimeline.appendChild(details);
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
        setLlmStatus(`執行中：${payloadData.phase || "processing"}`);
        appendTimelineEntry("assistant", "狀態更新", payloadData);
      } else if (parsed.event === "tool") {
        setLlmStatus(`工具呼叫：${payloadData.name || "unknown"}`);
        appendTimelineEntry("tool", `工具：${payloadData.name}`, payloadData);
      } else if (parsed.event === "assistant") {
        setLlmStatus(payloadData.done ? "Assistant 已完成回應" : "Assistant 回應中");
        appendTimelineEntry("assistant", "Assistant", payloadData);
      } else if (parsed.event === "complete") {
        setLlmStatus("LLM 測試完成");
        appendTimelineEntry("assistant", "完成", payloadData);
        renderJson(elements.llmResultViewer, payloadData);
        renderResultPreviews(payloadData);
        renderJson(elements.resultViewer, payloadData);
        renderTrace(payloadData.trace || []);
      } else if (parsed.event === "error") {
        setLlmStatus("LLM 測試失敗，請展開錯誤卡片查看詳細內容。");
        renderJson(elements.llmResultViewer, { error: payloadData });
        appendTimelineEntry("error", "錯誤", payloadData);
      }
    });
  }
}

async function handleConnectionTest() {
  saveSettings();
  setBadge("running", "檢查中");
  setOptionalText(elements.statusTransport, "檢查連線中");
  try {
    const report = await postJson("/api/connection/test", { connection: getConnectionPayload() });
    renderReport(report);
    setBadge(report.ok ? "success" : "failed", report.ok ? "已接通" : "檢查失敗");
    setOptionalText(
      elements.statusTransport,
      report.ok ? `${elements.transportMode.value.toUpperCase()} 已接通` : "連線檢查失敗",
    );
  } catch (error) {
    elements.reportSummary.textContent = "檢查失敗";
    elements.reportSummary.style.color = "var(--red)";
    elements.reportSteps.innerHTML = `<div class="empty-state">${error.message}</div>`;
    setBadge("failed", "檢查失敗");
    setOptionalText(elements.statusTransport, "連線檢查失敗");
  }
}

async function handleLoadTools() {
  saveSettings();
  setBadge("running", "載入中");
  setOptionalText(elements.statusTransport, "工具載入中");
  try {
    const payload = await postJson("/api/tools/list", { connection: getConnectionPayload() });
    state.tools = payload.tools || [];
    applyToolFilter();
    renderTrace(payload.trace || []);
    renderCapabilities(payload.initialize || null);
    setBadge("success", "工具已載入");
    setOptionalText(elements.statusTransport, "工具已載入");
    activateTab("tools");
  } catch (error) {
    elements.toolSummary.textContent = "工具載入失敗";
    elements.toolList.className = "tools-grid empty-state";
    elements.toolList.innerHTML = `<div class="empty-state">${error.message}</div>`;
    setBadge("failed", "載入失敗");
    setOptionalText(elements.statusTransport, "工具載入失敗");
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
  renderResultPreviews(payload);
  renderJson(elements.resultViewer, payload);
  renderTrace(payload.trace || []);
  activateTab("result");
  setBadge("success", "工具執行完成");
}

async function handleLlmRun() {
  saveSettings();
  elements.llmTimeline.className = "llm-timeline empty-state";
  elements.llmTimeline.textContent = "開始測試後會在這裡逐步顯示 assistant / tool / error 事件。";
  setLlmStatus("正在送出請求並等待模型規劃工具呼叫。");
  renderJson(elements.llmResultViewer, { status: "running" });
  activateTab("llm");
  setBadge("running", "LLM 測試中");
  const payload = {
    connection: getConnectionPayload(),
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
      setLlmStatus("LLM 測試失敗，請展開錯誤卡片查看詳細內容。");
      renderJson(elements.llmResultViewer, { error: error.message });
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
  renderResultPreviews({ status: "idle" });
  renderJson(elements.resultViewer, { status: "idle" });
  renderJson(elements.llmResultViewer, { status: "idle" });
  setLlmStatus("尚未開始執行。右側會顯示最終結果與每一步事件。");
  renderTrace([]);
  renderCapabilities(null);
  renderSchemaForm(null);
  setOptionalText(elements.statusTransport, "等待連線");
  setOptionalText(elements.statusCapabilities, "尚未初始化");
  setOptionalText(elements.statusTools, "0 工具已載入");
}

init();
