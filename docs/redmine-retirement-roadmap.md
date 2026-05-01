# Redmine Retirement Roadmap

Issue: #1000016  
Package: `redmine-retirement-roadmap`  
Target state: Cento Taskstream is the only system of record for agent work, task status, validation evidence, review gates, and operational reporting.

## Executive Summary

Redmine can be discontinued when Cento Taskstream owns every workflow currently depending on Redmine: issue creation, status transitions, journals, custom fields, validation evidence, search, saved views, agent dispatch, review drain, reporting, and historical audit. Taskstream is already functional enough for UI, SQLite-backed task storage, migration, dual-backend parity, agent-work CLI integration, and PWA access, but several prerequisites remain before Redmine can be shut down without losing operational control.

The cutover should happen in four phases:

1. **Parity closure**: fix remaining behavioral gaps and prove list/detail/update/validate parity.
2. **Operational ownership**: move coordinator, agent manager, validators, dashboards, and review drain to replacement-only mode.
3. **Data freeze and migration**: freeze Redmine writes, migrate final state, verify checksums/counts, archive Redmine.
4. **Retirement**: disable Redmine-backed paths, remove scheduled jobs/dependencies, document rollback as archive restore only.

## Current State

- Replacement UI/PWA runs at `http://127.0.0.1:47910/`.
- Replacement DB is SQLite today: `~/.local/state/cento/agent-work-app.sqlite3`.
- `agent_work.py` defaults to replacement backend, with environment-controlled redmine/dual modes.
- Dual-backend stress found that list and core field parity can pass, but attachment/evidence parity can diverge when validation evidence is attached.
- Agent Processes now includes Agent Manager risk signal, but some old Redmine language remains in docs and prompts.

## Prerequisite-To-Task Map

| ID | Prerequisite | Why It Blocks Redmine Retirement | Concrete Implementation Tasks | Validation Gate | Owner Lane | Status |
|---|---|---|---|---|---|---|
| P1 | Replacement is the single write path for agent work | Dual writes can diverge and hide bugs behind Redmine success | Add `CENTO_AGENT_WORK_BACKEND=replacement` hard default audit; remove implicit Redmine fallback from create/update/validate; add explicit `redmine-archive` command for read-only access | `agent_work.py create/update/validate/list/show` passes with no Redmine container or SSH available | backend | Open |
| P2 | Evidence and attachment parity is closed | Validators depend on durable evidence; current stress showed attachment mismatch when evidence exists | Normalize validation evidence storage; persist evidence in `validation_evidences` and `attachments`; expose evidence via API/UI; decide whether Redmine archive imports attachments as metadata-only or copied files | Dual stress with evidence attachment passes detail parity; UI shows evidence on issue detail | backend + validator | Open |
| P3 | Journal/audit semantics are stable | Redmine journals are the audit trail for who changed what and why | Define journal schema contract; preserve old/new status, author, timestamps, notes; normalize author mapping from `admin`/agents; add journal detail rows for changed fields | Contract test proves create, claim, update, validate, block, close all write expected journal rows | backend | Open |
| P4 | Saved queries and task filters are production-grade | Operators rely on review/blocked/running/custom views | Implement saved query CRUD in UI; persist default queries; add filters for package, role, agent, status, tracker, updated range, risk flags | Browser test creates a query, reloads, applies it, exports list | UI + backend | Open |
| P5 | Review drain works replacement-only | Review is the main release gate and used to close batches safely | Ensure `review-drain --package --apply` uses replacement only; enforce validation evidence gates; support dry-run transcript under `workspace/runs/agent-work/review-drain/` | Dry-run and apply close only eligible Review items; blocked/missing-evidence items remain open | coordinator | Open |
| P6 | Agent dispatch no longer references Redmine as active tasking | Builders/validators need prompts, ledgers, and status updates without Redmine terminology | Update prompts and docs from “Redmine” to “Cento Taskstream”; ensure dispatch, run-update, handoff, validate, and recovery-plan work against Taskstream | Dispatch a builder and validator in dry-run and live modes; ledgers and issue state update correctly | agent ops | Open |
| P7 | Agent Manager owns stale/stuck cleanup | Without Redmine, the tasklist must surface process hygiene and remediation | Continue integrating `agent_manager.py`; add `--apply` policies; generate follow-up tickets; include manager risk in UI and dashboard APIs | Manager detects #81-style stuck validators and stale done ledgers; dry-run actions are correct | agent ops | In progress |
| P8 | Coordinator can operate replacement-only | Overnight autonomous work must not depend on Redmine reports or manual chat loop | Convert coordinator reports/actions to replacement APIs; add actor policy controls; ensure no cron/pool action points at Redmine | Coordinator dry-run report and controlled apply both operate with Redmine stopped | coordinator | Open |
| P9 | Migration is repeatable and checksummed | Final cutover needs deterministic snapshot and verification | Build `redmine_retire_migration.py` or extend existing migration; export projects, trackers, statuses, users, issues, journals, custom fields, attachments metadata, validation evidence; write checksums | Re-running migration into empty DB produces identical counts/checksums; mismatch report is empty | migration | Open |
| P10 | Historical Redmine archive is searchable | Retirement cannot mean losing old context | Produce static archive or read-only SQLite import of Redmine history; link from task detail when issue came from Redmine | Random sample of archived issues/journals can be searched and opened without Redmine server | docs + backend | Open |
| P11 | UI has enough admin capability | Redmine UI replacement must support day-to-day task operations | Add create/edit issue modal, status transition controls, journal add, evidence attach, query save, export CSV/JSON, keyboard-safe review flow | Manual acceptance walkthrough covers create -> run -> validate -> review -> done | UI | Open |
| P12 | API contract is documented and tested | Agents and dashboards need stable endpoints | Document `/api/issues`, `/api/issues/{id}`, `/api/runs`, `/api/queries`, evidence endpoints, transition endpoints; add contract check script | Contract test passes against running app and isolated DB | backend | Open |
| P13 | Storage strategy is chosen | SQLite is fine for local use but needs backup/concurrency policy | Decide SQLite WAL vs Postgres-ready path; add backup command; set busy timeout; document single-node constraints | Stress test passes concurrent reads, sync, create/update/validate, evidence writes | backend | Open |
| P14 | Backup and restore are operational | Redmine retirement requires confidence in recovery | Add `agent_work_backup.py` or command in app; backup DB plus evidence files; restore to temp app; verify health | Restore drill produces working UI with same issue counts and sample evidence | ops | Open |
| P15 | Notification and escalation work without Redmine | Operators still need alerts for stuck/blocking work | Wire Agent Manager/coordinator notices to existing notify system; include issue links to replacement UI | Stuck validator creates a local ticket and optional notification without Redmine | ops | Open |
| P16 | All docs and runbooks stop assuming Redmine | Process drift will reintroduce Redmine dependency | Update `docs/agent-work.md`, validator/coordinator lane docs, prompts, README, deliverables hub wording | `rg -i redmine docs scripts templates` reviewed; remaining mentions are archive/migration-only | docs | Open |
| P17 | Cutover switch is explicit and reversible before freeze | Operators need controlled migration, not accidental backend changes | Add `agent-work cutover-status`, `cutover-freeze`, `cutover-verify`, `cutover-finalize`; preserve rollback until final archive | Cutover dry-run prints exact write target, counts, blockers, rollback steps | migration + ops | Open |
| P18 | Redmine dependencies are removed after finalization | Retirement is incomplete if scripts still require containers/SSH | Remove cron jobs, aliases, health checks, Docker dependencies, and transport logic from active path; keep archive commands separate | With Redmine container stopped, normal tasklist workflows pass | ops | Open |

## Implementation Task Backlog

### Phase 1: Parity Closure

1. **Evidence parity fix**
   - Add deterministic evidence storage for validation reports.
   - Ensure replacement and archive import represent evidence consistently.
   - Re-run dual-backend stress with evidence and require detail parity pass.

2. **Journal contract hardening**
   - Define expected journal rows for create/claim/update/validate/block/done.
   - Add contract tests for status transitions and note authors.
   - Normalize agent author names.

3. **Replacement-only API contract**
   - Add `scripts/agent_work_app_contract_check.py` coverage for issue CRUD, queries, journals, attachments, and evidence.
   - Require app to pass with Redmine stopped.

4. **Saved query and filter completion**
   - Implement UI controls for package, role, agent, status, tracker, evidence, risk.
   - Add saved query CRUD in the UI.

### Phase 2: Operational Ownership

5. **Agent dispatch replacement-only cleanup**
   - Remove Redmine wording from prompts.
   - Ensure dispatch/run-update/validate/handoff/review-drain do not need Redmine.
   - Add a live smoke run against an isolated replacement DB.

6. **Agent Manager policy integration**
   - Add policy file for safe auto-remediation.
   - Implement apply flows for stale ledger reconciliation and issue blocking.
   - Keep tmux termination behind explicit operator approval.

7. **Coordinator replacement-only actor mode**
   - Use replacement APIs for board state, context gathering, and action reports.
   - Add controls for read-only, recommend-only, and actor modes.

8. **Dashboard integration**
   - Show replacement tasklist health, manager risk count, stuck agents, and review queue in Industrial OS dashboard.
   - Link issue rows to `http://127.0.0.1:47910/?issue=ID`.

### Phase 3: Migration and Cutover

9. **Final migration tool**
   - Snapshot Redmine into replacement DB.
   - Copy or index evidence files.
   - Produce JSON/Markdown migration report.

10. **Cutover runbook**
    - Document exact commands for freeze, migrate, verify, finalize.
    - Include rollback window and archive restore procedure.

11. **Backup/restore drill**
    - Add backup command for DB + evidence.
    - Restore into temp DB and run contract checks.

12. **Read-only archive**
    - Keep Redmine data searchable without running Redmine.
    - Add archive links for migrated issues.

### Phase 4: Retirement

13. **Disable Redmine active path**
    - Remove active Redmine transport from default workflows.
    - Fail fast if a workflow tries to write Redmine after finalization.

14. **Remove scheduled Redmine dependencies**
    - Audit cron/tmux/systemd/scripts for Redmine references.
    - Keep only archive/migration commands.

15. **Final acceptance**
    - Run replacement-only e2e.
    - Run agent manager scan.
    - Run coordinator dry-run.
    - Run UI/PWA smoke test.
    - Confirm Redmine stopped and normal tasklist operations still pass.

## Cutover Gates

| Gate | Required Evidence | Pass Criteria |
|---|---|---|
| G1: Replacement-only smoke | `agent_work.py create/update/validate/list/show`, UI issue detail, PWA load | All pass with Redmine stopped |
| G2: Evidence parity | Dual stress with validation evidence | List and detail parity pass, no attachment mismatch |
| G3: Review gate | `review-drain --dry-run` and `--apply` on test package | Only validated Review items close |
| G4: Agent operations | Dispatch dry-run/live smoke, run ledger update, Agent Manager scan | No Redmine dependency, risks surfaced |
| G5: Migration verification | Counts/checksums/report | No missing issues/journals/evidence metadata |
| G6: Backup restore | Restore drill report | Restored DB serves UI and passes contract checks |
| G7: Final stop | Redmine container/transport disabled | Normal tasklist workflows still pass |

## Issue #133 Operator Gate Playbook (Redmine unavailable window)

### One-time local permission setup

1. Ensure root-only compose control exists for operators:

```bash
sudo mkdir -p /etc/sudoers.d
sudo sh -c 'cat > /etc/sudoers.d/cento-redmine-cutover <<EOF
alice ALL=(root) NOPASSWD: /home/alice/projects/cento/experimental/redmine-career-consulting/scripts/redmine-compose-root.sh *
EOF'
sudo chmod 440 /etc/sudoers.d/cento-redmine-cutover
```

Replace `alice` and `/home/alice/projects/cento` with the local operator account and repo path.

2. Verify helper visibility and command execution non-interactively:

```bash
cd /home/alice/projects/cento/experimental/redmine-career-consulting
./scripts/redmine-compose-root.sh ps
```

### Validation window command set

- Stop Redmine (isolate for replacement-only validation):

```bash
cd /home/alice/projects/cento/experimental/redmine-career-consulting
./scripts/redmine.sh cutover-stop
```

- Confirm Cento Taskstream operations still succeed while Redmine is unavailable:

```bash
cento agent-work bootstrap
./scripts/agent_work_e2e.sh 2>&1 | tee workspace/runs/agent-work/133/redmine-unavailable-smoke.log
curl -fsS http://127.0.0.1:47910/ > /tmp/redmine-unavailable-pwa.html
```

- Confirm Redmine is stopped:

```bash
./scripts/redmine.sh cutover-status
```

### Rollback/start steps

- Bring Redmine back online after the validation window:

```bash
cd /home/alice/projects/cento/experimental/redmine-career-consulting
./scripts/redmine.sh cutover-start
```

- Restarted state check:

```bash
./scripts/redmine.sh cutover-status
```

## Rollback Policy

Before finalization:

- Keep Redmine read/write available.
- Run dual-backend parity after every migration rehearsal.
- Roll back by setting `CENTO_AGENT_WORK_BACKEND=redmine` and restarting affected services.

After finalization:

- Redmine is archive-only.
- Rollback means restoring the replacement DB/evidence backup, not resuming Redmine writes.
- Any Redmine write attempt should fail with an explicit message.

## Immediate Next Tasks To Create

1. `Fix validation evidence attachment parity for replacement tasklist`
2. `Add replacement-only contract check for issue CRUD, journals, queries, and evidence`
3. `Update agent dispatch prompts and docs to remove Redmine active-system language`
4. `Implement replacement backup and restore drill`
5. `Add cutover-status/freeze/verify/finalize commands`
6. `Integrate Agent Manager risk summary into dashboard API`
7. `Create Redmine archive search/export view`

## Definition Of Done For Redmine Retirement

- Redmine can be stopped for 24 hours while create/claim/update/validate/review/close workflows continue in Cento Taskstream.
- Agent Manager and coordinator reports operate replacement-only.
- UI/PWA covers list, detail, search, saved queries, evidence, journals, and review workflow.
- Migration report proves no missing active issues or audit rows.
- Backup/restore drill passes.
- All remaining Redmine references in active workflows are removed or explicitly labeled archive/migration.
