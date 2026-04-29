const summaryEl = document.querySelector("#summary");
const nodesEl = document.querySelector("#nodes");
const registryEl = document.querySelector("#registry");
const updatedAtEl = document.querySelector("#updatedAt");
const clusterStatusEl = document.querySelector("#clusterStatus");
const meshStatusEl = document.querySelector("#meshStatus");
const commandsEl = document.querySelector("#commands");
const refreshButton = document.querySelector("#refreshButton");

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function metric(label, value) {
  return `<div class="metric"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`;
}

function renderSummary(data) {
  const nodes = data.nodes || [];
  const jobs = data.jobs || {};
  summaryEl.innerHTML = [
    metric("nodes", nodes.length),
    metric("jobs", jobs.total || 0),
    metric("failed jobs", jobs.failed || 0),
    metric("relay", data.relay?.host || "unknown"),
  ].join("");
}

function renderNodes(nodes) {
  if (!nodes.length) {
    nodesEl.innerHTML = '<div class="empty">No nodes configured.</div>';
    return;
  }
  nodesEl.innerHTML = nodes.map((node) => `
    <article class="nodeCard">
      <div class="taskHead">
        <div>
          <h3>${escapeHtml(node.id)}</h3>
          <div class="node">${escapeHtml(node.platform)} · ${escapeHtml(node.user)}</div>
        </div>
        <span class="pill status-planned">${escapeHtml(node.role || "node")}</span>
      </div>
      <div class="paths">
        <span>repo: ${escapeHtml(node.repo)}</span>
        <span>socket: ${escapeHtml(node.socket)}</span>
        <span>service: ${escapeHtml(node.bridge_service)}</span>
        <span>capabilities: ${escapeHtml((node.capabilities || []).join(", "))}</span>
      </div>
    </article>
  `).join("");
}

function renderCommands(commands) {
  commandsEl.innerHTML = Object.entries(commands || {}).map(([name, command]) => `
    <div class="command"><span>${escapeHtml(name)}</span><code>${escapeHtml(command)}</code></div>
  `).join("");
}

async function loadNetwork() {
  const response = await fetch("/api/network", { cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const data = await response.json();
  registryEl.textContent = data.cluster_file || "";
  updatedAtEl.textContent = `updated ${data.updated_at || ""}`;
  renderSummary(data);
  renderNodes(data.nodes || []);
  clusterStatusEl.textContent = [data.status?.stdout, data.status?.stderr].filter(Boolean).join("\n") || "No cluster status output.";
  meshStatusEl.textContent = [data.mesh?.stdout, data.mesh?.stderr].filter(Boolean).join("\n") || "No mesh output.";
  renderCommands(data.commands || {});
}

refreshButton.addEventListener("click", () => loadNetwork().catch((error) => {
  clusterStatusEl.textContent = error.message;
}));

loadNetwork().catch((error) => {
  clusterStatusEl.textContent = error.message;
});

setInterval(() => {
  loadNetwork().catch(() => {});
}, 5000);
