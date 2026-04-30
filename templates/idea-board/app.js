const state = {
  board: null,
  savedBoard: null,
  selectedId: null,
  dirty: false,
  editing: false,
};

const $ = (selector) => document.querySelector(selector);

function slugify(value) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 70) || `idea-${Date.now()}`;
}

function criteria() {
  return state.board?.scoring_scale?.criteria || [
    { key: "impact", label: "Impact" },
    { key: "cluster_leverage", label: "Cluster Leverage" },
    { key: "feasibility", label: "Feasibility" },
    { key: "momentum", label: "Momentum" },
  ];
}

function scoreIdea(idea) {
  const values = criteria().map((item) => Number(idea.scores?.[item.key] || 0));
  const total = values.reduce((sum, value) => sum + value, 0);
  return values.length ? total / values.length : 0;
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 2200);
}

function currentIdea() {
  return state.board.ideas.find((idea) => idea.id === state.selectedId) || state.board.ideas[0];
}

function markDirty() {
  state.dirty = true;
  $("#saveIdeas").textContent = "Save JSON *";
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function setEditing(editing) {
  state.editing = editing;
  $(".editor").classList.toggle("editing", editing);
  $("#editIdea").disabled = editing || !currentIdea();
  $("#duplicateIdea").disabled = !currentIdea();
  $("#deleteIdea").disabled = !currentIdea();
  $("#cancelEdit").disabled = !editing && !state.dirty;
  $("#editorState").textContent = editing
    ? "Editing selected idea. Save JSON writes changes to data/idea-board.json."
    : "Viewing selected idea. Press Edit to change fields.";
  [...$("#ideaForm").elements].forEach((element) => {
    element.disabled = !editing;
  });
}

function renderSummary(ideas) {
  const scores = state.board.ideas.map(scoreIdea);
  $("#ideaCount").textContent = state.board.ideas.length;
  $("#topScore").textContent = scores.length ? Math.max(...scores).toFixed(1) : "0.0";
  $("#nextCount").textContent = state.board.ideas.filter((idea) => idea.status === "next").length;
  $("#updatedAt").textContent = state.board.updated_at ? state.board.updated_at.slice(0, 10) : "unknown";
}

function renderFilters() {
  const categories = [...new Set([...(state.board.categories || []), ...state.board.ideas.map((idea) => idea.category).filter(Boolean)])].sort();
  $("#categoryFilter").innerHTML = `<option value="">All categories</option>${categories.map((category) => `<option>${escapeHtml(category)}</option>`).join("")}`;
  $("#categoryList").innerHTML = categories.map((category) => `<option value="${escapeHtml(category)}"></option>`).join("");
}

function filteredIdeas() {
  const query = $("#searchInput").value.trim().toLowerCase();
  const category = $("#categoryFilter").value;
  const status = $("#statusFilter").value;
  const sort = $("#sortMode").value;
  const ideas = state.board.ideas.filter((idea) => {
    const blob = [idea.title, idea.category, idea.status, idea.summary, idea.why_cluster, idea.next_step, ...(idea.tags || [])].join(" ").toLowerCase();
    return (!query || blob.includes(query)) && (!category || idea.category === category) && (!status || idea.status === status);
  });
  ideas.sort((a, b) => {
    if (sort === "score") return scoreIdea(b) - scoreIdea(a);
    return String(a[sort] || "").localeCompare(String(b[sort] || ""));
  });
  return ideas;
}

function renderIdeas() {
  const ideas = filteredIdeas();
  renderSummary(ideas);
  $("#ideaGrid").innerHTML = ideas.map((idea) => {
    const tags = (idea.tags || []).map((tag) => `<span class="pill">#${escapeHtml(tag)}</span>`).join("");
    return `
      <article class="idea-card ${idea.id === state.selectedId ? "selected" : ""}" data-id="${escapeHtml(idea.id)}">
        <header>
          <div>
            <h3>${escapeHtml(idea.title)}</h3>
            <div class="meta">
              <span class="pill category">${escapeHtml(idea.category || "Uncategorized")}</span>
              <span class="pill status-${escapeHtml(idea.status || "candidate")}">${escapeHtml(idea.status || "candidate")}</span>
              <span class="pill">${escapeHtml(idea.horizon || "near")}</span>
            </div>
          </div>
          <span class="score">${scoreIdea(idea).toFixed(1)}</span>
        </header>
        <p>${escapeHtml(idea.summary || "")}</p>
        <footer>
          <div class="tags">${tags}</div>
          <button type="button" class="card-edit" data-id="${escapeHtml(idea.id)}">Edit</button>
        </footer>
      </article>
    `;
  }).join("") || `<p class="empty">No ideas match the current filters.</p>`;

  document.querySelectorAll(".idea-card").forEach((card) => {
    card.addEventListener("click", () => {
      state.selectedId = card.dataset.id;
      renderIdeas();
      renderEditor();
    });
  });
  document.querySelectorAll(".card-edit").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      state.selectedId = button.dataset.id;
      renderIdeas();
      renderEditor();
      setEditing(true);
    });
  });
}

function renderScoreFields(idea) {
  $("#scoreFields").innerHTML = criteria().map((item) => {
    const value = Number(idea.scores?.[item.key] || 3);
    return `
      <label>${escapeHtml(item.label)}
        <input type="range" min="1" max="5" step="1" name="score:${escapeHtml(item.key)}" value="${value}">
        <span>${value}/5</span>
      </label>
    `;
  }).join("");
}

function renderEditor() {
  const idea = currentIdea();
  if (!idea) {
    $("#editorHeading").textContent = "Select an idea";
    setEditing(false);
    return;
  }
  state.selectedId = idea.id;
  $("#editorHeading").textContent = idea.title;
  const form = $("#ideaForm");
  form.title.value = idea.title || "";
  form.category.value = idea.category || "";
  form.status.value = idea.status || "candidate";
  form.horizon.value = idea.horizon || "near";
  form.tags.value = (idea.tags || []).join(", ");
  form.summary.value = idea.summary || "";
  form.why_cluster.value = idea.why_cluster || "";
  form.next_step.value = idea.next_step || "";
  renderScoreFields(idea);
  setEditing(state.editing);
}

function readEditor() {
  const idea = currentIdea();
  if (!idea) return;
  const form = $("#ideaForm");
  idea.title = form.title.value.trim() || "Untitled Idea";
  idea.category = form.category.value.trim() || "Uncategorized";
  idea.status = form.status.value;
  idea.horizon = form.horizon.value;
  idea.tags = form.tags.value.split(",").map((tag) => tag.trim()).filter(Boolean);
  idea.summary = form.summary.value.trim();
  idea.why_cluster = form.why_cluster.value.trim();
  idea.next_step = form.next_step.value.trim();
  idea.scores ||= {};
  criteria().forEach((item) => {
    idea.scores[item.key] = Number(form.elements[`score:${item.key}`].value);
  });
  if (!state.board.categories.includes(idea.category)) {
    state.board.categories.push(idea.category);
  }
}

function addIdea() {
  const idea = {
    id: slugify(`new idea ${Date.now()}`),
    title: "New Cluster Idea",
    category: "Cluster Ops",
    status: "candidate",
    horizon: "near",
    summary: "",
    why_cluster: "",
    next_step: "",
    scores: Object.fromEntries(criteria().map((item) => [item.key, 3])),
    tags: [],
  };
  state.board.ideas.unshift(idea);
  state.selectedId = idea.id;
  markDirty();
  state.editing = true;
  renderFilters();
  renderIdeas();
  renderEditor();
}

function deleteIdea() {
  const idea = currentIdea();
  if (!idea) return;
  state.board.ideas = state.board.ideas.filter((item) => item.id !== idea.id);
  state.selectedId = state.board.ideas[0]?.id || null;
  markDirty();
  state.editing = false;
  renderIdeas();
  renderEditor();
}

function duplicateIdea() {
  const idea = currentIdea();
  if (!idea) return;
  const copy = clone(idea);
  copy.id = slugify(`${idea.title || "idea"} copy ${Date.now()}`);
  copy.title = `${idea.title || "Untitled Idea"} Copy`;
  copy.status = "candidate";
  state.board.ideas.unshift(copy);
  state.selectedId = copy.id;
  markDirty();
  state.editing = true;
  renderFilters();
  renderIdeas();
  renderEditor();
}

function cancelEdit() {
  if (!state.savedBoard) return;
  const selectedId = state.selectedId;
  state.board = clone(state.savedBoard);
  state.selectedId = state.board.ideas.some((idea) => idea.id === selectedId) ? selectedId : state.board.ideas[0]?.id || null;
  state.dirty = false;
  state.editing = false;
  $("#saveIdeas").textContent = "Save JSON";
  renderFilters();
  renderIdeas();
  renderEditor();
  showToast("Reverted unsaved edits");
}

async function saveIdeas() {
  if (state.editing) readEditor();
  const response = await fetch("/api/ideas", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(state.board),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.error || `Save failed: ${response.status}`);
  }
  state.board = await response.json();
  state.savedBoard = clone(state.board);
  state.dirty = false;
  state.editing = false;
  $("#saveIdeas").textContent = "Save JSON";
  renderFilters();
  renderIdeas();
  renderEditor();
  showToast("Saved idea-board.json");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function boot() {
  const response = await fetch("/api/ideas");
  if (!response.ok) throw new Error(`Load failed: ${response.status}`);
  state.board = await response.json();
  state.savedBoard = clone(state.board);
  state.board.categories ||= [];
  state.board.ideas ||= [];
  state.selectedId = state.board.ideas[0]?.id || null;
  renderFilters();
  renderIdeas();
  renderEditor();

  ["searchInput", "categoryFilter", "statusFilter", "sortMode"].forEach((id) => {
    $(`#${id}`).addEventListener("input", renderIdeas);
  });
  $("#addIdea").addEventListener("click", addIdea);
  $("#editIdea").addEventListener("click", () => setEditing(true));
  $("#duplicateIdea").addEventListener("click", duplicateIdea);
  $("#cancelEdit").addEventListener("click", cancelEdit);
  $("#deleteIdea").addEventListener("click", deleteIdea);
  $("#saveIdeas").addEventListener("click", () => saveIdeas().catch((error) => showToast(error.message)));
  $("#ideaForm").addEventListener("input", (event) => {
    if (!state.editing) return;
    readEditor();
    if (event.target.type === "range") {
      event.target.nextElementSibling.textContent = `${event.target.value}/5`;
    }
    markDirty();
    renderFilters();
    renderIdeas();
  });
}

window.addEventListener("beforeunload", (event) => {
  if (!state.dirty) return;
  event.preventDefault();
  event.returnValue = "";
});

boot().catch((error) => {
  document.body.innerHTML = `<main class="shell"><h1>Idea board failed to load</h1><p>${escapeHtml(error.message)}</p></main>`;
});
