/* O servidor entrega nós, rota, prefixos e métricas prontos.
   Aqui só existem requisições, controles, desenho e reprodução da lista. */
"use strict";
const $ = (id) => document.getElementById(id);
const NS = "http://www.w3.org/2000/svg";
const colors = {source: "#2f6095", target: "#2c7848", key: "#b36512"};
const prefixColors = ["#2f6095", "#5763a0", "#785590", "#377a72", "#2c7848"];
let network = null, route = null, shown = 0, playing = false, busy = false;
let timer = null, motion = null, randomCounter = 0, routeDirty = false, tutorialStep = 0;

function svg(tag, attributes = {}, text) {
  const element = document.createElementNS(NS, tag);
  for (const [name, value] of Object.entries(attributes)) element.setAttribute(name, value);
  if (text !== undefined) element.textContent = text;
  return element;
}

async function api(url, data) {
  const response = await fetch(url, data === undefined ? {} : {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Não foi possível completar a operação.");
  return result;
}

function showError(error) {
  $("error").textContent = error.message || "Não foi possível conectar ao servidor Python.";
  $("error").hidden = false;
  $("error").scrollIntoView({block:"nearest"});
}

async function action(work) {
  if (busy) return;
  pause();
  busy = true;
  $("error").hidden = true;
  document.querySelectorAll("[data-network-control]").forEach((element) => element.disabled = true);
  try { await work(); } catch (error) {
    showError(error);
    if ($("search-feedback").textContent === "Calculando a busca…") {
      $("search-feedback").textContent = "A busca não foi concluída. Confira a chave e tente novamente.";
    }
    if ($("network-feedback").textContent === "Criando a rede…") {
      $("network-feedback").textContent = "Não foi possível criar a rede. Confira os valores.";
    }
  }
  finally {
    busy = false;
    document.querySelectorAll("[data-network-control]").forEach((element) => element.disabled = false);
    updatePlayback();
  }
}

function point(position, radius = 213) {
  const angle = position * Math.PI * 2 - Math.PI / 2;
  return {x: 310 + radius * Math.cos(angle), y: 290 + radius * Math.sin(angle)};
}

function nodeColor(hop) {
  return prefixColors[Math.min(hop.prefix_length, prefixColors.length - 1)];
}

function hopPath(from, to) {
  const a = point(from.position), b = point(to.position);
  const dx = b.x - a.x, dy = b.y - a.y;
  const distance = Math.hypot(dx, dy);
  if (distance < 80) {
    // Abra um arco para dentro do anel mesmo quando os nós quase coincidem.
    // Isso só amplia o desenho; as posições e a rota continuam as mesmas.
    const middle = {x:(a.x + b.x) / 2, y:(a.y + b.y) / 2};
    const radius = Math.hypot(310 - middle.x, 290 - middle.y);
    const inward = {x:(310 - middle.x) / radius, y:(290 - middle.y) / radius};
    const tangent = distance > 0 ? {x:dx / distance, y:dy / distance}
      : {x:-inward.y, y:inward.x};
    const spread = Math.max(0, 32 - distance / 2);
    const c1 = {x:a.x + inward.x * 80 - tangent.x * spread,
      y:a.y + inward.y * 80 - tangent.y * spread};
    const c2 = {x:b.x + inward.x * 80 + tangent.x * spread,
      y:b.y + inward.y * 80 + tangent.y * spread};
    return `M ${a.x} ${a.y} C ${c1.x} ${c1.y} ${c2.x} ${c2.y} ${b.x} ${b.y}`;
  }
  return `M ${a.x} ${a.y} Q ${(a.x + b.x) / 2 + 10} ${(a.y + b.y) / 2 - 20} ${b.x} ${b.y}`;
}

function drawRing() {
  const root = $("ring");
  root.replaceChildren();
  const defs = svg("defs");
  const marker = svg("marker", {id: "arrow", viewBox: "0 0 10 10", refX: 19, refY: 5,
    markerWidth: 10, markerHeight: 10, markerUnits:"userSpaceOnUse", orient: "auto-start-reverse"});
  marker.append(svg("path", {d: "M 0 0 L 10 5 L 0 10 z", fill: "context-stroke"}));
  defs.append(marker); root.append(defs);
  root.append(svg("circle", {cx:310, cy:290, r:213, fill:"none", stroke:"#bcc6cf", "stroke-width":1}));
  root.append(svg("circle", {cx:310, cy:290, r:187, fill:"none", stroke:"#dfe4e9", "stroke-dasharray":"2 6"}));
  for (let tick = 0; tick < 64; tick++) {
    const a = point(tick / 64, 229), b = point(tick / 64, tick % 16 === 0 ? 239 : 233);
    root.append(svg("line", {x1:a.x, y1:a.y, x2:b.x, y2:b.y, stroke:"#c0c9d2", "stroke-width":1}));
  }
  for (const [position, label] of [[0,"0000"],[.25,"4000"],[.5,"8000"],[.75,"C000"]]) {
    const p = point(position, 258);
    root.append(svg("text", {x:p.x, y:p.y + 4, "text-anchor":"middle", class:"svg-label"}, label));
  }
  if (!network) return;
  const visible = route ? route.path.slice(0, shown + 1) : [];
  for (let i = 1; i < visible.length; i++) {
    root.append(svg("path", {id:`hop-${i}`, d:hopPath(visible[i-1], visible[i]),
      fill:"none", stroke:nodeColor(visible[i]), "stroke-width":i === shown ? 3 : 2,
      "marker-end":"url(#arrow)", class:"path-line"}));
  }
  const visibleById = new Map(visible.map((hop) => [hop.id, hop]));
  for (const node of network.nodes) {
    const p = point(node.position), hop = visibleById.get(node.id);
    const isSource = route && node.id === route.source;
    const isTarget = route && node.id === route.responsible;
    if (isSource || isTarget) root.append(svg("circle", {cx:p.x, cy:p.y, r:10,
      fill:"none", stroke:isTarget ? colors.target : colors.source, "stroke-width":1.3}));
    const circle = svg("circle", {cx:p.x, cy:p.y, r:hop || isTarget ? 5 : network.n > 300 ? 2 : 3.4,
      fill:isTarget ? colors.target : hop ? nodeColor(hop) : "#8b97a2", class:"ring-node",
      "aria-label":`Nó ${node.hex}. Definir como origem.`, role:"button", tabindex:network.n <= 100 ? 0 : -1});
    circle.append(svg("title", {}, `${node.hex} · ${node.digits} (base ${network.base}) · clique para usar como origem`));
    const select = () => { if (busy) return; $("source").value = node.id; action(() => calculateRoute()); };
    circle.addEventListener("click", select);
    circle.addEventListener("keydown", (event) => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); select(); } });
    root.append(circle);
  }
  if (route) {
    const p = point(route.key_position, 241);
    root.append(svg("path", {d:`M ${p.x} ${p.y-7} l 6 7 l -6 7 l -6 -7 z`, fill:colors.key}));
    const label = point(route.key_position, 275);
    root.append(svg("text", {x:label.x, y:label.y + 4, "text-anchor":"middle",
      fill:colors.key, "font-family":"monospace", "font-size":11}, route.key_hex));
    const current = point(route.path[shown].position);
    root.append(svg("circle", {id:"message", cx:current.x, cy:current.y, r:7,
      fill:shown === route.hops ? colors.target : nodeColor(route.path[shown]),
      stroke:"#fff", "stroke-width":2, class:"message"}));
  }
}

function animateMessage() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  cancelAnimationFrame(motion);
  const element = $("message"), path = $(`hop-${shown}`);
  const length = path.getTotalLength();
  const origin = path.getPointAtLength(0);
  element.setAttribute("cx", origin.x);
  element.setAttribute("cy", origin.y);
  const start = performance.now();
  function frame(now) {
    const t = Math.min(1, (now - start) / 700);
    const position = path.getPointAtLength(length * t);
    element.setAttribute("cx", position.x);
    element.setAttribute("cy", position.y);
    if (t < 1) motion = requestAnimationFrame(frame);
  }
  motion = requestAnimationFrame(frame);
}

function updatePlayback() {
  const unavailable = busy || !route || routeDirty;
  $("step").disabled = unavailable || shown >= route.hops;
  $("back-step").disabled = unavailable || shown === 0;
  $("play").disabled = unavailable || route.hops === 0;
  $("restart").disabled = unavailable || shown === 0;
  $("play").textContent = playing ? "Pausar" : route && shown === route.hops && route.hops > 0 ? "Repetir animação" : "Animar busca";
  $("churn").disabled = busy || routeDirty || !network || network.n < 2;
}

function renderRoute() {
  if (!route) return;
  cancelAnimationFrame(motion);
  drawRing();
  $("key-stat").textContent = route.key_hex;
  $("target-stat").textContent = route.responsible_hex;
  $("hops-stat").textContent = route.hops;
  $("progress-stat").textContent = `${shown} de ${route.hops}`;
  $("path-base").textContent = `base ${network.base}`;
  $("path-key").textContent = route.key_digits;
  $("path-body").replaceChildren();
  route.path.forEach((hop, index) => {
    const row = document.createElement("tr");
    row.className = index === shown ? "current" : index > shown ? "future" : "";
    if (index === shown) row.setAttribute("aria-current", "step");
    const count = row.insertCell(); count.textContent = index;
    const id = row.insertCell(), prefix = document.createElement("strong");
    prefix.textContent = hop.digits.slice(0, hop.prefix_length);
    id.append(prefix, document.createTextNode(hop.digits.slice(hop.prefix_length)));
    id.title = `ID hexadecimal: ${hop.hex}`;
    row.insertCell().textContent = hop.prefix_length;
    const reason = row.insertCell(); reason.textContent = hop.reason; reason.className = "reason";
    $("path-body").append(row);
  });
  const hop = route.path[shown];
  $("route-status").textContent = routeDirty
    ? "Busca anterior. Clique em Buscar chave para usar a nova chave."
    : shown === route.hops
      ? `Busca concluída: o nó ${route.responsible_hex} é o responsável pela chave ${route.key_hex}.`
      : shown === 0
        ? `A mensagem está na origem ${hop.hex}. Clique em Próximo salto ou Animar busca.`
        : `Salto ${shown}: a mensagem chegou ao nó ${hop.hex} pela ${hop.reason === "Tabela" ? "tabela de roteamento" : hop.reason === "Leaf Set" ? "lista de vizinhos (Leaf Set)" : "alternativa de roteamento (Fallback)"}.`;
  const explanations = {
    Origem: route.hops === 0 ? "A própria origem já é o nó mais próximo da chave. Não foi necessário enviar a mensagem." : "Ainda não houve transmissão. A linha 0 da tabela representa o ponto de partida.",
    Tabela: `O nó anterior usou sua tabela para alcançar um ID com mais dígitos iniciais iguais aos da chave. Agora são ${hop.prefix_length}.`,
    "Leaf Set": "A chave está no intervalo dos vizinhos do nó anterior. Ele escolheu o nó mais próximo dela pela distância circular.",
    Fallback: "A entrada da tabela estava vazia. O nó anterior usou outro contato conhecido, com prefixo pelo menos tão longo e mais perto da chave."
  };
  $("hop-explanation").textContent = explanations[hop.reason];
  updatePlayback();
}

function pause() { playing = false; clearTimeout(timer); cancelAnimationFrame(motion); updatePlayback(); }
function advance() {
  if (!route || shown >= route.hops) { pause(); return; }
  shown++;
  renderRoute(); animateMessage();
  if (shown === route.hops) { playing = false; clearTimeout(timer); updatePlayback(); }
}
function tick() { if (!playing) return; advance(); if (playing) timer = setTimeout(tick, 1050); }

function acceptNetwork(data, preferredSource) {
  network = data; route = null; shown = 0; routeDirty = false;
  $("source").replaceChildren(...data.nodes.map((node) => new Option(node.hex, node.id)));
  if (data.nodes.some((node) => node.id === preferredSource)) $("source").value = preferredSource;
  const countLabel = `${data.n} ${data.n === 1 ? "nó" : "nós"}`;
  $("network-label").textContent = `${countLabel} · base ${data.base}`;
  $("ring-caption").textContent = `${countLabel} · base ${data.base}`;
  $("node-count").value = $("node-count-number").value = data.n;
  $("base").value = data.base;
  $("leaf-size").value = data.leaf_size;
  $("seed").value = data.seed;
  $("network-feedback").textContent = `Rede pronta: ${countLabel} ${data.n === 1 ? "ativo" : "ativos"}.`;
  $("key-stat").textContent = $("target-stat").textContent = $("hops-stat").textContent = "—";
  $("progress-stat").textContent = "0 de 0";
  $("path-body").replaceChildren(); $("routing-table").replaceChildren(); $("leaf-detail").textContent = "";
  $("route-status").textContent = "Rede criada. Calculando caminho…";
  $("hop-explanation").textContent = "";
  $("path-key").textContent = "—";
  drawRing();
}

async function inspectSource() {
  const detail = await api(`/api/networks/${network.network_id}/nodes/${$("source").value}`);
  const byId = new Map(network.nodes.map((node) => [node.id, node.hex]));
  $("leaf-detail").textContent = `Nó ${detail.hex} · Leaf Set anti-horário: ${detail.leaf_set.left.map((id) => byId.get(id)).join(", ") || "—"} · horário: ${detail.leaf_set.right.map((id) => byId.get(id)).join(", ") || "—"}`;
  const table = $("routing-table"); table.replaceChildren();
  const head = table.createTHead().insertRow();
  for (const label of ["Prefixo ℓ", ..."0123456789ABCDEF".slice(0, network.base)]) {
    const cell = document.createElement("th"); cell.textContent = label; head.append(cell);
  }
  const body = table.createTBody();
  detail.table.forEach((entries, index) => {
    const row = body.insertRow(); row.insertCell().textContent = index;
    entries.forEach((id) => { row.insertCell().textContent = id === null ? "—" : byId.get(id); });
  });
}

async function calculateRoute(randomize = false) {
  if (!network) throw new Error("Gere uma rede antes de buscar.");
  $("search-feedback").textContent = "Calculando a busca…";
  const data = await api("/api/route", {network_id:network.network_id,
    source:Number($("source").value), key:randomize ? null : $("key").value.trim(),
    random_seed:(network.seed + randomCounter++) % 4294967296});
  route = data; shown = 0; routeDirty = false;
  $("key").value = data.key_hex;
  $("search-feedback").textContent = "Busca pronta. Use os botões abaixo do anel para acompanhar.";
  renderRoute();
  await inspectSource();
}

$("node-count").addEventListener("input", () => $("node-count-number").value = $("node-count").value);
$("node-count-number").addEventListener("input", () => {
  if ($("node-count-number").validity.valid) $("node-count").value = $("node-count-number").value;
});
$("network-form").addEventListener("input", () => {
  $("network-feedback").textContent = "Clique em Criar rede para aplicar as alterações.";
});
$("network-form").addEventListener("invalid", (event) => {
  if (event.target.closest(".advanced")) event.target.closest(".advanced").open = true;
}, true);
$("network-form").addEventListener("submit", (event) => {
  event.preventDefault();
  action(async () => {
    $("network-feedback").textContent = "Criando a rede…";
    const data = await api("/api/networks", {n:Number($("node-count-number").value), base:Number($("base").value),
      leaf_size:Number($("leaf-size").value), seed:Number($("seed").value)});
    acceptNetwork(data); randomCounter = 0; $("churn-status").textContent = "";
    await calculateRoute();
  });
});
$("route-form").addEventListener("submit", (event) => { event.preventDefault(); action(() => calculateRoute()); });
$("random-key").addEventListener("click", () => action(() => calculateRoute(true)));
$("source").addEventListener("change", () => action(() => calculateRoute()));
$("key").addEventListener("input", () => {
  pause();
  routeDirty = true;
  $("search-feedback").textContent = "Clique em Buscar chave para atualizar o caminho.";
  renderRoute();
});
$("step").addEventListener("click", () => { pause(); advance(); });
$("back-step").addEventListener("click", () => { pause(); shown = Math.max(0, shown - 1); renderRoute(); });
$("restart").addEventListener("click", () => { pause(); shown = 0; renderRoute(); });
$("play").addEventListener("click", () => {
  if (playing) { pause(); renderRoute(); return; }
  if (!route) return;
  if (shown === route.hops) { shown = 0; renderRoute(); }
  playing = true; updatePlayback(); tick();
});
$("churn").addEventListener("click", () => action(async () => {
  const previousSource = Number($("source").value), previousTarget = route?.responsible_hex;
  const data = await api("/api/churn", {network_id:network.network_id,
    percent:Number($("churn-percent").value), seed:network.seed});
  acceptNetwork(data, previousSource);
  await calculateRoute();
  const sourceRemoved = data.removed.includes(previousSource);
  $("churn-status").textContent = `${data.removed.length} nós removidos; ${data.n} ativos. Tabelas reconstruídas. ${sourceRemoved ? "A origem saiu; selecionamos uma origem sobrevivente. " : "Origem preservada. "}Responsável: ${previousTarget || "—"} → ${route.responsible_hex}. Busca concluída em ${route.hops} saltos.`;
}));

const tutorialPages = [...document.querySelectorAll(".tutorial-page")];
function showTutorialStep(index) {
  tutorialStep = index;
  tutorialPages.forEach((page, position) => page.hidden = position !== index);
  $("tutorial-counter").textContent = `Etapa ${index + 1} de ${tutorialPages.length}`;
  $("tutorial-progress").value = index + 1;
  $("tutorial-back").disabled = index === 0;
  $("tutorial-next").textContent = index === tutorialPages.length - 1 ? "Começar a simulação" : "Próxima etapa →";
  $("tutorial-content").scrollTop = 0;
  tutorialPages[index].querySelector("h3").focus({preventScroll:true});
}
$("open-tutorial").addEventListener("click", () => {
  pause();
  renderRoute();
  $("tutorial").showModal();
  document.body.classList.add("tutorial-open");
  showTutorialStep(0);
});
$("tutorial-back").addEventListener("click", () => showTutorialStep(Math.max(0, tutorialStep - 1)));
$("tutorial-next").addEventListener("click", () => {
  if (tutorialStep === tutorialPages.length - 1) $("tutorial").close();
  else showTutorialStep(tutorialStep + 1);
});
$("tutorial").addEventListener("keydown", (event) => {
  if (event.key === "Tab") {
    const buttons = [...$("tutorial").querySelectorAll("button:not(:disabled)")];
    const first = buttons[0], last = buttons[buttons.length - 1];
    const active = document.activeElement;
    // Impede que Tab no último botão leve o foco à barra do navegador.
    if (event.shiftKey && (active === first || !buttons.includes(active))) {
      event.preventDefault(); last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault(); first.focus();
    }
  } else if (event.key === "ArrowRight" && tutorialStep < tutorialPages.length - 1) {
    event.preventDefault(); showTutorialStep(tutorialStep + 1);
  } else if (event.key === "ArrowLeft" && tutorialStep > 0) {
    event.preventDefault(); showTutorialStep(tutorialStep - 1);
  }
});
$("tutorial").addEventListener("close", () => {
  document.body.classList.remove("tutorial-open");
  $("open-tutorial").focus({preventScroll:true});
});
drawRing();
$("network-form").requestSubmit();
