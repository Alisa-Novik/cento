const appRoot = document.getElementById('app');

const store = {
  loading: true,
  saving: false,
  saveState: 'Idle',
  activeView: 'overview',
  profile: 'career-consulting',
  data: null,
  questionnaire: null,
  paths: null,
  requestLog: [],
  error: '',
};

const views = [
  { id: 'overview', label: 'Overview' },
  { id: 'pipeline', label: 'Pipeline' },
  { id: 'contacts', label: 'Contacts' },
  { id: 'tasks', label: 'Tasks' },
  { id: 'studio', label: 'Studio' },
];

function uid(prefix) {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

function formatDate(value) {
  if (!value) return 'No date';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}

function formatDateTime(value) {
  if (!value) return 'Unknown';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

function joinList(items) {
  return (items || []).filter(Boolean).join(', ') || 'Not defined yet';
}

function parseJsonSafe(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

async function request(url, options = {}) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  const text = await response.text();
  const payload = text ? parseJsonSafe(text) : {};
  if (!response.ok) {
    throw new Error(payload?.error || `Request failed with ${response.status}`);
  }
  return payload;
}

async function loadRequestLog() {
  try {
    const payload = await request('/api/request-log');
    store.requestLog = payload.requests || [];
  } catch {
    store.requestLog = [];
  }
}

async function loadState() {
  store.loading = true;
  render();
  try {
    const payload = await request(`/api/state?profile=${encodeURIComponent(store.profile)}`);
    store.data = payload.state;
    store.questionnaire = payload.questionnaire;
    store.paths = payload.paths;
    store.error = '';
    await loadRequestLog();
  } catch (error) {
    store.error = error.message;
  } finally {
    store.loading = false;
    render();
  }
}

async function saveState() {
  if (!store.data) return;
  store.saving = true;
  store.saveState = 'Saving...';
  render();
  try {
    const payload = await request('/api/save', {
      method: 'POST',
      body: JSON.stringify({ profile: store.profile, state: store.data }),
    });
    store.data = payload.state;
    store.saveState = `Saved ${new Date().toLocaleTimeString()}`;
    await loadRequestLog();
  } catch (error) {
    store.saveState = `Save failed: ${error.message}`;
  } finally {
    store.saving = false;
    render();
  }
}

function addNote(title, body, type = 'system') {
  store.data.notes.unshift({
    id: uid('note'),
    type,
    title,
    body,
    created_at: new Date().toISOString(),
  });
}

function metrics() {
  const state = store.data;
  const pipelineCards = state.pipeline.cards || [];
  const activeClients = pipelineCards.filter(card => ['client', 'active', 'won'].includes(card.stage_id)).length;
  const openTasks = (state.tasks || []).filter(task => task.status !== 'done').length;
  const templates = (state.templates || []).length;
  const contacts = (state.contacts || []).length;
  return [
    { label: 'Contacts', value: contacts, copy: 'People tracked inside the local CRM.' },
    { label: 'Open pipeline', value: pipelineCards.length, copy: 'Leads, calls, offers, and client relationships.' },
    { label: 'Active clients', value: activeClients, copy: 'Current paid engagements or live delivery.' },
    { label: 'Open tasks', value: openTasks, copy: 'Execution items still waiting on action.' },
    { label: 'Templates', value: templates, copy: 'Reusable outreach, intake, and delivery assets.' },
    { label: 'Integrations planned', value: (state.catalogs.integrations || []).length, copy: 'Connected systems to plan for, without slowing the MVP.' },
    { label: 'Forms ready', value: (state.forms || []).length, copy: 'Intake flows bootstrapped from the questionnaire.' },
    { label: 'Lead sources', value: (state.catalogs.lead_sources || []).length, copy: 'Channels you want visible from day one.' },
  ];
}

function renderHero() {
  const state = store.data;
  return `
    <section class="hero">
      <div class="hero-copy">
        <p class="eyebrow">Cento CRM / local-first operating system</p>
        <h1>${escapeHtml(state.branding.crm_name)}</h1>
        <p class="hero-subtitle">
          ${escapeHtml(state.branding.practice_name)} now runs inside cento as a self-hosted CRM focused on ${escapeHtml(state.settings.primary_goal.toLowerCase())}.
          This MVP is instant, local, and deliberately lightweight.
        </p>
        <div class="hero-tags">
          <span class="tag">${escapeHtml(state.settings.business_model)}</span>
          <span class="tag">${escapeHtml(state.settings.launch_preference)}</span>
          <span class="tag">Automation: ${escapeHtml(state.settings.automation_level)}</span>
        </div>
      </div>
      <div class="hero-panel">
        <div class="hero-note panel">
          <strong>What this build is optimizing for</strong>
          <p>${escapeHtml(state.settings.special_notes || 'Native cento integration, structured client tracking, and a workflow-ready local MVP.')}</p>
        </div>
        <div class="hero-note panel" style="background: linear-gradient(150deg, rgba(109, 79, 120, 0.9), rgba(56, 72, 112, 0.9));">
          <strong>Questionnaire sync</strong>
          <p>Bootstrapped from the saved profile updated ${escapeHtml(formatDateTime(store.questionnaire?.updated_at))}. Privacy-specific handling stays out of MVP scope.</p>
        </div>
      </div>
    </section>
  `;
}

function renderMetrics() {
  return `
    <section class="metrics-grid">
      ${metrics().map(metric => `
        <article class="metric-card">
          <div class="metric-label">${escapeHtml(metric.label)}</div>
          <div class="metric-value">${escapeHtml(metric.value)}</div>
          <div class="metric-subtext">${escapeHtml(metric.copy)}</div>
        </article>
      `).join('')}
    </section>
  `;
}

function renderNav() {
  return `
    <div class="toolbar">
      <div class="toolbar-nav">
        ${views.map(view => `
          <button class="nav-button ${store.activeView === view.id ? 'active' : ''}" data-nav="${view.id}">${escapeHtml(view.label)}</button>
        `).join('')}
      </div>
      <div class="section-actions">
        <button class="secondary-button" data-action="refresh">Refresh</button>
        <button class="primary-button" data-action="save">Save local state</button>
      </div>
    </div>
  `;
}

function renderOverview() {
  const state = store.data;
  return `
    <section class="view-grid">
      <div class="stack">
        <article class="panel metric-card">
          <div class="section-head">
            <div>
              <h2 class="section-title">Operating shape</h2>
              <p class="section-copy">This CRM was generated from your questionnaire and is already aligned to the current consulting model.</p>
            </div>
          </div>
          <div class="grid-2">
            <div class="summary-card">
              <div class="summary-label">Client segments</div>
              <div class="summary-value">${escapeHtml(joinList(state.catalogs.client_segments))}</div>
            </div>
            <div class="summary-card">
              <div class="summary-label">Services</div>
              <div class="summary-value">${escapeHtml(joinList((state.catalogs.services || []).map(item => item.label)))}</div>
            </div>
            <div class="summary-card">
              <div class="summary-label">Lead sources</div>
              <div class="summary-value">${escapeHtml(joinList(state.catalogs.lead_sources))}</div>
            </div>
            <div class="summary-card">
              <div class="summary-label">Channels</div>
              <div class="summary-value">${escapeHtml(joinList(state.catalogs.channels))}</div>
            </div>
          </div>
        </article>
        <article class="panel">
          <div class="section-head">
            <div>
              <h2 class="section-title">MVP focus</h2>
              <p class="section-copy">The build is biased toward speed, local ownership, and the feature set you marked as essential.</p>
            </div>
          </div>
          <div class="highlight-list">
            ${state.highlights.map(item => `<div class="summary-card"><div class="summary-label">${escapeHtml(item.title)}</div><div class="summary-value">${escapeHtml(item.value)}</div></div>`).join('')}
          </div>
        </article>
      </div>
      <div class="stack">
        <article class="timeline-card">
          <div class="section-head">
            <div>
              <h2 class="section-title">System timeline</h2>
              <p class="section-copy">Operational notes and local activity.</p>
            </div>
          </div>
          <div class="timeline-list">
            ${(state.notes || []).slice(0, 5).map(note => `
              <article class="timeline-item">
                <div class="timeline-head">
                  <strong>${escapeHtml(note.title)}</strong>
                  <span class="timeline-meta">${escapeHtml(formatDateTime(note.created_at))}</span>
                </div>
                <div class="timeline-body">${escapeHtml(note.body)}</div>
              </article>
            `).join('')}
          </div>
        </article>
        <article class="list-panel">
          <div class="section-head">
            <div>
              <h2 class="section-title">Infrastructure notes</h2>
              <p class="section-copy">Self-hosted through cento with no build step.</p>
            </div>
          </div>
          <div class="summary-card">
            <div class="summary-label">State file</div>
            <div class="summary-value">${escapeHtml(store.paths?.state_path || 'Unknown')}</div>
          </div>
          <div class="summary-card">
            <div class="summary-label">Questionnaire source</div>
            <div class="summary-value">${escapeHtml(store.questionnaire?.answers_path || 'Unknown')}</div>
          </div>
        </article>
      </div>
    </section>
  `;
}

function renderPipeline() {
  const state = store.data;
  return `
    <section class="view-grid">
      <div class="stack">
        <article class="form-panel">
          <div class="section-head">
            <div>
              <h2 class="section-title">Pipeline command deck</h2>
              <p class="section-copy">Add a new opportunity and drop it into the current questionnaire-derived stage model.</p>
            </div>
          </div>
          <form id="deal-form" class="form-grid">
            <div class="field"><label>Opportunity title</label><input name="title" required placeholder="Resume rewrite + strategy package" /></div>
            <div class="field"><label>Contact name</label><input name="contact_name" placeholder="Prospect or client name" /></div>
            <div class="field"><label>Stage</label><select name="stage_id">${state.pipeline.stages.map(stage => `<option value="${escapeHtml(stage.id)}">${escapeHtml(stage.label)}</option>`).join('')}</select></div>
            <div class="field"><label>Service</label><select name="service">${(state.catalogs.services || []).map(service => `<option value="${escapeHtml(service.label)}">${escapeHtml(service.label)}</option>`).join('')}</select></div>
            <div class="field"><label>Lead source</label><select name="source">${(state.catalogs.lead_sources || []).map(item => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join('')}</select></div>
            <div class="field"><label>Package value</label><input name="value" placeholder="950" /></div>
            <div class="field full"><label>Next step</label><input name="next_step" placeholder="Send discovery intake and offer outline" /></div>
            <div class="field"><label>Target date</label><input name="due_date" type="date" /></div>
            <div class="field full"><label>Notes</label><textarea name="note" placeholder="Any context worth keeping on the card."></textarea></div>
            <div class="field full form-actions"><button class="primary-button" type="submit">Add pipeline card</button></div>
          </form>
        </article>
        <article class="panel">
          <div class="section-head">
            <div>
              <h2 class="section-title">Live pipeline</h2>
              <p class="section-copy">The board is intentionally lean. Update stage directly on the card, then save.</p>
            </div>
          </div>
          ${state.pipeline.cards.length ? `
            <div class="kanban">
              ${state.pipeline.stages.map(stage => {
                const cards = state.pipeline.cards.filter(card => card.stage_id === stage.id);
                return `
                  <section class="column">
                    <div class="column-head">
                      <div>
                        <h3 class="column-title">${escapeHtml(stage.label)}</h3>
                        <p class="column-copy">${escapeHtml(stage.description)}</p>
                      </div>
                      <div class="count-badge">${cards.length}</div>
                    </div>
                    ${cards.map(card => `
                      <article class="card">
                        <div class="card-head">
                          <h4 class="card-title">${escapeHtml(card.title)}</h4>
                          <button class="icon-button" data-delete-deal="${escapeHtml(card.id)}">×</button>
                        </div>
                        <div class="card-meta">${escapeHtml(card.contact_name || 'Unassigned contact')} · ${escapeHtml(card.service || 'General')} · ${escapeHtml(card.source || 'Unknown source')}</div>
                        <div class="chip-row">
                          <span class="pill">Value: ${escapeHtml(card.value || 'TBD')}</span>
                          <span class="stage-pill">Due ${escapeHtml(formatDate(card.due_date))}</span>
                        </div>
                        <div class="card-copy">${escapeHtml(card.next_step || 'No next step yet.')}</div>
                        <div class="field">
                          <label>Move stage</label>
                          <select class="stage-select" data-stage-select="${escapeHtml(card.id)}">
                            ${state.pipeline.stages.map(option => `<option value="${escapeHtml(option.id)}" ${option.id === card.stage_id ? 'selected' : ''}>${escapeHtml(option.label)}</option>`).join('')}
                          </select>
                        </div>
                      </article>
                    `).join('') || `<div class="empty-card"><h3 class="empty-title">No cards here</h3><p class="empty-copy">This stage is ready, but still empty. Add a card above to start using the board.</p></div>`}
                  </section>
                `;
              }).join('')}
            </div>
          ` : `<div class="empty-card"><h3 class="empty-title">No opportunities yet</h3><p class="empty-copy">Create the first opportunity from the command deck to turn the questionnaire into a live client pipeline.</p></div>`}
        </article>
      </div>
      <div class="stack">
        <article class="list-panel">
          <div class="section-head">
            <div>
              <h2 class="section-title">Pipeline rules</h2>
              <p class="section-copy">Derived from the saved profile and kept intentionally simple for the MVP.</p>
            </div>
          </div>
          ${state.pipeline.stages.map(stage => `
            <div class="summary-card">
              <div class="summary-label">${escapeHtml(stage.label)}</div>
              <div class="summary-value">${escapeHtml(stage.description)}</div>
            </div>
          `).join('')}
        </article>
      </div>
    </section>
  `;
}

function renderContacts() {
  const state = store.data;
  return `
    <section class="view-grid">
      <div class="stack">
        <article class="form-panel">
          <div class="section-head">
            <div>
              <h2 class="section-title">Add contact</h2>
              <p class="section-copy">A local-first contact record with only the fields your MVP needs today.</p>
            </div>
          </div>
          <form id="contact-form" class="form-grid">
            <div class="field"><label>Name</label><input name="name" required placeholder="Candidate name" /></div>
            <div class="field"><label>Email</label><input name="email" type="email" placeholder="name@example.com" /></div>
            <div class="field"><label>Segment</label><select name="segment">${(state.catalogs.client_segments || []).map(item => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join('')}</select></div>
            <div class="field"><label>Lead source</label><select name="source">${(state.catalogs.lead_sources || []).map(item => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join('')}</select></div>
            <div class="field"><label>Primary service</label><select name="service">${(state.catalogs.services || []).map(item => `<option value="${escapeHtml(item.label)}">${escapeHtml(item.label)}</option>`).join('')}</select></div>
            <div class="field"><label>Preferred channel</label><select name="channel">${(state.catalogs.channels || []).map(item => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join('')}</select></div>
            <div class="field full"><label>Notes</label><textarea name="notes" placeholder="Current goal, urgency, or what matters before the first session."></textarea></div>
            <div class="field full form-actions"><button class="primary-button" type="submit">Add contact</button></div>
          </form>
        </article>
      </div>
      <div class="stack">
        <article class="list-panel">
          <div class="section-head">
            <div>
              <h2 class="section-title">Contact roster</h2>
              <p class="section-copy">Tracked people with segment, service, and source context.</p>
            </div>
          </div>
          ${(state.contacts || []).length ? `<div class="contact-list">${state.contacts.map(contact => `
            <article class="list-item">
              <div class="list-item-head">
                <strong>${escapeHtml(contact.name)}</strong>
                <button class="icon-button" data-delete-contact="${escapeHtml(contact.id)}">×</button>
              </div>
              <div class="list-meta">${escapeHtml(contact.email || 'No email')} · ${escapeHtml(contact.segment || 'No segment')} · ${escapeHtml(contact.source || 'No source')}</div>
              <div class="chip-row">
                <span class="pill">${escapeHtml(contact.service || 'General')}</span>
                <span class="stage-pill">${escapeHtml(contact.channel || 'No channel')}</span>
              </div>
              <div class="list-item-body">${escapeHtml(contact.notes || 'No notes yet.')}</div>
            </article>
          `).join('')}</div>` : `<div class="empty-card"><h3 class="empty-title">No contacts yet</h3><p class="empty-copy">Add the first contact to start turning the CRM from a plan into an operating system.</p></div>`}
        </article>
      </div>
    </section>
  `;
}

function renderTasks() {
  const state = store.data;
  return `
    <section class="view-grid">
      <div class="stack">
        <article class="form-panel">
          <div class="section-head">
            <div>
              <h2 class="section-title">Task runner</h2>
              <p class="section-copy">Simple execution layer for follow-ups, prep work, and delivery handoffs.</p>
            </div>
          </div>
          <form id="task-form" class="form-grid">
            <div class="field"><label>Task title</label><input name="title" required placeholder="Prepare discovery intake for Tuesday call" /></div>
            <div class="field"><label>Linked area</label><select name="area"><option value="pipeline">Pipeline</option><option value="contact">Contact</option><option value="delivery">Delivery</option><option value="ops">Ops</option></select></div>
            <div class="field"><label>Due date</label><input name="due_date" type="date" /></div>
            <div class="field"><label>Status</label><select name="status"><option value="todo">Todo</option><option value="doing">Doing</option><option value="done">Done</option></select></div>
            <div class="field full"><label>Notes</label><textarea name="notes" placeholder="Keep the task context concise and useful."></textarea></div>
            <div class="field full form-actions"><button class="primary-button" type="submit">Add task</button></div>
          </form>
        </article>
      </div>
      <div class="stack">
        <article class="list-panel">
          <div class="section-head">
            <div>
              <h2 class="section-title">Task ledger</h2>
              <p class="section-copy">Toggle status inline. The state file remains the source of truth.</p>
            </div>
          </div>
          ${(state.tasks || []).length ? `<div class="task-list">${state.tasks.map(task => `
            <article class="list-item">
              <div class="list-item-head">
                <strong>${escapeHtml(task.title)}</strong>
                <div class="section-actions">
                  <select class="inline-select" data-task-status="${escapeHtml(task.id)}">
                    <option value="todo" ${task.status === 'todo' ? 'selected' : ''}>Todo</option>
                    <option value="doing" ${task.status === 'doing' ? 'selected' : ''}>Doing</option>
                    <option value="done" ${task.status === 'done' ? 'selected' : ''}>Done</option>
                  </select>
                  <button class="icon-button" data-delete-task="${escapeHtml(task.id)}">×</button>
                </div>
              </div>
              <div class="list-meta">${escapeHtml(task.area || 'General')} · Due ${escapeHtml(formatDate(task.due_date))}</div>
              <div class="list-item-body">${escapeHtml(task.notes || 'No notes yet.')}</div>
            </article>
          `).join('')}</div>` : `<div class="empty-card"><h3 class="empty-title">No tasks yet</h3><p class="empty-copy">Create the first execution item so pipeline work actually moves.</p></div>`}
        </article>
      </div>
    </section>
  `;
}

function renderStudio() {
  const state = store.data;
  return `
    <section class="view-grid">
      <div class="stack">
        <article class="panel">
          <div class="section-head">
            <div>
              <h2 class="section-title">Reusable templates</h2>
              <p class="section-copy">Seeded from the services you selected so outreach and delivery can start immediately.</p>
            </div>
          </div>
          <div class="template-grid">
            ${(state.templates || []).map(template => `
              <article class="content-card">
                <div class="card-head">
                  <h3 class="card-title">${escapeHtml(template.title)}</h3>
                  <span class="pill">${escapeHtml(template.channel)}</span>
                </div>
                <div class="card-meta">${escapeHtml(template.service)}</div>
                <p>${escapeHtml(template.body)}</p>
              </article>
            `).join('')}
          </div>
        </article>
        <article class="panel">
          <div class="section-head">
            <div>
              <h2 class="section-title">Intake forms</h2>
              <p class="section-copy">Questionnaire-derived intake kits to avoid rebuilding the same discovery logic each time.</p>
            </div>
          </div>
          <div class="form-grid-display">
            ${(state.forms || []).map(form => `
              <article class="content-card">
                <div class="card-head">
                  <h3 class="card-title">${escapeHtml(form.title)}</h3>
                  <span class="stage-pill">${escapeHtml(form.status)}</span>
                </div>
                <p>${escapeHtml(form.purpose)}</p>
                <ul>${(form.fields || []).map(field => `<li>${escapeHtml(field)}</li>`).join('')}</ul>
              </article>
            `).join('')}
          </div>
        </article>
      </div>
      <div class="stack">
        <article class="form-panel">
          <div class="section-head">
            <div>
              <h2 class="section-title">Timeline note</h2>
              <p class="section-copy">Capture key operational notes directly into the local state timeline.</p>
            </div>
          </div>
          <form id="note-form" class="form-grid">
            <div class="field"><label>Title</label><input name="title" required placeholder="New partnership lead source" /></div>
            <div class="field"><label>Type</label><select name="type"><option value="ops">Ops</option><option value="delivery">Delivery</option><option value="system">System</option></select></div>
            <div class="field full"><label>Body</label><textarea name="body" required placeholder="What changed, what matters, and what should happen next."></textarea></div>
            <div class="field full form-actions"><button class="primary-button" type="submit">Add note</button></div>
          </form>
        </article>
        <article class="timeline-card">
          <div class="section-head">
            <div>
              <h2 class="section-title">Full timeline</h2>
              <p class="section-copy">Notes, bootstraps, and meaningful local events.</p>
            </div>
          </div>
          <div class="timeline-list">
            ${(state.notes || []).map(note => `
              <article class="timeline-item">
                <div class="timeline-head">
                  <strong>${escapeHtml(note.title)}</strong>
                  <span class="timeline-meta">${escapeHtml(formatDateTime(note.created_at))}</span>
                </div>
                <div class="list-meta">${escapeHtml(note.type || 'system')}</div>
                <div class="timeline-body">${escapeHtml(note.body)}</div>
              </article>
            `).join('')}
          </div>
        </article>
      </div>
    </section>
  `;
}

function renderFooter() {
  return `
    <footer class="footer-bar">
      <div class="footer-meta">State: ${escapeHtml(store.paths?.state_path || 'Unknown')} · Questionnaire: ${escapeHtml(store.questionnaire?.summary_path || 'Unknown')}</div>
      <div class="footer-meta">${escapeHtml(store.saveState)}</div>
    </footer>
  `;
}

function renderError(error) {
  return `
    <main class="page">
      <div class="empty-card">
        <h1 class="empty-title">CRM failed to load</h1>
        <p class="empty-copy">${escapeHtml(error)}</p>
        <div class="section-actions" style="justify-content:center; margin-top:18px;">
          <button class="primary-button" data-action="refresh">Try again</button>
        </div>
      </div>
    </main>
  `;
}

function renderView() {
  switch (store.activeView) {
    case 'pipeline':
      return renderPipeline();
    case 'contacts':
      return renderContacts();
    case 'tasks':
      return renderTasks();
    case 'studio':
      return renderStudio();
    default:
      return renderOverview();
  }
}

function render() {
  if (store.loading) {
    appRoot.innerHTML = `
      <div class="loading-screen">
        <div class="loading-mark">C</div>
        <p>Loading local CRM...</p>
      </div>
    `;
    return;
  }
  if (store.error) {
    appRoot.innerHTML = renderError(store.error);
    bindEvents();
    return;
  }
  appRoot.innerHTML = `
    <main class="page">
      ${renderHero()}
      ${renderMetrics()}
      ${renderNav()}
      ${renderView()}
      ${renderFooter()}
    </main>
  `;
  bindEvents();
}

function bindEvents() {
  appRoot.querySelectorAll('[data-nav]').forEach(button => {
    button.addEventListener('click', () => {
      store.activeView = button.dataset.nav;
      render();
    });
  });

  appRoot.querySelectorAll('[data-action="refresh"]').forEach(button => {
    button.addEventListener('click', () => loadState());
  });

  appRoot.querySelectorAll('[data-action="save"]').forEach(button => {
    button.addEventListener('click', () => saveState());
  });

  const dealForm = document.getElementById('deal-form');
  if (dealForm) {
    dealForm.addEventListener('submit', async event => {
      event.preventDefault();
      const formData = new FormData(dealForm);
      const card = {
        id: uid('deal'),
        title: formData.get('title')?.toString().trim(),
        contact_name: formData.get('contact_name')?.toString().trim(),
        stage_id: formData.get('stage_id')?.toString(),
        service: formData.get('service')?.toString(),
        source: formData.get('source')?.toString(),
        value: formData.get('value')?.toString().trim(),
        next_step: formData.get('next_step')?.toString().trim(),
        due_date: formData.get('due_date')?.toString(),
        note: formData.get('note')?.toString().trim(),
        created_at: new Date().toISOString(),
      };
      store.data.pipeline.cards.unshift(card);
      addNote('Pipeline card added', `${card.title} entered the pipeline at ${card.stage_id}.`, 'pipeline');
      dealForm.reset();
      await saveState();
    });
  }

  appRoot.querySelectorAll('[data-stage-select]').forEach(select => {
    select.addEventListener('change', async () => {
      const card = store.data.pipeline.cards.find(item => item.id === select.dataset.stageSelect);
      if (!card) return;
      card.stage_id = select.value;
      addNote('Pipeline stage updated', `${card.title} moved to ${select.value}.`, 'pipeline');
      await saveState();
    });
  });

  appRoot.querySelectorAll('[data-delete-deal]').forEach(button => {
    button.addEventListener('click', async () => {
      const id = button.dataset.deleteDeal;
      const card = store.data.pipeline.cards.find(item => item.id === id);
      store.data.pipeline.cards = store.data.pipeline.cards.filter(item => item.id !== id);
      addNote('Pipeline card removed', `${card?.title || 'Opportunity'} was removed from the local board.`, 'pipeline');
      await saveState();
    });
  });

  const contactForm = document.getElementById('contact-form');
  if (contactForm) {
    contactForm.addEventListener('submit', async event => {
      event.preventDefault();
      const formData = new FormData(contactForm);
      const contact = {
        id: uid('contact'),
        name: formData.get('name')?.toString().trim(),
        email: formData.get('email')?.toString().trim(),
        segment: formData.get('segment')?.toString(),
        source: formData.get('source')?.toString(),
        service: formData.get('service')?.toString(),
        channel: formData.get('channel')?.toString(),
        notes: formData.get('notes')?.toString().trim(),
        created_at: new Date().toISOString(),
      };
      store.data.contacts.unshift(contact);
      addNote('Contact added', `${contact.name} entered the CRM contact roster.`, 'contact');
      contactForm.reset();
      await saveState();
    });
  }

  appRoot.querySelectorAll('[data-delete-contact]').forEach(button => {
    button.addEventListener('click', async () => {
      const id = button.dataset.deleteContact;
      const contact = store.data.contacts.find(item => item.id === id);
      store.data.contacts = store.data.contacts.filter(item => item.id !== id);
      addNote('Contact removed', `${contact?.name || 'Contact'} was removed from the roster.`, 'contact');
      await saveState();
    });
  });

  const taskForm = document.getElementById('task-form');
  if (taskForm) {
    taskForm.addEventListener('submit', async event => {
      event.preventDefault();
      const formData = new FormData(taskForm);
      const task = {
        id: uid('task'),
        title: formData.get('title')?.toString().trim(),
        area: formData.get('area')?.toString(),
        due_date: formData.get('due_date')?.toString(),
        status: formData.get('status')?.toString(),
        notes: formData.get('notes')?.toString().trim(),
        created_at: new Date().toISOString(),
      };
      store.data.tasks.unshift(task);
      addNote('Task added', `${task.title} was captured in the task ledger.`, 'task');
      taskForm.reset();
      await saveState();
    });
  }

  appRoot.querySelectorAll('[data-task-status]').forEach(select => {
    select.addEventListener('change', async () => {
      const task = store.data.tasks.find(item => item.id === select.dataset.taskStatus);
      if (!task) return;
      task.status = select.value;
      addNote('Task status updated', `${task.title} moved to ${task.status}.`, 'task');
      await saveState();
    });
  });

  appRoot.querySelectorAll('[data-delete-task]').forEach(button => {
    button.addEventListener('click', async () => {
      const id = button.dataset.deleteTask;
      const task = store.data.tasks.find(item => item.id === id);
      store.data.tasks = store.data.tasks.filter(item => item.id !== id);
      addNote('Task removed', `${task?.title || 'Task'} was removed from the ledger.`, 'task');
      await saveState();
    });
  });

  const noteForm = document.getElementById('note-form');
  if (noteForm) {
    noteForm.addEventListener('submit', async event => {
      event.preventDefault();
      const formData = new FormData(noteForm);
      addNote(
        formData.get('title')?.toString().trim(),
        formData.get('body')?.toString().trim(),
        formData.get('type')?.toString() || 'ops',
      );
      noteForm.reset();
      await saveState();
    });
  }
}

loadState();
