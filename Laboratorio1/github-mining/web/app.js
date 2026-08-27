const state = { rows: [], analysis: null, page: 0, pageSize: 50, selectedRQ: "RQ01", activeJob: null };
const number = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });
const byId = (id) => document.getElementById(id);
const numeric = (value) => value === "" || value == null ? null : Number(value);
const median = (values) => { const v = values.filter(Number.isFinite).sort((a,b)=>a-b); if (!v.length) return null; const m = Math.floor(v.length/2); return v.length % 2 ? v[m] : (v[m-1]+v[m])/2; };
const fmt = (value, suffix="") => value == null || Number.isNaN(value) ? "n/a" : `${number.format(value)}${suffix}`;
const percent = (value) => value == null ? "n/a" : `${number.format(value * 100)}%`;
const language = (row) => row.primary_language || "Sem linguagem detectada";
const rqOrder = ["RQ01", "RQ02", "RQ03", "RQ04", "RQ05", "RQ06", "RQ07"];

async function request(url, options = {}) { const response = await fetch(url, options); const data = await response.json(); if (!response.ok) throw new Error(data.error || "Falha na operacao."); return data; }
function metric(label, value, caption) { return `<article class="metric"><span class="metric-label">${label}</span><strong class="metric-value">${value}</strong><span class="metric-caption">${caption}</span></article>`; }
function rqMetric(rows, field) { return median(rows.map((row) => numeric(row[field]))); }

function renderOverview() {
  const rows = state.rows;
  const ratioRows = rows.filter((r) => numeric(r.closed_issues_ratio) != null);
  byId("summary-cards").innerHTML = [
    metric("REPOSITORIOS", fmt(rows.length), "CSV carregado"),
    metric("REPOSITORIOS UNICOS", fmt(new Set(rows.map((r)=>r.name_with_owner)).size), "sem duplicidade"),
    metric("MEDIANA PRS", fmt(rqMetric(rows,"merged_pull_requests")), "RQ02"),
    metric("MEDIANA ISSUES FECHADAS", percent(median(ratioRows.map((r)=>numeric(r.closed_issues_ratio)))), "RQ06"),
  ].join("");
  const rqs = [
    ["RQ01","Idade do repositorio", `${fmt(rqMetric(rows,"age_days"))} dias`],
    ["RQ02","PRs aceitas",fmt(rqMetric(rows,"merged_pull_requests"))],
    ["RQ03","Releases",fmt(rqMetric(rows,"releases_count"))],
    ["RQ04","Dias desde atualizacao",fmt(rqMetric(rows,"days_since_update"))],
    ["RQ05","Sem linguagem detectada",fmt(rows.filter((r)=>!r.primary_language).length)],
    ["RQ06","Issues fechadas",percent(median(ratioRows.map((r)=>numeric(r.closed_issues_ratio))))],
    ["RQ07","Comparacao por linguagem","ver aba Linguagens"],
  ];
  byId("rq-summary").innerHTML = rqs.map(([rq,label,value])=>`<article class="rq-item"><b>${rq}</b><strong>${label}</strong><span>${value}</span></article>`).join("");
}

function rawLanguageEntries() {
  const grouped = new Map();
  state.rows.forEach((row)=>{ const key=language(row); if (!grouped.has(key)) grouped.set(key,[]); grouped.get(key).push(row); });
  return [...grouped.entries()].map(([name, rows])=>({
    name,
    count: rows.length,
    prs: rqMetric(rows,"merged_pull_requests"),
    releases: rqMetric(rows,"releases_count"),
    update: rqMetric(rows,"days_since_update"),
  })).sort((a,b)=>b.count-a.count || a.name.localeCompare(b.name));
}

function renderLanguages() {
  const rawEntries = rawLanguageEntries();
  const rq05 = state.analysis?.results?.RQ05;
  const rq07 = state.analysis?.results?.RQ07;
  const entries = rq07 ? rq07.by_language.map((item)=>({
    name: item.language,
    count: item.repository_count,
    prs: item.median_merged_pull_requests,
    releases: item.median_releases_count,
    update: item.median_days_since_update,
  })) : rawEntries.filter((item)=>item.name !== "Sem linguagem detectada" && item.count >= 10);

  byId("language-table").innerHTML = entries.length
    ? entries.map((item)=>`<tr><td>${item.name}</td><td>${fmt(item.count)}</td><td>${fmt(item.prs)}</td><td>${fmt(item.releases)}</td><td>${fmt(item.update)} dias</td></tr>`).join("")
    : `<tr><td colspan="5">Nenhuma linguagem com amostra suficiente.</td></tr>`;
  byId("language-filter").innerHTML = `<option>Todas</option>${rawEntries.map((item)=>`<option>${item.name}</option>`).join("")}`;

  const uniqueDetected = rq05?.validation?.unique_detected_languages ?? rawEntries.filter((item)=>item.name !== "Sem linguagem detectada").length;
  const missing = rq05?.validation?.missing_count ?? state.rows.filter((row)=>!row.primary_language).length;
  const octoverseShare = rq05?.octoverse_top_10_share_of_detected_percent;
  const eligible = rq07?.eligible_language_count ?? entries.length;
  byId("language-cards").innerHTML = [
    metric("LINGUAGENS DETECTADAS", fmt(uniqueDetected), "RQ05"),
    metric("SEM LINGUAGEM", fmt(missing), "tratados explicitamente"),
    metric("TOP 10 OCTOVERSE", fmt(octoverseShare, "%"), "dos repositorios com linguagem"),
    metric("LINGUAGENS NA RQ07", fmt(eligible), "minimo de 10 repositorios"),
  ].join("");
  byId("language-reading").textContent = rq07?.conclusion || "Gere a analise S03 para ver a comparacao por linguagem.";
}

function filteredRepositories() { const term=byId("repository-search").value.trim().toLowerCase(); const selected=byId("language-filter").value; return state.rows.filter((row)=>(!term||row.name_with_owner.toLowerCase().includes(term))&&(selected==="Todas"||language(row)===selected)); }
function renderRepositories() { const rows=filteredRepositories(); const pages=Math.max(1,Math.ceil(rows.length/state.pageSize)); state.page=Math.max(0,Math.min(state.page,pages-1)); const shown=rows.slice(state.page*state.pageSize,(state.page+1)*state.pageSize); byId("repository-table").innerHTML=shown.map((r)=>`<tr><td>${r.repository_rank}</td><td>${r.name_with_owner}</td><td>${language(r)}</td><td>${fmt(numeric(r.age_days))} dias</td><td>${fmt(numeric(r.merged_pull_requests))}</td><td>${fmt(numeric(r.releases_count))}</td><td>${fmt(numeric(r.days_since_update))} dias</td><td>${percent(numeric(r.closed_issues_ratio))}</td></tr>`).join(""); byId("page-label").textContent=`Pagina ${state.page+1}/${pages} - ${rows.length} repositorios`; }

function resultValue(rq, result) {
  if (rq === "RQ01") return fmt(result.median_years, " anos");
  if (rq === "RQ05") return fmt(result.octoverse_top_10_share_of_detected_percent, "%");
  if (rq === "RQ06") return fmt(result.median_percent, "%");
  if (rq === "RQ07") return fmt(result.eligible_language_count, " linguagens");
  return fmt(result.statistics?.median);
}

function resultDetail(rq, result) {
  if (rq === "RQ05") return `${result.validation?.missing_count ?? 0} sem linguagem`;
  if (rq === "RQ07") return `${result.excluded_below_minimum_count ?? 0} repos excluidos`;
  return `${result.outliers?.count ?? 0} outliers`;
}

function readingText(rq, result) {
  const notes = [];
  if (result.validation?.missing_count) notes.push(`${result.validation.missing_count} valores ausentes.`);
  if (rq === "RQ05") notes.push(`Valores vazios aparecem como "${result.validation?.missing_label}".`);
  if (rq === "RQ06") notes.push(`${result.excluded_no_issues} repositorios sem issues foram excluidos.`);
  if (rq === "RQ07") notes.push(`Comparacao restrita a linguagens com pelo menos ${result.minimum_repositories_per_language} repositorios.`);
  return [result.conclusion, ...notes].filter(Boolean).join(" ");
}

function renderSprint3() {
  const analysis = state.analysis;
  const results = analysis?.results || {};
  const available = rqOrder.filter((rq)=>results[rq]);
  if (!analysis || !available.length) {
    byId("sprint3-cards").innerHTML="";
    byId("sprint3-results").innerHTML="";
    byId("reading-text").textContent="Gere a analise S03 para ver os resultados.";
    byId("chart-image").removeAttribute("src");
    return;
  }
  if (!results[state.selectedRQ]) state.selectedRQ = available[0];
  byId("sprint3-cards").innerHTML = available.map((rq)=>metric(
    `${rq} - ${results[rq].metric}`,
    resultValue(rq, results[rq]),
    results[rq].hypothesis_evaluation ? `hipotese ${results[rq].hypothesis_evaluation}` : "resultado da amostra",
  )).join("");
  byId("sprint3-results").innerHTML = available.map((rq)=>{
    const result = results[rq];
    return `<button class="result-row ${rq===state.selectedRQ?"is-active":""}" data-rq="${rq}"><strong>${rq}</strong><span>${result.metric}</span><span>Resultado: ${resultValue(rq,result)}</span><span>${resultDetail(rq,result)}</span></button>`;
  }).join("");
  document.querySelectorAll(".result-row").forEach((element)=>element.addEventListener("click",()=>{ state.selectedRQ=element.dataset.rq; renderSprint3(); }));
  const result = results[state.selectedRQ];
  byId("reading-rq").textContent=state.selectedRQ;
  byId("reading-title").textContent=result.title;
  byId("reading-text").textContent=readingText(state.selectedRQ,result);
  renderChart();
}

function renderChart() {
  if (!state.analysis) return;
  const rq = byId("chart-selector").value;
  const names = {
    RQ01:"rq01_idade.png",
    RQ02:"rq02_prs_aceitas.png",
    RQ03:"rq03_releases.png",
    RQ04:"rq04_atualizacao.png",
    RQ05:"rq05_linguagens.png",
    RQ06:"rq06_issues_fechadas.png",
    RQ07:"rq07_comparacao_linguagens.png",
  };
  if (!state.analysis.results?.[rq]) { byId("chart-image").removeAttribute("src"); return; }
  byId("chart-image").src=`/api/chart/${names[rq]}?v=${Date.now()}`;
}

function setView(view) { document.querySelectorAll(".view").forEach((node)=>node.classList.toggle("is-visible",node.id===`${view}-view`)); document.querySelectorAll(".nav-item").forEach((node)=>node.classList.toggle("is-active",node.dataset.view===view)); byId("view-title").textContent=document.querySelector(`.nav-item[data-view="${view}"]`).textContent; }
function renderLog(jobs) { const entries=Object.entries(jobs||{}); const running=entries.find(([,job])=>job.running); state.activeJob=running?.[0]||null; const selected=running||entries.at(-1); byId("job-log").textContent=selected?selected[1].lines.join("\n"):"Nenhum processo executado nesta sessao."; }

async function loadData() { const [data,status]=await Promise.all([request("/api/data"),request("/api/status")]); state.rows=data.rows; state.analysis=data.analysis; renderOverview(); renderLanguages(); renderRepositories(); renderSprint3(); renderLog(status.jobs); byId("sidebar-status").textContent=status.csv_exists?`${state.rows.length} repositorios carregados.`:"Nenhum CSV carregado."; byId("app-status").textContent=state.activeJob?"Processo em andamento":"Dados locais prontos"; }
async function startAction(path, payload={}) { try { const result=await request(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)}); byId("app-status").textContent=result.message; await loadData(); } catch(error) { alert(error.message); } }
async function poll() { try { await loadData(); } catch(error) { byId("app-status").textContent="Servidor indisponivel"; } finally { window.setTimeout(poll,2500); } }

document.querySelectorAll(".nav-item").forEach((button)=>button.addEventListener("click",()=>setView(button.dataset.view)));
byId("refresh-button").addEventListener("click",loadData);
byId("collect-button").addEventListener("click",()=>startAction("/api/collect"));
byId("analyze-button").addEventListener("click",()=>startAction("/api/analyze"));
byId("clear-button").addEventListener("click",()=>{ if(confirm("Remover o CSV local e as analises geradas?")) startAction("/api/clear"); });
byId("chart-selector").addEventListener("change",renderChart);
byId("repository-search").addEventListener("input",()=>{state.page=0;renderRepositories();});
byId("language-filter").addEventListener("change",()=>{state.page=0;renderRepositories();});
byId("previous-page").addEventListener("click",()=>{state.page--;renderRepositories();});
byId("next-page").addEventListener("click",()=>{state.page++;renderRepositories();});
byId("snapshot-form").addEventListener("submit",(event)=>{event.preventDefault(); startAction("/api/snapshot",Object.fromEntries(new FormData(event.target)));});
loadData();
poll();
