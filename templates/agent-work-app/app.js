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
const quickRunPipelineButton = document.querySelector("#quickRunPipelineButton");
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
const pipelineSaveManifestButton = document.querySelector("#pipelineSaveManifestButton");
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
const pipelineInspectorBadge = document.querySelector("#pipelineInspectorBadge");
const pipelineInspectorState = document.querySelector("#pipelineInspectorState");
const pipelineInspectorNav = document.querySelector("#pipelineInspectorNav");
const pipelineInputInspector = document.querySelector("#pipelineInputInspector");
const pipelineInputTitleInput = document.querySelector("#pipelineInputTitleInput");
const pipelineInputTypeSelect = document.querySelector("#pipelineInputTypeSelect");
const pipelineInputSourceSelect = document.querySelector("#pipelineInputSourceSelect");
const pipelineInputDetailInput = document.querySelector("#pipelineInputDetailInput");
const pipelineInputStatusSelect = document.querySelector("#pipelineInputStatusSelect");
const pipelineInputAutomationInput = document.querySelector("#pipelineInputAutomationInput");
const pipelineInputRequiredCheckbox = document.querySelector("#pipelineInputRequiredCheckbox");
const pipelineInputMutedCheckbox = document.querySelector("#pipelineInputMutedCheckbox");
const pipelineInputFormatInput = document.querySelector("#pipelineInputFormatInput");
const pipelineInputImageRefsInput = document.querySelector("#pipelineInputImageRefsInput");
const pipelineInputImageNotesInput = document.querySelector("#pipelineInputImageNotesInput");
const pipelineInputImagePreview = document.querySelector("#pipelineInputImagePreview");
const pipelineInputQuestionsInput = document.querySelector("#pipelineInputQuestionsInput");
const pipelineInputPathsInput = document.querySelector("#pipelineInputPathsInput");
const pipelineInputPathPolicyInput = document.querySelector("#pipelineInputPathPolicyInput");
const pipelineInputArtifactsInput = document.querySelector("#pipelineInputArtifactsInput");
const pipelineInputEvidencePolicyInput = document.querySelector("#pipelineInputEvidencePolicyInput");
const pipelineInputAnswerInput = document.querySelector("#pipelineInputAnswerInput");
const pipelineInputAnswerValuesInput = document.querySelector("#pipelineInputAnswerValuesInput");
const pipelineInputAnswerNotesInput = document.querySelector("#pipelineInputAnswerNotesInput");
const pipelineInputAnswerState = document.querySelector("#pipelineInputAnswerState");
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
const pipelineValidationRunButton = document.querySelector("#pipelineValidationRunButton");
const pipelineValidationRunStatus = document.querySelector("#pipelineValidationRunStatus");
const pipelineValidationRunResults = document.querySelector("#pipelineValidationRunResults");
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
const pipelineEvidenceInspector = document.querySelector("#pipelineEvidenceInspector");
const pipelineEvidenceTitleInput = document.querySelector("#pipelineEvidenceTitleInput");
const pipelineEvidenceStatusSelect = document.querySelector("#pipelineEvidenceStatusSelect");
const pipelineEvidenceKindSelect = document.querySelector("#pipelineEvidenceKindSelect");
const pipelineEvidencePathInput = document.querySelector("#pipelineEvidencePathInput");
const pipelineEvidenceSourcesInput = document.querySelector("#pipelineEvidenceSourcesInput");
const pipelineEvidencePublishInput = document.querySelector("#pipelineEvidencePublishInput");
const pipelineEvidenceRetentionInput = document.querySelector("#pipelineEvidenceRetentionInput");
const pipelineEvidenceNotesInput = document.querySelector("#pipelineEvidenceNotesInput");
const pipelineEvidenceSaveButton = document.querySelector("#pipelineEvidenceSaveButton");
const pipelineEvidenceInspectorStatus = document.querySelector("#pipelineEvidenceInspectorStatus");
const pipelineEvidenceConfigPath = document.querySelector("#pipelineEvidenceConfigPath");
const pipelineEvidenceArtifactPath = document.querySelector("#pipelineEvidenceArtifactPath");
const pipelineEvidenceArtifactPreview = document.querySelector("#pipelineEvidenceArtifactPreview");
const pipelineWorkerInspectorActions = document.querySelector("#pipelineWorkerInspectorActions");
const pipelineContractSummary = document.querySelector("#pipelineContractSummary");
const pipelineContractPanel = document.querySelector("#pipelineContractPanel");
const pipelineArtifactPanel = document.querySelector("#pipelineArtifactPanel");
const pipelineLogsPanel = document.querySelector("#pipelineLogsPanel");
const pipelineCostPanel = document.querySelector("#pipelineCostPanel");
let currentInspectorTab = "manifest";
let currentPipelineTab = "contracts";
let currentPipelineExecutionStageId = "factory";
let currentPipelineExecutionLogFilter = "all";
let currentPipelineExecutionRunId = "";
let pendingRunPipelinePrompt = "";
let currentRunPipelineTemplateId = "";
let pipelineExecutionAnimationTimers = [];
let pipelineExecutionAnimationSignature = "";
let pipelineExecutionPollTimer = null;
let pipelineExecutionPollingActive = false;
let pipelineExecutionVisualTimer = null;
const pipelineExecutionVisualRuns = new Map();
let pipelineExecutionEvidenceLayoutRunId = "";
const manifestExplorerEl = document.querySelector("#manifestExplorer");
const pipelineExecutionPage = document.querySelector("#pipeline-flow.pipelineExecutionPage");
const pipelineExecutionStageStrip = document.querySelector("#pipelineExecutionStageStrip");
const pipelineExecutionTimelineBody = document.querySelector("#pipelineExecutionTimelineBody");
const pipelineExecutionTimelineWindow = document.querySelector("#pipelineExecutionTimelineWindow");
const pipelineExecutionSelectedTitle = document.querySelector("#pipelineExecutionSelectedTitle");
const pipelineExecutionSelectedStatus = document.querySelector("#pipelineExecutionSelectedStatus");
const pipelineExecutionSelectedMeta = document.querySelector("#pipelineExecutionSelectedMeta");
const pipelineExecutionStepTable = document.querySelector("#pipelineExecutionStepTable");
const pipelineExecutionArtifactCount = document.querySelector("#pipelineExecutionArtifactCount");
const pipelineExecutionArtifactFacts = document.querySelector("#pipelineExecutionArtifactFacts");
const pipelineExecutionArtifactList = document.querySelector("#pipelineExecutionArtifactList");
const pipelineExecutionValidationResults = document.querySelector("#pipelineExecutionValidationResults");
const pipelineExecutionLogFilters = document.querySelector("#pipelineExecutionLogFilters");
const pipelineExecutionLogSearch = document.querySelector("#pipelineExecutionLogSearch");
const pipelineExecutionLogRows = document.querySelector("#pipelineExecutionLogRows");
const pipelineExecutionRunButton = document.querySelector("#pipelineExecutionRunButton");
const pipelineExecutionRunsCount = document.querySelector("#pipelineExecutionRunsCount");
const pipelineExecutionRunsList = document.querySelector("#pipelineExecutionRunsList");
const pipelineExecutionLiveBadge = document.querySelector("#pipelineExecutionLiveBadge");
const pipelineExecutionNowStatus = document.querySelector("#pipelineExecutionNowStatus");
const pipelineExecutionNowTitle = document.querySelector("#pipelineExecutionNowTitle");
const pipelineExecutionNowMessage = document.querySelector("#pipelineExecutionNowMessage");
const pipelineExecutionProgressSteps = document.querySelector("#pipelineExecutionProgressSteps");
const pipelineExecutionParallelPanel = document.querySelector("#pipelineExecutionParallelPanel");
const pipelineExecutionProofStatus = document.querySelector("#pipelineExecutionProofStatus");
const pipelineExecutionProofFacts = document.querySelector("#pipelineExecutionProofFacts");
const manifestSearchInput = document.querySelector("#manifestSearchInput");
const manifestCodeEl = document.querySelector("#manifestCode");
const manifestLineNumsEl = document.querySelector("#manifestLineNums");
const manifestListScroll = document.querySelector("#manifestListScroll");
const manifestReferenceCount = document.querySelector("#manifestReferenceCount");
const manifestReferenceSummary = document.querySelector("#manifestReferenceSummary");
const manifestReferenceTabs = document.querySelector("#manifestReferenceTabs");
const manifestReferenceRows = document.querySelector("#manifestReferenceRows");
const manifestReferenceMode = document.querySelector("#manifestReferenceMode");
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
const patchSwarmView = document.querySelector("#patchSwarmView");
const patchSwarmForm = document.querySelector("#patchSwarmForm");
const patchSwarmRepoSelect = document.querySelector("#patchSwarmRepoSelect");
const patchSwarmTask = document.querySelector("#patchSwarmTask");
const patchSwarmCandidateTarget = document.querySelector("#patchSwarmCandidateTarget");
const patchSwarmMaxAgents = document.querySelector("#patchSwarmMaxAgents");
const patchSwarmMode = document.querySelector("#patchSwarmMode");
const patchSwarmProviders = document.querySelector("#patchSwarmProviders");
const patchSwarmRepoState = document.querySelector("#patchSwarmRepoState");
const patchSwarmStartStatus = document.querySelector("#patchSwarmStartStatus");
const patchSwarmStartButton = document.querySelector("#patchSwarmStartButton");
const patchSwarmStartHint = document.querySelector("#patchSwarmStartHint");
const patchSwarmRefreshRepos = document.querySelector("#patchSwarmRefreshRepos");
const patchSwarmRunList = document.querySelector("#patchSwarmRunList");
const patchSwarmCandidateList = document.querySelector("#patchSwarmCandidateList");
const patchSwarmDiffPreview = document.querySelector("#patchSwarmDiffPreview");
const patchSwarmDiffTitle = document.querySelector("#patchSwarmDiffTitle");
const patchSwarmDiffMeta = document.querySelector("#patchSwarmDiffMeta");
const patchSwarmRunSubtitle = document.querySelector("#patchSwarmRunSubtitle");
const patchSwarmCandidateCount = document.querySelector("#patchSwarmCandidateCount");
const patchSwarmSelectedCount = document.querySelector("#patchSwarmSelectedCount");
const patchSwarmValidationStatus = document.querySelector("#patchSwarmValidationStatus");
const patchSwarmCost = document.querySelector("#patchSwarmCost");
const patchSwarmApprovalStatus = document.querySelector("#patchSwarmApprovalStatus");
const patchSwarmApproveButton = document.querySelector("#patchSwarmApproveButton");
const patchSwarmApplyButton = document.querySelector("#patchSwarmApplyButton");
const patchSwarmRejectButton = document.querySelector("#patchSwarmRejectButton");
const patchSwarmDetailEmpty = document.querySelector("#patchSwarmDetailEmpty");
const patchSwarmStatsPanel = document.querySelector("#patchSwarmStats");
const patchSwarmReviewGrid = document.querySelector("#patchSwarmReviewGrid");
const patchSwarmEvidence = document.querySelector("#patchSwarmEvidence");
const issueModal = document.querySelector("#issueModal");
const issueForm = document.querySelector("#issueForm");
const issueModalEyebrow = document.querySelector("#issueModalEyebrow");
const issueModalTitle = document.querySelector("#issueModalTitle");
const issueSubmitButton = document.querySelector("#issueSubmitButton");
const runPipelineTemplateField = document.querySelector("#runPipelineTemplateField");
const runPipelineTemplateSelect = document.querySelector("#runPipelineTemplateSelect");
const runPipelineRouteTitle = document.querySelector("#runPipelineRouteTitle");
const runPipelineRouteDescription = document.querySelector("#runPipelineRouteDescription");
const runPipelineInputCards = document.querySelector("#runPipelineInputCards");
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
const issueDescriptionField = document.querySelector("#issueDescriptionField");
const runPipelineScreenshotInput = document.querySelector("#runPipelineScreenshot");
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
let patchSwarmRepos = [];
let patchSwarmRuns = [];
let patchSwarmDetail = null;
let patchSwarmSelectedCandidateId = "";

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

const DEV_PIPELINE_ARTIFACT_ROOT = "workspace/runs/dev-pipeline-studio/docs-pages/latest/";

function pipelineArtifactAssetPath(value) {
  let clean = String(value || "").trim();
  if (!clean) return "";
  if (/^https?:\/\//i.test(clean) || clean.startsWith("/api/artifacts?")) return clean;
  clean = clean.replace(/^\/+/, "");
  if (!clean.startsWith("workspace/") && /^(execution|evidence|validation|inputs|workers|integration|integration_receipts)\//.test(clean)) {
    clean = `${DEV_PIPELINE_ARTIFACT_ROOT}${clean}`;
  }
  return clean;
}

function pipelineArtifactUrl(value) {
  const path = pipelineArtifactAssetPath(value);
  if (!path) return "";
  if (/^https?:\/\//i.test(path) || path.startsWith("/api/artifacts?")) return path;
  return `/api/artifacts?path=${encodeURIComponent(path)}`;
}

function pipelineArtifactName(value) {
  const clean = String(value || "").split("?")[0].replace(/\/+$/, "");
  return clean.split("/").filter(Boolean).pop() || "image";
}

function pipelineArtifactBaseName(value) {
  return pipelineArtifactName(value).toLowerCase();
}

function pipelineIsImageArtifact(value) {
  return /\.(png|jpe?g|webp|gif)$/i.test(String(value || "").split("?")[0]);
}

function pipelineExecutionArtifactKey(artifact) {
  return String(artifact?.path || artifact?.name || "").trim().toLowerCase();
}

function pipelineExecutionArtifactFromValue(value, flow = pipelineExecutionData()) {
  if (value && typeof value === "object") {
    const path = String(value.path || "").trim();
    const name = String(value.name || "").trim();
    if (path || name) {
      return {
        name: name || pipelineArtifactName(path),
        path,
        size: String(value.size || ""),
        exists: value.exists !== false,
      };
    }
  }
  const clean = String(value || "").trim();
  if (!clean) return null;
  const artifacts = Array.isArray(flow?.artifacts) ? flow.artifacts : [];
  const cleanName = pipelineArtifactBaseName(clean);
  const match = artifacts.find((artifact) => {
    const artifactPath = String(artifact?.path || "");
    const artifactName = String(artifact?.name || "");
    return artifactPath === clean
      || artifactName === clean
      || pipelineArtifactBaseName(artifactPath) === cleanName
      || pipelineArtifactBaseName(artifactName) === cleanName;
  });
  if (match) return match;
  if (!clean.includes("/") && !clean.startsWith("workspace/")) return null;
  return {
    name: pipelineArtifactName(clean),
    path: clean,
    size: "",
    exists: true,
  };
}

function pipelineExecutionArtifactsForRow(row = {}, flow = pipelineExecutionData()) {
  const seen = new Set();
  const values = [
    ...(Array.isArray(row.artifacts) ? row.artifacts : []),
    row.file,
    row.receipt,
    row.stdout_log,
    row.stderr_log,
  ];
  return values
    .map((value) => pipelineExecutionArtifactFromValue(value, flow))
    .filter(Boolean)
    .filter((artifact) => {
      const key = pipelineExecutionArtifactKey(artifact);
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function pipelineExecutionArtifactsForRows(rows = [], flow = pipelineExecutionData()) {
  const seen = new Set();
  return (rows || [])
    .flatMap((row) => pipelineExecutionArtifactsForRow(row, flow))
    .filter((artifact) => {
      const key = pipelineExecutionArtifactKey(artifact);
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function renderPipelineExecutionArtifactLinks(artifacts = [], limit = 3) {
  const visible = (artifacts || []).slice(0, limit);
  const extra = Math.max(0, (artifacts || []).length - visible.length);
  if (!visible.length) return `<span class="pipelineExecutionArtifactEmpty">-</span>`;
  return `
    ${visible.map((artifact) => {
      const url = artifact.exists !== false && artifact.path ? pipelineArtifactUrl(artifact.path) : "";
      const label = artifact.name || pipelineArtifactName(artifact.path) || "artifact";
      return url
        ? `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer" title="${escapeHtml(artifact.path || label)}">${escapeHtml(label)}</a>`
        : `<span class="missing" title="${escapeHtml(artifact.path || label)}">${escapeHtml(label)}</span>`;
    }).join("")}
    ${extra ? `<span class="more">+${extra}</span>` : ""}
  `;
}

function pipelineExecutionArtifactStats(flow = pipelineExecutionData()) {
  const artifacts = Array.isArray(flow?.artifacts) ? flow.artifacts : [];
  const ready = artifacts.filter((artifact) => artifact?.exists !== false).length;
  return {
    total: artifacts.length,
    ready,
    missing: Math.max(0, artifacts.length - ready),
  };
}

function pipelineExecutionFactValue(flow, labels = []) {
  for (const label of labels) {
    const value = pipelineExecutionFact(flow, label);
    if (value) return value;
  }
  return "";
}

function renderPipelineExecutionEvidenceSummary(flow = pipelineExecutionData()) {
  const stats = pipelineExecutionArtifactStats(flow);
  const result = flow?.validation_results || {};
  const parallel = pipelineExecutionParallelModel(flow);
  const cost = pipelineExecutionFactValue(flow, ["AI cost", "Cost"]) || (flow?.total_ai_cost_usd != null ? `$${Number(flow.total_ai_cost_usd).toFixed(6)}` : "$0.000000");
  const budget = pipelineExecutionFactValue(flow, ["Budget"]) || flow?.budget || "-";
  const engine = pipelineExecutionFactValue(flow, ["Engine"]) || flow?.source || "pipeline";
  const runtime = pipelineExecutionFactValue(flow, ["Runtime"]) || flow?.run_mode || "-";
  const laneLabel = parallel.enabled
    ? `${Number(parallel.task_count || parallel.tasks?.length || 0)} lanes`
    : pipelineExecutionFactValue(flow, ["Frontend lane", "Schema"]) || pipelineExecutionStatusText(flow?.status);
  const cards = [
    ["Run", pipelineExecutionStatusText(flow?.status), flow?.duration || "-"],
    ["Evidence", `${stats.ready}/${stats.total} ready`, stats.missing ? `${stats.missing} missing` : "all linked"],
    ["Work", laneLabel, runtime],
    ["Gate", `${Number(result.passed || 0)}/${Number(result.total || 0)} validators`, parallel.enabled ? "serialized" : "deterministic"],
    ["Cost", cost, budget],
    ["Engine", engine, flow?.run_id || ""],
  ];
  return cards.map(([label, value, detail]) => `
    <div>
      <dt>${escapeHtml(label)}</dt>
      <dd>${escapeHtml(value || "-")}</dd>
      <small>${escapeHtml(detail || "")}</small>
    </div>
  `).join("");
}

function pipelineExecutionArtifactClass(artifact = {}) {
  if (artifact.exists === false) return "missing";
  if (pipelineIsImageArtifact(artifact.path || artifact.name)) return "image";
  return "ready";
}

function pipelineExecutionArtifactKind(artifact = {}) {
  const name = String(artifact.name || artifact.path || "").toLowerCase();
  if (pipelineIsImageArtifact(name)) return "image";
  if (name.includes("receipt")) return "receipt";
  if (name.includes("manifest") || name.includes("workset")) return "manifest";
  if (name.includes("plan") || name.includes("request")) return "plan";
  if (name.includes("log") || name.includes("events")) return "log";
  return "artifact";
}

function initializePipelineExecutionEvidenceLayout(flow = pipelineExecutionData()) {
  const runId = String(flow?.run_id || "");
  if (!runId || pipelineExecutionEvidenceLayoutRunId === runId) return;
  pipelineExecutionEvidenceLayoutRunId = runId;
  const factsDetails = pipelineExecutionArtifactFacts?.closest?.("details");
  const listDetails = pipelineExecutionArtifactList?.closest?.("details");
  const validationDetails = pipelineExecutionValidationResults?.closest?.("details");
  if (factsDetails) factsDetails.open = true;
  if (listDetails) listDetails.open = false;
  if (validationDetails) validationDetails.open = false;
}

function uniquePipelineImagePaths(values) {
  return Array.from(new Set((values || []).map(pipelineArtifactAssetPath).filter(pipelineIsImageArtifact)));
}

function pipelineValueList(value) {
  if (Array.isArray(value)) return value;
  if (!value) return [];
  return String(value).split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
}

function renderPipelineImagePreviews(container, values) {
  if (!container) return;
  const images = uniquePipelineImagePaths(values);
  container.classList.toggle("hidden", !images.length);
  container.innerHTML = images.map((path) => {
    const href = pipelineArtifactUrl(path);
    const name = pipelineArtifactName(path);
    return `
      <a class="pipelineImagePreviewCard" href="${escapeHtml(href)}" target="_blank" rel="noreferrer">
        <img src="${escapeHtml(href)}" alt="${escapeHtml(name)}">
        <span>${escapeHtml(name)}</span>
      </a>
    `;
  }).join("");
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
  const editing = mode === "edit";
  if (issueModal) issueModal.dataset.mode = editing ? "edit" : "run";
  if (issueModalEyebrow) issueModalEyebrow.textContent = editing ? "Issue editor" : "Pipeline runner";
  issueModalTitle.textContent = editing ? `Edit prompt #${issue?.id || ""}`.trim() : "Run Pipeline";
  if (issueSubmitButton) issueSubmitButton.textContent = editing ? "Save issue" : "Run pipeline";
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
  issueDescriptionInput.required = editing;
  issueDescriptionField?.classList.toggle("hidden", !editing);
  if (runPipelineScreenshotInput) runPipelineScreenshotInput.value = "";
  runPipelineTemplateField?.classList.toggle("hidden", editing);
  if (runPipelineInputCards) {
    runPipelineInputCards.classList.toggle("hidden", editing);
    if (!editing) {
      refreshRunPipelineTemplateSelect();
      renderRunPipelineInputCards();
    }
  }
}

function openIssueModal(issue = null) {
  const editing = Boolean(issue);
  setIssueFormMode(editing ? "edit" : "create", issue);
  issueModal.classList.remove("hidden");
  issueModal.setAttribute("aria-hidden", "false");
  window.requestAnimationFrame(() => {
    const modalCard = issueModal.querySelector(".modalCard");
    if (modalCard) modalCard.scrollTop = 0;
    if (editing) issueDescriptionInput.focus();
  });
}

async function openRunPipelineModal(prompt = "", options = {}) {
  try {
    const useDefaultRoute = Boolean(options.forceDefaultRoute || prompt);
    if (useDefaultRoute) {
      if (pipelineProjectSelect) pipelineProjectSelect.value = "hard-proreq-project";
      if (pipelineTemplateSelect) pipelineTemplateSelect.value = "hard-proreq-task";
    }
    const selectedTemplate = useDefaultRoute
      ? "hard-proreq-task"
      : options.templateId || pipelineTemplateSelect?.value || pipelineStudioState?.selected?.template_id || "hard-proreq-task";
    currentRunPipelineTemplateId = selectedTemplate;
    if (!pipelineStudioState || pipelineStudioState?.selected?.template_id !== selectedTemplate) {
      if (pipelineTemplateSelect) pipelineTemplateSelect.value = selectedTemplate;
      await loadPipelineStudioStateForRun("");
    }
  } catch {
    // The modal can still use local fallback copy; submit will surface API errors.
  }
  openIssueModal();
  if (prompt) issueDescriptionInput.value = prompt;
  refreshRunPipelineTemplateSelect();
  renderRunPipelineInputCards();
  window.requestAnimationFrame(() => {
    const modalCard = issueModal.querySelector(".modalCard");
    if (modalCard) modalCard.scrollTop = 0;
  });
}

function capturePrefilledIssuePromptFromUrl() {
  const params = new URLSearchParams(location.search);
  const prompt = params.get("new_issue_prompt") || params.get("prompt") || "";
  if (!prompt) return false;
  pendingRunPipelinePrompt = prompt;
  params.delete("new_issue_prompt");
  params.delete("prompt");
  const nextSearch = params.toString();
  const cleanPath = location.pathname === "/issues/new" ? "/issues" : location.pathname;
  history.replaceState(null, "", `${cleanPath}${nextSearch ? `?${nextSearch}` : ""}${location.hash}`);
  return true;
}

function openPrefilledIssueModalFromUrl() {
  if (!pendingRunPipelinePrompt) return false;
  const prompt = pendingRunPipelinePrompt;
  pendingRunPipelinePrompt = "";
  void openRunPipelineModal(prompt, { forceDefaultRoute: true });
  return true;
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
  "hard-proreq-project": {
    key: "hard-proreq-project",
    name: "Hard Proreq Project",
    surface: "Cento pro requirements route",
    surfaceValue: "hard-proreq-task",
    ownedRoot: "workspace/runs/hard-proreq/outputs",
    readPaths: ["AGENTS.md", "README.md", "scripts/**", "templates/agent-work-app/**", "docs/**", "tests/**", "data/tools.json", ".cento/api_workers.yaml"]
  },
  "parallel-pipeline-project": {
    key: "parallel-pipeline-project",
    name: "Parallel Pipeline Project",
    surface: "Cento workset parallel execution",
    surfaceValue: "parallel-pipeline",
    ownedRoot: "workspace/runs/parallel-pipeline/outputs",
    readPaths: ["AGENTS.md", "README.md", "scripts/**", "templates/agent-work-app/**", "docs/**", "tests/**", "data/tools.json", ".cento/api_workers.yaml"]
  },
  "multipipeline-proreq-project": {
    key: "multipipeline-proreq-project",
    name: "Multipipeline ProReq Project",
    surface: "Sequential ProReq meta-pipeline",
    surfaceValue: "multipipeline-proreq-chain",
    ownedRoot: "workspace/runs/multipipeline-proreq/outputs",
    readPaths: ["AGENTS.md", "README.md", "scripts/**", "templates/agent-work-app/**", "docs/**", "tests/**", "data/tools.json", ".cento/api_workers.yaml"]
  },
  "generic-easy-medium-task": {
    key: "generic-easy-medium-task",
    name: "Generic Easy Task",
    surface: "Cento repo task",
    surfaceValue: "generic-task",
    ownedRoot: "workspace/runs/generic-task/outputs",
    readPaths: ["AGENTS.md", "README.md", "scripts/**", "templates/agent-work-app/**", "docs/**", "tests/**", "templates/pipelines/generic-task.json"]
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
  "hard-proreq-task": {
    id: "hard-proreq-task",
    label: "Hard proreq task",
    detail: "Manifest-backed requirement planning with optional screenshot context",
    slug: "hard-proreq-task",
    workerType: "hard_proreq_worker",
    validationTier: "proreq-contract",
    risk: "high",
    tasks: "0 / 10",
    budget: "$0.00",
    budgetDetail: "of $20.00 budget",
    selectedIndex: 0,
    requiredInputs: [
      { id: "operator-thoughts", title: "Operator thoughts and full plan", detail: "Raw request, goals, constraints, assumptions, and complete plan text.", kind: "questionnaire", source: "user", status: "missing", required: true },
      { id: "generated-cento-context", title: "Generated mini Cento context", detail: "Cento-native context and repo search generated from operator input.", kind: "path", source: "auto", automation: "cento-context", status: "configured", required: true },
      { id: "ui-screenshot-request", title: "Optional muted screenshot context", detail: "Optional local screenshot path or OpenAI image edit request generated from the existing UI screenshot.", kind: "image", source: "auto", automation: "openai-image", status: "muted", required: false, muted: true, blocking: false },
      { id: "pro-backend-schema", title: "GPT Pro backend schema manifest", detail: "Strict JSON Schema for backend planning output.", kind: "details", source: "auto", automation: "schema-artifact", status: "configured", required: true },
      { id: "backend-work-handoff", title: "10-story backend handoff", detail: "Ten story manifests, parallel patch workset, manifest integration policy, validation plan, and evidence.", kind: "evidence", source: "auto", automation: "evidence-handoff", status: "configured", required: true }
    ],
    workers: [
      { id: "mini-cento-context", title: "Mini Cento Context", file: "mini_cento_context.json", description: "Generate Cento-native context from the operator request", stage: "repo" },
      { id: "proreq-splitter", title: "Prompt Splitter", file: "proreq_prompt_split.json", description: "Split optional screenshot context and backend story requests", stage: "blueprint", dependencies: ["mini-cento-context"] },
      { id: "backend-work-materializer", title: "Backend Work Materializer", file: "backend_work_manifest.json", description: "Create ten story manifests, parallel workset, integration, and validation manifests", stage: "blueprint", dependencies: ["proreq-splitter"] }
    ],
    factorySteps: [
      { id: "collect-operator-intake", title: "collect_operator_intake", file: "operator_intake.json", status: "Accepted" },
      { id: "build-cento-context", title: "build_mini_cento_context", file: "mini_cento_context.json", status: "Accepted" },
      { id: "write-ui-screenshot-request", title: "ui_screenshot_request_muted", file: "ui_screenshot_request.json", status: "Muted" },
      { id: "prepare-pro-backend-request", title: "prepare_gpt_pro_backend_request", file: "pro_backend_request.json", status: "Accepted" },
      { id: "dispatch-pro-backend-plan", title: "gpt_pro_backend_plan", file: "pro_backend_plan.json", status: "Accepted" },
      { id: "materialize-backend-work", title: "materialize_10_story_backend_work", file: "backend_work_manifest.json", status: "Accepted" }
    ]
  },
  "parallel-pipeline": {
    id: "parallel-pipeline",
    label: "Parallel workset pipeline",
    detail: "Contract-first parallel workers with one serialized integration lane",
    slug: "parallel-pipeline",
    workerType: "parallel_workset_worker",
    validationTier: "workset-contract",
    risk: "high",
    executionModel: "parallel",
    tasks: "0 / 7",
    budget: "$0.00",
    budgetDetail: "of $20.00 budget",
    selectedIndex: 0,
    requiredInputs: [
      { id: "parallel-objective", title: "Parallel pipeline objective", detail: "Operator goal, acceptance criteria, risk limits, and completion definition.", kind: "questionnaire", source: "user", status: "missing", required: true },
      { id: "parallel-workstreams", title: "Parallel worker owned write paths", detail: "Exclusive repo-relative write paths, one independent worker task per path.", kind: "path", source: "user", status: "missing", required: true },
      { id: "parallel-read-context", title: "Generated parallel read context", detail: "Shared read context for all parallel workers.", kind: "path", source: "auto", automation: "cento-context", status: "configured", required: true },
      { id: "parallel-ui-config", title: "Parallel UI and runtime config", detail: "Max parallelism, runtime profile, budget, validation mode, and Execution Flow display policy.", kind: "details", source: "user", status: "missing", required: true },
      { id: "parallel-integrator-gate", title: "Serialized integration gate", detail: "Auto evidence proving worker patches converge through one sequential integrator.", kind: "evidence", source: "auto", automation: "sequential-integrator", status: "configured", required: true },
      { id: "parallel-validation-evidence", title: "Parallel validation and handoff evidence", detail: "Validator receipts, worker receipts, costs, logs, and residual risk notes.", kind: "evidence", source: "auto", automation: "parallel-evidence-handoff", status: "configured", required: true }
    ],
    workers: [
      { id: "workset-config", title: "Workset Config Contract", file: "parallel_workset_config.json", description: "Normalize objective, runtime limits, read context, and exclusive write paths", stage: "repo" },
      { id: "parallel-split", title: "Parallel Worker Split", file: "parallel_worker_split.json", description: "Split independent owned-path workstreams into runnable workset tasks", stage: "blueprint", dependencies: ["workset-config"] },
      { id: "serialized-integrator", title: "Serialized Integrator", file: "parallel_integrator.json", description: "Accept worker receipts one at a time and preserve rollback evidence", stage: "blueprint", dependencies: ["parallel-split"] }
    ],
    factorySteps: [
      { id: "resolve-parallel-inputs", title: "resolve_parallel_inputs", file: "execution_run.json", status: "Accepted" },
      { id: "write-parallel-workset", title: "write_parallel_workset", file: "workset.json", status: "Accepted" },
      { id: "dispatch-parallel-workers", title: "dispatch_parallel_workers", file: "workset_receipt.json", status: "Accepted" },
      { id: "integrate-sequentially", title: "integrate_sequentially", file: "integration_receipts", status: "Accepted" },
      { id: "run-parallel-validation", title: "run_parallel_validation", file: "validation_receipts", status: "Accepted" },
      { id: "collect-parallel-evidence", title: "collect_parallel_evidence", file: "parallel_evidence.json", status: "Accepted" }
    ]
  },
  "multipipeline-proreq-chain": {
    id: "multipipeline-proreq-chain",
    label: "Multipipeline ProReq chain",
    detail: "Four sequential ProReq passes with guidance handoff",
    slug: "multipipeline-proreq-chain",
    workerType: "multipipeline_proreq_coordinator",
    validationTier: "multipipeline-contract",
    risk: "medium",
    executionModel: "ordered",
    tasks: "0 / 9",
    budget: "$0.00",
    budgetDetail: "request-only",
    selectedIndex: 0,
    requiredInputs: [
      { id: "multipipeline-objective", title: "Multipipeline objective", detail: "Operator goal, target areas, boundaries, and success evidence for four sequential ProReq passes.", kind: "questionnaire", source: "user", status: "missing", required: true },
      { id: "multipipeline-schedule-config", title: "Sequential schedule controls", detail: "Pass count, child pipeline, execution mode, UI screenshot request mode, Pro request mode, and handoff policy.", kind: "details", source: "user", status: "provided", required: true, answer: "passes: 4\nchild_pipeline: hard-proreq-task\nexecution_mode: request-artifacts\nui_screenshot: request-artifact\npro_call: request-artifact\nhandoff_policy: previous-guidance-required" },
      { id: "multipipeline-context", title: "Generated Cento route context", detail: "Shared route context for all four ProReq pass requests.", kind: "path", source: "auto", automation: "cento-context", status: "configured", required: true },
      { id: "ui-screenshot-request", title: "UI screenshot guidance request", detail: "Muted image prompt artifact for the multipipeline execution UI.", kind: "image", source: "auto", automation: "openai-image-request", status: "muted", required: false, muted: true, blocking: false },
      { id: "multipipeline-pro-request", title: "ChatGPT Pro chain request", detail: "Request artifact for manifests, integration guidance, validation guidance, and next steps.", kind: "details", source: "auto", automation: "proreq-pro-request", status: "configured", required: true },
      { id: "multipipeline-evidence", title: "Sequential chain evidence", detail: "Pass guidance, UI screenshot request, ChatGPT Pro request, roadmap, and validation evidence.", kind: "evidence", source: "auto", automation: "multipipeline-evidence-handoff", status: "configured", required: true }
    ],
    workers: [
      { id: "chain-intake", title: "Meta-pipeline Intake", file: "operator_intake.json", description: "Normalize objective, boundaries, and compute policy", stage: "repo" },
      { id: "chain-scheduler", title: "Sequential ProReq Scheduler", file: "multipipeline_schedule.json", description: "Schedule four ordered ProReq pass request artifacts", stage: "blueprint", dependencies: ["chain-intake"] },
      { id: "chain-handoff", title: "Guidance And Evidence Handoff", file: "multipipeline_evidence.json", description: "Collect pass guidance, UI prompt, Pro request, roadmap, and evidence", stage: "blueprint", dependencies: ["chain-scheduler"] }
    ],
    factorySteps: [
      { id: "collect-multipipeline-intake", title: "collect_multipipeline_intake", file: "operator_intake.json", status: "Accepted" },
      { id: "write-multipipeline-schedule", title: "write_multipipeline_schedule", file: "multipipeline_schedule.json", status: "Accepted" },
      { id: "run-proreq-pass-1", title: "proreq_pass_1_scope", file: "pass_01_proreq_request.json", status: "Accepted" },
      { id: "run-proreq-pass-2", title: "proreq_pass_2_architecture", file: "pass_02_proreq_request.json", status: "Accepted" },
      { id: "run-proreq-pass-3", title: "proreq_pass_3_integration", file: "pass_03_proreq_request.json", status: "Accepted" },
      { id: "run-proreq-pass-4", title: "proreq_pass_4_validation", file: "pass_04_proreq_request.json", status: "Accepted" },
      { id: "write-multipipeline-ui-screenshot-request", title: "write_ui_screenshot_request", file: "ui_screenshot_request.json", status: "Muted" },
      { id: "write-multipipeline-pro-request", title: "write_chatgpt_pro_request", file: "chatgpt_pro_request.json", status: "Accepted" },
      { id: "collect-multipipeline-evidence", title: "collect_multipipeline_evidence", file: "multipipeline_evidence.json", status: "Accepted" }
    ]
  },
  "generic-task": {
    id: "generic-task",
    label: "Generic easy task",
    detail: "Fully configured non-UI easy programming blueprint",
    slug: "generic-task",
    workerType: "automation_contract_worker",
    validationTier: "contract",
    risk: "low",
    tasks: "9 / 9",
    budget: "$1.42",
    budgetDetail: "of $3.00 budget",
    selectedIndex: 0,
    workers: [
      { id: "repo-context", title: "Repo Context Manifest", file: "repo_context.json", description: "Discover languages, tests, ownership hints, and dependency graph source", stage: "repo" },
      { id: "change-blueprint", title: "Change Plan Contract", file: "change_plan.json", description: "Define bounded change units, test units, and optional AI review gates", stage: "blueprint", dependencies: ["repo-context"] }
    ],
    factorySteps: [
      { id: "checkout-branch", title: "checkout_branch", file: "execution_manifest.json", status: "Accepted" },
      { id: "snapshot-repo-state", title: "snapshot_repo_state", file: "repo_snapshot.json", status: "Accepted" },
      { id: "apply-change-units", title: "apply_change_units", file: "factory_apply_receipt.json", status: "Accepted" },
      { id: "run-formatters", title: "run_formatters", file: "format_receipt.json", status: "Accepted" },
      { id: "run-focused-tests", title: "run_focused_tests", file: "focused_tests.log", status: "Accepted" },
      { id: "run-full-tests", title: "run_full_tests", file: "full_tests.log", status: "Accepted" },
      { id: "collect-diff", title: "collect_diff", file: "diff.patch", status: "Accepted" },
      { id: "collect-logs", title: "collect_logs", file: "evidence_manifest.json", status: "Accepted" }
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
let pipelineSelectedEvidenceId = "";
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
  return pipelineStudioProjects[pipelineProjectSelect?.value || "hard-proreq-project"] || pipelineStudioProjects["hard-proreq-project"] || pipelineStudioProjects["generic-easy-medium-task"];
}

function selectedPipelineStudioTemplate() {
  return pipelineStudioTemplates[pipelineTemplateSelect?.value || "hard-proreq-task"] || pipelineStudioTemplates["hard-proreq-task"] || pipelineStudioTemplates["generic-task"];
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
        maxParallel: Number(template.max_parallel || 1),
        executionModel: template.execution_model || payload.pipeline.execution_model || "",
        workerStageLabel: template.worker_stage_label || payload.pipeline.worker_stage_label || "",
        selectedWorker: template.selected_worker || "",
        requiredInputs: Array.isArray(template.required_inputs) ? template.required_inputs : [],
        factorySteps: Array.isArray(template.factory_steps) ? template.factory_steps : [],
        selectedIndex: 0,
        workers: Array.isArray(template.workers) ? template.workers : (payload.pipeline.workers || [])
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

function pipelineExecutionStatusClass(status) {
  const raw = String(status || "configured").toLowerCase().replace(/\s+/g, "-");
  if (["completed", "passed", "accepted", "applied", "healthy"].includes(raw)) return "completed";
  if (["muted", "separate-flow", "deferred"].includes(raw)) return "muted";
  if (["blocked", "rejected", "budget-blocked", "budget-exceeded", "dependency-blocked"].includes(raw)) return "blocked";
  if (["failed", "error"].includes(raw)) return "failed";
  if (["running", "active", "in-progress"].includes(raw)) return "running";
  if (["queued", "configured", "pending"].includes(raw)) return "queued";
  return raw;
}

function pipelineExecutionStatusText(status) {
  return titleCasePipelineStatus(String(status || "configured").replace(/-/g, " "));
}

function pipelineExecutionData() {
  return pipelineStudioState?.pipeline?.execution_flow || null;
}

function pipelineExecutionIsLive(flow = pipelineExecutionData()) {
  const status = String(flow?.status || "").toLowerCase().replace(/\s+/g, "-");
  return ["running", "queued", "active", "in-progress"].includes(status);
}

function pipelineExecutionFact(flow, label) {
  const item = (flow?.facts || []).find((fact) => String(fact?.label || "").toLowerCase() === String(label || "").toLowerCase());
  return String(item?.value || "");
}

function pipelineExecutionPrimaryPath(flow) {
  return (flow?.changed_paths || [])[0] || (flow?.target_paths || [])[0] || pipelineExecutionFact(flow, "Changed paths") || "";
}

function pipelineExecutionCurrentStep(flow) {
  const steps = flow?.steps || [];
  return steps.find((step) => pipelineExecutionStatusClass(step.status) === "running")
    || steps.find((step) => pipelineExecutionStatusClass(step.status) === "queued")
    || steps.find((step) => ["failed", "blocked"].includes(pipelineExecutionStatusClass(step.status)))
    || [...steps].reverse().find((step) => pipelineExecutionStatusClass(step.status) === "completed")
    || null;
}

function pipelineExecutionReadinessMessage(message) {
  const raw = String(message || "").trim();
  const dirty = raw.match(/^Target write path is already dirty:\s*(?:(\S{1,2})\s+)?(.+)$/i);
  if (dirty) {
    const status = dirty[1] || "";
    const path = (dirty[2] || dirty[1] || "").trim();
    const reason = status.includes("?") ? "untracked" : "modified";
    return `Target path is already ${reason}: ${path}. Use a fresh target path or commit/remove the existing file before rerunning.`;
  }
  return raw;
}

function pipelineExecutionReadinessErrors(flow) {
  return (flow?.readiness_errors || []).map(pipelineExecutionReadinessMessage).filter(Boolean);
}

function pipelineExecutionLiveMessage(flow, step) {
  const status = pipelineExecutionStatusClass(flow?.status || "");
  const stepId = String(step?.id || "");
  const changedPath = pipelineExecutionPrimaryPath(flow);
  const cost = pipelineExecutionFact(flow, "AI cost") || (flow?.total_ai_cost_usd != null ? `$${Number(flow.total_ai_cost_usd).toFixed(6)}` : "");
  const readinessErrors = pipelineExecutionReadinessErrors(flow);
  const parallel = pipelineExecutionParallelModel(flow);
  if (readinessErrors.length) return `Blocked before dispatch: ${readinessErrors[0]}`;
  if (status === "completed" && flow?.source === "cento-hard-proreq-pro") return "Hard proreq planning is complete. The schema-backed GPT pro request, backend work manifest, integration plan, validation plan, and muted frontend screenshot request are ready.";
  if (status === "completed" && flow?.source === "cento-multipipeline-proreq-chain") return "Multipipeline ProReq chain is complete. Four pass requests, UI screenshot request, ChatGPT Pro request, roadmap, and evidence handoff are ready.";
  if (status === "completed" && parallel.enabled) return `${parallel.task_count || parallel.tasks.length} parallel worker lanes converged through the serialized integration gate with evidence ready for handoff.`;
  if (status === "completed") return `Applied ${changedPath || "the requested path"} with receipt-backed cost ${cost || "recorded"}.`;
  if (status === "failed") return `Stopped at ${step?.title || "the current step"}. The receipt and logs below show the failure point.`;
  if (status === "blocked") return `Blocked at ${step?.title || "readiness checks"}. No worktree change was applied.`;
  if (parallel.enabled) {
    const counts = pipelineExecutionParallelCounts(parallel.tasks);
    if (counts.running || counts.queued) return `Fan-out is staging ${parallel.task_count || parallel.tasks.length} exclusive worker lane${(parallel.task_count || parallel.tasks.length) === 1 ? "" : "s"} before one sequential integration gate.`;
    return "Parallel worker output is waiting for the serialized integration and validation gates.";
  }
  if (stepId === "collect-operator-intake") return "Capturing your prompt, plan, and questionnaire input into a run-scoped intake artifact.";
  if (stepId === "collect-multipipeline-intake") return "Capturing the meta-pipeline objective, boundaries, and request-only compute policy.";
  if (stepId === "write-multipipeline-schedule") return "Scheduling four ordered Hard ProReq pass requests with previous-guidance handoff gates.";
  if (stepId?.startsWith("run-proreq-pass-")) return "Writing the next sequential ProReq request and guidance artifact from the previous pass.";
  if (stepId === "write-multipipeline-ui-screenshot-request") return "Writing the muted UI screenshot guidance request for the four-pass execution view.";
  if (stepId === "write-multipipeline-pro-request") return "Preparing the ChatGPT Pro request artifact for manifests, integration guidance, validation guidance, and next steps.";
  if (stepId === "collect-multipipeline-evidence") return "Collecting pass guidance, UI request, Pro request, roadmap, validation status, and handoff evidence.";
  if (stepId === "build-cento-context") return "Using Cento-native context and repo search to build the mini task context.";
  if (stepId === "write-ui-screenshot-request") return "Writing the muted frontend screenshot request. Backend planning continues separately.";
  if (stepId === "prepare-pro-backend-request") return "Preparing the GPT pro backend request with strict JSON Schema output.";
  if (stepId === "dispatch-pro-backend-plan") return "Producing the backend plan artifact. Live Pro dispatch is gated by configuration.";
  if (stepId === "materialize-backend-work") return "Converting the backend plan into Cento-native workstream and Codex exec commands.";
  if (stepId === "api-worker") return "Calling the OpenAI patch worker. The worktree is unchanged until materialization and apply finish.";
  if (stepId === "materialize-patch") return "Converting the structured API response into a local patch bundle.";
  if (stepId === "integrate-sequential") return "Checking the patch in the sequential integration lane before apply.";
  if (stepId === "apply-worktree") return "Applying the accepted patch to the local worktree now.";
  if (stepId === "collect-receipts") return "Collecting cost, patch, validation, and handoff receipts.";
  return "Run accepted. The worker dispatch waits briefly so this page can redirect before execution starts.";
}

function pipelineExecutionDurationText(seconds, fallback = "") {
  const value = Number(seconds || 0);
  if (!Number.isFinite(value) || value <= 0) return fallback || "0s";
  if (value < 60) return `${Math.round(value)}s`;
  const minutes = Math.floor(value / 60);
  const remainder = Math.round(value % 60);
  return remainder ? `${minutes}m ${remainder}s` : `${minutes}m`;
}

function pipelineExecutionCleanTitle(stage, fallback = "") {
  const title = String(stage?.short_title || stage?.title || fallback || "").trim();
  return title.replace(/^\d+\.\s*/, "");
}

function pipelineExecutionAggregateStatus(items) {
  const statuses = (items || []).map((item) => pipelineExecutionStatusClass(item?.status));
  if (statuses.includes("failed")) return "failed";
  if (statuses.includes("blocked")) return "blocked";
  if (statuses.includes("running")) return "running";
  if (statuses.includes("queued")) return "queued";
  if (statuses.length && statuses.every((status) => ["completed", "muted"].includes(status))) return "completed";
  if (statuses.length && statuses.every((status) => status === "completed")) return "completed";
  return statuses[0] || "queued";
}

function pipelineExecutionStageBounds(items) {
  const started = (items || []).map((item) => item?.started).find(Boolean) || "";
  const finished = [...(items || [])].reverse().map((item) => item?.finished).find(Boolean) || "";
  const durationSeconds = (items || []).reduce((sum, item) => sum + Number(item?.duration_seconds || 0), 0);
  return { started, finished, durationSeconds };
}

function pipelineExecutionDisplayStages(rawStages = []) {
  const byId = new Map((rawStages || []).map((stage) => [stage.id, stage]));
  const setupStages = ["input", "repo", "blueprint"].map((id) => byId.get(id)).filter(Boolean);
  const display = [];
  if (setupStages.length) {
    const bounds = pipelineExecutionStageBounds(setupStages);
    display.push({
      id: "preflight",
      index: 1,
      title: "Preflight",
      short_title: "Preflight",
      status: pipelineExecutionAggregateStatus(setupStages),
      count: "contract, repo, blueprint",
      duration: pipelineExecutionDurationText(bounds.durationSeconds),
      duration_seconds: bounds.durationSeconds,
      started: bounds.started,
      finished: bounds.finished,
      steps: setupStages.map((stage) => ({
        id: stage.id,
        title: pipelineExecutionCleanTitle(stage),
        status: stage.status,
        duration: stage.duration,
        duration_seconds: stage.duration_seconds,
        started: stage.started,
        finished: stage.finished,
      })),
    });
  }
  [
    ["factory", setupStages.length ? 2 : 1, "Workset Delivery"],
    ["validation", setupStages.length ? 3 : 2, "Deterministic Validation"],
    ["handoff", setupStages.length ? 4 : 3, "Evidence / Handoff"],
  ].forEach(([id, index, fallback]) => {
    const stage = byId.get(id);
    if (!stage) return;
    display.push({
      ...stage,
      index,
      title: pipelineExecutionCleanTitle(stage, fallback),
      short_title: pipelineExecutionCleanTitle(stage, fallback),
    });
  });
  return display.length ? display : rawStages;
}

function pipelineExecutionNormalizeStageSelection(stageId, stages, flow) {
  const clean = String(stageId || "");
  if (stages.some((stage) => stage.id === clean)) return clean;
  if (["input", "repo", "blueprint"].includes(clean) && stages.some((stage) => stage.id === "preflight")) return "preflight";
  const selected = String(flow?.selected_stage_id || "");
  if (stages.some((stage) => stage.id === selected)) return selected;
  if (["input", "repo", "blueprint"].includes(selected) && stages.some((stage) => stage.id === "preflight")) return "preflight";
  return stages[0]?.id || "";
}

function renderPipelineExecutionLivePanel(flow, stages) {
  const status = pipelineExecutionStatusClass(flow?.status || "");
  const step = pipelineExecutionCurrentStep(flow);
  const parallel = pipelineExecutionParallelModel(flow);
  const changedPath = pipelineExecutionPrimaryPath(flow);
  const worksetReceipt = flow?.workset_receipt || "";
  const cost = pipelineExecutionFact(flow, "AI cost") || (flow?.total_ai_cost_usd != null ? `$${Number(flow.total_ai_cost_usd).toFixed(6)}` : "");
  const budget = pipelineExecutionFact(flow, "Budget") || flow?.budget || "";
  const engine = pipelineExecutionFact(flow, "Engine") || flow?.source || "";
  const runtime = pipelineExecutionFact(flow, "Runtime") || "";
  const readinessErrors = pipelineExecutionReadinessErrors(flow);

  if (pipelineExecutionLiveBadge) {
    pipelineExecutionLiveBadge.textContent = flow?.source === "cento-hard-proreq-pro"
      ? "Hard proreq route"
      : flow?.source === "cento-multipipeline-proreq-chain"
      ? "Multipipeline proreq"
      : (parallel.enabled ? "Parallel workset" : (flow?.source === "cento-workset-api-openai" ? "Real api-openai workset" : "Manifest run"));
    pipelineExecutionLiveBadge.className = status;
  }
  if (pipelineExecutionNowStatus) {
    pipelineExecutionNowStatus.textContent = pipelineExecutionStatusText(flow?.status || "configured");
    pipelineExecutionNowStatus.className = status;
  }
  if (pipelineExecutionNowTitle) {
    pipelineExecutionNowTitle.textContent = parallel.enabled
      ? (status === "completed" ? "Parallel run complete" : `${pipelineExecutionParallelPhase(parallel)} in progress`)
      : readinessErrors.length
      ? "Target path needs cleanup"
      : (step?.title || (status === "completed" ? (flow?.source === "cento-hard-proreq-pro" ? "Hard proreq plan ready" : flow?.source === "cento-multipipeline-proreq-chain" ? "Multipipeline chain ready" : "Delivery completed") : (flow?.source === "cento-hard-proreq-pro" ? "Preparing hard proreq" : flow?.source === "cento-multipipeline-proreq-chain" ? "Preparing multipipeline chain" : "Preparing delivery")));
  }
  if (pipelineExecutionNowMessage) {
    pipelineExecutionNowMessage.textContent = pipelineExecutionLiveMessage(flow, step);
  }
  if (pipelineExecutionProgressSteps) {
    const rows = parallel.enabled ? (stages || []).map((stage) => ({
      id: stage.id,
      title: stage.short_title || stage.title,
      status: stage.status,
      stage_id: stage.id,
    })) : (flow?.steps || []).length ? flow.steps : (stages || []).map((stage) => ({
      id: stage.id,
      title: stage.short_title || stage.title,
      status: stage.status,
      stage_id: stage.id,
    }));
    pipelineExecutionProgressSteps.innerHTML = rows.map((row, index) => {
      const rowStatus = pipelineExecutionStatusClass(row.status);
      return `
        <button type="button" class="${rowStatus} ${row.id === step?.id ? "current" : ""}" data-execution-stage="${escapeHtml(row.stage_id || row.stage || "factory")}">
          <span>${index + 1}</span>
          <strong>${escapeHtml(row.title || row.id || "")}</strong>
          <em>${pipelineExecutionStatusText(row.status)}</em>
        </button>
      `;
    }).join("");
  }
  if (pipelineExecutionProofStatus) {
    pipelineExecutionProofStatus.textContent = worksetReceipt
      ? "Receipt linked"
      : (status === "blocked" ? "Blocked" : (status === "failed" ? "Failed" : (status === "completed" ? "Receipt pending" : "Waiting")));
    pipelineExecutionProofStatus.className = worksetReceipt ? "completed" : status;
  }
  if (pipelineExecutionProofFacts) {
    const facts = readinessErrors.length ? [
      ["Blocker", readinessErrors[0]],
      ["Next action", "Use a fresh target path, or commit/remove the dirty file, then run delivery again."],
      ["Engine", engine],
      ["Runtime", runtime],
      ["Budget", budget || "-"],
      ["Target path", changedPath || "-"],
    ] : [
      ["Engine", engine],
      ["Runtime", runtime],
      ["Cost", cost || "-"],
      ["Budget", budget || "-"],
      ["Changed path", changedPath || "-"],
      ["Workset receipt", worksetReceipt || "-"],
    ];
    pipelineExecutionProofFacts.innerHTML = facts.map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value || "-")}</dd>`).join("");
  }
}

function pipelineExecutionStepRows(flow = pipelineExecutionData()) {
  const steps = Array.isArray(flow?.steps) ? flow.steps : [];
  if (steps.length) return steps;
  return (flow?.stages || []).flatMap((stage) => Array.isArray(stage?.steps) ? stage.steps : []);
}

function pipelineExecutionShortPath(value = "") {
  const text = String(value || "").trim();
  if (!text) return "";
  const parts = text.split("/").filter(Boolean);
  if (parts.length <= 3) return text;
  return `${parts.slice(0, 2).join("/")}/.../${parts.slice(-1)[0]}`;
}

function pipelineExecutionWorkerTitle(value = "", fallback = "Worker lane") {
  const clean = String(value || fallback)
    .replace(/^Worker:\s*/i, "")
    .replace(/^Implement exclusive workstream for\s*/i, "")
    .trim();
  if (/^(workspace|templates|scripts|docs|tests|data|\.cento)\//.test(clean) || /\.[a-z0-9]{1,8}$/i.test(clean)) return fallback;
  return clean || fallback;
}

function pipelineExecutionParallelCounts(tasks = []) {
  return tasks.reduce((counts, task) => {
    const status = pipelineExecutionStatusClass(task.status);
    counts[status] = (counts[status] || 0) + 1;
    return counts;
  }, { completed: 0, running: 0, queued: 0, blocked: 0, failed: 0, muted: 0 });
}

function pipelineExecutionParallelProgress(status, index = 0) {
  const clean = pipelineExecutionStatusClass(status);
  if (clean === "completed") return 100;
  if (clean === "running") return 58 + ((index % 3) * 9);
  if (clean === "queued") return 14;
  if (clean === "blocked" || clean === "failed") return 100;
  if (clean === "muted") return 8;
  return 22;
}

function pipelineExecutionEase(value) {
  const x = Math.max(0, Math.min(1, Number(value || 0)));
  return 1 - Math.pow(1 - x, 3);
}

function pipelineExecutionVisualState(flow) {
  const runId = String(flow?.run_id || "current");
  const now = performance.now();
  let state = pipelineExecutionVisualRuns.get(runId);
  if (!state) {
    const live = pipelineExecutionIsLive(flow);
    const status = pipelineExecutionStatusClass(flow?.status);
    state = {
      createdAt: now,
      sawLive: live,
      completedAt: status === "completed" && !live ? now - 100000 : 0,
    };
    pipelineExecutionVisualRuns.set(runId, state);
    if (pipelineExecutionVisualRuns.size > 8) {
      const firstKey = pipelineExecutionVisualRuns.keys().next().value;
      pipelineExecutionVisualRuns.delete(firstKey);
    }
  }
  if (pipelineExecutionIsLive(flow)) state.sawLive = true;
  if (pipelineExecutionStatusClass(flow?.status) === "completed" && !state.completedAt) {
    state.completedAt = state.sawLive ? now : now - 100000;
  }
  return state;
}

function pipelineExecutionParallelVisualModel(flow, parallel) {
  const tasks = Array.isArray(parallel?.tasks) ? parallel.tasks : [];
  const gateSteps = Array.isArray(parallel?.gate_steps) ? parallel.gate_steps : [];
  const flowStatus = pipelineExecutionStatusClass(flow?.status);
  const state = pipelineExecutionVisualState(flow);
  const now = performance.now();
  if (flowStatus === "failed" || flowStatus === "blocked") {
    return {
      tasks: tasks.map((task, index) => ({ ...task, visual_status: pipelineExecutionStatusClass(task.status), visual_progress: pipelineExecutionParallelProgress(task.status, index) })),
      gate_steps: gateSteps,
      shouldTick: false,
    };
  }

  if (flowStatus === "completed") {
    const elapsed = Math.max(0, now - (state.completedAt || now));
    const laneDelay = Math.max(70, Math.min(130, 980 / Math.max(1, tasks.length)));
    const laneFill = 620;
    const visualTasks = tasks.map((task, index) => {
      const actualStatus = pipelineExecutionStatusClass(task.status);
      if (!state.sawLive) return { ...task, visual_status: actualStatus, visual_progress: pipelineExecutionParallelProgress(actualStatus, index) };
      const localElapsed = elapsed - (index * laneDelay);
      if (localElapsed >= laneFill) return { ...task, visual_status: "completed", visual_progress: 100 };
      const progress = localElapsed <= 0 ? 86 : 86 + Math.round(14 * pipelineExecutionEase(localElapsed / laneFill));
      return { ...task, visual_status: "running", visual_progress: progress };
    });
    const gateStart = (tasks.length * laneDelay) + 420;
    const gateDelay = 320;
    const visualGates = gateSteps.map((step, index) => {
      const localElapsed = elapsed - gateStart - (index * gateDelay);
      if (!state.sawLive) return step;
      if (localElapsed >= gateDelay) return { ...step, visual_status: "completed" };
      if (localElapsed >= 0) return { ...step, visual_status: "running" };
      return { ...step, visual_status: "queued" };
    });
    const doneAt = gateStart + (Math.max(1, gateSteps.length) * gateDelay) + 360;
    return {
      tasks: visualTasks,
      gate_steps: visualGates,
      shouldTick: state.sawLive && elapsed < doneAt,
    };
  }

  const liveElapsed = now - state.createdAt;
  return {
    tasks: tasks.map((task, index) => {
      const actualStatus = pipelineExecutionStatusClass(task.status);
      if (["completed", "failed", "blocked"].includes(actualStatus)) {
        return { ...task, visual_status: actualStatus, visual_progress: pipelineExecutionParallelProgress(actualStatus, index) };
      }
      const localElapsed = liveElapsed - (index * 95);
      if (localElapsed <= 0) return { ...task, visual_status: "queued", visual_progress: 12 };
      const progress = Math.min(86, 22 + Math.round(localElapsed / 42));
      return { ...task, visual_status: "running", visual_progress: progress };
    }),
    gate_steps: gateSteps.map((step) => ({ ...step, visual_status: pipelineExecutionStatusClass(step.status) })),
    shouldTick: pipelineExecutionIsLive(flow),
  };
}

function pipelineExecutionParallelPhase(parallel) {
  const tasks = parallel?.tasks || [];
  const counts = pipelineExecutionParallelCounts(tasks);
  const gateStatuses = (parallel?.gate_steps || []).map((step) => pipelineExecutionStatusClass(step.status));
  if (counts.failed || gateStatuses.includes("failed")) return "Blocked";
  if (counts.blocked || gateStatuses.includes("blocked")) return "Needs review";
  if (tasks.length && counts.completed >= tasks.length && gateStatuses.every((status) => status === "completed" || status === "muted")) return "Complete";
  if (gateStatuses.includes("running")) return "Serializing";
  if (counts.running || counts.queued) return "Fan-out";
  return "Waiting";
}

function pipelineExecutionParallelGateSteps(stepRows = []) {
  const gateIds = new Set(["collect-worker-artifacts", "integrate-sequentially", "integrate-sequential", "run-parallel-validation", "apply-worktree", "collect-parallel-evidence", "collect-receipts"]);
  return stepRows.filter((step) => gateIds.has(String(step.id || ""))).map((step) => ({
    id: String(step.id || ""),
    title: String(step.title || step.id || ""),
    status: pipelineExecutionStatusClass(step.status),
    duration: String(step.duration || ""),
    file: String(step.file || ""),
  }));
}

function pipelineExecutionParallelModel(flow = pipelineExecutionData()) {
  const explicit = flow?.parallel && typeof flow.parallel === "object" ? flow.parallel : {};
  const stepRows = pipelineExecutionStepRows(flow);
  const workerSteps = stepRows.filter((step) => {
    const id = String(step?.id || "");
    const title = String(step?.title || "");
    return id.startsWith("parallel-worker-") || /^Worker:/i.test(title);
  });
  const explicitTasks = Array.isArray(explicit.tasks) ? explicit.tasks : [];
  const tasks = explicitTasks.length ? explicitTasks.map((task, index) => ({
    id: String(task.id || `parallel-worker-${index + 1}`),
    title: pipelineExecutionWorkerTitle(task.title || task.id, `Worker lane ${index + 1}`),
    worker_id: String(task.worker_id || task.id || `worker-${index + 1}`),
    status: pipelineExecutionStatusClass(task.status),
    write_paths: Array.isArray(task.write_paths) ? task.write_paths.map((path) => String(path || "")).filter(Boolean) : [],
    depends_on: Array.isArray(task.depends_on) ? task.depends_on.map((item) => String(item || "")).filter(Boolean) : [],
    patch_bundle: String(task.patch_bundle || ""),
    integration_receipt: String(task.integration_receipt || ""),
    validation_receipt: String(task.validation_receipt || ""),
  })) : workerSteps.map((step, index) => ({
    id: String(step.id || `parallel-worker-${index + 1}`),
    title: pipelineExecutionWorkerTitle(step.title, `Worker lane ${index + 1}`),
    worker_id: String(step.worker_id || step.id || `worker-${index + 1}`),
    status: pipelineExecutionStatusClass(step.status),
    write_paths: pipelineTextToLines(step.file || ""),
    depends_on: Array.isArray(step.dependencies) ? step.dependencies.map((item) => String(item || "")).filter(Boolean) : [],
    patch_bundle: String(step.patch_bundle || ""),
    integration_receipt: String(step.integration_receipt || ""),
    validation_receipt: String(step.validation_receipt || ""),
    duration: String(step.duration || ""),
  }));
  const gateSteps = pipelineExecutionParallelGateSteps(stepRows);
  const enabled = explicit.enabled === true
    || tasks.length > 1
    || stepRows.some((step) => String(step?.id || "").includes("parallel") || String(step?.title || "").toLowerCase().includes("parallel"));
  if (!enabled) return { enabled: false, tasks: [], gate_steps: [] };
  const maxParallel = Number(explicit.max_parallel || flow?.workset_max_parallel || tasks.length || 1);
  const modelPolicy = explicit.integration_model_policy || {};
  return {
    ...explicit,
    enabled: true,
    tasks,
    gate_steps: gateSteps,
    max_parallel: Number.isFinite(maxParallel) && maxParallel > 0 ? maxParallel : Math.max(1, tasks.length),
    task_count: Number(explicit.task_count || tasks.length || 0),
    integration: explicit.integration || "sequential",
    apply: explicit.apply || "sequential",
    no_shared_files: explicit.no_shared_files !== false,
    integration_model_policy: {
      model_ceiling: modelPolicy.model_ceiling || "gpt-4.1-mini",
      mode: modelPolicy.mode || "deterministic-first",
      fallback: modelPolicy.fallback || "only-if-needed",
      profile: modelPolicy.profile || "api-mini-integrator",
    },
    summary: explicit.summary || `${tasks.length} worker lane${tasks.length === 1 ? "" : "s"}, max ${Math.max(1, Number(explicit.max_parallel || tasks.length || 1))} concurrent, one serialized integration gate`,
  };
}

function renderPipelineExecutionParallelPanel(flow, parallel = pipelineExecutionParallelModel(flow)) {
  if (!pipelineExecutionParallelPanel) return null;
  if (!parallel.enabled) {
    pipelineExecutionParallelPanel.classList.add("hidden");
    pipelineExecutionParallelPanel.innerHTML = "";
    return null;
  }
  pipelineExecutionParallelPanel.classList.remove("hidden");
  const fallbackGateSteps = [
    { id: "collect-worker-artifacts", title: "Collect worker artifacts", status: "queued", duration: "" },
    { id: "integrate-sequentially", title: "Integrate", status: "queued", duration: "" },
    { id: "run-parallel-validation", title: "Validate", status: "queued", duration: "" },
    { id: "collect-parallel-evidence", title: "Handoff", status: "queued", duration: "" },
  ];
  const baseParallel = {
    ...parallel,
    gate_steps: parallel.gate_steps?.length ? parallel.gate_steps : fallbackGateSteps,
  };
  const visual = pipelineExecutionParallelVisualModel(flow, baseParallel);
  const tasks = Array.isArray(visual.tasks) ? visual.tasks : [];
  const modelPolicy = parallel.integration_model_policy || {};
  const modelCeiling = modelPolicy.model_ceiling || "gpt-4.1-mini";
  const visualTasksForCounts = tasks.map((task) => ({ ...task, status: task.visual_status || task.status }));
  const visualGatesForPhase = (visual.gate_steps || []).map((step) => ({ ...step, status: step.visual_status || step.status }));
  const statusCounts = pipelineExecutionParallelCounts(visualTasksForCounts);
  const phase = pipelineExecutionParallelPhase({ ...parallel, tasks: visualTasksForCounts, gate_steps: visualGatesForPhase });
  const gateSteps = visual.gate_steps?.length ? visual.gate_steps : fallbackGateSteps;
  const totalTasks = Number(parallel.task_count || tasks.length || 0);
  pipelineExecutionParallelPanel.innerHTML = `
    <header>
      <div class="pipelineExecutionParallelIntro">
        <small>Parallel Execution</small>
        <strong>${escapeHtml(phase)} · ${totalTasks} lane${totalTasks === 1 ? "" : "s"}</strong>
        <span>${Number(parallel.max_parallel || 1)} max parallel · ${escapeHtml(parallel.integration || "sequential")} integration · ${parallel.no_shared_files === false ? "write paths need review" : "exclusive write paths"}</span>
      </div>
      <div class="pipelineExecutionParallelMeter" style="--parallel-overall:${totalTasks ? Math.round((Number(statusCounts.completed || 0) / totalTasks) * 100) : 0}%">
        <strong>${Number(statusCounts.completed || 0)} / ${totalTasks}</strong>
        <span>workers complete</span>
        <i aria-hidden="true"></i>
      </div>
    </header>
    <div class="pipelineExecutionParallelBody">
      <div class="pipelineExecutionParallelLanes" aria-label="Parallel worker lanes">
        ${tasks.map((task, index) => {
          const status = pipelineExecutionStatusClass(task.visual_status || task.status);
          const writePaths = Array.isArray(task.write_paths) ? task.write_paths : [];
          const pathLabel = writePaths.map(pipelineExecutionShortPath).join(", ") || "write path pending";
          const progress = Number(task.visual_progress || pipelineExecutionParallelProgress(status, index));
          return `
            <article class="${status}" style="--parallel-progress:${progress}%; --lane-index:${index}">
              <b>${index + 1}</b>
              <div>
                <strong>${escapeHtml(task.title || task.id || `worker ${index + 1}`)}</strong>
                <span>${escapeHtml(pathLabel)}</span>
              </div>
              <em>${pipelineExecutionStatusText(status)}</em>
              <i aria-hidden="true"></i>
            </article>
          `;
        }).join("")}
      </div>
      <aside class="pipelineExecutionIntegrator" aria-label="Serialized integration lane">
        <header>
          <span>Serialized Gate</span>
          <strong>Integrate · Validate · Handoff</strong>
        </header>
        <p>Worker patches fan in once. Model review stays only-if-needed and capped at ${escapeHtml(modelCeiling)}.</p>
        <ol>
          ${gateSteps.map((step, index) => `
            <li class="${pipelineExecutionStatusClass(step.visual_status || step.status)}">
              <b>${index + 1}</b>
              <span>${escapeHtml(step.title || step.id || "")}</span>
              <em>${pipelineExecutionStatusText(step.visual_status || step.status)}</em>
            </li>
          `).join("")}
        </ol>
        <div class="pipelineExecutionParallelBadges">
          <small>${Number(statusCounts.running || 0)} running</small>
          <small>${Number(statusCounts.queued || 0)} queued</small>
          <small>${pipelineExecutionFact(flow, "AI cost") || "$0.000000"}</small>
        </div>
      </aside>
    </div>
  `;
  return visual;
}

function selectPipelineExecutionStage(stageId) {
  const flow = pipelineExecutionData();
  const stages = pipelineExecutionDisplayStages(flow?.stages || []);
  currentPipelineExecutionStageId = pipelineExecutionNormalizeStageSelection(stageId, stages, flow);
  renderPipelineExecutionFlow();
}

function setPipelineExecutionLogFilter(filter) {
  currentPipelineExecutionLogFilter = filter || "all";
  renderPipelineExecutionLogs();
}

function clearPipelineExecutionAnimation() {
  pipelineExecutionAnimationTimers.forEach((timer) => clearTimeout(timer));
  pipelineExecutionAnimationTimers = [];
  pipelineExecutionAnimationSignature = "";
  pipelineExecutionPage?.classList.remove("animating", "animationComplete");
  if (pipelineExecutionPage) {
    pipelineExecutionPage.dataset.animationState = "idle";
    pipelineExecutionPage.style.setProperty("--execution-animation-step-count", "0");
  }
}

function clearPipelineExecutionVisualTimer() {
  if (pipelineExecutionVisualTimer) clearTimeout(pipelineExecutionVisualTimer);
  pipelineExecutionVisualTimer = null;
}

function schedulePipelineExecutionVisualTick(visual) {
  clearPipelineExecutionVisualTimer();
  if (!visual?.shouldTick || currentPipelineTab !== "execution-flow") return;
  pipelineExecutionVisualTimer = setTimeout(() => {
    pipelineExecutionVisualTimer = null;
    renderPipelineExecutionFlow();
  }, 120);
}

function pipelineExecutionAnimationKey(flow, stages) {
  const stageKey = (stages || []).map((stage) => {
    const stepKey = (stage.steps || []).map((step) => `${step.id || step.title}:${pipelineExecutionStatusClass(step.status)}:${step.duration_seconds || ""}`).join(",");
    return `${stage.id}:${pipelineExecutionStatusClass(stage.status)}:${stage.duration_seconds || ""}:${stepKey}`;
  }).join("|");
  const parallel = pipelineExecutionParallelModel(flow);
  const parallelKey = parallel.enabled
    ? (parallel.tasks || []).map((task) => `${task.id}:${pipelineExecutionStatusClass(task.status)}:${(task.write_paths || []).join(",")}`).join("|")
    : "";
  return [flow?.run_id || "", pipelineExecutionStatusClass(flow?.status), flow?.event_count || "", stageKey, parallelKey].join("::");
}

function schedulePipelineExecutionAnimation(flow, stages, isLive) {
  if (!pipelineExecutionPage) return;
  const rows = Array.from(pipelineExecutionPage.querySelectorAll("[data-execution-stage-card], [data-execution-animation-row]"));
  if (!rows.length) return;
  const signature = pipelineExecutionAnimationKey(flow, stages);
  pipelineExecutionAnimationTimers.forEach((timer) => clearTimeout(timer));
  pipelineExecutionAnimationTimers = [];
  if (signature === pipelineExecutionAnimationSignature) {
    pipelineExecutionPage.classList.remove("animating");
    pipelineExecutionPage.classList.add("animationComplete");
    rows.forEach((row) => row.classList.add("animationRevealed"));
    return;
  }
  pipelineExecutionAnimationSignature = signature;
  pipelineExecutionPage.classList.remove("animationComplete");
  pipelineExecutionPage.classList.add("animating");
  pipelineExecutionPage.dataset.animationState = isLive ? "live" : "replay";
  pipelineExecutionPage.style.setProperty("--execution-animation-step-count", String(rows.length));
  rows.forEach((row) => row.classList.remove("animationRevealed", "animationActive"));
  const stepMs = isLive ? 105 : 48;
  rows.forEach((row, index) => {
    const timer = setTimeout(() => {
      rows.forEach((item) => item.classList.remove("animationActive"));
      row.classList.add("animationRevealed", "animationActive");
    }, index * stepMs);
    pipelineExecutionAnimationTimers.push(timer);
  });
  const doneTimer = setTimeout(() => {
    pipelineExecutionPage.classList.remove("animating");
    pipelineExecutionPage.classList.add("animationComplete");
    pipelineExecutionPage.dataset.animationState = isLive ? "live" : "idle";
    rows.forEach((row) => row.classList.remove("animationActive"));
  }, rows.length * stepMs + 240);
  pipelineExecutionAnimationTimers.push(doneTimer);
}

function stopPipelineExecutionPolling() {
  if (pipelineExecutionPollTimer) clearTimeout(pipelineExecutionPollTimer);
  pipelineExecutionPollTimer = null;
  pipelineExecutionPollingActive = false;
}

function ensurePipelineExecutionPolling(flow = pipelineExecutionData()) {
  if (currentPipelineTab !== "execution-flow" || !pipelineExecutionIsLive(flow) || flow?.is_active_run === false || pipelineExecutionPollingActive) return;
  pipelineExecutionPollingActive = true;
  pipelineExecutionPollTimer = setTimeout(pollPipelineExecutionDelivery, 650);
}

async function loadPipelineExecutionRun(runId) {
  const cleanRunId = String(runId || "").trim();
  stopPipelineExecutionPolling();
  clearPipelineExecutionAnimation();
  clearPipelineExecutionVisualTimer();
  currentPipelineExecutionRunId = cleanRunId;
  const payload = await loadPipelineStudioStateForRun(cleanRunId);
  const flow = payload?.pipeline?.execution_flow;
  currentPipelineExecutionStageId = flow?.selected_stage_id || flow?.stages?.[0]?.id || "factory";
  renderPipelineExecutionFlow();
}

async function pollPipelineExecutionDelivery() {
  if (!pipelineExecutionPollingActive) return;
  try {
    await loadPipelineStudioStateForRun("");
    const flow = pipelineExecutionData();
    if (flow?.stages?.length) {
      const activeStage = flow.stages.find((stage) => pipelineExecutionStatusClass(stage.status) === "running")
        || flow.stages.find((stage) => pipelineExecutionStatusClass(stage.status) === "queued")
        || flow.stages[flow.stages.length - 1];
      currentPipelineExecutionStageId = activeStage?.id || currentPipelineExecutionStageId;
      renderPipelineExecutionFlow();
    }
    if (pipelineExecutionIsLive(flow)) {
      pipelineExecutionPollTimer = setTimeout(pollPipelineExecutionDelivery, 650);
      return;
    }
    stopPipelineExecutionPolling();
    if (!pipelineExecutionParallelModel(flow).enabled) {
      clearPipelineExecutionAnimation();
    }
    if (pipelineExecutionRunButton) {
      pipelineExecutionRunButton.disabled = false;
      pipelineExecutionRunButton.textContent = "↻ Re-run";
    }
    setPipelineSaveStatus(`Delivery ${pipelineExecutionStatusText(flow?.status || "completed")} at ${new Date().toLocaleTimeString()}`);
  } catch (error) {
    stopPipelineExecutionPolling();
    clearPipelineExecutionAnimation();
    if (pipelineExecutionRunButton) {
      pipelineExecutionRunButton.disabled = false;
      pipelineExecutionRunButton.textContent = "↻ Re-run";
    }
    setPipelineSaveStatus(`Execution polling failed: ${error.message}`, true);
  }
}

async function runPipelineExecutionDelivery() {
  if (!pipelineExecutionRunButton) return;
  stopPipelineExecutionPolling();
  currentPipelineExecutionRunId = "";
  pipelineExecutionRunButton.disabled = true;
  pipelineExecutionRunButton.textContent = "Starting...";
  clearPipelineExecutionAnimation();
  clearPipelineExecutionVisualTimer();
  try {
    const payload = await savePipelineDraft("run_delivery", { includeManifest: false });
    if (!payload) throw new Error("Delivery did not return pipeline state");
    const flow = payload.pipeline?.execution_flow;
    currentPipelineExecutionStageId = flow?.stages?.find((stage) => pipelineExecutionStatusClass(stage.status) === "running")?.id
      || flow?.stages?.[0]?.id
      || "input";
    renderPipelineExecutionFlow();
    if (pipelineExecutionRunButton) pipelineExecutionRunButton.textContent = pipelineExecutionIsLive(flow) ? "Running..." : "↻ Re-run";
    if (pipelineExecutionIsLive(flow) && !pipelineExecutionPollingActive) {
      pipelineExecutionPollingActive = true;
      pipelineExecutionPollTimer = setTimeout(pollPipelineExecutionDelivery, 250);
    } else {
      pipelineExecutionRunButton.disabled = false;
    }
  } catch (error) {
    stopPipelineExecutionPolling();
    pipelineExecutionRunButton.disabled = false;
    pipelineExecutionRunButton.textContent = "↻ Re-run";
    setPipelineSaveStatus(`Delivery failed: ${error.message}`, true);
  }
}

async function openDefaultPipelineRouteFromIssue(result) {
  const route = result?.pipeline_route || {};
  const routeRunId = String(route.run_id || "");
  const routeUrl = String(route.url || "/dev-pipeline-studio#pipeline-flow");
  currentPipelineExecutionRunId = routeRunId;
  stopPipelineExecutionPolling();
  clearPipelineExecutionAnimation();
  clearPipelineExecutionVisualTimer();
  if (pipelineProjectSelect) pipelineProjectSelect.value = route.project_id || "hard-proreq-project";
  if (pipelineTemplateSelect) pipelineTemplateSelect.value = route.template_id || "hard-proreq-task";
  history.pushState(null, "", routeUrl.includes("#") ? routeUrl : `${routeUrl}#pipeline-flow`);
  showDevPipelineStudio();
  setPipelineTab("execution-flow", { updateHash: true });
  const payload = await loadPipelineStudioStateForRun(routeRunId);
  const flow = payload?.pipeline?.execution_flow;
  currentPipelineExecutionStageId = flow?.stages?.find((stage) => pipelineExecutionStatusClass(stage.status) === "running")?.id
    || flow?.stages?.[0]?.id
    || "factory";
  renderPipelineExecutionFlow();
  if (pipelineExecutionIsLive(flow) && !pipelineExecutionPollingActive) {
    pipelineExecutionPollingActive = true;
    pipelineExecutionPollTimer = setTimeout(pollPipelineExecutionDelivery, 250);
  }
  const issue = result?.issue || {};
  const prefix = issue.id ? `Prompt #${issue.id}` : "Run Pipeline";
  setPipelineSaveStatus(`${prefix} routed to pipeline run ${flow?.run_id || route.run_id || ""}`.trim());
}

function renderPipelineExecutionFlow() {
  const flow = pipelineExecutionData();
  if (!flow) return;
  const stages = pipelineExecutionDisplayStages(flow.stages || []);
  const selectedRunId = currentPipelineExecutionRunId || flow.run_id || "";
  const isLive = pipelineExecutionIsLive(flow);
  const parallel = pipelineExecutionParallelModel(flow);
  if (pipelineExecutionPage) pipelineExecutionPage.dataset.executionSource = flow.source || "unknown";
  if (pipelineExecutionPage) pipelineExecutionPage.dataset.executionRunId = selectedRunId;
  if (pipelineExecutionPage) pipelineExecutionPage.dataset.executionModel = parallel.enabled ? "parallel" : "standard";
  if (pipelineExecutionPage) {
    pipelineExecutionPage.dataset.animationState = isLive ? "live" : "idle";
  }
  if (isLive) {
    ensurePipelineExecutionPolling(flow);
  }
  renderPipelineExecutionLivePanel(flow, stages);
  const parallelVisual = renderPipelineExecutionParallelPanel(flow, parallel);
  if (pipelineExecutionRunButton && !pipelineExecutionPollingActive) {
    pipelineExecutionRunButton.disabled = isLive;
    pipelineExecutionRunButton.textContent = isLive ? "Running..." : "↻ Re-run";
  }
  if (pipelineExecutionRunsCount) {
    const count = (flow.history || []).length;
    pipelineExecutionRunsCount.textContent = `${count} run${count === 1 ? "" : "s"}`;
  }
  if (pipelineExecutionRunsList) {
    pipelineExecutionRunsList.innerHTML = (flow.history || []).map((run) => {
      const isSelected = String(run.run_id || "") === selectedRunId;
      const isActive = String(run.run_id || "") === String(flow.active_run_id || "");
      const artifactCount = Number(run.artifact_count || 0);
      const durationLabel = [run.duration || "", artifactCount ? `${artifactCount} artifacts` : ""].filter(Boolean).join(" · ");
      return `
        <button type="button" class="${isSelected ? "selected" : ""} ${pipelineExecutionStatusClass(run.status)}" data-execution-run-id="${escapeHtml(run.run_id || "")}">
          <strong>${escapeHtml(run.run_id || "")}</strong>
          <span>${escapeHtml(run.started || "")}</span>
          <em>${pipelineExecutionStatusText(run.status)}${isActive ? " · Active" : ""}</em>
          <small>${escapeHtml(durationLabel)}</small>
        </button>
      `;
    }).join("");
  }
  if (!currentPipelineExecutionStageId || !stages.some((stage) => stage.id === currentPipelineExecutionStageId)) {
    currentPipelineExecutionStageId = pipelineExecutionNormalizeStageSelection(currentPipelineExecutionStageId, stages, flow);
  }
  document.querySelectorAll("[data-execution-field]").forEach((field) => {
    const key = field.dataset.executionField;
    const values = {
      runId: flow.run_id,
      status: pipelineExecutionStatusText(flow.status),
      started: flow.started,
      finished: flow.finished,
      duration: flow.duration,
      triggeredBy: flow.triggered_by,
      runMode: flow.run_mode,
      evidencePolicy: flow.evidence_policy,
      overallStatus: pipelineExecutionStatusText(flow.status),
    };
    field.textContent = values[key] || "";
    if (key === "status" || key === "overallStatus") field.className = pipelineExecutionStatusClass(flow.status);
  });
  if (pipelineExecutionStageStrip) {
    pipelineExecutionStageStrip.innerHTML = stages.map((stage, index) => `
      <button type="button" class="${stage.id === currentPipelineExecutionStageId ? "selected" : ""} ${pipelineExecutionStatusClass(stage.status)}" data-execution-stage="${escapeHtml(stage.id)}" data-execution-stage-card="${index}">
        <span><b>${stage.index}</b> ${escapeHtml(stage.title)}</span>
        <strong>${escapeHtml(stage.count || "")}</strong>
        <small>${escapeHtml(stage.duration || "")}</small>
        <em>${pipelineExecutionStatusText(stage.status)}</em>
      </button>
    `).join("");
  }
  if (pipelineExecutionTimelineWindow) {
    const first = flow.started || stages[0]?.started || "";
    const last = flow.finished || stages[stages.length - 1]?.finished || "";
    pipelineExecutionTimelineWindow.textContent = first && last ? `${first} - ${last}` : "";
  }
  if (pipelineExecutionTimelineBody) {
    pipelineExecutionTimelineBody.innerHTML = `
      <div class="pipelineExecutionTimelineHeader"><span>Stage</span><span>Start</span><span>Progress</span><span>Elapsed</span></div>
      ${stages.map((stage) => `
        <button type="button" class="${stage.id === currentPipelineExecutionStageId ? "selected" : ""} ${pipelineExecutionStatusClass(stage.status)}" data-execution-stage="${escapeHtml(stage.id)}" data-execution-animation-row="stage">
          <span><i></i>${escapeHtml(stage.short_title || stage.title)}</span>
          <b>${escapeHtml(stage.started || "")}</b>
          <em style="--execution-width:${Math.max(8, Math.min(100, Number(stage.duration_seconds || 0) / 1.4))}%"></em>
          <strong>${escapeHtml(stage.duration || "")}</strong>
        </button>
        ${(stage.steps || []).map((step) => `
          <button type="button" class="nested ${pipelineExecutionStatusClass(step.status)} ${stage.id === currentPipelineExecutionStageId ? "activeParent" : ""}" data-execution-stage="${escapeHtml(stage.id)}" data-execution-animation-row="step">
            <span>› ${escapeHtml(step.title || step.id)}</span>
            <b>${escapeHtml(step.started || "")}</b>
            <em style="--execution-width:${Math.max(6, Math.min(84, Number(step.duration_seconds || 0) * 3))}%"></em>
            <strong>${escapeHtml(step.duration || "")}</strong>
          </button>
        `).join("")}
      `).join("")}
    `;
  }
  if (parallel.enabled) {
    pipelineExecutionPage?.classList.remove("animating", "animationComplete");
    schedulePipelineExecutionVisualTick(parallelVisual);
  } else {
    clearPipelineExecutionVisualTimer();
    schedulePipelineExecutionAnimation(flow, stages, isLive);
  }
  const selectedStage = stages.find((stage) => stage.id === currentPipelineExecutionStageId) || stages[0] || {};
  if (pipelineExecutionSelectedTitle) pipelineExecutionSelectedTitle.textContent = selectedStage.short_title || selectedStage.title || "";
  if (pipelineExecutionSelectedStatus) {
    pipelineExecutionSelectedStatus.textContent = pipelineExecutionStatusText(selectedStage.status);
    pipelineExecutionSelectedStatus.className = pipelineExecutionStatusClass(selectedStage.status);
  }
  const rows = selectedStage.steps?.length ? selectedStage.steps : stages.map((stage) => ({
    title: stage.short_title,
    status: stage.status,
    duration: stage.duration,
    started: stage.started,
    finished: stage.finished,
    artifacts: stage.artifacts || [],
  }));
  const selectedStageArtifacts = pipelineExecutionArtifactsForRows(rows, flow);
  if (pipelineExecutionSelectedMeta) {
    pipelineExecutionSelectedMeta.innerHTML = [
      ["Status", pipelineExecutionStatusText(selectedStage.status)],
      ["Duration", selectedStage.duration],
      ["Started", selectedStage.started],
      ["Finished", selectedStage.finished],
      ["Items", selectedStage.count],
      ["Artifacts", selectedStageArtifacts.length ? `${selectedStageArtifacts.length} linked` : "none"],
    ].map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value || "-")}</strong></div>`).join("");
  }
  if (pipelineExecutionStepTable) {
    pipelineExecutionStepTable.innerHTML = `
      <div><span>Step</span><span>Status</span><span>Duration</span><span>Started</span><span>Finished</span><span>Artifacts</span></div>
      ${rows.map((row) => {
        const rowArtifacts = pipelineExecutionArtifactsForRow(row, flow);
        return `
        <div>
          <strong>${escapeHtml(row.title || row.id || "")}</strong>
          <em class="${pipelineExecutionStatusClass(row.status)}">${pipelineExecutionStatusText(row.status)}</em>
          <span>${escapeHtml(row.duration || "")}</span>
          <span>${escapeHtml(row.started || "")}</span>
          <span>${escapeHtml(row.finished || "")}</span>
          <span class="pipelineExecutionStepArtifacts">${renderPipelineExecutionArtifactLinks(rowArtifacts)}</span>
        </div>
      `;
      }).join("")}
    `;
  }
  initializePipelineExecutionEvidenceLayout(flow);
  const artifactStats = pipelineExecutionArtifactStats(flow);
  if (pipelineExecutionArtifactCount) pipelineExecutionArtifactCount.textContent = String(artifactStats.total);
  if (pipelineExecutionArtifactFacts) {
    pipelineExecutionArtifactFacts.innerHTML = renderPipelineExecutionEvidenceSummary(flow);
  }
  if (pipelineExecutionArtifactList) {
    pipelineExecutionArtifactList.innerHTML = (flow.artifacts || []).map((artifact) => {
      const url = artifact.exists && artifact.path ? pipelineArtifactUrl(artifact.path) : "";
      return `
        <article class="${pipelineExecutionArtifactClass(artifact)}">
          <span>${escapeHtml(pipelineExecutionArtifactKind(artifact))}</span>
          ${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(artifact.name || "")}</a>` : `<strong>${escapeHtml(artifact.name || "")}</strong>`}
          <small>${escapeHtml(artifact.size || "")}</small>
          <em>${artifact.exists ? "Ready" : "Missing"}</em>
        </article>
      `;
    }).join("");
  }
  if (pipelineExecutionValidationResults) {
    const result = flow.validation_results || {};
    const readinessErrors = pipelineExecutionReadinessErrors(flow);
    pipelineExecutionValidationResults.innerHTML = `
      <p>${readinessErrors.length ? `${readinessErrors.length} readiness blocker${readinessErrors.length === 1 ? "" : "s"}` : `${Number(result.passed || 0)} / ${Number(result.total || 0)} validators passed`}</p>
      ${readinessErrors.map((message) => `
        <article class="blocked">
          <span>!</span>
          <strong>${escapeHtml(message)}</strong>
          <em>Blocked</em>
          <small>readiness</small>
        </article>
      `).join("")}
      ${(result.items || []).map((item) => `
        <article class="${pipelineExecutionStatusClass(item.status)}">
          <span>✓</span>
          <strong>${escapeHtml(item.title || "")}</strong>
          <em>${pipelineExecutionStatusText(item.status)}</em>
          <small>${escapeHtml(item.duration || "")}</small>
        </article>
      `).join("")}
    `;
  }
  renderPipelineExecutionLogs();
}

function renderPipelineExecutionLogs() {
  const flow = pipelineExecutionData();
  if (!flow) return;
  const logs = flow.logs || [];
  const filters = ["all", "input", "repo", "blueprint", "execution", "validation", "handoff", "pipeline"];
  if (pipelineExecutionLogFilters) {
    pipelineExecutionLogFilters.innerHTML = filters.map((filter) => `
      <button type="button" class="${filter === currentPipelineExecutionLogFilter ? "active" : ""}" data-execution-log-filter="${escapeHtml(filter)}">${escapeHtml(filter === "repo" ? "Discovery" : titleCasePipelineStatus(filter))}</button>
    `).join("");
  }
  const search = String(pipelineExecutionLogSearch?.value || "").trim().toLowerCase();
  const visible = logs.filter((log) => {
    const filterMatch = currentPipelineExecutionLogFilter === "all" || log.stage === currentPipelineExecutionLogFilter;
    const text = `${log.time} ${log.stage} ${log.source} ${log.message}`.toLowerCase();
    return filterMatch && (!search || text.includes(search));
  });
  if (pipelineExecutionLogRows) {
    pipelineExecutionLogRows.textContent = visible.map((log) => `${log.time}  [${String(log.source || log.stage).padEnd(24).slice(0, 24)}]  ${log.message}`).join("\n");
  }
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

function pipelineInputSource(item = {}) {
  const raw = String(item.source || item.automation_source || "").trim().toLowerCase();
  if (["auto", "generated", "automation", "automated"].includes(raw)) return "auto";
  if (["user", "manual", "operator"].includes(raw)) return "user";
  return pipelineInputId(item) === "operator-thoughts" ? "user" : "auto";
}

function pipelineInputAutomation(item = {}) {
  return String(item.automation || item.automation_source || "").trim();
}

function pipelineTemplateInputs(template = {}) {
  if (Array.isArray(template.required_inputs)) return template.required_inputs;
  if (Array.isArray(template.requiredInputs)) return template.requiredInputs;
  return [];
}

function pipelineTemplateListForRun() {
  const templates = [];
  const addTemplate = (template = {}) => {
    const id = String(template.id || "").trim();
    if (!id) return;
    const existingIndex = templates.findIndex((item) => item.id === id);
    const normalized = {
      ...template,
      id,
      label: template.label || template.name || id,
      detail: template.detail || template.description || template.tagline || "",
      requiredInputs: pipelineTemplateInputs(template),
    };
    if (existingIndex >= 0) {
      templates[existingIndex] = {
        ...templates[existingIndex],
        ...normalized,
        requiredInputs: normalized.requiredInputs.length ? normalized.requiredInputs : templates[existingIndex].requiredInputs,
      };
      return;
    }
    templates.push(normalized);
  };
  (Array.isArray(pipelineStudioState?.templates) ? pipelineStudioState.templates : []).forEach(addTemplate);
  Object.values(pipelineStudioTemplates || {}).forEach(addTemplate);
  return templates;
}

function runPipelineSelectedTemplateId() {
  const selected = String(runPipelineTemplateSelect?.value || currentRunPipelineTemplateId || pipelineTemplateSelect?.value || pipelineStudioState?.selected?.template_id || "").trim();
  const templates = pipelineTemplateListForRun();
  return selected || templates[0]?.id || "hard-proreq-task";
}

function selectedRunPipelineTemplate(templateId = runPipelineSelectedTemplateId()) {
  return pipelineTemplateListForRun().find((template) => template.id === templateId)
    || pipelineStudioTemplates?.[templateId]
    || selectedPipelineStudioTemplate()
    || {};
}

function pipelineProjectListForRun() {
  const projects = [];
  const addProject = (project = {}) => {
    const id = String(project.id || project.key || "").trim();
    if (!id || projects.some((item) => item.id === id)) return;
    projects.push({
      ...project,
      id,
      label: project.label || project.name || id,
      surface_value: project.surface_value || project.surfaceValue || project.surface || "",
    });
  };
  (Array.isArray(pipelineStudioState?.projects) ? pipelineStudioState.projects : []).forEach(addProject);
  Object.values(pipelineStudioProjects || {}).forEach(addProject);
  return projects;
}

function runPipelineProjectForTemplate(templateId = runPipelineSelectedTemplateId()) {
  const currentProjectId = pipelineStudioState?.selected?.project_id || pipelineProjectSelect?.value || "";
  const projects = pipelineProjectListForRun();
  const surfaceMatch = projects.find((project) => String(project.surface_value || project.surfaceValue || "") === templateId);
  return surfaceMatch?.id || currentProjectId || projects[0]?.id || "hard-proreq-project";
}

function refreshRunPipelineTemplateSelect() {
  if (!runPipelineTemplateSelect) return;
  const templates = pipelineTemplateListForRun();
  const requestedId = currentRunPipelineTemplateId || pipelineTemplateSelect?.value || pipelineStudioState?.selected?.template_id || templates[0]?.id || "hard-proreq-task";
  runPipelineTemplateSelect.innerHTML = templates.map((template) => {
    const inputCount = pipelineTemplateInputs(template).length || template.requiredInputs?.length || 0;
    const suffix = inputCount ? ` (${inputCount} inputs)` : "";
    return `<option value="${escapeHtml(template.id)}">${escapeHtml(template.label || template.id)}${escapeHtml(suffix)}</option>`;
  }).join("");
  if (templates.some((template) => template.id === requestedId)) {
    runPipelineTemplateSelect.value = requestedId;
  } else if (templates[0]) {
    runPipelineTemplateSelect.value = templates[0].id;
  }
  currentRunPipelineTemplateId = runPipelineTemplateSelect.value || requestedId;
}

function currentRunPipelineInputs() {
  const templateId = runPipelineSelectedTemplateId();
  const template = selectedRunPipelineTemplate(templateId);
  const stateSelectedTemplateId = pipelineStudioState?.selected?.template_id || "";
  const inputs = templateId === stateSelectedTemplateId && Array.isArray(pipelineStudioState?.pipeline?.input_cards)
    ? pipelineStudioState.pipeline.input_cards
    : pipelineTemplateInputs(template);
  return Array.isArray(inputs) ? inputs : [];
}

function runPipelineInputPlaceholder(kind, item = {}) {
  if (kind === "path") return "templates/agent-work-app/app.js\nworkspace/runs/parallel-pipeline/execution-ui.json";
  if (kind === "image") return "workspace/runs/ui/reference.png";
  if (kind === "evidence") return "workspace/runs/pipeline/evidence.json\nworkspace/runs/pipeline/validation.log";
  if (kind === "details") return "max_parallel: 3\nruntime: api-openai\nvalidation: focused";
  if (kind === "questionnaire") return item.format || "Goal, acceptance criteria, constraints, and done definition";
  return item.format || "Manual input";
}

function runPipelineInputInitialValue(item = {}, index = 0, kind = pipelineInputType(item)) {
  const direct = String(item.answer || item.provided_answer || item.value || item.answer_notes || "").trim();
  if (direct) return direct;
  if (kind === "path") return pipelineLinesToText(item.paths || item.target_paths || item.routes);
  if (kind === "image") return pipelineLinesToText(item.image_refs || item.images || item.references);
  if (kind === "evidence") return pipelineLinesToText(item.artifacts || item.evidence_artifacts);
  const prompt = issueDescriptionInput?.value?.trim() || "";
  const firstManualIndex = currentRunPipelineInputs().findIndex((input) => pipelineInputSource(input) === "user");
  const inputId = pipelineInputId(item, index);
  if (prompt && (inputId === "operator-thoughts" || index === firstManualIndex) && ["questionnaire", "details", "text"].includes(kind)) {
    return prompt;
  }
  return "";
}

const PARALLEL_CONFIG_DEFAULTS = {
  max_parallel: "10",
  runtime: "fixture",
  integrator: "sequential",
  validation: "smoke",
  apply_mode: "dry-run",
  budget_usd: "0.00",
  max_budget_usd: "0.00",
};

const MULTIPIPELINE_CONFIG_DEFAULTS = {
  passes: "4",
  child_pipeline: "hard-proreq-task",
  execution_mode: "request-artifacts",
  ui_screenshot: "request-artifact",
  pro_call: "request-artifact",
  handoff_policy: "previous-guidance-required",
};

function runPipelineIsParallelTemplate(templateId = runPipelineSelectedTemplateId()) {
  return templateId === "parallel-pipeline";
}

function runPipelineParseKeyValueConfig(text = "") {
  const config = {};
  String(text || "").split(/\r?\n/).forEach((line) => {
    const index = line.indexOf(":");
    if (index < 0) return;
    const key = line.slice(0, index).trim().toLowerCase().replace(/[^a-z0-9_]+/g, "_").replace(/^_+|_+$/g, "");
    const value = line.slice(index + 1).trim();
    if (key && value) config[key] = value;
  });
  return config;
}

function runPipelineParallelConfigInitial(item = {}, index = 0) {
  const config = { ...PARALLEL_CONFIG_DEFAULTS };
  const parsed = runPipelineParseKeyValueConfig(runPipelineInputInitialValue(item, index, "details"));
  Object.entries(parsed).forEach(([key, value]) => {
    if (key in config) config[key] = String(value);
  });
  if (config.runtime !== "api-openai") {
    config.budget_usd = "0.00";
    config.max_budget_usd = "0.00";
  }
  return config;
}

function runPipelineMultipipelineConfigInitial(item = {}, index = 0) {
  const config = { ...MULTIPIPELINE_CONFIG_DEFAULTS };
  const parsed = runPipelineParseKeyValueConfig(runPipelineInputInitialValue(item, index, "details"));
  Object.entries(parsed).forEach(([key, value]) => {
    if (key in config) config[key] = String(value);
  });
  config.passes = "4";
  config.child_pipeline = "hard-proreq-task";
  return config;
}

function runPipelineSelectOptions(options, selected) {
  return options.map((option) => {
    const value = typeof option === "string" ? option : option.value;
    const label = typeof option === "string" ? option : option.label;
    return `<option value="${escapeHtml(value)}"${String(value) === String(selected) ? " selected" : ""}>${escapeHtml(label)}</option>`;
  }).join("");
}

function renderParallelConfigControl(item = {}, index = 0) {
  const config = runPipelineParallelConfigInitial(item, index);
  return `
    <div class="runPipelineStructuredConfig" data-config-profile="parallel" data-run-pipeline-input-index="${index}" data-run-pipeline-input-id="parallel-ui-config" data-runtime="${escapeHtml(config.runtime)}">
      <label><span>Max parallel</span><select data-run-pipeline-config="max_parallel">${runPipelineSelectOptions(["3", "5", "10", "12"], config.max_parallel)}</select></label>
      <label><span>Runtime</span><select data-run-pipeline-config="runtime">${runPipelineSelectOptions([
        { value: "fixture", label: "Fixture dry run" },
        { value: "api-openai", label: "API workers" }
      ], config.runtime)}</select></label>
      <label><span>Integrator</span><select data-run-pipeline-config="integrator">${runPipelineSelectOptions([
        { value: "sequential", label: "Sequential deterministic" },
        { value: "sequential-review", label: "Sequential + fallback review" }
      ], config.integrator)}</select></label>
      <label><span>Validation</span><select data-run-pipeline-config="validation">${runPipelineSelectOptions([
        { value: "smoke", label: "Smoke" },
        { value: "focused", label: "Focused" }
      ], config.validation)}</select></label>
      <label><span>Apply mode</span><select data-run-pipeline-config="apply_mode">${runPipelineSelectOptions([
        { value: "dry-run", label: "Dry-run / no apply" },
        { value: "apply", label: "Apply accepted patches" }
      ], config.apply_mode)}</select></label>
      <label class="runPipelineBudgetField"><span>Budget target</span><input data-run-pipeline-config="budget_usd" type="number" min="0" step="0.01" value="${escapeHtml(config.budget_usd)}"></label>
      <label class="runPipelineBudgetField"><span>Hard cap</span><input data-run-pipeline-config="max_budget_usd" type="number" min="0" step="0.01" value="${escapeHtml(config.max_budget_usd)}"></label>
    </div>
  `;
}

function renderMultipipelineConfigControl(item = {}, index = 0) {
  const config = runPipelineMultipipelineConfigInitial(item, index);
  return `
    <div class="runPipelineStructuredConfig" data-config-profile="multipipeline" data-run-pipeline-input-index="${index}" data-run-pipeline-input-id="multipipeline-schedule-config">
      <label><span>Passes</span><select data-run-pipeline-config="passes">${runPipelineSelectOptions(["4"], config.passes)}</select></label>
      <label><span>Child pipeline</span><select data-run-pipeline-config="child_pipeline">${runPipelineSelectOptions([{ value: "hard-proreq-task", label: "Hard ProReq" }], config.child_pipeline)}</select></label>
      <label><span>Execution</span><select data-run-pipeline-config="execution_mode">${runPipelineSelectOptions([
        { value: "request-artifacts", label: "Request artifacts" },
        { value: "live-child-runs", label: "Live child runs" }
      ], config.execution_mode)}</select></label>
      <label><span>UI screenshot</span><select data-run-pipeline-config="ui_screenshot">${runPipelineSelectOptions([
        { value: "request-artifact", label: "Request artifact" },
        { value: "live-image", label: "Live image opt-in" }
      ], config.ui_screenshot)}</select></label>
      <label><span>Pro call</span><select data-run-pipeline-config="pro_call">${runPipelineSelectOptions([
        { value: "request-artifact", label: "Request artifact" },
        { value: "live-pro", label: "Live Pro opt-in" }
      ], config.pro_call)}</select></label>
      <label><span>Handoff</span><select data-run-pipeline-config="handoff_policy">${runPipelineSelectOptions([
        { value: "previous-guidance-required", label: "Previous guidance required" },
        { value: "advisory", label: "Advisory" }
      ], config.handoff_policy)}</select></label>
    </div>
  `;
}

function runPipelineQuestionId(question = {}, index = 0) {
  const raw = String(question.id || question.key || question.name || question.prompt || question.question || "").trim();
  const slug = raw.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return slug || `question-${index + 1}`;
}

function renderRunPipelineQuestionControl(question = {}, inputIndex = 0, questionIndex = 0, required = false, optionsOverride = {}) {
  const questionId = runPipelineQuestionId(question, questionIndex);
  const label = question.prompt || question.question || question.label || questionId;
  const answerType = String(question.answer_type || question.type || "text").toLowerCase();
  const options = Array.isArray(question.options) ? question.options.map((option) => String(option || "").trim()).filter(Boolean) : [];
  const requiredAttr = required && question.required !== false ? " required" : "";
  if (options.length) {
    return `
      <label class="runPipelineQuestion">
        <span>${escapeHtml(label)}</span>
        <select data-run-pipeline-input-index="${inputIndex}" data-run-pipeline-question-id="${escapeHtml(questionId)}"${requiredAttr}>
          <option value="">Select...</option>
          ${options.map((option) => `<option value="${escapeHtml(option)}">${escapeHtml(option)}</option>`).join("")}
        </select>
      </label>
    `;
  }
  const rows = optionsOverride.forceTextarea ? Number(optionsOverride.rows || 4) : (answerType === "long" || answerType === "textarea" || String(label).length > 80 ? 3 : 1);
  const tag = rows > 1 ? "textarea" : "input";
  if (tag === "textarea") {
    return `
      <label class="runPipelineQuestion">
        <span>${escapeHtml(label)}</span>
        <textarea data-run-pipeline-input-index="${inputIndex}" data-run-pipeline-question-id="${escapeHtml(questionId)}" rows="${rows}"${requiredAttr}></textarea>
      </label>
    `;
  }
  return `
    <label class="runPipelineQuestion">
      <span>${escapeHtml(label)}</span>
      <input type="text" data-run-pipeline-input-index="${inputIndex}" data-run-pipeline-question-id="${escapeHtml(questionId)}"${requiredAttr} />
    </label>
  `;
}

function renderRunPipelineInputControl(item = {}, index = 0, kind = pipelineInputType(item), source = pipelineInputSource(item)) {
  const inputId = pipelineInputId(item, index);
  const required = item.required !== false;
  const requiredAttr = required ? " required" : "";
  if (source === "auto") {
    const automation = pipelineInputAutomation(item);
    return `
      <details class="runPipelineAutoInput" aria-readonly="true">
        <summary><strong>Automated</strong><span>${escapeHtml(automation ? `Generated by ${automation}` : "Resolved during pipeline execution")}</span></summary>
        <p>${escapeHtml(item.evidence_policy || item.path_policy || item.detail || "Resolved during pipeline execution.")}</p>
      </details>
    `;
  }
  const initialValue = runPipelineInputInitialValue(item, index, kind);
  const placeholder = runPipelineInputPlaceholder(kind, item);
  if (inputId === "parallel-ui-config") {
    return renderParallelConfigControl(item, index);
  }
  if (inputId === "multipipeline-schedule-config") {
    return renderMultipipelineConfigControl(item, index);
  }
  if (inputId === "parallel-workstreams") {
    return `
      <details class="runPipelineAdvancedInput">
        <summary><strong>Auto-generated by default</strong><span>Open only to override worker paths or provide JSON workstreams.</span></summary>
        <textarea data-run-pipeline-input-index="${index}" data-run-pipeline-input-id="${escapeHtml(inputId)}" rows="5" placeholder="${escapeHtml(placeholder)}">${escapeHtml(initialValue)}</textarea>
      </details>
    `;
  }
  if (kind === "questionnaire" && Array.isArray(item.questions) && item.questions.length) {
    const isParallelObjective = inputId === "parallel-objective";
    const isMultipipelineObjective = inputId === "multipipeline-objective";
    return `
      <div class="runPipelineQuestionGrid${isParallelObjective || isMultipipelineObjective ? " objective" : ""}">
        ${item.questions.map((question, questionIndex) => renderRunPipelineQuestionControl(question, index, questionIndex, required, isParallelObjective || isMultipipelineObjective ? { forceTextarea: true, rows: questionIndex === 2 ? 3 : 4 } : {})).join("")}
      </div>
    `;
  }
  if (kind === "path" || kind === "evidence" || kind === "details" || kind === "questionnaire" || kind === "text") {
    const rows = kind === "path" || kind === "evidence" ? 3 : 4;
    return `
      <textarea data-run-pipeline-input-index="${index}" data-run-pipeline-input-id="${escapeHtml(inputId)}" rows="${rows}" placeholder="${escapeHtml(placeholder)}"${requiredAttr}>${escapeHtml(initialValue)}</textarea>
    `;
  }
  if (kind === "image") {
    return `
      <input type="text" data-run-pipeline-input-index="${index}" data-run-pipeline-input-id="${escapeHtml(inputId)}" placeholder="${escapeHtml(placeholder)}" value="${escapeHtml(initialValue)}"${requiredAttr} />
    `;
  }
  return `
    <input type="text" data-run-pipeline-input-index="${index}" data-run-pipeline-input-id="${escapeHtml(inputId)}" placeholder="${escapeHtml(placeholder)}" value="${escapeHtml(initialValue)}"${requiredAttr} />
  `;
}

function renderRunPipelineInputCards() {
  if (!runPipelineInputCards) return;
  refreshRunPipelineTemplateSelect();
  const template = selectedRunPipelineTemplate();
  const inputs = currentRunPipelineInputs();
  const manualCount = inputs.filter((item) => pipelineInputSource(item) === "user" && item.required !== false).length;
  const advancedCount = inputs.filter((item) => pipelineInputSource(item) === "user" && item.required === false).length;
  const autoCount = inputs.filter((item) => pipelineInputSource(item) === "auto").length;
  const project = pipelineProjectListForRun().find((item) => item.id === runPipelineProjectForTemplate(template.id || runPipelineSelectedTemplateId()));
  if (runPipelineRouteTitle) {
    runPipelineRouteTitle.textContent = template.label || template.id || "Selected route";
  }
  if (runPipelineRouteDescription) {
    runPipelineRouteDescription.textContent = `${manualCount} required manual input${manualCount === 1 ? "" : "s"}, ${advancedCount} advanced override${advancedCount === 1 ? "" : "s"}, ${autoCount} automated input${autoCount === 1 ? "" : "s"} resolved by the pipeline${project?.label ? ` · ${project.label}` : ""}.`;
  }
  if (!inputs.length) {
    runPipelineInputCards.innerHTML = `
      <article class="runPipelineInputCard automated configured empty" data-run-input-id="no-manual-inputs">
        <b>0</b>
        <div class="runPipelineInputCardBody">
          <div class="runPipelineInputCopy">
            <strong>No manual inputs</strong>
            <span>This pipeline can run from its configured template contract.</span>
            <small>Automated route</small>
          </div>
          <div class="runPipelineInputControl">
            <div class="runPipelineAutoInput" aria-readonly="true"><strong>Ready</strong><span>No operator form fields required</span></div>
          </div>
        </div>
      </article>
    `;
    return;
  }
  runPipelineInputCards.innerHTML = inputs.map((item, index) => {
    const kind = pipelineInputType(item);
    const source = pipelineInputSource(item);
    const automation = pipelineInputAutomation(item);
    const status = String(item.status || (source === "auto" ? "configured" : "missing")).toLowerCase();
    const inputId = pipelineInputId(item, index);
    const requirement = item.required === false ? "Optional" : "Required";
    const variantClass = [
      inputId === "parallel-objective" ? "objective" : "",
      inputId === "parallel-workstreams" ? "advanced" : "",
      source === "auto" ? "collapsedAuto" : "",
    ].filter(Boolean).join(" ");
    return `
      <article class="runPipelineInputCard ${source === "auto" ? "automated" : "manual"} ${escapeHtml(status)} ${escapeHtml(variantClass)}" data-run-input-id="${escapeHtml(inputId)}">
        <b>${index + 1}</b>
        <div class="runPipelineInputCardBody">
          <div class="runPipelineInputCopy">
            <strong>${escapeHtml(item.title || inputId)}</strong>
            <span>${escapeHtml(item.detail || item.evidence_policy || item.path_policy || "")}</span>
            <small>${escapeHtml(pipelineInputTypeLabel(kind))} · ${escapeHtml(source === "auto" ? `Auto${automation ? `: ${automation}` : ""}` : `${requirement} user input`)}</small>
          </div>
          <div class="runPipelineInputControl">
            ${renderRunPipelineInputControl(item, index, kind, source)}
          </div>
        </div>
      </article>
    `;
  }).join("");
}

function runPipelineInputValue(index) {
  const structured = runPipelineInputCards?.querySelector(`.runPipelineStructuredConfig[data-run-pipeline-input-index="${index}"]`);
  if (structured) {
    const values = {};
    structured.querySelectorAll("[data-run-pipeline-config]").forEach((control) => {
      const key = control.getAttribute("data-run-pipeline-config") || "";
      if (key) values[key] = String(control.value || "").trim();
    });
    if (values.runtime !== "api-openai") {
      values.budget_usd = "0.00";
      values.max_budget_usd = "0.00";
    }
    if (structured.dataset.configProfile === "multipipeline") {
      return [
        `passes: ${values.passes || MULTIPIPELINE_CONFIG_DEFAULTS.passes}`,
        `child_pipeline: ${values.child_pipeline || MULTIPIPELINE_CONFIG_DEFAULTS.child_pipeline}`,
        `execution_mode: ${values.execution_mode || MULTIPIPELINE_CONFIG_DEFAULTS.execution_mode}`,
        `ui_screenshot: ${values.ui_screenshot || MULTIPIPELINE_CONFIG_DEFAULTS.ui_screenshot}`,
        `pro_call: ${values.pro_call || MULTIPIPELINE_CONFIG_DEFAULTS.pro_call}`,
        `handoff_policy: ${values.handoff_policy || MULTIPIPELINE_CONFIG_DEFAULTS.handoff_policy}`,
      ].join("\n");
    }
    return [
      `max_parallel: ${values.max_parallel || PARALLEL_CONFIG_DEFAULTS.max_parallel}`,
      `runtime: ${values.runtime || PARALLEL_CONFIG_DEFAULTS.runtime}`,
      `integrator: ${values.integrator || PARALLEL_CONFIG_DEFAULTS.integrator}`,
      `validation: ${values.validation || PARALLEL_CONFIG_DEFAULTS.validation}`,
      `apply_mode: ${values.apply_mode || PARALLEL_CONFIG_DEFAULTS.apply_mode}`,
      `budget_usd: ${values.budget_usd || PARALLEL_CONFIG_DEFAULTS.budget_usd}`,
      `max_budget_usd: ${values.max_budget_usd || PARALLEL_CONFIG_DEFAULTS.max_budget_usd}`,
    ].join("\n");
  }
  const control = runPipelineInputCards?.querySelector(`[data-run-pipeline-input-index="${index}"][data-run-pipeline-input-id]`);
  return String(control?.value || "").trim();
}

function runPipelineQuestionAnswers(index) {
  const answers = {};
  runPipelineInputCards?.querySelectorAll(`[data-run-pipeline-input-index="${index}"][data-run-pipeline-question-id]`).forEach((control) => {
    const questionId = control.getAttribute("data-run-pipeline-question-id") || "";
    const value = String(control.value || "").trim();
    if (questionId && value) answers[questionId] = value;
  });
  return answers;
}

function runPipelineInputPayload(item, index) {
  const inputId = pipelineInputId(item, index);
  const kind = pipelineInputType(item);
  const source = pipelineInputSource(item);
  const base = { id: inputId, kind, source };
  const screenshotPath = runPipelineScreenshotInput?.value?.trim() || "";
  if (source === "auto") {
    if (kind === "image" && inputId === "ui-screenshot-request" && screenshotPath) {
      return { ...base, image_refs: [screenshotPath], image_notes: "Operator-provided optional screenshot context." };
    }
    return base;
  }
  const manualValue = runPipelineInputValue(index);
  const prompt = issueDescriptionInput.value.trim();
  const value = manualValue || (inputId === "operator-thoughts" ? prompt : "");
  if (kind === "questionnaire") {
    const answers = runPipelineQuestionAnswers(index);
    const answer = value || Object.entries(answers).map(([key, answerValue]) => `${key}: ${answerValue}`).join("\n");
    return { ...base, answer, answers };
  }
  if (kind === "details" || kind === "text") return { ...base, answer: value };
  if (kind === "path") return { ...base, paths: pipelineTextToLines(value) };
  if (kind === "image") {
    const imageRefs = pipelineTextToLines(value || screenshotPath);
    return { ...base, image_refs: imageRefs, image_notes: value };
  }
  if (kind === "evidence") return { ...base, artifacts: pipelineTextToLines(value), evidence_policy: value };
  return base;
}

function syncRunPipelineStructuredConfig(control) {
  const container = control?.closest?.(".runPipelineStructuredConfig");
  if (!container) return;
  const runtime = container.querySelector('[data-run-pipeline-config="runtime"]')?.value || PARALLEL_CONFIG_DEFAULTS.runtime;
  container.dataset.runtime = runtime;
  if (runtime !== "api-openai") {
    const budget = container.querySelector('[data-run-pipeline-config="budget_usd"]');
    const cap = container.querySelector('[data-run-pipeline-config="max_budget_usd"]');
    if (budget) budget.value = "0.00";
    if (cap) cap.value = "0.00";
  }
}

function runPipelinePayload() {
  const inputs = currentRunPipelineInputs();
  const templateId = runPipelineSelectedTemplateId();
  return {
    schema_version: "cento.pipeline_run_request.v1",
    project_id: runPipelineProjectForTemplate(templateId),
    template_id: templateId,
    inputs: inputs.map(runPipelineInputPayload),
  };
}

function pipelineElementIcon(name) {
  const paths = {
    pencil: '<path d="M4 13.5V16h2.5L14 8.5 11.5 6 4 13.5Z"></path><path d="m10.8 6.7 1.5-1.5a1.4 1.4 0 0 1 2 0l.5.5a1.4 1.4 0 0 1 0 2l-1.5 1.5"></path>',
    trash: '<path d="M3.5 5h9"></path><path d="M6 5V3.8c0-.5.4-.8.8-.8h2.4c.4 0 .8.3.8.8V5"></path><path d="M5 6.5 5.6 14c0 .6.5 1 1.1 1h2.6c.6 0 1.1-.4 1.1-1l.6-7.5"></path>',
  };
  return `<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">${paths[name] || ""}</svg>`;
}

function pipelineCardActionButtons(type, id, title = "") {
  const safeType = escapeHtml(type);
  const safeId = escapeHtml(id);
  const safeTitle = escapeHtml(title || id || "element");
  return `
    <div class="pipelineCardActions" aria-label="Element actions">
      <button class="pipelineCardIconButton" type="button" data-pipeline-card-action="edit" data-element-type="${safeType}" data-element-id="${safeId}" aria-label="Edit ${safeTitle}" title="Edit">${pipelineElementIcon("pencil")}</button>
      <button class="pipelineCardIconButton danger" type="button" data-pipeline-card-action="delete" data-element-type="${safeType}" data-element-id="${safeId}" aria-label="Remove ${safeTitle}" title="Remove">${pipelineElementIcon("trash")}</button>
    </div>
  `;
}

function pipelineStageFooterButton(stage) {
  return Array.from(stage?.children || []).find((child) => child.tagName === "BUTTON") || null;
}

function pipelineInputId(item, index = 0) {
  const existing = String(item?.id || "").trim();
  if (existing) return existing;
  const title = String(item?.title || "").trim();
  const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return slug || `input-${index + 1}`;
}

function pipelineInputAnswerPresent(item = {}) {
  return Boolean(
    item.answer_present ||
    String(item.answer || item.provided_answer || "").trim() ||
    String(item.answer_notes || item.provided_notes || "").trim() ||
    (Array.isArray(item.answer_values) && item.answer_values.length) ||
    (Array.isArray(item.provided_values) && item.provided_values.length)
  );
}

function renderPipelineInputCards(items) {
  const inputStage = document.querySelector(".stageInput");
  if (!inputStage) return;
  inputStage.querySelectorAll(".pipelineCard").forEach((card) => card.remove());
  const button = pipelineStageFooterButton(inputStage);
  const inputItems = items || [];
  inputStage.classList.toggle("inputSequenceList", inputItems.length > 1);
  inputItems.forEach((item, index) => {
    const card = document.createElement("div");
    const status = String(item.status || "Missing").toLowerCase();
    const inputId = pipelineInputId(item, index);
    const inputType = pipelineInputType(item);
    const hasAnswer = pipelineInputAnswerPresent(item);
    card.className = `pipelineCard operatorInput ${status} inputType-${inputType} ${pipelineSelectedInputId === inputId ? "selected" : ""}`;
    card.dataset.inputId = inputId;
    card.dataset.sequenceIndex = String(index + 1);
    card.dataset.sequenceLast = String(index === inputItems.length - 1);
    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");
    card.setAttribute("aria-pressed", String(pipelineSelectedInputId === inputId));
    card.innerHTML = `
      <b class="pipelineInputSequenceNode">${index + 1}</b>
      <div class="pipelineInputCardContent">
        <div class="pipelineInputCardTitle">
          <i class="pipelineInputTypeMark">${escapeHtml(pipelineInputTypeIcon(inputType))}</i>
          <strong>${escapeHtml(item.title || "")}</strong>
        </div>
        <span>${escapeHtml(item.detail || item.file || item.manifest || "")}</span>
        <div class="pipelineInputCardMeta">
          <small>${escapeHtml(pipelineInputTypeLabel(inputType))}</small>
          <small class="pipelineCardAnswer ${hasAnswer ? "answered" : ""}">${hasAnswer ? "Answer saved" : "Needs answer"}</small>
        </div>
      </div>
      ${pipelineCardActionButtons("input", inputId, item.title || "input")}
    `;
    inputStage.insertBefore(card, button || null);
  });
  if (button) button.textContent = `View all (${inputItems.length})`;
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
  const button = pipelineStageFooterButton(integrationStage);
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
      ${pipelineCardActionButtons("integration", integrationId, item.title || "integration")}
    `;
    integrationStage.insertBefore(card, button || null);
  });
  const headerCount = integrationStage.querySelector("header span");
  if (headerCount) {
    const factoryLabel = document.querySelector('[data-pipeline-field="factoryStageLabel"]')?.textContent || "";
    const defaultSuffix = factoryLabel.toLowerCase().includes("factory") ? "execution steps" : "integration steps";
    headerCount.textContent = pipelineStudioState?.pipeline?.integration_count || `${(items || []).length} ${defaultSuffix}`;
  }
  if (button) button.textContent = `View all (${(items || []).length})`;
}

function renderPipelineValidatorCards(items) {
  const validateStage = document.querySelector(".stageValidate");
  if (!validateStage) return;
  validateStage.querySelectorAll(".pipelineCard.validator").forEach((card) => card.remove());
  const button = pipelineStageFooterButton(validateStage);
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
      ${mode === "evidence" || validatorId === "screenshot" ? `<div class="pipelineThumb" aria-hidden="true"><span></span><span></span><span></span><span></span></div>` : ""}
      ${pipelineCardActionButtons("validation", validatorId, item.title || "validator")}
    `;
    validateStage.insertBefore(card, button || null);
  });
  const headerCount = validateStage.querySelector("header span");
  if (headerCount) headerCount.textContent = `${(items || []).length} validators`;
  if (button) button.textContent = `View all (${(items || []).length})`;
}

function pipelineEvidenceId(item, index = 0) {
  const raw = String(item?.id || item?.title || "").trim();
  const slug = raw.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return slug || `evidence-${index + 1}`;
}

function renderPipelineEvidenceCards(items) {
  const evidenceStage = document.querySelector(".stageEvidence");
  if (!evidenceStage) return;
  evidenceStage.querySelectorAll(".pipelineCard.evidence").forEach((card) => card.remove());
  const button = pipelineStageFooterButton(evidenceStage);
  (items || []).forEach((item, index) => {
    const evidenceId = pipelineEvidenceId(item, index);
    const state = String(item.state || item.status || "configured").toLowerCase().replace(/\s+/g, "-");
    const card = document.createElement("div");
    card.className = `pipelineCard evidence ${state} ${pipelineSelectedEvidenceId === evidenceId ? "selected" : ""}`;
    card.dataset.evidenceId = evidenceId;
    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");
    card.setAttribute("aria-pressed", String(pipelineSelectedEvidenceId === evidenceId));
    const statusText = escapeHtml(item.status || titleCasePipelineStatus(item.state || "Configured"));
    const statusNode = /events|\$/.test(String(item.status || "")) ? `<small>${statusText}</small>` : `<em>${statusText}</em>`;
    card.innerHTML = `
      <i>▧</i>
      <strong>${escapeHtml(item.title || "")}</strong>
      <span>${escapeHtml(item.file || item.path || "evidence.json")}</span>
      ${statusNode}
      ${pipelineCardActionButtons("evidence", evidenceId, item.title || "evidence")}
    `;
    evidenceStage.insertBefore(card, button || null);
  });
  const headerCount = evidenceStage.querySelector("header span");
  if (headerCount) headerCount.textContent = `${(items || []).length} artifacts`;
  if (button) button.textContent = `View all (${(items || []).length})`;
}

function workerStageKey(worker, index = 0) {
  const raw = String(worker?.stage || worker?.stage_kind || worker?.lane || "").trim().toLowerCase().replaceAll("_", "-");
  if (raw === "blueprint" || raw === "change-blueprint" || raw === "plan") return "blueprint";
  if (raw === "repo" || raw === "repo-discovery" || raw === "context") return "repo";
  if (String(worker?.id || "").includes("blueprint") || String(worker?.id || "") === "plan") return "blueprint";
  return index === 1 ? "blueprint" : "repo";
}

function renderPipelineWorkerCards(items) {
  const stages = {
    repo: document.querySelector(".stageWorkers"),
    blueprint: document.querySelector(".stageBlueprint")
  };
  Object.values(stages).forEach((stage) => {
    stage?.querySelectorAll(".pipelineCard.worker").forEach((card) => card.remove());
  });
  const counts = { repo: 0, blueprint: 0 };
  (items || []).forEach((worker, index) => {
    const stageKey = workerStageKey(worker, index);
    const stage = stages[stageKey] || stages.repo;
    const button = pipelineStageFooterButton(stage);
    if (!stage) return;
    counts[stageKey] = (counts[stageKey] || 0) + 1;
    const card = document.createElement("div");
    card.className = `pipelineCard worker ${worker.selected ? "selected" : ""}`;
    card.dataset.workerId = worker.id || "";
    card.setAttribute("role", "button");
    card.setAttribute("tabindex", "0");
    card.setAttribute("aria-pressed", String(Boolean(worker.selected)));
    card.innerHTML = `
      <i>▧</i>
      <strong>${escapeHtml(worker.title || worker.id || "Contract")}</strong>
      <span>${escapeHtml(worker.file || worker.detail || "")}</span>
      <em>${escapeHtml(worker.status || "Ready")}</em>
      ${pipelineCardActionButtons("worker", worker.id || "", worker.title || worker.id || "worker")}
    `;
    stage.insertBefore(card, button || null);
  });
  Object.entries(stages).forEach(([stageKey, stage]) => {
    const count = counts[stageKey] || 0;
    const label = `${count} ${count === 1 ? "contract" : "contracts"}`;
    const headerCount = stage?.querySelector(`[data-worker-stage-count="${stageKey}"]`);
    const button = pipelineStageFooterButton(stage);
    if (headerCount) headerCount.textContent = label;
    if (button) button.textContent = `View all (${count})`;
  });
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

function selectedPipelineEvidence(evidenceId = pipelineSelectedEvidenceId) {
  const evidence = pipelineStudioState?.pipeline?.evidence || [];
  return (evidence || []).find((item, index) => pipelineEvidenceId(item, index) === evidenceId) || null;
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

function setPipelineInspectorMode(mode) {
  const inputMode = mode === "input";
  const integrationMode = mode === "integration";
  const validationMode = mode === "validation";
  const evidenceMode = mode === "evidence";
  const workerMode = !inputMode && !integrationMode && !validationMode && !evidenceMode;
  pipelineInputInspector?.classList.toggle("hidden", !inputMode);
  pipelineIntegrationInspector?.classList.toggle("hidden", !integrationMode);
  pipelineValidationInspector?.classList.toggle("hidden", !validationMode);
  pipelineEvidenceInspector?.classList.toggle("hidden", !evidenceMode);
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
  pipelineSelectedEvidenceId = "";
  if (pipelineInspectorBadge) pipelineInspectorBadge.textContent = "W1";
  if (pipelineInspectorState) pipelineInspectorState.textContent = "Completed";
  renderPipelineInputCards(pipelineStudioState?.pipeline?.input_cards || selectedPipelinePayloadTemplate()?.required_inputs || selectedPipelineStudioTemplate()?.requiredInputs || []);
  renderPipelineIntegrationCards(pipelineStudioState?.pipeline?.integration || []);
  renderPipelineValidatorCards(pipelineStudioState?.pipeline?.validators || selectedPipelinePayloadTemplate()?.validators || []);
  renderPipelineEvidenceCards(pipelineStudioState?.pipeline?.evidence || []);
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
  pipelineSelectedEvidenceId = "";
  setPipelineInspectorMode("input");
  setPipelineField("selectedWorker", input.title || "Input");
  if (pipelineInspectorBadge) pipelineInspectorBadge.textContent = "Input";
  if (pipelineInspectorState) pipelineInspectorState.textContent = titleCasePipelineStatus(status);
  if (pipelineInputTitleInput) pipelineInputTitleInput.value = input.title || "";
  if (pipelineInputTypeSelect) pipelineInputTypeSelect.value = pipelineInputType(input);
  if (pipelineInputSourceSelect) pipelineInputSourceSelect.value = pipelineInputSource(input);
  if (pipelineInputDetailInput) pipelineInputDetailInput.value = input.detail || input.file || "";
  if (pipelineInputStatusSelect) {
    pipelineInputStatusSelect.value = status;
    pipelineInputStatusSelect.dataset.initialStatus = status;
  }
  if (pipelineInputAutomationInput) pipelineInputAutomationInput.value = pipelineInputAutomation(input);
  if (pipelineInputRequiredCheckbox) pipelineInputRequiredCheckbox.checked = input.required !== false;
  if (pipelineInputMutedCheckbox) pipelineInputMutedCheckbox.checked = Boolean(input.muted || status === "muted" || input.blocking === false);
  if (pipelineInputFormatInput) pipelineInputFormatInput.value = input.format || PIPELINE_INPUT_TYPES[pipelineInputType(input)]?.format || "";
  if (pipelineInputImageRefsInput) pipelineInputImageRefsInput.value = pipelineLinesToText(input.image_refs || input.images || input.references);
  if (pipelineInputImageNotesInput) pipelineInputImageNotesInput.value = input.image_notes || input.reference_notes || "";
  if (pipelineInputQuestionsInput) pipelineInputQuestionsInput.value = pipelineQuestionItemsToText(input.questions || input.questionnaire);
  if (pipelineInputPathsInput) pipelineInputPathsInput.value = pipelineLinesToText(input.paths || input.target_paths || input.routes);
  if (pipelineInputPathPolicyInput) pipelineInputPathPolicyInput.value = input.path_policy || input.ownership_policy || "";
  if (pipelineInputArtifactsInput) pipelineInputArtifactsInput.value = pipelineLinesToText(input.artifacts || input.evidence_artifacts);
  if (pipelineInputEvidencePolicyInput) pipelineInputEvidencePolicyInput.value = input.evidence_policy || input.validation_policy || "";
  if (pipelineInputAnswerInput) pipelineInputAnswerInput.value = input.answer || input.provided_answer || "";
  if (pipelineInputAnswerValuesInput) pipelineInputAnswerValuesInput.value = pipelineLinesToText(input.answer_values || input.provided_values || input.provided_paths);
  if (pipelineInputAnswerNotesInput) pipelineInputAnswerNotesInput.value = input.answer_notes || input.provided_notes || "";
  if (pipelineInputAnswerState) {
    pipelineInputAnswerState.textContent = pipelineInputAnswerPresent(input)
      ? `Answer saved${input.provided_at ? ` at ${new Date(input.provided_at).toLocaleTimeString()}` : ""}`
      : "No answer saved yet";
  }
  if (pipelineInputManifestPath) pipelineInputManifestPath.textContent = input.manifest ? `Input manifest: ${input.manifest}` : "Input manifest output pending";
  updatePipelineInputTypeEditors(pipelineInputType(input));
  renderPipelineImagePreviews(pipelineInputImagePreview, [
    ...pipelineValueList(input.image_refs || input.images || input.references),
    ...pipelineValueList(input.artifacts || input.evidence_artifacts),
    ...pipelineValueList(input.answer_values || input.provided_values || input.provided_paths),
  ]);
  if (pipelineInputInspectorStatus) pipelineInputInspectorStatus.textContent = message || "Edit the input contract or provide run configuration, then save.";
  renderPipelineInputCards(pipelineStudioState?.pipeline?.input_cards || selectedPipelinePayloadTemplate()?.required_inputs || selectedPipelineStudioTemplate()?.requiredInputs || []);
  renderPipelineIntegrationCards(pipelineStudioState?.pipeline?.integration || []);
  renderPipelineValidatorCards(pipelineStudioState?.pipeline?.validators || selectedPipelinePayloadTemplate()?.validators || []);
  renderPipelineEvidenceCards(pipelineStudioState?.pipeline?.evidence || []);
  syncPipelineWorkerCards(pipelineStudioState?.pipeline?.workers || selectedPipelineStudioTemplate()?.workers || []);
}

function collectPipelineInputConfig() {
  const selected = selectedPipelineInput() || {};
  const kind = pipelineInputType({ kind: pipelineInputTypeSelect?.value || selected.kind || selected.input_type || selected.type });
  const answer = pipelineInputAnswerInput?.value?.trim() || "";
  const answerValues = pipelineTextToLines(pipelineInputAnswerValuesInput?.value || "");
  const answerNotes = pipelineInputAnswerNotesInput?.value?.trim() || "";
  const answerPresent = Boolean(answer || answerValues.length || answerNotes);
  const selectedStatus = pipelineInputStatusSelect?.value || "missing";
  const initialStatus = pipelineInputStatusSelect?.dataset.initialStatus || selected.status || "missing";
  const status = answerPresent && selectedStatus === initialStatus && selectedStatus !== "optional"
    ? "provided"
    : selectedStatus;
  return {
    ...selected,
    id: pipelineSelectedInputId,
    title: pipelineInputTitleInput?.value?.trim() || selected.title || "Untitled input",
    detail: pipelineInputDetailInput?.value?.trim() || "",
    kind,
    input_type: kind,
    source: pipelineInputSourceSelect?.value || selected.source || "user",
    automation: pipelineInputAutomationInput?.value?.trim() || selected.automation || selected.automation_source || "",
    automation_source: pipelineInputAutomationInput?.value?.trim() || selected.automation_source || selected.automation || "",
    muted: Boolean(pipelineInputMutedCheckbox?.checked),
    blocking: !Boolean(pipelineInputMutedCheckbox?.checked),
    status,
    required: Boolean(pipelineInputRequiredCheckbox?.checked),
    format: pipelineInputFormatInput?.value?.trim() || PIPELINE_INPUT_TYPES[kind]?.format || "",
    image_refs: pipelineTextToLines(pipelineInputImageRefsInput?.value || ""),
    image_notes: pipelineInputImageNotesInput?.value?.trim() || "",
    questions: pipelineTextToQuestionItems(pipelineInputQuestionsInput?.value || ""),
    paths: pipelineTextToLines(pipelineInputPathsInput?.value || ""),
    path_policy: pipelineInputPathPolicyInput?.value?.trim() || "",
    artifacts: pipelineTextToLines(pipelineInputArtifactsInput?.value || ""),
    evidence_policy: pipelineInputEvidencePolicyInput?.value?.trim() || "",
    answer,
    answer_values: answerValues,
    answer_notes: answerNotes,
    answer_present: answerPresent,
    provided_at: answerPresent ? selected.provided_at || new Date().toISOString() : "",
    manifest: selected.manifest || ""
  };
}

async function savePipelineSelectedInput() {
  if (!pipelineSelectedInputId) return;
  const values = collectPipelineInputConfig();
  if (pipelineInputInspectorStatus) pipelineInputInspectorStatus.textContent = "Saving input...";
  const payload = await savePipelineDraft("save_input", { includeManifest: false, inputConfig: values });
  if (payload) {
    pipelineSelectedInputId = values.id || pipelineSelectedInputId;
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
  if (pipelineValidationRunButton) {
    pipelineValidationRunButton.textContent = `Run ${validationModeLabel(mode)}`;
  }
  const validator = selectedPipelineValidator();
  if (validator) renderPipelineValidationRunResults(validator, mode);
}

function validationModeLabel(mode = "commands") {
  const labels = {
    commands: "commands",
    evidence: "evidence",
    gates: "gates",
    schema: "schema"
  };
  return labels[mode] || "validation";
}

function validationResultLabel(item = {}) {
  return item.command || item.path || item.gate || item.resolved_path || item.id || "validation result";
}

function renderPipelineValidationRunResults(validator = {}, mode = "commands") {
  if (!pipelineValidationRunResults) return;
  const results = validator.results && typeof validator.results === "object" ? validator.results : {};
  const items = Array.isArray(results[mode]) ? results[mode] : [];
  const status = validator.last_run_status || validator.status || "configured";
  if (pipelineValidationRunStatus) {
    const activeStatus = items.length ? resultCollectionStatus(items) : "";
    const lastMode = validator.last_run_mode ? validationModeLabel(validator.last_run_mode) : "";
    const when = validator.executed_at ? ` at ${new Date(validator.executed_at).toLocaleTimeString()}` : "";
    pipelineValidationRunStatus.textContent = items.length
      ? `${validationModeLabel(mode)} ${activeStatus}${when}`
      : validator.executed_at
        ? `Last run: ${lastMode} ${status}${when}`
        : "No execution yet";
  }
  if (!items.length) {
    pipelineValidationRunResults.innerHTML = `
      <header><strong>${escapeHtml(validationModeLabel(mode))} results</strong><span>Run this tab to write execution results.</span></header>
      <p>No ${escapeHtml(validationModeLabel(mode))} results recorded yet.</p>
    `;
    return;
  }
  pipelineValidationRunResults.innerHTML = `
    <header><strong>${escapeHtml(validationModeLabel(mode))} results</strong><span>${items.length} check${items.length === 1 ? "" : "s"} recorded</span></header>
    <div>
      ${items.map((item) => {
        const resultStatus = String(item.status || "configured").toLowerCase();
        const details = item.details || (typeof item.returncode !== "undefined" ? `exit ${item.returncode}` : "");
        return `
          <article class="${escapeHtml(resultStatus)}">
            <b>${escapeHtml(resultStatus)}</b>
            <strong>${escapeHtml(validationResultLabel(item))}</strong>
            <span>${escapeHtml(details)}</span>
          </article>
        `;
      }).join("")}
    </div>
  `;
}

function resultCollectionStatus(items) {
  const statuses = new Set((items || []).map((item) => String(item.status || "").toLowerCase()).filter(Boolean));
  if (!statuses.size) return "not run";
  if (statuses.has("failed")) return "failed";
  if (statuses.has("warning")) return "warning";
  if ([...statuses].every((status) => status === "passed" || status === "accepted")) return "passed";
  return "recorded";
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
  pipelineSelectedEvidenceId = "";
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
  renderPipelineEvidenceCards(pipelineStudioState?.pipeline?.evidence || []);
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
  pipelineSelectedEvidenceId = "";
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
  renderPipelineEvidenceCards(pipelineStudioState?.pipeline?.evidence || []);
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

async function runPipelineSelectedValidation() {
  if (!pipelineSelectedValidationId) return;
  const validationConfig = collectPipelineValidationConfig();
  const validationRunMode = pipelineValidationModeSelect?.value || validationConfig.mode || "commands";
  if (pipelineValidationInspectorStatus) pipelineValidationInspectorStatus.textContent = `Running ${validationModeLabel(validationRunMode)} validation...`;
  if (pipelineValidationRunStatus) pipelineValidationRunStatus.textContent = `Running ${validationModeLabel(validationRunMode)}...`;
  const payload = await savePipelineDraft("run_validation", { includeManifest: false, validationConfig, validationRunMode });
  if (payload) {
    showPipelineValidationInspector(pipelineSelectedValidationId, `Ran ${validationModeLabel(validationRunMode)} for ${validationConfig.title}.`);
  }
}

function showPipelineEvidenceInspector(evidenceId, message = "") {
  const evidence = selectedPipelineEvidence(evidenceId);
  if (!evidence) {
    pipelineSelectedEvidenceId = "";
    showPipelineWorkerInspector();
    return;
  }
  const status = String(evidence.state || evidence.status || "configured").toLowerCase().replace(/\s+/g, "-");
  pipelineSelectedEvidenceId = evidenceId;
  pipelineSelectedInputId = "";
  pipelineSelectedIntegrationId = "";
  pipelineSelectedValidationId = "";
  setPipelineInspectorMode("evidence");
  setPipelineField("selectedWorker", evidence.title || "Evidence");
  if (pipelineInspectorBadge) pipelineInspectorBadge.textContent = "Evidence";
  if (pipelineInspectorState) pipelineInspectorState.textContent = titleCasePipelineStatus(status);
  if (pipelineEvidenceTitleInput) pipelineEvidenceTitleInput.value = evidence.title || "";
  if (pipelineEvidenceStatusSelect) pipelineEvidenceStatusSelect.value = status;
  if (pipelineEvidenceKindSelect) pipelineEvidenceKindSelect.value = evidence.kind || "artifact";
  if (pipelineEvidencePathInput) pipelineEvidencePathInput.value = evidence.path || "";
  if (pipelineEvidenceSourcesInput) pipelineEvidenceSourcesInput.value = pipelineLinesToText(evidence.required_sources);
  if (pipelineEvidencePublishInput) pipelineEvidencePublishInput.value = evidence.publish_policy || "";
  if (pipelineEvidenceRetentionInput) pipelineEvidenceRetentionInput.value = evidence.retention_policy || "";
  if (pipelineEvidenceNotesInput) pipelineEvidenceNotesInput.value = evidence.review_notes || "";
  if (pipelineEvidenceConfigPath) pipelineEvidenceConfigPath.textContent = evidence.config ? `Config: ${evidence.config}` : "Config output pending";
  if (pipelineEvidenceArtifactPath) pipelineEvidenceArtifactPath.textContent = evidence.path ? `Artifact: ${evidence.path}` : "Artifact output pending";
  renderPipelineImagePreviews(pipelineEvidenceArtifactPreview, [
    evidence.path || "",
    ...pipelineValueList(evidence.required_sources),
  ]);
  if (pipelineEvidenceInspectorStatus) pipelineEvidenceInspectorStatus.textContent = message || "Choose and configure this evidence artifact, then save outputs.";
  renderPipelineInputCards(pipelineStudioState?.pipeline?.input_cards || selectedPipelinePayloadTemplate()?.required_inputs || selectedPipelineStudioTemplate()?.requiredInputs || []);
  renderPipelineIntegrationCards(pipelineStudioState?.pipeline?.integration || []);
  renderPipelineValidatorCards(pipelineStudioState?.pipeline?.validators || selectedPipelinePayloadTemplate()?.validators || []);
  renderPipelineEvidenceCards(pipelineStudioState?.pipeline?.evidence || []);
  syncPipelineWorkerCards(pipelineStudioState?.pipeline?.workers || selectedPipelineStudioTemplate()?.workers || []);
}

function collectPipelineEvidenceConfig() {
  const selected = selectedPipelineEvidence();
  return {
    id: pipelineSelectedEvidenceId,
    title: pipelineEvidenceTitleInput?.value?.trim() || selected?.title || "Evidence artifact",
    status: pipelineEvidenceStatusSelect?.value || selected?.state || "configured",
    kind: pipelineEvidenceKindSelect?.value || selected?.kind || "artifact",
    path: pipelineEvidencePathInput?.value?.trim() || selected?.path || "",
    required_sources: pipelineTextToLines(pipelineEvidenceSourcesInput?.value || ""),
    publish_policy: pipelineEvidencePublishInput?.value?.trim() || "",
    retention_policy: pipelineEvidenceRetentionInput?.value?.trim() || "",
    review_notes: pipelineEvidenceNotesInput?.value?.trim() || "",
    config_path: selected?.config?.replace(/^.*workspace\/runs\/dev-pipeline-studio\/docs-pages\/latest\//, "") || ""
  };
}

async function savePipelineSelectedEvidence() {
  if (!pipelineSelectedEvidenceId) return;
  const evidenceConfig = collectPipelineEvidenceConfig();
  if (pipelineEvidenceInspectorStatus) pipelineEvidenceInspectorStatus.textContent = "Saving evidence outputs...";
  const payload = await savePipelineDraft("save_evidence", { includeManifest: false, evidenceConfig });
  if (payload) {
    showPipelineEvidenceInspector(pipelineSelectedEvidenceId, `Saved ${evidenceConfig.title}.`);
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
  const selectedTemplateId = pipelineStudioState?.selected?.template_id || pipelineTemplateSelect?.value || "";
  const workerStageLabel = selectedTemplateId === "generic-task"
    ? "2. Repo Discovery"
    : selectedTemplateId === "hard-proreq-task"
      ? "2. Cento Context"
      : selectedTemplateId === "multipipeline-proreq-chain"
      ? "2. Multipipeline Context"
      : (pipelineExecutionModelSelect?.value || template?.execution_model) === "ordered"
      ? "2. Task Execution"
      : "2. Workers (Parallel)";
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
      worker_stage_label: workerStageLabel,
      factory_stage_label: "4. Factory Execution",
      selected_worker: selectedWorker
    },
    worker_manifest: workerManifest
  };
  if (options.validationConfig) payload.validation_config = options.validationConfig;
  if (options.validationRunMode) payload.validation_run_mode = options.validationRunMode;
  if (options.integrationConfig) payload.integration_config = options.integrationConfig;
  if (options.evidenceConfig) payload.evidence_config = options.evidenceConfig;
  if (options.inputConfig) payload.input_config = options.inputConfig;
  if (options.elementType) payload.element_type = options.elementType;
  if (options.elementId) payload.element_id = options.elementId;
  if (options.elementStage) payload.element_stage = options.elementStage;
  return payload;
}

async function savePipelineDraft(action = "save", options = {}) {
  if (!pipelineProjectSelect || !pipelineTemplateSelect) return null;
  try {
    setPipelineSaveStatus(action === "select_worker" ? "Selecting worker..." : action === "save_input" ? "Saving input contract..." : action === "save_integration" ? "Saving integration outputs..." : action === "save_validation" ? "Saving validation outputs..." : action === "run_validation" ? "Running validation..." : action === "run_delivery" || action === "run_execution_e2e" ? "Starting pipeline run..." : action === "save_evidence" ? "Saving evidence outputs..." : action === "add_element" ? "Adding pipeline element..." : action === "delete_element" ? "Removing pipeline element..." : "Saving pipeline draft...");
    const response = await fetch(`${API_BASE}/dev-pipeline-studio`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(pipelineEditorPayload(action, options))
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    normalizePipelineState(payload);
    applyPipelineStudioContext();
    const verb = action === "duplicate" ? "Duplicated" : action === "new" ? "Created" : action === "select_worker" ? "Selected" : action === "save_input" ? "Saved input" : action === "save_integration" ? "Saved integration" : action === "save_validation" ? "Saved validation" : action === "run_validation" ? "Ran validation" : action === "run_delivery" || action === "run_execution_e2e" ? "Started pipeline run" : action === "save_evidence" ? "Saved evidence" : action === "add_element" ? "Added element" : action === "delete_element" ? "Removed element" : "Saved";
    setPipelineSaveStatus(`${verb} ${payload.selected?.template_id || "pipeline"} at ${new Date().toLocaleTimeString()}`);
    return payload;
  } catch (error) {
    setPipelineSaveStatus(`Save failed: ${error.message}`, true);
    return null;
  }
}

async function savePipelineSelectedManifest() {
  try {
    parsePipelineManifestEditor();
  } catch (error) {
    return;
  }
  setPipelineManifestStatus("Saving worker manifest...");
  const payload = await savePipelineDraft("save", { includeManifest: true });
  if (!payload) {
    setPipelineManifestStatus("Worker manifest save failed", true);
    return;
  }
  setInspectorTab("manifest");
  const manifestPath = payload?.pipeline?.inspector?.manifest_path || "";
  setPipelineManifestStatus(manifestPath ? `Saved ${manifestPath}` : "Worker manifest saved");
}

function openPipelineElementEditor(type, id) {
  const elementType = String(type || "");
  const elementId = String(id || "");
  if (!elementId) return;
  if (elementType === "input") {
    showPipelineInputInspector(elementId);
    return;
  }
  if (elementType === "integration") {
    showPipelineIntegrationInspector(elementId);
    return;
  }
  if (elementType === "validation") {
    showPipelineValidationInspector(elementId);
    return;
  }
  if (elementType === "evidence") {
    showPipelineEvidenceInspector(elementId);
    return;
  }
  if (elementType === "worker") {
    pipelineSelectedInputId = "";
    pipelineSelectedIntegrationId = "";
    pipelineSelectedValidationId = "";
    pipelineSelectedEvidenceId = "";
    showPipelineWorkerInspector();
    void savePipelineDraft("select_worker", { workerId: elementId, includeManifest: false });
  }
}

async function addPipelineStageElement(type, stage) {
  const payload = await savePipelineDraft("add_element", {
    includeManifest: false,
    elementType: type,
    elementStage: stage || type
  });
  const mutation = payload?.mutation || {};
  const elementType = mutation.element_type || type;
  const elementId = mutation.element_id || "";
  if (elementId) {
    openPipelineElementEditor(elementType, elementId);
    setPipelineSaveStatus(`Added ${mutation.title || elementId}`);
  }
}

async function deletePipelineStageElement(type, id) {
  const elementType = String(type || "");
  const elementId = String(id || "");
  if (!elementType || !elementId) return;
  const label = `${elementType} ${elementId}`;
  if (!window.confirm(`Remove ${label} from this pipeline?`)) return;
  if (pipelineSelectedInputId === elementId) pipelineSelectedInputId = "";
  if (pipelineSelectedIntegrationId === elementId) pipelineSelectedIntegrationId = "";
  if (pipelineSelectedValidationId === elementId) pipelineSelectedValidationId = "";
  if (pipelineSelectedEvidenceId === elementId) pipelineSelectedEvidenceId = "";
  const payload = await savePipelineDraft("delete_element", {
    includeManifest: false,
    elementType,
    elementId
  });
  if (payload) {
    showPipelineWorkerInspector();
    setPipelineSaveStatus(`Removed ${label}`);
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
    setPipelineField("factoryStageLabel", pipeline.factory_stage_label || "4. Factory Execution");
    setPipelineField("workerCount", pipeline.worker_count || "");
    setPipelineField("integrationCount", pipeline.integration_count || "");
    setPipelineField("selectedWorker", inspector.selected_worker || "");
    setPipelineField("ownedPathCount", summary.owned_paths || "");
    setPipelineField("readPathCount", summary.read_paths || "");
    setPipelineField("validationTier", summary.validation_tier || pipeline.validation?.tier || "");
    setPipelineField("riskLevel", summary.risk_level || "");
    renderPipelineInputCards(pipeline.input_cards || []);
    renderPipelineWorkerCards(pipeline.workers || []);
    renderPipelineIntegrationCards(pipeline.integration || []);
    renderPipelineValidatorCards(pipeline.validators || []);
    renderPipelineEvidenceCards(pipeline.evidence || []);
    renderPipelineCards("data-pipeline-input", pipeline.input_cards || [], [["title", "title"], ["file", "file"], ["status", "status"]]);
    renderPipelineCards("data-pipeline-worker", pipeline.workers || [], [["title", "title"], ["file", "detail"]]);
    renderPipelineCards("data-pipeline-integrate", pipeline.integration || [], [["title", "title"]]);
    renderPipelineCards("data-pipeline-validator", pipeline.validators || [], [["title", "title"], ["file", "file"], ["status", "status"]]);
    renderPipelineCards("data-pipeline-evidence", pipeline.evidence || [], [["title", "title"], ["file", "file"], ["status", "status"]]);
    renderPipelineExecutionFlow();
    if (pipelineManifestCode) {
      pipelineManifestCode.textContent = JSON.stringify(inspector.manifest || {}, null, 2);
    }
    populatePipelineEditor();
    syncPipelineWorkerCards(pipeline.workers || []);
    if (pipelineSelectedIntegrationId) {
      showPipelineIntegrationInspector(pipelineSelectedIntegrationId);
    } else if (pipelineSelectedValidationId) {
      showPipelineValidationInspector(pipelineSelectedValidationId);
    } else if (pipelineSelectedEvidenceId) {
      showPipelineEvidenceInspector(pipelineSelectedEvidenceId);
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
    if (manifestExplorerEl?.dataset.initialized) {
      refreshManifestExplorer({ preserveSelection: true });
    }
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
  setPipelineField("factoryStageLabel", "4. Factory Execution");
  setPipelineField("workerCount", `${template.workers.length} workers`);
  const fallbackFactorySteps = template.factorySteps || [
    { id: "checkout", title: "checkout_branch", file: "execution_manifest.json", status: "Queued" },
    { id: "snapshot", title: "snapshot_repo_state", file: "repo_snapshot.json", status: "Queued" },
    { id: "apply", title: "apply_change_units", file: "factory_apply_receipt.json", status: "Queued" },
    { id: "focused-tests", title: "run_focused_tests", file: "focused_tests.log", status: "Queued" },
    { id: "collect", title: "collect_diff_and_logs", file: "evidence_manifest.json", status: "Queued" }
  ];
  setPipelineField("integrationCount", `${fallbackFactorySteps.length} execution steps`);
  setPipelineField("selectedWorker", selectedWorker.title);
  setPipelineField("ownedPathCount", "1 path");
  setPipelineField("readPathCount", `${readPaths.length} paths`);
  setPipelineField("validationTier", template.validationTier);
  setPipelineField("riskLevel", template.risk);
  updateIndexedPipelineText("data-pipeline-worker-title", template.workers.map((worker) => worker.title));
  updateIndexedPipelineText("data-pipeline-worker-file", workerFiles);
  updateIndexedPipelineText("data-pipeline-integrate-title", workerFiles.map((file) => `Integrate: ${file}`));
  renderPipelineWorkerCards(template.workers || []);
  renderPipelineIntegrationCards(fallbackFactorySteps.map((step) => ({
    id: step.id,
    title: step.title,
    file: step.file || "execution_receipt.json",
    status: step.status || "Queued",
    mode: "deterministic"
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
  return loadPipelineStudioStateForRun(currentPipelineExecutionRunId);
}

async function loadPipelineStudioStateForRun(runId = "") {
  if (!pipelineProjectSelect || !pipelineTemplateSelect) {
    applyPipelineStudioContext();
    return;
  }
  const params = new URLSearchParams(location.search);
  const routeProject = params.get("project") || "";
  const routeTemplate = params.get("template") || "";
  const routeRunId = params.get("run_id") || "";
  const project = routeProject || pipelineProjectSelect.value || "hard-proreq-project";
  const template = routeTemplate || pipelineTemplateSelect.value || "hard-proreq-task";
  if (routeProject && Array.from(pipelineProjectSelect.options).some((option) => option.value === routeProject)) {
    pipelineProjectSelect.value = routeProject;
  }
  if (routeTemplate && Array.from(pipelineTemplateSelect.options).some((option) => option.value === routeTemplate)) {
    pipelineTemplateSelect.value = routeTemplate;
  }
  try {
    const selectedRunId = runId || routeRunId;
    const runQuery = selectedRunId ? `&run_id=${encodeURIComponent(selectedRunId)}` : "";
    const payload = await apiGetJson(`${API_BASE}/dev-pipeline-studio?project=${encodeURIComponent(project)}&template=${encodeURIComponent(template)}${runQuery}`);
    normalizePipelineState(payload);
    applyPipelineStudioContext();
    return payload;
  } catch (error) {
    console.warn("Dev Pipeline Studio backend unavailable; using local fallback.", error);
    pipelineStudioState = null;
    applyPipelineStudioContext();
    return null;
  }
}

// ── Manifest Explorer ─────────────────────────────────────────────────────────

let manifestExplorerPayload = null;
let currentManifestId = "";
let currentManifestView = "json";
let currentManifestReferenceKind = "all";

function manifestSlug(value, fallback = "manifest") {
  const slug = String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return slug || fallback;
}

function manifestPathFile(path, fallback = "manifest.json") {
  const parts = String(path || "").split("/").filter(Boolean);
  return parts.length ? parts[parts.length - 1] : fallback;
}

function manifestPathDir(path, fallback = "workspace/runs/dev-pipeline-studio/docs-pages/latest/") {
  const clean = String(path || "").trim();
  if (!clean) return fallback;
  const index = clean.lastIndexOf("/");
  return index >= 0 ? `${clean.slice(0, index + 1)}` : fallback;
}

function manifestStatusClass(status) {
  const normalized = String(status || "active").toLowerCase().replace(/[^a-z0-9]+/g, "-");
  if (normalized.includes("pass")) return "passed";
  if (normalized.includes("complete") || normalized.includes("accept") || normalized.includes("merge")) return "completed";
  if (normalized.includes("fail") || normalized.includes("block") || normalized.includes("reject")) return "failed";
  return "active";
}

function manifestDisplayUpdated(value) {
  const raw = String(value || "current").trim();
  const date = new Date(raw);
  if (!Number.isNaN(date.getTime())) return date.toISOString().slice(0, 16).replace("T", " ");
  return raw.length > 22 ? `${raw.slice(0, 19)}...` : raw;
}

function manifestTypeGlyph(type) {
  const glyphs = {
    pipeline: "▣",
    input: "▤",
    worker: "▧",
    integration: "⌁",
    validator: "▦",
    evidence: "▥",
  };
  return glyphs[type] || "▧";
}

function manifestSchemaName(type) {
  const schemas = {
    pipeline: "pipeline_manifest.schema.json",
    input: "input_manifest.schema.json",
    worker: "worker_manifest.schema.json",
    integration: "integration_config.schema.json",
    validator: "validator_manifest.schema.json",
    evidence: "evidence_manifest.schema.json",
  };
  return schemas[type] || "manifest.schema.json";
}

function manifestReference(kind, name, path, description, usedIn = "") {
  return {
    kind,
    name: String(name || path || "reference"),
    path: String(path || ""),
    description: String(description || ""),
    usedIn: String(usedIn || ""),
  };
}

function manifestEntry(options) {
  const file = options.file || manifestPathFile(options.path, `${options.id}.json`);
  const status = options.status || "Active";
  return {
    id: options.id,
    type: options.type || "worker",
    name: options.name || options.id,
    file,
    path: options.path || file,
    version: options.version || "v1",
    active: options.active !== false,
    status,
    updated: options.updated || "Current run",
    schema: options.schema || manifestSchemaName(options.type),
    source: options.source || manifestPathDir(options.path),
    tags: options.tags || [options.type || "manifest"],
    lineage: options.lineage || [],
    downstream: options.downstream || [],
    validation: options.validation || [
      { label: "Schema valid", detail: options.schema || manifestSchemaName(options.type), passed: true },
      { label: "References resolved", detail: "Inputs and artifacts found in active pipeline state", passed: true },
    ],
    references: options.references || [],
    payload: options.payload || {},
  };
}

function selectedPipelineManifestTemplate() {
  const payloadTemplate = selectedPipelinePayloadTemplate();
  if (payloadTemplate) return payloadTemplate;
  const fallback = selectedPipelineStudioTemplate();
  return {
    id: fallback.id,
    label: fallback.label,
    detail: fallback.detail,
    validation_tier: fallback.validationTier,
    risk: fallback.risk,
    execution_model: fallback.executionModel || "ordered",
    required_inputs: fallback.requiredInputs || [],
    workers: fallback.workers || [],
    validators: [
      { id: "smoke-plus", title: "Smoke-plus Validator", mode: "commands", status: "Passed" },
      { id: "contract", title: "Contract Validator", mode: "schema", status: "Passed" },
      { id: "evidence", title: "Evidence Validator", mode: "evidence", status: "Passed" },
    ],
  };
}

function selectedPipelineManifestProject() {
  const payloadProject = selectedPipelinePayloadProject();
  if (payloadProject) return payloadProject;
  const fallback = selectedPipelineStudioProject();
  return {
    id: fallback.key,
    label: fallback.name,
    surface: fallback.surface,
    surface_value: fallback.surfaceValue,
    owned_root: fallback.ownedRoot,
    read_paths: fallback.readPaths || [],
  };
}

function buildPipelineManifestExplorerData() {
  const project = selectedPipelineManifestProject();
  const template = selectedPipelineManifestTemplate();
  const root = pipelineStudioState?.root || "workspace/runs/dev-pipeline-studio/docs-pages/latest";
  const generatedAt = pipelineStudioState?.generated_at || new Date().toISOString();
  const pipeline = pipelineStudioState?.pipeline || {};
  const templateId = template.id || pipelineStudioState?.selected?.template_id || "hard-proreq-task";
  const inputCards = pipeline.input_cards || template.required_inputs || [];
  const workers = pipeline.workers || template.workers || [];
  const integrations = pipeline.integration || [];
  const validators = pipeline.validators || template.validators || [];
  const evidence = pipeline.evidence || [];
  const groupEntries = {
    pipeline: [],
    input: [],
    worker: [],
    integration: [],
    validator: [],
    evidence: [],
  };
  const entries = [];
  const add = (group, entry) => {
    groupEntries[group].push(entry);
    entries.push(entry);
    return entry;
  };
  const downstreamWorkers = workers.map((worker) => ({
    label: worker.title || worker.id || "Worker",
    file: worker.file || `${worker.id}.json`,
    type: "worker",
  }));
  const pipelinePath = `${root}/pipeline_manifest.json`;
  add("pipeline", manifestEntry({
    id: "pipeline_manifest",
    type: "pipeline",
    name: pipeline.template ? `${pipeline.template} Pipeline` : "Pipeline Manifest",
    file: "pipeline_manifest.json",
    path: pipelinePath,
    version: "v3",
    status: pipeline.status || "Healthy",
    updated: generatedAt,
    schema: "pipeline_manifest.schema.json",
    source: root,
    tags: ["pipeline", templateId, template.execution_model || pipeline.execution_model || "ordered"],
    downstream: downstreamWorkers,
    references: [
      ...inputCards.map((item, index) => manifestReference("input", item.title || `Input ${index + 1}`, item.manifest || item.file || "", item.detail || "Required operator input", "Pipeline Manifest")),
      ...workers.map((worker) => manifestReference("worker", worker.title || worker.id, worker.file || `${worker.id}.json`, worker.detail || worker.description || "Worker contract", "Pipeline Manifest")),
      ...validators.map((validator) => manifestReference("command", validator.title || validator.id, validator.receipt || validator.file || "", validator.summary || "Validation command set", "Validation lane")),
      ...evidence.map((item) => manifestReference("artifact", item.title || item.id, item.path || item.file || "", item.review_notes || "Evidence artifact", "Evidence bundle")),
    ],
    payload: {
      schema_version: "cento.pipeline_manifest.explorer.v1",
      id: pipeline.id || `${templateId}-pipeline`,
      run_name: pipeline.run_name || `${templateId}-${project.id}`,
      status: pipeline.status || "Healthy",
      status_detail: pipeline.status_detail || "",
      project: {
        id: project.id,
        label: project.label,
        surface: project.surface,
        read_paths: project.read_paths || [],
      },
      template: {
        id: templateId,
        label: template.label,
        detail: template.detail,
        execution_model: template.execution_model || pipeline.execution_model || "ordered",
        validation_tier: template.validation_tier || pipeline.validation?.tier || "",
        risk: template.risk || "",
      },
      manifests: {
        inputs: inputCards.map((item, index) => pipelineInputId(item, index)),
        workers: workers.map((worker) => worker.id || worker.title),
        integration: integrations.map((item, index) => pipelineIntegrationId(item, index)),
        validators: validators.map((item, index) => pipelineValidatorId(item, index)),
        evidence: evidence.map((item, index) => pipelineEvidenceId(item, index)),
      },
      budget: {
        spent: pipeline.budget || "",
        detail: pipeline.budget_detail || "",
      },
    },
  }));

  inputCards.forEach((input, index) => {
    const inputId = pipelineInputId(input, index);
    const path = input.manifest ? `${root}/${input.manifest}` : `${root}/inputs/${templateId}_${inputId}.json`;
    add("input", manifestEntry({
      id: `input_${manifestSlug(inputId)}`,
      type: "input",
      name: input.title || `Input ${index + 1}`,
      file: manifestPathFile(path),
      path,
      status: input.status || "Configured",
      updated: generatedAt,
      tags: ["input", pipelineInputType(input), input.required === false ? "optional" : "required"],
      lineage: [
        { label: "Pipeline Manifest", file: "pipeline_manifest.json", type: "pipeline" },
        { label: input.title || inputId, file: manifestPathFile(path), type: "input", current: true },
      ],
      downstream: workers.slice(0, 3).map((worker) => ({ label: worker.title || worker.id, file: worker.file || `${worker.id}.json`, type: "worker" })),
      references: [
        ...(input.paths || []).map((pathValue) => manifestReference("input", pathValue, pathValue, input.path_policy || "Read path", input.title)),
        ...(input.artifacts || []).map((artifact) => manifestReference("artifact", manifestPathFile(artifact), artifact, input.evidence_policy || "Input artifact", input.title)),
        ...(input.questions || []).map((question) => manifestReference("input", question.prompt || question.id, question.id || "", question.required === false ? "Optional question" : "Required question", input.title)),
      ],
      payload: {
        schema_version: "cento.input_manifest.v1",
        id: inputId,
        project: project.id,
        template_id: templateId,
        title: input.title || "",
        kind: pipelineInputType(input),
        status: String(input.status || "configured").toLowerCase(),
        required: input.required !== false,
        detail: input.detail || input.file || "",
        format: input.format || "",
        image_refs: input.image_refs || [],
        questions: input.questions || [],
        paths: input.paths || [],
        artifacts: input.artifacts || [],
        evidence_policy: input.evidence_policy || "",
      },
    }));
  });

  workers.forEach((worker, index) => {
    const workerId = String(worker.id || `worker-${index + 1}`);
    const templateWorker = (template.workers || []).find((item) => String(item.id || "") === workerId) || {};
    const selectedManifest = pipeline.inspector?.manifest?.task_id === workerId ? pipeline.inspector.manifest : null;
    const manifestPayload = selectedManifest || {
      schema_version: "cento.worker_manifest.v1",
      id: `${workerId}_worker_01`,
      project: project.id,
      template_id: templateId,
      type: template.worker_type || "pipeline_worker",
      task_id: workerId,
      description: worker.detail || worker.description || templateWorker.description || "",
      owned_paths: [`${project.owned_root || "workspace/generated"}/${worker.file || `${workerId}.json`}`],
      read_paths: [...(project.read_paths || []), `templates/pipelines/${templateId}.json`],
      dependencies: templateWorker.dependencies || worker.dependencies || [],
      acceptance: [
        "Template output is valid",
        "Only declared owned paths change",
        "Validation evidence is attached before review",
      ],
      validation: { tier: template.validation_tier || pipeline.validation?.tier || "" },
    };
    const path = `${root}/workers/${templateId}_${workerId}.json`;
    const dependencies = manifestPayload.dependencies || [];
    add("worker", manifestEntry({
      id: `worker_${manifestSlug(workerId)}`,
      type: "worker",
      name: worker.title || templateWorker.title || workerId,
      file: manifestPathFile(path),
      path,
      status: worker.status || "Completed",
      updated: generatedAt,
      tags: ["worker", worker.stage || workerStageKey(worker, index), template.validation_tier || "validation"],
      lineage: [
        { label: "Pipeline Manifest", file: "pipeline_manifest.json", type: "pipeline" },
        ...dependencies.map((dependency) => ({ label: dependency, file: `${dependency}.json`, type: "worker" })),
        { label: worker.title || workerId, file: manifestPathFile(path), type: "worker", current: true },
      ],
      downstream: integrations.filter((item) => (item.dependencies || []).includes(workerId) || item.id === workerId).map((item) => ({ label: item.title || item.id, file: item.receipt || item.file || "integration_receipt.json", type: "integration" })),
      references: [
        ...(manifestPayload.read_paths || []).map((pathValue) => manifestReference("input", manifestPathFile(pathValue, pathValue), pathValue, "Read path", worker.title || workerId)),
        ...(manifestPayload.owned_paths || []).map((pathValue) => manifestReference("artifact", manifestPathFile(pathValue), pathValue, "Owned output", worker.title || workerId)),
        ...dependencies.map((dependency) => manifestReference("worker", dependency, `${dependency}.json`, "Worker dependency", worker.title || workerId)),
      ],
      payload: manifestPayload,
    }));
  });

  integrations.forEach((integration, index) => {
    const integrationId = pipelineIntegrationId(integration, index);
    const path = integration.config || integration.receipt || `integration/configs/${integrationId}.json`;
    add("integration", manifestEntry({
      id: `integration_${manifestSlug(integrationId)}`,
      type: "integration",
      name: integration.title || integrationId,
      file: manifestPathFile(path),
      path: path.startsWith("workspace/") ? path : `${root}/${path}`,
      status: integration.status || "Accepted",
      updated: generatedAt,
      tags: ["integration", integration.mode || "dependency-order", integration.status || "accepted"],
      lineage: [
        ...((integration.dependencies || []).map((dependency) => ({ label: dependency, file: `${dependency}.json`, type: "worker" }))),
        { label: integration.title || integrationId, file: manifestPathFile(path), type: "integration", current: true },
      ],
      downstream: validators.slice(0, 3).map((validator) => ({ label: validator.title || validator.id, file: validator.receipt || validator.file || "validator.json", type: "validator" })),
      references: [
        ...(integration.dependencies || []).map((dependency) => manifestReference("worker", dependency, `${dependency}.json`, "Dependency receipt", integration.title)),
        ...(integration.artifacts || []).map((artifact) => manifestReference("artifact", manifestPathFile(artifact), artifact, "Integrated artifact", integration.title)),
        ...(integration.gates || []).map((gate) => manifestReference("command", gate, "", "Receipt gate", integration.title)),
        manifestReference("artifact", manifestPathFile(integration.receipt || "integration_receipt.json"), integration.receipt || "", "Integration receipt", integration.title),
      ],
      payload: {
        schema_version: "cento.integration_manifest.v1",
        ...integration,
        id: integrationId,
        project: project.id,
        template_id: templateId,
      },
    }));
  });

  validators.forEach((validator, index) => {
    const validatorId = pipelineValidatorId(validator, index);
    const path = validator.config || validator.receipt || `validation/validator_configs/${validatorId}.json`;
    add("validator", manifestEntry({
      id: `validator_${manifestSlug(validatorId)}`,
      type: "validator",
      name: validator.title || validatorId,
      file: manifestPathFile(path),
      path: path.startsWith("workspace/") ? path : `${root}/${path}`,
      status: validator.status || "Passed",
      updated: validator.executed_at || generatedAt,
      tags: ["validator", validator.tier || template.validation_tier || "smoke", validator.mode || "commands"],
      lineage: [
        ...(integrations.slice(-2).map((item) => ({ label: item.title || item.id, file: item.receipt || item.file || "integration_receipt.json", type: "integration" }))),
        { label: validator.title || validatorId, file: manifestPathFile(path), type: "validator", current: true },
      ],
      downstream: evidence.slice(0, 3).map((item) => ({ label: item.title || item.id, file: item.file || item.path || "evidence.json", type: "evidence" })),
      references: [
        ...(validator.commands || []).map((command) => manifestReference("command", command, command, "Validation command", validator.title)),
        ...(validator.evidence || []).map((artifact) => manifestReference("artifact", manifestPathFile(artifact), artifact, "Required evidence", validator.title)),
        ...(validator.gates || []).map((gate) => manifestReference("command", gate, "", "Validation gate", validator.title)),
        ...(validator.schema_paths || []).map((schema) => manifestReference("artifact", manifestPathFile(schema), schema, "Schema path", validator.title)),
      ],
      validation: [
        { label: "Schema valid", detail: manifestSchemaName("validator"), passed: true },
        { label: "References resolved", detail: `${(validator.commands || []).length} commands, ${(validator.evidence || []).length} evidence paths`, passed: true },
        { label: "Blocking policy", detail: validator.blocking === false ? "Non-blocking validator" : "Blocks handoff on failure", passed: true },
      ],
      payload: {
        schema_version: "cento.validator_manifest.v1",
        ...validator,
        id: validatorId,
        project: project.id,
        template_id: templateId,
      },
    }));
  });

  evidence.forEach((item, index) => {
    const evidenceId = pipelineEvidenceId(item, index);
    const path = item.config || item.path || `evidence/configs/${evidenceId}.json`;
    add("evidence", manifestEntry({
      id: `evidence_${manifestSlug(evidenceId)}`,
      type: "evidence",
      name: item.title || evidenceId,
      file: manifestPathFile(path),
      path: path.startsWith("workspace/") ? path : `${root}/${path}`,
      status: item.status || "Configured",
      updated: generatedAt,
      tags: ["evidence", item.kind || "artifact", item.state || "configured"],
      lineage: [
        ...(validators.slice(-2).map((validator) => ({ label: validator.title || validator.id, file: validator.receipt || validator.file || "validator.json", type: "validator" }))),
        { label: item.title || evidenceId, file: manifestPathFile(path), type: "evidence", current: true },
      ],
      references: [
        ...(item.required_sources || []).map((source) => manifestReference("artifact", manifestPathFile(source), source, "Required source", item.title)),
        manifestReference("artifact", manifestPathFile(item.path || item.file || "evidence.json"), item.path || item.file || "", item.publish_policy || "Published evidence", item.title),
      ],
      payload: {
        schema_version: "cento.evidence_manifest.v1",
        ...item,
        id: evidenceId,
        project: project.id,
        template_id: templateId,
      },
    }));
  });

  return {
    groups: [
      { id: "pipeline", label: "Pipeline Manifest", entries: groupEntries.pipeline },
      { id: "input", label: "Input Manifests", entries: groupEntries.input },
      { id: "worker", label: "Worker Manifests", entries: groupEntries.worker },
      { id: "integration", label: "Integration Manifests", entries: groupEntries.integration },
      { id: "validator", label: "Validator Manifests", entries: groupEntries.validator },
      { id: "evidence", label: "Evidence Manifests", entries: groupEntries.evidence },
    ].filter((group) => group.entries.length),
    entries,
    defaultId: entries.find((entry) => entry.type === "validator")?.id || entries[0]?.id || "",
  };
}

function findManifestEntry(manifestId) {
  return (manifestExplorerPayload?.entries || []).find((entry) => entry.id === manifestId) || null;
}

function highlightManifestJson(json) {
  return json
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/("(?:\\u[\da-fA-F]{4}|\\[^u]|[^\\"])*"(?:\s*:)?|true|false|null|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g, (m) => {
      if (/^"/.test(m)) return /:$/.test(m) ? `<span class="mjk">${m}</span>` : `<span class="mjs">${m}</span>`;
      if (/true|false/.test(m)) return `<span class="mjb">${m}</span>`;
      if (m === "null") return `<span class="mjn">${m}</span>`;
      return `<span class="mjnum">${m}</span>`;
    });
}

function renderManifestCode(jsonText) {
  if (!manifestCodeEl || !manifestLineNumsEl) return;
  const lines = jsonText.split("\n");
  manifestLineNumsEl.innerHTML = lines.map((_, i) => `<span>${i + 1}</span>`).join("");
  manifestCodeEl.innerHTML = highlightManifestJson(jsonText);
}

function renderManifestList() {
  if (!manifestListScroll || !manifestExplorerPayload) return;
  manifestListScroll.innerHTML = manifestExplorerPayload.groups.map((group) => `
    <section class="manifestGroup">
      <header><strong>${escapeHtml(group.label)}</strong><span class="manifestGroupCount">${group.entries.length}</span></header>
      <ul>
        ${group.entries.map((entry) => `
          <li class="manifestItem ${entry.id === currentManifestId ? "selected" : ""}" data-manifest-id="${escapeHtml(entry.id)}" data-manifest-type="${escapeHtml(entry.type)}" tabindex="0">
            <span class="manifestTypeIcon ${escapeHtml(entry.type)}" aria-hidden="true">${manifestTypeGlyph(entry.type)}</span>
            <div>
              <strong>${escapeHtml(entry.file)}</strong>
              <small><span class="miBadge${entry.active ? " active" : ""}">${escapeHtml(entry.version)}${entry.active ? " (active)" : ""}</span> · ${escapeHtml(manifestDisplayUpdated(entry.updated))}</small>
            </div>
            <button type="button" class="manifestItemMenu" aria-label="Manifest options">⋮</button>
          </li>
        `).join("")}
      </ul>
    </section>
  `).join("");
}

function manifestReferenceMatchesKind(reference, kind) {
  if (kind === "all") return true;
  if (kind === "artifact") return reference.kind === "artifact" || reference.kind === "schema";
  return reference.kind === kind;
}

function renderManifestReferences(entry) {
  const references = Array.isArray(entry.references) ? entry.references : [];
  const visible = references.filter((reference) => manifestReferenceMatchesKind(reference, currentManifestReferenceKind));
  if (manifestReferenceCount) manifestReferenceCount.textContent = String(references.length);
  if (manifestReferenceSummary) {
    manifestReferenceSummary.textContent = references.length
      ? `${entry.name} resolves ${references.length} direct reference${references.length === 1 ? "" : "s"} from the active pipeline.`
      : `${entry.name} has no direct references in the active pipeline.`;
  }
  if (manifestReferenceTabs) {
    const counts = {
      all: references.length,
      input: references.filter((reference) => reference.kind === "input").length,
      command: references.filter((reference) => reference.kind === "command").length,
      artifact: references.filter((reference) => reference.kind === "artifact" || reference.kind === "schema").length,
      worker: references.filter((reference) => reference.kind === "worker").length,
    };
    const labels = { all: "All", input: "Inputs", command: "Commands", artifact: "Artifacts", worker: "Workers" };
    manifestReferenceTabs.querySelectorAll("a[data-reference-kind]").forEach((link) => {
      const kind = link.dataset.referenceKind || "all";
      link.classList.toggle("active", kind === currentManifestReferenceKind);
      link.textContent = `${labels[kind] || kind} (${counts[kind] || 0})`;
    });
  }
  if (!manifestReferenceRows) return;
  if (!visible.length) {
    manifestReferenceRows.innerHTML = `<p class="manifestReferenceEmpty">No ${escapeHtml(currentManifestReferenceKind === "all" ? "" : currentManifestReferenceKind)} references for this manifest.</p>`;
    return;
  }
  manifestReferenceRows.innerHTML = `
    <div class="manifestReferenceHeader" role="row">
      <span>Type</span><span>Name / Path</span><span>Description</span><span>Used In</span>
    </div>
    ${visible.map((reference) => `
      <div class="manifestReferenceRow" role="row">
        <span>${escapeHtml(reference.kind)}</span>
        <code>${escapeHtml(reference.path || reference.name)}</code>
        <span>${escapeHtml(reference.description || "-")}</span>
        <span>${escapeHtml(reference.usedIn || entry.name)}</span>
      </div>
    `).join("")}
  `;
}

function manifestCodePayload(entry) {
  if (currentManifestView === "schema") {
    return {
      schema: entry.schema,
      type: entry.type,
      status: "valid",
      required_fields: Object.keys(entry.payload || {}).slice(0, 8),
      source: entry.source,
    };
  }
  if (currentManifestView === "references") {
    return {
      manifest: entry.id,
      references: entry.references,
      lineage: entry.lineage,
      downstream: entry.downstream,
    };
  }
  if (currentManifestView === "diff") {
    return {
      manifest: entry.id,
      from: entry.previous_version || "previous",
      to: entry.version,
      status: "preview",
      changed_fields: ["status", "updated", "references"],
      note: "Diff preview is synthesized from the active pipeline state.",
    };
  }
  if (currentManifestView === "raw") {
    return {
      path: entry.path,
      payload: entry.payload,
    };
  }
  return entry.payload;
}

function renderManifestCodeView(entry) {
  renderManifestCode(JSON.stringify(manifestCodePayload(entry), null, 2));
  manifestExplorerEl?.querySelectorAll(".manifestViewerTabs a[data-manifest-view]").forEach((link) => {
    link.classList.toggle("active", link.dataset.manifestView === currentManifestView);
  });
}

function selectManifest(manifestId) {
  const meta = findManifestEntry(manifestId) || findManifestEntry(manifestExplorerPayload?.defaultId || "");
  if (!meta) return;
  currentManifestId = meta.id;
  manifestExplorerEl?.querySelectorAll(".manifestItem").forEach((el) => {
    el.classList.toggle("selected", el.dataset.manifestId === meta.id);
  });
  renderManifestCodeView(meta);
  const set = (id, val) => { const el = document.querySelector(id); if (el) el.innerHTML = val; };
  const nameEl = document.querySelector("#manifestViewerName");
  const fileEl = document.querySelector("#manifestViewerFile");
  const badgeEl = document.querySelector("#manifestViewerBadge");
  const iconEl = manifestExplorerEl?.querySelector(".manifestViewer .manifestViewerTitle .manifestTypeIcon");
  if (nameEl) nameEl.textContent = meta.name;
  if (fileEl) fileEl.textContent = meta.file;
  if (badgeEl) { badgeEl.textContent = meta.version + (meta.active ? " (active)" : ""); badgeEl.className = "miBadge" + (meta.active ? " active" : ""); }
  if (iconEl) { iconEl.className = `manifestTypeIcon ${meta.type} large`; iconEl.textContent = manifestTypeGlyph(meta.type); }
  set("#mdType", escapeHtml(meta.type));
  set("#mdName", escapeHtml(meta.name));
  set("#mdId", escapeHtml(meta.id));
  set("#mdVersion", `<span class="miBadge${meta.active ? " active" : ""}">${escapeHtml(meta.version)}${meta.active ? " (active)" : ""}</span>`);
  set("#mdStatus", `<span class="manifestStatusBadge ${manifestStatusClass(meta.status)}">${escapeHtml(meta.status)}</span>`);
  set("#mdUpdated", escapeHtml(meta.updated));
  set("#mdSchema", `<a href="#">${escapeHtml(meta.schema)}</a>`);
  set("#mdSource", `<a href="#">${escapeHtml(meta.source)}</a>`);
  const lineageEl = document.querySelector("#manifestLineage");
  if (lineageEl) lineageEl.innerHTML = meta.lineage.length ? meta.lineage.map((n, i) => (i > 0 ? `<div class="lineageArrow" aria-hidden="true">↓</div>` : "") + `<div class="lineageNode ${n.type}${n.current ? " current" : ""}"><span class="lineageIcon ${n.type}" aria-hidden="true">${manifestTypeGlyph(n.type)}</span><div><strong>${escapeHtml(n.label)}</strong><small>${escapeHtml(n.file)}</small></div></div>`).join("") : '<p class="manifestNone">— No upstream manifests</p>';
  const dsEl = document.querySelector("#manifestDownstream");
  if (dsEl) dsEl.innerHTML = meta.downstream.length ? meta.downstream.map((n) => `<div class="lineageNode ${n.type}"><span class="lineageIcon ${n.type}" aria-hidden="true">${manifestTypeGlyph(n.type)}</span><div><strong>${escapeHtml(n.label)}</strong><small>${escapeHtml(n.file)}</small></div></div>`).join("") : "— No downstream manifests";
  const valEl = document.querySelector("#manifestValidationList");
  if (valEl) valEl.innerHTML = meta.validation.map((v) => `<div class="mvCheck ${v.passed ? "passed" : "failed"}"><span class="mvCheckIcon" aria-hidden="true">${v.passed ? "✓" : "✕"}</span><div><strong>${escapeHtml(v.label)}</strong><small>${escapeHtml(v.detail)}</small></div></div>`).join("");
  const tagsEl = document.querySelector("#manifestTags");
  if (tagsEl) tagsEl.innerHTML = meta.tags.map((t) => `<span class="manifestTag">${escapeHtml(t)}</span>`).join("");
  renderManifestReferences(meta);
}

function refreshManifestExplorer(options = {}) {
  if (!manifestExplorerEl) return;
  manifestExplorerPayload = buildPipelineManifestExplorerData();
  const hasCurrent = options.preserveSelection && currentManifestId && findManifestEntry(currentManifestId);
  if (!hasCurrent) currentManifestId = manifestExplorerPayload.defaultId;
  renderManifestList();
  selectManifest(currentManifestId);
  const q = (manifestSearchInput?.value || "").toLowerCase();
  if (q) {
    manifestExplorerEl.querySelectorAll(".manifestItem").forEach((el) => {
      const text = `${el.querySelector("strong")?.textContent || ""} ${el.dataset.manifestType || ""}`.toLowerCase();
      el.classList.toggle("manifestItemHidden", !text.includes(q));
    });
  }
}

function initManifestExplorer() {
  refreshManifestExplorer();
  manifestListScroll?.addEventListener("click", (e) => {
    const item = e.target.closest(".manifestItem[data-manifest-id]");
    if (!item || e.target.closest(".manifestItemMenu")) return;
    selectManifest(item.dataset.manifestId);
  });
  manifestListScroll?.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const item = e.target.closest(".manifestItem[data-manifest-id]");
    if (item) selectManifest(item.dataset.manifestId);
  });
  manifestSearchInput?.addEventListener("input", () => {
    const q = (manifestSearchInput.value || "").toLowerCase();
    manifestExplorerEl?.querySelectorAll(".manifestItem").forEach((el) => {
      const text = `${el.querySelector("strong")?.textContent || ""} ${el.dataset.manifestType || ""}`.toLowerCase();
      el.classList.toggle("manifestItemHidden", Boolean(q && !text.includes(q)));
    });
  });
  manifestExplorerEl?.querySelector(".manifestViewerTabs")?.addEventListener("click", (e) => {
    const link = e.target.closest("a[data-manifest-view]");
    if (!link) return;
    e.preventDefault();
    currentManifestView = link.dataset.manifestView || "json";
    const item = findManifestEntry(currentManifestId);
    if (item) renderManifestCodeView(item);
  });
  manifestReferenceTabs?.addEventListener("click", (e) => {
    const link = e.target.closest("a[data-reference-kind]");
    if (!link) return;
    e.preventDefault();
    currentManifestReferenceKind = link.dataset.referenceKind || "all";
    const item = findManifestEntry(currentManifestId);
    if (item) renderManifestReferences(item);
  });
  manifestReferenceMode?.addEventListener("change", () => {
    const item = findManifestEntry(currentManifestId);
    if (item) renderManifestReferences(item);
  });
  document.querySelector("#manifestFormatBtn")?.addEventListener("click", () => {
    const item = findManifestEntry(currentManifestId);
    if (item) renderManifestCodeView(item);
  });
  document.querySelector("#manifestValidateBtn")?.addEventListener("click", () => {
    document.querySelectorAll("#manifestValidationList .mvCheck").forEach((c) => c.classList.add("passed"));
  });
}

const PIPELINE_TAB_HASHES = {
  overview: "pipeline-overview",
  contracts: "dev-pipeline-studio",
  "execution-flow": "pipeline-flow",
  "manifest-explorer": "manifest-explorer",
  evidence: "pipeline-evidence",
  "best-practices": "pipeline-practices",
};

function pipelineTabFromHash(hash = location.hash) {
  const clean = String(hash || "").replace(/^#/, "");
  const match = Object.entries(PIPELINE_TAB_HASHES).find(([, value]) => value === clean);
  return match ? match[0] : "contracts";
}

function setPipelineTab(tab, options = {}) {
  currentPipelineTab = tab;
  document.querySelectorAll(".pipelineTabs a[data-pipeline-tab]").forEach((a) => {
    a.classList.toggle("active", a.dataset.pipelineTab === tab);
  });
  const isExplorer = tab === "manifest-explorer";
  const isExecution = tab === "execution-flow";
  const studioRoot = document.querySelector("#dev-pipeline-studio");
  studioRoot?.classList.toggle("pipelineFlowMode", isExecution);
  studioRoot?.classList.toggle("pipelineExplorerMode", isExplorer);
  document.querySelectorAll('.sdHubRailLinks a[href="/dev-pipeline-studio#manifest-explorer"]').forEach((link) => {
    link.classList.toggle("active", isExplorer);
    if (isExplorer) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  });
  document.querySelector("#dev-pipeline-studio > .pipelineHero")?.classList.toggle("hidden", isExplorer);
  document.querySelector("#dev-pipeline-studio > .pipelineContextPanel")?.classList.toggle("hidden", isExplorer);
  document.querySelector("#dev-pipeline-studio .pipelineWorkbench")?.classList.toggle("hidden", isExplorer || isExecution);
  pipelineExecutionPage?.classList.toggle("hidden", !isExecution);
  manifestExplorerEl?.classList.toggle("hidden", !isExplorer);
  if (isExecution) {
    const runsDisclosure = document.querySelector(".pipelineExecutionRuns");
    const logsDisclosure = document.querySelector(".pipelineExecutionLogs");
    if (runsDisclosure) runsDisclosure.open = false;
    if (logsDisclosure) logsDisclosure.open = false;
  }
  if (options.updateHash) {
    const hash = PIPELINE_TAB_HASHES[tab] || PIPELINE_TAB_HASHES.contracts;
    history.replaceState(null, "", `/dev-pipeline-studio#${hash}`);
  }
  if (isExplorer && manifestExplorerEl && !manifestExplorerEl.dataset.initialized) {
    manifestExplorerEl.dataset.initialized = "1";
    initManifestExplorer();
  } else if (isExplorer) {
    refreshManifestExplorer({ preserveSelection: true });
  } else if (isExecution) {
    clearPipelineExecutionAnimation();
    renderPipelineExecutionFlow();
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
      pipelineTemplateSelect.value = card.dataset.templateCard || "hard-proreq-task";
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
  const pipelineTabsNav = document.querySelector(".pipelineTabs");
  if (pipelineTabsNav) {
    pipelineTabsNav.addEventListener("click", (event) => {
      const link = event.target.closest("a[data-pipeline-tab]");
      if (!link) return;
      event.preventDefault();
      setPipelineTab(link.dataset.pipelineTab || "contracts", { updateHash: true });
    });
  }
  if (pipelineExecutionPage) {
    pipelineExecutionPage.addEventListener("click", (event) => {
      const stageButton = event.target.closest("[data-execution-stage]");
      if (stageButton) {
        selectPipelineExecutionStage(stageButton.dataset.executionStage || "");
        return;
      }
      const runButton = event.target.closest("[data-execution-run-id]");
      if (runButton) {
        void loadPipelineExecutionRun(runButton.dataset.executionRunId || "");
        return;
      }
      const logButton = event.target.closest("[data-execution-log-filter]");
      if (logButton) setPipelineExecutionLogFilter(logButton.dataset.executionLogFilter || "all");
    });
  }
  if (pipelineExecutionRunButton) {
    pipelineExecutionRunButton.addEventListener("click", () => {
      void runPipelineExecutionDelivery();
    });
  }
  if (pipelineExecutionLogSearch) {
    pipelineExecutionLogSearch.addEventListener("input", renderPipelineExecutionLogs);
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
  if (pipelineSaveManifestButton) {
    pipelineSaveManifestButton.addEventListener("click", () => {
      void savePipelineSelectedManifest();
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
  if (pipelineValidationRunButton) {
    pipelineValidationRunButton.addEventListener("click", () => {
      void runPipelineSelectedValidation();
    });
  }
  if (pipelineIntegrationSaveButton) {
    pipelineIntegrationSaveButton.addEventListener("click", () => {
      void savePipelineSelectedIntegration();
    });
  }
  if (pipelineEvidenceSaveButton) {
    pipelineEvidenceSaveButton.addEventListener("click", () => {
      void savePipelineSelectedEvidence();
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
  document.querySelector(".pipelineStageGrid")?.addEventListener("click", (event) => {
    const addButton = event.target.closest("[data-pipeline-add-element]");
    if (addButton) {
      event.preventDefault();
      event.stopPropagation();
      void addPipelineStageElement(addButton.dataset.pipelineAddElement || "", addButton.dataset.pipelineAddStage || "");
      return;
    }
    const actionButton = event.target.closest("[data-pipeline-card-action]");
    if (actionButton) {
      event.preventDefault();
      event.stopPropagation();
      const type = actionButton.dataset.elementType || "";
      const id = actionButton.dataset.elementId || "";
      if (actionButton.dataset.pipelineCardAction === "delete") {
        void deletePipelineStageElement(type, id);
      } else {
        openPipelineElementEditor(type, id);
      }
      return;
    }
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
    const evidenceCard = event.target.closest(".pipelineCard.evidence");
    const evidenceId = evidenceCard?.dataset?.evidenceId || "";
    if (evidenceId) {
      showPipelineEvidenceInspector(evidenceId);
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
    const evidenceCard = event.target.closest(".pipelineCard.evidence");
    const evidenceId = evidenceCard?.dataset?.evidenceId || "";
    if (evidenceId) {
      event.preventDefault();
      showPipelineEvidenceInspector(evidenceId);
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
  setOptionalHidden(patchSwarmView, true);
}

function hideResearchViews() {
  setOptionalHidden(researchView, true);
  setOptionalHidden(codebaseIntelligenceView, true);
}

function routeFromLocation() {
  if (location.pathname === "/") return "home";
  if (location.pathname === "/software-delivery-hub") return "software-delivery";
  if (location.pathname === "/patch-swarm" || location.pathname.startsWith("/patch-swarm/runs/")) return "patch-swarm";
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
  const activeRoute = route === "dev-pipeline-studio" || route === "factory" || route === "software-delivery" || route === "patch-swarm"
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
  } else if (activeRoute === "software-delivery" || activeRoute === "factory" || activeRoute === "issues" || activeRoute === "dev-pipeline-studio" || activeRoute === "patch-swarm") {
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
  const issueId = issueIdInput.value ? Number.parseInt(issueIdInput.value, 10) : null;
  if (!issueId) {
    const response = await fetch(`${API_BASE}/pipeline-runs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(runPipelinePayload()),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
    closeIssueModal();
    await openDefaultPipelineRouteFromIssue(result);
    return;
  }
  const payload = issueFormPayload();
  const response = await fetch(issueId ? `${API_BASE}/issues/${issueId}` : `${API_BASE}/issues`, {
    method: "PATCH",
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

function shouldAutoOpenPipelineRoute(payload) {
  return Boolean(payload?.pipeline_route?.default && location.pathname !== "/dev-pipeline-studio");
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
    if (shouldAutoOpenPipelineRoute(payload)) {
      await openDefaultPipelineRouteFromIssue(payload);
      return;
    }
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
  setOptionalHidden(patchSwarmView, true);
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
  setOptionalHidden(patchSwarmView, true);
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
  setOptionalHidden(patchSwarmView, true);
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
  setPipelineTab(pipelineTabFromHash(hash));
  history.replaceState(null, "", `/dev-pipeline-studio${hash}`);
  const cleanHash = String(hash || "").replace(/^#/, "");
  const isPipelineTabHash = Object.values(PIPELINE_TAB_HASHES).includes(cleanHash);
  if (hash && !isPipelineTabHash) {
    window.requestAnimationFrame(() => {
      const target = document.querySelector(hash);
      if (target) target.scrollIntoView({ block: "start" });
    });
  } else {
    window.requestAnimationFrame(() => {
      window.scrollTo({ top: 0, left: 0 });
      setTimeout(() => window.scrollTo({ top: 0, left: 0 }), 0);
    });
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

function patchSwarmRunPathId() {
  const match = location.pathname.match(/^\/patch-swarm\/runs\/([^/]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

function patchSwarmStatusText(value, fallback = "-") {
  const clean = String(value || fallback || "").trim();
  return clean ? clean.replaceAll("_", " ") : fallback;
}

function patchSwarmRepoCanStart(repo) {
  return Boolean(repo?.can_start) && Number(repo?.protected_dirty_count || 0) === 0;
}

function patchSwarmRepoDirtyLabel(repo) {
  if (!repo) return "";
  if (!repo.dirty) return "clean";
  const count = Number(repo.dirty_count || 0);
  return `${count} dirty path${count === 1 ? "" : "s"}`;
}

function patchSwarmRepoOptionLabel(repo) {
  const state = patchSwarmRepoCanStart(repo)
    ? `startable · ${patchSwarmRepoDirtyLabel(repo)}`
    : `blocked${Number(repo.protected_dirty_count || 0) ? " · protected dirty" : ""}`;
  return `${repo.name || repo.path} · ${state} · ${repo.path}`;
}

function patchSwarmSortedRepos(repos) {
  return [...(repos || [])].sort((left, right) => {
    const leftStart = patchSwarmRepoCanStart(left) ? 0 : 1;
    const rightStart = patchSwarmRepoCanStart(right) ? 0 : 1;
    if (leftStart !== rightStart) return leftStart - rightStart;
    return `${left.name || ""}\u0000${left.path || ""}`.localeCompare(`${right.name || ""}\u0000${right.path || ""}`);
  });
}

function patchSwarmSelectedRepo() {
  const selected = patchSwarmRepoSelect?.value || "";
  return patchSwarmRepos.find((repo) => repo.path === selected) || patchSwarmRepos[0] || null;
}

function patchSwarmTaskReady() {
  return Boolean(patchSwarmTask?.value.trim());
}

function patchSwarmCanSubmitStart() {
  return patchSwarmRepoCanStart(patchSwarmSelectedRepo()) && patchSwarmTaskReady();
}

function patchSwarmSetStartStatus(state, message = "") {
  if (!patchSwarmStartStatus) return;
  const labels = {
    ready: "Ready",
    blocked: "Blocked",
    task_required: "Task required",
    starting: "Starting",
    run_created: "Run created",
    failed: "Failed",
  };
  patchSwarmStartStatus.dataset.state = state;
  patchSwarmStartStatus.innerHTML = `<strong>${escapeHtml(labels[state] || state)}</strong><span> ${escapeHtml(message)}</span>`;
}

function updatePatchSwarmStartControls({ preserveStatus = false } = {}) {
  const repo = patchSwarmSelectedRepo();
  const mode = patchSwarmMode?.value || "fixture";
  const fixtureMessage = mode === "fixture"
    ? "Fixture mode generates local candidate receipts with no API spend."
    : "Live gated mode requires backend budget gates before real provider use.";
  if (patchSwarmStartHint) {
    patchSwarmStartHint.textContent = `${fixtureMessage} Generation does not mutate the selected repo.`;
  }
  if (!repo) {
    if (patchSwarmStartButton) {
      patchSwarmStartButton.disabled = true;
      patchSwarmStartButton.title = "No local Git repos discovered.";
    }
    if (!preserveStatus) patchSwarmSetStartStatus("blocked", "No local Git repos were discovered.");
    return false;
  }
  if (!patchSwarmRepoCanStart(repo)) {
    const protectedPaths = Array.isArray(repo.protected_dirty) ? repo.protected_dirty.join(", ") : "";
    if (patchSwarmStartButton) {
      patchSwarmStartButton.disabled = true;
      patchSwarmStartButton.title = protectedPaths ? `Clear protected dirty paths first: ${protectedPaths}` : "Selected repo is blocked.";
    }
    if (!preserveStatus) {
      patchSwarmSetStartStatus(
        "blocked",
        protectedPaths ? `Clear protected dirty paths first: ${protectedPaths}` : "The selected repo cannot start a run.",
      );
    }
    return false;
  }
  if (!patchSwarmTaskReady()) {
    if (patchSwarmStartButton) {
      patchSwarmStartButton.disabled = true;
      patchSwarmStartButton.title = "Enter a task brief before starting.";
    }
    if (!preserveStatus) patchSwarmSetStartStatus("task_required", "Enter a task brief to start a fixture run.");
    return false;
  }
  if (patchSwarmStartButton) {
    patchSwarmStartButton.disabled = false;
    patchSwarmStartButton.title = "";
  }
  if (!preserveStatus) patchSwarmSetStartStatus("ready", "Start a safe fixture run for the selected repo.");
  return true;
}

function renderPatchSwarmRepoState() {
  if (!patchSwarmRepoState) return;
  const repo = patchSwarmSelectedRepo();
  if (!repo) {
    patchSwarmRepoState.textContent = "No local Git repos discovered.";
    patchSwarmRepoState.classList.add("blocked");
    patchSwarmRepoState.classList.remove("ready");
    updatePatchSwarmStartControls();
    return;
  }
  const canStart = patchSwarmRepoCanStart(repo);
  const protectedPaths = Array.isArray(repo.protected_dirty) ? repo.protected_dirty : [];
  const protectedText = protectedPaths.length ? `Protected dirty: ${protectedPaths.join(", ")}` : "No protected dirty paths.";
  patchSwarmRepoState.innerHTML = `
    <strong>${escapeHtml(repo.name || repo.path)}</strong>
    <span>${escapeHtml(repo.branch || "unknown")} · ${escapeHtml(patchSwarmRepoDirtyLabel(repo))} · ${escapeHtml(canStart ? "startable" : "blocked")}</span>
    <small>${escapeHtml(protectedText)}</small>
  `;
  patchSwarmRepoState.classList.toggle("blocked", !canStart);
  patchSwarmRepoState.classList.toggle("ready", canStart);
  updatePatchSwarmStartControls();
}

function renderPatchSwarmRepos(payload) {
  const currentSelection = patchSwarmRepoSelect?.value || "";
  patchSwarmRepos = patchSwarmSortedRepos(Array.isArray(payload?.repos) ? payload.repos : []);
  if (!patchSwarmRepoSelect) return;
  patchSwarmRepoSelect.innerHTML = patchSwarmRepos.length
    ? patchSwarmRepos.map((repo) => `<option value="${escapeHtml(repo.path)}">${escapeHtml(patchSwarmRepoOptionLabel(repo))}</option>`).join("")
    : `<option value="">No Git repos found</option>`;
  const previous = patchSwarmRepos.find((repo) => repo.path === currentSelection);
  const preferred = previous && patchSwarmRepoCanStart(previous)
    ? previous
    : patchSwarmRepos.find(patchSwarmRepoCanStart) || patchSwarmRepos[0];
  if (preferred) patchSwarmRepoSelect.value = preferred.path;
  renderPatchSwarmRepoState();
}

async function loadPatchSwarmRepos() {
  if (!patchSwarmRepoSelect) return;
  patchSwarmRepoState.textContent = "Loading repositories...";
  try {
    renderPatchSwarmRepos(await apiGetJson(`${API_BASE}/patch-swarm/repos`));
  } catch (error) {
    patchSwarmRepoState.textContent = error.message;
    patchSwarmRepoState.classList.add("blocked");
    patchSwarmSetStartStatus("failed", error.message);
    if (patchSwarmStartButton) patchSwarmStartButton.disabled = true;
  }
}

function renderPatchSwarmRunList(payload) {
  patchSwarmRuns = Array.isArray(payload?.runs) ? payload.runs : [];
  if (!patchSwarmRunList) return;
  if (!patchSwarmRuns.length) {
    patchSwarmRunList.innerHTML = `<div class="factoryEmpty">No Patch Swarm runs yet.</div>`;
    return;
  }
  patchSwarmRunList.innerHTML = patchSwarmRuns.slice(0, 12).map((run) => {
    const active = patchSwarmDetail?.run?.run_id === run.run_id ? " active" : "";
    const repo = run.selected_repo || {};
    const kind = run.run_kind || (repo.path || repo.name ? "product" : "engine");
    const isProductRun = kind === "product";
    const repoLabel = repo.name || repo.path || "legacy engine-only run";
    const status = patchSwarmStatusText(run.status, "unknown");
    const approval = patchSwarmStatusText(run.approval_status, "not approved");
    const apply = patchSwarmStatusText(run.apply_status, "not applied");
    return `
      <button class="patchSwarmRunItem ${kind}${active}" type="button" data-patch-swarm-run="${escapeHtml(run.run_id)}">
        <span class="patchSwarmRunTop">
          <strong>${escapeHtml(run.run_id)}</strong>
          <b>${escapeHtml(isProductRun ? "Product" : "Engine")}</b>
        </span>
        <span class="patchSwarmRunRepo">${escapeHtml(repoLabel)}</span>
        <span class="patchSwarmRunFacts">
          <em>Status ${escapeHtml(status)}</em>
          <em>${escapeHtml(String(run.candidate_count || 0))} candidates</em>
          <em>Approval ${escapeHtml(approval)}</em>
          <em>Apply ${escapeHtml(apply)}</em>
        </span>
      </button>
    `;
  }).join("");
}

async function loadPatchSwarmRuns() {
  if (!patchSwarmRunList) return;
  try {
    const payload = await apiGetJson(`${API_BASE}/patch-swarm/runs`);
    renderPatchSwarmRunList(payload);
  } catch (error) {
    patchSwarmRunList.innerHTML = `<div class="factoryEmpty">${escapeHtml(error.message)}</div>`;
  }
}

function patchSwarmSelectedCandidate() {
  const candidates = Array.isArray(patchSwarmDetail?.candidates) ? patchSwarmDetail.candidates : [];
  return candidates.find((candidate) => candidate.id === patchSwarmSelectedCandidateId) || null;
}

function patchSwarmSelectedValidatedCandidates() {
  const candidates = Array.isArray(patchSwarmDetail?.candidates) ? patchSwarmDetail.candidates : [];
  const selectedIds = new Set((patchSwarmDetail?.integration?.selected_candidates || []).map(String));
  const selected = candidates.filter((candidate) => selectedIds.has(String(candidate.id)));
  return selected.filter((candidate) => String(candidate.status || "") === "validated");
}

function patchSwarmCanApproveRun() {
  const selectedIds = new Set((patchSwarmDetail?.integration?.selected_candidates || []).map(String));
  return selectedIds.size > 0 && patchSwarmSelectedValidatedCandidates().length === selectedIds.size;
}

function patchSwarmActionGates() {
  return patchSwarmDetail?.action_gates || patchSwarmDetail?.run?.action_gates || {};
}

function updatePatchSwarmReviewActions() {
  const gates = patchSwarmActionGates();
  if (patchSwarmApproveButton) {
    patchSwarmApproveButton.disabled = !gates.can_approve;
    patchSwarmApproveButton.title = gates.can_approve ? "" : (gates.approve_disabled_reason || "Approval is disabled by the run contract.");
  }
  if (patchSwarmApplyButton) {
    patchSwarmApplyButton.disabled = !gates.can_apply;
    patchSwarmApplyButton.title = gates.can_apply ? "" : (gates.apply_disabled_reason || "Apply is disabled by the run contract.");
  }
  if (patchSwarmRejectButton) {
    patchSwarmRejectButton.disabled = !gates.can_reject;
    patchSwarmRejectButton.title = gates.can_reject ? "" : (gates.reject_disabled_reason || "Reject is disabled by the run contract.");
  }
}

function setPatchSwarmDetailPanelsVisible(visible) {
  patchSwarmDetailEmpty?.classList.toggle("hidden", visible);
  patchSwarmStatsPanel?.classList.toggle("hidden", !visible);
  patchSwarmReviewGrid?.classList.toggle("hidden", !visible);
  patchSwarmEvidence?.classList.toggle("hidden", !visible);
}

function renderPatchSwarmEmptyDetail() {
  patchSwarmDetail = null;
  patchSwarmSelectedCandidateId = "";
  const title = document.querySelector("#patch-swarm-detail-title");
  if (title) title.textContent = "No run selected";
  if (patchSwarmRunSubtitle) {
    patchSwarmRunSubtitle.textContent = "Start a fixture run with a startable repo, or select a recent product run.";
  }
  if (patchSwarmCandidateList) patchSwarmCandidateList.innerHTML = `<div class="factoryEmpty">No candidates loaded.</div>`;
  renderPatchSwarmDiff(null);
  setPatchSwarmDetailPanelsVisible(false);
  updatePatchSwarmReviewActions();
  renderPatchSwarmRunList({ runs: patchSwarmRuns });
}

function renderPatchSwarmDiff(candidate) {
  if (!patchSwarmDiffPreview) return;
  if (!candidate) {
    patchSwarmSelectedCandidateId = "";
    patchSwarmDiffTitle.textContent = "Diff Preview";
    patchSwarmDiffMeta.textContent = "Select a candidate.";
    patchSwarmDiffPreview.textContent = "No diff selected.";
    updatePatchSwarmReviewActions();
    return;
  }
  patchSwarmSelectedCandidateId = candidate.id || "";
  patchSwarmDiffTitle.textContent = candidate.id || "Candidate";
  patchSwarmDiffMeta.textContent = `${candidate.provider || "provider"} · score ${candidate.score ?? "-"} · ${candidate.status || "unknown"}`;
  patchSwarmDiffPreview.textContent = candidate.diff_preview || "Diff preview unavailable.";
  document.querySelectorAll("[data-patch-swarm-candidate]").forEach((row) => {
    row.classList.toggle("active", row.dataset.patchSwarmCandidate === patchSwarmSelectedCandidateId);
  });
  updatePatchSwarmReviewActions();
}

function renderPatchSwarmCandidates(candidates) {
  if (!patchSwarmCandidateList) return;
  if (!candidates.length) {
    patchSwarmCandidateList.innerHTML = `<div class="factoryEmpty">No candidates loaded.</div>`;
    renderPatchSwarmDiff(null);
    return;
  }
  const selectedIds = new Set((patchSwarmDetail?.integration?.selected_candidates || []).map(String));
  patchSwarmCandidateList.innerHTML = candidates.slice(0, 80).map((candidate) => {
    const selected = selectedIds.has(String(candidate.id));
    const rejected = candidate.decision === "rejected";
    return `
      <button class="patchSwarmCandidate ${selected ? "winner" : ""} ${rejected ? "rejected" : ""}" type="button" data-patch-swarm-candidate="${escapeHtml(candidate.id)}">
        <span><strong>${escapeHtml(candidate.id)}</strong><small>${escapeHtml(candidate.execution_id || "")}</small></span>
        <span>${escapeHtml(candidate.provider || "")}</span>
        <span>${escapeHtml(candidate.status || "")}</span>
        <span>${escapeHtml(String(candidate.score ?? ""))}</span>
      </button>
    `;
  }).join("");
  if (!patchSwarmSelectedCandidateId || !candidates.some((candidate) => candidate.id === patchSwarmSelectedCandidateId)) {
    patchSwarmSelectedCandidateId = candidates[0]?.id || "";
  }
  renderPatchSwarmDiff(patchSwarmSelectedCandidate());
}

function patchSwarmArtifactLink(label, path) {
  if (!path) return `<span>${escapeHtml(label)} pending</span>`;
  return `<a href="${escapeHtml(`/api/artifacts?path=${encodeURIComponent(path)}`)}" target="_blank" rel="noreferrer">${escapeHtml(label)}</a>`;
}

function patchSwarmEvidenceValue(label, value) {
  return `<code><b>${escapeHtml(label)}</b>${escapeHtml(value || "pending")}</code>`;
}

function renderPatchSwarmDetail(payload) {
  patchSwarmDetail = payload;
  const run = payload?.run || {};
  const candidates = Array.isArray(payload?.candidates) ? payload.candidates : [];
  document.querySelector("#patch-swarm-detail-title").textContent = run.run_id || "No run selected";
  patchSwarmRunSubtitle.textContent = run.task_brief || "Start or select a run to inspect ranked candidates.";
  patchSwarmCandidateCount.textContent = String(run.candidate_count || 0);
  patchSwarmSelectedCount.textContent = String(run.selected_count || 0);
  patchSwarmValidationStatus.textContent = run.validation || "unknown";
  patchSwarmCost.textContent = `$${Number(run.estimated_cost_usd || 0).toFixed(6)}`;
  patchSwarmApprovalStatus.textContent = run.approval_status || "not_approved";
  patchSwarmSelectedCandidateId = patchSwarmSelectedCandidateId || candidates[0]?.id || "";
  setPatchSwarmDetailPanelsVisible(true);
  renderPatchSwarmCandidates(candidates);
  const artifacts = run.artifacts || {};
  const repo = run.selected_repo || {};
  const applyReceipt = payload?.apply_receipt || {};
  const noMutationReceipt = artifacts.no_mutation_apply || artifacts.no_mutation || "";
  const consoleHref = run.run_id ? `/patch-swarm/runs/${encodeURIComponent(run.run_id)}/console` : "";
  patchSwarmEvidence.innerHTML = `
    ${consoleHref ? `<a href="${escapeHtml(consoleHref)}" target="_blank" rel="noreferrer">Status console</a>` : ""}
    ${patchSwarmArtifactLink("Decision report", artifacts.decision_report || "")}
    ${patchSwarmArtifactLink("Candidate index", artifacts.candidate_index || "")}
    ${patchSwarmEvidenceValue("Repo", repo.path || run.run_dir || "")}
    ${patchSwarmEvidenceValue("Worktree", applyReceipt.worktree || "")}
    ${patchSwarmArtifactLink("No-mutation receipt", noMutationReceipt)}
  `;
  updatePatchSwarmReviewActions();
  renderPatchSwarmRunList({ runs: patchSwarmRuns });
}

async function loadPatchSwarmDetail(runId) {
  if (!runId) return;
  patchSwarmSelectedCandidateId = "";
  const payload = await apiGetJson(`${API_BASE}/patch-swarm/runs/${encodeURIComponent(runId)}`);
  renderPatchSwarmDetail(payload);
  history.replaceState(null, "", `/patch-swarm/runs/${encodeURIComponent(runId)}`);
}

async function submitPatchSwarmRun(event) {
  event.preventDefault();
  const repo = patchSwarmSelectedRepo();
  if (!repo || !patchSwarmCanSubmitStart()) {
    updatePatchSwarmStartControls();
    return;
  }
  patchSwarmSetStartStatus("starting", "Creating the fixture run and candidate receipts...");
  if (patchSwarmStartButton) patchSwarmStartButton.disabled = true;
  const response = await fetch(`${API_BASE}/patch-swarm/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      repo_path: repo.path,
      task_brief: patchSwarmTask.value.trim(),
      candidate_target: Number.parseInt(patchSwarmCandidateTarget.value, 10) || 30,
      max_parallel_agents: Number.parseInt(patchSwarmMaxAgents.value, 10) || 3,
      mode: patchSwarmMode.value || "fixture",
      providers: patchSwarmProviders.value || "codex-exec,claude-code,api-openai",
    }),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    patchSwarmSetStartStatus("failed", payload.error || `HTTP ${response.status}`);
    updatePatchSwarmStartControls({ preserveStatus: true });
    return;
  }
  patchSwarmSetStartStatus("run_created", `Run ${payload.run?.run_id || ""} is ready for review.`);
  updatePatchSwarmStartControls({ preserveStatus: true });
  await loadPatchSwarmRuns();
  renderPatchSwarmDetail(payload);
  history.replaceState(null, "", `/patch-swarm/runs/${encodeURIComponent(payload.run?.run_id || "")}`);
}

async function patchSwarmPostAction(action, body = {}) {
  const runId = patchSwarmDetail?.run?.run_id;
  if (!runId) return;
  const response = await fetch(`${API_BASE}/patch-swarm/runs/${encodeURIComponent(runId)}/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    patchSwarmSetStartStatus("failed", payload.error || `HTTP ${response.status}`);
    return;
  }
  renderPatchSwarmDetail(payload);
  await loadPatchSwarmRuns();
}

async function showPatchSwarm(runId = patchSwarmRunPathId()) {
  if (!patchSwarmView) {
    showSoftwareDeliveryHub();
    return;
  }
  setNavActive("patch-swarm");
  document.body.classList.remove("reviewMode");
  document.body.classList.remove("studioMode");
  setOptionalHidden(homeView, true);
  setOptionalHidden(softwareDeliveryHubView, true);
  setOptionalHidden(devPipelineStudioView, true);
  setOptionalHidden(patchSwarmView, false);
  reviewView.classList.add("hidden");
  detailView.classList.add("hidden");
  listView.classList.add("hidden");
  clusterView.classList.add("hidden");
  consultingView.classList.add("hidden");
  factoryView.classList.add("hidden");
  docsView.classList.add("hidden");
  hideResearchViews();
  await loadPatchSwarmRepos();
  await loadPatchSwarmRuns();
  if (runId) {
    await loadPatchSwarmDetail(runId).catch((error) => {
      patchSwarmSetStartStatus("failed", error.message);
      renderPatchSwarmEmptyDetail();
    });
  } else {
    renderPatchSwarmEmptyDetail();
    history.replaceState(null, "", "/patch-swarm");
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

newIssueButton.addEventListener("click", () => void openRunPipelineModal());
headerNewIssueButton.addEventListener("click", () => void openRunPipelineModal());
quickRunPipelineButton?.addEventListener("click", () => void openRunPipelineModal());
patchSwarmForm?.addEventListener("submit", (event) => void submitPatchSwarmRun(event).catch((error) => {
  patchSwarmSetStartStatus("failed", error.message);
  updatePatchSwarmStartControls({ preserveStatus: true });
}));
patchSwarmRefreshRepos?.addEventListener("click", () => void loadPatchSwarmRepos());
patchSwarmRepoSelect?.addEventListener("change", renderPatchSwarmRepoState);
patchSwarmTask?.addEventListener("input", () => updatePatchSwarmStartControls());
patchSwarmMode?.addEventListener("change", () => updatePatchSwarmStartControls());
patchSwarmRunList?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-patch-swarm-run]");
  if (!button) return;
  void loadPatchSwarmDetail(button.dataset.patchSwarmRun || "").catch((error) => {
    patchSwarmSetStartStatus("failed", error.message);
  });
});
patchSwarmCandidateList?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-patch-swarm-candidate]");
  if (!button) return;
  const candidate = (patchSwarmDetail?.candidates || []).find((item) => item.id === button.dataset.patchSwarmCandidate);
  renderPatchSwarmDiff(candidate);
});
patchSwarmApproveButton?.addEventListener("click", () => void patchSwarmPostAction("approve", {}).catch((error) => {
  patchSwarmSetStartStatus("failed", error.message);
}));
patchSwarmApplyButton?.addEventListener("click", () => void patchSwarmPostAction("apply", { limit: 1, validate_each: true, use_factory: true }).catch((error) => {
  patchSwarmSetStartStatus("failed", error.message);
}));
patchSwarmRejectButton?.addEventListener("click", () => {
  const candidate = patchSwarmSelectedCandidate();
  if (!candidate) return;
  void patchSwarmPostAction("reject", { candidate_ids: [candidate.id], reason: "Rejected in Patch Swarm review." }).catch((error) => {
    patchSwarmSetStartStatus("failed", error.message);
  });
});
detailEditButton.addEventListener("click", () => {
  if (detailPayload?.issue) openIssueModal(currentIssuePayloadFromDetail());
});
runPipelineTemplateSelect?.addEventListener("change", () => {
  currentRunPipelineTemplateId = runPipelineTemplateSelect.value || currentRunPipelineTemplateId;
  if (pipelineTemplateSelect && Array.from(pipelineTemplateSelect.options).some((option) => option.value === currentRunPipelineTemplateId)) {
    pipelineTemplateSelect.value = currentRunPipelineTemplateId;
  }
  const projectId = runPipelineProjectForTemplate(currentRunPipelineTemplateId);
  if (pipelineProjectSelect && Array.from(pipelineProjectSelect.options).some((option) => option.value === projectId)) {
    pipelineProjectSelect.value = projectId;
  }
  renderRunPipelineInputCards();
});
runPipelineInputCards?.addEventListener("change", (event) => {
  const control = event.target.closest("[data-run-pipeline-config]");
  if (control) syncRunPipelineStructuredConfig(control);
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
  } else if (location.pathname === "/patch-swarm" || location.pathname.startsWith("/patch-swarm/runs/")) {
    void showPatchSwarm();
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

window.addEventListener("hashchange", () => {
  if (location.pathname === "/dev-pipeline-studio") {
    setPipelineTab(pipelineTabFromHash(location.hash));
    return;
  }
  syncDocsHashNavigation({ scrollToHash: true });
});

async function boot() {
  syncStateFromLocation();
  setNavActive();
  await loadQueriesIntoSelect();
  capturePrefilledIssuePromptFromUrl();
  window.setTimeout(openPrefilledIssueModalFromUrl, 0);
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
  if (location.pathname === "/patch-swarm" || location.pathname.startsWith("/patch-swarm/runs/")) {
    await showPatchSwarm();
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
  if (location.pathname === "/issues" || location.pathname === "/issues/new") {
    showList();
    return;
  }
  showHome();
}

initPipelineStudioControls();
void boot();
