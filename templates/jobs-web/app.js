const jobsEl = document.querySelector("#jobs");
const summaryEl = document.querySelector("#summary");
const updatedAtEl = document.querySelector("#updatedAt");
const runRootEl = document.querySelector("#runRoot");
const refreshButton = document.querySelector("#refreshButton");

const statusClass = (status) => `status-${String(status || "unknown").replace(/[^a-z0-9-]/gi, "-")}`;

function taskState(task) {
  if (task.returncode === 0) return "succeeded";
  if (typeof task.returncode === "number") return "failed";
  if (task.log_exists) return "running";
  return "planned";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function metric(label, value) {
  return `<div class="metric"><strong>${value}</strong><span>${label}</span></div>`;
}

function renderSummary(data) {
  const jobs = data.jobs || [];
  const running = jobs.filter((job) => ["running", "planned"].includes(job.status)).length;
  const failed = jobs.filter((job) => job.status === "failed").length;
  const tasks = jobs.reduce((count, job) => count + (job.tasks || []).length, 0);
  summaryEl.innerHTML = [
    metric("jobs", jobs.length),
    metric("active", running),
    metric("failed", failed),
    metric("tasks", tasks),
  ].join("");
}

function renderTask(task) {
  const state = taskState(task);
  const tail = task.log_tail && task.log_tail.length ? task.log_tail.join("\n") : "No log output yet.";
  const elapsed = task.elapsed_seconds == null ? "" : ` · ${task.elapsed_seconds}s`;
  return `
    <article class="task">
      <div class="taskHead">
        <div>
          <h3>${escapeHtml(task.title || task.id)}</h3>
          <div class="node">${escapeHtml(task.node)} · ${escapeHtml(task.id)}${elapsed}</div>
        </div>
        <span class="pill ${statusClass(state)}">${escapeHtml(state)}</span>
      </div>
      <p class="scope">${escapeHtml(task.scope)}</p>
      <pre class="log">${escapeHtml(tail)}</pre>
      <div class="paths">
        <span>log: ${escapeHtml(task.log)}</span>
        <span>script: ${escapeHtml(task.script)}</span>
      </div>
    </article>
  `;
}

function renderJob(job) {
  const tasks = (job.tasks || []).map(renderTask).join("");
  return `
    <article class="job">
      <div class="jobHeader">
        <div>
          <div class="jobTitle">
            <h2>${escapeHtml(job.id)}</h2>
            <span class="pill ${statusClass(job.status)}">${escapeHtml(job.status)}</span>
          </div>
          <p class="feature">${escapeHtml(job.feature || job.error || "No feature text.")}</p>
          <p class="meta">created ${escapeHtml(job.created_at || "unknown")} · finished ${escapeHtml(job.finished_at || "not finished")}</p>
        </div>
        <div class="meta">
          <div>${escapeHtml(job.repo)}</div>
          <div>${escapeHtml(job.job)}</div>
          <div>${escapeHtml(job.summary)}</div>
        </div>
      </div>
      <div class="tasks">${tasks}</div>
    </article>
  `;
}

async function loadJobs() {
  const response = await fetch("/api/jobs", { cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const data = await response.json();
  runRootEl.textContent = data.run_root || "";
  updatedAtEl.textContent = `updated ${data.updated_at || ""}`;
  renderSummary(data);
  if (!data.jobs || data.jobs.length === 0) {
    jobsEl.innerHTML = '<div class="empty">No cluster jobs yet. Run cento cluster implement "feature" --dry-run.</div>';
    return;
  }
  jobsEl.innerHTML = data.jobs.map(renderJob).join("");
}

refreshButton.addEventListener("click", () => loadJobs().catch((error) => {
  jobsEl.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
}));

loadJobs().catch((error) => {
  jobsEl.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
});

setInterval(() => {
  loadJobs().catch(() => {});
}, 2000);
