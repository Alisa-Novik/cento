// Inspector panel and Ask Cento panel module for the Codebase Intelligence route.
// Exposes window.CIpanels with render + init functions; no live model dependency.

(function (global) {
  "use strict";

  // --- CSS injection ---

  function injectStyles() {
    if (document.getElementById("ci-panels-styles")) return;
    const style = document.createElement("style");
    style.id = "ci-panels-styles";
    style.textContent = `
/* Inspector Panel */
.ciInspectorPanel {
  display: flex;
  flex-direction: column;
  background: var(--panel, #0b0b0a);
  border-left: 1px solid var(--panel-line, #2d211a);
  height: 100%;
  overflow: hidden;
  min-width: 0;
  font-size: 0.82rem;
  color: var(--text, #ece3d8);
}

.ciInspectorHeader {
  display: flex;
  align-items: center;
  padding: 0.55rem 0.85rem;
  border-bottom: 1px solid var(--panel-line, #2d211a);
  flex-shrink: 0;
}

.ciInspectorTitle {
  font-size: 0.78rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted, #a89c91);
}

.ciInspectorMeta {
  padding: 0.6rem 0.85rem;
  border-bottom: 1px solid var(--panel-line, #2d211a);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.ciMetaPath {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
  flex-wrap: wrap;
  word-break: break-all;
}

.ciMetaPath code {
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.78rem;
  color: var(--orange-soft, #ff8a2a);
}

.ciMetaRow {
  display: flex;
  gap: 1rem;
  align-items: center;
  flex-wrap: wrap;
}

.ciMetaLabel {
  color: var(--muted, #a89c91);
  margin-right: 0.25rem;
  font-size: 0.75rem;
}

.ciLangBadge {
  background: var(--panel-soft, #12110f);
  border: 1px solid var(--line-dim, #612000);
  color: var(--orange-soft, #ff8a2a);
  padding: 0.1rem 0.45rem;
  border-radius: 2px;
  font-size: 0.72rem;
  font-weight: 500;
  margin-left: auto;
}

.ciInspectorTabs {
  display: flex;
  border-bottom: 1px solid var(--panel-line, #2d211a);
  flex-shrink: 0;
  overflow-x: auto;
  scrollbar-width: none;
}

.ciInspectorTabs::-webkit-scrollbar { display: none; }

.ciInspectorTab {
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--muted, #a89c91);
  padding: 0.45rem 0.7rem;
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  border-radius: 0;
  flex-shrink: 0;
}

.ciInspectorTab:hover {
  color: var(--text, #ece3d8);
  border-color: transparent;
  background: transparent;
}

.ciInspectorTab.active {
  color: var(--orange, #ff5a00);
  border-bottom-color: var(--orange, #ff5a00);
}

.ciInspectorTabContent {
  flex: 1;
  overflow-y: auto;
  padding: 0.75rem 0.85rem;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.ciTabPane.hidden { display: none; }

.ciPurpose {
  margin: 0;
  color: var(--muted, #a89c91);
  line-height: 1.55;
  font-size: 0.8rem;
}

.ciSection {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.ciSectionTitle {
  margin: 0;
  font-size: 0.73rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--muted, #a89c91);
  padding-bottom: 0.25rem;
  border-bottom: 1px solid var(--panel-line, #2d211a);
}

.ciRouteList {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.ciRouteRow {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.ciMethodBadge {
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.68rem;
  font-weight: 600;
  color: var(--green, #10b66a);
  min-width: 2.2rem;
}

.ciRoutePath {
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.75rem;
  color: var(--cyan, #4dd7d1);
  word-break: break-all;
}

.ciRouteLabel {
  color: var(--muted, #a89c91);
  font-size: 0.74rem;
}

.ciDatastore {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.ciDsBadge {
  background: var(--panel-soft, #12110f);
  border: 1px solid var(--panel-line, #2d211a);
  color: var(--yellow, #ffb02e);
  padding: 0.1rem 0.4rem;
  border-radius: 2px;
  font-size: 0.71rem;
  font-weight: 600;
}

.ciDsPath {
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.72rem;
  color: var(--muted, #a89c91);
  word-break: break-all;
}

.ciDebtList {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.22rem;
}

.ciDebtItem {
  color: var(--muted, #a89c91);
  font-size: 0.78rem;
  padding-left: 0.9rem;
  position: relative;
}

.ciDebtItem::before {
  content: "▸";
  position: absolute;
  left: 0;
  color: var(--line-dim, #612000);
}

.ciAiAssistant {
  border: 1px solid var(--panel-line, #2d211a);
  border-radius: 3px;
  padding: 0.65rem;
  background: var(--panel-soft, #12110f);
}

.ciAiPromptBox {
  background: var(--bg, #050403);
  border: 1px solid var(--line-dim, #612000);
  border-radius: 2px;
  padding: 0.4rem 0.55rem;
  font-size: 0.78rem;
  color: var(--text, #ece3d8);
  margin-bottom: 0.5rem;
}

.ciAiAnswer {
  font-size: 0.76rem;
  color: var(--muted, #a89c91);
  line-height: 1.5;
  white-space: pre-line;
  margin-bottom: 0.45rem;
}

.ciAiRefs {
  list-style: none;
  margin: 0 0 0.5rem;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.ciAiRefs li {
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.71rem;
  color: var(--cyan, #4dd7d1);
}

.ciAiReportLink {
  display: inline-block;
  font-size: 0.75rem;
  color: var(--orange, #ff5a00);
  text-decoration: none;
  border: 1px solid var(--line-dim, #612000);
  padding: 0.2rem 0.55rem;
  border-radius: 2px;
  margin-top: 0.25rem;
}

.ciAiReportLink:hover {
  border-color: var(--orange, #ff5a00);
  background: rgba(255,90,0,0.08);
}

.ciPlaceholder {
  margin: 0;
  color: var(--muted, #a89c91);
  font-size: 0.78rem;
  font-style: italic;
}

/* Ask Cento Panel */
.ciAskPanel {
  display: flex;
  flex-direction: column;
  background: var(--panel, #0b0b0a);
  border-top: 1px solid var(--panel-line, #2d211a);
  font-size: 0.82rem;
  color: var(--text, #ece3d8);
  min-width: 0;
}

.ciAskHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0.85rem;
  border-bottom: 1px solid var(--panel-line, #2d211a);
  flex-shrink: 0;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.ciAskTitle {
  font-size: 0.78rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--muted, #a89c91);
}

.ciAskContext {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.ciAskContextLabel {
  font-size: 0.72rem;
  color: var(--muted, #a89c91);
}

.ciAskContextValue {
  background: var(--panel-soft, #12110f);
  border: 1px solid var(--panel-line, #2d211a);
  padding: 0.1rem 0.45rem;
  border-radius: 2px;
  font-size: 0.72rem;
  color: var(--text, #ece3d8);
}

.ciAskThread {
  flex: 1;
  overflow-y: auto;
  padding: 0.65rem 0.85rem;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  max-height: 12rem;
}

.ciAskBubble {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.ciAskAvatar {
  font-size: 0.68rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.07em;
}

.ciAskAvatarUser { color: var(--muted, #a89c91); }
.ciAskAvatarCento { color: var(--orange, #ff5a00); }

.ciAskMessage {
  margin: 0;
  background: var(--panel-soft, #12110f);
  border: 1px solid var(--panel-line, #2d211a);
  border-radius: 2px;
  padding: 0.4rem 0.6rem;
  color: var(--text, #ece3d8);
  font-size: 0.8rem;
  line-height: 1.45;
}

.ciAskAnswerWrap {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.ciAskAnswer {
  margin: 0;
  flex: 1;
  min-width: 0;
  color: var(--muted, #a89c91);
  font-size: 0.78rem;
  line-height: 1.5;
  white-space: pre-line;
  word-break: break-word;
}

.ciAskRefBlock {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 9rem;
  flex-shrink: 0;
}

.ciAskRefTitle {
  font-size: 0.68rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--muted, #a89c91);
}

.ciAskRefList {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.ciAskRef {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 0.4rem;
}

.ciAskRefLink {
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.71rem;
  color: var(--cyan, #4dd7d1);
  text-decoration: none;
  word-break: break-all;
}

.ciAskRefLink:hover { text-decoration: underline; }

.ciAskRefLines {
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.7rem;
  color: var(--muted, #a89c91);
  white-space: nowrap;
}

.ciAskRefExtra {
  font-size: 0.72rem;
  color: var(--muted, #a89c91);
  font-style: italic;
}

.ciAskActions {
  display: flex;
  align-items: center;
  padding: 0.3rem 0.85rem;
  gap: 0.75rem;
  border-top: 1px solid var(--panel-line, #2d211a);
  flex-shrink: 0;
}

.ciAskFollowUpLink {
  font-size: 0.75rem;
  color: var(--orange-soft, #ff8a2a);
  text-decoration: none;
}

.ciAskFollowUpLink:hover { text-decoration: underline; }

.ciAskInputRow {
  display: flex;
  align-items: center;
  padding: 0.5rem 0.85rem;
  gap: 0.5rem;
  border-top: 1px solid var(--panel-line, #2d211a);
  flex-shrink: 0;
}

.ciAskInput {
  flex: 1;
  min-width: 0;
  background: var(--panel-soft, #12110f);
  border: 1px solid var(--panel-line, #2d211a);
  color: var(--text, #ece3d8);
  padding: 0.4rem 0.6rem;
  border-radius: 2px;
  font-size: 0.8rem;
}

.ciAskInput:focus {
  outline: none;
  border-color: var(--line-dim, #612000);
}

.ciAskInput::placeholder { color: var(--muted, #a89c91); }

.ciAskSend {
  background: var(--line-dim, #612000);
  border: 1px solid var(--line-dim, #612000);
  color: var(--text, #ece3d8);
  width: 2rem;
  height: 2rem;
  padding: 0;
  border-radius: 2px;
  cursor: pointer;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.ciAskSend:hover {
  background: var(--orange, #ff5a00);
  border-color: var(--orange, #ff5a00);
}

@media (max-width: 768px) {
  .ciAskAnswerWrap { flex-direction: column; }
  .ciAskRefBlock { min-width: 0; }
  .ciInspectorTabs { flex-wrap: wrap; }
}
    `;
    document.head.appendChild(style);
  }

  // --- Fixture data ---

  const INSPECTOR_FIXTURE = {
    path: "scripts/agent_work_app.py",
    language: "Python",
    size_kb: 31.4,
    loc: 872,
    modified: "Today, 10:42 AM",
    purpose:
      "ThrottlingHTTPServer local web app for Agent Work (Taskstream). Serves REST API and static UI. Processes issues, review, factory, artifacts, and health endpoints.",
    api_routes: [
      { method: "GET", path: "/api/issues", label: "List issues" },
      { method: "GET", path: "/api/review", label: "Issue detail review" },
      { method: "GET", path: "/api/factory", label: "List factory runs" },
      { method: "GET", path: "/api/artifacts", label: "List catalog entries" },
      { method: "GET", path: "/api/health", label: "Health check" },
    ],
    datastore: {
      type: "SQLite",
      path: "~/...state/cento/agent-work-app.sqlite3",
    },
    tech_debt: [
      "Large single-file backend (872 LOC)",
      "Missing DOM frontend (no framework)",
      "Limited symbol search / no pagination",
      "Workspace path needs pruning without pruning",
    ],
    ai_assistant: {
      prompt: "Explain AgentWorkAppError and every route that can raise it",
      answer:
        "Here are all routes that can raise AgentWorkAppError, with any and\nwhere in the code.\n\nGET /api/issues\n- Raises when invalid query params or data load fails.\n\nPOST /api/review\n- Raised on invalid payload or persistence failure,\nscripts/agent_work_app.py:401-527\n\nGET /api/factory\n- Raises when accessing missing or unavailable\nfactory, scripts/agent_work_app.py:512-640\n\nGET /api/artifacts\n- Raises missing catalog entries.\n\nFull details with code snippets",
      references: [
        { path: "scripts/agent_work_app.py", lines: 66 },
        { path: "scripts/agent_work_app.py", lines: 412 },
        { path: "scripts/agent_work_app.py", lines: 458 },
        { path: "scripts/agent_work_app.py", lines: 812 },
      ],
    },
  };

  const ASK_PANEL_FIXTURE = {
    context: "Current Repository",
    example_prompt: "Explain AgentWorkAppError and every route that can raise it",
    answer:
      "AgentWorkAppError is the base exception for the Agent Work web app. It's raised for domain and request errors and returned as JSON {\"error\": \"...\"} with appropriate HTTP status codes.\n\nAll routes that can raise it, with conditions and code references.",
    references: [
      { path: "scripts/agent_work_app.py", lines: 412 },
      { path: "scripts/agent_work_app.py", lines: 458 },
      { path: "scripts/agent_work_app.py", lines: 612 },
      { path: "scripts/agent_work_app.py", lines: 736 },
    ],
    extra_refs: 1,
  };

  // --- Helpers ---

  function esc(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // --- Inspector Panel ---

  function renderInspectorPanel(data) {
    data = data || INSPECTOR_FIXTURE;

    const tabs = ["Summary", "Call Graph", "Owners", "Debt", "Tests", "Evidence"];
    const tabsHtml = tabs
      .map(
        (t, i) =>
          `<button class="ciInspectorTab${i === 0 ? " active" : ""}" data-tab="${esc(t.toLowerCase().replace(/\s+/g, "-"))}" role="tab" aria-selected="${i === 0}">${esc(t)}</button>`
      )
      .join("");

    const routesHtml = (data.api_routes || [])
      .map(
        (r) =>
          `<li class="ciRouteRow"><span class="ciMethodBadge">${esc(r.method)}</span><code class="ciRoutePath">${esc(r.path)}</code><span class="ciRouteLabel">${esc(r.label)}</span></li>`
      )
      .join("");

    const debtHtml = (data.tech_debt || [])
      .map((d) => `<li class="ciDebtItem">${esc(d)}</li>`)
      .join("");

    const aiRefs = (data.ai_assistant.references || [])
      .map((r) => `<li>${esc(r.path)}:${esc(String(r.lines))}</li>`)
      .join("");

    return `
<div class="ciInspectorPanel" id="ciInspectorPanel">
  <div class="ciInspectorHeader">
    <span class="ciInspectorTitle">Inspector</span>
  </div>
  <div class="ciInspectorMeta">
    <div class="ciMetaPath">
      <span class="ciMetaLabel">File</span>
      <code>${esc(data.path)}</code>
    </div>
    <div class="ciMetaRow">
      <span><span class="ciMetaLabel">Size</span>${esc(String(data.size_kb))} KB</span>
      <span><span class="ciMetaLabel">Loc</span>${esc(String(data.loc))}</span>
    </div>
    <div class="ciMetaRow">
      <span><span class="ciMetaLabel">Modified</span>${esc(data.modified)}</span>
      <span class="ciLangBadge">${esc(data.language)}</span>
    </div>
  </div>
  <nav class="ciInspectorTabs" role="tablist" aria-label="Inspector sections">${tabsHtml}</nav>
  <div class="ciInspectorTabContent">
    <div class="ciTabPane" data-pane="summary" role="tabpanel">
      <p class="ciPurpose">${esc(data.purpose)}</p>

      <section class="ciSection">
        <h4 class="ciSectionTitle">API Routes / Routes</h4>
        <ul class="ciRouteList">${routesHtml}</ul>
      </section>

      <section class="ciSection">
        <h4 class="ciSectionTitle">Datastore</h4>
        <div class="ciDatastore">
          <span class="ciDsBadge">${esc(data.datastore.type)}</span>
          <code class="ciDsPath">${esc(data.datastore.path)}</code>
        </div>
      </section>

      <section class="ciSection">
        <h4 class="ciSectionTitle">Tech / Debt</h4>
        <ul class="ciDebtList">${debtHtml}</ul>
      </section>

      <section class="ciSection ciAiAssistant">
        <h4 class="ciSectionTitle">AI Assistant (Cento)</h4>
        <div class="ciAiPromptBox">${esc(data.ai_assistant.prompt)}</div>
        <div class="ciAiAnswer">${esc(data.ai_assistant.answer)}</div>
        <ul class="ciAiRefs">${aiRefs}</ul>
        <a href="#ai-report" class="ciAiReportLink">Open in AI Report</a>
      </section>
    </div>

    <div class="ciTabPane hidden" data-pane="call-graph" role="tabpanel">
      <p class="ciPlaceholder">Call graph analysis not yet available for this file.</p>
    </div>
    <div class="ciTabPane hidden" data-pane="owners" role="tabpanel">
      <p class="ciPlaceholder">Owner data not yet available for this file.</p>
    </div>
    <div class="ciTabPane hidden" data-pane="debt" role="tabpanel">
      <ul class="ciDebtList">${debtHtml}</ul>
    </div>
    <div class="ciTabPane hidden" data-pane="tests" role="tabpanel">
      <p class="ciPlaceholder">Test coverage data not yet available for this file.</p>
    </div>
    <div class="ciTabPane hidden" data-pane="evidence" role="tabpanel">
      <p class="ciPlaceholder">No linked evidence for this file.</p>
    </div>
  </div>
</div>`.trim();
  }

  function initInspectorPanel(containerEl) {
    if (!containerEl) return;
    const tabs = containerEl.querySelectorAll(".ciInspectorTab");
    const panes = containerEl.querySelectorAll(".ciTabPane");
    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        const target = tab.dataset.tab;
        tabs.forEach((t) => {
          t.classList.remove("active");
          t.setAttribute("aria-selected", "false");
        });
        tab.classList.add("active");
        tab.setAttribute("aria-selected", "true");
        panes.forEach((pane) => {
          pane.classList.toggle("hidden", pane.dataset.pane !== target);
        });
      });
    });
  }

  // --- Ask Cento Panel ---

  function renderAskCentoPanel(data) {
    data = data || ASK_PANEL_FIXTURE;

    const refsHtml = (data.references || [])
      .map(
        (r) =>
          `<li class="ciAskRef"><a href="#" class="ciAskRefLink">${esc(r.path)}</a><span class="ciAskRefLines">${esc(String(r.lines))}</span></li>`
      )
      .join("");
    const extraRef =
      data.extra_refs > 0
        ? `<li class="ciAskRefExtra">+${data.extra_refs} more reference${data.extra_refs > 1 ? "s" : ""}</li>`
        : "";

    return `
<div class="ciAskPanel" id="ciAskPanel">
  <div class="ciAskHeader">
    <span class="ciAskTitle">Ask Cento about code</span>
    <div class="ciAskContext">
      <span class="ciAskContextLabel">Context</span>
      <span class="ciAskContextValue">${esc(data.context)}</span>
    </div>
  </div>
  <div class="ciAskThread" aria-live="polite" aria-label="Conversation">
    <div class="ciAskBubble ciAskBubbleUser">
      <span class="ciAskAvatar ciAskAvatarUser">You</span>
      <p class="ciAskMessage">${esc(data.example_prompt)}</p>
    </div>
    <div class="ciAskBubble ciAskBubbleCento">
      <span class="ciAskAvatar ciAskAvatarCento">Cento AI</span>
      <div class="ciAskAnswerWrap">
        <p class="ciAskAnswer">${esc(data.answer)}</p>
        <div class="ciAskRefBlock">
          <span class="ciAskRefTitle">Referenced in</span>
          <ul class="ciAskRefList">${refsHtml}${extraRef}</ul>
        </div>
      </div>
    </div>
  </div>
  <div class="ciAskActions">
    <a href="#" class="ciAskFollowUpLink">&#9655; Follow up</a>
  </div>
  <div class="ciAskInputRow">
    <input
      class="ciAskInput"
      id="ciAskInput"
      type="text"
      placeholder="Ask anything about this codebase..."
      aria-label="Ask Cento about this codebase"
    />
    <button class="ciAskSend" id="ciAskSend" type="button" aria-label="Send question">&#8593;</button>
  </div>
</div>`.trim();
  }

  function initAskCentoPanel(containerEl) {
    if (!containerEl) return;
    const input = containerEl.querySelector(".ciAskInput");
    const send = containerEl.querySelector(".ciAskSend");
    const thread = containerEl.querySelector(".ciAskThread");
    if (!input || !send) return;

    function appendUserBubble(text) {
      if (!thread) return;
      const div = document.createElement("div");
      div.className = "ciAskBubble ciAskBubbleUser";
      const avatar = document.createElement("span");
      avatar.className = "ciAskAvatar ciAskAvatarUser";
      avatar.textContent = "You";
      const msg = document.createElement("p");
      msg.className = "ciAskMessage";
      msg.textContent = text;
      div.appendChild(avatar);
      div.appendChild(msg);
      thread.appendChild(div);
      thread.scrollTop = thread.scrollHeight;
    }

    function submitAsk() {
      const val = input.value.trim();
      if (!val) return;
      input.value = "";
      appendUserBubble(val);
    }

    send.addEventListener("click", submitAsk);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        submitAsk();
      }
    });

    const followUp = containerEl.querySelector(".ciAskFollowUpLink");
    if (followUp) {
      followUp.addEventListener("click", (e) => {
        e.preventDefault();
        input.focus();
      });
    }
  }

  // --- API loader ---

  async function loadInspectorData(filePath) {
    try {
      const resp = await fetch(
        `/api/codebase-intelligence/inspect?path=${encodeURIComponent(filePath)}`
      );
      if (!resp.ok) return null;
      return await resp.json();
    } catch {
      return null;
    }
  }

  // --- Mount helpers ---

  function mountInspectorPanel(containerEl, data) {
    if (!containerEl) return;
    injectStyles();
    containerEl.innerHTML = renderInspectorPanel(data || INSPECTOR_FIXTURE);
    initInspectorPanel(containerEl);
  }

  function mountAskCentoPanel(containerEl, data) {
    if (!containerEl) return;
    injectStyles();
    containerEl.innerHTML = renderAskCentoPanel(data || ASK_PANEL_FIXTURE);
    initAskCentoPanel(containerEl);
  }

  // --- Public API ---

  global.CIpanels = {
    INSPECTOR_FIXTURE,
    ASK_PANEL_FIXTURE,
    injectStyles,
    renderInspectorPanel,
    initInspectorPanel,
    renderAskCentoPanel,
    initAskCentoPanel,
    loadInspectorData,
    mountInspectorPanel,
    mountAskCentoPanel,
  };
})(window);
