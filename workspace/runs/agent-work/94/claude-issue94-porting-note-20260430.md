Now I have a complete picture. Here is the coordination note:

---

## Coordination Note — Issue #94: Linux Pool Tooling → Mac/origin main

### Current State Summary

| Layer | Content |
|---|---|
| **origin/main** | Newer commit: includes MCP tooling updates, workspace runs 60/61/82, deleted CLAUDE.md/CLUSTER_NOTICE.md/cento_mcp_server.py |
| **Linux local HEAD** | Older commit — behind origin/main by several commits (missing the MCP work) |
| **Linux dirty working tree** | 18 modified files (3,356 insertions) + 15+ untracked new scripts, all uncommitted |

The Linux machine has not pulled origin/main, so local HEAD diverges significantly from it.

---

### Safe to Port to Mac main (net-new, no overwrite risk)

Both target scripts are **untracked on Linux** (never committed anywhere) and are self-contained enough to copy directly:

**`scripts/agent_pool_kick.py`** — Safe to add to origin/main as-is.
- Calls `python3 scripts/agent_work.py runs --json --active --no-untracked` and `list --json`.
- Both flags confirmed present in origin/main's `agent_work.py` (lines 2135, 2137, 2043–2045).
- Also calls `./scripts/cento.sh agent-work dispatch` — verify that path resolves on Mac.

**`scripts/agent_work_hygiene.sh`** — Safe to add to origin/main as-is.
- Calls `cento agent-work runs --json --reconcile` — `--reconcile` flag confirmed at line 2139 of origin/main's `agent_work.py`.
- Output goes to `workspace/runs/agent-work/reconciliation/` — path is created at runtime, no pre-existing conflict.

Other **untracked scripts that are similarly net-new** (no origin/main counterpart, safe to port when ready): `agent_coordinator.py`, `agent_work_hygiene.sh`, `industrial_activity.py`, `*_contract_check.py` files, `story_screenshot_runner.py`, `migrate_redmine_to_tracker.py`.

---

### Conflicts / Version Skew That Matter

**`scripts/agent_work.py` — HIGH RISK, do not blindly overwrite.**

The Linux dirty tree adds a full dual-backend migration layer on top of the older local HEAD:
- `import sqlite3`, `import agent_work_app` (the latter is an untracked file `scripts/agent_work_app.py`)
- Constants: `BACKEND_REDLINE`, `BACKEND_REPLACEMENT`, `BACKEND_DUAL`, `TRACKER_DB_PATH`, `DEFAULT_REPLACEMENT_API = "http://127.0.0.1:47910"`, `REPLACEMENT_LOCAL_ID_FLOOR`
- `agent_work_backend()` dispatcher routing Redmine vs. replacement vs. dual

Meanwhile, origin/main has advanced the same file with ~214 lines of MCP and other changes not present in the Linux HEAD. A `git pull` over dirty Linux state would either refuse (dirty tree) or produce merge conflicts in this file.

**Other dirty modified files requiring merge resolution before pull:**

| File | Dirty change size | Risk |
|---|---|---|
| `scripts/industrial_panel.py` | 613-line change | Medium — active development |
| `scripts/industrial_jobs_tui.go` | 403-line change | Medium |
| `scripts/network_web_server.py` | 194 lines added | Low — likely new endpoints |
| `scripts/industrial_aux_tui.go` | 209 lines | Medium |
| `scripts/industrial_cluster_tui.go` | 168 lines | Medium |
| `scripts/jobs_server.py` | 150-line change | Medium |
| `scripts/agent_work.py` | 1,509-line change | **Critical** |
| `Makefile`, `data/tools.json`, `docs/*`, `workspace/runs/agent-work/59/story.json` | Smaller | Low |

**Key dependency chain:** `agent_work.py` (dirty) imports `agent_work_app` (untracked). If `agent_work.py` is merged to origin/main without also porting `scripts/agent_work_app.py`, the merged file will fail to import.

---

### Recommended Approach

1. **Commit or stash Linux dirty work to a branch before touching origin/main:**
   ```bash
   git checkout -b linux/pool-tooling-wip
   git add scripts/agent_pool_kick.py scripts/agent_work_hygiene.sh scripts/agent_work_app.py  # + others
   git add -p  # selectively stage dirty changes
   git commit -m "wip: Linux pool tooling and dual-backend migration"
   ```

2. **Port the two untracked pool scripts directly to Mac main** (no conflict risk):
   ```bash
   git checkout main
   git add scripts/agent_pool_kick.py scripts/agent_work_hygiene.sh
   git commit -m "Add agent pool kick and hygiene scripts"
   git push origin main
   ```

3. **Merge the dual-backend agent_work.py changes** via a proper three-way merge between Linux WIP branch, origin/main, and the common ancestor.

---

### Validation Commands

```bash
# Confirm pool kick script works against origin/main's agent_work.py
python3 scripts/agent_pool_kick.py --dry-run

# Confirm hygiene script help text loads (no missing deps)
bash scripts/agent_work_hygiene.sh --help

# Confirm agent_work.py CLI is intact after any merge
python3 scripts/agent_work.py --help

# Confirm the two key subcommands agent_pool_kick.py depends on exist
python3 scripts/agent_work.py runs --json --active --no-untracked 2>&1 | python3 -c "import sys,json; d=json.load(sys.stdin); print('ok, runs:', len(d.get('runs',[])))"
python3 scripts/agent_work.py list --json 2>&1 | python3 -c "import sys,json; d=json.load(sys.stdin); print('ok, issues:', len(d.get('issues',[])))"

# After merging agent_work.py: confirm import of agent_work_app does not blow up
python3 -c "import sys; sys.path.insert(0, 'scripts'); import agent_work_app; print('agent_work_app ok')"

# Run existing e2e after merge
bash scripts/agent_work_e2e.sh
```

---

**Bottom line:** `agent_pool_kick.py` and `agent_work_hygiene.sh` are safe to land on Mac main immediately. The `agent_work.py` dual-backend migration is the landmine — it must be merged (not overwritten) and must travel with `agent_work_app.py` as a co-dependency.
y`, `scripts/migrate_redmine_to_tracker.py`, `scripts/agent_work_app_contract_check.py`, `scripts/agent_work_dual_backend_stress.sh`, `scripts/agent_work_redmine_replacement_visual_validation.py`, `scripts/fixtures/` |
| **D — activity + panel** (after B) | `scripts/industrial_activity.py`, `scripts/industrial_activity_contract_check.py`, `scripts/industrial_panel.py`, `scripts/industrial_panel_e2e.sh`, `scripts/industrial_aux_tui.go`, `scripts/story_screenshot_runner.py` |
| **E — cluster TUI + network server** | `scripts/industrial_cluster_tui.go`, `scripts/industrial_jobs_tui.go`, `scripts/jobs_server.py`, `scripts/network_web_server.py` — verify health payload shape is consistent before separating Go from Python side |
| **F — coordinator** | `scripts/agent_coordinator.py` (inspect first; likely also calls updated `agent_work.py`) |
| **G — app scaffolding** | `apps/agent-tracker/`, `templates/agent-work-app/`, `apps/ios/CentoMobile/README.md` — review separately; `agent-tracker-backend` Makefile target points to `apps/agent-tracker/backend/main.py` via uvicorn |

---

### Validation commands (run on Mac main after each bundle)

```bash
# After bundle B:
python3 -m py_compile scripts/agent_work.py scripts/agent_work_app.py
python3 -c "import sys; sys.path.insert(0,'scripts'); import agent_work_app; print('agent_work_app ok')"
make check   # existing syntax check target

# After bundle C:
python3 scripts/agent_pool_kick.py --dry-run
./scripts/agent_work_hygiene.sh --out-dir /tmp/hygiene-smoke 2>&1 | tail -5
CENTO_AGENT_WORK_BACKEND=replacement ./scripts/agent_work_e2e.sh

# After bundle D:
python3 -c "import sys; sys.path.insert(0,'scripts'); from industrial_activity import build_activity_events; print('ok')"
./scripts/industrial_panel_e2e.sh   # if it exists and is runnable on Mac

# After bundle E:
# Re-run Go TUI build
cd scripts && go build -o /dev/null ./industrial_cluster_tui.go ./industrial_jobs_tui.go ./industrial_aux_tui.go 2>&1

# General dual-backend smoke (after all bundles):
CENTO_AGENT_WORK_BACKEND=dual make agent-work-e2e
```

---

### Do not port

- `workspace/runs/agent-work/59/story.json` — Linux-local run artifact, will collide with Mac's workspace state.
- Any `apps/agent-tracker/db/` SQLite files if present — these are runtime state, not source.
