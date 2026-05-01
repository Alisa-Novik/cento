package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	tea "charm.land/bubbletea/v2"
	"charm.land/lipgloss/v2"
)

type tickMsg time.Time

type jobsLoadedMsg struct {
	data jobsData
}

type jobRecord struct {
	ID           string           `json:"id"`
	Status       string           `json:"status"`
	Feature      string           `json:"feature"`
	CreatedAt    string           `json:"created_at"`
	UpdatedAt    string           `json:"updated_at"`
	FinishedAt   string           `json:"finished_at"`
	RunDir       string           `json:"run_dir"`
	AgentCommand string           `json:"agent_command"`
	Artifacts    map[string]any   `json:"artifacts"`
	Tasks        []map[string]any `json:"tasks"`
	Results      []map[string]any `json:"results"`
}

type taskState struct {
	ID         string
	Title      string
	Node       string
	ReturnCode string
	Log        string
}

type jobRow struct {
	ID          string
	Status      string
	Feature     string
	Tasks       int
	Results     int
	Failed      int
	Step        string
	Age         string
	State       string
	Reasons     []string
	LatestLog   string
	LogTail     []string
	RunDir      string
	Summary     string
	Command     string
	TasksDetail []taskState
	ModTime     time.Time
}

type jobsData struct {
	Rows      []jobRow
	Counts    map[string]int
	UpdatedAt time.Time
	Err       error
}

type model struct {
	root     string
	width    int
	height   int
	interval time.Duration
	loading  bool
	selected int
	data     jobsData
}

var (
	orange      = lipgloss.Color("#FF4B00")
	amber       = lipgloss.Color("#FF9A3D")
	green       = lipgloss.Color("#62E886")
	red         = lipgloss.Color("#FF5E4A")
	blue        = lipgloss.Color("#8DB9C7")
	purple      = lipgloss.Color("#B68CFF")
	text        = lipgloss.Color("#D8D0C4")
	muted       = lipgloss.Color("#8B746F")
	dark        = lipgloss.Color("#080503")
	panelStyle  = lipgloss.NewStyle().Foreground(text).Padding(1, 1)
	titleStyle  = lipgloss.NewStyle().Foreground(orange).Bold(true)
	nameStyle   = lipgloss.NewStyle().Foreground(text)
	idStyle     = lipgloss.NewStyle().Foreground(orange)
	mutedStyle  = lipgloss.NewStyle().Foreground(muted)
	ruleStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("#8A4A45"))
	headerStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("#FFF4DC"))
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

func (m model) Init() tea.Cmd {
	return tea.Batch(loadJobsCmd(m.root), tickCmd(m.interval))
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
			return m, loadJobsCmd(m.root)
		case "j", "down":
			if len(m.data.Rows) > 0 && m.selected < len(m.data.Rows)-1 {
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
		return m, tea.Batch(loadJobsCmd(m.root), tickCmd(m.interval))
	case jobsLoadedMsg:
		m.loading = false
		m.data = msg.data
		if m.selected >= len(m.data.Rows) {
			m.selected = max(0, len(m.data.Rows)-1)
		}
	}
	return m, nil
}

func (m model) View() tea.View {
	width := m.width
	if width <= 0 {
		width = 88
	}
	width = clamp(width-2, 46, 140)
	body := m.renderBody(width - 2)
	view := tea.NewView(panelStyle.Width(width).Render(body))
	view.AltScreen = true
	return view
}

func (m model) renderBody(width int) string {
	parts := []string{
		mutedStyle.Render(time.Now().Format("15:04:05") + "  jobs"),
		titleStyle.Render("> JOBS DASHBOARD"),
		ruleStyle.Render(strings.Repeat("─", max(8, width))),
		m.renderSummary(width),
		"",
	}
	if m.data.Err != nil {
		parts = append(parts, statusStyle("failed").Render(m.data.Err.Error()))
	} else if len(m.data.Rows) == 0 {
		parts = append(parts, mutedStyle.Render("No cluster jobs found."))
	} else {
		parts = append(parts, m.renderRows(width))
		parts = append(parts, "", m.renderDetail(width))
	}
	parts = append(parts, "", mutedStyle.Render("j/k select · r refresh · q quit · auto "+m.interval.String()))
	return lipgloss.JoinVertical(lipgloss.Left, parts...)
}

func (m model) renderSummary(width int) string {
	order := []string{"total", "running", "queued", "planned", "dry-run", "succeeded", "failed", "invalid", "unknown"}
	items := []string{}
	for _, key := range order {
		value := 0
		if key == "total" {
			value = len(m.data.Rows)
		} else {
			value = m.data.Counts[key]
		}
		if value == 0 && key != "total" {
			continue
		}
		label := strings.ToUpper(key)
		items = append(items, headerStyle.Render(label), nameStyle.Render(fmt.Sprintf("%d", value)))
	}
	line := strings.Join(items, "   ")
	if m.loading {
		line += mutedStyle.Render("   refreshing")
	}
	return clipStyled(line, width)
}

func (m model) renderRows(width int) string {
	statusWidth := 11
	taskWidth := 3
	ageWidth := 5
	stateWidth := 8
	gutters := 9
	idWidth := clamp(width/5, 16, 28)
	featureWidth := max(8, width-idWidth-statusWidth-taskWidth-ageWidth-stateWidth-gutters)
	maxRows := len(m.data.Rows)
	if m.height > 0 {
		maxRows = min(maxRows, max(4, m.height-8))
	} else {
		maxRows = min(maxRows, 10)
	}
	lines := make([]string, 0, maxRows+1)
	lines = append(lines, strings.Join([]string{
		cell(mutedStyle.Render("ID"), idWidth, false),
		cell(mutedStyle.Render("STATUS"), statusWidth, false),
		cell(mutedStyle.Render("TSK"), taskWidth, true),
		cell(mutedStyle.Render("AGE"), ageWidth, true),
		cell(mutedStyle.Render("STATE"), stateWidth, false),
		mutedStyle.Render("STEP / FEATURE"),
	}, "  "))
	for index, row := range m.data.Rows[:maxRows] {
		status := normalizeStatus(row.Status)
		statusText := statusBadge(status)
		stateStyle := green
		if row.State == "degraded" {
			stateStyle = orange
		} else if row.State == "empty" {
			stateStyle = muted
		}
		step := row.Step
		if row.Feature != "" && row.Feature != step {
			step = step + " · " + row.Feature
		}
		prefix := " "
		if index == m.selected {
			prefix = ">"
		}
		lines = append(lines, strings.Join([]string{
			cell(idStyle.Render(prefix+clip(row.ID, idWidth-1)), idWidth, false),
			cell(statusText, statusWidth, false),
			cell(nameStyle.Render(fmt.Sprintf("%d", row.Tasks)), taskWidth, true),
			cell(mutedStyle.Render(row.Age), ageWidth, true),
			cell(lipgloss.NewStyle().Foreground(stateStyle).Render(row.State), stateWidth, false),
			nameStyle.Render(clip(step, featureWidth)),
		}, "  "))
		if len(row.Reasons) > 0 && len(lines) < maxRows+1 {
			lines = append(lines, mutedStyle.Render("  degraded: "+clip(strings.Join(row.Reasons, "; "), width-14)))
		}
	}
	return lipgloss.JoinVertical(lipgloss.Left, lines...)
}

func (m model) renderDetail(width int) string {
	if len(m.data.Rows) == 0 || m.selected < 0 || m.selected >= len(m.data.Rows) {
		return ""
	}
	row := m.data.Rows[m.selected]
	lines := []string{
		ruleStyle.Render(strings.Repeat("─", max(8, width))),
		headerStyle.Render("SELECTED JOB"),
		nameStyle.Render(clip(row.ID, width)),
	}
	lines = append(lines,
		mutedStyle.Render("step")+" "+nameStyle.Render(clip(row.Step, width-6)),
		mutedStyle.Render("run ")+" "+nameStyle.Render(clip(row.RunDir, width-6)),
		mutedStyle.Render("summary")+" "+nameStyle.Render(clip(row.Summary, width-10)),
		mutedStyle.Render("command")+" "+nameStyle.Render(clip(row.Command, width-10)),
	)
	if len(row.Reasons) > 0 {
		lines = append(lines, statusStyle("failed").Render("degraded")+" "+mutedStyle.Render(clip(strings.Join(row.Reasons, "; "), width-10)))
	}
	lines = append(lines, headerStyle.Render("TASKS"))
	if len(row.TasksDetail) == 0 {
		lines = append(lines, mutedStyle.Render("no tasks recorded"))
	} else {
		for _, task := range row.TasksDetail {
			result := task.ReturnCode
			if result == "" {
				result = "pending"
			}
			lines = append(lines, nameStyle.Render(clip(task.ID, 18))+" "+mutedStyle.Render(clip(task.Node, 8))+" "+statusStyle(result).Render(result)+" "+nameStyle.Render(clip(task.Title, max(8, width-34))))
		}
	}
	if row.LatestLog != "" {
		lines = append(lines, headerStyle.Render("LATEST LOG"), mutedStyle.Render(clip(row.LatestLog, width)))
		for _, line := range row.LogTail {
			lines = append(lines, mutedStyle.Render("  "+clip(line, max(8, width-2))))
		}
	}
	lines = append(lines, headerStyle.Render("NEXT"), nameStyle.Render(clip(nextAction(row), width)))
	return lipgloss.JoinVertical(lipgloss.Left, lines...)
}

func loadJobsCmd(root string) tea.Cmd {
	return func() tea.Msg {
		return jobsLoadedMsg{data: loadJobs(root)}
	}
}

func tickCmd(interval time.Duration) tea.Cmd {
	return tea.Tick(interval, func(t time.Time) tea.Msg {
		return tickMsg(t)
	})
}

func loadJobs(root string) jobsData {
	runRoot := os.Getenv("CENTO_CLUSTER_JOBS_ROOT")
	if runRoot == "" {
		runRoot = filepath.Join(root, "workspace", "runs", "cluster-jobs")
	}
	if err := os.MkdirAll(runRoot, 0o755); err != nil {
		return jobsData{Err: err, UpdatedAt: time.Now(), Counts: map[string]int{}}
	}
	entries, err := os.ReadDir(runRoot)
	if err != nil {
		return jobsData{Err: err, UpdatedAt: time.Now(), Counts: map[string]int{}}
	}
	rows := []jobRow{}
	counts := map[string]int{}
	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		path := filepath.Join(runRoot, entry.Name(), "job.json")
		info, err := os.Stat(path)
		if err != nil {
			continue
		}
		raw, err := os.ReadFile(path)
		if err != nil {
			rows = append(rows, jobRow{ID: entry.Name(), Status: "invalid", Feature: err.Error(), Step: "read job.json", Age: ageLabel(info.ModTime()), State: "degraded", Reasons: []string{err.Error()}, ModTime: info.ModTime()})
			counts["invalid"]++
			continue
		}
		var record jobRecord
		if err := json.Unmarshal(raw, &record); err != nil {
			rows = append(rows, jobRow{ID: entry.Name(), Status: "invalid", Feature: err.Error(), Step: "parse job.json", Age: ageLabel(info.ModTime()), State: "degraded", Reasons: []string{err.Error()}, ModTime: info.ModTime()})
			counts["invalid"]++
			continue
		}
		if record.ID == "" {
			record.ID = entry.Name()
		}
		status := normalizeStatus(record.Status)
		counts[status]++
		runDir := record.RunDir
		if runDir == "" {
			runDir = filepath.Join(runRoot, entry.Name())
		}
		failed := failedResultCount(record.Results)
		reasons := degradedReasons(status, record, runDir)
		state := "ok"
		if len(record.Tasks) == 0 {
			state = "empty"
		}
		if len(reasons) > 0 {
			state = "degraded"
		}
		rows = append(rows, jobRow{
			ID:          record.ID,
			Status:      status,
			Feature:     firstLine(record.Feature),
			Tasks:       len(record.Tasks),
			Results:     len(record.Results),
			Failed:      failed,
			Step:        currentStep(record),
			Age:         ageLabel(jobUpdatedAt(record, info.ModTime())),
			State:       state,
			Reasons:     reasons,
			LatestLog:   latestLog(record, runDir),
			LogTail:     logTail(latestLog(record, runDir), 4),
			RunDir:      runDir,
			Summary:     artifactPath(record, runDir, "summary", "summary.md"),
			Command:     record.AgentCommand,
			TasksDetail: taskStates(record, runDir),
			ModTime:     info.ModTime(),
		})
	}
	sort.Slice(rows, func(i, j int) bool {
		return rows[i].ModTime.After(rows[j].ModTime)
	})
	return jobsData{Rows: rows, Counts: counts, UpdatedAt: time.Now()}
}

func artifactPath(record jobRecord, runDir string, key string, fallback string) string {
	if record.Artifacts != nil {
		if value := strings.TrimSpace(fmt.Sprint(record.Artifacts[key])); value != "" && value != "<nil>" {
			return value
		}
	}
	return filepath.Join(runDir, fallback)
}

func taskStates(record jobRecord, runDir string) []taskState {
	results := map[string]map[string]any{}
	for _, result := range record.Results {
		if taskID := strings.TrimSpace(fmt.Sprint(result["task"])); taskID != "" {
			results[taskID] = result
		}
	}
	tasks := make([]taskState, 0, len(record.Tasks))
	for _, task := range record.Tasks {
		id := strings.TrimSpace(fmt.Sprint(task["id"]))
		result := results[id]
		code := ""
		logPath := filepath.Join(runDir, "logs", id+".log")
		if result != nil {
			if value, ok := result["returncode"]; ok && value != nil {
				code = fmt.Sprint(value)
			} else {
				code = "ok"
			}
			if value := strings.TrimSpace(fmt.Sprint(result["log"])); value != "" && value != "<nil>" {
				logPath = value
			}
		}
		tasks = append(tasks, taskState{
			ID:         id,
			Title:      strings.TrimSpace(fmt.Sprint(task["title"])),
			Node:       strings.TrimSpace(fmt.Sprint(task["node"])),
			ReturnCode: code,
			Log:        logPath,
		})
	}
	return tasks
}

func logTail(path string, limit int) []string {
	if path == "" {
		return nil
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	all := strings.Split(strings.TrimRight(string(raw), "\n"), "\n")
	if len(all) <= limit {
		return all
	}
	return all[len(all)-limit:]
}

func nextAction(row jobRow) string {
	status := normalizeStatus(row.Status)
	if row.State == "degraded" || status == "failed" || status == "invalid" {
		if row.LatestLog != "" {
			return "inspect latest log, then rerun or mark blocked with failure detail"
		}
		return "inspect job.json and task manifests; log path is missing"
	}
	if status == "running" {
		return "tail latest log and wait for task result or timeout"
	}
	if status == "planned" || status == "queued" {
		return "run the job or keep planned until an operator assigns execution"
	}
	if status == "dry-run" {
		return "review generated scripts/manifests before actual execution"
	}
	return "review summary artifact and archive outcome"
}

func failedResultCount(results []map[string]any) int {
	count := 0
	for _, result := range results {
		value, ok := result["returncode"]
		if !ok || value == nil {
			continue
		}
		switch typed := value.(type) {
		case float64:
			if typed != 0 {
				count++
			}
		case int:
			if typed != 0 {
				count++
			}
		default:
			if fmt.Sprint(value) != "0" {
				count++
			}
		}
	}
	return count
}

func degradedReasons(status string, record jobRecord, runDir string) []string {
	reasons := []string{}
	if status == "failed" || status == "error" || status == "invalid" || status == "unknown" {
		reasons = append(reasons, "status="+status)
	}
	if failed := failedResultCount(record.Results); failed > 0 {
		reasons = append(reasons, fmt.Sprintf("%d failed task result(s)", failed))
	}
	if len(record.Tasks) > 0 && len(record.Results) == 0 && status != "planned" && status != "queued" && status != "dry-run" {
		reasons = append(reasons, "tasks have no results")
	}
	if latestLog(record, runDir) == "" && (status == "running" || status == "failed" || status == "succeeded") {
		reasons = append(reasons, "latest log missing")
	}
	return reasons
}

func currentStep(record jobRecord) string {
	results := map[string]bool{}
	for _, result := range record.Results {
		if task, ok := result["task"]; ok {
			results[fmt.Sprint(task)] = true
		}
	}
	for _, task := range record.Tasks {
		id := fmt.Sprint(task["id"])
		if id == "" {
			continue
		}
		if !results[id] {
			if title := strings.TrimSpace(fmt.Sprint(task["title"])); title != "" {
				return title
			}
			return id
		}
	}
	if len(record.Tasks) > 0 {
		last := record.Tasks[len(record.Tasks)-1]
		if title := strings.TrimSpace(fmt.Sprint(last["title"])); title != "" {
			return title
		}
		if id := strings.TrimSpace(fmt.Sprint(last["id"])); id != "" {
			return id
		}
		return "tasks complete"
	}
	return "no tasks"
}

func latestLog(record jobRecord, runDir string) string {
	candidates := []string{}
	for _, result := range record.Results {
		if value := strings.TrimSpace(fmt.Sprint(result["log"])); value != "" {
			candidates = append(candidates, value)
		}
	}
	matches, _ := filepath.Glob(filepath.Join(runDir, "logs", "*.log"))
	candidates = append(candidates, matches...)
	var latest string
	var latestTime time.Time
	for _, path := range candidates {
		info, err := os.Stat(path)
		if err != nil || info.IsDir() {
			continue
		}
		if latest == "" || info.ModTime().After(latestTime) {
			latest = path
			latestTime = info.ModTime()
		}
	}
	return latest
}

func jobUpdatedAt(record jobRecord, fallback time.Time) time.Time {
	for _, raw := range []string{record.FinishedAt, record.UpdatedAt, record.CreatedAt} {
		if parsed, ok := parseTime(raw); ok {
			return parsed
		}
	}
	return fallback
}

func parseTime(raw string) (time.Time, bool) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return time.Time{}, false
	}
	if strings.HasSuffix(raw, "Z") {
		raw = strings.TrimSuffix(raw, "Z") + "+00:00"
	}
	if parsed, err := time.Parse(time.RFC3339, raw); err == nil {
		return parsed, true
	}
	return time.Time{}, false
}

func ageLabel(value time.Time) string {
	if value.IsZero() {
		return "?"
	}
	seconds := int(time.Since(value).Seconds())
	if seconds < 0 {
		seconds = 0
	}
	if seconds < 60 {
		return fmt.Sprintf("%ds", seconds)
	}
	if seconds < 3600 {
		return fmt.Sprintf("%dm", seconds/60)
	}
	if seconds < 86400 {
		return fmt.Sprintf("%dh", seconds/3600)
	}
	return fmt.Sprintf("%dd", seconds/86400)
}

func firstLine(value string) string {
	for _, line := range strings.Split(value, "\n") {
		line = strings.TrimSpace(line)
		if line != "" {
			return line
		}
	}
	return ""
}

func normalizeStatus(value string) string {
	status := strings.ToLower(strings.TrimSpace(value))
	status = strings.ReplaceAll(status, "_", "-")
	if status == "" {
		return "unknown"
	}
	return status
}

func statusStyle(status string) lipgloss.Style {
	base := lipgloss.NewStyle().Bold(true)
	switch status {
	case "succeeded", "success", "done", "completed":
		return base.Foreground(green)
	case "failed", "error", "invalid":
		return base.Foreground(red)
	case "running", "active":
		return base.Foreground(blue)
	case "queued":
		return base.Foreground(purple)
	case "planned":
		return base.Foreground(amber)
	case "dry-run":
		return base.Foreground(muted)
	default:
		return base.Foreground(text)
	}
}

func statusBadge(status string) string {
	label := strings.ToUpper(status)
	return statusStyle(status).Render(label)
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

func clipStyled(value string, width int) string {
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
	fs := flag.NewFlagSet("industrial-jobs-tui", flag.ExitOnError)
	once := fs.Bool("once", false, "render once and exit")
	interval := fs.Duration("interval", 5*time.Second, "refresh interval")
	fs.Parse(os.Args[1:])

	model := model{root: root, interval: *interval, data: loadJobs(root), width: 100}
	if *once || !isTTY() {
		fmt.Println(model.renderBody(98))
		if model.data.Err != nil {
			os.Exit(1)
		}
		return
	}

	program := tea.NewProgram(model)
	if _, err := program.Run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
