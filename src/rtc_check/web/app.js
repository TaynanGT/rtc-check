const token = document.querySelector('meta[name="rtc-token"]').content;
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
let selectedFiles = [];
let currentResult = null;
let currentFilter = "todos";

document.addEventListener("keydown", (event) => {
  if (event.key === "Tab") document.body.classList.add("keyboard-nav");
});
document.addEventListener("pointerdown", () => document.body.classList.remove("keyboard-nav"));

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("X-RTC-Token", token);
  const response = await fetch(path, {...options, headers});
  const type = response.headers.get("content-type") || "";
  if (!response.ok) {
    const payload = type.includes("json") ? await response.json() : {erro: await response.text()};
    throw new Error(payload.erro || "Não foi possível concluir a operação.");
  }
  return type.includes("json") ? response.json() : response;
}

function toast(message) {
  const node = $("#toast");
  node.textContent = message;
  node.classList.remove("hidden");
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => node.classList.add("hidden"), 4200);
}

function setBusy(active, message = "Lendo XMLs e agrupando os produtos.") {
  $("#progress").classList.toggle("hidden", !active);
  $("#progress-message").textContent = message;
  $("#analyze").disabled = active || !selectedFiles.length;
  $("#demo").disabled = active;
}

function renderStatus(status) {
  $("#version").textContent = `v${status.versao}`;
  $("#plan-name").textContent = status.plano;
  const details = [];
  details.push(`<p><strong>${status.pago ? "Exportações liberadas" : "Diagnóstico gratuito"}</strong></p>`);
  if (status.dias_restantes !== null && status.dias_restantes !== undefined) {
    details.push(`<p>${status.dias_restantes} dia(s) restante(s)</p>`);
  }
  details.push(`<p>NT ${status.normativa.versao} · tabela ${status.normativa.tabela_versao}</p>`);
  $("#plan-details").innerHTML = details.join("");
  $("#trial").classList.toggle("hidden", status.pago);
  $("#checkout").classList.toggle("hidden", status.pago);
  $("#checkout").href = status.checkout.url;
  $("#checkout").setAttribute("aria-disabled", "false");
  $("#checkout-note").textContent = status.checkout.automatico
    ? `Checkout seguro por ${status.checkout.provedor}. O teste continua sem cartão.`
    : "Compra assistida; não inclua dados fiscais no formulário público. O teste é local.";
  if (status.aviso) toast(status.aviso);
}

function metric(value, label, kind = "") {
  return `<div class="metric ${kind}"><strong>${value.toLocaleString("pt-BR")}</strong><span>${label}</span></div>`;
}

function escapeText(value) {
  const node = document.createElement("span");
  node.textContent = value ?? "";
  return node.innerHTML;
}

function renderRows() {
  if (!currentResult) return;
  const items = currentResult.itens.filter((item) =>
    currentFilter === "todos" || item.severidade === currentFilter
  );
  $("#empty-filter").classList.toggle("hidden", items.length !== 0);
  $("#result-rows").innerHTML = items.map((item) => {
    const first = item.mensagens[0] || {codigo: "", mensagem: "", acao: ""};
    const messages = item.mensagens.map((entry) =>
      `<span class="message"><span class="code">${escapeText(entry.codigo)}</span>${escapeText(entry.mensagem)}</span>`
    ).join("");
    return `<tr data-severity="${item.severidade}">
      <td><span class="severity ${item.severidade}">${item.severidade}</span></td>
      <td><span class="sku">${escapeText(item.sku)}</span>
        <span class="description">${escapeText(item.descricao)}</span>${messages}</td>
      <td><span class="action">${escapeText(first.acao)}</span></td>
      <td><span class="impact">${item.ocorrencias.toLocaleString("pt-BR")} ocorrência(s)</span>
        <span class="description">${item.notas_afetadas.toLocaleString("pt-BR")} nota(s)</span></td>
      <td><span class="code">${escapeText(item.emitente)}</span></td>
    </tr>`;
  }).join("");
}

function renderResult(result) {
  currentResult = result;
  $("#results").classList.remove("hidden");
  $("#results-summary").textContent = result.aprovado
    ? "Nenhum bloqueio foi encontrado no lote analisado."
    : `${result.skus_a_corrigir.toLocaleString("pt-BR")} SKU(s) concentram os bloqueios encontrados.`;
  const score = $("#score");
  score.querySelector("strong").textContent = `${result.pontuacao}%`;
  score.style.background = `conic-gradient(var(--brand) ${result.pontuacao * 3.6}deg,#e5eeeb 0deg)`;
  $("#metrics").innerHTML = [
    metric(result.arquivos_lidos, "XMLs lidos"),
    metric(result.total_itens, "Itens analisados"),
    metric(result.bloqueios, "Bloqueios", result.bloqueios ? "bad" : ""),
    metric(result.alertas, "Alertas", result.alertas ? "warn" : ""),
    metric(result.skus_a_corrigir, "SKUs a corrigir", result.skus_a_corrigir ? "bad" : ""),
  ].join("");
  const upgrade = result.grupos_ocultos > 0 || !result.pode_exportar;
  $("#upgrade-note").classList.toggle("hidden", !upgrade);
  $("#upgrade-message").textContent = result.grupos_ocultos > 0
    ? `${result.grupos_ocultos} item(ns) adicionais e as exportações estão disponíveis no teste.`
    : "Ative o teste local para exportar CSV, JSON e relatório para PDF.";
  $$(".export").forEach((button) => {
    button.disabled = !result.pode_exportar;
    button.title = result.pode_exportar ? "" : "Disponível no teste grátis";
  });
  renderRows();
  $("#results").scrollIntoView({behavior: "smooth", block: "start"});
}

async function analyze(path, options = {}) {
  setBusy(true, options.message);
  try {
    const result = await api(path, options);
    renderResult(result);
  } catch (error) {
    toast(error.message);
  } finally {
    setBusy(false);
  }
}

function updateSelection(files) {
  selectedFiles = [...files].filter((file) => /\.(xml|zip)$/i.test(file.name));
  $("#selection-label").textContent = selectedFiles.length
    ? `${selectedFiles.length} arquivo(s) selecionado(s)`
    : "Nenhum arquivo XML ou ZIP selecionado";
  $("#analyze").disabled = !selectedFiles.length;
}

async function activateTrial() {
  try {
    const payload = await api("/api/teste", {method: "POST", body: "{}"});
    renderStatus(payload.status);
    toast(payload.mensagem);
    if (currentResult && !currentResult.demo) {
      toast("Execute a análise novamente para liberar todos os recursos.");
    }
  } catch (error) {
    toast(error.message);
  }
}

async function exportResult(format) {
  if (!currentResult) return;
  const brand = localStorage.getItem("rtc-brand") || "RTC Check";
  const color = localStorage.getItem("rtc-color") || "#0f766e";
  try {
    const response = await api(`/api/exportar/${currentResult.id}/${format}`, {
      method: "POST",
      body: "{}",
      headers: {"X-RTC-Brand": brand, "X-RTC-Color": color},
    });
    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") || "";
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match ? match[1] : `rtc-check.${format}`;
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = filename; anchor.click();
    if (format === "html") {
      toast("Relatório baixado. Abra o HTML e use Imprimir para salvar em PDF.");
    }
    window.setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (error) {
    toast(error.message);
  }
}

$("#files").addEventListener("change", (event) => updateSelection(event.target.files));
$("#folder-files").addEventListener("change", (event) => updateSelection(event.target.files));
$("#folder-open").addEventListener("click", () => $("#folder-files").click());
const dropzone = $("#dropzone");
["dragenter", "dragover"].forEach((name) => dropzone.addEventListener(name, (event) => {
  event.preventDefault(); dropzone.classList.add("drag");
}));
["dragleave", "drop"].forEach((name) => dropzone.addEventListener(name, (event) => {
  event.preventDefault(); dropzone.classList.remove("drag");
}));
dropzone.addEventListener("drop", (event) => updateSelection(event.dataTransfer.files));

$("#analyze").addEventListener("click", () => {
  const data = new FormData();
  selectedFiles.forEach((file) => data.append("arquivos", file, file.name));
  analyze("/api/analisar", {
    method: "POST", body: data,
    message: `Processando ${selectedFiles.length} arquivo(s) somente neste PC.`,
  });
});
$("#demo").addEventListener("click", () => analyze("/api/demo", {
  method: "POST", body: "{}",
  message: "Preparando uma análise demonstrativa.",
}));
$("#trial").addEventListener("click", activateTrial);
$("#upgrade-trial").addEventListener("click", activateTrial);

$$(".filter").forEach((button) => button.addEventListener("click", () => {
  $$(".filter").forEach((item) => item.classList.remove("active"));
  button.classList.add("active");
  currentFilter = button.dataset.filter;
  renderRows();
}));
$$(".export").forEach((button) => button.addEventListener("click", () =>
  exportResult(button.dataset.format)
));

const settings = $("#settings-dialog");
$("#settings-open").addEventListener("click", () => {
  $("#brand-name").value = localStorage.getItem("rtc-brand") || "RTC Check";
  $("#brand-color").value = localStorage.getItem("rtc-color") || "#0f766e";
  settings.showModal();
});
$("#settings-save").addEventListener("click", () => {
  localStorage.setItem("rtc-brand", $("#brand-name").value.trim() || "RTC Check");
  localStorage.setItem("rtc-color", $("#brand-color").value);
  toast("Personalização salva neste navegador.");
});

const license = $("#license-dialog");
$("#license-open").addEventListener("click", () => license.showModal());
$("#license-activate").addEventListener("click", async (event) => {
  event.preventDefault();
  $("#license-error").classList.add("hidden");
  try {
    const payload = await api("/api/licenca", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({chave: $("#license-key").value.trim()}),
    });
    renderStatus(payload.status);
    license.close();
    toast(payload.mensagem);
  } catch (error) {
    $("#license-error").textContent = error.message;
    $("#license-error").classList.remove("hidden");
  }
});

$("#shutdown").addEventListener("click", async () => {
  if (!window.confirm("Encerrar o RTC Check Desktop e apagar os resultados desta sessão?")) return;
  try {
    await api("/api/encerrar", {method: "POST", body: "{}"});
    document.body.innerHTML = `<main class="closed-screen">
      <p class="section-kicker">Sessão encerrada</p>
      <h1>RTC Check foi fechado com segurança.</h1>
      <p class="hero-text">Os uploads temporários e resultados em memória não estão mais acessíveis.
      Você já pode fechar esta aba.</p></main>`;
  } catch (error) {
    toast(error.message);
  }
});

api("/api/status").then(renderStatus).catch((error) => toast(error.message));
