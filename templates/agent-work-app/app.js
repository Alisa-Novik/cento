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
const docsHashLinks = document.querySelectorAll(".docsSidebar nav a[href^='#'], .docsToc a[href^='#']");
const agentSummary = document.querySelector("#agentSummary");
const agentCards = document.querySelector("#agentCards");
const taskstreamNav = document.querySelector(".taskstreamNav");
const homeView = document.querySelector("#homeView");
const softwareDeliveryHubView = document.querySelector("#softwareDeliveryHubView");
const devPipelineStudioView = document.querySelector("#devPipelineStudioView, .devPipelineStudioView");
const sdHubRailLinks = document.querySelectorAll("[data-sd-hub-route]");
const pipelineProjectSelect = document.querySelector("#pipelineProjectSelect");
const pipelineTemplateSelect = document.querySelector("#pipelineTemplateSelect");
const pipelineSurfaceSelect = document.querySelector("#pipelineSurfaceSelect");
const pipelineTemplateLibrary = document.querySelector(".pipelineTemplateLibrary");
let pipelineTemplateCards = document.querySelectorAll("[data-template-card]");
const pipelineManifestCode = document.querySelector("#pipelineManifestCode");
const pipelineManifestEditor = document.querySelector("#pipelineManifestEditor");
const pipelineManifestStatus = document.querySelector("#pipelineManifestStatus");
const pipelineFormatManifestButton = document.querySelector("#pipelineFormatManifestButton");
const pipelineNewTemplateButton = document.querySelector("#pipelineNewTemplateButton");
const pipelineDuplicateButton = document.querySelector("#pipelineDuplicateButton");
const pipelineSaveDraftButton = document.querySelector("#pipelineSaveDraftButton");
const pipelineSaveStatus = document.querySelector("#pipelineSaveStatus");
const pipelineProjectLabelInput = document.querySelector("#pipelineProjectLabelInput");
const pipelineTemplateLabelInput = document.querySelector("#pipelineTemplateLabelInput");
const pipelineTemplateDetailInput = document.querySelector("#pipelineTemplateDetailInput");
const pipelineExecutionModelSelect = document.querySelector("#pipelineExecutionModelSelect");
const pipelineValidationTierInput = document.querySelector("#pipelineValidationTierInput");
const pipelineRiskSelect = document.querySelector("#pipelineRiskSelect");
const pipelineBudgetCapInput = document.querySelector("#pipelineBudgetCapInput");
const pipelineReadPathsInput = document.querySelector("#pipelineReadPathsInput");
const pipelineRequiredInputsEditor = document.querySelector("#pipelineRequiredInputsEditor");
const pipelineAddInputButton = document.querySelector("#pipelineAddInputButton");
const pipelineInspectorBadge = document.querySelector("#pipelineInspectorBadge");
const pipelineInspectorState = document.querySelector("#pipelineInspectorState");
const pipelineInspectorNav = document.querySelector("#pipelineInspectorNav");
const pipelineInputInspector = document.querySelector("#pipelineInputInspector");
const pipelineInputTitleInput = document.querySelector("#pipelineInputTitleInput");
const pipelineInputTypeSelect = document.querySelector("#pipelineInputTypeSelect");
const pipelineInputDetailInput = document.querySelector("#pipelineInputDetailInput");
const pipelineInputStatusSelect = document.querySelector("#pipelineInputStatusSelect");
const pipelineInputRequiredCheckbox = document.querySelector("#pipelineInputRequiredCheckbox");
const pipelineInputFormatInput = document.querySelector("#pipelineInputFormatInput");
const pipelineInputImageRefsInput = document.querySelector("#pipelineInputImageRefsInput");
const pipelineInputImageNotesInput = document.querySelector("#pipelineInputImageNotesInput");
const pipelineInputQuestionsInput = document.querySelector("#pipelineInputQuestionsInput");
const pipelineInputPathsInput = document.querySelector("#pipelineInputPathsInput");
const pipelineInputPathPolicyInput = document.querySelector("#pipelineInputPathPolicyInput");
const pipelineInputArtifactsInput = document.querySelector("#pipelineInputArtifactsInput");
const pipelineInputEvidencePolicyInput = document.querySelector("#pipelineInputEvidencePolicyInput");
const pipelineInputManifestPath = document.querySelector("#pipelineInputManifestPath");
const pipelineInputSaveButton = document.querySelector("#pipelineInputSaveButton");
const pipelineInputInspectorStatus = document.querySelector("#pipelineInputInspectorStatus");
const pipelineIntegrationInspector = document.querySelector("#pipelineIntegrationInspector");
const pipelineIntegrationTitleInput = document.querySelector("#pipelineIntegrationTitleInput");
const pipelineIntegrationStatusSelect = document.querySelector("#pipelineIntegrationStatusSelect");
const pipelineIntegrationModeSelect = document.querySelector("#pipelineIntegrationModeSelect");
const pipelineIntegrationApplyInput = document.querySelector("#pipelineIntegrationApplyInput");
const pipelineIntegrationConflictInput = document.querySelector("#pipelineIntegrationConflictInput");
const pipelineIntegrationDependenciesInput = document.querySelector("#pipelineIntegrationDependenciesInput");
const pipelineIntegrationArtifactsInput = document.querySelector("#pipelineIntegrationArtifactsInput");
const pipelineIntegrationGatesInput = document.querySelector("#pipelineIntegrationGatesInput");
const pipelineIntegrationRollbackInput = document.querySelector("#pipelineIntegrationRollbackInput");
const pipelineIntegrationSaveButton = document.querySelector("#pipelineIntegrationSaveButton");
const pipelineIntegrationInspectorStatus = document.querySelector("#pipelineIntegrationInspectorStatus");
const pipelineIntegrationConfigPath = document.querySelector("#pipelineIntegrationConfigPath");
const pipelineIntegrationReceiptPath = document.querySelector("#pipelineIntegrationReceiptPath");
const pipelineValidationInspector = document.querySelector("#pipelineValidationInspector");
const pipelineValidationTitleInput = document.querySelector("#pipelineValidationTitleInput");
const pipelineValidationStatusSelect = document.querySelector("#pipelineValidationStatusSelect");
const pipelineValidationTierSelect = document.querySelector("#pipelineValidationTierSelect");
const pipelineValidationModeSelect = document.querySelector("#pipelineValidationModeSelect");
const pipelineValidationSummaryInput = document.querySelector("#pipelineValidationSummaryInput");
const pipelineValidationCommandsInput = document.querySelector("#pipelineValidationCommandsInput");
const pipelineValidationEvidenceInput = document.querySelector("#pipelineValidationEvidenceInput");
const pipelineValidationGatesInput = document.querySelector("#pipelineValidationGatesInput");
const pipelineValidationSchemaInput = document.querySelector("#pipelineValidationSchemaInput");
const pipelineValidationBlockingCheckbox = document.querySelector("#pipelineValidationBlockingCheckbox");
const pipelineValidationSaveButton = document.querySelector("#pipelineValidationSaveButton");
const pipelineValidationInspectorStatus = document.querySelector("#pipelineValidationInspectorStatus");
const pipelineValidationConfigPath = document.querySelector("#pipelineValidationConfigPath");
const pipelineValidationReceiptPath = document.querySelector("#pipelineValidationReceiptPath");
const pipelineValidationUseIntegrationButton = document.querySelector("#pipelineValidationUseIntegrationButton");
const pipelineValidationIntegrationContext = document.querySelector("#pipelineValidationIntegrationContext");
const pipelineValidationCommandRows = document.querySelector("#pipelineValidationCommandRows");
const pipelineValidationEvidenceRows = document.querySelector("#pipelineValidationEvidenceRows");
const pipelineValidationGateRows = document.querySelector("#pipelineValidationGateRows");
const pipelineValidationSchemaRows = document.querySelector("#pipelineValidationSchemaRows");
const pipelineValidationAddCommandButton = document.querySelector("#pipelineValidationAddCommandButton");
const pipelineValidationAddEvidenceButton = document.querySelector("#pipelineValidationAddEvidenceButton");
const pipelineValidationAddGateButton = document.querySelector("#pipelineValidationAddGateButton");
const pipelineValidationAddSchemaButton = document.querySelector("#pipelineValidationAddSchemaButton");
const pipelineWorkerInspectorActions = document.querySelector("#pipelineWorkerInspectorActions");
const pipelineContractSummary = document.querySelector("#pipelineContractSummary");
const pipelineContractPanel = document.querySelector("#pipelineContractPanel");
const pipelineArtifactPanel = document.querySelector("#pipelineArtifactPanel");
const pipelineLogsPanel = document.querySelector("#pipelineLogsPanel");
const pipelineCostPanel = document.querySelector("#pipelineCostPanel");
let currentInspectorTab = "manifest";
const clusterView = document.querySelector("#clusterView");
const consultingView = document.querySelector("#consultingView");
const factoryView = document.querySelector("#factoryView");
const docsView = document.querySelector("#docsView");
const researchView = document.querySelector("#researchView");
const codebaseIntelligenceView = document.querySelector("#codebaseIntelligenceView");
const researchRailLinks = document.querySelectorAll("[data-research-route]");
const ciGraphMount = document.querySelector("#ciGraphMount");
const ciInspectorMount = document.querySelector("#ciInspectorMount");
const ciAskMount = document.querySelector("#ciAskMount");
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
let codebaseIntelligenceInitialized = false;
let codebaseIntelligencePayload = null;

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
  history.replaceState(null, "", `${location.pathname.startsWith("/issues/") ? "/issues" : location.pathname}${suffix}`);
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

let pipelineStudioProjects = {
  "generic-easy-medium-task": {
    key: "generic-easy-medium-task",
    name: "Generic Easy-Medium Task",
    surface: "Cento code task",
    surfaceValue: "generic-task",
    ownedRoot: "workspace/runs/generic-task/outputs",
    readPaths: ["AGENTS.md", "README.md", "scripts/**", "templates/agent-work-app/**", "tests/**"]
  },
  "kanji-a-day": {
    key: "kanji-a-day",
    name: "Kanji a Day",
    surface: "Docs app page",
    surfaceValue: "docs-app-page",
    ownedRoot: "docs/apps/kanji-a-day/sections",
    readPaths: ["docs/templates/**", "docs/apps/kanji-a-day/page.config.json"]
  },
  "cento-console-docs": {
    key: "cento-console-docs",
    name: "Cento Console Docs",
    surface: "Console documentation page",
    surfaceValue: "console-doc-page",
    ownedRoot: "docs/console/sections",
    readPaths: ["docs/templates/**", "templates/agent-work-app/index.html"]
  },
  "consulting-crm": {
    key: "consulting-crm",
    name: "Consulting CRM",
    surface: "CRM app page",
    surfaceValue: "crm-page",
    ownedRoot: "templates/crm/pages",
    readPaths: ["templates/crm/**", "workspace/runs/crm-app/latest.json"]
  }
};

let pipelineStudioTemplates = {
  "generic-task": {
    id: "generic-task",
    label: "Generic easy-medium task",
    detail: "Standard Cento task template",
    slug: "generic-task",
    workerType: "generic_task_worker",
    validationTier: "smoke-plus",
    risk: "medium",
    tasks: "9 / 9",
    budget: "$1.42",
    budgetDetail: "of $3.00 budget",
    selectedIndex: 0,
    workers: [
      { id: "scope", title: "Scope & Acceptance Worker", file: "scope.json", description: "Convert request into acceptance criteria and owned paths" },
      { id: "context", title: "Context Discovery Worker", file: "context.json", description: "Inspect existing code, docs, tests, and conventions" },
      { id: "plan", title: "Change Plan Worker", file: "plan.json", description: "Create implementation and validation plan" },
      { id: "implementation", title: "Implementation Worker", file: "implementation.json", description: "Make the scoped change" },
      { id: "validation", title: "Focused Validation Worker", file: "validation.json", description: "Run checks, smoke tests, and focused tests" },
      { id: "handoff", title: "Handoff Evidence Worker", file: "handoff.json", description: "Prepare screenshots and final notes" }
    ]
  },
  "doc-page": {
    id: "doc-page",
    label: "Doc page creation",
    detail: "Reusable web docs template",
    slug: "doc-page",
    workerType: "doc_page_worker",
    validationTier: "smoke",
    risk: "low",
    tasks: "8 / 8",
    budget: "$2.42",
    budgetDetail: "of $5.00 budget",
    selectedIndex: 0,
    workers: [
      { id: "hero", title: "Hero Section Worker", file: "hero.json", description: "Generate hero section" },
      { id: "sections", title: "Body Sections Worker", file: "sections.json", description: "Generate body section structure" },
      { id: "metadata", title: "Metadata Worker", file: "metadata.json", description: "Generate metadata and navigation" },
      { id: "release", title: "Release Notes Worker", file: "release.json", description: "Generate release notes" },
      { id: "operations", title: "Operations Worker", file: "operations.json", description: "Generate operational details" },
      { id: "links", title: "Links Worker", file: "links.json", description: "Generate links and references" }
    ]
  },
  "dashboard-module": {
    id: "dashboard-module",
    label: "Dashboard module",
    detail: "Operational console template",
    slug: "dashboard-module",
    workerType: "dashboard_module_worker",
    validationTier: "screenshot",
    risk: "medium",
    tasks: "10 / 10",
    budget: "$3.18",
    budgetDetail: "of $6.50 budget",
    selectedIndex: 1,
    workers: [
      { id: "metrics", title: "Metric Model Worker", file: "metrics.json", description: "Define metric contracts" },
      { id: "panels", title: "Panel Layout Worker", file: "panels.json", description: "Generate dashboard panel layout" },
      { id: "actions", title: "Action Controls Worker", file: "actions.json", description: "Generate action controls" },
      { id: "adapter", title: "Data Adapter Worker", file: "adapter.json", description: "Define data adapter bindings" },
      { id: "empty-states", title: "Empty States Worker", file: "empty_states.json", description: "Generate loading and empty states" },
      { id: "screenshot", title: "Screenshot Worker", file: "screenshot.json", description: "Capture dashboard validation screenshot" }
    ]
  },
  "release-page": {
    id: "release-page",
    label: "Release evidence page",
    detail: "Evidence and compliance template",
    slug: "release-evidence",
    workerType: "release_evidence_worker",
    validationTier: "review",
    risk: "medium",
    tasks: "9 / 9",
    budget: "$2.86",
    budgetDetail: "of $5.50 budget",
    selectedIndex: 2,
    workers: [
      { id: "summary", title: "Change Summary Worker", file: "summary.json", description: "Generate release change summary" },
      { id: "artifacts", title: "Artifact Index Worker", file: "artifacts.json", description: "Generate artifact index" },
      { id: "approvals", title: "Approval Gate Worker", file: "approvals.json", description: "Generate approval gates" },
      { id: "cost", title: "Cost Receipt Worker", file: "cost.json", description: "Generate cost receipt" },
      { id: "risk", title: "Risk Notes Worker", file: "risk.json", description: "Generate risk notes" },
      { id: "audit", title: "Audit Trail Worker", file: "audit.json", description: "Generate audit trail" }
    ]
  }
};

let pipelineStudioControlsInitialized = false;
let pipelineStudioState = null;
let pipelineStudioOptionsReady = false;
let pipelineSelectedInputId = "";
let pipelineSelectedIntegrationId = "";
let pipelineSelectedValidationId = "";
let pipelineIntegrationActiveView = "order";

function setPipelineField(name, value) {
  document.querySelectorAll(`[data-pipeline-field="${name}"]`).forEach((element) => {
    element.textContent = value;
  });
}

function updateIndexedPipelineText(attribute, values) {
  document.querySelectorAll(`[${attribute}]`).forEach((element) => {
    const index = Number.parseInt(element.getAttribute(attribute) || "0", 10);
    element.textContent = values[index] || "";
  });
}

function selectedPipelineStudioProject() {
  return pipelineStudioProjects[pipelineProjectSelect?.value || "generic-easy-medium-task"] || pipelineStudioProjects["generic-easy-medium-task"];
}

function selectedPipelineStudioTemplate() {
  return pipelineStudioTemplates[pipelineTemplateSelect?.value || "generic-task"] || pipelineStudioTemplates["generic-task"];
}

function optionMarkup(items, labelKey = "label") {
  return items
    .map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item[labelKey] || item.name || item.id)}</option>`)
    .join("");
}

function renderPipelineTemplateCards(templates, selectedTemplateId) {
  if (!pipelineTemplateLibrary || !templates.length) return;
  pipelineTemplateLibrary.innerHTML = templates
    .map((template) => {
      const isActive = template.id === selectedTemplateId;
      return `
        <button class="pipelineTemplateCard ${isActive ? "active" : ""}" type="button" data-template-card="${escapeHtml(template.id)}" aria-pressed="${String(isActive)}">
          <strong>${escapeHtml(template.label || template.id)}</strong>
          <span>${escapeHtml(template.description || template.detail || "")}</span>
          <small>${escapeHtml(template.tagline || template.detail || "")}</small>
        </button>
      `;
    })
    .join("");
  pipelineTemplateCards = document.querySelectorAll("[data-template-card]");
}

function normalizePipelineState(payload) {
  if (!payload || !payload.pipeline) return;
  const projects = Array.isArray(payload.projects) ? payload.projects : [];
  const templates = Array.isArray(payload.templates) ? payload.templates : [];
  if (projects.length) {
    pipelineStudioProjects = Object.fromEntries(projects.map((project) => [
      project.id,
      {
        key: project.id,
        name: project.label || project.id,
        surface: project.surface || "",
        surfaceValue: project.surface_value || "",
        ownedRoot: project.owned_root || "",
        readPaths: Array.isArray(project.read_paths) ? project.read_paths : []
      }
    ]));
    if (pipelineProjectSelect) {
      pipelineProjectSelect.innerHTML = optionMarkup(projects);
    }
  }
  if (templates.length) {
    pipelineStudioTemplates = Object.fromEntries(templates.map((template) => [
      template.id,
      {
        id: template.id,
        label: template.label || template.id,
        detail: template.detail || "",
        slug: template.id,
        workerType: template.worker_type || "pipeline_worker",
        validationTier: template.validation_tier || payload.pipeline.validation?.tier || "",
        risk: template.risk || payload.pipeline.inspector?.summary?.risk_level || "",
        tasks: payload.pipeline.tasks || "",
        budget: payload.pipeline.budget || "",
        budgetDetail: payload.pipeline.budget_detail || "",
        budgetSpentUsd: Number(template.budget_spent_usd || 0),
        budgetCapUsd: Number(template.budget_cap_usd || 0),
        executionModel: template.execution_model || payload.pipeline.execution_model || "",
        workerStageLabel: template.worker_stage_label || payload.pipeline.worker_stage_label || "",
        selectedWorker: template.selected_worker || "",
        requiredInputs: Array.isArray(template.required_inputs) ? template.required_inputs : [],
        selectedIndex: 0,
        workers: payload.pipeline.workers || []
      }
    ]));
  }
  pipelineStudioState = payload;
  pipelineStudioOptionsReady = true;
  if (pipelineProjectSelect) pipelineProjectSelect.value = payload.selected?.project_id || pipelineProjectSelect.value;
  if (pipelineTemplateSelect) {
    if (templates.length) {
      pipelineTemplateSelect.innerHTML = optionMarkup(templates);
    }
    pipelineTemplateSelect.value = payload.selected?.template_id || pipelineTemplateSelect.value;
  }
  if (pipelineSurfaceSelect) {
    const selectedProject = projects.find((project) => project.id === (payload.selected?.project_id || ""));
    if (selectedProject?.surface_value) {
      if (!Array.from(pipelineSurfaceSelect.options).some((option) => option.value === selectedProject.surface_value)) {
        pipelineSurfaceSelect.add(new Option(selectedProject.surface || selectedProject.surface_value, selectedProject.surface_value));
      }
      pipelineSurfaceSelect.value = selectedProject.surface_value;
    }
  }
  renderPipelineTemplateCards(templates, payload.selected?.template_id || "");
}

function renderPipelineCards(attributeBase, items, keys) {
  keys.forEach(([suffix, key]) => {
    updateIndexedPipelineText(`${attributeBase}-${suffix}`, items.map((item) => item[key] || ""));
  });
}

function selectedPipelinePayloadProject() {
  const projectId = pipelineStudioState?.selected?.project_id || pipelineProjectSelect?.value || "";
  return (pipelineStudioState?.projects || []).find((project) => project.id === projectId) || null;
}

function selectedPipelinePayloadTemplate() {
  const templateId = pipelineStudioState?.selected?.template_id || pipelineTemplateSelect?.value || "";
  return (pipelineStudioState?.templates || []).find((template) => template.id === templateId) || null;
}

function setPipelineSaveStatus(message, isError = false) {
  if (pipelineSaveStatus) {
    pipelineSaveStatus.textContent = message;
    pipelineSaveStatus.classList.toggle("error", isError);
  }
}

function setPipelineManifestStatus(message, isError = false) {
  if (pipelineManifestStatus) {
    pipelineManifestStatus.textContent = message;
    pipelineManifestStatus.classList.toggle("error", isError);
  }
}

const PIPELINE_INPUT_TYPES = {
  text: { label: "Text", icon: "T", format: "plain text" },
  details: { label: "Details", icon: "D", format: "markdown" },
  image: { label: "Image", icon: "IMG", format: "image reference" },
  questionnaire: { label: "Questionnaire", icon: "Q", format: "structured answers" },
  path: { label: "Path target", icon: "P", format: "path list" },
  evidence: { label: "Evidence", icon: "E", format: "artifact list" }
};

function pipelineInputType(item) {
  const raw = String(item?.kind || item?.input_type || item?.type || "text").trim().toLowerCase().replaceAll("_", "-");
  if (raw === "images" || raw === "screenshot" || raw === "mockup") return "image";
  if (raw === "question" || raw === "questions" || raw === "form") return "questionnaire";
  if (raw === "paths" || raw === "route" || raw === "routes" || raw === "command") return "path";
  if (raw === "artifact" || raw === "artifacts" || raw === "receipt") return "evidence";
  if (raw === "detail") return "details";
  return Object.prototype.hasOwnProperty.call(PIPELINE_INPUT_TYPES, raw) ? raw : "text";
}

function pipelineInputTypeLabel(type) {
  return PIPELINE_INPUT_TYPES[type]?.label || PIPELINE_INPUT_TYPES.text.label;
}

function pipelineInputTypeIcon(type) {
  return PIPELINE_INPUT_TYPES[type]?.icon || PIPELINE_INPUT_TYPES.text.icon;
}

function pipelineInputTypeOptions(selected = "text") {
  return Object.entries(PIPELINE_INPUT_TYPES)
    .map(([value, meta]) => `<option value="${escapeHtml(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(meta.label)}</option>`)
    .join("");
}

function safeParsePipelineInputPayload(row) {
  try {
    const parsed = JSON.parse(row?.dataset?.inputPayload || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function pipelineInputStatusOptions(selected = "missing") {
  return ["provided", "configured", "missing", "optional"]
    .map((status) => `<option value="${status}" ${status === selected ? "selected" : ""}>${escapeHtml(status.replace("-", " "))}</option>`)
    .join("");
}

function pipelineInputId(item, index = 0) {
  const existing = String(item?.id || "").trim();
  if (existing) return existing;
  const title = String(item?.title || "").trim();
  const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return slug || `input-${index + 1}`;
}

function renderPipelineRequiredInputsEditor(inputs) {
  if (!pipelineRequiredInputsEditor) return;
  const rows = Array.isArray(inputs) && inputs.length ? inputs : [
    { id: "task-request", title: "Task request", detail: "What should the AI change or build?", status: "missing", required: true }
  ];
  pipelineRequiredInputsEditor.innerHTML = rows
    .map((item, index) => {
      const inputType = pipelineInputType(item);
      const inputStatus = String(item.status || "missing").toLowerCase().replaceAll("_", "-").replaceAll(" ", "-");
      return `
      <div class="pipelineInputConfigRow" data-input-row data-input-id="${escapeHtml(pipelineInputId(item, index))}" data-input-payload="${escapeHtml(JSON.stringify({ ...item, kind: inputType }))}">
        <input data-input-title type="text" value="${escapeHtml(item.title || "")}" aria-label="Input title">
        <select data-input-type aria-label="Input type">${pipelineInputTypeOptions(inputType)}</select>
        <input data-input-detail type="text" value="${escapeHtml(item.detail || "")}" aria-label="Input detail">
        <select data-input-status aria-label="Input status">${pipelineInputStatusOptions(inputStatus)}</select>
        <label><input data-input-required type="checkbox" ${item.required === false ? "" : "checked"}>Required</label>
        <button type="button" data-remove-input>×</button>
      </div>
    `;
    })
    .join("");
}

function collectPipelineRequiredInputs() {
  if (!pipelineRequiredInputsEditor) return [];
  return Array.from(pipelineRequiredInputsEditor.querySelectorAll("[data-input-row]"))
    .map((row, index) => {
      const existing = safeParsePipelineInputPayload(row);
      const title = row.querySelector("[data-input-title]")?.value?.trim() || "";
      const detail = row.querySelector("[data-input-detail]")?.value?.trim() || "";
      const kind = pipelineInputType({ kind: row.querySelector("[data-input-type]")?.value || existing.kind || existing.input_type || existing.type });
      const status = row.querySelector("[data-input-status]")?.value || "missing";
      const required = Boolean(row.querySelector("[data-input-required]")?.checked);
      const existingId = String(row.dataset.inputId || "").trim();
      const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
      return {
        ...existing,
        id: existingId || slug || `input-${index + 1}`,
        title,
        detail,
        kind,
        input_type: kind,
        status,
        required
      };
    })
    .filter((item) => item.title);
}

function renderPipelineInputCards(items) {
  const inputStage = document.querySelector(".stageInput");
  if (!inputStage) return;
  inputStage.querySelectorAll(".pipelineCard").forEach((card) => card.remove());
  const button = inputStage.querySelector("button");
  (items || []).forEach((item, index) => {
    const card = document.createElement("div");
    const status = String(item.status || "Missing").toLowerCase();
    const inputId = pipelineInputId(item, index);
    const inputType = pipelineInputType(item);
    card.className = `pipelineCard operatorInput ${status} inputType-${inputType} ${pipelineSelectedInputId === inputId ? "selected" : ""}`;
    card.dataset.inputId = inputId;
    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");
    card.setAttribute("aria-pressed", String(pipelineSelectedInputId === inputId));
    card.innerHTML = `
      <i>${escapeHtml(pipelineInputTypeIcon(inputType))}</i>
      <strong>${escapeHtml(item.title || "")}</strong>
      <span>${escapeHtml(item.detail || item.file || item.manifest || "")}</span>
      <small>${escapeHtml(pipelineInputTypeLabel(inputType))}</small>
      <em>${escapeHtml(item.status || "Missing")}</em>
    `;
    inputStage.insertBefore(card, button || null);
  });
  if (button) button.textContent = `View all (${(items || []).length})`;
}

function pipelineValidatorId(item, index = 0) {
  const existing = String(item?.id || "").trim();
  if (existing) return existing;
  const title = String(item?.title || "").trim();
  const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return slug || `validator-${index + 1}`;
}

function pipelineIntegrationId(item, index = 0) {
  const existing = String(item?.id || "").trim();
  if (existing) return existing;
  const title = String(item?.title || "").trim();
  const slug = title.toLowerCase().replace(/^integrate-?/, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return slug || `integration-${index + 1}`;
}

function renderPipelineIntegrationCards(items) {
  const integrationStage = document.querySelector(".stageIntegrate");
  if (!integrationStage) return;
  integrationStage.querySelectorAll(".pipelineCard.receipt").forEach((card) => card.remove());
  const button = integrationStage.querySelector("button");
  (items || []).forEach((item, index) => {
    const integrationId = pipelineIntegrationId(item, index);
    const status = String(item.status || "Accepted").toLowerCase().replace(/\s+/g, "-");
    const card = document.createElement("div");
    card.className = `pipelineCard receipt ${status} ${pipelineSelectedIntegrationId === integrationId ? "selected" : ""}`;
    card.dataset.integrationId = integrationId;
    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");
    card.setAttribute("aria-pressed", String(pipelineSelectedIntegrationId === integrationId));
    card.innerHTML = `
      <i>▧</i>
      <strong>${escapeHtml(item.title || "")}</strong>
      <span>${escapeHtml(item.file || item.receipt || "integration_receipt.json")}</span>
      <em>${escapeHtml(item.status || "Accepted")}</em>
    `;
    integrationStage.insertBefore(card, button || null);
  });
  const headerCount = integrationStage.querySelector("header span");
  if (headerCount) headerCount.textContent = `${(items || []).length} integration steps`;
  if (button) button.textContent = `View all (${(items || []).length})`;
}

function renderPipelineValidatorCards(items) {
  const validateStage = document.querySelector(".stageValidate");
  if (!validateStage) return;
  validateStage.querySelectorAll(".pipelineCard.validator").forEach((card) => card.remove());
  const button = validateStage.querySelector("button");
  (items || []).forEach((item, index) => {
    const validatorId = pipelineValidatorId(item, index);
    const status = String(item.status || "Configured").toLowerCase().replace(/\s+/g, "-");
    const mode = String(item.mode || "").toLowerCase();
    const card = document.createElement("div");
    card.className = `pipelineCard validator ${status} ${mode === "evidence" || validatorId === "screenshot" ? "screenshotCard" : ""} ${pipelineSelectedValidationId === validatorId ? "selected" : ""}`;
    card.dataset.validatorId = validatorId;
    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");
    card.setAttribute("aria-pressed", String(pipelineSelectedValidationId === validatorId));
    card.innerHTML = `
      <i>▧</i>
      <strong>${escapeHtml(item.title || "")}</strong>
      <span>${escapeHtml(item.file || item.receipt || "")}</span>
      <em>${escapeHtml(item.status || "Configured")}</em>
      ${mode === "evidence" || validatorId === "screenshot" ? `<div class="pipelineThumb" aria-hidden="true"><span></span><span></span><span></span><span></span></div>` : ""}
    `;
    validateStage.insertBefore(card, button || null);
  });
  const headerCount = validateStage.querySelector("header span");
  if (headerCount) headerCount.textContent = `${(items || []).length} validators`;
  if (button) button.textContent = `View all (${(items || []).length})`;
}

function selectedPipelineInput(inputId = pipelineSelectedInputId) {
  const inputs = pipelineStudioState?.pipeline?.input_cards || selectedPipelinePayloadTemplate()?.required_inputs || selectedPipelineStudioTemplate()?.requiredInputs || [];
  return (inputs || []).find((item, index) => pipelineInputId(item, index) === inputId) || null;
}

function selectedPipelineValidator(validatorId = pipelineSelectedValidationId) {
  const validators = pipelineStudioState?.pipeline?.validators || selectedPipelinePayloadTemplate()?.validators || [];
  return (validators || []).find((item, index) => pipelineValidatorId(item, index) === validatorId) || null;
}

function selectedPipelineIntegration(integrationId = pipelineSelectedIntegrationId) {
  const integrations = pipelineStudioState?.pipeline?.integration || [];
  return (integrations || []).find((item, index) => pipelineIntegrationId(item, index) === integrationId) || null;
}

function pipelineLinesToText(value) {
  if (Array.isArray(value)) return value.map((item) => String(item || "").trim()).filter(Boolean).join("\n");
  return String(value || "").trim();
}

function pipelineTextToLines(value) {
  return String(value || "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
}

function uniquePipelineLines(values) {
  return Array.from(new Set((values || []).map((value) => String(value || "").trim()).filter(Boolean)));
}

function setPipelineTextareaLines(textarea, values) {
  if (!textarea) return;
  textarea.value = uniquePipelineLines(values).join("\n");
}

function appendPipelineTextareaLines(textarea, values) {
  if (!textarea) return;
  setPipelineTextareaLines(textarea, [...pipelineTextToLines(textarea.value), ...values]);
}

function pipelineQuestionItemsToText(value) {
  if (!Array.isArray(value)) return String(value || "").trim();
  return value
    .map((item) => {
      if (typeof item === "string") return item.trim();
      if (!item || typeof item !== "object") return "";
      const prompt = String(item.prompt || item.question || "").trim();
      const required = item.required === false ? "optional" : "required";
      const answerType = String(item.answer_type || item.type || "text").trim();
      const options = Array.isArray(item.options) ? item.options.join(", ") : String(item.options || "").trim();
      return [prompt, required, answerType, options].filter(Boolean).join(" | ");
    })
    .filter(Boolean)
    .join("\n");
}

function pipelineTextToQuestionItems(value) {
  return String(value || "")
    .split(/\r?\n/)
    .map((line, index) => {
      const parts = line.split("|").map((part) => part.trim());
      const prompt = parts[0] || "";
      if (!prompt) return null;
      const requiredText = (parts[1] || "required").toLowerCase();
      const answerType = parts[2] || "text";
      const options = (parts[3] || "").split(",").map((option) => option.trim()).filter(Boolean);
      return {
        id: `q-${index + 1}`,
        prompt,
        required: requiredText !== "optional" && requiredText !== "false",
        answer_type: answerType,
        options
      };
    })
    .filter(Boolean);
}

function renderValidationCommandRows(commands) {
  if (!pipelineValidationCommandRows) return;
  const rows = uniquePipelineLines(commands);
  pipelineValidationCommandRows.innerHTML = rows.map((command, index) => `
    <div class="pipelineValidationRow commandRow" data-validation-command-row>
      <span>${index + 1}</span>
      <input data-validation-command-value type="text" value="${escapeHtml(command)}" aria-label="Validation command ${index + 1}">
      <button type="button" data-validation-row-remove>Remove</button>
    </div>
  `).join("");
}

function renderValidationEvidenceRows(evidence) {
  if (!pipelineValidationEvidenceRows) return;
  const rows = uniquePipelineLines(evidence);
  pipelineValidationEvidenceRows.innerHTML = rows.map((item, index) => {
    const type = item.match(/\.(png|jpg|jpeg|webp)$/i) ? "screenshot" : item.match(/\.(ndjson|log|txt)$/i) ? "log" : item.includes("receipt") ? "receipt" : "artifact";
    return `
      <div class="pipelineValidationRow evidenceRow" data-validation-evidence-row>
        <select data-validation-evidence-type aria-label="Evidence type ${index + 1}">
          <option value="receipt" ${type === "receipt" ? "selected" : ""}>Receipt</option>
          <option value="screenshot" ${type === "screenshot" ? "selected" : ""}>Screenshot</option>
          <option value="artifact" ${type === "artifact" ? "selected" : ""}>Artifact</option>
          <option value="log" ${type === "log" ? "selected" : ""}>Log</option>
        </select>
        <input data-validation-evidence-value type="text" value="${escapeHtml(item)}" aria-label="Evidence path ${index + 1}">
        <button type="button" data-validation-row-remove>Remove</button>
      </div>
    `;
  }).join("");
}

function renderValidationGateRows(gates) {
  if (!pipelineValidationGateRows) return;
  const rows = uniquePipelineLines(gates);
  pipelineValidationGateRows.innerHTML = rows.map((gate, index) => `
    <div class="pipelineValidationRow gateRow" data-validation-gate-row>
      <select data-validation-gate-severity aria-label="Gate severity ${index + 1}">
        <option value="blocking" selected>Blocking</option>
        <option value="warning">Warning</option>
        <option value="review">Review</option>
      </select>
      <input data-validation-gate-value type="text" value="${escapeHtml(gate)}" aria-label="Validation gate ${index + 1}">
      <button type="button" data-validation-row-remove>Remove</button>
    </div>
  `).join("");
}

function renderValidationSchemaRows(paths) {
  if (!pipelineValidationSchemaRows) return;
  const rows = uniquePipelineLines(paths);
  pipelineValidationSchemaRows.innerHTML = rows.map((path, index) => {
    const scope = path.includes("integration") ? "integration" : path.includes("validation") ? "validation" : "pipeline";
    return `
      <div class="pipelineValidationRow schemaRow" data-validation-schema-row>
        <select data-validation-schema-scope aria-label="Schema scope ${index + 1}">
          <option value="pipeline" ${scope === "pipeline" ? "selected" : ""}>Pipeline</option>
          <option value="integration" ${scope === "integration" ? "selected" : ""}>Integration</option>
          <option value="validation" ${scope === "validation" ? "selected" : ""}>Validation</option>
          <option value="evidence" ${scope === "evidence" ? "selected" : ""}>Evidence</option>
        </select>
        <input data-validation-schema-value type="text" value="${escapeHtml(path)}" aria-label="Schema path ${index + 1}">
        <button type="button" data-validation-row-remove>Remove</button>
      </div>
    `;
  }).join("");
}

function renderPipelineValidationTypedEditors(validator = {}) {
  renderValidationCommandRows(validator.commands || pipelineTextToLines(pipelineValidationCommandsInput?.value || ""));
  renderValidationEvidenceRows(validator.evidence || pipelineTextToLines(pipelineValidationEvidenceInput?.value || ""));
  renderValidationGateRows(validator.gates || pipelineTextToLines(pipelineValidationGatesInput?.value || ""));
  renderValidationSchemaRows(validator.schema_paths || pipelineTextToLines(pipelineValidationSchemaInput?.value || ""));
}

function collectValidationRowValues(selector, valueSelector) {
  return Array.from(document.querySelectorAll(selector))
    .map((row) => row.querySelector(valueSelector)?.value?.trim() || "")
    .filter(Boolean);
}

function syncValidationRowsToTextareas() {
  setPipelineTextareaLines(pipelineValidationCommandsInput, collectValidationRowValues("[data-validation-command-row]", "[data-validation-command-value]"));
  setPipelineTextareaLines(pipelineValidationEvidenceInput, collectValidationRowValues("[data-validation-evidence-row]", "[data-validation-evidence-value]"));
  setPipelineTextareaLines(pipelineValidationGatesInput, collectValidationRowValues("[data-validation-gate-row]", "[data-validation-gate-value]"));
  setPipelineTextareaLines(pipelineValidationSchemaInput, collectValidationRowValues("[data-validation-schema-row]", "[data-validation-schema-value]"));
}

function ensureValidationIntegrationGate() {
  const referencesIntegrationLane = [
    pipelineValidationEvidenceInput?.value || "",
    pipelineValidationSchemaInput?.value || "",
    pipelineValidationCommandsInput?.value || ""
  ].some((value) => value.includes("integration/integration_lane.json"));
  if (!referencesIntegrationLane) return;
  appendPipelineTextareaLines(pipelineValidationGatesInput, ["Integration lane has no blocked or rejected receipts"]);
}

function syncValidationTextareaToRows(kind) {
  if (kind === "commands") renderValidationCommandRows(pipelineTextToLines(pipelineValidationCommandsInput?.value || ""));
  if (kind === "evidence") renderValidationEvidenceRows(pipelineTextToLines(pipelineValidationEvidenceInput?.value || ""));
  if (kind === "gates") renderValidationGateRows(pipelineTextToLines(pipelineValidationGatesInput?.value || ""));
  if (kind === "schema") renderValidationSchemaRows(pipelineTextToLines(pipelineValidationSchemaInput?.value || ""));
}

function addPipelineValidationRow(kind, value = "") {
  if (kind === "commands") {
    renderValidationCommandRows([...collectValidationRowValues("[data-validation-command-row]", "[data-validation-command-value]"), value || ""]);
    return;
  }
  if (kind === "evidence") {
    renderValidationEvidenceRows([...collectValidationRowValues("[data-validation-evidence-row]", "[data-validation-evidence-value]"), value || ""]);
    return;
  }
  if (kind === "gates") {
    renderValidationGateRows([...collectValidationRowValues("[data-validation-gate-row]", "[data-validation-gate-value]"), value || ""]);
    return;
  }
  renderValidationSchemaRows([...collectValidationRowValues("[data-validation-schema-row]", "[data-validation-schema-value]"), value || ""]);
}

function integrationValidationContext(steps = []) {
  const selectedSteps = Array.isArray(steps) ? steps : [];
  const receipts = selectedSteps.map((step) => step.receipt || step.path || "").filter(Boolean);
  const artifacts = selectedSteps.flatMap((step) => Array.isArray(step.artifacts) ? step.artifacts : []);
  const dependencies = selectedSteps.flatMap((step) => Array.isArray(step.dependencies) ? step.dependencies : []);
  const gates = selectedSteps.flatMap((step) => Array.isArray(step.gates) ? step.gates : []);
  return {
    commands: ["python3 -m json.tool workspace/runs/dev-pipeline-studio/docs-pages/latest/integration/integration_lane.json"],
    evidence: uniquePipelineLines(["integration/integration_lane.json", ...receipts, ...artifacts]),
    gates: uniquePipelineLines([
      ...gates,
      ...dependencies.map((dependency) => `Dependency receipt accepted: ${dependency}`),
      "Integration lane has no blocked or rejected receipts"
    ]),
    schema: uniquePipelineLines(["integration/integration_lane.json", "integration_receipts/*.json"])
  };
}

function importPipelineIntegrationContext(steps) {
  const context = integrationValidationContext(steps);
  appendPipelineTextareaLines(pipelineValidationCommandsInput, context.commands);
  appendPipelineTextareaLines(pipelineValidationEvidenceInput, context.evidence);
  appendPipelineTextareaLines(pipelineValidationGatesInput, context.gates);
  appendPipelineTextareaLines(pipelineValidationSchemaInput, context.schema);
  renderPipelineValidationTypedEditors({
    commands: pipelineTextToLines(pipelineValidationCommandsInput?.value || ""),
    evidence: pipelineTextToLines(pipelineValidationEvidenceInput?.value || ""),
    gates: pipelineTextToLines(pipelineValidationGatesInput?.value || ""),
    schema_paths: pipelineTextToLines(pipelineValidationSchemaInput?.value || "")
  });
  updatePipelineValidationModeButtons(pipelineValidationModeSelect?.value || "commands");
  if (pipelineValidationInspectorStatus) {
    pipelineValidationInspectorStatus.textContent = `Imported ${steps.length} integration step${steps.length === 1 ? "" : "s"} into this validator. Save validation to write receipts.`;
  }
}

function renderPipelineValidationConsultation() {
  if (!pipelineValidationIntegrationContext) return;
  const integrations = pipelineStudioState?.pipeline?.integration || [];
  if (!integrations.length) {
    pipelineValidationIntegrationContext.innerHTML = `<p>No integration steps are configured for this template yet.</p>`;
    return;
  }
  pipelineValidationIntegrationContext.innerHTML = integrations.map((step, index) => `
    <article>
      <div>
        <strong>${escapeHtml(step.title || step.id || `Integration ${index + 1}`)}</strong>
        <span>${escapeHtml(step.status || "Configured")} · ${escapeHtml(step.mode || "dependency-order")}</span>
      </div>
      <small>${escapeHtml((step.artifacts || []).slice(0, 2).join(", ") || step.receipt || "artifact pending")}</small>
      <button type="button" data-import-integration-step="${index}">Use step</button>
    </article>
  `).join("");
}

function pipelineInputRowById(inputId) {
  return Array.from(pipelineRequiredInputsEditor?.querySelectorAll("[data-input-row]") || [])
    .find((row) => row.dataset.inputId === inputId) || null;
}

function setPipelineInspectorMode(mode) {
  const inputMode = mode === "input";
  const integrationMode = mode === "integration";
  const validationMode = mode === "validation";
  const workerMode = !inputMode && !integrationMode && !validationMode;
  pipelineInputInspector?.classList.toggle("hidden", !inputMode);
  pipelineIntegrationInspector?.classList.toggle("hidden", !integrationMode);
  pipelineValidationInspector?.classList.toggle("hidden", !validationMode);
  pipelineInspectorNav?.classList.toggle("hidden", !workerMode);
  if (workerMode) {
    setInspectorTab(currentInspectorTab);
  } else {
    pipelineWorkerInspectorActions?.classList.add("hidden");
    pipelineManifestEditor?.classList.add("hidden");
    pipelineContractSummary?.classList.add("hidden");
    pipelineContractPanel?.classList.add("hidden");
    pipelineArtifactPanel?.classList.add("hidden");
    pipelineLogsPanel?.classList.add("hidden");
    pipelineCostPanel?.classList.add("hidden");
  }
}

function setInspectorTab(tabName) {
  currentInspectorTab = tabName || "manifest";
  const isManifest = currentInspectorTab === "manifest";
  const isContract = currentInspectorTab === "contract";
  const isArtifact = currentInspectorTab === "artifact";
  const isLogs = currentInspectorTab === "logs";
  const isCost = currentInspectorTab === "cost";
  pipelineInspectorNav?.querySelectorAll("a[data-inspector-tab]").forEach((link) => {
    link.classList.toggle("active", link.dataset.inspectorTab === currentInspectorTab);
  });
  pipelineWorkerInspectorActions?.classList.toggle("hidden", !isManifest);
  pipelineManifestEditor?.classList.toggle("hidden", !isManifest);
  pipelineContractSummary?.classList.toggle("hidden", !isManifest);
  pipelineContractPanel?.classList.toggle("hidden", !isContract);
  pipelineArtifactPanel?.classList.toggle("hidden", !isArtifact);
  pipelineLogsPanel?.classList.toggle("hidden", !isLogs);
  pipelineCostPanel?.classList.toggle("hidden", !isCost);
  if (isContract) populateContractPanel();
}

function populateContractPanel() {
  let manifest = null;
  try { manifest = parsePipelineManifestEditor(); } catch { manifest = {}; }
  const ownedPaths = manifest?.owned_paths || [];
  const readPaths = manifest?.read_paths || [];
  const dependencies = manifest?.dependencies || [];
  const acceptance = manifest?.acceptance || [];
  const tier = manifest?.validation?.tier || manifest?.validation_tier || "—";
  const risk = manifest?.validation?.risk || manifest?.risk || "—";
  const noneItem = '<li class="contractNone">None</li>';
  const pathItem = (p) => `<li><code>${escapeHtml(String(p))}</code></li>`;
  const acceptItem = (a) => `<li><span class="contractCheck">⊙</span>${escapeHtml(String(a))}</li>`;
  const owned = document.querySelector("#contractOwnedPaths");
  const read = document.querySelector("#contractReadPaths");
  const deps = document.querySelector("#contractDependencies");
  const acc = document.querySelector("#contractAcceptance");
  const tierEl = document.querySelector("#contractValidationTier");
  const riskEl = document.querySelector("#contractRiskLevel");
  if (owned) owned.innerHTML = ownedPaths.length ? ownedPaths.map(pathItem).join("") : noneItem;
  if (read) read.innerHTML = readPaths.length ? readPaths.map(pathItem).join("") : noneItem;
  if (deps) deps.innerHTML = dependencies.length ? dependencies.map(pathItem).join("") : noneItem;
  if (acc) acc.innerHTML = acceptance.length ? acceptance.map(acceptItem).join("") : noneItem;
  if (tierEl) tierEl.textContent = tier;
  if (riskEl) riskEl.textContent = risk;
}

function titleCasePipelineStatus(status) {
  const raw = String(status || "").trim();
  if (!raw) return "Input";
  return raw.charAt(0).toUpperCase() + raw.slice(1);
}

function showPipelineWorkerInspector() {
  currentInspectorTab = "manifest";
  setPipelineInspectorMode("worker");
  pipelineSelectedInputId = "";
  pipelineSelectedIntegrationId = "";
  pipelineSelectedValidationId = "";
  if (pipelineInspectorBadge) pipelineInspectorBadge.textContent = "W1";
  if (pipelineInspectorState) pipelineInspectorState.textContent = "Completed";
  renderPipelineInputCards(pipelineStudioState?.pipeline?.input_cards || selectedPipelinePayloadTemplate()?.required_inputs || selectedPipelineStudioTemplate()?.requiredInputs || []);
  renderPipelineIntegrationCards(pipelineStudioState?.pipeline?.integration || []);
  renderPipelineValidatorCards(pipelineStudioState?.pipeline?.validators || selectedPipelinePayloadTemplate()?.validators || []);
}

function updatePipelineInputEditorRow(inputId, values) {
  const row = pipelineInputRowById(inputId);
  if (!row) return;
  const title = row.querySelector("[data-input-title]");
  const type = row.querySelector("[data-input-type]");
  const detail = row.querySelector("[data-input-detail]");
  const status = row.querySelector("[data-input-status]");
  const required = row.querySelector("[data-input-required]");
  if (title) title.value = values.title || "";
  if (type) type.value = pipelineInputType(values);
  if (detail) detail.value = values.detail || "";
  if (status) status.value = values.status || "missing";
  if (required) required.checked = values.required !== false;
  row.dataset.inputPayload = JSON.stringify(values);
}

function updatePipelineInputTypeEditors(type) {
  const activeType = pipelineInputType({ kind: type });
  document.querySelectorAll("[data-input-type-editor]").forEach((editor) => {
    const supported = String(editor.getAttribute("data-input-type-editor") || "").split(/\s+/);
    editor.classList.toggle("hidden", !supported.includes(activeType));
  });
}

function showPipelineInputInspector(inputId, message = "") {
  const input = selectedPipelineInput(inputId);
  if (!input) {
    pipelineSelectedInputId = "";
    showPipelineWorkerInspector();
    return;
  }
  const status = String(input.status || "missing").toLowerCase();
  pipelineSelectedInputId = inputId;
  pipelineSelectedIntegrationId = "";
  pipelineSelectedValidationId = "";
  setPipelineInspectorMode("input");
  setPipelineField("selectedWorker", input.title || "Input");
  if (pipelineInspectorBadge) pipelineInspectorBadge.textContent = "Input";
  if (pipelineInspectorState) pipelineInspectorState.textContent = titleCasePipelineStatus(status);
  if (pipelineInputTitleInput) pipelineInputTitleInput.value = input.title || "";
  if (pipelineInputTypeSelect) pipelineInputTypeSelect.value = pipelineInputType(input);
  if (pipelineInputDetailInput) pipelineInputDetailInput.value = input.detail || input.file || "";
  if (pipelineInputStatusSelect) pipelineInputStatusSelect.value = status;
  if (pipelineInputRequiredCheckbox) pipelineInputRequiredCheckbox.checked = input.required !== false;
  if (pipelineInputFormatInput) pipelineInputFormatInput.value = input.format || PIPELINE_INPUT_TYPES[pipelineInputType(input)]?.format || "";
  if (pipelineInputImageRefsInput) pipelineInputImageRefsInput.value = pipelineLinesToText(input.image_refs || input.images || input.references);
  if (pipelineInputImageNotesInput) pipelineInputImageNotesInput.value = input.image_notes || input.reference_notes || "";
  if (pipelineInputQuestionsInput) pipelineInputQuestionsInput.value = pipelineQuestionItemsToText(input.questions || input.questionnaire);
  if (pipelineInputPathsInput) pipelineInputPathsInput.value = pipelineLinesToText(input.paths || input.target_paths || input.routes);
  if (pipelineInputPathPolicyInput) pipelineInputPathPolicyInput.value = input.path_policy || input.ownership_policy || "";
  if (pipelineInputArtifactsInput) pipelineInputArtifactsInput.value = pipelineLinesToText(input.artifacts || input.evidence_artifacts);
  if (pipelineInputEvidencePolicyInput) pipelineInputEvidencePolicyInput.value = input.evidence_policy || input.validation_policy || "";
  if (pipelineInputManifestPath) pipelineInputManifestPath.textContent = input.manifest ? `Input manifest: ${input.manifest}` : "Input manifest output pending";
  updatePipelineInputTypeEditors(pipelineInputType(input));
  if (pipelineInputInspectorStatus) pipelineInputInspectorStatus.textContent = message || "Edit the input contract, then save.";
  renderPipelineInputCards(pipelineStudioState?.pipeline?.input_cards || selectedPipelinePayloadTemplate()?.required_inputs || selectedPipelineStudioTemplate()?.requiredInputs || []);
  renderPipelineIntegrationCards(pipelineStudioState?.pipeline?.integration || []);
  renderPipelineValidatorCards(pipelineStudioState?.pipeline?.validators || selectedPipelinePayloadTemplate()?.validators || []);
  syncPipelineWorkerCards(pipelineStudioState?.pipeline?.workers || selectedPipelineStudioTemplate()?.workers || []);
}

function collectPipelineInputConfig() {
  const selected = selectedPipelineInput() || {};
  const kind = pipelineInputType({ kind: pipelineInputTypeSelect?.value || selected.kind || selected.input_type || selected.type });
  return {
    ...selected,
    id: pipelineSelectedInputId,
    title: pipelineInputTitleInput?.value?.trim() || selected.title || "Untitled input",
    detail: pipelineInputDetailInput?.value?.trim() || "",
    kind,
    input_type: kind,
    status: pipelineInputStatusSelect?.value || "missing",
    required: Boolean(pipelineInputRequiredCheckbox?.checked),
    format: pipelineInputFormatInput?.value?.trim() || PIPELINE_INPUT_TYPES[kind]?.format || "",
    image_refs: pipelineTextToLines(pipelineInputImageRefsInput?.value || ""),
    image_notes: pipelineInputImageNotesInput?.value?.trim() || "",
    questions: pipelineTextToQuestionItems(pipelineInputQuestionsInput?.value || ""),
    paths: pipelineTextToLines(pipelineInputPathsInput?.value || ""),
    path_policy: pipelineInputPathPolicyInput?.value?.trim() || "",
    artifacts: pipelineTextToLines(pipelineInputArtifactsInput?.value || ""),
    evidence_policy: pipelineInputEvidencePolicyInput?.value?.trim() || "",
    manifest: selected.manifest || ""
  };
}

async function savePipelineSelectedInput() {
  if (!pipelineSelectedInputId) return;
  const values = collectPipelineInputConfig();
  updatePipelineInputEditorRow(pipelineSelectedInputId, values);
  if (pipelineInputInspectorStatus) pipelineInputInspectorStatus.textContent = "Saving input...";
  const payload = await savePipelineDraft("save", { includeManifest: false });
  if (payload) {
    pipelineSelectedInputId = values.title
      ? (pipelineInputRowById(pipelineSelectedInputId)?.dataset.inputId || pipelineSelectedInputId)
      : pipelineSelectedInputId;
    showPipelineInputInspector(pipelineSelectedInputId, `Saved ${values.title}.`);
  }
}

function updatePipelineValidationModeButtons(mode) {
  document.querySelectorAll("[data-validation-mode]").forEach((button) => {
    const active = button.dataset.validationMode === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll("[data-validation-editor]").forEach((editor) => {
    editor.classList.toggle("active", editor.dataset.validationEditor === mode);
  });
}

function updatePipelineIntegrationView(view = pipelineIntegrationActiveView) {
  const nextView = ["order", "apply", "conflicts", "receipts"].includes(view) ? view : "order";
  pipelineIntegrationActiveView = nextView;
  document.querySelectorAll("[data-integration-view]").forEach((button) => {
    const active = button.dataset.integrationView === nextView;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll("[data-integration-section]").forEach((section) => {
    const views = String(section.dataset.integrationSection || "").split(/\s+/).filter(Boolean);
    section.classList.toggle("hidden", !views.includes(nextView));
  });
}

function showPipelineIntegrationInspector(integrationId, message = "") {
  const integration = selectedPipelineIntegration(integrationId);
  if (!integration) {
    pipelineSelectedIntegrationId = "";
    showPipelineWorkerInspector();
    return;
  }
  const status = String(integration.status || "configured").toLowerCase().replace(/\s+/g, "-");
  const mode = String(integration.mode || "dependency-order").toLowerCase();
  pipelineSelectedIntegrationId = integrationId;
  pipelineSelectedInputId = "";
  pipelineSelectedValidationId = "";
  setPipelineInspectorMode("integration");
  setPipelineField("selectedWorker", integration.title || "Integration");
  if (pipelineInspectorBadge) pipelineInspectorBadge.textContent = "Integrator";
  if (pipelineInspectorState) pipelineInspectorState.textContent = titleCasePipelineStatus(status);
  if (pipelineIntegrationTitleInput) pipelineIntegrationTitleInput.value = integration.title || "";
  if (pipelineIntegrationStatusSelect) pipelineIntegrationStatusSelect.value = status;
  if (pipelineIntegrationModeSelect) pipelineIntegrationModeSelect.value = mode;
  if (pipelineIntegrationApplyInput) pipelineIntegrationApplyInput.value = integration.apply_policy || integration.summary || "";
  if (pipelineIntegrationConflictInput) pipelineIntegrationConflictInput.value = integration.conflict_policy || "";
  if (pipelineIntegrationDependenciesInput) pipelineIntegrationDependenciesInput.value = pipelineLinesToText(integration.dependencies);
  if (pipelineIntegrationArtifactsInput) pipelineIntegrationArtifactsInput.value = pipelineLinesToText(integration.artifacts);
  if (pipelineIntegrationGatesInput) pipelineIntegrationGatesInput.value = pipelineLinesToText(integration.gates);
  if (pipelineIntegrationRollbackInput) pipelineIntegrationRollbackInput.value = pipelineLinesToText(integration.rollback_plan);
  if (pipelineIntegrationConfigPath) pipelineIntegrationConfigPath.textContent = integration.config ? `Config: ${integration.config}` : "Config output pending";
  if (pipelineIntegrationReceiptPath) pipelineIntegrationReceiptPath.textContent = integration.receipt ? `Receipt: ${integration.receipt}` : integration.path ? `Receipt: ${integration.path}` : "Receipt output pending";
  if (pipelineIntegrationInspectorStatus) pipelineIntegrationInspectorStatus.textContent = message || "Configure this integration lane view, then save outputs.";
  updatePipelineIntegrationView(pipelineIntegrationActiveView);
  renderPipelineInputCards(pipelineStudioState?.pipeline?.input_cards || selectedPipelinePayloadTemplate()?.required_inputs || selectedPipelineStudioTemplate()?.requiredInputs || []);
  renderPipelineIntegrationCards(pipelineStudioState?.pipeline?.integration || []);
  renderPipelineValidatorCards(pipelineStudioState?.pipeline?.validators || selectedPipelinePayloadTemplate()?.validators || []);
  syncPipelineWorkerCards(pipelineStudioState?.pipeline?.workers || selectedPipelineStudioTemplate()?.workers || []);
}

function collectPipelineIntegrationConfig() {
  const selected = selectedPipelineIntegration();
  return {
    id: pipelineSelectedIntegrationId,
    title: pipelineIntegrationTitleInput?.value?.trim() || selected?.title || "Integration step",
    status: pipelineIntegrationStatusSelect?.value || "configured",
    mode: pipelineIntegrationModeSelect?.value || "dependency-order",
    apply_policy: pipelineIntegrationApplyInput?.value?.trim() || "",
    conflict_policy: pipelineIntegrationConflictInput?.value?.trim() || "",
    dependencies: pipelineTextToLines(pipelineIntegrationDependenciesInput?.value || ""),
    artifacts: pipelineTextToLines(pipelineIntegrationArtifactsInput?.value || ""),
    gates: pipelineTextToLines(pipelineIntegrationGatesInput?.value || ""),
    rollback_plan: pipelineTextToLines(pipelineIntegrationRollbackInput?.value || ""),
    receipt: selected?.receipt || "",
    config_path: selected?.config?.replace(/^.*workspace\/runs\/dev-pipeline-studio\/docs-pages\/latest\//, "") || ""
  };
}

async function savePipelineSelectedIntegration() {
  if (!pipelineSelectedIntegrationId) return;
  const integrationConfig = collectPipelineIntegrationConfig();
  if (pipelineIntegrationInspectorStatus) pipelineIntegrationInspectorStatus.textContent = "Saving integration outputs...";
  const payload = await savePipelineDraft("save_integration", { includeManifest: false, integrationConfig });
  if (payload) {
    showPipelineIntegrationInspector(pipelineSelectedIntegrationId, `Saved ${integrationConfig.title}.`);
  }
}

function showPipelineValidationInspector(validatorId, message = "") {
  const validator = selectedPipelineValidator(validatorId);
  if (!validator) {
    pipelineSelectedValidationId = "";
    showPipelineWorkerInspector();
    return;
  }
  const status = String(validator.status || "configured").toLowerCase().replace(/\s+/g, "-");
  const mode = String(validator.mode || "commands").toLowerCase();
  pipelineSelectedValidationId = validatorId;
  pipelineSelectedInputId = "";
  pipelineSelectedIntegrationId = "";
  setPipelineInspectorMode("validation");
  setPipelineField("selectedWorker", validator.title || "Validation");
  if (pipelineInspectorBadge) pipelineInspectorBadge.textContent = "Validator";
  if (pipelineInspectorState) pipelineInspectorState.textContent = titleCasePipelineStatus(status);
  if (pipelineValidationTitleInput) pipelineValidationTitleInput.value = validator.title || "";
  if (pipelineValidationStatusSelect) pipelineValidationStatusSelect.value = status;
  if (pipelineValidationTierSelect) pipelineValidationTierSelect.value = validator.tier || pipelineStudioState?.pipeline?.validation?.tier || "smoke-plus";
  if (pipelineValidationModeSelect) pipelineValidationModeSelect.value = mode;
  if (pipelineValidationSummaryInput) pipelineValidationSummaryInput.value = validator.summary || "";
  if (pipelineValidationCommandsInput) pipelineValidationCommandsInput.value = pipelineLinesToText(validator.commands);
  if (pipelineValidationEvidenceInput) pipelineValidationEvidenceInput.value = pipelineLinesToText(validator.evidence || validator.path || validator.receipt);
  if (pipelineValidationGatesInput) pipelineValidationGatesInput.value = pipelineLinesToText(validator.gates);
  if (pipelineValidationSchemaInput) pipelineValidationSchemaInput.value = pipelineLinesToText(validator.schema_paths);
  if (pipelineValidationBlockingCheckbox) pipelineValidationBlockingCheckbox.checked = validator.blocking !== false;
  if (pipelineValidationConfigPath) pipelineValidationConfigPath.textContent = validator.config ? `Config: ${validator.config}` : "Config output pending";
  if (pipelineValidationReceiptPath) pipelineValidationReceiptPath.textContent = validator.receipt ? `Receipt: ${validator.receipt}` : validator.path ? `Receipt: ${validator.path}` : "Receipt output pending";
  if (pipelineValidationInspectorStatus) pipelineValidationInspectorStatus.textContent = message || "Configure the validation lane, then save outputs.";
  renderPipelineValidationTypedEditors(validator);
  renderPipelineValidationConsultation();
  updatePipelineValidationModeButtons(mode);
  renderPipelineInputCards(pipelineStudioState?.pipeline?.input_cards || selectedPipelinePayloadTemplate()?.required_inputs || selectedPipelineStudioTemplate()?.requiredInputs || []);
  renderPipelineIntegrationCards(pipelineStudioState?.pipeline?.integration || []);
  renderPipelineValidatorCards(pipelineStudioState?.pipeline?.validators || selectedPipelinePayloadTemplate()?.validators || []);
  syncPipelineWorkerCards(pipelineStudioState?.pipeline?.workers || selectedPipelineStudioTemplate()?.workers || []);
}

function collectPipelineValidationConfig() {
  const selected = selectedPipelineValidator();
  syncValidationRowsToTextareas();
  ensureValidationIntegrationGate();
  return {
    id: pipelineSelectedValidationId,
    title: pipelineValidationTitleInput?.value?.trim() || selected?.title || "Validator",
    status: pipelineValidationStatusSelect?.value || "configured",
    tier: pipelineValidationTierSelect?.value || pipelineStudioState?.pipeline?.validation?.tier || "smoke-plus",
    mode: pipelineValidationModeSelect?.value || "commands",
    summary: pipelineValidationSummaryInput?.value?.trim() || "",
    commands: pipelineTextToLines(pipelineValidationCommandsInput?.value || ""),
    evidence: pipelineTextToLines(pipelineValidationEvidenceInput?.value || ""),
    gates: pipelineTextToLines(pipelineValidationGatesInput?.value || ""),
    schema_paths: pipelineTextToLines(pipelineValidationSchemaInput?.value || ""),
    blocking: Boolean(pipelineValidationBlockingCheckbox?.checked),
    receipt: selected?.receipt || "",
    config_path: selected?.config?.replace(/^.*workspace\/runs\/dev-pipeline-studio\/docs-pages\/latest\//, "") || ""
  };
}

async function savePipelineSelectedValidation() {
  if (!pipelineSelectedValidationId) return;
  const validationConfig = collectPipelineValidationConfig();
  if (pipelineValidationInspectorStatus) pipelineValidationInspectorStatus.textContent = "Saving validation outputs...";
  const payload = await savePipelineDraft("save_validation", { includeManifest: false, validationConfig });
  if (payload) {
    showPipelineValidationInspector(pipelineSelectedValidationId, `Saved ${validationConfig.title}.`);
  }
}

function populatePipelineEditor() {
  const project = selectedPipelinePayloadProject();
  const template = selectedPipelinePayloadTemplate();
  const inspector = pipelineStudioState?.pipeline?.inspector || {};
  if (pipelineProjectLabelInput) pipelineProjectLabelInput.value = project?.label || "";
  if (pipelineTemplateLabelInput) pipelineTemplateLabelInput.value = template?.label || "";
  if (pipelineTemplateDetailInput) pipelineTemplateDetailInput.value = template?.detail || "";
  if (pipelineExecutionModelSelect) pipelineExecutionModelSelect.value = template?.execution_model || pipelineStudioState?.pipeline?.execution_model || "ordered";
  if (pipelineValidationTierInput) pipelineValidationTierInput.value = template?.validation_tier || pipelineStudioState?.pipeline?.validation?.tier || "";
  if (pipelineRiskSelect) pipelineRiskSelect.value = template?.risk || inspector.summary?.risk_level || "medium";
  if (pipelineBudgetCapInput) pipelineBudgetCapInput.value = template?.budget_cap_usd ?? "";
  if (pipelineReadPathsInput) pipelineReadPathsInput.value = Array.isArray(project?.read_paths) ? project.read_paths.join("\n") : "";
  renderPipelineRequiredInputsEditor(template?.required_inputs || []);
  const manifestText = JSON.stringify(inspector.manifest || {}, null, 2);
  if (pipelineManifestEditor) pipelineManifestEditor.value = manifestText;
  if (pipelineManifestCode) pipelineManifestCode.textContent = manifestText;
  setPipelineSaveStatus("Loaded from pipeline manifest");
  setPipelineManifestStatus(inspector.manifest_path ? `Editing ${inspector.manifest_path}` : "Worker manifest synthesized from template");
}

function syncPipelineWorkerCards(workers) {
  const cards = document.querySelectorAll(".pipelineCard.worker");
  cards.forEach((card, index) => {
    const worker = workers[index];
    if (!worker) {
      card.removeAttribute("data-worker-id");
      card.classList.remove("selected");
      return;
    }
    card.dataset.workerId = worker.id || "";
    card.classList.toggle("selected", Boolean(worker.selected));
    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");
    card.setAttribute("aria-pressed", String(Boolean(worker.selected)));
  });
}

function parsePipelineManifestEditor() {
  if (!pipelineManifestEditor) return null;
  const raw = pipelineManifestEditor.value.trim();
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch (error) {
    setPipelineManifestStatus(`Invalid worker manifest JSON: ${error.message}`, true);
    throw error;
  }
}

function pipelineEditorPayload(action = "save", options = {}) {
  const project = selectedPipelinePayloadProject();
  const template = selectedPipelinePayloadTemplate();
  const includeManifest = options.includeManifest !== false;
  const workerManifest = includeManifest ? parsePipelineManifestEditor() : null;
  const selectedWorker = options.workerId || workerManifest?.task_id || template?.selected_worker || pipelineStudioState?.pipeline?.workers?.find((worker) => worker.selected)?.id || "";
  const payload = {
    action,
    project_id: pipelineStudioState?.selected?.project_id || pipelineProjectSelect?.value || "",
    template_id: pipelineStudioState?.selected?.template_id || pipelineTemplateSelect?.value || "",
    worker_id: options.workerId || "",
    project: {
      label: pipelineProjectLabelInput?.value || project?.label || "",
      surface: pipelineSurfaceSelect?.selectedOptions?.[0]?.textContent || project?.surface || "",
      surface_value: pipelineSurfaceSelect?.value || project?.surface_value || "",
      owned_root: project?.owned_root || "",
      read_paths_text: pipelineReadPathsInput?.value || ""
    },
    template: {
      label: pipelineTemplateLabelInput?.value || template?.label || "",
      detail: pipelineTemplateDetailInput?.value || template?.detail || "",
      description: template?.description || "",
      tagline: template?.tagline || "",
      validation_tier: pipelineValidationTierInput?.value || template?.validation_tier || "",
      risk: pipelineRiskSelect?.value || template?.risk || "",
      budget_spent_usd: template?.budget_spent_usd ?? 0,
      budget_cap_usd: pipelineBudgetCapInput?.value || template?.budget_cap_usd || 0,
      execution_model: pipelineExecutionModelSelect?.value || template?.execution_model || "ordered",
      worker_stage_label: (pipelineExecutionModelSelect?.value || template?.execution_model) === "ordered" ? "2. Task Execution" : "2. Workers (Parallel)",
      selected_worker: selectedWorker,
      required_inputs: collectPipelineRequiredInputs()
    },
    worker_manifest: workerManifest
  };
  if (options.validationConfig) payload.validation_config = options.validationConfig;
  if (options.integrationConfig) payload.integration_config = options.integrationConfig;
  return payload;
}

async function savePipelineDraft(action = "save", options = {}) {
  if (!pipelineProjectSelect || !pipelineTemplateSelect) return null;
  try {
    setPipelineSaveStatus(action === "select_worker" ? "Selecting worker..." : action === "save_integration" ? "Saving integration outputs..." : action === "save_validation" ? "Saving validation outputs..." : "Saving pipeline draft...");
    const response = await fetch(`${API_BASE}/dev-pipeline-studio`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(pipelineEditorPayload(action, options))
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    normalizePipelineState(payload);
    applyPipelineStudioContext();
    const verb = action === "duplicate" ? "Duplicated" : action === "new" ? "Created" : action === "select_worker" ? "Selected" : action === "save_integration" ? "Saved integration" : action === "save_validation" ? "Saved validation" : "Saved";
    setPipelineSaveStatus(`${verb} ${payload.selected?.template_id || "pipeline"} at ${new Date().toLocaleTimeString()}`);
    return payload;
  } catch (error) {
    setPipelineSaveStatus(`Save failed: ${error.message}`, true);
    return null;
  }
}

function applyPipelineStudioContext() {
  if (pipelineStudioState?.pipeline) {
    const pipeline = pipelineStudioState.pipeline;
    const inspector = pipeline.inspector || {};
    const summary = inspector.summary || {};
    setPipelineField("status", pipeline.status || "Unknown");
    setPipelineField("statusDetail", pipeline.status_detail || "");
    setPipelineField("project", pipeline.project || "");
    setPipelineField("surface", pipeline.surface || "");
    setPipelineField("template", pipeline.template || "");
    setPipelineField("templateDetail", pipeline.template_detail || "");
    setPipelineField("tasks", pipeline.tasks || "");
    setPipelineField("taskState", pipeline.task_state || "");
    setPipelineField("budget", pipeline.budget || "");
    setPipelineField("budgetDetail", pipeline.budget_detail || "");
    setPipelineField("runName", pipeline.run_name || "");
    setPipelineField("inputCount", pipeline.input_count || "");
    setPipelineField("workerStageLabel", pipeline.worker_stage_label || "2. Workers (Parallel)");
    setPipelineField("workerCount", pipeline.worker_count || "");
    setPipelineField("integrationCount", pipeline.integration_count || "");
    setPipelineField("selectedWorker", inspector.selected_worker || "");
    setPipelineField("ownedPathCount", summary.owned_paths || "");
    setPipelineField("readPathCount", summary.read_paths || "");
    setPipelineField("validationTier", summary.validation_tier || pipeline.validation?.tier || "");
    setPipelineField("riskLevel", summary.risk_level || "");
    renderPipelineInputCards(pipeline.input_cards || []);
    renderPipelineIntegrationCards(pipeline.integration || []);
    renderPipelineValidatorCards(pipeline.validators || []);
    renderPipelineCards("data-pipeline-input", pipeline.input_cards || [], [["title", "title"], ["file", "file"], ["status", "status"]]);
    renderPipelineCards("data-pipeline-worker", pipeline.workers || [], [["title", "title"], ["file", "detail"]]);
    renderPipelineCards("data-pipeline-integrate", pipeline.integration || [], [["title", "title"]]);
    renderPipelineCards("data-pipeline-validator", pipeline.validators || [], [["title", "title"], ["file", "file"], ["status", "status"]]);
    renderPipelineCards("data-pipeline-evidence", pipeline.evidence || [], [["title", "title"], ["file", "file"], ["status", "status"]]);
    if (pipelineManifestCode) {
      pipelineManifestCode.textContent = JSON.stringify(inspector.manifest || {}, null, 2);
    }
    populatePipelineEditor();
    syncPipelineWorkerCards(pipeline.workers || []);
    if (pipelineSelectedIntegrationId) {
      showPipelineIntegrationInspector(pipelineSelectedIntegrationId);
    } else if (pipelineSelectedValidationId) {
      showPipelineValidationInspector(pipelineSelectedValidationId);
    } else if (pipelineSelectedInputId) {
      showPipelineInputInspector(pipelineSelectedInputId);
    } else {
      showPipelineWorkerInspector();
    }
    pipelineTemplateCards.forEach((card) => {
      const isActive = card.dataset.templateCard === (pipelineStudioState.selected?.template_id || "");
      card.classList.toggle("active", isActive);
      card.setAttribute("aria-pressed", String(isActive));
    });
    return;
  }
  if (!pipelineProjectSelect || !pipelineTemplateSelect) return;
  const project = selectedPipelineStudioProject();
  const template = selectedPipelineStudioTemplate();
  const selectedWorker = template.workers[template.selectedIndex] || template.workers[0];
  const workerFiles = template.workers.map((worker) => worker.file);
  const runName = `${template.slug}-${project.key}_2026-05-02_120501`;
  const readPaths = [...project.readPaths, `templates/pipelines/${template.id}.json`];
  const manifest = {
    schema_version: "cento.worker_manifest.v1",
    id: `${selectedWorker.id}_worker_01`,
    project: project.key,
    template_id: template.id,
    type: template.workerType,
    task_id: selectedWorker.id,
    description: `${selectedWorker.description} for ${project.name} using the ${template.label} template`,
    owned_paths: [`${project.ownedRoot}/${selectedWorker.file}`],
    read_paths: readPaths,
    dependencies: [],
    acceptance: [
      `${template.label} output is valid`,
      "Template parameters are preserved",
      "Only owned paths changed"
    ],
    validation: {
      tier: template.validationTier
    }
  };

  if (pipelineSurfaceSelect) pipelineSurfaceSelect.value = project.surfaceValue;
  setPipelineField("project", project.name);
  setPipelineField("surface", project.surface);
  setPipelineField("template", template.label);
  setPipelineField("templateDetail", template.detail);
  setPipelineField("tasks", template.tasks);
  setPipelineField("taskState", "Template ready");
  setPipelineField("budget", template.budget);
  setPipelineField("budgetDetail", template.budgetDetail);
  setPipelineField("runName", runName);
  setPipelineField("inputCount", `${(template.requiredInputs || []).length} inputs`);
  setPipelineField("workerStageLabel", template.workerStageLabel || "2. Workers (Parallel)");
  setPipelineField("workerCount", `${template.workers.length} workers`);
  setPipelineField("integrationCount", `${template.workers.length} integration steps`);
  setPipelineField("selectedWorker", selectedWorker.title);
  setPipelineField("ownedPathCount", "1 path");
  setPipelineField("readPathCount", `${readPaths.length} paths`);
  setPipelineField("validationTier", template.validationTier);
  setPipelineField("riskLevel", template.risk);
  updateIndexedPipelineText("data-pipeline-worker-title", template.workers.map((worker) => worker.title));
  updateIndexedPipelineText("data-pipeline-worker-file", workerFiles);
  updateIndexedPipelineText("data-pipeline-integrate-title", workerFiles.map((file) => `Integrate: ${file}`));
  renderPipelineIntegrationCards(template.workers.map((worker) => ({
    id: worker.id,
    title: `Integrate: ${worker.file}`,
    file: "integration_receipt.json",
    status: "Accepted",
    dependencies: worker.dependencies || [],
    artifacts: [`${project.ownedRoot}/${worker.file}`],
    gates: ["Dependencies integrated first", "No owned-path conflict", "Receipt written before validation starts"],
    rollback_plan: ["Reject this integration step and preserve worker artifact for retry"],
    mode: "dependency-order"
  })));
  renderPipelineInputCards(template.requiredInputs || []);
  renderPipelineValidatorCards(template.validators || []);
  if (pipelineManifestCode) {
    pipelineManifestCode.textContent = JSON.stringify(manifest, null, 2);
  }
  if (pipelineManifestEditor) pipelineManifestEditor.value = JSON.stringify(manifest, null, 2);
  syncPipelineWorkerCards(template.workers || []);
  showPipelineWorkerInspector();
  pipelineTemplateCards.forEach((card) => {
    const isActive = card.dataset.templateCard === template.id;
    card.classList.toggle("active", isActive);
    card.setAttribute("aria-pressed", String(isActive));
  });
}

async function loadPipelineStudioState() {
  if (!pipelineProjectSelect || !pipelineTemplateSelect) {
    applyPipelineStudioContext();
    return;
  }
  const project = pipelineProjectSelect.value || "generic-easy-medium-task";
  const template = pipelineTemplateSelect.value || "generic-task";
  try {
    const payload = await apiGetJson(`${API_BASE}/dev-pipeline-studio?project=${encodeURIComponent(project)}&template=${encodeURIComponent(template)}`);
    normalizePipelineState(payload);
    applyPipelineStudioContext();
  } catch (error) {
    console.warn("Dev Pipeline Studio backend unavailable; using local fallback.", error);
    pipelineStudioState = null;
    applyPipelineStudioContext();
  }
}

function initPipelineStudioControls() {
  if (pipelineStudioControlsInitialized || !pipelineProjectSelect || !pipelineTemplateSelect) return;
  pipelineProjectSelect.addEventListener("change", () => {
    pipelineSelectedInputId = "";
    pipelineSelectedIntegrationId = "";
    pipelineSelectedValidationId = "";
    void loadPipelineStudioState();
  });
  pipelineTemplateSelect.addEventListener("change", () => {
    pipelineSelectedInputId = "";
    pipelineSelectedIntegrationId = "";
    pipelineSelectedValidationId = "";
    void loadPipelineStudioState();
  });
  if (pipelineTemplateLibrary) {
    pipelineTemplateLibrary.addEventListener("click", (event) => {
      const card = event.target.closest("[data-template-card]");
      if (!card || !pipelineTemplateSelect) return;
      pipelineTemplateSelect.value = card.dataset.templateCard || "generic-task";
      pipelineSelectedInputId = "";
      pipelineSelectedIntegrationId = "";
      pipelineSelectedValidationId = "";
      void loadPipelineStudioState();
    });
  }
  if (pipelineSaveDraftButton) {
    pipelineSaveDraftButton.addEventListener("click", () => {
      void savePipelineDraft("save");
    });
  }
  if (pipelineDuplicateButton) {
    pipelineDuplicateButton.addEventListener("click", () => {
      void savePipelineDraft("duplicate");
    });
  }
  if (pipelineNewTemplateButton) {
    pipelineNewTemplateButton.addEventListener("click", () => {
      void savePipelineDraft("new");
    });
  }
  if (pipelineInspectorNav) {
    pipelineInspectorNav.addEventListener("click", (event) => {
      const link = event.target.closest("a[data-inspector-tab]");
      if (!link) return;
      event.preventDefault();
      setInspectorTab(link.dataset.inspectorTab || "manifest");
    });
  }
  const logsCopyButton = document.querySelector("#logsCopyButton");
  if (logsCopyButton) {
    logsCopyButton.addEventListener("click", () => {
      const scroll = document.querySelector("#logsScroll");
      if (!scroll) return;
      const text = Array.from(scroll.querySelectorAll(".logEntry")).map((el) => {
        const time = el.querySelector("time")?.textContent || "";
        const msg = el.querySelector("span")?.textContent || "";
        return `[${time}] ${msg}`;
      }).join("\n");
      navigator.clipboard?.writeText(text).catch(() => {});
    });
  }
  if (pipelineFormatManifestButton) {
    pipelineFormatManifestButton.addEventListener("click", () => {
      try {
        const manifest = parsePipelineManifestEditor();
        if (pipelineManifestEditor) pipelineManifestEditor.value = JSON.stringify(manifest || {}, null, 2);
        setPipelineManifestStatus("Worker manifest formatted");
      } catch (error) {
        setPipelineManifestStatus(`Format failed: ${error.message}`, true);
      }
    });
  }
  if (pipelineAddInputButton) {
    pipelineAddInputButton.addEventListener("click", () => {
      const current = collectPipelineRequiredInputs();
      current.push({ id: `input-${current.length + 1}`, title: "New input", detail: "", kind: "text", input_type: "text", status: "missing", required: true, format: "plain text" });
      renderPipelineRequiredInputsEditor(current);
    });
  }
  if (pipelineInputSaveButton) {
    pipelineInputSaveButton.addEventListener("click", () => {
      void savePipelineSelectedInput();
    });
  }
  if (pipelineInputTypeSelect) {
    pipelineInputTypeSelect.addEventListener("change", () => {
      updatePipelineInputTypeEditors(pipelineInputTypeSelect.value || "text");
    });
  }
  if (pipelineValidationSaveButton) {
    pipelineValidationSaveButton.addEventListener("click", () => {
      void savePipelineSelectedValidation();
    });
  }
  if (pipelineIntegrationSaveButton) {
    pipelineIntegrationSaveButton.addEventListener("click", () => {
      void savePipelineSelectedIntegration();
    });
  }
  document.querySelectorAll("[data-integration-view]").forEach((button) => {
    button.addEventListener("click", () => {
      updatePipelineIntegrationView(button.dataset.integrationView || "order");
    });
  });
  if (pipelineValidationModeSelect) {
    pipelineValidationModeSelect.addEventListener("change", () => {
      updatePipelineValidationModeButtons(pipelineValidationModeSelect.value || "commands");
    });
  }
  document.querySelectorAll("[data-validation-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      const mode = button.dataset.validationMode || "commands";
      if (pipelineValidationModeSelect) pipelineValidationModeSelect.value = mode;
      updatePipelineValidationModeButtons(mode);
    });
  });
  if (pipelineValidationAddCommandButton) {
    pipelineValidationAddCommandButton.addEventListener("click", () => {
      addPipelineValidationRow("commands", "python3 -m json.tool workspace/runs/dev-pipeline-studio/docs-pages/latest/pipeline_manifest.json");
      syncValidationRowsToTextareas();
    });
  }
  if (pipelineValidationAddEvidenceButton) {
    pipelineValidationAddEvidenceButton.addEventListener("click", () => {
      addPipelineValidationRow("evidence", "validation/validator_manifest.json");
      syncValidationRowsToTextareas();
    });
  }
  if (pipelineValidationAddGateButton) {
    pipelineValidationAddGateButton.addEventListener("click", () => {
      addPipelineValidationRow("gates", "Blocking validator prevents handoff until resolved");
      syncValidationRowsToTextareas();
    });
  }
  if (pipelineValidationAddSchemaButton) {
    pipelineValidationAddSchemaButton.addEventListener("click", () => {
      addPipelineValidationRow("schema", "integration/integration_lane.json");
      syncValidationRowsToTextareas();
    });
  }
  [
    [pipelineValidationCommandsInput, "commands"],
    [pipelineValidationEvidenceInput, "evidence"],
    [pipelineValidationGatesInput, "gates"],
    [pipelineValidationSchemaInput, "schema"]
  ].forEach(([textarea, kind]) => {
    textarea?.addEventListener("input", () => syncValidationTextareaToRows(kind));
  });
  document.querySelector(".pipelineValidationTypedEditors")?.addEventListener("click", (event) => {
    const removeButton = event.target.closest("[data-validation-row-remove]");
    if (!removeButton) return;
    removeButton.closest(".pipelineValidationRow")?.remove();
    syncValidationRowsToTextareas();
  });
  document.querySelector(".pipelineValidationTypedEditors")?.addEventListener("input", () => {
    syncValidationRowsToTextareas();
  });
  if (pipelineValidationUseIntegrationButton) {
    pipelineValidationUseIntegrationButton.addEventListener("click", () => {
      importPipelineIntegrationContext(pipelineStudioState?.pipeline?.integration || []);
    });
  }
  if (pipelineValidationIntegrationContext) {
    pipelineValidationIntegrationContext.addEventListener("click", (event) => {
      const button = event.target.closest("[data-import-integration-step]");
      if (!button) return;
      const index = Number.parseInt(button.dataset.importIntegrationStep || "0", 10);
      const step = (pipelineStudioState?.pipeline?.integration || [])[index];
      if (step) importPipelineIntegrationContext([step]);
    });
  }
  if (pipelineRequiredInputsEditor) {
    pipelineRequiredInputsEditor.addEventListener("click", (event) => {
      const removeButton = event.target.closest("[data-remove-input]");
      if (!removeButton) return;
      removeButton.closest("[data-input-row]")?.remove();
    });
  }
  document.querySelector(".pipelineStageGrid")?.addEventListener("click", (event) => {
    const inputCard = event.target.closest(".pipelineCard.operatorInput");
    const inputId = inputCard?.dataset?.inputId || "";
    if (inputId) {
      showPipelineInputInspector(inputId);
      return;
    }
    const integrationCard = event.target.closest(".pipelineCard.receipt");
    const integrationId = integrationCard?.dataset?.integrationId || "";
    if (integrationId) {
      showPipelineIntegrationInspector(integrationId);
      return;
    }
    const validatorCard = event.target.closest(".pipelineCard.validator");
    const validatorId = validatorCard?.dataset?.validatorId || "";
    if (validatorId) {
      showPipelineValidationInspector(validatorId);
      return;
    }
    const card = event.target.closest(".pipelineCard.worker");
    const workerId = card?.dataset?.workerId || "";
    if (!workerId) return;
    pipelineSelectedInputId = "";
    showPipelineWorkerInspector();
    void savePipelineDraft("select_worker", { workerId, includeManifest: false });
  });
  document.querySelector(".pipelineStageGrid")?.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const inputCard = event.target.closest(".pipelineCard.operatorInput");
    const inputId = inputCard?.dataset?.inputId || "";
    if (inputId) {
      event.preventDefault();
      showPipelineInputInspector(inputId);
      return;
    }
    const integrationCard = event.target.closest(".pipelineCard.receipt");
    const integrationId = integrationCard?.dataset?.integrationId || "";
    if (integrationId) {
      event.preventDefault();
      showPipelineIntegrationInspector(integrationId);
      return;
    }
    const validatorCard = event.target.closest(".pipelineCard.validator");
    const validatorId = validatorCard?.dataset?.validatorId || "";
    if (validatorId) {
      event.preventDefault();
      showPipelineValidationInspector(validatorId);
      return;
    }
    const card = event.target.closest(".pipelineCard.worker");
    const workerId = card?.dataset?.workerId || "";
    if (!workerId) return;
    event.preventDefault();
    pipelineSelectedInputId = "";
    showPipelineWorkerInspector();
    void savePipelineDraft("select_worker", { workerId, includeManifest: false });
  });
  pipelineStudioControlsInitialized = true;
  void loadPipelineStudioState();
}

function setOptionalHidden(element, isHidden) {
  if (element) element.classList.toggle("hidden", isHidden);
}

function hideSoftwareDeliveryViews() {
  setOptionalHidden(homeView, true);
  setOptionalHidden(softwareDeliveryHubView, true);
  setOptionalHidden(devPipelineStudioView, true);
}

function hideResearchViews() {
  setOptionalHidden(researchView, true);
  setOptionalHidden(codebaseIntelligenceView, true);
}

function routeFromLocation() {
  if (location.pathname === "/") return "home";
  if (location.pathname === "/software-delivery-hub") return "software-delivery";
  if (location.pathname === "/dev-pipeline-studio") return "dev-pipeline-studio";
  if (location.pathname === "/codebase-intelligence") return "codebase-intelligence";
  if (location.pathname === "/review") return "review";
  if (location.pathname === "/cluster") return "cluster";
  if (location.pathname === "/consulting") return "consulting";
  if (location.pathname === "/factory") return "factory";
  if (location.pathname === "/research-center") return "research";
  if (location.pathname === "/docs") return "docs";
  if (location.pathname === "/issues" || location.pathname.startsWith("/issues/")) return "issues";
  return "home";
}

function hasMainRoute(route) {
  return Array.from(mainNavLinks).some((link) => link.dataset.mainRoute === route);
}

function setSdHubRailActive(route) {
  const activeRoute = route === "dev-pipeline-studio" || route === "factory" || route === "software-delivery"
    ? route
    : route === "issues" || route === "review"
      ? "issues"
      : "";
  sdHubRailLinks.forEach((link) => {
    const isActive = link.dataset.sdHubRoute === activeRoute;
    link.classList.toggle("active", isActive);
    if (isActive) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  });
}

function setResearchRailActive(route) {
  const activeRoute = route === "codebase-intelligence" ? "codebase-intelligence" : route === "research" ? "research" : "";
  researchRailLinks.forEach((link) => {
    const isActive = link.dataset.researchRoute === activeRoute;
    link.classList.toggle("active", isActive);
    if (isActive) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  });
}

function setNavActive(route) {
  const activeRoute = route || routeFromLocation();
  let activeMain = "taskstream";
  if (activeRoute === "home") {
    activeMain = homeView ? "home" : "taskstream";
  } else if (activeRoute === "software-delivery" || activeRoute === "factory" || activeRoute === "issues" || activeRoute === "dev-pipeline-studio") {
    activeMain = softwareDeliveryHubView ? "software-delivery" : activeRoute === "factory" ? "factory" : "taskstream";
  } else if (activeRoute === "review") {
    activeMain = hasMainRoute("review") ? "review" : "taskstream";
  } else if (activeRoute === "codebase-intelligence") {
    activeMain = "research";
  } else if (["cluster", "consulting", "docs", "research"].includes(activeRoute)) {
    activeMain = activeRoute;
  }
  mainNavLinks.forEach((link) => {
    link.classList.toggle("active", link.dataset.mainRoute === activeMain);
  });
  primaryNavLinks.forEach((link) => {
    link.classList.toggle("active", link.dataset.navRoute === activeRoute);
  });
  if (taskstreamNav) taskstreamNav.classList.toggle("hidden", activeMain !== "taskstream");
  document.body.classList.toggle("homeMode", activeMain === "home");
  document.body.classList.toggle("softwareDeliveryMode", activeMain === "software-delivery");
  document.body.classList.toggle("docsMode", activeMain === "docs");
  document.body.classList.toggle("researchMode", activeMain === "research");
  document.body.classList.toggle("codebaseMode", activeRoute === "codebase-intelligence");
  setSdHubRailActive(activeMain === "software-delivery" ? activeRoute : "");
  setResearchRailActive(activeMain === "research" ? activeRoute : "");
  if (activeMain !== "docs") {
    document.body.classList.remove("docsAppPage");
    document.body.classList.remove("docsPipelinePage");
    document.body.classList.remove("docsParallelPage");
  }
}

function syncDocsHashNavigation(options = {}) {
  if (!docsHashLinks.length) return;
  const activeHash = location.hash || "#overview";
  const isKanjiAppPage = activeHash.startsWith("#kanji");
  const isParallelPage = activeHash.startsWith("#parallel");
  const isPipelinePage = activeHash.startsWith("#pipeline-");
  const activePipelineSidebarHash = activeHash.startsWith("#pipeline-input-")
    ? "#pipeline-studio-input-docs"
    : activeHash;
  document.body.classList.toggle("docsAppPage", isKanjiAppPage);
  document.body.classList.toggle("docsPipelinePage", isPipelinePage);
  document.body.classList.toggle("docsParallelPage", isParallelPage);
  docsHashLinks.forEach((link) => {
    const href = link.getAttribute("href") || "";
    const isSidebarKanjiParent = href === "#kanji-a-day" && link.classList.contains("docsAppParentLink");
    const isSidebarParallelParent = href === "#parallel-execution" && link.classList.contains("docsParallelParentLink");
    const isParallelParentActive = isSidebarParallelParent && isParallelPage;
    const isPipelineSubsectionActive = isPipelinePage && href === activePipelineSidebarHash;
    link.classList.toggle("active", (href === activeHash && !isSidebarKanjiParent) || isParallelParentActive || isPipelineSubsectionActive);
  });
  if (options.scrollToHash && (isKanjiAppPage || isPipelinePage || isParallelPage)) {
    window.requestAnimationFrame(() => {
      const target = document.querySelector(activeHash);
      if (target) target.scrollIntoView({ block: "start" });
    });
  }
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
  hideSoftwareDeliveryViews();
  listView.classList.add("hidden");
  detailView.classList.add("hidden");
  clusterView.classList.add("hidden");
  consultingView.classList.add("hidden");
  factoryView.classList.add("hidden");
  docsView.classList.add("hidden");
  hideResearchViews();
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
  document.body.classList.remove("studioMode");
  hideSoftwareDeliveryViews();
  listView.classList.add("hidden");
  reviewView.classList.add("hidden");
  clusterView.classList.add("hidden");
  consultingView.classList.add("hidden");
  factoryView.classList.add("hidden");
  docsView.classList.add("hidden");
  hideResearchViews();
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
  document.body.classList.remove("studioMode");
  hideSoftwareDeliveryViews();
  reviewView.classList.add("hidden");
  detailView.classList.add("hidden");
  clusterView.classList.add("hidden");
  consultingView.classList.add("hidden");
  factoryView.classList.add("hidden");
  docsView.classList.add("hidden");
  hideResearchViews();
  listView.classList.remove("hidden");
  setLocationFromState();
  void withSpinner(loadIssues());
}

function showHome() {
  if (!homeView) {
    showList();
    return;
  }
  setNavActive("home");
  document.body.classList.remove("reviewMode");
  document.body.classList.remove("studioMode");
  setOptionalHidden(homeView, false);
  setOptionalHidden(softwareDeliveryHubView, true);
  setOptionalHidden(devPipelineStudioView, true);
  reviewView.classList.add("hidden");
  detailView.classList.add("hidden");
  listView.classList.add("hidden");
  clusterView.classList.add("hidden");
  consultingView.classList.add("hidden");
  factoryView.classList.add("hidden");
  docsView.classList.add("hidden");
  hideResearchViews();
  history.replaceState(null, "", "/");
}

function showSoftwareDeliveryHub() {
  if (!softwareDeliveryHubView) {
    showCentoSection("factory");
    return;
  }
  if (location.hash === "#dev-pipeline-studio") {
    history.replaceState(null, "", "/dev-pipeline-studio");
    showDevPipelineStudio();
    return;
  }
  setNavActive("software-delivery");
  document.body.classList.remove("reviewMode");
  document.body.classList.remove("studioMode");
  softwareDeliveryHubView.querySelectorAll('.hubSidebar a').forEach((a) => {
    a.classList.toggle('active', a.getAttribute('href') === '/software-delivery-hub');
  });
  setOptionalHidden(homeView, true);
  setOptionalHidden(softwareDeliveryHubView, false);
  setOptionalHidden(devPipelineStudioView, true);
  reviewView.classList.add("hidden");
  detailView.classList.add("hidden");
  listView.classList.add("hidden");
  clusterView.classList.add("hidden");
  consultingView.classList.add("hidden");
  factoryView.classList.add("hidden");
  docsView.classList.add("hidden");
  hideResearchViews();
  history.replaceState(null, "", "/software-delivery-hub");
}

function showDevPipelineStudio() {
  if (!softwareDeliveryHubView || !devPipelineStudioView) {
    showSoftwareDeliveryHub();
    return;
  }
  setNavActive("dev-pipeline-studio");
  document.body.classList.remove("reviewMode");
  document.body.classList.add("studioMode");
  softwareDeliveryHubView.querySelectorAll('.hubSidebar a').forEach((a) => {
    a.classList.toggle('active', a.getAttribute('href') === '/dev-pipeline-studio');
  });
  setOptionalHidden(homeView, true);
  setOptionalHidden(softwareDeliveryHubView, false);
  setOptionalHidden(devPipelineStudioView, false);
  reviewView.classList.add("hidden");
  detailView.classList.add("hidden");
  listView.classList.add("hidden");
  clusterView.classList.add("hidden");
  consultingView.classList.add("hidden");
  factoryView.classList.add("hidden");
  docsView.classList.add("hidden");
  hideResearchViews();
  const pipelineControlsAlreadyReady = pipelineStudioControlsInitialized;
  initPipelineStudioControls();
  if (pipelineControlsAlreadyReady) void loadPipelineStudioState();
  const hash = location.hash;
  history.replaceState(null, "", `/dev-pipeline-studio${hash}`);
  if (hash) {
    window.requestAnimationFrame(() => {
      const target = document.querySelector(hash);
      if (target) target.scrollIntoView({ block: "start" });
    });
  } else {
    window.scrollTo({ top: 0, left: 0 });
  }
}

function ciCompactNumber(value) {
  const number = Number(value || 0);
  if (!Number.isFinite(number)) return "--";
  if (number >= 1000) return `${(number / 1000).toFixed(number >= 10000 ? 0 : 1)}k`;
  return String(number);
}

function setCiText(selector, value) {
  document.querySelectorAll(selector).forEach((element) => {
    element.textContent = value;
  });
}

function setCiHealth(name, pct, label) {
  const normalized = Math.max(0, Math.min(100, Number(pct || 0)));
  document.querySelectorAll(`[data-ci-health="${name}"]`).forEach((element) => {
    element.style.width = `${normalized}%`;
  });
  setCiText(`[data-ci-health-label="${name}"]`, label || `${normalized}%`);
}

function renderCodebaseInventory(payload) {
  if (!payload) return;
  const health = payload.health || {};
  const graph = payload.graph || {};
  const capabilities = Array.isArray(payload.capabilities) ? payload.capabilities : [];
  const routes = Array.isArray(payload.routes) ? payload.routes : [];
  const datastores = Array.isArray(payload.datastores) ? payload.datastores : [];
  const uncategorized = Array.isArray(health.uncategorized_files) ? health.uncategorized_files.length : 0;
  const routeHealth = Math.min(100, routes.length * 8);
  const testHealth = Math.min(100, (Number(health.test_file_count || 0) / Math.max(1, Number(health.script_count || 1))) * 100);

  setCiText('[data-ci-metric="scriptCount"]', `${ciCompactNumber(health.script_count)} scripts indexed`);
  setCiText('[data-ci-metric="capabilityCount"]', ciCompactNumber(capabilities.length || graph.nodes?.length));
  setCiText('[data-ci-metric="routeCount"]', ciCompactNumber(routes.length));
  setCiText('[data-ci-metric="dataFileCount"]', ciCompactNumber(health.data_file_count || datastores.length));
  setCiText('[data-ci-metric="testCount"]', ciCompactNumber(health.test_file_count));
  setCiText('[data-ci-metric="lineCount"]', `${ciCompactNumber(health.total_lines)} lines`);
  setCiText("[data-ci-repo-state]", uncategorized ? "Needs map" : "Indexed");

  const repoState = document.querySelector("[data-ci-repo-state]");
  if (repoState) repoState.classList.toggle("clean", uncategorized === 0);
  setCiHealth("docstrings", health.with_docstring_pct || 0);
  setCiHealth("tests", testHealth, `${Math.round(testHealth)}%`);
  setCiHealth("routes", routeHealth, `${routes.length}`);
}

function normalizeInspectorPayload(payload) {
  if (!payload || payload.error) return null;
  const extension = String(payload.extension || "").replace(/^\./, "");
  const language = extension ? extension.toUpperCase() : "File";
  const routes = Array.isArray(codebaseIntelligencePayload?.routes) ? codebaseIntelligencePayload.routes.slice(0, 5) : [];
  const apiRoutes = routes.map((route) => ({
    method: Array.isArray(route.methods) ? route.methods[0] : "GET",
    path: route.prefix || "/",
    label: route.description || route.module || "Route",
  }));
  const debt = Array.isArray(payload.health?.issues) && payload.health.issues.length
    ? payload.health.issues
    : ["No high-risk inspector issues detected for this file."];
  return {
    path: payload.path,
    size_kb: ((Number(payload.size_bytes || 0)) / 1024).toFixed(1),
    loc: payload.lines || 0,
    modified: "Local workspace",
    language,
    purpose: payload.docstring || `Repository file inspected by Codebase Intelligence (${payload.path}).`,
    api_routes: apiRoutes,
    datastore: {
      type: "repository",
      path: payload.path,
    },
    tech_debt: debt,
    ai_assistant: {
      prompt: "Explain this file and its connected routes",
      answer: `This inspector entry summarizes ${payload.path}, including line count, parsed symbols, imports, and local capability mapping.`,
      references: [{ path: payload.path, lines: payload.lines || 1 }],
    },
  };
}

async function loadCodebaseIntelligencePayload() {
  try {
    codebaseIntelligencePayload = await apiGetJson(`${API_BASE}/codebase-intelligence`);
    renderCodebaseInventory(codebaseIntelligencePayload);
  } catch (error) {
    setCiText('[data-ci-metric="scriptCount"]', "Inventory unavailable");
    setCiText('[data-ci-metric="lineCount"]', error.message);
  }
}

async function initCodebaseIntelligence() {
  if (codebaseIntelligenceInitialized) return;
  codebaseIntelligenceInitialized = true;

  if (ciGraphMount && window.CodebaseIntelligenceGraph?.init) {
    ciGraphMount.innerHTML = "";
    window.CodebaseIntelligenceGraph.init(ciGraphMount);
  }

  await loadCodebaseIntelligencePayload();

  if (window.CIpanels) {
    let inspectorPayload = null;
    if (window.CIpanels.loadInspectorData) {
      inspectorPayload = normalizeInspectorPayload(await window.CIpanels.loadInspectorData("scripts/agent_work_app.py"));
    }
    window.CIpanels.mountInspectorPanel?.(ciInspectorMount, inspectorPayload || undefined);
    window.CIpanels.mountAskCentoPanel?.(ciAskMount, {
      context: "Cento repository",
      example_prompt: "Which console routes connect to Agent Work and Factory?",
      answer: "Codebase Intelligence maps registered API routes, local script capabilities, and data stores so route ownership and dependencies stay visible while working in the Research Center.",
      references: [
        { path: "scripts/agent_work_app.py", lines: 2542 },
        { path: "scripts/codebase_intelligence.py", lines: 472 },
        { path: "templates/agent-work-app/app.js", lines: 1 },
      ],
      extra_refs: 2,
    });
  }
}

function showResearchCenter() {
  setNavActive("research");
  document.body.classList.remove("reviewMode");
  document.body.classList.remove("studioMode");
  hideSoftwareDeliveryViews();
  reviewView.classList.add("hidden");
  detailView.classList.add("hidden");
  listView.classList.add("hidden");
  clusterView.classList.add("hidden");
  consultingView.classList.add("hidden");
  factoryView.classList.add("hidden");
  docsView.classList.add("hidden");
  setOptionalHidden(codebaseIntelligenceView, true);
  setOptionalHidden(researchView, false);
  history.replaceState(null, "", `/research-center${location.hash || ""}`);
  if (location.hash) {
    window.requestAnimationFrame(() => {
      const target = document.querySelector(location.hash);
      if (target) target.scrollIntoView({ block: "start" });
    });
  }
}

function showCodebaseIntelligence() {
  if (!codebaseIntelligenceView) {
    showResearchCenter();
    return;
  }
  setNavActive("codebase-intelligence");
  document.body.classList.remove("reviewMode");
  document.body.classList.remove("studioMode");
  hideSoftwareDeliveryViews();
  reviewView.classList.add("hidden");
  detailView.classList.add("hidden");
  listView.classList.add("hidden");
  clusterView.classList.add("hidden");
  consultingView.classList.add("hidden");
  factoryView.classList.add("hidden");
  docsView.classList.add("hidden");
  setOptionalHidden(researchView, true);
  setOptionalHidden(codebaseIntelligenceView, false);
  history.replaceState(null, "", "/codebase-intelligence");
  window.scrollTo({ top: 0, left: 0 });
  void initCodebaseIntelligence().catch((error) => {
    if (ciGraphMount) ciGraphMount.innerHTML = `<div class="ciLoading">${escapeHtml(error.message)}</div>`;
  });
}

function showCentoSection(route) {
  if (route === "research") {
    showResearchCenter();
    return;
  }
  if (route === "codebase-intelligence") {
    showCodebaseIntelligence();
    return;
  }
  setNavActive(route);
  document.body.classList.remove("reviewMode");
  document.body.classList.remove("studioMode");
  hideSoftwareDeliveryViews();
  reviewView.classList.add("hidden");
  detailView.classList.add("hidden");
  listView.classList.add("hidden");
  clusterView.classList.toggle("hidden", route !== "cluster");
  consultingView.classList.toggle("hidden", route !== "consulting");
  factoryView.classList.toggle("hidden", route !== "factory");
  docsView.classList.toggle("hidden", route !== "docs");
  hideResearchViews();
  if (route === "factory") {
    history.replaceState(null, "", "/factory");
    void loadFactory();
    return;
  }
  const hash = route === "docs" ? location.hash : "";
  history.replaceState(null, "", `/${route}${hash}`);
  if (route === "docs") syncDocsHashNavigation({ scrollToHash: true });
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
      const integration = run.integration || {};
      const validation = run.validation || {};
      const preflight = run.preflight || {};
      const queueTasks = Array.isArray(run.queue_tasks) ? run.queue_tasks : [];
      const leases = Array.isArray(run.leases) ? run.leases : [];
      const patches = Array.isArray(run.patch_queue) ? run.patch_queue : [];
      const decision = String(run.decision || "incomplete");
      const statusClassName = decision === "delivered" ? "good" : decision === "approve" ? "good" : "warn";
      const hubLink = run.start_hub
        ? `<a href="${escapeHtml(`/api/artifacts?path=${encodeURIComponent(run.start_hub)}`)}" target="_blank" rel="noreferrer">hub</a>`
        : `<span>hub missing</span>`;
      const mapLink = run.implementation_map
        ? `<a href="${escapeHtml(`/api/artifacts?path=${encodeURIComponent(run.implementation_map)}`)}" target="_blank" rel="noreferrer">map</a>`
        : `<span>map missing</span>`;
      const releaseLink = run.release_packet
        ? `<a href="${escapeHtml(`/api/artifacts?path=${encodeURIComponent(run.release_packet)}`)}" target="_blank" rel="noreferrer">release packet</a>`
        : `<span>release packet pending</span>`;
      const queuePreview = queueTasks
        .slice(0, 4)
        .map((item) => `<li>${escapeHtml(item.task_id || "")}: ${escapeHtml(item.status || "")}</li>`)
        .join("") || `<li>No queue entries yet</li>`;
      const leasePreview = leases
        .slice(0, 3)
        .map((item) => `<li>${escapeHtml(item.task_id || "")}: ${escapeHtml(item.status || "")}</li>`)
        .join("") || `<li>No active leases</li>`;
      const patchPreview = patches
        .slice(0, 4)
        .map((item) => `<li>${escapeHtml(item.task_id || "")}: ${escapeHtml(item.state || item.integration_status || "")}</li>`)
        .join("") || `<li>No patch bundles collected</li>`;
      const appliedPreview = Array.isArray(integration.applied_patches)
        ? integration.applied_patches
            .slice(0, 4)
            .map((item) => `<li>${escapeHtml(item.task_id || "")}: ${escapeHtml((item.changed_files || []).join(", ") || "applied")}</li>`)
            .join("")
        : "";
      const rejectedPreview = Array.isArray(integration.rejected_patches)
        ? integration.rejected_patches
            .slice(0, 4)
            .map((item) => `<li>${escapeHtml(item.task_id || "")}: ${escapeHtml((item.reasons || []).join(", ") || "rejected")}</li>`)
            .join("")
        : "";
      const validationAfterPreview = Array.isArray(integration.validation_after_each)
        ? integration.validation_after_each
            .slice(0, 4)
            .map((item) => `<li>${escapeHtml(item.task_id || "")}: ${escapeHtml(item.decision || "unknown")}</li>`)
            .join("")
        : "";
      const branchLine = integration.branch
        ? `<p><strong>Branch:</strong> ${escapeHtml(integration.branch)}</p><p><strong>Worktree:</strong> ${escapeHtml(integration.worktree || "pending")}</p>`
        : `<p>Integration branch not prepared.</p>`;
      const preflightReason = Array.isArray(preflight.reasons) && preflight.reasons.length ? preflight.reasons[0] : "no blockers";
      const releaseCandidateLink = run.release_candidate
        ? `<a href="${escapeHtml(`/api/artifacts?path=${encodeURIComponent(run.release_candidate)}`)}" target="_blank" rel="noreferrer">release candidate</a>`
        : `<span>release candidate pending</span>`;
      const integrationSummaryLink = run.integration_summary
        ? `<a href="${escapeHtml(`/api/artifacts?path=${encodeURIComponent(run.integration_summary)}`)}" target="_blank" rel="noreferrer">integration summary</a>`
        : "";
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
            <span>${escapeHtml(String(preflight.status || "not_run"))} preflight</span>
            <span>${escapeHtml(String(run.integration_decision || "not_run"))} integration</span>
            <span>${escapeHtml(String(integration.merge_readiness || "not_ready"))} merge readiness</span>
            <span>${escapeHtml(String(run.ai_calls_used || 0))} AI calls</span>
            <span>$${escapeHtml(String(Number(run.estimated_cost_usd || 0).toFixed(2)))} est.</span>
            <span>${escapeHtml(String(Math.round(Number(run.total_duration_ms || 0))))} ms</span>
          </div>
          <div class="factoryRunSections">
            <section class="factoryMiniPanel">
              <h3>Queue</h3>
              <ul>${queuePreview}</ul>
            </section>
            <section class="factoryMiniPanel">
              <h3>Active Leases</h3>
              <ul>${leasePreview}</ul>
            </section>
            <section class="factoryMiniPanel">
              <h3>Patch Queue</h3>
              <ul>${patchPreview}</ul>
            </section>
            <section class="factoryMiniPanel">
              <h3>Integration Dry-Run</h3>
              <p>${escapeHtml(String(integration.candidates || 0))} candidates, ${escapeHtml(String(integration.rejected || 0))} rejected, ${escapeHtml(String(integration.conflicts || 0))} conflicts.</p>
              <p>Release gates: ${escapeHtml(integration.release_gate_status || "pending")}</p>
            </section>
            <section class="factoryMiniPanel">
              <h3>Safe Integrator</h3>
              ${branchLine}
              <p>${escapeHtml(String(integration.applied_count || 0))} applied, ${escapeHtml(String(integration.rejected_count || 0))} rejected.</p>
            </section>
            <section class="factoryMiniPanel">
              <h3>Applied Patches</h3>
              <ul>${appliedPreview || `<li>No applied patches yet</li>`}</ul>
            </section>
            <section class="factoryMiniPanel">
              <h3>Rejected Patches</h3>
              <ul>${rejectedPreview || `<li>No rejected patches</li>`}</ul>
            </section>
            <section class="factoryMiniPanel">
              <h3>Validation After Each</h3>
              <ul>${validationAfterPreview || `<li>No per-patch validation yet</li>`}</ul>
            </section>
            <section class="factoryMiniPanel">
              <h3>Merge Readiness</h3>
              <p>${escapeHtml(integration.merge_readiness || "pending")}</p>
              <p>Blockers: ${escapeHtml(Array.isArray(integration.merge_blockers) && integration.merge_blockers.length ? integration.merge_blockers.join(", ") : "none")}</p>
            </section>
            <section class="factoryMiniPanel">
              <h3>Rollback</h3>
              <p>${escapeHtml(String(integration.rollback_patches || 0))} reverse patch commands ready.</p>
              <p>Registry gate: ${escapeHtml(integration.registry_gate || "pending")}</p>
            </section>
            <section class="factoryMiniPanel">
              <h3>Validation Ladder</h3>
              <p>${escapeHtml(String(validation.passed || 0))}/${escapeHtml(String(validation.checks || 0))} checks passed.</p>
              <p>Preflight: ${escapeHtml(preflightReason)}</p>
            </section>
            <section class="factoryMiniPanel">
              <h3>Cost & Model Usage</h3>
              <p>${escapeHtml(String(run.ai_calls_used || 0))} AI calls used.</p>
              <p>$${escapeHtml(String(Number(run.estimated_cost_usd || 0).toFixed(2)))} estimated cost.</p>
            </section>
          </div>
          <div class="factoryRunLinks">
            <code>${escapeHtml(run.run_dir)}</code>
            ${hubLink}
            ${mapLink}
            ${releaseLink}
            ${releaseCandidateLink}
            ${integrationSummaryLink}
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
  if (location.pathname === "/") {
    showHome();
  } else if (location.pathname === "/software-delivery-hub") {
    showSoftwareDeliveryHub();
  } else if (location.pathname === "/dev-pipeline-studio") {
    showDevPipelineStudio();
  } else if (location.pathname === "/review") {
    showReview();
  } else if (location.pathname === "/cluster") {
    showCentoSection("cluster");
  } else if (location.pathname === "/consulting") {
    showCentoSection("consulting");
  } else if (location.pathname === "/factory") {
    showCentoSection("factory");
  } else if (location.pathname === "/research-center") {
    showResearchCenter();
  } else if (location.pathname === "/codebase-intelligence") {
    showCodebaseIntelligence();
  } else if (location.pathname === "/docs") {
    showCentoSection("docs");
  } else if (match) {
    void showDetail(match[1]).catch(console.error);
  } else if (location.pathname === "/issues") {
    showList();
  } else {
    showHome();
  }
});

window.addEventListener("hashchange", () => syncDocsHashNavigation({ scrollToHash: true }));

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
  if (location.pathname === "/") {
    showHome();
    return;
  }
  if (location.pathname === "/software-delivery-hub") {
    showSoftwareDeliveryHub();
    return;
  }
  if (location.pathname === "/dev-pipeline-studio") {
    showDevPipelineStudio();
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
    showResearchCenter();
    return;
  }
  if (location.pathname === "/codebase-intelligence") {
    showCodebaseIntelligence();
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
  if (location.pathname === "/issues") {
    showList();
    return;
  }
  showHome();
}

initPipelineStudioControls();
void boot();
