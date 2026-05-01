const listView = document.querySelector("#listView");
const detailView = document.querySelector("#detailView");
const issueRows = document.querySelector("#issueRows");
const detailContent = document.querySelector("#detailContent");
const historyList = document.querySelector("#historyList");
const backButton = document.querySelector("#backButton");
const clearFiltersButton = document.querySelector("#clearFiltersButton");
const savedQuerySelect = document.querySelector("#savedQuerySelect");
const queryNameInput = document.querySelector("#queryNameInput");
const newIssueButton = document.querySelector("#newIssueButton");
const headerNewIssueButton = document.querySelector("#headerNewIssueButton");
const saveQueryButton = document.querySelector("#saveQueryButton");
const exportJsonButton = document.querySelector("#exportJsonButton");
const exportCsvButton = document.querySelector("#exportCsvButton");
const statusFilter = document.querySelector("#statusFilter");
const trackerFilter = document.querySelector("#trackerFilter");
const packageFilter = document.querySelector("#packageFilter");
const roleFilter = document.querySelector("#roleFilter");
const agentFilter = document.querySelector("#agentFilter");
const updatedFromFilter = document.querySelector("#updatedFromFilter");
const updatedToFilter = document.querySelector("#updatedToFilter");
const evidenceFilter = document.querySelector("#evidenceFilter");
const riskFilter = document.querySelector("#riskFilter");
const searchInput = document.querySelector("#searchInput");
const rangeLabel = document.querySelector("#rangeLabel");
const listLoading = document.querySelector("#listLoading");
const emptyState = document.querySelector("#emptyState");
const prevPageButton = document.querySelector("#prevPage");
const nextPageButton = document.querySelector("#nextPage");
const pageButton = document.querySelector("#pageButton");
const perPageButtons = document.querySelectorAll(".perPageButton");
const countLinks = document.querySelectorAll("a[data-filter]");
const mainNavLinks = document.querySelectorAll("[data-main-route]");
const primaryNavLinks = document.querySelectorAll("[data-nav-route]");
const agentSummary = document.querySelector("#agentSummary");
const agentCards = document.querySelector("#agentCards");
const taskstreamNav = document.querySelector(".taskstreamNav");
const clusterView = document.querySelector("#clusterView");
const consultingView = document.querySelector("#consultingView");
const factoryView = document.querySelector("#factoryView");
const docsView = document.querySelector("#docsView");
const factoryRunList = document.querySelector("#factoryRunList");
const factoryRunCount = document.querySelector("#factoryRunCount");
const factoryDeliveredCount = document.querySelector("#factoryDeliveredCount");
const factoryQueuedCount = document.querySelector("#factoryQueuedCount");
const factoryAiCalls = document.querySelector("#factoryAiCalls");
const issueModal = document.querySelector("#issueModal");
const issueForm = document.querySelector("#issueForm");
const issueModalTitle = document.querySelector("#issueModalTitle");
const issueSubmitButton = document.querySelector("#issueSubmitButton");
const issueIdInput = document.querySelector("#issueId");
const issueSubjectInput = document.querySelector("#issueSubject");
const issueTrackerInput = document.querySelector("#issueTracker");
const issueStatusInput = document.querySelector("#issueStatus");
const issuePriorityInput = document.querySelector("#issuePriority");
const issueAssigneeInput = document.querySelector("#issueAssignee");
const issueAgentInput = document.querySelector("#issueAgent");
const issueRoleInput = document.querySelector("#issueRole");
const issuePackageInput = document.querySelector("#issuePackage");
const issueNodeInput = document.querySelector("#issueNode");
const issueDoneRatioInput = document.querySelector("#issueDoneRatio");
const issueValidationReportInput = document.querySelector("#issueValidationReport");
const issueDescriptionInput = document.querySelector("#issueDescription");
const detailEditButton = document.querySelector("#detailEditButton");
const statusForm = document.querySelector("#statusForm");
const statusSelect = document.querySelector("#detailStatusSelect");
const detailDoneRatio = document.querySelector("#detailDoneRatio");
const detailAssignee = document.querySelector("#detailAssignee");
const detailTransitionNote = document.querySelector("#detailTransitionNote");
const journalForm = document.querySelector("#journalForm");
const journalAuthor = document.querySelector("#journalAuthor");
const journalNote = document.querySelector("#journalNote");
const evidenceForm = document.querySelector("#evidenceForm");
const evidenceType = document.querySelector("#evidenceType");
const evidenceLabel = document.querySelector("#evidenceLabel");
const evidencePath = document.querySelector("#evidencePath");
const evidenceNote = document.querySelector("#evidenceNote");
const reviewView = document.querySelector("#reviewView");
const reviewQueue = document.querySelector("#reviewQueue");
const reviewTotal = document.querySelector("#reviewTotal");
const reviewApproveCount = document.querySelector("#reviewApproveCount");
const reviewFixCount = document.querySelector("#reviewFixCount");
const reviewRejectCount = document.querySelector("#reviewRejectCount");
const reviewBlockerCount = document.querySelector("#reviewBlockerCount");
const reviewAgent = document.querySelector("#reviewAgent");
const reviewTask = document.querySelector("#reviewTask");
const reviewIssue = document.querySelector("#reviewIssue");
const reviewPosition = document.querySelector("#reviewPosition");
const reviewArtifactTitle = document.querySelector("#reviewArtifactTitle");
const reviewConfidence = document.querySelector("#reviewConfidence");
const reviewArtifact = document.querySelector("#reviewArtifact");
const reviewLogText = document.querySelector("#reviewLogText");
const reviewLogHighlights = document.querySelector("#reviewLogHighlights");
const reviewContext = document.querySelector("#reviewContext");
const reviewAutoAdvance = document.querySelector("#reviewAutoAdvance");
const reviewApprove = document.querySelector("#reviewApprove");
const reviewReject = document.querySelector("#reviewReject");
const reviewNeedsFix = document.querySelector("#reviewNeedsFix");
const blockerResolution = document.querySelector("#blockerResolution");
const blockerKind = document.querySelector("#blockerKind");
const blockerSummary = document.querySelector("#blockerSummary");
const blockerNote = document.querySelector("#blockerNote");
const blockerQuestion = document.querySelector("#blockerQuestion");
const blockerCommand = document.querySelector("#blockerCommand");
const blockerRequeue = document.querySelector("#blockerRequeue");
const API_BASE = "/api";
const PAGE_OPTIONS = [25, 50];
const ISSUE_STATUS_OPTIONS = ["Queued", "Running", "Review", "Blocked", "Validating", "Done"];
const LOCAL_STORAGE_KEY = "cento.agentWork.filters";
const LOCAL_STORAGE_QUERY_KEY = "cento.agentWork.savedQuery";

let allIssues = [];
let visibleIssues = [];
let totalIssues = 0;
let searchTerm = "";
let page = 1;
let perPage = 25;
let activeFilter = "open";
let activeTracker = "all";
let activePackage = "";
let activeRole = "";
let activeAgent = "";
let activeUpdatedFrom = "";
let activeUpdatedTo = "";
let activeEvidence = "";
let activeRisk = "";
let savedQueries = [];
let activeQueryId = "";
let reviewItems = [];
let reviewSelectedIndex = 0;
let reviewDetailPayload = null;
let reviewActiveArtifactTab = "screenshot";
let detailPayload = null;
let detailIssueId = null;
let detailLoadingId = null;
let loadedIssueMode = "create";

function clampInt(value, fallback, minValue = 1) {
  const parsed = Number.parseInt(value, 10);
  return Number.isInteger(parsed) ? Math.max(minValue, parsed) : fallback;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function statusClass(status) {
  return `status-${String(status || "").toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}

function shortDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function compactDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function dateInputValue(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString().slice(0, 10);
}

function parseDateOnly(value) {
  if (!value) return null;
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function fillStatusOptions(select) {
  if (!select) return;
  select.innerHTML = ISSUE_STATUS_OPTIONS.map((status) => `<option value="${escapeHtml(status)}">${escapeHtml(status)}</option>`).join("");
}

function getFilterState() {
  return {
    status: statusFilter.value || "open",
    tracker: trackerFilter.value || "",
    package: packageFilter.value.trim(),
    role: roleFilter.value.trim(),
    agent: agentFilter.value.trim(),
    search: searchInput.value.trim(),
    updatedFrom: updatedFromFilter.value,
    updatedTo: updatedToFilter.value,
    evidence: evidenceFilter.value,
    risk: riskFilter.value,
  };
}

function applyFilterState(state = {}) {
  activeFilter = state.status || "open";
  activeTracker = state.tracker || "all";
  activePackage = state.package || "";
  activeRole = state.role || "";
  activeAgent = state.agent || "";
  searchTerm = state.search || "";
  activeUpdatedFrom = state.updatedFrom || "";
  activeUpdatedTo = state.updatedTo || "";
  activeEvidence = state.evidence || "";
  activeRisk = state.risk || "";

  statusFilter.value = activeFilter;
  trackerFilter.value = activeTracker === "all" ? "" : activeTracker;
  packageFilter.value = activePackage;
  roleFilter.value = activeRole;
  agentFilter.value = activeAgent;
  searchInput.value = searchTerm;
  updatedFromFilter.value = activeUpdatedFrom;
  updatedToFilter.value = activeUpdatedTo;
  evidenceFilter.value = activeEvidence;
  riskFilter.value = activeRisk;
  setFilterActive(activeTracker);
  setPerPageButtons();
}

function persistFilterState() {
  try {
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(getFilterState()));
    if (activeQueryId) {
      localStorage.setItem(LOCAL_STORAGE_QUERY_KEY, activeQueryId);
    } else {
      localStorage.removeItem(LOCAL_STORAGE_QUERY_KEY);
    }
  } catch {
    // Ignore storage failures in locked-down browser contexts.
  }
}

function loadPersistedFilterState() {
  try {
    const raw = localStorage.getItem(LOCAL_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

function issueRiskFlag(issue) {
  const haystack = [
    issue.subject,
    issue.description,
    issue.validation_report,
    issue.package,
  ]
    .map((value) => String(value || "").toLowerCase())
    .join(" ");
  return /risk|blocker|critical|high-risk|high risk/.test(haystack);
}

function issueHasEvidence(issue) {
  return Boolean(
    String(issue.validation_report || "").trim() ||
    String(issue.closed_on || "").trim() ||
    String(issue.dispatch || "").trim()
  );
}

function validationState(issue) {
  return issue?.validation_state && typeof issue.validation_state === "object" ? issue.validation_state : {};
}

function validationLabel(issue) {
  const state = validationState(issue);
  const mode = state.mode || "unknown";
  const coverage = Number(state.automation_coverage_percent || 0);
  if (state.escalation_state === "ready") return `${mode} ${coverage.toFixed(0)}%`;
  if (state.escalation_state === "manual-review") return `${mode} manual`;
  if (state.escalation_state === "low-coverage") return `${mode} ${coverage.toFixed(0)}%`;
  if (state.escalation_state === "missing-validation") return `${mode} missing`;
  return mode;
}

function validationClass(issue) {
  const state = validationState(issue);
  return `validation-${String(state.escalation_state || "unknown").toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}

function issueUpdatedInRange(issue, startValue, endValue) {
  const updated = new Date(issue.updated_on);
  if (Number.isNaN(updated.getTime())) return true;
  const start = parseDateOnly(startValue);
  const end = parseDateOnly(endValue);
  if (start && updated < start) return false;
  if (end) {
    const endOfDay = new Date(end);
    endOfDay.setHours(23, 59, 59, 999);
    if (updated > endOfDay) return false;
  }
  return true;
}

function issueMatchesFilters(issue) {
  const status = String(activeFilter || "open").toLowerCase();
  const issueStatus = String(issue.status || "").toLowerCase();
  if (status === "open") {
    if (issueStatus === "done") return false;
  } else if (status !== "all" && issueStatus !== status) {
    return false;
  }
  if (activeTracker !== "all" && String(issue.tracker || "").toLowerCase() !== activeTracker.toLowerCase()) return false;
  if (activePackage && String(issue.package || "").toLowerCase().indexOf(activePackage.toLowerCase()) === -1) return false;
  if (activeRole && String(issue.role || "").toLowerCase().indexOf(activeRole.toLowerCase()) === -1) return false;
  if (activeAgent) {
    const agentBlob = `${issue.agent || ""} ${issue.assignee || ""}`.toLowerCase();
    if (!agentBlob.includes(activeAgent.toLowerCase())) return false;
  }
  if (searchTerm) {
    const blob = [
      issue.id,
      issue.subject,
      issue.tracker,
      issue.status,
      issue.priority,
      issue.assignee,
      issue.agent,
      issue.role,
      issue.package,
      issue.description,
      issue.validation_report,
      validationLabel(issue),
      validationState(issue).escalation_state,
    ]
      .map((value) => String(value || "").toLowerCase())
      .join(" ");
    if (!blob.includes(searchTerm.toLowerCase())) return false;
  }
  if (!issueUpdatedInRange(issue, activeUpdatedFrom, activeUpdatedTo)) return false;
  if (activeEvidence === "present" && !issueHasEvidence(issue)) return false;
  if (activeEvidence === "missing" && issueHasEvidence(issue)) return false;
  if (activeRisk === "flagged" && !issueRiskFlag(issue)) return false;
  if (activeRisk === "clear" && issueRiskFlag(issue)) return false;
  return true;
}

function filteredIssueRows() {
  return allIssues.filter(issueMatchesFilters);
}

function currentPageIssues() {
  const filtered = filteredIssueRows();
  totalIssues = filtered.length;
  const totalPages = Math.max(1, Math.ceil(totalIssues / perPage));
  if (page > totalPages) page = totalPages;
  const start = Math.max(0, (page - 1) * perPage);
  visibleIssues = filtered.slice(start, start + perPage);
  return visibleIssues;
}

function poolLabel(run) {
  const agent = String(run.agent || "");
  if (agent.startsWith("small-worker")) return "small";
  return String(run.role || "builder");
}

function getTrackerCount(data, tracker) {
  if (tracker === "all") return data.length;
  return data.filter((issue) => issue.tracker === tracker).length;
}

function setFilterCounts(counts = {}, fallbackData = allIssues) {
  const value = (key) => {
    const raw = counts[key];
    const count = Number.parseInt(raw, 10);
    return Number.isInteger(count) ? count : getTrackerCount(fallbackData, key);
  };

  document.querySelector("#countAll").textContent = value("all") || getTrackerCount(fallbackData, "all");
  document.querySelector("#countAgentTask").textContent = value("Agent Task");
  document.querySelector("#countFeature").textContent = value("Feature");
  document.querySelector("#countBug").textContent = value("Bug");
  document.querySelector("#countSupport").textContent = value("Support");
  document.querySelector("#countReview").textContent = value("Review");
}

function setFilterActive(tracker) {
  for (const link of countLinks) {
    const match = link.dataset.filter === tracker;
    link.classList.toggle("active", match);
  }
}

function setPerPageButtons() {
  for (const button of perPageButtons) {
    const value = Number.parseInt(button.textContent, 10);
    if (!Number.isInteger(value)) continue;
    button.classList.toggle("pageActive", value === perPage);
  }
}

function setListLoading(isLoading) {
  listLoading.classList.toggle("hidden", !isLoading);
  if (isLoading) {
    emptyState.classList.add("hidden");
  }
}

function setLocationFromState() {
  const params = new URLSearchParams();
  if (activeFilter) params.set("status", activeFilter);
  if (activeTracker !== "all") params.set("tracker", activeTracker);
  if (activePackage) params.set("package", activePackage);
  if (activeRole) params.set("role", activeRole);
  if (activeAgent) params.set("agent", activeAgent);
  if (searchTerm) {
    params.set("search", searchTerm);
    params.set("q", searchTerm);
  }
  if (activeUpdatedFrom) params.set("updated_from", activeUpdatedFrom);
  if (activeUpdatedTo) params.set("updated_to", activeUpdatedTo);
  if (activeEvidence) params.set("evidence", activeEvidence);
  if (activeRisk) params.set("risk", activeRisk);
  if (activeQueryId) params.set("query", activeQueryId);
  if (page > 1) params.set("page", String(page));
  if (perPage !== 25) params.set("per_page", String(perPage));

  const suffix = params.toString() ? `?${params.toString()}` : "";
  history.replaceState(null, "", `${location.pathname.startsWith("/issues/") ? "/" : location.pathname}${suffix}`);
}

function syncStateFromLocation() {
  const params = new URLSearchParams(location.search);
  activeFilter = params.get("status") || "open";
  activeTracker = params.get("tracker") || "all";
  activePackage = params.get("package") || "";
  activeRole = params.get("role") || "";
  activeAgent = params.get("agent") || "";
  searchTerm = params.get("search") || params.get("q") || "";
  activeUpdatedFrom = params.get("updated_from") || "";
  activeUpdatedTo = params.get("updated_to") || "";
  activeEvidence = params.get("evidence") || "";
  activeRisk = params.get("risk") || "";
  activeQueryId = params.get("query") || "";
  page = clampInt(params.get("page"), page);
  perPage = clampInt(params.get("per_page"), perPage);
  if (!PAGE_OPTIONS.includes(perPage)) perPage = 25;

  const persisted = loadPersistedFilterState();
  if (persisted && !location.search) {
    applyFilterState(persisted);
  } else {
    applyFilterState({
      status: activeFilter,
      tracker: activeTracker,
      package: activePackage,
      role: activeRole,
      agent: activeAgent,
      search: searchTerm,
      updatedFrom: activeUpdatedFrom,
      updatedTo: activeUpdatedTo,
      evidence: activeEvidence,
      risk: activeRisk,
    });
  }
  if (activeQueryId) {
    localStorage.setItem(LOCAL_STORAGE_QUERY_KEY, activeQueryId);
  }
}

function listQueryUrl() {
  const query = new URLSearchParams();
  query.set("status", "all");
  query.set("limit", "0");
  return `${API_BASE}/issues?${query.toString()}`;
}

function renderRows(visibleIssues) {
  const totalPages = Math.max(1, Math.ceil(totalIssues / perPage));
  if (page > totalPages) page = totalPages;

  issueRows.innerHTML = visibleIssues.map((issue) => `
    <tr>
      <td><input type=\"checkbox\" /></td>
      <td><a class="issueId" href="/issues/${issue.id}" data-issue="${issue.id}">#${escapeHtml(issue.id)}</a></td>
      <td>${escapeHtml(issue.tracker)}</td>
      <td><span class=\"statusDot ${statusClass(issue.status)}\"></span>${escapeHtml(issue.status)}</td>
      <td><span class="validationBadge ${validationClass(issue)}">${escapeHtml(validationLabel(issue))}</span></td>
      <td>${escapeHtml(issue.priority || "Normal")}</td>
      <td><a class="subjectLink" href="/issues/${issue.id}" data-issue="${issue.id}">${escapeHtml(issue.subject)}</a></td>
      <td class="assignee">${escapeHtml(issue.assignee || issue.agent || "Taskstream Admin")}</td>
      <td>${escapeHtml(shortDate(issue.updated_on))}</td>
    </tr>
  `).join("");

  prevPageButton.disabled = page <= 1;
  nextPageButton.disabled = page >= totalPages;
  pageButton.textContent = String(page);
  if (totalIssues === 0) {
    rangeLabel.textContent = "(0/0)";
    emptyState.classList.remove("hidden");
  } else {
    const start = Math.min(totalIssues, (page - 1) * perPage + 1);
    const end = Math.min(totalIssues, page * perPage);
    rangeLabel.textContent = `(${start}-${end}/${totalIssues})`;
    emptyState.classList.add("hidden");
  }
}

function renderAgents(payload) {
  const runs = Array.isArray(payload.runs) ? payload.runs : [];
  const summary = payload.summary || {};
  const pools = summary.by_pool || {};
  const targets = summary.targets || {};
  const live = Number(summary.live || 0);
  const actionableStale = Number(summary.actionable_stale ?? summary.stale ?? 0);
  const historicalStale = Number(summary.historical_stale || 0);
  agentSummary.textContent =
    `${live} live, ${actionableStale} actionable stale, ${historicalStale} historical · builders ${pools.builder || 0}/${targets.builder || 0} · validators ${pools.validator || 0}/${targets.validator || 0} · small ${pools.small || 0}/${targets.small || 0} · coordinators ${pools.coordinator || 0}/${targets.coordinator || 0}`;

  const rankedRuns = runs
    .slice()
    .sort((a, b) => Number(Boolean(b.pid_alive || b.tmux_alive)) - Number(Boolean(a.pid_alive || a.tmux_alive)))
    .slice(0, 12);

  agentCards.innerHTML = rankedRuns.map((run) => {
    const alive = Boolean(run.pid_alive || run.tmux_alive || run.status === "untracked_interactive");
    const state = alive ? "live" : "stale";
    const subject = String(run.issue_subject || run.command || "untracked agent");
    const issue = run.issue_id ? `#${escapeHtml(run.issue_id)}` : "untracked";
    return `
      <article class="agentCard ${state}">
        <div class="agentCardTop">
          <strong>${escapeHtml(issue)}</strong>
          <span>${escapeHtml(state)}</span>
        </div>
        <p>${escapeHtml(subject)}</p>
        <footer>
          <span>${escapeHtml(poolLabel(run))}</span>
          <span>${escapeHtml(run.agent || run.runtime_display_name || "agent")}</span>
          <span>${escapeHtml(compactDate(run.started_at))}</span>
        </footer>
      </article>
    `;
  }).join("");
}

function getVisibleIssues(payload) {
  const returnedIssues = Array.isArray(payload.issues) ? payload.issues : [];
  totalIssues = Number(payload.total);
  if (!Number.isInteger(totalIssues) || totalIssues < 0) totalIssues = returnedIssues.length;

  const serverSupportsPagination =
    returnedIssues.length < totalIssues ||
    payload.offset !== undefined ||
    payload.limit !== undefined ||
    payload.page !== undefined;
  if (serverSupportsPagination) {
    return returnedIssues;
  }

  const start = (page - 1) * perPage;
  return returnedIssues.slice(start, start + perPage);
}

function parseIssueSections(description) {
  const lines = String(description || "").replace(/\r\n/g, "\n").split("\n");
  const heading = /^\s*h[23]\.\s*(.+?)\s*$/i;
  const sections = new Map();
  let active = "__body__";
  const buffer = [];

  for (const line of lines) {
    const match = line.match(heading);
    if (match) {
      sections.set(active, buffer.splice(0).join("\n").trim());
      active = String(match[1] || "").trim().toLowerCase();
      continue;
    }
    buffer.push(line);
  }
  sections.set(active, buffer.join("\n").trim());

  const pick = (keys) => {
    const normalized = keys.map((key) =>
      String(key).toLowerCase().replace(/[^a-z0-9]/g, "")
    );
    for (const [name, value] of sections) {
      const normalizedName = String(name || "").toLowerCase().replace(/[^a-z0-9]/g, "");
      for (const key of normalized) {
        if (!key) continue;
        if (
          normalizedName.includes(key) ||
          key.includes(normalizedName) ||
          normalizedName === key
        ) {
          return String(value || "").trim();
        }
      }
    }
    return "";
  };

  return {
    objective: pick(["objective"]) || pick(["task"]) || pick(["goal"]) || pick(["body"]) || pick(["description"]) || "No description provided.",
    acceptance: pick(["acceptance criteria", "acceptance", "criteria"]) || "No acceptance criteria provided.",
    protocol: pick(["agent protocol"]) || "",
  };
}

function getCustomFieldValue(customFields, ...names) {
  const fieldMap = new Map();
  for (const [key, value] of Object.entries(customFields || {})) {
    fieldMap.set(String(key).trim().toLowerCase().replace(/[^a-z0-9]/g, ""), String(value || ""));
  }
  for (const name of names) {
    const candidate = String(name).trim().toLowerCase().replace(/[^a-z0-9]/g, "");
    if (fieldMap.has(candidate)) return fieldMap.get(candidate);
  }
  return "";
}

function buildMetaRows(issue, customFields) {
  const percent = Number(issue.done_ratio || 0);
  const safePercent = Number.isFinite(percent) ? Math.max(0, Math.min(percent, 100)) : 0;
  const rows = [];
  const add = (label, value) => {
    rows.push(`<div class="metaRow"><span>${escapeHtml(label)}:</span><strong>${escapeHtml(value || "-")}</strong></div>`);
  };

  add("Project", issue.project);
  add("Tracker", issue.tracker);
  add("Status", issue.status);
  add("Priority", issue.priority || "Normal");
  add("Assignee", issue.assignee || issue.agent || "Taskstream Admin");
  add("Node", issue.node || getCustomFieldValue(customFields, "Agent Node", "Node") || "—");
  add("Owner", issue.agent || getCustomFieldValue(customFields, "Agent Owner", "Owner") || "—");
  add("Role", issue.role || getCustomFieldValue(customFields, "Agent Role", "Role") || "—");
  add("Package", issue.package || getCustomFieldValue(customFields, "Cento Work Package", "Package") || "default");
  add("Validation mode", validationLabel(issue));
  add("Escalation state", validationState(issue).escalation_state || "unknown");
  add("Dispatch", getCustomFieldValue(customFields, "Cluster Dispatch", "Dispatch") || "Not dispatched");
  add("Validation report", getCustomFieldValue(customFields, "Validation Report", "Validation Report"));
  add("Due date", getCustomFieldValue(customFields, "Due Date", "Due") || "-");
  add("Start date", getCustomFieldValue(customFields, "Start Date", "Start") || "-");
  rows.push(`<div class="metaRow"><span>% Done:</span><div class="progress"><div class="bar"><b style="width:${safePercent}%"></b></div><strong>${safePercent}%</strong></div></div>`);
  add("Target version", "Industrial OS 1.1");
  add("Story Points", getCustomFieldValue(customFields, "Story Points") || "5");
  add("Sprint", getCustomFieldValue(customFields, "Sprint") || "Industrial OS Sprint 7");
  add("Risk Level", getCustomFieldValue(customFields, "Risk Level") || "Medium");
  add("Updated", shortDate(issue.updated_on));
  add("Created", shortDate(issue.created_on));

  return rows.join("");
}

function normalizeAttachmentLabel(item) {
  const name = String(item.filename || item.label || "").trim();
  if (name) return name;
  const rawPath = String(item.path || item.url || "");
  if (!rawPath) return "Untitled attachment";
  const slash = rawPath.split("/").filter(Boolean);
  return slash.length ? slash[slash.length - 1] : "Untitled attachment";
}

function renderTextBody(content) {
  const trimmed = String(content || "").trim();
  if (!trimmed) return `<p class="emptyText">No content.</p>`;
  return `<pre class="detailText">${escapeHtml(trimmed)}</pre>`;
}

function metaRow(label, value) {
  return `<div class="metaRow"><span>${escapeHtml(label)}:</span><strong>${escapeHtml(value || "-")}</strong></div>`;
}

function renderDetail(payload) {
  detailPayload = payload;
  const issue = payload.issue || {};
  const percent = Number(issue.done_ratio || 0);
  const sections = parseIssueSections(issue.description);
  const journals = Array.isArray(payload.journals) ? payload.journals : [];
  const attachments = Array.isArray(payload.attachments) ? payload.attachments : [];
  const validationEvidences = Array.isArray(payload.validation_evidences) ? payload.validation_evidences : [];
  const customFields = payload.custom_fields || {};
  const safePercent = Number.isFinite(percent) ? Math.max(0, Math.min(percent, 100)) : 0;
  const assignee = issue.assignee || issue.agent || "Taskstream Admin";
  const source = String(issue.source || "local");

  const attachmentRows = [
    ...attachments.map((item) => {
      const created = shortDate(item.created_on);
      return `
        <div class="attachmentRow">
          <strong>▧ ${escapeHtml(normalizeAttachmentLabel(item))}</strong>
          <span>${escapeHtml(item.size || "-")}</span>
          <span>${escapeHtml(created || "—")}</span>
          <span>attachment</span>
        </div>`;
    }),
    ...validationEvidences.map((item) => {
      const created = shortDate(item.created_on);
      return `
        <div class="attachmentRow">
          <strong>✓ ${escapeHtml(normalizeAttachmentLabel(item))}</strong>
          <span>${escapeHtml(item.url ? "url" : "evidence")}</span>
          <span>${escapeHtml(created || "—")}</span>
          <span>${escapeHtml(item.label || "Evidence")}</span>
        </div>`;
    }),
  ];

  detailContent.innerHTML = `
    <div class="detailSummary">
      <div class="detailBadges">
        <strong class="issueId">#${escapeHtml(issue.id)}</strong>
        <span class="badge">${escapeHtml(issue.tracker || "Agent Task")}</span>
        <span class="badge status"><span class="statusDot ${statusClass(issue.status)}"></span>${escapeHtml(issue.status || "Unknown")}</span>
        <span class="badge validation ${validationClass(issue)}">${escapeHtml(validationLabel(issue))}</span>
        <span class="badge">Priority ${escapeHtml(issue.priority || "Normal")}</span>
        <span class="badge">Source ${escapeHtml(source)}</span>
      </div>
      <h1 class="issueTitle">${escapeHtml(issue.subject || "Untitled issue")}</h1>
      <p class="issueMeta">Added by <strong>${escapeHtml(assignee)}</strong>. Updated ${escapeHtml(shortDate(issue.updated_on) || "—")}.</p>
    </div>
    <section class="metaGrid">
      ${buildMetaRows(issue, customFields)}
    </section>
    <div class="sectionGrid">
      <section class="detailSection description">
        <h2>Description</h2>
        ${renderTextBody(sections.objective)}
      </section>
      <section class="detailSection acceptance">
        <h2>Acceptance Criteria</h2>
        ${renderTextBody(sections.acceptance)}
      </section>
      <section class="detailSection attachments">
        <div class="attachmentsHeader">
          <h2>Evidence (${attachmentRows.length})</h2>
          <span>${escapeHtml(source)}</span>
        </div>
        ${attachmentRows.length
          ? attachmentRows.join("")
          : '<div class="attachmentRow"><span>No attachments yet</span></div>'}
      </section>
    </div>
  `;

  fillStatusOptions(statusSelect);
  if (issue.status) statusSelect.value = issue.status;
  detailDoneRatio.value = String(safePercent);
  detailAssignee.value = assignee;
  journalAuthor.value = issue.assignee || issue.agent || "local operator";
  journalNote.value = "";
  evidenceType.value = "attachment";
  evidenceLabel.value = "";
  evidencePath.value = "";
  evidenceNote.value = "";

  if (journals.length === 0) {
    historyList.innerHTML = `<div class="historyCard historyEmpty">No activity yet.</div>`;
    return;
  }
  historyList.innerHTML = journals.map((journal, index) => {
    const author = String(journal.author || "Taskstream Admin");
    const oldStatus = String(journal.old_status || "");
    const newStatus = String(journal.new_status || issue.status || "");
    const summary = oldStatus
      ? `Status changed from <mark>${escapeHtml(oldStatus)}</mark> to <mark>${escapeHtml(newStatus)}</mark>`
      : newStatus
        ? `Status set to <mark>${escapeHtml(newStatus)}</mark>`
        : "Update";
    const notes = escapeHtml(journal.notes || journal.note || "");
    const eventNumber = journals.length - index;

    return `
      <article class="historyCard">
        <div class="historyMeta"><strong>${escapeHtml(author)}</strong><span>#${eventNumber}</span></div>
        <p class="historyText">${shortDate(journal.created_on)} • ${summary}</p>
        ${notes ? `<pre class="historyText">${notes}</pre>` : ""}
      </article>
    `;
  }).join("");
}

function promptSubject(prompt, fallback = "") {
  const lines = String(prompt || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const candidate = lines.find((line) => line.length >= 12) || lines[0] || fallback || "New agent task";
  return candidate.length > 90 ? `${candidate.slice(0, 87)}...` : candidate;
}

function issueFormPayload() {
  const prompt = issueDescriptionInput.value.trim();
  return {
    subject: issueSubjectInput.value.trim() || promptSubject(prompt),
    tracker: issueTrackerInput.value.trim() || "Agent Task",
    status: issueStatusInput.value,
    priority: issuePriorityInput.value.trim() || "Normal",
    assignee: issueAssigneeInput.value.trim(),
    agent: issueAgentInput.value.trim(),
    role: issueRoleInput.value.trim() || "builder",
    package: issuePackageInput.value.trim() || "default",
    node: issueNodeInput.value.trim(),
    done_ratio: Number.parseInt(issueDoneRatioInput.value, 10) || 0,
    validation_report: issueValidationReportInput.value.trim(),
    description: prompt,
  };
}

function setIssueFormMode(mode, issue = null) {
  loadedIssueMode = mode;
  issueModalTitle.textContent = mode === "edit" ? `Edit prompt #${issue?.id || ""}`.trim() : "Create from prompt";
  if (issueSubmitButton) issueSubmitButton.textContent = mode === "edit" ? "Save issue" : "Create issue";
  issueIdInput.value = issue?.id ? String(issue.id) : "";
  issueSubjectInput.value = issue?.subject || "";
  issueTrackerInput.value = issue?.tracker || "Agent Task";
  issueStatusInput.value = issue?.status || "Queued";
  issuePriorityInput.value = issue?.priority || "Normal";
  issueAssigneeInput.value = issue?.assignee || issue?.agent || "local operator";
  issueAgentInput.value = issue?.agent || "";
  issueRoleInput.value = issue?.role || "builder";
  issuePackageInput.value = issue?.package || "default";
  issueNodeInput.value = issue?.node || "";
  issueDoneRatioInput.value = String(issue?.done_ratio || 0);
  issueValidationReportInput.value = issue?.validation_report || "";
  issueDescriptionInput.value = issue?.description || "";
}

function openIssueModal(issue = null) {
  setIssueFormMode(issue ? "edit" : "create", issue);
  issueModal.classList.remove("hidden");
  issueModal.setAttribute("aria-hidden", "false");
  window.requestAnimationFrame(() => issueDescriptionInput.focus());
}

function closeIssueModal() {
  issueModal.classList.add("hidden");
  issueModal.setAttribute("aria-hidden", "true");
}

function currentIssueIdFromDetail() {
  if (detailPayload?.issue?.id) return detailPayload.issue.id;
  if (detailIssueId) return detailIssueId;
  const match = location.pathname.match(/^\/issues\/(\d+)/);
  return match ? Number.parseInt(match[1], 10) : null;
}

function setNavActive(route) {
  const activeRoute = route || (location.pathname.startsWith("/review") ? "review" : "issues");
  const activeMain = ["cluster", "consulting", "factory", "docs", "research"].includes(activeRoute) ? activeRoute : "taskstream";
  mainNavLinks.forEach((link) => {
    link.classList.toggle("active", link.dataset.mainRoute === activeMain);
  });
  primaryNavLinks.forEach((link) => {
    link.classList.toggle("active", link.dataset.navRoute === activeRoute);
  });
  if (taskstreamNav) taskstreamNav.classList.toggle("hidden", activeMain !== "taskstream");
  document.body.classList.toggle("docsMode", activeMain === "docs");
}

function refreshSavedQueryOptions() {
  if (!savedQuerySelect) return;
  const options = ['<option value="">Custom filters</option>'];
  for (const query of savedQueries) {
    options.push(`<option value="${escapeHtml(query.id)}">${escapeHtml(query.name)}</option>`);
  }
  savedQuerySelect.innerHTML = options.join("");
  if (activeQueryId) savedQuerySelect.value = activeQueryId;
}

function queryFilterPayload() {
  return {
    status: activeFilter,
    tracker: activeTracker,
    package: activePackage,
    role: activeRole,
    agent: activeAgent,
    search: searchTerm,
    updatedFrom: activeUpdatedFrom,
    updatedTo: activeUpdatedTo,
    evidence: activeEvidence,
    risk: activeRisk,
    perPage,
  };
}

async function loadSavedQueries() {
  try {
    const payload = await apiGetJson(`${API_BASE}/queries`);
    savedQueries = Array.isArray(payload.queries) ? payload.queries : [];
  } catch {
    savedQueries = [];
  }
  refreshSavedQueryOptions();
}

function queryToFilterState(rawFilters) {
  let filters = {};
  if (typeof rawFilters === "string" && rawFilters.trim()) {
    try {
      filters = JSON.parse(rawFilters);
    } catch {
      filters = {};
    }
  } else if (rawFilters && typeof rawFilters === "object") {
    filters = rawFilters;
  }
  return {
    status: String(filters.status || "open"),
    tracker: String(filters.tracker || filters.trackerFilter || ""),
    package: String(filters.package || ""),
    role: String(filters.role || ""),
    agent: String(filters.agent || ""),
    search: String(filters.search || ""),
    updatedFrom: String(filters.updatedFrom || filters.updated_from || ""),
    updatedTo: String(filters.updatedTo || filters.updated_to || ""),
    evidence: String(filters.evidence || ""),
    risk: String(filters.risk || ""),
  };
}

function applyQueryFilters(query) {
  const nextState = queryToFilterState(query?.filters || query?.query?.filters || {});
  activeQueryId = String(query?.id || query?.query?.id || "");
  applyFilterState(nextState);
  if (query?.name && queryNameInput) queryNameInput.value = query.name;
  page = 1;
  persistFilterState();
  setLocationFromState();
  void withSpinner(loadIssues());
}

async function saveCurrentQuery() {
  if (!queryNameInput || !savedQuerySelect) return;
  const name = queryNameInput.value.trim() || "Custom filter";
  const payload = {
    name,
    filters: JSON.stringify(queryFilterPayload()),
    is_default: false,
  };
  const response = await fetch(`${API_BASE}/queries`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const result = await response.json();
  const query = result.query || {};
  activeQueryId = String(query.id || "");
  persistFilterState();
  await loadSavedQueries();
  savedQuerySelect.value = activeQueryId;
}

function exportIssues(format) {
  const rows = filteredIssueRows();
  const issueSet = rows.map((issue) => ({
    id: issue.id,
    subject: issue.subject,
    tracker: issue.tracker,
    status: issue.status,
    priority: issue.priority,
    assignee: issue.assignee,
    agent: issue.agent,
    role: issue.role,
    package: issue.package,
    node: issue.node,
    updated_on: issue.updated_on,
    validation_report: issue.validation_report || "",
  }));
  let content = "";
  let mime = "application/json";
  let filename = `agent-work-export-${Date.now()}.json`;
  if (format === "csv") {
    const headers = Object.keys(issueSet[0] || {
      id: "",
      subject: "",
      tracker: "",
      status: "",
      priority: "",
      assignee: "",
      agent: "",
      role: "",
      package: "",
      node: "",
      updated_on: "",
      validation_report: "",
    });
    const csvEscape = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
    content = [
      headers.join(","),
      ...issueSet.map((row) => headers.map((header) => csvEscape(row[header])).join(",")),
    ].join("\n");
    mime = "text/csv";
    filename = `agent-work-export-${Date.now()}.csv`;
  } else {
    content = JSON.stringify(issueSet, null, 2);
  }
  const blob = new Blob([content], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function currentIssuePayloadFromDetail() {
  const issue = detailPayload?.issue || {};
  const customFields = detailPayload?.custom_fields || {};
  return {
    id: issue.id,
    subject: issue.subject,
    tracker: issue.tracker,
    status: issue.status,
    priority: issue.priority,
    assignee: issue.assignee,
    agent: issue.agent,
    role: issue.role,
    package: issue.package,
    node: issue.node,
    done_ratio: issue.done_ratio,
    description: issue.description,
    validation_report: issue.validation_report || customFields["Validation Report"] || "",
  };
}

async function submitIssueForm(event) {
  event.preventDefault();
  const payload = issueFormPayload();
  const issueId = issueIdInput.value ? Number.parseInt(issueIdInput.value, 10) : null;
  const response = await fetch(issueId ? `${API_BASE}/issues/${issueId}` : `${API_BASE}/issues`, {
    method: issueId ? "PATCH" : "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const result = await response.json();
  closeIssueModal();
  if (savedQuerySelect) await loadSavedQueries();
  page = 1;
  await withSpinner(loadIssues());
  const issue = result.issue || result;
  if (issue?.id) {
    await showDetail(issue.id).catch(console.error);
  }
}

async function submitStatusTransition(event) {
  event.preventDefault();
  const issueId = currentIssueIdFromDetail();
  if (!issueId) return;
  const payload = {
    status: statusSelect.value,
    done_ratio: Number.parseInt(detailDoneRatio.value, 10) || 0,
    assignee: detailAssignee.value.trim() || "local operator",
    note: detailTransitionNote.value.trim(),
  };
  const response = await fetch(`${API_BASE}/issues/${issueId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  detailTransitionNote.value = "";
  await showDetail(issueId);
  await withSpinner(loadIssues());
}

async function submitJournal(event) {
  event.preventDefault();
  const issueId = currentIssueIdFromDetail();
  if (!issueId) return;
  const response = await fetch(`${API_BASE}/issues/${issueId}/journals`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      author: journalAuthor.value.trim() || "local operator",
      notes: journalNote.value.trim(),
    }),
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  journalNote.value = "";
  await showDetail(issueId);
  await withSpinner(loadIssues());
}

async function submitEvidence(event) {
  event.preventDefault();
  const issueId = currentIssueIdFromDetail();
  if (!issueId) return;
  const type = evidenceType.value;
  const payload = {
    label: evidenceLabel.value.trim(),
    path: evidencePath.value.trim(),
    note: evidenceNote.value.trim(),
    source: "local-ui",
  };
  const endpoint = type === "validation" ? "validation_evidences" : "attachments";
  const body = type === "validation"
    ? {
        label: payload.label,
        path: payload.path,
        url: payload.path.startsWith("http") ? payload.path : "",
        note: payload.note,
        source: payload.source,
      }
    : {
        filename: payload.label || payload.path.split("/").pop() || "evidence",
        path: payload.path,
        size: "",
        evidence_type: payload.note,
      };
  const response = await fetch(`${API_BASE}/issues/${issueId}/${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  evidenceLabel.value = "";
  evidencePath.value = "";
  evidenceNote.value = "";
  await showDetail(issueId);
  await withSpinner(loadIssues());
}

function showDetailError(message) {
  detailContent.innerHTML = `<div class="detailError">${escapeHtml(message)}</div>`;
  historyList.innerHTML = `<div class="historyCard historyEmpty">${escapeHtml(message)}</div>`;
}

function reviewRelativeTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const diff = Math.max(0, Date.now() - date.getTime());
  const minutes = Math.max(1, Math.round(diff / 60000));
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  return `${hours}h ago`;
}

function selectedReviewIssueId() {
  const item = reviewItems[reviewSelectedIndex];
  return item?.issue?.id;
}

function reviewArtifactMatches(item, tab) {
  const kind = String(item.kind || "metadata");
  if (tab === "screenshot") return kind === "screenshot";
  if (tab === "logs") return kind === "logs";
  if (tab === "video") return kind === "video";
  if (tab === "output") return kind === "output";
  if (tab === "notes") return kind === "notes";
  return kind === "metadata";
}

function availableArtifactTabs() {
  const artifacts = Array.isArray(reviewDetailPayload?.artifacts) ? reviewDetailPayload.artifacts : [];
  const tabs = new Set();
  for (const artifact of artifacts) {
    for (const tab of ["screenshot", "logs", "video", "output", "metadata", "notes"]) {
      if (reviewArtifactMatches(artifact, tab)) tabs.add(tab);
    }
  }
  if (reviewDetailPayload?.queue_type === "blocker") tabs.add("notes");
  return tabs;
}

function updateArtifactTabs() {
  const tabs = availableArtifactTabs();
  if (!tabs.has(reviewActiveArtifactTab)) {
    reviewActiveArtifactTab = tabs.values().next().value || "metadata";
  }
  document.querySelectorAll("[data-artifact-tab]").forEach((button) => {
    const available = tabs.has(button.dataset.artifactTab);
    button.disabled = !available;
    button.classList.toggle("unavailable", !available);
    button.classList.toggle("active", available && button.dataset.artifactTab === reviewActiveArtifactTab);
    button.title = available ? "" : "No artifact of this type is attached";
  });
}

function chooseReviewArtifact(tab = reviewActiveArtifactTab) {
  const artifacts = Array.isArray(reviewDetailPayload?.artifacts) ? reviewDetailPayload.artifacts : [];
  return artifacts.find((item) => reviewArtifactMatches(item, tab)) || null;
}

async function artifactText(artifact) {
  if (!artifact?.url || artifact.kind === "screenshot" || artifact.kind === "video") return "";
  const response = await fetch(artifact.url, { cache: "no-store" });
  if (!response.ok) return "";
  const text = await response.text();
  return text.length > 9000 ? `${text.slice(0, 9000)}\n\n... truncated ...` : text;
}

function logHighlights(text) {
  const noisy = /^(#|[-*]\s|[0-9]+\.\s|h[23]\.|you are |issue:|project:|status:|node:|agent:|role:|package:|owned files|work instructions|acceptance|before editing|otherwise run|fail or block|builder claim|validator pass|validator claim|keep notes|close only|created:|docs\/)/i;
  const lines = String(text || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !noisy.test(line) && !line.includes("ISSUE_ID") && !line.includes("--evidence PATH") && !/validator pass|agent-work claim|agent-work update|agent-work validate/i.test(line));
  const patterns = [
    ["passed", /\b(PASS|PASSED|SUCCESS|SUCCEEDED|completed successfully|all checks passed|ok$)\b/i],
    ["failed", /\b(FAIL|FAILED|ERROR|Exception|Traceback|deadlock|blocked)\b/i],
    ["tests", /\b(test finished|pytest|playwright|validation passed|validation failed|check passed|check failed)\b/i],
    ["command", /^\$|executed:|running:|npm |python[0-9]? |pytest|playwright|curl |node /i],
  ];
  const seen = new Set();
  const items = [];
  for (const [kind, pattern] of patterns) {
    const line = lines.find((candidate) => pattern.test(candidate) && !seen.has(candidate));
    if (line) {
      seen.add(line);
      items.push({ kind, text: scrubInternalReferences(line).slice(0, 220) });
    }
  }
  if (!items.length && lines.length) {
    items.push({ kind: "summary", text: scrubInternalReferences(lines[0]).slice(0, 220) });
  }
  return items;
}

function renderLogHighlights(text) {
  const items = logHighlights(text);
  if (!items.length) {
    reviewLogHighlights.classList.add("hidden");
    reviewLogHighlights.innerHTML = "";
    return;
  }
  reviewLogHighlights.classList.remove("hidden");
  reviewLogHighlights.innerHTML = `
    <h3>Highlights</h3>
    <ul>
      ${items.map((item) => `<li class="${escapeHtml(item.kind)}"><strong>${escapeHtml(item.kind)}</strong><span>${escapeHtml(item.text)}</span></li>`).join("")}
    </ul>
  `;
}

function firstMatch(text, pattern) {
  const match = String(text || "").match(pattern);
  return match ? String(match[1] || "").trim() : "";
}

function stripTaskProtocol(text) {
  return String(text || "")
    .replace(/^h[23]\.\s+/gm, "")
    .replace(/^\s*#\s+/gm, "")
    .replace(/^\s*\*\s+/gm, "")
    .replace(/@\w[^@]+@/g, (value) => value.slice(1, -1))
    .trim();
}

function scrubInternalReferences(text) {
  return String(text || "")
    .replace(/\/home\/alice\/projects\/cento\/[^\s]+/g, "attached evidence")
    .replace(/workspace\/runs\/[^\s]+/g, "attached evidence")
    .replace(/cento-agent-[^\s.;,]+/g, "the agent session")
    .replace(/\bclaude-code\b/g, "an agent")
    .replace(/\bcodex\b/g, "an agent")
    .replace(/\s+/g, " ")
    .trim();
}

function blockerPlainIssueType(issue) {
  const subject = String(issue?.subject || "").toLowerCase();
  if (subject.includes("smoke") || subject.includes("validation")) return "validation check";
  if (subject.includes("concurrency") || subject.includes("stress")) return "stress test";
  if (String(issue?.tracker || "").toLowerCase().includes("epic")) return "project";
  return "task";
}

function blockerFriendlyKind(kind, latestNote) {
  const note = String(latestNote || "").toLowerCase();
  if (kind === "question" || note.includes("?")) return "Needs your answer";
  if (kind === "external") return "Waiting outside Taskstream";
  if (kind === "command" || note.includes("command") || note.includes("log:")) return "Needs operator action";
  return "Needs decision";
}

function blockerPresentation(payload) {
  const issue = payload?.issue || {};
  const blocker = payload?.blocker || {};
  const journals = Array.isArray(payload?.journals) ? payload.journals : [];
  const notes = journals.map((item) => String(item.notes || "").trim()).filter(Boolean);
  const latestNote = String(notes[0] || blocker.summary || "").trim();
  const allNotes = [latestNote, ...notes, String(blocker.summary || ""), String(issue.dispatch || "")].join("\n");
  const description = String(issue.description || "");
  const logPath = firstMatch(allNotes, /log:\s*([^\s]+)(?:\s|$)/i) || firstMatch(issue.dispatch, /local_prompt=([^\s]+)/i);
  const objective = firstMatch(description, /h3\.\s*objective\s*\n+([\s\S]*?)(?:\n\s*h3\.|\n\s*h2\.|$)/i);
  const node = firstMatch(description, /\*\s*Node:\s*([^\n]+)/i) || issue.node || "-";
  const role = firstMatch(description, /\*\s*Role:\s*([^\n]+)/i) || issue.role || "-";
  const agent = firstMatch(description, /\*\s*Agent:\s*([^\n]+)/i) || issue.agent || issue.assignee || "-";
  const pkg = firstMatch(description, /\*\s*Package:\s*([^\n]+)/i) || issue.package || "-";
  const kind = String(blocker.kind || "blocked");
  const issueType = blockerPlainIssueType(issue);
  const failed = /failed|error|rejected/i.test(allNotes);
  const rejected = /rejected deliverable|requested changes|not meet/i.test(allNotes);
  const external = kind === "external";
  const question = kind === "question";
  const commandAsk = kind === "command" || /run|command|terminal|log:/i.test(allNotes);
  let problem = `This ${issueType} cannot move forward yet.`;
  if (failed) problem = `This ${issueType} tried to run, but the run did not finish cleanly.`;
  if (rejected) problem = `This ${issueType} was reviewed and sent back for more work.`;
  if (question) problem = `This ${issueType} is waiting for an answer from you.`;
  if (external) problem = `This ${issueType} is waiting on something outside Taskstream.`;
  let why = "Taskstream has a blocker recorded, but the note does not explain it clearly yet.";
  if (failed) why = "The last automated run reported a failure, so Taskstream paused it instead of guessing.";
  if (rejected) why = "The review outcome was not accepted as complete, so the work needs another pass.";
  if (commandAsk) why = "The system needs a human decision: retry the work, request a command, or leave it blocked.";
  if (question) why = "An agent needs a human decision or missing context.";
  if (external) why = "The required dependency is not controlled by the agent workflow.";
  let nextStep = "Pick Requeue if you want an agent to try again. Pick Ask question if you want to write a clearer instruction first.";
  if (failed || commandAsk) nextStep = "Pick Requeue if you want me to try again. Pick Ask command only if you know a specific command that must run first.";
  if (rejected) nextStep = "Pick Requeue to send it back for another pass. Add a short note if you know what should change.";
  if (question) nextStep = "Type the answer in the note box, then pick Ask question to record it or Requeue when the answer is enough.";
  if (external) nextStep = "Resolve the outside dependency first. Then pick Requeue so the cluster can continue.";
  const details = [
    ["Issue", `#${issue.id || "-"}`],
    ["Task", issue.subject || "-"],
    ["Status", issue.status || "-"],
    ["Package", pkg],
    ["Owner", agent && role ? `${agent} (${role})` : agent || role || "-"],
  ];
  return {
    kind: blockerFriendlyKind(kind, latestNote),
    problem,
    why,
    nextStep,
    objective: stripTaskProtocol(objective || description).slice(0, 700),
    raw: stripTaskProtocol([latestNote, logPath ? `Evidence: ${logPath}` : "", `Node: ${node}`].filter(Boolean).join("\n\n") || description).slice(0, 1200),
    details,
  };
}

function readableActivityLine(item) {
  const raw = String(item?.notes || "").trim();
  if (!raw) return "";
  const note = raw.toLowerCase();
  let action = stripTaskProtocol(raw);
  if (note.includes("requested an operator command")) {
    action = "Asked for an operator action before continuing.";
  } else if (note.includes("rejected deliverable")) {
    action = "Sent back for another pass.";
  } else if (note.includes("requested changes")) {
    action = "Requested changes.";
  } else if (note.includes("failed with")) {
    action = "Agent run failed.";
  } else if (note.includes("finished with")) {
    action = "Agent run finished and is waiting for review.";
  } else if (note.includes("claimed by")) {
    action = "Work was picked up.";
  } else if (note.includes("dispatched")) {
    action = "Agent was dispatched.";
  } else {
    action = "Recorded a technical note.";
  }
  return `${shortDate(item?.created_on)}: ${action}`;
}

function renderReviewQueue() {
  reviewQueue.innerHTML = reviewItems.map((item, index) => {
    const issue = item.issue || {};
    const active = index === reviewSelectedIndex ? "active" : "";
    const recommendation = String(item.recommendation || "pending");
    const artifact = item.primary_artifact;
    const isBlocker = item.queue_type === "blocker" || String(issue.status || "").toLowerCase() === "blocked";
    const typeLabel = isBlocker ? blockerFriendlyKind(item.blocker?.kind || "blocked", item.blocker?.summary || "") : (artifact ? artifact.kind : "metadata");
    const score = isBlocker ? "BLOCKED" : `${escapeHtml(item.confidence || 0)}%`;
    return `
      <button class="reviewQueueItem ${active} ${escapeHtml(recommendation)}" data-review-index="${index}">
        <div class="reviewQueueItemTop">
          <strong>#${escapeHtml(issue.id)}</strong>
          <span class="score">${score}</span>
        </div>
        <h2>${escapeHtml(issue.subject || "Untitled review item")}</h2>
        <div class="reviewQueueMeta">
          <span>${escapeHtml(issue.tracker || "Agent Task")} · ${escapeHtml(typeLabel)}</span>
          <span>${escapeHtml(reviewRelativeTime(issue.updated_on))}</span>
        </div>
      </button>
    `;
  }).join("");
}

function setReviewCounts(payload) {
  const counts = payload.counts || {};
  reviewTotal.textContent = String(payload.total || reviewItems.length);
  reviewApproveCount.textContent = String(counts.approve || 0);
  reviewFixCount.textContent = String(counts.needs_fix || 0);
  reviewRejectCount.textContent = String(counts.reject || 0);
  reviewBlockerCount.textContent = String(counts.blocker || 0);
}

async function renderReviewArtifact() {
  updateArtifactTabs();
  if (reviewDetailPayload?.queue_type === "blocker") {
    const issue = reviewDetailPayload.issue || {};
    const presentation = blockerPresentation(reviewDetailPayload);
    const logsTitle = document.querySelector(".reviewLogs h2");
    if (logsTitle) logsTitle.textContent = "Recent activity";
    reviewArtifactTitle.textContent = "Blocker resolution";
    reviewConfidence.textContent = presentation.kind.toUpperCase();
    reviewArtifact.innerHTML = `
      <article class="blockerArtifact">
        <span>${escapeHtml(presentation.kind)}</span>
        <h2>${escapeHtml(issue.subject || "Blocked issue")}</h2>
        <div class="blockerBriefGrid">
          <section>
            <h3>What happened</h3>
            <p>${escapeHtml(presentation.problem)}</p>
          </section>
          <section>
            <h3>Why it is blocked</h3>
            <p>${escapeHtml(presentation.why)}</p>
          </section>
          <section class="blockerNextStep">
            <h3>Suggested next step</h3>
            <p>${escapeHtml(presentation.nextStep)}</p>
          </section>
        </div>
        <dl class="blockerDetails">
          ${presentation.details.map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("")}
        </dl>
        <details class="blockerRaw">
          <summary>Show raw blocker details</summary>
          <pre>${escapeHtml(presentation.objective || presentation.raw || "No additional details recorded.")}</pre>
        </details>
      </article>
    `;
    reviewLogText.textContent = (reviewDetailPayload.journals || [])
      .slice(0, 5)
      .map(readableActivityLine)
      .filter(Boolean)
      .join("\n") || "No recent activity recorded.";
    renderLogHighlights(reviewLogText.textContent);
    return;
  }
  const logsTitle = document.querySelector(".reviewLogs h2");
  if (logsTitle) logsTitle.textContent = "Logs";
  const artifact = chooseReviewArtifact();
  reviewArtifactTitle.textContent = artifact ? artifact.label : "No deliverable evidence";
  if (!artifact) {
    reviewArtifact.innerHTML = `<div class="reviewEmpty">No ${escapeHtml(reviewActiveArtifactTab)} artifact is attached to this review item.</div>`;
    reviewLogText.textContent = "No log artifact found for this item.";
    renderLogHighlights("");
    return;
  }
  if (artifact.kind === "screenshot") {
    reviewArtifact.innerHTML = `<img src="${escapeHtml(artifact.url)}" alt="${escapeHtml(artifact.label)}" />`;
  } else if (artifact.kind === "video") {
    reviewArtifact.innerHTML = `<video src="${escapeHtml(artifact.url)}" controls></video>`;
  } else {
    const text = await artifactText(artifact);
    reviewArtifact.innerHTML = `<pre>${escapeHtml(text || artifact.note || artifact.path || "No preview available.")}</pre>`;
  }

  const logs = chooseReviewArtifact("logs");
  if (logs) {
    reviewLogText.textContent = await artifactText(logs) || logs.path || "Log artifact is not readable.";
  } else {
    reviewLogText.textContent = "No log artifact found for this item.";
  }
  renderLogHighlights(logs ? reviewLogText.textContent : "");
}

function renderReviewContext(payload) {
  const issue = payload.issue || {};
  const artifacts = Array.isArray(payload.artifacts) ? payload.artifacts : [];
  const rows = [
    ["Created by", issue.assignee || issue.agent || "alice"],
    ["Updated", shortDate(issue.updated_on) || "-"],
    ["Related issue", `#${issue.id || "-"}`],
    ["Status", issue.status || "-"],
    ["Package", issue.package || "-"],
    ["Validation", validationLabel(issue)],
    ["Escalation", validationState(issue).escalation_state || "unknown"],
    ["Artifacts", String(artifacts.length)],
  ];
  reviewContext.innerHTML = rows.map(([label, value]) => `
    <div class="reviewContextRow"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>
  `).join("");
}

function renderBlockerResolution(payload) {
  const isBlocker = payload?.queue_type === "blocker";
  blockerResolution.classList.toggle("hidden", !isBlocker);
  reviewApprove.classList.toggle("hidden", isBlocker);
  reviewReject.classList.toggle("hidden", isBlocker);
  reviewNeedsFix.classList.toggle("hidden", isBlocker);
  if (!isBlocker) return;
  const presentation = blockerPresentation(payload);
  blockerKind.textContent = presentation.kind.toUpperCase();
  blockerSummary.textContent = presentation.nextStep;
  blockerNote.value = "";
}

async function loadReviewDetail(issueId) {
  if (!issueId) {
    reviewDetailPayload = null;
    reviewAgent.textContent = "-";
    reviewTask.textContent = "-";
    reviewIssue.textContent = "-";
    reviewPosition.textContent = "0/0";
    reviewArtifact.innerHTML = `<div class="reviewEmpty">No review items.</div>`;
    reviewLogText.textContent = "No logs selected.";
    renderLogHighlights("");
    reviewContext.innerHTML = "";
    renderBlockerResolution(null);
    return;
  }
  reviewDetailPayload = await apiGetJson(`${API_BASE}/review/${issueId}`);
  const issue = reviewDetailPayload.issue || {};
  reviewAgent.textContent = issue.agent || issue.assignee || "alice";
  reviewTask.textContent = issue.subject || "-";
  reviewIssue.textContent = `#${issue.id}`;
  reviewPosition.textContent = `${reviewSelectedIndex + 1}/${reviewItems.length}`;
  reviewConfidence.textContent = `${reviewDetailPayload.confidence || 0}%`;
  renderReviewContext(reviewDetailPayload);
  renderBlockerResolution(reviewDetailPayload);
  await renderReviewArtifact();
}

async function loadReview() {
  const payload = await apiGetJson(`${API_BASE}/review`);
  reviewItems = Array.isArray(payload.items) ? payload.items : [];
  if (reviewSelectedIndex >= reviewItems.length) reviewSelectedIndex = Math.max(0, reviewItems.length - 1);
  setReviewCounts(payload);
  renderReviewQueue();
  await loadReviewDetail(selectedReviewIssueId());
}

function showReview() {
  setNavActive("review");
  document.body.classList.remove("reviewMode");
  listView.classList.add("hidden");
  detailView.classList.add("hidden");
  clusterView.classList.add("hidden");
  consultingView.classList.add("hidden");
  factoryView.classList.add("hidden");
  docsView.classList.add("hidden");
  reviewView.classList.remove("hidden");
  history.replaceState(null, "", "/review");
  void loadReview().catch((error) => {
    reviewArtifact.innerHTML = `<div class="reviewEmpty">${escapeHtml(error.message)}</div>`;
  });
}

function moveReviewSelection(delta) {
  if (!reviewItems.length) return;
  reviewSelectedIndex = (reviewSelectedIndex + delta + reviewItems.length) % reviewItems.length;
  renderReviewQueue();
  void loadReviewDetail(selectedReviewIssueId()).catch(console.error);
}

async function decideReview(decision) {
  const issueId = selectedReviewIssueId();
  if (!issueId) return;
  const note = ["question", "command", "unblock"].includes(decision)
    ? blockerNote.value.trim()
    : "";
  await fetch(`${API_BASE}/review/${issueId}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision, note }),
  }).then((response) => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  });
  if (reviewAutoAdvance.checked) {
    reviewItems.splice(reviewSelectedIndex, 1);
    if (reviewSelectedIndex >= reviewItems.length) reviewSelectedIndex = Math.max(0, reviewItems.length - 1);
    renderReviewQueue();
    await loadReviewDetail(selectedReviewIssueId());
  } else {
    await loadReview();
  }
}

function withSpinner(promise) {
  setListLoading(true);
  return promise.finally(() => setListLoading(false));
}

async function apiGetJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

async function showDetail(issueId) {
  setNavActive("issues");
  detailIssueId = issueId;
  detailContent.innerHTML = `<div class="detailLoading">Loading issue…</div>`;
  historyList.innerHTML = `<div class="historyCard historyEmpty">Loading history…</div>`;
  document.body.classList.remove("reviewMode");
  listView.classList.add("hidden");
  reviewView.classList.add("hidden");
  clusterView.classList.add("hidden");
  consultingView.classList.add("hidden");
  factoryView.classList.add("hidden");
  docsView.classList.add("hidden");
  detailView.classList.remove("hidden");
  history.replaceState(null, "", `/issues/${issueId}`);
  try {
    const payload = await apiGetJson(`${API_BASE}/issues/${issueId}`);
    renderDetail(payload);
  } catch (error) {
    showDetailError(error.message);
  }
}

function showList() {
  setNavActive("issues");
  document.body.classList.remove("reviewMode");
  reviewView.classList.add("hidden");
  detailView.classList.add("hidden");
  clusterView.classList.add("hidden");
  consultingView.classList.add("hidden");
  factoryView.classList.add("hidden");
  docsView.classList.add("hidden");
  listView.classList.remove("hidden");
  setLocationFromState();
  void withSpinner(loadIssues());
}

function showCentoSection(route) {
  setNavActive(route);
  const docsLike = route === "docs" || route === "research";
  document.body.classList.remove("reviewMode");
  reviewView.classList.add("hidden");
  detailView.classList.add("hidden");
  listView.classList.add("hidden");
  clusterView.classList.toggle("hidden", route !== "cluster");
  consultingView.classList.toggle("hidden", route !== "consulting");
  factoryView.classList.toggle("hidden", route !== "factory");
  docsView.classList.toggle("hidden", !docsLike);
  if (route === "factory") {
    history.replaceState(null, "", "/factory");
    void loadFactory();
    return;
  }
  if (route === "research") {
    history.replaceState(null, "", "/research-center#research-implementation");
    document.querySelector("#research-implementation")?.scrollIntoView({ block: "start" });
    return;
  }
  const hash = route === "docs" ? location.hash : "";
  history.replaceState(null, "", `/${route}${hash}`);
}

async function loadIssues() {
  setLocationFromState();
  try {
    const payload = await apiGetJson(listQueryUrl());
    allIssues = Array.isArray(payload.issues) ? payload.issues : [];
    totalIssues = allIssues.length;
    setFilterCounts(payload.counts || {}, allIssues);
    renderRows(currentPageIssues());
    refreshSavedQueryOptions();
  } catch (error) {
    issueRows.innerHTML = `<tr><td colspan="8">${escapeHtml(error.message)}</td></tr>`;
    totalIssues = 0;
    setFilterCounts({}, []);
    renderRows([]);
  }
}

async function loadAgents() {
  if (!agentSummary || !agentCards) return;
  try {
    const payload = await apiGetJson(`${API_BASE}/runs`);
    renderAgents(payload);
  } catch (error) {
    agentSummary.textContent = `agent pool visibility failed: ${error.message}`;
    agentCards.innerHTML = "";
  }
}

function renderFactory(payload) {
  if (!factoryRunList) return;
  const summary = payload.summary || {};
  const runs = Array.isArray(payload.runs) ? payload.runs : [];
  factoryRunCount.textContent = summary.total ?? runs.length;
  factoryDeliveredCount.textContent = summary.delivered ?? runs.filter((run) => run.decision === "delivered").length;
  factoryQueuedCount.textContent = summary.queued ?? 0;
  factoryAiCalls.textContent = summary.ai_calls_used ?? 0;
  if (!runs.length) {
    factoryRunList.innerHTML = `<div class="factoryEmpty">No Factory runs yet.</div>`;
    return;
  }
  factoryRunList.innerHTML = runs
    .map((run) => {
      const queue = run.queue || {};
      const decision = String(run.decision || "incomplete");
      const statusClassName = decision === "delivered" ? "good" : decision === "approve" ? "good" : "warn";
      const hubLink = run.start_hub
        ? `<a href="${escapeHtml(`/api/artifacts?path=${encodeURIComponent(run.start_hub)}`)}" target="_blank" rel="noreferrer">hub</a>`
        : `<span>hub missing</span>`;
      const mapLink = run.implementation_map
        ? `<a href="${escapeHtml(`/api/artifacts?path=${encodeURIComponent(run.implementation_map)}`)}" target="_blank" rel="noreferrer">map</a>`
        : `<span>map missing</span>`;
      return `
        <article class="factoryRunCard">
          <div class="factoryRunTop">
            <div>
              <strong>${escapeHtml(run.package || run.run_id)}</strong>
              <small>${escapeHtml(run.goal || run.run_dir)}</small>
            </div>
            <span class="factoryDecision ${statusClassName}">${escapeHtml(decision.replaceAll("_", " "))}</span>
          </div>
          <div class="factoryRunMeta">
            <span>${escapeHtml(String(run.tasks || 0))} tasks</span>
            <span>${escapeHtml(String(queue.queued || 0))} queued</span>
            <span>${escapeHtml(String(queue.waiting || 0))} waiting</span>
            <span>${escapeHtml(String(run.dispatch_selected || 0))} dispatch planned</span>
            <span>${escapeHtml(String(run.ai_calls_used || 0))} AI calls</span>
            <span>${escapeHtml(String(Math.round(Number(run.total_duration_ms || 0))))} ms</span>
          </div>
          <div class="factoryRunLinks">
            <code>${escapeHtml(run.run_dir)}</code>
            ${hubLink}
            ${mapLink}
          </div>
        </article>
      `;
    })
    .join("");
}

async function loadFactory() {
  if (!factoryRunList) return;
  factoryRunList.innerHTML = `<div class="factoryEmpty">Loading Factory runs...</div>`;
  try {
    const payload = await apiGetJson(`${API_BASE}/factory`);
    renderFactory(payload);
  } catch (error) {
    factoryRunList.innerHTML = `<div class="factoryEmpty">${escapeHtml(error.message)}</div>`;
  }
}

async function loadQueriesIntoSelect() {
  if (!savedQuerySelect) {
    savedQueries = [];
    activeQueryId = "";
    return;
  }
  await loadSavedQueries();
  const persistedQueryId = (() => {
    try {
      return localStorage.getItem(LOCAL_STORAGE_QUERY_KEY) || "";
    } catch {
      return "";
    }
  })();
  if (persistedQueryId && !activeQueryId) {
    activeQueryId = persistedQueryId;
    savedQuerySelect.value = activeQueryId;
  }
  const selected = savedQueries.find((query) => String(query.id) === String(activeQueryId));
  if (selected && (location.search.includes("query=") || !location.search)) {
    const nextState = queryToFilterState(selected.filters);
    applyFilterState(nextState);
    if (queryNameInput) queryNameInput.value = selected.name || queryNameInput.value;
    persistFilterState();
    setLocationFromState();
  }
  refreshSavedQueryOptions();
}

let searchDelay = null;

fillStatusOptions(issueStatusInput);
fillStatusOptions(statusSelect);

issueRows.addEventListener("click", (event) => {
  const link = event.target.closest("[data-issue]");
  if (!link) return;
  event.preventDefault();
  void showDetail(link.dataset.issue).catch(console.error);
});

reviewQueue.addEventListener("click", (event) => {
  const item = event.target.closest("[data-review-index]");
  if (!item) return;
  reviewSelectedIndex = Number.parseInt(item.dataset.reviewIndex, 10) || 0;
  renderReviewQueue();
  void loadReviewDetail(selectedReviewIssueId()).catch(console.error);
});

document.querySelectorAll("[data-artifact-tab]").forEach((button) => {
  button.addEventListener("click", () => {
    if (button.disabled) return;
    reviewActiveArtifactTab = button.dataset.artifactTab || "screenshot";
    void renderReviewArtifact().catch(console.error);
  });
});

reviewApprove.addEventListener("click", () => void decideReview("approve").catch(console.error));
reviewReject.addEventListener("click", () => void decideReview("reject").catch(console.error));
reviewNeedsFix.addEventListener("click", () => void decideReview("needs_fix").catch(console.error));
blockerQuestion.addEventListener("click", () => void decideReview("question").catch(console.error));
blockerCommand.addEventListener("click", () => void decideReview("command").catch(console.error));
blockerRequeue.addEventListener("click", () => void decideReview("unblock").catch(console.error));

document.querySelectorAll("[data-modal-close]").forEach((button) => {
  button.addEventListener("click", closeIssueModal);
});

newIssueButton.addEventListener("click", () => openIssueModal());
headerNewIssueButton.addEventListener("click", () => openIssueModal());
detailEditButton.addEventListener("click", () => {
  if (detailPayload?.issue) openIssueModal(currentIssuePayloadFromDetail());
});

issueForm.addEventListener("submit", (event) => void submitIssueForm(event).catch((error) => showDetailError(error.message)));
statusForm.addEventListener("submit", (event) => void submitStatusTransition(event).catch((error) => showDetailError(error.message)));
journalForm.addEventListener("submit", (event) => void submitJournal(event).catch((error) => showDetailError(error.message)));
evidenceForm.addEventListener("submit", (event) => void submitEvidence(event).catch((error) => showDetailError(error.message)));

saveQueryButton?.addEventListener("click", () => {
  void saveCurrentQuery().then(() => loadSavedQueries()).catch((error) => showDetailError(error.message));
});

exportJsonButton?.addEventListener("click", () => exportIssues("json"));
exportCsvButton?.addEventListener("click", () => exportIssues("csv"));

savedQuerySelect?.addEventListener("change", () => {
  const selected = savedQueries.find((query) => String(query.id) === savedQuerySelect.value);
  if (!selected) {
    activeQueryId = "";
    persistFilterState();
    return;
  }
  applyQueryFilters(selected);
});

clearFiltersButton.addEventListener("click", () => {
  activeQueryId = "";
  applyFilterState({
    status: "open",
    tracker: "all",
    package: "",
    role: "",
    agent: "",
    search: "",
    updatedFrom: "",
    updatedTo: "",
    evidence: "",
    risk: "",
  });
  if (queryNameInput) queryNameInput.value = "";
  if (savedQuerySelect) savedQuerySelect.value = "";
  page = 1;
  persistFilterState();
  setLocationFromState();
  void withSpinner(loadIssues());
});

for (const control of [statusFilter, trackerFilter, packageFilter, roleFilter, agentFilter, updatedFromFilter, updatedToFilter, evidenceFilter, riskFilter]) {
  const refresh = () => {
    applyFilterState(getFilterState());
    page = 1;
    persistFilterState();
    setLocationFromState();
    void withSpinner(loadIssues());
  };
  control.addEventListener("input", refresh);
  control.addEventListener("change", refresh);
}

document.addEventListener("keydown", (event) => {
  if (!issueModal.classList.contains("hidden") && event.key === "Escape") {
    closeIssueModal();
  }
});

document.addEventListener("keydown", (event) => {
  if (reviewView.classList.contains("hidden")) return;
  if (event.target && ["INPUT", "TEXTAREA", "SELECT"].includes(event.target.tagName)) return;
  const key = event.key.toLowerCase();
  if (key === "j") {
    event.preventDefault();
    moveReviewSelection(1);
  } else if (key === "k") {
    event.preventDefault();
    moveReviewSelection(-1);
  } else if (key === "a") {
    event.preventDefault();
    void decideReview("approve").catch(console.error);
  } else if (key === "r") {
    event.preventDefault();
    void decideReview("reject").catch(console.error);
  } else if (key === "f") {
    event.preventDefault();
    void decideReview("needs_fix").catch(console.error);
  } else if (key === "d") {
    event.preventDefault();
    const issueId = selectedReviewIssueId();
    if (issueId) void showDetail(issueId).catch(console.error);
  }
});

prevPageButton.addEventListener("click", () => {
  if (page <= 1) return;
  page -= 1;
  persistFilterState();
  setLocationFromState();
  void withSpinner(loadIssues());
});

nextPageButton.addEventListener("click", () => {
  const pages = Math.max(1, Math.ceil(totalIssues / perPage));
  if (page >= pages) return;
  page += 1;
  persistFilterState();
  setLocationFromState();
  void withSpinner(loadIssues());
});

for (const button of perPageButtons) {
  button.addEventListener("click", () => {
    const nextPerPage = Number.parseInt(button.textContent, 10);
    if (!Number.isInteger(nextPerPage) || nextPerPage === perPage) return;
    perPage = nextPerPage;
    page = 1;
    setPerPageButtons();
    persistFilterState();
    setLocationFromState();
    void withSpinner(loadIssues());
  });
}

for (const link of countLinks) {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    const nextTracker = link.dataset.filter || "all";
    page = 1;
    applyFilterState({ ...getFilterState(), tracker: nextTracker });
    persistFilterState();
    setLocationFromState();
    void withSpinner(loadIssues());
  });
}

searchInput.addEventListener("input", () => {
  searchTerm = searchInput.value.trim();
  page = 1;
  window.clearTimeout(searchDelay);
  searchDelay = window.setTimeout(() => {
    persistFilterState();
    setLocationFromState();
    void withSpinner(loadIssues());
  }, 220);
});

backButton.addEventListener("click", showList);

window.addEventListener("popstate", () => {
  syncStateFromLocation();
  const match = location.pathname.match(/^\/issues\/(\d+)/);
  if (location.pathname === "/review") {
    showReview();
  } else if (location.pathname === "/cluster") {
    showCentoSection("cluster");
  } else if (location.pathname === "/consulting") {
    showCentoSection("consulting");
  } else if (location.pathname === "/factory") {
    showCentoSection("factory");
  } else if (location.pathname === "/research-center") {
    showCentoSection("research");
  } else if (location.pathname === "/docs") {
    showCentoSection("docs");
  } else if (match) {
    void showDetail(match[1]).catch(console.error);
  } else {
    void withSpinner(loadIssues());
  }
});

async function boot() {
  syncStateFromLocation();
  setNavActive();
  await loadQueriesIntoSelect();
  if (agentSummary && agentCards) {
    await loadAgents();
    window.setInterval(loadAgents, 30000);
  }
  if (location.pathname === "/review") {
    showReview();
    return;
  }
  if (location.pathname === "/cluster") {
    showCentoSection("cluster");
    return;
  }
  if (location.pathname === "/consulting") {
    showCentoSection("consulting");
    return;
  }
  if (location.pathname === "/factory") {
    showCentoSection("factory");
    return;
  }
  if (location.pathname === "/research-center") {
    showCentoSection("research");
    return;
  }
  if (location.pathname === "/docs") {
    showCentoSection("docs");
    return;
  }
  const issueMatch = location.pathname.match(/^\/issues\/(\d+)/);
  if (issueMatch) {
    await showDetail(issueMatch[1]).catch((error) => {
      issueRows.innerHTML = `<tr><td colspan="8">${escapeHtml(error.message)}</td></tr>`;
      showList();
    });
    return;
  }
  await withSpinner(loadIssues());
}

void boot();
