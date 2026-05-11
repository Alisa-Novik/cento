package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"time"

	tea "charm.land/bubbletea/v2"
	"charm.land/lipgloss/v2"
)

// ── data types ──────────────────────────────────────────────────────────────

type runsResponse struct {
	Runs []runRecord `json:"runs"`
}

type runRecord struct {
	RunID        string `json:"run_id"`
	IssueID      int    `json:"issue_id"`
	IssueSubject string `json:"issue_subject"`
	Status       string `json:"status"`
	Health       string `json:"health"`
	Role         string `json:"role"`
	Agent        string `json:"agent"`
	Runtime      string `json:"runtime"`
	Node         string `json:"node"`
	Elapsed      string `json:"elapsed"`
	UpdatedAt    string `json:"updated_at"`
	PIDAlive     bool   `json:"pid_alive"`
	TmuxAlive    bool   `json:"tmux_alive"`
	Package      string `json:"package"`
	Command      string `json:"command"`
	CWD          string `json:"cwd"`
}

type issuesResponse struct {
	Issues []issueRecord `json:"issues"`
}

type issueRecord struct {
	ID      int    `json:"id"`
	Subject string `json:"subject"`
	Status  string `json:"status"`
	Node    string `json:"node"`
	Agent   string `json:"agent"`
	Role    string `json:"role"`
	Package string `json:"package"`
}

type managerScan struct {
	Summary managerSummary `json:"summary"`
}

type managerSummary struct {
	Live            int            `json:"live"`
	ManagedLive     int            `json:"managed_live"`
	Manual          int            `json:"manual"`
	Stale           int            `json:"stale"`
	ActionableStale int            `json:"actionable_stale"`
	RiskCount       int            `json:"risk_count"`
	Warning         int            `json:"warning"`
	ByRole          map[string]int `json:"by_role"`
	ByRuntime       map[string]int `json:"by_runtime"`
}

type processRow struct {
	RunID   string
	IssueID int
	Subject string
	Status  string
	Health  string
	Role    string
	Runtime string
	Node    string
	Elapsed string
	Alive   bool
	Package string
	Command string
	CWD     string
}

type queueRow struct {
	IssueID int
	Subject string
	Status  string
	Node    string
	Agent   string
	Role    string
}

type processData struct {
	Runs      []processRow
	Queue     []queueRow
	Counts    map[string]int
	Scan      *managerSummary
	UpdatedAt time.Time
	Err       error
}

// ── tea messages ─────────────────────────────────────────────────────────────

type dataLoadedMsg struct{ data processData }
type tickMsg time.Time

// ── model ────────────────────────────────────────────────────────────────────

type model struct {
	root     string
	width    int
	height   int
	interval time.Duration
	loading  bool
	selected int
	data     processData
}

// ── styles ───────────────────────────────────────────────────────────────────

var (
	orange     = lipgloss.Color("#FF4B00")
	amber      = lipgloss.Color("#FF9A3D")
	green      = lipgloss.Color("#62E886")
	red        = lipgloss.Color("#FF5E4A")
	blue       = lipgloss.Color("#8DB9C7")
	purple     = lipgloss.Color("#B68CFF")
	text       = lipgloss.Color("#D8D0C4")
	muted      = lipgloss.Color("#8B746F")
	panelStyle = lipgloss.NewStyle().Foreground(text).Padding(1, 1)
	titleStyle = lipgloss.NewStyle().Foreground(orange).Bold(true)
	mutedStyle = lipgloss.NewStyle().Foreground(muted)
	ruleStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color("#8A4A45"))
	hdrStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("#FFF4DC"))
	idStyle    = lipgloss.NewStyle().Foreground(orange)
	nameStyle  = lipgloss.NewStyle().Foreground(text)
)

// ── tea interface ─────────────────────────────────────────────────────────────

func (m model) Init() tea.Cmd {
	return tea.Batch(loadDataCmd(m.root), tickCmd(m.interval))
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
	case tea.KeyPressMsg:
		switch msg.String() {
		case "ctrl+c", "q":
			return m, tea.Quit
		case "r":
			m.loading = true
			return m, loadDataCmd(m.root)
		case "j", "down":
			if m.selected < len(m.data.Runs)-1 {
				m.selected++
			}
		case "k", "up":
			if m.selected > 0 {
				m.selected--
			}
		}
	case tickMsg:
		if m.loading {
			return m, tickCmd(m.interval)
		}
		m.loading = true
		return m, tea.Batch(loadDataCmd(m.root), tickCmd(m.interval))
	case dataLoadedMsg:
		m.loading = false
		m.data = msg.data
		if m.selected >= len(m.data.Runs) {
			m.selected = max(0, len(m.data.Runs)-1)
		}
	}
	return m, nil
}

func (m model) View() tea.View {
	w := m.width
	if w <= 0 {
		w = 100
	}
	w = clamp(w-2, 50, 160)
	body := m.renderBody(w - 2)
	view := tea.NewView(panelStyle.Width(w).Render(body))
	view.AltScreen = true
	return view
}

// ── render ───────────────────────────────────────────────────────────────────

func (m model) renderBody(width int) string {
	rule := ruleStyle.Render(strings.Repeat("─", max(8, width)))
	parts := []string{
		mutedStyle.Render(time.Now().Format("15:04:05") + "  agent-processes"),
		titleStyle.Render("> AGENT PROCESSES DASHBOARD"),
		rule,
		m.renderSummary(width),
		"",
	}
	if m.data.Err != nil {
		parts = append(parts, nameStyle.Foreground(red).Render(m.data.Err.Error()))
	} else {
		if len(m.data.Runs) == 0 {
			parts = append(parts, mutedStyle.Render("No active agent runs."))
		} else {
			parts = append(parts, hdrStyle.Render("ACTIVE RUNS"))
			parts = append(parts, m.renderRuns(width))
		}
		if len(m.data.Queue) > 0 {
			parts = append(parts, "", rule, hdrStyle.Render("QUEUE"))
			parts = append(parts, m.renderQueue(width))
		}
		if m.data.Scan != nil {
			parts = append(parts, "", rule)
			parts = append(parts, m.renderScan(width))
		}
	}
	hint := "r refresh · q quit · auto " + m.interval.String()
	if m.loading {
		hint = "refreshing…  " + hint
	}
	parts = append(parts, "", mutedStyle.Render(hint))
	return lipgloss.JoinVertical(lipgloss.Left, parts...)
}

func (m model) renderSummary(width int) string {
	d := m.data
	live := len(d.Runs)
	queued := 0
	running := 0
	for _, q := range d.Queue {
		switch strings.ToLower(q.Status) {
		case "queued":
			queued++
		case "running":
			running++
		}
	}
	items := []string{
		hdrStyle.Render("LIVE"), nameStyle.Render(fmt.Sprintf("%d", live)),
		hdrStyle.Render("RUNNING"), nameStyle.Render(fmt.Sprintf("%d", running)),
		hdrStyle.Render("QUEUED"), nameStyle.Render(fmt.Sprintf("%d", queued)),
	}
	if d.Scan != nil {
		items = append(items,
			hdrStyle.Render("STALE"), nameStyle.Render(fmt.Sprintf("%d", d.Scan.Stale)),
			hdrStyle.Render("RISK"), nameStyle.Render(fmt.Sprintf("%d", d.Scan.RiskCount)),
		)
	}
	line := strings.Join(items, "   ")
	return clipLine(line, width)
}

func (m model) renderRuns(width int) string {
	roleW := 10
	rtW := 12
	nodeW := 6
	elW := 7
	healthW := 7
	gutters := 10
	doingW := max(10, width-roleW-rtW-nodeW-elW-healthW-gutters)
	maxShow := len(m.data.Runs)
	if m.height > 0 {
		maxShow = min(maxShow, max(3, m.height/3))
	} else {
		maxShow = min(maxShow, 8)
	}
	lines := make([]string, 0, maxShow+1)
	lines = append(lines, strings.Join([]string{
		cell(mutedStyle.Render("HEALTH"), healthW, false),
		cell(mutedStyle.Render("ROLE"), roleW, false),
		cell(mutedStyle.Render("RUNTIME"), rtW, false),
		cell(mutedStyle.Render("NODE"), nodeW, false),
		cell(mutedStyle.Render("ELAPSED"), elW, true),
		mutedStyle.Render("DOING"),
	}, "  "))
	for i, row := range m.data.Runs[:maxShow] {
		health := row.Health
		if health == "" {
			health = row.Status
		}
		healthText := statusStyle(health).Render(clip(strings.ToUpper(health), healthW))
		prefix := " "
		if i == m.selected {
			prefix = ">"
		}
		doing := prefix + clip(processDoing(row), doingW-1)
		lines = append(lines, strings.Join([]string{
			cell(healthText, healthW, false),
			cell(nameStyle.Render(clip(row.Role, roleW)), roleW, false),
			cell(mutedStyle.Render(clip(row.Runtime, rtW)), rtW, false),
			cell(mutedStyle.Render(clip(row.Node, nodeW)), nodeW, false),
			cell(mutedStyle.Render(clip(row.Elapsed, elW)), elW, true),
			idStyle.Render(doing),
		}, "  "))
	}
	return lipgloss.JoinVertical(lipgloss.Left, lines...)
}

func (m model) renderQueue(width int) string {
	statusW := 10
	roleW := 10
	nodeW := 6
	gutters := 6
	subjW := max(10, width-statusW-roleW-nodeW-gutters)
	maxShow := min(len(m.data.Queue), 6)
	lines := make([]string, 0, maxShow+1)
	lines = append(lines, strings.Join([]string{
		cell(mutedStyle.Render("STATUS"), statusW, false),
		cell(mutedStyle.Render("ROLE"), roleW, false),
		cell(mutedStyle.Render("NODE"), nodeW, false),
		mutedStyle.Render("SUBJECT"),
	}, "  "))
	for _, row := range m.data.Queue[:maxShow] {
		statusText := statusStyle(strings.ToLower(row.Status)).Render(clip(row.Status, statusW))
		lines = append(lines, strings.Join([]string{
			cell(statusText, statusW, false),
			cell(nameStyle.Render(clip(row.Role, roleW)), roleW, false),
			cell(mutedStyle.Render(clip(row.Node, nodeW)), nodeW, false),
			nameStyle.Render(clip(issueLabel(row.IssueID, row.Subject), subjW)),
		}, "  "))
	}
	if len(m.data.Queue) > maxShow {
		lines = append(lines, mutedStyle.Render(fmt.Sprintf("  … and %d more", len(m.data.Queue)-maxShow)))
	}
	return lipgloss.JoinVertical(lipgloss.Left, lines...)
}

func (m model) renderScan(width int) string {
	s := m.data.Scan
	parts := []string{hdrStyle.Render("MANAGER SCAN")}
	roleItems := []string{}
	for role, count := range s.ByRole {
		roleItems = append(roleItems, fmt.Sprintf("%s:%d", role, count))
	}
	sort.Strings(roleItems)
	rtItems := []string{}
	for rt, count := range s.ByRuntime {
		rtItems = append(rtItems, fmt.Sprintf("%s:%d", rt, count))
	}
	sort.Strings(rtItems)
	parts = append(parts,
		nameStyle.Render(fmt.Sprintf("live %d  managed %d  manual %d  stale %d  actionable-stale %d  risk %d  warn %d",
			s.Live, s.ManagedLive, s.Manual, s.Stale, s.ActionableStale, s.RiskCount, s.Warning)),
	)
	if len(roleItems) > 0 {
		parts = append(parts, mutedStyle.Render("by-role: "+strings.Join(roleItems, "  ")))
	}
	if len(rtItems) > 0 {
		parts = append(parts, mutedStyle.Render("by-runtime: "+strings.Join(rtItems, "  ")))
	}
	_ = width
	return lipgloss.JoinVertical(lipgloss.Left, parts...)
}

// ── data loading ─────────────────────────────────────────────────────────────

func loadDataCmd(root string) tea.Cmd {
	return func() tea.Msg {
		return dataLoadedMsg{data: loadData(root)}
	}
}

func tickCmd(interval time.Duration) tea.Cmd {
	return tea.Tick(interval, func(t time.Time) tea.Msg {
		return tickMsg(t)
	})
}

func loadData(root string) processData {
	runs, err := loadRuns(root)
	if err != nil {
		return processData{Err: err, UpdatedAt: time.Now(), Counts: map[string]int{}}
	}
	queue, _ := loadQueue(root)
	runs = enrichProcessRows(runs, queue)
	scan, _ := loadManagerScan(root)
	counts := map[string]int{}
	for _, r := range runs {
		counts[strings.ToLower(r.Health)]++
	}
	return processData{
		Runs:      runs,
		Queue:     queue,
		Counts:    counts,
		Scan:      scan,
		UpdatedAt: time.Now(),
	}
}

func runPython(root string, args ...string) ([]byte, error) {
	cmd := exec.Command("python3", args...)
	cmd.Dir = root
	return cmd.Output()
}

func loadRuns(root string) ([]processRow, error) {
	raw, err := runPython(root, "scripts/agent_work.py", "runs", "--json", "--active")
	if err != nil {
		return nil, fmt.Errorf("agent_work.py runs: %w", err)
	}
	var resp runsResponse
	if err := json.Unmarshal(raw, &resp); err != nil {
		return nil, fmt.Errorf("parse runs: %w", err)
	}
	rows := make([]processRow, 0, len(resp.Runs))
	for _, r := range resp.Runs {
		rows = append(rows, processRow{
			RunID:   r.RunID,
			IssueID: r.IssueID,
			Subject: r.IssueSubject,
			Status:  r.Status,
			Health:  r.Health,
			Role:    r.Role,
			Runtime: r.Runtime,
			Node:    r.Node,
			Elapsed: r.Elapsed,
			Alive:   r.PIDAlive || r.TmuxAlive,
			Package: r.Package,
			Command: r.Command,
			CWD:     r.CWD,
		})
	}
	return rows, nil
}

func loadQueue(root string) ([]queueRow, error) {
	raw, err := runPython(root, "scripts/agent_work.py", "list", "--json")
	if err != nil {
		return nil, err
	}
	var resp issuesResponse
	if err := json.Unmarshal(raw, &resp); err != nil {
		return nil, err
	}
	rows := make([]queueRow, 0, len(resp.Issues))
	for _, iss := range resp.Issues {
		if strings.ToLower(iss.Status) == "done" {
			continue
		}
		rows = append(rows, queueRow{
			IssueID: iss.ID,
			Subject: iss.Subject,
			Status:  iss.Status,
			Node:    iss.Node,
			Agent:   iss.Agent,
			Role:    iss.Role,
		})
	}
	return rows, nil
}

func loadManagerScan(root string) (*managerSummary, error) {
	scanScript := filepath.Join(root, "scripts", "agent_manager.py")
	if _, err := os.Stat(scanScript); err != nil {
		return nil, nil
	}
	raw, err := runPython(root, "scripts/agent_manager.py", "scan", "--json")
	if err != nil {
		return nil, nil
	}
	var scan managerScan
	if err := json.Unmarshal(raw, &scan); err != nil {
		return nil, nil
	}
	return &scan.Summary, nil
}

// ── helpers ───────────────────────────────────────────────────────────────────

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

func issueLabel(id int, subject string) string {
	if id > 0 {
		return fmt.Sprintf("#%d %s", id, subject)
	}
	return subject
}

func processDoing(row processRow) string {
	subject := strings.TrimSpace(row.Subject)
	if subject != "" {
		return issueLabel(row.IssueID, subject)
	}
	if row.Package != "" && row.IssueID > 0 {
		return fmt.Sprintf("#%d package %s", row.IssueID, row.Package)
	}
	command := compactCommand(row.Command)
	cwd := compactPath(row.CWD)
	if command != "" && cwd != "" {
		return command + " @ " + cwd
	}
	if command != "" {
		return command
	}
	if cwd != "" {
		return "shell @ " + cwd
	}
	if row.RunID != "" {
		return row.RunID
	}
	return "unknown"
}

func enrichProcessRows(runs []processRow, queue []queueRow) []processRow {
	if len(runs) == 0 || len(queue) == 0 {
		return runs
	}
	byID := make(map[int]queueRow, len(queue))
	for _, issue := range queue {
		byID[issue.IssueID] = issue
	}
	for index := range runs {
		if runs[index].IssueID == 0 || strings.TrimSpace(runs[index].Subject) != "" {
			continue
		}
		if issue, ok := byID[runs[index].IssueID]; ok {
			runs[index].Subject = issue.Subject
		}
	}
	return runs
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

func compactPath(path string) string {
	path = strings.TrimSpace(path)
	if path == "" {
		return ""
	}
	if home, err := os.UserHomeDir(); err == nil && home != "" {
		if path == home {
			return "~"
		}
		prefix := home + string(os.PathSeparator)
		if strings.HasPrefix(path, prefix) {
			return "~/" + strings.TrimPrefix(path, prefix)
		}
	}
	return path
}

func statusStyle(status string) lipgloss.Style {
	base := lipgloss.NewStyle().Bold(true)
	switch status {
	case "running", "active":
		return base.Foreground(blue)
	case "queued":
		return base.Foreground(purple)
	case "done", "succeeded", "success":
		return base.Foreground(green)
	case "failed", "error":
		return base.Foreground(red)
	case "stale", "warning":
		return base.Foreground(amber)
	default:
		return base.Foreground(text)
	}
}

func clip(value string, width int) string {
	if lipgloss.Width(value) <= width {
		return value
	}
	runes := []rune(value)
	if width <= 1 || len(runes) <= width {
		return value
	}
	return string(runes[:width-1]) + "…"
}

func clipLine(value string, width int) string {
	if lipgloss.Width(value) <= width {
		return value
	}
	return clip(value, width)
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
	fs := flag.NewFlagSet("agent-processes-tui", flag.ExitOnError)
	once := fs.Bool("once", false, "render once and exit (for CI / non-interactive)")
	interval := fs.Duration("interval", 5*time.Second, "refresh interval")
	if err := fs.Parse(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	m := model{root: root, interval: *interval, data: loadData(root), width: 100}
	if *once || !isTTY() {
		fmt.Println(m.renderBody(98))
		if m.data.Err != nil {
			os.Exit(1)
		}
		return
	}

	program := tea.NewProgram(m)
	if _, err := program.Run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
