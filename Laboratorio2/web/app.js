const state = {
  payload: null,
  view: "overview",
  timer: null,
};

const byId = (id) => document.getElementById(id);
const fmtNumber = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });
const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
const numeric = (value) => value === "" || value == null ? null : Number(value);

function median(values) {
  const ordered = values.filter(Number.isFinite).sort((a, b) => a - b);
  if (!ordered.length) return null;
  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2 ? ordered[middle] : (ordered[middle - 1] + ordered[middle]) / 2;
}

function formatDuration(seconds) {
  if (!Number.isFinite(seconds)) return "n/a";
  const rounded = Math.round(seconds);
  const minutes = Math.floor(rounded / 60);
  const rest = rounded % 60;
  return `${minutes}min ${String(rest).padStart(2, "0")}s`;
}

function treatmentLabel(value) { return value === "com_ia" ? "Com IA" : "Sem IA"; }

function rowsForMode() {
  if (!state.payload) return [];
  const metrics = new Map(state.payload.metrics.map((row) => [`${row.participant}|${row.kata}|${row.treatment}`, row]));
  return state.payload.trials.map((row) => ({
    ...row,
    ...metrics.get(`${row.participant}|${row.kata}|${row.treatment}`),
  }));
}

async function request(url, options = {}) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || "Falha na operacao.");
  return body;
}

function post(url, payload) {
  return request(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
}

function metric(label, value, caption, tone = "") {
  return `<article class="metric ${tone}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(caption)}</small></article>`;
}

function selectedPayload() {
  const form = new FormData(byId("trial-form"));
  return Object.fromEntries(form.entries());
}

function statusCell(row) {
  const green = numeric(row.tests_failed) === 0 && numeric(row.tests_passed) > 0;
  return `<span class="status-chip ${green ? "is-green" : "is-red"}">${green ? "Green" : "Incompleto"}</span>`;
}

function renderSummary() {
  const rows = rowsForMode();
  const times = rows.map((row) => numeric(row.time_to_green_seconds));
  const green = rows.filter((row) => numeric(row.tests_failed) === 0 && numeric(row.tests_passed) > 0).length;
  const success = rows.length ? (green / rows.length) * 100 : 0;
  const complexities = rows.map((row) => numeric(row.avg_cyclomatic_complexity));

  byId("summary-metrics").innerHTML = [
    metric("TRIALS", `${rows.length}/8`, "execucoes registradas", "tone-teal"),
    metric("MEDIANA DE TEMPO", formatDuration(median(times)), "time-to-green", "tone-coral"),
    metric("TAXA DE SUCESSO", `${fmtNumber.format(success)}%`, `${green} trials verdes`, "tone-green"),
    metric("COMPLEXIDADE", median(complexities) == null ? "n/a" : fmtNumber.format(median(complexities)), "mediana McCabe", "tone-amber"),
  ].join("");

  renderProgress(rows);
  renderBars(byId("overview-bars"), [
    { label: "Com IA", value: median(rows.filter((r) => r.treatment === "com_ia").map((r) => numeric(r.time_to_green_seconds))), format: formatDuration, tone: "teal" },
    { label: "Sem IA", value: median(rows.filter((r) => r.treatment === "sem_ia").map((r) => numeric(r.time_to_green_seconds))), format: formatDuration, tone: "coral" },
  ]);

  byId("recent-trials").innerHTML = rows.length
    ? rows.slice(-5).reverse().map((row) => `<tr><td>${escapeHtml(row.participant)}</td><td>${escapeHtml(row.kata)}</td><td>${treatmentLabel(row.treatment)}</td><td>${formatDuration(numeric(row.time_to_green_seconds))}</td><td>${escapeHtml(row.tests_passed)}/${numeric(row.tests_passed) + numeric(row.tests_failed)}</td><td>${statusCell(row)}</td></tr>`).join("")
    : `<tr><td colspan="6" class="empty-cell">Nenhum trial registrado.</td></tr>`;
}

function renderProgress(rows) {
  const planned = [
    ["flavio", "kata_01", "com_ia"], ["flavio", "kata_01", "sem_ia"],
    ["flavio", "kata_02", "com_ia"], ["flavio", "kata_02", "sem_ia"],
    ["luidi", "kata_03", "com_ia"], ["luidi", "kata_03", "sem_ia"],
    ["luidi", "kata_04", "com_ia"], ["luidi", "kata_04", "sem_ia"],
  ];
  const completed = new Set(rows.map((row) => `${row.participant}|${row.kata}|${row.treatment}`));
  byId("progress-matrix").innerHTML = planned.map(([participant, kata, treatment]) => {
    const done = completed.has(`${participant}|${kata}|${treatment}`);
    return `<div class="progress-row"><span class="check ${done ? "is-done" : ""}">${done ? "&#10003;" : ""}</span><strong>${participant}</strong><span>${kata.replace("_", " ")}</span><span>${treatmentLabel(treatment)}</span></div>`;
  }).join("");
}

function renderBars(container, items) {
  const valid = items.filter((item) => Number.isFinite(item.value));
  const max = Math.max(...valid.map((item) => item.value), 1);
  container.innerHTML = items.map((item) => {
    const width = Number.isFinite(item.value) ? Math.max((item.value / max) * 100, 4) : 0;
    const value = Number.isFinite(item.value) ? item.format(item.value) : "Sem dados";
    return `<div class="bar-row"><div class="bar-meta"><span>${escapeHtml(item.label)}</span><strong>${escapeHtml(value)}</strong></div><div class="bar-track"><span class="bar-fill ${item.tone}" style="width:${width}%"></span></div></div>`;
  }).join("");
}

function renderResults() {
  const rows = rowsForMode();
  const ai = rows.filter((row) => row.treatment === "com_ia");
  const manual = rows.filter((row) => row.treatment === "sem_ia");
  const successRate = (list) => list.length ? list.reduce((sum, row) => sum + (numeric(row.success_rate) || 0), 0) / list.length : null;
  const duplicate = rows.map((row) => numeric(row.duplication_percentage));

  byId("result-metrics").innerHTML = [
    metric("TEMPO COM IA", formatDuration(median(ai.map((r) => numeric(r.time_to_green_seconds)))), `${ai.length} trials`, "tone-teal"),
    metric("TEMPO SEM IA", formatDuration(median(manual.map((r) => numeric(r.time_to_green_seconds)))), `${manual.length} trials`, "tone-coral"),
    metric("SUCESSO MEDIO", successRate(rows) == null ? "n/a" : `${fmtNumber.format(successRate(rows) * 100)}%`, "testes de aceitacao", "tone-green"),
    metric("DUPLICACAO", median(duplicate) == null ? "n/a" : `${fmtNumber.format(median(duplicate))}%`, "mediana das solucoes", "tone-amber"),
  ].join("");

  renderBars(byId("performance-bars"), [
    { label: "Tempo com IA", value: median(ai.map((r) => numeric(r.time_to_green_seconds))), format: formatDuration, tone: "teal" },
    { label: "Tempo sem IA", value: median(manual.map((r) => numeric(r.time_to_green_seconds))), format: formatDuration, tone: "coral" },
    { label: "Sucesso com IA", value: successRate(ai) == null ? null : successRate(ai) * 100, format: (v) => `${fmtNumber.format(v)}%`, tone: "green" },
    { label: "Sucesso sem IA", value: successRate(manual) == null ? null : successRate(manual) * 100, format: (v) => `${fmtNumber.format(v)}%`, tone: "amber" },
  ]);
  renderBars(byId("structure-bars"), [
    { label: "Complexidade com IA", value: median(ai.map((r) => numeric(r.avg_cyclomatic_complexity))), format: (v) => fmtNumber.format(v), tone: "teal" },
    { label: "Complexidade sem IA", value: median(manual.map((r) => numeric(r.avg_cyclomatic_complexity))), format: (v) => fmtNumber.format(v), tone: "coral" },
    { label: "LOC com IA", value: median(ai.map((r) => numeric(r.loc))), format: (v) => fmtNumber.format(v), tone: "green" },
    { label: "LOC sem IA", value: median(manual.map((r) => numeric(r.loc))), format: (v) => fmtNumber.format(v), tone: "amber" },
  ]);

  byId("results-table").innerHTML = rows.length
    ? rows.map((row) => `<tr><td>${escapeHtml(row.participant)}</td><td>${escapeHtml(row.kata)}</td><td>${treatmentLabel(row.treatment)}</td><td>${formatDuration(numeric(row.time_to_green_seconds))}</td><td>${numeric(row.success_rate) == null ? "n/a" : `${fmtNumber.format(numeric(row.success_rate) * 100)}%`}</td><td>${escapeHtml(row.loc || "n/a")}</td><td>${escapeHtml(row.avg_cyclomatic_complexity || "n/a")}</td><td>${escapeHtml(row.maintainability_index || "n/a")}</td><td>${row.duplication_percentage == null ? "n/a" : `${escapeHtml(row.duplication_percentage)}%`}</td></tr>`).join("")
    : `<tr><td colspan="9" class="empty-cell">Nenhum resultado registrado.</td></tr>`;
}

function renderKatas() {
  const descriptions = {
    kata_01: "Agrupar solicitacoes proximas do mesmo equipamento em visitas de calibracao.",
    kata_02: "Montar viagens preservando fila, capacidade, destinos e prioridade urgente.",
    kata_03: "Reconstruir retiradas e devolucoes validas de ferramentas da oficina.",
    kata_04: "Detectar ciclos completos de rega a partir das medicoes de umidade.",
  };
  byId("kata-grid").innerHTML = Object.entries(state.payload?.katas || {}).map(([key, item], index) => `<article class="kata-card"><div class="kata-index">0${index + 1}</div><div><span class="owner-label">${escapeHtml(item.owner)}</span><h2>${escapeHtml(item.title)}</h2><p>${escapeHtml(descriptions[key])}</p><code>${escapeHtml(item.function)}()</code></div></article>`).join("");
}

function renderData() {
  const rows = rowsForMode();
  byId("row-count").textContent = `${rows.length} registros`;
  byId("data-table").innerHTML = rows.length
    ? rows.map((row) => `<tr><td class="mono compact-id">${escapeHtml(row.trial_id)}</td><td>${escapeHtml(row.participant)}</td><td>${escapeHtml(row.kata)}</td><td>${escapeHtml(row.treatment)}</td><td>${escapeHtml(row.started_at)}</td><td>${escapeHtml(row.finished_at)}</td><td>${escapeHtml(row.time_to_green_seconds)}</td><td>${escapeHtml(row.censored)}</td><td>${escapeHtml(row.tests_passed)}</td><td>${escapeHtml(row.tests_failed)}</td></tr>`).join("")
    : `<tr><td colspan="10" class="empty-cell">Nenhum registro carregado.</td></tr>`;
}

function activeForExecution() {
  if (!state.payload) return null;
  return state.payload.active || null;
}

function renderTimer() {
  const active = activeForExecution();
  const startButton = byId("start-button");
  const testButton = byId("test-button");
  const cancelButton = byId("cancel-button");
  const finishButton = byId("finish-button");
  startButton.disabled = Boolean(active);
  testButton.disabled = !active;
  cancelButton.disabled = !active;
  finishButton.disabled = !active;

  if (!active) {
    byId("active-label").textContent = "Nenhum trial ativo";
    byId("timer-status").textContent = "Parado";
    byId("timer-status").className = "status-chip";
    byId("timer-value").textContent = "35:00";
    byId("timer-progress").style.width = "0%";
    return;
  }

  const limit = Number(active.timebox_minutes || 35) * 60;
  const elapsed = Math.max(0, (Date.now() - new Date(active.started_at).getTime()) / 1000);
  const remaining = Math.max(0, limit - elapsed);
  const minutes = Math.floor(remaining / 60);
  const seconds = Math.floor(remaining % 60);
  byId("active-label").textContent = `${active.participant} / ${active.kata} / ${treatmentLabel(active.treatment)}`;
  byId("timer-status").textContent = remaining ? "Em andamento" : "Time-box";
  byId("timer-status").className = `status-chip ${remaining ? "is-running" : "is-red"}`;
  byId("timer-value").textContent = `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  byId("timer-progress").style.width = `${Math.min((elapsed / limit) * 100, 100)}%`;
}

function renderExecution() {
  renderTimer();
}

function renderAll() {
  renderSummary();
  renderResults();
  renderKatas();
  renderData();
  renderExecution();
  byId("sidebar-status").textContent = `${rowsForMode().length} trials carregados`;
}

async function loadData() {
  state.payload = await request("/api/data");
  renderAll();
}

function log(message, error = false) {
  byId("execution-log").textContent = message;
  byId("execution-log").classList.toggle("is-error", error);
}

async function perform(url, payload = selectedPayload()) {
  try {
    const result = await post(url, payload);
    log(result.output || result.message);
    if (result.workspace) byId("workspace-path").textContent = result.workspace;
    if (typeof result.passed === "number") {
      byId("tests-passed").value = result.passed;
      byId("tests-failed").value = result.failed;
      byId("outcome").value = result.green ? "green" : "timebox";
    }
    await loadData();
    return result;
  } catch (error) {
    log(error.message, true);
    return null;
  }
}

function setView(view) {
  state.view = view;
  document.querySelectorAll(".view").forEach((element) => element.classList.toggle("is-visible", element.id === `${view}-view`));
  document.querySelectorAll(".nav-item").forEach((element) => element.classList.toggle("is-active", element.dataset.view === view));
  const active = document.querySelector(`.nav-item[data-view="${view}"]`);
  byId("view-title").textContent = active?.textContent.trim().replace(/^\d+/, "") || "Lab02";
}

document.querySelectorAll(".nav-item").forEach((button) => button.addEventListener("click", () => setView(button.dataset.view)));
document.querySelectorAll("[data-go]").forEach((button) => button.addEventListener("click", () => setView(button.dataset.go)));

byId("refresh-button").addEventListener("click", loadData);
byId("trial-form").addEventListener("change", renderTimer);
byId("prepare-button").addEventListener("click", () => perform("/api/workspace"));
byId("start-button").addEventListener("click", () => perform("/api/trials/start"));
byId("test-button").addEventListener("click", () => perform("/api/tests"));
byId("cancel-button").addEventListener("click", () => perform("/api/trials/cancel"));
byId("metrics-button").addEventListener("click", () => perform("/api/metrics"));
byId("finish-button").addEventListener("click", () => perform("/api/trials/finish", {
  ...selectedPayload(),
  outcome: byId("outcome").value,
  tests_passed: Number(byId("tests-passed").value),
  tests_failed: Number(byId("tests-failed").value),
  notes: byId("trial-notes").value,
}));

state.timer = window.setInterval(renderTimer, 1000);
loadData().catch((error) => {
  byId("sidebar-status").textContent = "Falha ao carregar";
  log(error.message, true);
});
