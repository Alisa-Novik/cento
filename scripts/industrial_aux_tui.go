package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"time"

	tea "charm.land/bubbletea/v2"
	"charm.land/lipgloss/v2"
)

type tickMsg time.Time

type activityLoadedMsg struct {
	entries []activityEntry
}

type actionDoneMsg struct {
	action quickAction
	output string
	err    error
	dryRun bool
}

type agentBoardLoadedMsg struct {
	runs    []agentRun
	issues  []agentIssue
	manager agentManagerSummary
	err     error
}

type activityEntry struct {
	Stamp    string `json:"stamp"`
	Age      string `json:"age"`
	Label    string `json:"message"`
	Badge    string `json:"kind"`
	Source   string `json:"source"`
	Severity string `json:"severity"`
	Hot      bool
}

type quickAction struct {
	Key                  string   `json:"key"`
	ID                   string   `json:"id"`
	Label                string   `json:"label"`
	Description          string   `json:"description"`
	Allowlist            []string `json:"allowlist"`
	Command              []string `json:"command"`
	DryRunCommand        []string `json:"dry_run_command"`
	TargetNode           string   `json:"target_node"`
	AvailabilityCheck    string   `json:"availability_check"`
	ExpectedOutputSignal string   `json:"expected_output_signal"`
	Available            bool     `json:"-"`
	AvailabilityReason   string   `json:"-"`
}

type agentRun struct {
	RunID     string      `json:"run_id"`
	IssueID   interface{} `json:"issue_id"`
	Package   string      `json:"package"`
	Node      string      `json:"node"`
	Agent     string      `json:"agent"`
	Role      string      `json:"role"`
	Runtime   string      `json:"runtime"`
	Model     string      `json:"model"`
	Command   string      `json:"command"`
	PID       interface{} `json:"pid"`
	Status    string      `json:"status"`
	Health    string      `json:"health"`
	LogPath   string      `json:"log_path"`
	Elapsed   string      `json:"elapsed"`
	UpdatedAt string      `json:"updated_at"`
}

type agentIssue struct {
	ID        int    `json:"id"`
	Subject   string `json:"subject"`
	Tracker   string `json:"tracker"`
	Status    string `json:"status"`
	Node      string `json:"node"`
	Agent     string `json:"agent"`
	Role      string `json:"role"`
	Package   string `json:"package"`
	DoneRatio int    `json:"done_ratio"`
}

type agentRunsPayload struct {
	Runs []agentRun `json:"runs"`
}

type agentIssuesPayload struct {
	Issues []agentIssue `json:"issues"`
}

type agentManagerPayload struct {
	Summary agentManagerSummary `json:"summary"`
}

type agentManagerSummary struct {
	Live            int            `json:"live"`
	ManagedLive     int            `json:"managed_live"`
	Manual          int            `json:"manual"`
	Stale           int            `json:"stale"`
	ActionableStale int            `json:"actionable_stale"`
	HistoricalStale int            `json:"historical_stale"`
	Archived        int            `json:"archived"`
	Stuck           int            `json:"stuck"`
	Idle            int            `json:"idle"`
	Errored         int            `json:"errored"`
	Duplicate       int            `json:"duplicate"`
	Critical        int            `json:"critical"`
	Warning         int            `json:"warning"`
	RiskCount       int            `json:"risk_count"`
	ByRole          map[string]int `json:"by_role"`
}

type auxModel struct {
	root     string
	mode     string
	width    int
	height   int
	interval time.Duration
	entries  []activityEntry
	actions  []quickAction
	agents   []agentRun
	work     []agentIssue
	manager  agentManagerSummary
	agentErr string
	selected int
	running  string
	output   string
	filter   string
}

var (
	auxOrange     = lipgloss.Color("#FF4B00")
	auxAmber      = lipgloss.Color("#FF9A3D")
	auxGreen      = lipgloss.Color("#A0D76E")
	auxPurple     = lipgloss.Color("#B68CFF")
	auxText       = lipgloss.Color("#FFFFFF")
	auxMuted      = lipgloss.Color("#DCCFC4")
	auxDark       = lipgloss.Color("#080909")
	auxPanel      = lipgloss.NewStyle().Foreground(auxText).Background(lipgloss.Color("#050403")).Padding(1, 1)
	auxTitle      = lipgloss.NewStyle().Foreground(auxOrange).Bold(true)
	auxTextStyle  = lipgloss.NewStyle().Foreground(auxText)
	auxMutedStyle = lipgloss.NewStyle().Foreground(auxMuted)
	auxHotDot     = lipgloss.NewStyle().Foreground(auxOrange).Bold(true).Render("●")
	auxQuietDot   = lipgloss.NewStyle().Foreground(auxMuted).Render("●")
	auxLine       = lipgloss.NewStyle().Foreground(lipgloss.Color("#3D3430")).Render("│")
	auxActionCard = lipgloss.NewStyle().Background(lipgloss.Color("#111315")).Padding(0, 1).MarginBottom(1)
	auxActiveCard = lipgloss.NewStyle().Background(lipgloss.Color("#17191B")).Border(lipgloss.NormalBorder(), false, false, false, true).BorderForeground(auxOrange).Padding(0, 1).MarginBottom(1)
	auxANSIPat    = regexp.MustCompile(`\x1b\[[0-9;?]*[ -/]*[@-~]`)
)

func initRoot() string {
	if root := os.Getenv("CENTO_ROOT_DIR"); root != "" {
		return root
	}
	if cwd, err := os.Getwd(); err == nil {
		if _, err := os.Stat(filepath.Join(cwd, "data", "tools.json")); err == nil {
			return cwd
		}
	}
	return "."
}

func actionPlatform() string {
	switch runtime.GOOS {
	case "darwin":
		return "macos"
	default:
		return runtime.GOOS
	}
}

func normalizeActionPlatform(value string) string {
	switch strings.ToLower(value) {
	case "darwin":
		return "macos"
	default:
		return strings.ToLower(value)
	}
}

func actionFilePath(root string) string {
	return filepath.Join(root, "data", "industrial-actions.json")
}

func parseCommandValue(value any) []string {
	switch typed := value.(type) {
	case nil:
		return nil
	case string:
		fields := strings.Fields(typed)
		out := make([]string, 0, len(fields))
		for _, field := range fields {
			if strings.TrimSpace(field) != "" {
				out = append(out, field)
			}
		}
		return out
	case []any:
		out := make([]string, 0, len(typed))
		for _, item := range typed {
			text := strings.TrimSpace(fmt.Sprint(item))
			if text != "" {
				out = append(out, text)
			}
		}
		return out
	case []string:
		out := make([]string, 0, len(typed))
		for _, item := range typed {
			text := strings.TrimSpace(item)
			if text != "" {
				out = append(out, text)
			}
		}
		return out
	default:
		return nil
	}
}

func actionText(command []string) string {
	return strings.Join(command, " ")
}

func loadQuickActions(root string) []quickAction {
	raw, err := os.ReadFile(actionFilePath(root))
	if err != nil {
		return nil
	}
	var payload any
	if err := json.Unmarshal(raw, &payload); err != nil {
		return nil
	}
	items := make([]any, 0)
	switch typed := payload.(type) {
	case []any:
		items = typed
	case map[string]any:
		if actions, ok := typed["actions"].([]any); ok {
			items = actions
		}
	default:
		return nil
	}
	actions := make([]quickAction, 0, len(items))
	for index, item := range items {
		rawAction, ok := item.(map[string]any)
		if !ok {
			continue
		}
		action := quickAction{
			Key:                  strings.TrimSpace(fmt.Sprint(rawAction["key"])),
			ID:                   strings.TrimSpace(fmt.Sprint(rawAction["id"])),
			Label:                strings.TrimSpace(fmt.Sprint(rawAction["label"])),
			Description:          strings.TrimSpace(fmt.Sprint(rawAction["description"])),
			Allowlist:            []string{},
			Command:              parseCommandValue(rawAction["command"]),
			DryRunCommand:        parseCommandValue(rawAction["dry_run_command"]),
			TargetNode:           strings.TrimSpace(fmt.Sprint(rawAction["target_node"])),
			AvailabilityCheck:    strings.TrimSpace(fmt.Sprint(rawAction["availability_check"])),
			ExpectedOutputSignal: strings.TrimSpace(fmt.Sprint(rawAction["expected_output_signal"])),
		}
		if allowlist, ok := rawAction["allowlist"].([]any); ok {
			for _, value := range allowlist {
				text := normalizeActionPlatform(fmt.Sprint(value))
				if text != "" {
					action.Allowlist = append(action.Allowlist, text)
				}
			}
		}
		if action.Key == "" {
			action.Key = fmt.Sprint(index + 1)
		}
		if action.ID == "" {
			action.ID = fmt.Sprintf("action-%d", index+1)
		}
		if action.Label == "" {
			action.Label = fmt.Sprintf("Action %d", index+1)
		}
		if action.TargetNode == "" {
			action.TargetNode = "cluster"
		}
		if action.AvailabilityCheck == "" {
			action.AvailabilityCheck = "always"
		}
		actions = append(actions, action)
	}
	return actions
}

func loadClusterSnapshot(root string) (map[string]any, error) {
	code := `
import json
import sys
sys.path.insert(0, "scripts")
from network_web_server import cluster_snapshot
print(json.dumps(cluster_snapshot()))
`
	cmd := exec.Command("python3", "-c", code)
	cmd.Dir = root
	cmd.Env = append(os.Environ(), "CENTO_ROOT_DIR="+root)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return nil, fmt.Errorf("%v: %s", err, strings.TrimSpace(string(out)))
	}
	var payload map[string]any
	if err := json.Unmarshal(out, &payload); err != nil {
		return nil, err
	}
	return payload, nil
}

func actionIsAllowed(action quickAction, platformName string) (bool, string) {
	platformName = normalizeActionPlatform(platformName)
	if len(action.Allowlist) == 0 {
		return true, ""
	}
	for _, item := range action.Allowlist {
		if normalizeActionPlatform(item) == platformName {
			return true, ""
		}
	}
	return false, fmt.Sprintf("not available on %s (allowlist: %s)", platformName, strings.Join(action.Allowlist, ", "))
}

func actionClusterAvailable(action quickAction, clusterPayload map[string]any, clusterError error) (bool, string) {
	if clusterError != nil {
		return false, fmt.Sprintf("cluster payload unavailable: %v", clusterError)
	}
	if strings.EqualFold(action.AvailabilityCheck, "always") {
		return true, ""
	}
	health, _ := clusterPayload["health"].(map[string]any)
	nodes, _ := health["nodes"].([]any)
	switch strings.ToLower(action.AvailabilityCheck) {
	case "non_empty_cluster":
		if len(nodes) == 0 {
			return false, "cluster has no registered nodes"
		}
		return true, ""
	case "degraded_nodes":
		if len(nodes) == 0 {
			return false, "cluster has no registered nodes"
		}
		for _, item := range nodes {
			node, ok := item.(map[string]any)
			if !ok {
				continue
			}
			state := strings.ToLower(strings.TrimSpace(fmt.Sprint(node["state"])))
			if state == "degraded" || state == "offline" {
				return true, ""
			}
		}
		return false, "no degraded or offline nodes"
	default:
		return true, ""
	}
}

func actionMetadataLines(action quickAction, width int) []string {
	allowlist := "all"
	if len(action.Allowlist) > 0 {
		allowlist = strings.Join(action.Allowlist, ", ")
	}
	lines := []string{
		"DESCRIPTION  " + clip(action.Description, max(1, width-14)),
		"ALLOWLIST    " + clip(allowlist, max(1, width-14)),
		"TARGET NODE  " + clip(action.TargetNode, max(1, width-14)),
		"DRY RUN      " + clip(actionText(action.DryRunCommand), max(1, width-14)),
		"EXPECTED     " + clip(action.ExpectedOutputSignal, max(1, width-14)),
		"CHECK        " + clip(action.AvailabilityCheck, max(1, width-14)),
	}
	return lines
}

func resolveActionRows(root string, actions []quickAction) ([]quickAction, error) {
	clusterPayload, clusterErr := loadClusterSnapshot(root)
	rows := make([]quickAction, 0, len(actions))
	for _, action := range actions {
		entry := action
		available, reason := actionIsAllowed(action, actionPlatform())
		if available {
			clusterAvailable, clusterReason := actionClusterAvailable(action, clusterPayload, clusterErr)
			if !clusterAvailable {
				available = false
				reason = clusterReason
			}
		}
		if reason == "" {
			reason = "ready"
		}
		entry.Available = available
		entry.AvailabilityReason = reason
		rows = append(rows, entry)
	}
	return rows, clusterErr
}

func newModel(root, mode string, interval time.Duration) auxModel {
	return auxModel{
		root:     root,
		mode:     mode,
		interval: interval,
		actions:  loadQuickActions(root),
	}
}

func (m auxModel) Init() tea.Cmd {
	if m.mode == "activity" {
		return tea.Batch(loadActivityCmd(m.root), tickCmd(m.interval))
	}
	if m.mode == "agents" {
		return tea.Batch(loadAgentBoardCmd(m.root), tickCmd(m.interval))
	}
	return tickCmd(m.interval)
}

func (m auxModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
	case tea.KeyPressMsg:
		switch msg.String() {
		case "ctrl+c", "q":
			return m, tea.Quit
		case "r":
			if m.mode == "activity" {
				return m, loadActivityCmd(m.root)
			}
			if m.mode == "agents" {
				return m, loadAgentBoardCmd(m.root)
			}
		case "0":
			if m.mode == "activity" {
				m.filter = ""
			}
		case "!", "1":
			if m.mode == "activity" {
				m.filter = "hot"
			}
		case "c":
			if m.mode == "activity" {
				m.filter = "cluster"
			}
		case "j":
			if m.mode == "activity" {
				m.filter = "jobs"
			} else if m.mode == "actions" && m.selected < len(m.actions)-1 {
				m.selected++
			}
		case "a":
			if m.mode == "activity" {
				m.filter = "agent-work"
			}
		case "l":
			if m.mode == "activity" {
				m.filter = "log"
			}
		case "up", "k":
			if m.mode == "actions" && m.selected > 0 {
				m.selected--
			}
		case "down":
			if m.mode == "actions" && m.selected < len(m.actions)-1 {
				m.selected++
			}
		case "enter":
			if m.mode == "actions" && len(m.actions) > 0 {
				rows, err := resolveActionRows(m.root, m.actions)
				if err != nil && len(rows) == 0 {
					m.output = err.Error()
					return m, nil
				}
				selected := clamp(m.selected, 0, len(rows)-1)
				action := rows[selected]
				if !action.Available {
					m.output = action.AvailabilityReason
					return m, nil
				}
				m.running = actionText(action.Command)
				m.output = "running..."
				return m, runActionCmd(m.root, action, false)
			}
		case "d":
			if m.mode == "actions" && len(m.actions) > 0 {
				rows, err := resolveActionRows(m.root, m.actions)
				if err != nil && len(rows) == 0 {
					m.output = err.Error()
					return m, nil
				}
				selected := clamp(m.selected, 0, len(rows)-1)
				action := rows[selected]
				allowed, reason := actionIsAllowed(action, actionPlatform())
				if !allowed {
					m.output = reason
					return m, nil
				}
				m.running = actionText(action.DryRunCommand)
				m.output = "dry-running..."
				return m, runActionCmd(m.root, action, true)
			}
		}
	case tickMsg:
		if m.mode == "activity" {
			return m, tea.Batch(loadActivityCmd(m.root), tickCmd(m.interval))
		}
		if m.mode == "agents" {
			return m, tea.Batch(loadAgentBoardCmd(m.root), tickCmd(m.interval))
		}
		return m, tickCmd(m.interval)
	case activityLoadedMsg:
		m.entries = msg.entries
	case agentBoardLoadedMsg:
		m.agents = msg.runs
		m.work = msg.issues
		m.manager = msg.manager
		m.agentErr = ""
		if msg.err != nil {
			m.agentErr = msg.err.Error()
		}
	case actionDoneMsg:
		m.running = ""
		m.output = msg.output
		if msg.err != nil {
			m.output = fmt.Sprintf("%v: %s", msg.err, msg.output)
		} else if strings.TrimSpace(m.output) == "" {
			m.output = "completed: " + actionText(msg.action.Command)
		}
		if expected := strings.TrimSpace(msg.action.ExpectedOutputSignal); expected != "" && !strings.Contains(msg.output, expected) {
			if strings.TrimSpace(m.output) == "" {
				m.output = "missing expected output signal: " + expected
			} else {
				m.output = m.output + "\nmissing expected output signal: " + expected
			}
		}
	}
	return m, nil
}

func (m auxModel) View() tea.View {
	width := m.width
	if width <= 0 {
		width = 46
	}
	width = clamp(width-2, 34, 58)
	bodyWidth := width - 4
	var body string
	if m.mode == "actions" {
		body = m.renderActions(bodyWidth)
	} else if m.mode == "agents" {
		body = m.renderAgents(bodyWidth)
	} else {
		body = m.renderActivity(bodyWidth)
	}
	view := tea.NewView(auxPanel.Width(width).Render(body))
	view.AltScreen = true
	return view
}

func (m auxModel) renderActivity(width int) string {
	rows := make([]string, 0, 16)
	rows = append(rows, auxTitle.Render("♨ ACTIVITY FEED"), "")
	entries := filteredActivity(m.entries, m.filter)
	filterLabel := "all"
	if m.filter != "" {
		filterLabel = m.filter
	}
	rows = append(rows, auxMutedStyle.Render(clip("filter: "+filterLabel+" · 0 all · ! hot · c cluster · j jobs · a agents · l logs", width)), "")
	if len(entries) == 0 {
		rows = append(rows, auxMutedStyle.Render("no recent activity"))
	} else {
		for index, entry := range entries[:min(len(entries), 5)] {
			rows = append(rows, activityLine(entry, width))
			if index < min(len(entries), 5)-1 {
				rows = append(rows, "  "+auxLine)
			}
		}
	}
	rows = append(rows, "", auxMutedStyle.Render(clip("r refresh · q quit", width)))
	return lipgloss.JoinVertical(lipgloss.Left, rows...)
}

func (m auxModel) renderActions(width int) string {
	rowsResolved, clusterErr := resolveActionRows(m.root, m.actions)
	rows := []string{auxTitle.Render("QUICK ACTIONS"), ""}
	cardWidth := max(20, width-4)
	for index, action := range rowsResolved {
		prefix := auxAmberStyle().Render("›")
		textWidth := max(8, cardWidth-5)
		command := auxTextStyle.Render(clip(actionText(action.Command), textWidth))
		label := auxMutedStyle.Render(clip(action.Label, textWidth))
		cardBody := lipgloss.JoinVertical(lipgloss.Left, prefix+"  "+command, "   "+label)
		style := auxActionCard.Width(cardWidth)
		if index == m.selected {
			style = auxActiveCard.Width(cardWidth - 1)
		}
		rows = append(rows, style.Render(cardBody))
	}
	if clusterErr != nil {
		rows = append(rows, auxMutedStyle.Render("cluster unavailable: "+clusterErr.Error()))
	}
	prompt := "› _"
	if m.running != "" {
		prompt = "› " + m.running
	} else if m.output != "" {
		prompt = "› " + clip(strings.TrimSpace(m.output), width-3)
	}
	rows = append(rows, auxMutedStyle.Render(prompt))
	rows = append(rows, auxMutedStyle.Render("j/k move · enter run · d dry-run · q quit"))
	if len(rowsResolved) > 0 {
		selected := clamp(m.selected, 0, len(rowsResolved)-1)
		action := rowsResolved[selected]
		rows = append(rows, "")
		rows = append(rows, auxAmberStyle().Render("ACTION DETAILS"))
		for _, line := range actionMetadataLines(action, width) {
			rows = append(rows, auxMutedStyle.Render(line))
		}
	}
	return lipgloss.JoinVertical(lipgloss.Left, rows...)
}

func (m auxModel) renderAgents(width int) string {
	rows := []string{auxTitle.Render("AGENT PROCESSES"), ""}
	ledger := 0
	manual := 0
	stale := 0
	for _, run := range m.agents {
		switch run.Status {
		case "running", "launching", "planned":
			ledger++
		case "untracked_interactive":
			manual++
		case "stale":
			stale++
		}
	}
	workItems := nonEpicWork(m.work)
	activeIssues := 0
	queuedWork := 0
	for _, issue := range workItems {
		if isActiveIssueSignal(issue.Status) {
			activeIssues++
		} else if strings.EqualFold(issue.Status, "Queued") {
			queuedWork++
		}
	}
	live := ledger + manual
	summary := fmt.Sprintf("%d live · %d managed · %d manual", live, ledger, manual)
	if queuedWork > 0 {
		summary += fmt.Sprintf(" · %d queued", queuedWork)
	}
	if stale > 0 {
		summary += fmt.Sprintf(" · %d stale", stale)
	}
	rows = append(rows, auxMutedStyle.Render(clip(summary, width)))
	rows = append(rows, runtimeLegend())
	if managerLine := agentManagerLine(m.manager, width); managerLine != "" {
		rows = append(rows, managerLine)
	}
	rows = append(rows, "")
	if m.agentErr != "" {
		rows = append(rows, badgeStyle("WARN").Render("WARN")+" "+auxTextStyle.Render(clip(m.agentErr, width-8)))
	} else {
		processRows := agentProcessRuns(m.agents, 5)
		if len(processRows) > 0 {
			rows = append(rows, auxMutedStyle.Render("Running now"))
			for _, run := range processRows {
				rows = append(rows, agentLine(run, width))
			}
		} else {
			rows = append(rows, auxMutedStyle.Render("no live agent process detected"))
		}
		if activeIssues > 0 || queuedWork > 0 {
			rows = append(rows, "", auxMutedStyle.Render("Queue signal"))
			rows = append(rows, "  "+auxMutedStyle.Render(clip(queueSignal(activeIssues, queuedWork), width-2)))
		}
	}
	rows = append(rows, "", auxMutedStyle.Render("manual = live shell without issue/log ledger"))
	return lipgloss.JoinVertical(lipgloss.Left, rows...)
}

func loadActivityCmd(root string) tea.Cmd {
	return func() tea.Msg {
		entries, err := structuredActivity(root, 80)
		if err == nil {
			return activityLoadedMsg{entries: entries}
		}
		return activityLoadedMsg{entries: recentActivity(filepath.Join(root, "logs"), 7)}
	}
}

func structuredActivity(root string, limit int) ([]activityEntry, error) {
	code := `
import json
import sys
from pathlib import Path
sys.path.insert(0, "scripts")
from industrial_activity import build_activity_events, load_agent_work_payload
from jobs_server import load_jobs
from network_web_server import cluster_snapshot
root = Path(".")
cluster = None
jobs = None
try:
    cluster = cluster_snapshot()
except Exception:
    pass
try:
    jobs = load_jobs()
except Exception:
    pass
rows = build_activity_events(
    log_root=root / "logs",
    cluster_payload=cluster,
    jobs_payload=jobs,
    agent_payload=load_agent_work_payload(root),
    limit=int(sys.argv[1]),
)
print(json.dumps(rows))
`
	cmd := exec.Command("python3", "-c", code, fmt.Sprint(limit))
	cmd.Dir = root
	cmd.Env = append(os.Environ(), "CENTO_ROOT_DIR="+root)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return nil, fmt.Errorf("%v: %s", err, strings.TrimSpace(string(out)))
	}
	var entries []activityEntry
	if err := json.Unmarshal(out, &entries); err != nil {
		return nil, err
	}
	for index := range entries {
		entries[index].Hot = isHotActivity(entries[index])
		if entries[index].Badge == "" {
			entries[index].Badge = entries[index].Severity
		}
	}
	return entries, nil
}

func loadAgentBoardCmd(root string) tea.Cmd {
	return func() tea.Msg {
		runsCmd := exec.Command("python3", filepath.Join(root, "scripts", "agent_work.py"), "runs", "--json", "--active")
		runsCmd.Dir = root
		runsCmd.Env = append(os.Environ(), "CENTO_ROOT_DIR="+root)
		runsOut, err := runsCmd.CombinedOutput()
		if err != nil {
			return agentBoardLoadedMsg{err: fmt.Errorf("%v: %s", err, strings.TrimSpace(string(runsOut)))}
		}
		var runsPayload agentRunsPayload
		if err := json.Unmarshal(runsOut, &runsPayload); err != nil {
			return agentBoardLoadedMsg{err: err}
		}
		listCmd := exec.Command("python3", filepath.Join(root, "scripts", "agent_work.py"), "list", "--json")
		listCmd.Dir = root
		listCmd.Env = append(os.Environ(), "CENTO_ROOT_DIR="+root)
		listOut, err := listCmd.CombinedOutput()
		if err != nil {
			return agentBoardLoadedMsg{runs: runsPayload.Runs, err: fmt.Errorf("%v: %s", err, strings.TrimSpace(string(listOut)))}
		}
		var issuesPayload agentIssuesPayload
		if err := json.Unmarshal(listOut, &issuesPayload); err != nil {
			return agentBoardLoadedMsg{runs: runsPayload.Runs, err: err}
		}
		managerSummary := agentManagerSummary{}
		managerCmd := exec.Command("python3", filepath.Join(root, "scripts", "agent_manager.py"), "scan", "--json")
		managerCmd.Dir = root
		managerCmd.Env = append(os.Environ(), "CENTO_ROOT_DIR="+root)
		if managerOut, err := managerCmd.CombinedOutput(); err == nil {
			var managerPayload agentManagerPayload
			if json.Unmarshal(managerOut, &managerPayload) == nil {
				managerSummary = managerPayload.Summary
			}
		}
		return agentBoardLoadedMsg{runs: runsPayload.Runs, issues: issuesPayload.Issues, manager: managerSummary}
	}
}

func activityLine(entry activityEntry, width int) string {
	dot := auxQuietDot
	if isHotActivity(entry) {
		dot = auxHotDot
	}
	severity := entry.Severity
	if severity == "" {
		severity = "info"
	}
	source := entry.Source
	if source == "" {
		source = entry.Badge
	}
	badge := badgeStyle(activityBadge(severity)).Render(activityBadge(severity))
	age := clip(entry.Age, 5)
	top := strings.Join([]string{
		"  " + dot,
		"  ",
		cell(auxMutedStyle.Render(age), 5, false),
		" ",
		cell(auxMutedStyle.Render(clip(source, 14)), 14, false),
		" ",
		badge,
	}, "")
	detail := "     " + auxTextStyle.Render(clip(entry.Label, max(8, width-5)))
	return lipgloss.JoinVertical(lipgloss.Left, top, detail)
}

func filteredActivity(entries []activityEntry, filter string) []activityEntry {
	if filter == "" {
		return entries
	}
	filtered := make([]activityEntry, 0, len(entries))
	for _, entry := range entries {
		switch filter {
		case "hot":
			if isHotActivity(entry) {
				filtered = append(filtered, entry)
			}
		case "log":
			if entry.Badge == "log" {
				filtered = append(filtered, entry)
			}
		default:
			if entry.Source == filter {
				filtered = append(filtered, entry)
			}
		}
	}
	return filtered
}

func isHotActivity(entry activityEntry) bool {
	if entry.Hot {
		return true
	}
	severity := strings.ToLower(entry.Severity)
	return severity == "critical" || severity == "warning"
}

func activityBadge(severity string) string {
	switch strings.ToLower(severity) {
	case "critical":
		return "CRIT"
	case "warning":
		return "WARN"
	case "ok":
		return "OK"
	default:
		return "INFO"
	}
}

func agentLine(run agentRun, width int) string {
	status := run.Status
	if status == "" {
		status = "unknown"
	}
	runtime := run.Runtime
	if runtime == "" {
		runtime = "agent"
	}
	issue := issueLabel(run.IssueID)
	health := run.Health
	if health == "" {
		health = status
	}
	icon := statusIcon(status)
	target := "manual"
	if issue != "" {
		target = "#" + issue
	}
	role := strings.TrimSpace(run.Role)
	if role == "" {
		role = "agent"
	} else if role == "interactive" && issue == "" {
		role = "shell"
	}
	row := fmt.Sprintf(
		"(%s -> %s -> %s -> %s -> %s)",
		strings.ToLower(runtimeName(runtime)),
		target,
		role,
		processStatusLabel(status, health),
		compactElapsed(run.Elapsed),
	)
	prefix := "  " + icon + " "
	return prefix + auxTextStyle.Bold(true).Render(clip(row, max(8, width-lipgloss.Width(prefix))))
}

func workLine(issue agentIssue, width int) string {
	status := issue.Status
	badge := badgeStyle(workBadge(status)).Render(workBadge(status))
	icon := statusIcon(status)
	titleWidth := max(10, width-18)
	title := fmt.Sprintf("#%d %s", issue.ID, compactSubject(issue.Subject))
	owner := issue.Agent
	if owner == "" {
		owner = issue.Role
	}
	if owner == "" {
		owner = "unassigned"
	}
	detail := fmt.Sprintf("%s@%s", owner, issue.Node)
	if issue.Package != "" {
		detail += " · " + issue.Package
	}
	line1 := "  " + icon + " " + cell(auxTextStyle.Bold(true).Render(clip(title, titleWidth)), titleWidth, false) + " " + badge
	line2 := "    " + auxMutedStyle.Render(clip(detail, max(8, width-4)))
	return lipgloss.JoinVertical(lipgloss.Left, line1, line2)
}

func prioritizedWork(issues []agentIssue, limit int) []agentIssue {
	filtered := make([]agentIssue, 0, len(issues))
	for _, issue := range issues {
		if isActiveWorkStatus(issue.Status) || strings.EqualFold(issue.Status, "Queued") {
			filtered = append(filtered, issue)
		}
	}
	sort.SliceStable(filtered, func(i, j int) bool {
		left := workRank(filtered[i].Status)
		right := workRank(filtered[j].Status)
		if left != right {
			return left < right
		}
		return filtered[i].ID > filtered[j].ID
	})
	if len(filtered) > limit {
		return filtered[:limit]
	}
	return filtered
}

func agentProcessRuns(runs []agentRun, limit int) []agentRun {
	filtered := make([]agentRun, 0, len(runs))
	for _, run := range runs {
		if isLiveAgentProcessStatus(run.Status) {
			filtered = append(filtered, run)
		}
	}
	sort.SliceStable(filtered, func(i, j int) bool {
		left := agentProcessRank(filtered[i].Status)
		right := agentProcessRank(filtered[j].Status)
		if left != right {
			return left < right
		}
		return runtimeName(filtered[i].Runtime) < runtimeName(filtered[j].Runtime)
	})
	if len(filtered) > limit {
		return filtered[:limit]
	}
	return filtered
}

func nonEpicWork(issues []agentIssue) []agentIssue {
	filtered := make([]agentIssue, 0, len(issues))
	for _, issue := range issues {
		if strings.EqualFold(issue.Tracker, "Agent Epic") {
			continue
		}
		filtered = append(filtered, issue)
	}
	return filtered
}

func manualRuns(runs []agentRun, limit int) []agentRun {
	filtered := make([]agentRun, 0, len(runs))
	for _, run := range runs {
		if run.Status == "untracked_interactive" {
			filtered = append(filtered, run)
		}
	}
	if len(filtered) > limit {
		return filtered[:limit]
	}
	return filtered
}

func isLiveAgentProcessStatus(status string) bool {
	switch strings.ToLower(status) {
	case "running", "launching", "planned", "untracked_interactive":
		return true
	default:
		return false
	}
}

func agentProcessRank(status string) int {
	switch strings.ToLower(status) {
	case "running", "launching":
		return 0
	case "untracked_interactive":
		return 1
	case "planned":
		return 2
	case "stale":
		return 3
	default:
		return 9
	}
}

func isActiveIssueSignal(status string) bool {
	switch strings.ToLower(status) {
	case "running", "validating", "blocked":
		return true
	default:
		return false
	}
}

func queueSignal(active, queued int) string {
	parts := []string{}
	if active > 0 {
		parts = append(parts, fmt.Sprintf("%d active %s", active, plural(active, "issue", "issues")))
	}
	if queued > 0 {
		parts = append(parts, fmt.Sprintf("%d queued", queued))
	}
	if len(parts) == 0 {
		return "no active issue queue"
	}
	return strings.Join(parts, " · ")
}

func plural(count int, singular, pluralValue string) string {
	if count == 1 {
		return singular
	}
	return pluralValue
}

func isActiveWorkStatus(status string) bool {
	switch strings.ToLower(status) {
	case "running", "validating", "review", "blocked":
		return true
	default:
		return false
	}
}

func workRank(status string) int {
	switch strings.ToLower(status) {
	case "blocked":
		return 0
	case "running":
		return 1
	case "validating":
		return 2
	case "review":
		return 3
	case "queued":
		return 4
	default:
		return 9
	}
}

func workBadge(status string) string {
	switch strings.ToLower(status) {
	case "blocked":
		return "WARN"
	case "running":
		return "RUN"
	case "validating":
		return "CHECK"
	case "review":
		return "REVIEW"
	case "queued":
		return "TODO"
	default:
		return "LOG"
	}
}

func compactSubject(subject string) string {
	subject = strings.TrimSpace(subject)
	replacer := strings.NewReplacer(
		"Industrial OS ", "",
		"iPhone Cento App: ", "iPhone: ",
		"Improve Dev Process: ", "Dev: ",
		" Panel: ", ": ",
	)
	return replacer.Replace(subject)
}

func agentBadge(status, health string) string {
	lower := strings.ToLower(status + " " + health)
	switch {
	case strings.Contains(lower, "untracked"):
		return "MANUAL"
	case strings.Contains(lower, "stale") || strings.Contains(lower, "failed") || strings.Contains(lower, "blocked"):
		return "WARN"
	case strings.Contains(lower, "running") || strings.Contains(lower, "launch"):
		return "LIVE"
	case strings.Contains(lower, "planned"):
		return "START"
	default:
		return "LOG"
	}
}

func processStatusLabel(status, health string) string {
	lower := strings.ToLower(status + " " + health)
	switch {
	case strings.Contains(lower, "untracked"):
		return "running"
	case strings.Contains(lower, "launch") || strings.Contains(lower, "planned"):
		return "starting"
	case strings.Contains(lower, "stale"):
		return "stale"
	case strings.Contains(lower, "failed"):
		return "failed"
	case strings.Contains(lower, "blocked"):
		return "blocked"
	case strings.Contains(lower, "running"):
		return "running"
	default:
		if status == "" {
			return "unknown"
		}
		return strings.ToLower(status)
	}
}

func statusIcon(status string) string {
	switch strings.ToLower(status) {
	case "running", "launching", "planned":
		return lipgloss.NewStyle().Foreground(auxGreen).Bold(true).Render("▶")
	case "untracked_interactive":
		return lipgloss.NewStyle().Foreground(auxGreen).Bold(true).Render("●")
	case "review":
		return auxAmberStyle().Render("◆")
	case "validating":
		return lipgloss.NewStyle().Foreground(auxPurple).Bold(true).Render("◆")
	case "blocked", "failed", "stale":
		return lipgloss.NewStyle().Foreground(auxAmber).Bold(true).Render("!")
	case "queued":
		return auxMutedStyle.Render("□")
	default:
		return auxQuietDot
	}
}

func runtimeLabel(runtime string) string {
	return runtimeName(runtime)
}

func runtimeName(runtime string) string {
	switch runtime {
	case "claude-code":
		return "Claude"
	case "codex":
		return "Codex"
	default:
		if runtime == "" {
			return "agent"
		}
		return runtime
	}
}

func runtimeBadge(runtime string) string {
	style := lipgloss.NewStyle().Bold(true).Padding(0, 1)
	switch runtime {
	case "claude-code":
		return style.Foreground(lipgloss.Color("#050403")).Background(lipgloss.Color("#DCCFC4")).Render("CL")
	case "codex":
		return style.Foreground(lipgloss.Color("#050403")).Background(auxGreen).Render("CX")
	default:
		return style.Foreground(auxText).Background(lipgloss.Color("#303030")).Render("AG")
	}
}

func runtimeLegend() string {
	return auxMutedStyle.Render("runtimes ") + runtimeBadge("codex") + auxMutedStyle.Render(" Codex  ") + runtimeBadge("claude-code") + auxMutedStyle.Render(" Claude")
}

func agentManagerLine(summary agentManagerSummary, width int) string {
	actionableStale := summary.ActionableStale
	if actionableStale == 0 && summary.Stale > 0 && summary.HistoricalStale == 0 {
		actionableStale = summary.Stale
	}
	if summary.Live == 0 && summary.RiskCount == 0 && actionableStale == 0 && summary.HistoricalStale == 0 {
		return ""
	}
	label := "OK"
	if summary.Critical > 0 {
		label = "CRIT"
	} else if summary.Warning > 0 || summary.RiskCount > 0 {
		label = "WARN"
	}
	text := fmt.Sprintf(
		"mgr %d risk · %d stale · %d hist · %d manual",
		summary.RiskCount,
		actionableStale,
		summary.HistoricalStale,
		summary.Manual,
	)
	return badgeStyle(label).Render(label) + " " + auxMutedStyle.Render(clip(text, max(8, width-8)))
}

func agentOwner(run agentRun) string {
	agent := strings.TrimSpace(run.Agent)
	node := strings.TrimSpace(run.Node)
	if agent != "" && node != "" {
		return agent + "@" + node
	}
	if agent != "" {
		return agent
	}
	if node != "" {
		return node
	}
	return ""
}

func compactCommand(command string) string {
	fields := strings.Fields(command)
	if len(fields) == 0 {
		return ""
	}
	for index, field := range fields {
		base := filepath.Base(field)
		if base == "codex" || base == "claude" {
			end := min(len(fields), index+2)
			parts := []string{base}
			for _, part := range fields[index+1 : end] {
				parts = append(parts, filepath.Base(part))
			}
			return strings.Join(parts, " ")
		}
	}
	return filepath.Base(fields[0])
}

func issueLabel(value interface{}) string {
	switch typed := value.(type) {
	case nil:
		return ""
	case float64:
		if typed == 0 {
			return ""
		}
		return fmt.Sprintf("%.0f", typed)
	case string:
		return strings.TrimSpace(typed)
	default:
		return fmt.Sprintf("%v", typed)
	}
}

func compactElapsed(elapsed string) string {
	elapsed = strings.TrimSpace(elapsed)
	if elapsed == "" {
		return "0:00"
	}
	parts := strings.Split(elapsed, ":")
	if len(parts) != 3 {
		return elapsed
	}
	hours, errH := strconv.Atoi(parts[0])
	minutes, errM := strconv.Atoi(parts[1])
	seconds, errS := strconv.Atoi(parts[2])
	if errH != nil || errM != nil || errS != nil {
		return elapsed
	}
	if hours > 0 {
		return fmt.Sprintf("%dh%02dm", hours, minutes)
	}
	return fmt.Sprintf("%d:%02d", minutes, seconds)
}

func tickCmd(interval time.Duration) tea.Cmd {
	return tea.Tick(interval, func(t time.Time) tea.Msg {
		return tickMsg(t)
	})
}

func runActionCmd(root string, action quickAction, dryRun bool) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
		defer cancel()
		command := action.Command
		if dryRun {
			command = action.DryRunCommand
			if len(command) == 0 {
				command = action.Command
			}
		}
		commandText := actionText(command)
		cmd := exec.CommandContext(ctx, "bash", "-lc", commandText)
		cmd.Dir = root
		cmd.Env = append(os.Environ(), "CENTO_ROOT_DIR="+root)
		out, err := cmd.CombinedOutput()
		if ctx.Err() != nil {
			err = ctx.Err()
		}
		return actionDoneMsg{action: action, output: strings.TrimSpace(string(out)), err: err, dryRun: dryRun}
	}
}

func recentActivity(logRoot string, limit int) []activityEntry {
	type candidate struct {
		mod   time.Time
		entry activityEntry
	}
	var candidates []candidate
	dirs, err := os.ReadDir(logRoot)
	if err != nil {
		return nil
	}
	for _, dirEntry := range dirs {
		if !dirEntry.IsDir() {
			continue
		}
		source := dirEntry.Name()
		files, _ := filepath.Glob(filepath.Join(logRoot, source, "*.log"))
		for _, file := range files {
			info, err := os.Stat(file)
			if err != nil {
				continue
			}
			label := cleanEventLabel(source, lastMeaningfulLine(file))
			candidates = append(candidates, candidate{
				mod: info.ModTime(),
				entry: activityEntry{
					Stamp: info.ModTime().Format("15:04:05"),
					Label: label,
					Badge: eventBadge(source, label),
					Hot:   isHotSource(source),
				},
			})
		}
	}
	sort.Slice(candidates, func(i, j int) bool {
		return candidates[i].mod.After(candidates[j].mod)
	})
	seen := map[string]bool{}
	entries := make([]activityEntry, 0, limit)
	for _, candidate := range candidates {
		if seen[candidate.entry.Label] {
			continue
		}
		seen[candidate.entry.Label] = true
		entries = append(entries, candidate.entry)
		if len(entries) >= limit {
			break
		}
	}
	return entries
}

func lastMeaningfulLine(path string) string {
	raw, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	lines := strings.Split(string(raw), "\n")
	for i := len(lines) - 1; i >= 0; i-- {
		line := strings.TrimSpace(lines[i])
		if line != "" && !strings.Contains(line, "Log file:") && !strings.Contains(line, "Log saved to:") {
			return line
		}
	}
	return ""
}

func cleanEventLabel(source, line string) string {
	plain := strings.ReplaceAll(stripANSI(line), "_", "-")
	switch {
	case strings.Contains(plain, "GET /api/jobs "):
		return "jobs-dashboard completed"
	case strings.Contains(plain, "GET /api/network "):
		return "cluster health check ok"
	case strings.Contains(plain, "GET /api/state "):
		return "system state refreshed"
	case strings.Contains(plain, "Industrial workspace") && strings.Contains(plain, "composed"):
		return "workspace composed"
	case strings.Contains(plain, "pr-plan") || strings.Contains(plain, "PR #"):
		return plain
	case strings.Contains(plain, "Completed successfully"):
		return source + " completed"
	case plain == "":
		return source
	}
	if index := strings.Index(plain, "] "); index >= 0 {
		plain = plain[index+2:]
	}
	return plain
}

func eventBadge(source, label string) string {
	lower := strings.ToLower(source + " " + label)
	switch {
	case strings.Contains(lower, "replay"):
		return "REPLAY"
	case strings.Contains(lower, "cluster") || strings.Contains(lower, "system"):
		return "SYSTEM"
	case strings.Contains(lower, "job"):
		return "JOB"
	case strings.Contains(lower, "git") || strings.Contains(lower, "pr-"):
		return "GIT"
	case strings.Contains(lower, "lead"):
		return "LEAD"
	default:
		return "LOG"
	}
}

func isHotSource(source string) bool {
	switch source {
	case "cluster-jobs", "dashboard", "industrial-os", "industrial-workspace":
		return true
	default:
		return false
	}
}

func badgeStyle(label string) lipgloss.Style {
	style := lipgloss.NewStyle().Bold(true).Padding(0, 1)
	switch label {
	case "CRIT":
		return style.Foreground(auxOrange).Background(lipgloss.Color("#3A160D"))
	case "LIVE":
		return style.Foreground(auxGreen).Background(lipgloss.Color("#142318"))
	case "START":
		return style.Foreground(auxAmber).Background(lipgloss.Color("#33230D"))
	case "RUN":
		return style.Foreground(auxGreen).Background(lipgloss.Color("#142318"))
	case "WARN":
		return style.Foreground(auxAmber).Background(lipgloss.Color("#33230D"))
	case "INFO":
		return style.Foreground(auxMuted).Background(lipgloss.Color("#17191B"))
	case "OK":
		return style.Foreground(auxGreen).Background(lipgloss.Color("#142318"))
	case "MANUAL":
		return style.Foreground(auxPurple).Background(lipgloss.Color("#25193C"))
	case "REVIEW":
		return style.Foreground(auxAmber).Background(lipgloss.Color("#33230D"))
	case "CHECK":
		return style.Foreground(auxPurple).Background(lipgloss.Color("#25193C"))
	case "TODO":
		return style.Foreground(auxMuted).Background(lipgloss.Color("#17191B"))
	case "JOB":
		return style.Foreground(auxGreen).Background(lipgloss.Color("#142318"))
	case "GIT":
		return style.Foreground(auxOrange).Background(lipgloss.Color("#3A160D"))
	case "LEAD":
		return style.Foreground(auxPurple).Background(lipgloss.Color("#25193C"))
	case "SYSTEM":
		return style.Foreground(auxAmber).Background(lipgloss.Color("#33230D"))
	case "REPLAY":
		return style.Foreground(auxAmber).Background(lipgloss.Color("#2B1C12"))
	default:
		return style.Foreground(auxMuted).Background(lipgloss.Color("#17191B"))
	}
}

func auxAmberStyle() lipgloss.Style {
	return lipgloss.NewStyle().Foreground(auxAmber).Bold(true)
}

func stripANSI(value string) string {
	return auxANSIPat.ReplaceAllString(value, "")
}

func clip(value string, width int) string {
	plain := stripANSI(value)
	if lipgloss.Width(plain) <= width {
		return plain
	}
	runes := []rune(plain)
	if width <= 1 || len(runes) <= width {
		return plain
	}
	return string(runes[:width-1]) + "…"
}

func cell(value string, width int, right bool) string {
	current := lipgloss.Width(value)
	if current >= width {
		return value
	}
	padding := strings.Repeat(" ", width-current)
	if right {
		return padding + value
	}
	return value + padding
}

func clamp(value, low, high int) int {
	if value < low {
		return low
	}
	if value > high {
		return high
	}
	return value
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func isTTY() bool {
	info, err := os.Stdout.Stat()
	return err == nil && (info.Mode()&os.ModeCharDevice) != 0
}

func main() {
	root := initRoot()
	fs := flag.NewFlagSet("industrial-aux-tui", flag.ExitOnError)
	defaultMode := "activity"
	args := os.Args[1:]
	if len(args) > 0 && !strings.HasPrefix(args[0], "-") {
		defaultMode = args[0]
		args = args[1:]
	}
	mode := fs.String("mode", defaultMode, "panel mode: activity, agents, or actions")
	once := fs.Bool("once", false, "render once and exit")
	filter := fs.String("filter", "", "activity filter: hot, cluster, jobs, agent-work, or log")
	interval := fs.Duration("interval", 5*time.Second, "refresh interval")
	fs.Parse(args)
	if fs.NArg() > 0 {
		*mode = fs.Arg(0)
	}
	if *mode != "activity" && *mode != "agents" && *mode != "actions" {
		fmt.Fprintln(os.Stderr, "mode must be activity, agents, or actions")
		os.Exit(2)
	}

	model := newModel(root, *mode, *interval)
	model.filter = *filter
	if *mode == "activity" {
		if entries, err := structuredActivity(root, 80); err == nil {
			model.entries = entries
		} else {
			model.entries = recentActivity(filepath.Join(root, "logs"), 7)
		}
	} else if *mode == "agents" {
		msg := loadAgentBoardCmd(root)()
		if loaded, ok := msg.(agentBoardLoadedMsg); ok {
			model.agents = loaded.runs
			model.work = loaded.issues
			model.manager = loaded.manager
			if loaded.err != nil {
				model.agentErr = loaded.err.Error()
			}
		}
	}
	if *once || !isTTY() {
		view := model
		view.width = 46
		if *mode == "agents" {
			view.width = 58
		}
		if *mode == "actions" {
			fmt.Println(view.renderActions(42))
		} else if *mode == "agents" {
			fmt.Println(view.renderAgents(54))
		} else {
			fmt.Println(view.renderActivity(42))
		}
		return
	}

	program := tea.NewProgram(model)
	if _, err := program.Run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
