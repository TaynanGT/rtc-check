const token = document.querySelector('meta[name="rtc-token"]').content;
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
let selectedFiles = [];
let currentResult = null;
let currentFilter = "todos";
let currentSearch = "";
let selectionTooLarge = false;
let currentAnalysisId = null;
const MAX_UPLOAD_BYTES = 64 * 1024 * 1024;

function setStep(step) {
  ["select", "analyze", "correct"].forEach((name, index) => {
    const node = $(`#step-${name}`);
    const number = index + 1;
    node.classList.toggle("active", number === step);
    node.classList.toggle("done", number < step);
    if (number === step) node.setAttribute("aria-current", "step");
    else node.removeAttribute("aria-current");
  });
}

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
  $("#cancel-analysis").classList.toggle("hidden", !active || !currentAnalysisId);
  if (active && currentAnalysisId) $("#cancel-analysis").disabled = false;
  $("#analyze").disabled = active || !selectedFiles.length || selectionTooLarge;
  $("#demo").disabled = active;
  $("#hero-demo").disabled = active;
  setStep(active ? 2 : (currentResult ? 3 : 1));
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
  $("#checkout").classList.toggle("hidden", status.licenciado);
  $("#offer-summary").classList.toggle("hidden", status.licenciado);
  $("#offer-monthly").textContent = `Escritório · ${status.checkout.preco_mensal}`;
  $("#offer-annual").textContent =
    `ou ${status.checkout.preco_anual} · exportações e fila completa`;
  $("#checkout").href = status.checkout.url;
  $("#checkout").setAttribute("aria-disabled", "false");
  $("#checkout").textContent = status.em_teste
    ? `Continuar após o teste — ${status.checkout.preco_mensal}`
    : `Assinar Escritório — ${status.checkout.preco_mensal}`;
  if (status.licenciado) {
    $("#checkout-note").textContent = status.dias_restantes !== null
      ? `Recursos liberados neste PC por mais ${status.dias_restantes} dia(s).`
      : "Licença ativa: análises e exportações liberadas.";
  } else if (status.em_teste) {
    $("#checkout-note").textContent =
      `Teste ativo por mais ${status.dias_restantes} dia(s). A compra assistida abre a captação privada: não inclua XMLs nem dados fiscais.`;
  } else {
    $("#checkout-note").textContent = status.checkout.automatico
      ? `Checkout seguro por ${status.checkout.provedor}. O teste continua sem cartão.`
      : "Compra assistida por captação privada; não inclua dados fiscais. O teste é local.";
  }
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

function escapeAttribute(value) {
  return escapeText(value).replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}

async function copyText(value, successMessage) {
  try {
    await navigator.clipboard.writeText(value);
  } catch {
    const helper = document.createElement("textarea");
    helper.value = value;
    helper.setAttribute("readonly", "");
    helper.style.position = "fixed";
    helper.style.opacity = "0";
    document.body.appendChild(helper);
    helper.select();
    document.execCommand("copy");
    helper.remove();
  }
  toast(successMessage);
}

function renderRows() {
  if (!currentResult) return;
  const query = currentSearch.trim().toLocaleLowerCase("pt-BR");
  const items = currentResult.itens.filter((item) => {
    const matchesFilter = currentFilter === "todos" || item.severidade === currentFilter;
    const haystack = [
      item.sku, item.descricao, item.ncm, item.emitente,
      ...item.codigos, ...item.mensagens.map((message) => message.acao),
    ].join(" ").toLocaleLowerCase("pt-BR");
    return matchesFilter && (!query || haystack.includes(query));
  });
  $("#empty-filter").classList.toggle("hidden", items.length !== 0);
  $("#visible-count").textContent = query || currentFilter !== "todos"
    ? `${items.length} correspondência(s) · ${currentResult.itens.length} carregada(s)`
    : `Mostrando ${items.length} de ${currentResult.total_grupos} SKU(s)`;
  $("#result-rows").innerHTML = items.map((item) => {
    const first = item.mensagens[0] || {codigo: "", mensagem: "", acao: ""};
    const messages = item.mensagens.map((entry) =>
      `<span class="message"><span class="code">${escapeText(entry.codigo)}</span>${escapeText(entry.mensagem)}</span>`
    ).join("");
    return `<tr data-severity="${item.severidade}">
      <td><span class="severity ${item.severidade}">${item.severidade}</span></td>
      <td><span class="sku">${escapeText(item.sku)}</span>
        <span class="description">${escapeText(item.descricao)}</span>${messages}</td>
      <td><span class="action">${escapeText(first.acao)}</span>
        <button class="button ghost compact copy-action" type="button"
          data-copy-sku="${escapeAttribute(item.sku)}">Copiar ação</button></td>
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
  const invalid = result.arquivos_invalidos || [];
  const invalidTotal = result.total_arquivos_invalidos ?? invalid.length;
  $("#invalid-alert").classList.toggle("hidden", !invalid.length);
  $("#invalid-title").textContent = invalidTotal === 1
    ? "1 arquivo não pôde ser lido"
    : `${invalidTotal} arquivos não puderam ser lidos`;
  $("#invalid-files").innerHTML = invalid.map((entry) =>
    `<li><strong>${escapeText(entry.arquivo)}</strong>: ${escapeText(entry.motivo)}</li>`
  ).join("");

  const issuers = result.emitentes || [];
  $("#issuer-title").textContent = result.pode_exportar
    ? `Resumo por emitente (${issuers.length})`
    : "Resumo por emitente — disponível no teste";
  $("#issuer-grid").innerHTML = result.pode_exportar
    ? issuers.map((issuer) => `<article class="issuer-card">
        <strong>${escapeText(issuer.nome || issuer.cnpj)}</strong>
        <span>${escapeText(issuer.cnpj)} · ${issuer.notas} nota(s) · ${issuer.itens} item(ns)</span>
        <span>${issuer.bloqueios} bloqueio(s) · ${issuer.skus} SKU(s)</span>
      </article>`).join("")
    : `<article class="issuer-card"><strong>Ative o teste grátis</strong>
        <span>Veja notas, itens, bloqueios e SKUs separados por emitente.</span></article>`;
  const upgrade = result.grupos_ocultos > 0 || !result.pode_exportar;
  $("#upgrade-note").classList.toggle("hidden", !upgrade);
  $("#upgrade-message").textContent = result.grupos_ocultos > 0
    ? `${result.grupos_ocultos} item(ns) adicionais e as exportações estão disponíveis no teste.`
    : "Ative o teste local para exportar CSV, JSON e relatório para PDF.";
  $$(".export").forEach((button) => {
    button.disabled = !result.pode_exportar;
    button.title = result.pode_exportar ? "" : "Disponível no teste grátis";
  });
  const first = result.itens[0];
  $("#next-action-title").textContent = first
    ? `Comece por ${first.sku}: ${first.mensagens[0]?.acao || "revise a parametrização indicada."}`
    : "Nenhum ajuste bloqueador foi encontrado neste lote.";
  $("#copy-first").classList.toggle("hidden", !first);
  $("#copy-queue").disabled = !result.itens.length;
  currentFilter = "todos";
  $$(".filter").forEach((button) =>
    button.classList.toggle("active", button.dataset.filter === "todos")
  );
  currentSearch = "";
  $("#queue-search").value = "";
  renderRows();
  setStep(3);
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

function sleep(milliseconds) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function renderProgress(status) {
  $("#progress-message").textContent = status.mensagem;
  $("#progress-count").textContent = status.total
    ? `${status.processados.toLocaleString("pt-BR")} de ${status.total.toLocaleString("pt-BR")} XMLs analisados`
    : "Preparação local em andamento.";
}

async function analyzeSelectedAsync(data, message) {
  setBusy(true, message);
  try {
    const started = await api("/api/analisar", {method: "POST", body: data});
    currentAnalysisId = started.id;
    setBusy(true, started.mensagem);
    while (currentAnalysisId === started.id) {
      const status = await api(`/api/analises/${started.id}`);
      renderProgress(status);
      if (!status.concluida) {
        await sleep(350);
        continue;
      }
      currentAnalysisId = null;
      if (status.resultado) {
        renderResult(status.resultado);
        return;
      }
      throw new Error(status.erro || status.mensagem || "A análise não foi concluída.");
    }
  } catch (error) {
    toast(error.message);
  } finally {
    currentAnalysisId = null;
    setBusy(false);
  }
}

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toLocaleString("pt-BR", {maximumFractionDigits: 1})} MB`;
}

function updateSelection(files, {preserveResult = false} = {}) {
  const received = [...files];
  selectedFiles = received.filter((file) => /\.(xml|zip)$/i.test(file.name));
  const rejected = received.length - selectedFiles.length;
  $("#selection-label").textContent = selectedFiles.length
    ? `${selectedFiles.length} arquivo(s) selecionado(s)`
    : "Nenhum arquivo XML ou ZIP selecionado";
  const total = selectedFiles.reduce((sum, file) => sum + file.size, 0);
  const tooLarge = total > MAX_UPLOAD_BYTES;
  selectionTooLarge = tooLarge;
  $("#selection-panel").classList.toggle("hidden", !selectedFiles.length);
  $("#selection-panel").classList.toggle("danger", tooLarge);
  $("#selection-summary").textContent = tooLarge
    ? "Este lote ultrapassa o limite de 64 MB"
    : `${selectedFiles.length} arquivo(s) pronto(s) para análise`;
  $("#selection-meta").textContent = tooLarge
    ? `${formatBytes(total)} no total · divida em lotes de até 64 MB`
    : `${formatBytes(total)} no total${rejected ? ` · ${rejected} arquivo(s) ignorado(s)` : ""}`;
  const visible = selectedFiles.slice(0, 3);
  $("#selection-files").innerHTML = visible.map((file) =>
    `<li title="${escapeAttribute(file.name)}">${escapeText(file.name)} · ${formatBytes(file.size)}</li>`
  ).join("") + (selectedFiles.length > 3
    ? `<li>+ ${selectedFiles.length - 3} arquivo(s)</li>` : "");
  $("#analyze").disabled = !selectedFiles.length || tooLarge;
  if (!preserveResult) {
    currentResult = null;
    $("#results").classList.add("hidden");
    setStep(1);
  } else {
    setStep(currentResult ? 3 : 1);
  }
  if (!selectedFiles.length && rejected) {
    toast("Nenhum XML ou ZIP válido foi encontrado na seleção.");
  }
}

async function activateTrial() {
  try {
    const payload = await api("/api/teste", {method: "POST", body: "{}"});
    renderStatus(payload.status);
    if (currentResult && !currentResult.demo) {
      if (selectedFiles.length) {
        toast(`${payload.mensagem} Refazendo a análise com todos os recursos…`);
        await analyzeSelected("Reprocessando o lote com todos os recursos liberados.");
      } else {
        toast(`${payload.mensagem} Selecione o lote novamente para aplicar todas as regras.`);
      }
    } else {
      toast(payload.mensagem);
    }
  } catch (error) {
    toast(error.message);
  }
}

function analyzeSelected(message = `Processando ${selectedFiles.length} arquivo(s) somente neste PC.`) {
  if (!selectedFiles.length || selectionTooLarge) {
    toast("Selecione um lote válido de até 64 MB.");
    return Promise.resolve();
  }
  const data = new FormData();
  selectedFiles.forEach((file) => data.append("arquivos", file, file.name));
  return analyzeSelectedAsync(data, message);
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
$("#selection-clear").addEventListener("click", () => {
  selectedFiles = [];
  $("#files").value = "";
  $("#folder-files").value = "";
  updateSelection([], {preserveResult: true});
  toast(currentResult ? "Seleção limpa; o resultado atual foi preservado." : "Seleção limpa.");
});
$("#cancel-analysis").addEventListener("click", async () => {
  if (!currentAnalysisId) return;
  try {
    const status = await api(`/api/analises/${currentAnalysisId}/cancelar`, {
      method: "POST", body: "{}",
    });
    renderProgress(status);
    $("#cancel-analysis").disabled = true;
  } catch (error) {
    toast(error.message);
  }
});
const dropzone = $("#dropzone");
["dragenter", "dragover"].forEach((name) => dropzone.addEventListener(name, (event) => {
  event.preventDefault(); dropzone.classList.add("drag");
}));
["dragleave", "drop"].forEach((name) => dropzone.addEventListener(name, (event) => {
  event.preventDefault(); dropzone.classList.remove("drag");
}));
dropzone.addEventListener("drop", (event) => {
  const hasDirectory = [...(event.dataTransfer.items || [])].some((item) =>
    item.webkitGetAsEntry?.()?.isDirectory
  );
  if (hasDirectory) {
    toast("Para incluir uma pasta, use “Selecionar uma pasta inteira”.");
    $("#folder-open").focus();
    return;
  }
  updateSelection(event.dataTransfer.files);
});
window.addEventListener("dragover", (event) => event.preventDefault());
window.addEventListener("drop", (event) => {
  event.preventDefault();
  if (!dropzone.contains(event.target)) {
    toast("Solte os arquivos dentro da área pontilhada.");
  }
});

$("#analyze").addEventListener("click", () => analyzeSelected());
$("#demo").addEventListener("click", () => analyze("/api/demo", {
  method: "POST", body: "{}",
  message: "Preparando uma análise demonstrativa.",
}));
$("#hero-demo").addEventListener("click", () => $("#demo").click());
$("#trial").addEventListener("click", activateTrial);
$("#upgrade-trial").addEventListener("click", activateTrial);

$$(".filter").forEach((button) => button.addEventListener("click", () => {
  $$(".filter").forEach((item) => item.classList.remove("active"));
  button.classList.add("active");
  currentFilter = button.dataset.filter;
  renderRows();
}));
$("#queue-search").addEventListener("input", (event) => {
  currentSearch = event.target.value;
  renderRows();
});
$$(".export").forEach((button) => button.addEventListener("click", () =>
  exportResult(button.dataset.format)
));
$("#result-rows").addEventListener("click", (event) => {
  const button = event.target.closest("[data-copy-sku]");
  if (!button || !currentResult) return;
  const item = currentResult.itens.find((entry) => entry.sku === button.dataset.copySku);
  const first = item?.mensagens[0];
  if (!item || !first) return;
  copyText(
    `SKU ${item.sku} — ${item.descricao}\nEmitente: ${item.emitente}\nAção: ${first.acao}`,
    `Ação do SKU ${item.sku} copiada.`,
  );
});

$("#copy-queue").addEventListener("click", () => {
  if (!currentResult?.itens.length) return;
  const lines = ["Prioridade\tSKU\tProduto\tEmitente\tAção"];
  currentResult.itens.forEach((item) => {
    lines.push([
      item.severidade,
      item.sku,
      item.descricao,
      item.emitente,
      item.mensagens[0]?.acao || "",
    ].join("\t"));
  });
  copyText(lines.join("\n"), "Fila copiada. Cole no Excel, e-mail ou chamado do ERP.");
});

$("#copy-first").addEventListener("click", () => {
  const item = currentResult?.itens[0];
  const first = item?.mensagens[0];
  if (!item || !first) return;
  copyText(
    `SKU ${item.sku} — ${item.descricao}\nEmitente: ${item.emitente}\nAção: ${first.acao}`,
    "Primeira ação copiada.",
  );
});

$("#new-analysis").addEventListener("click", () => {
  selectedFiles = [];
  currentResult = null;
  $("#files").value = "";
  $("#folder-files").value = "";
  updateSelection([]);
  $("#analisar-title").scrollIntoView({behavior: "smooth", block: "start"});
});

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
    if (currentResult && !currentResult.demo) {
      if (selectedFiles.length) {
        toast(`${payload.mensagem} Refazendo a análise com a licença ativa…`);
        await analyzeSelected("Reprocessando o lote com a licença ativa.");
      } else {
        toast(`${payload.mensagem} Selecione o lote novamente para aplicar todas as regras.`);
      }
    } else {
      toast(payload.mensagem);
    }
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
