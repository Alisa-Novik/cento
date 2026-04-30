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
	ID         string           `json:"id"`
	Status     string           `json:"status"`
	Feature    string           `json:"feature"`
	CreatedAt  string           `json:"created_at"`
	FinishedAt string           `json:"finished_at"`
	Tasks      []map[string]any `json:"tasks"`
}

type jobRow struct {
	ID      string
	Status  string
	Feature string
	Tasks   int
	ModTime time.Time
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
	}
	parts = append(parts, "", mutedStyle.Render("r refresh · q quit · auto "+m.interval.String()))
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
	gutters := 5
	idWidth := clamp(width/4, 18, 34)
	featureWidth := max(8, width-idWidth-statusWidth-taskWidth-gutters)
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
		mutedStyle.Render("FEATURE"),
	}, "  "))
	for _, row := range m.data.Rows[:maxRows] {
		status := normalizeStatus(row.Status)
		statusText := statusBadge(status)
		lines = append(lines, strings.Join([]string{
			cell(idStyle.Render(clip(row.ID, idWidth)), idWidth, false),
			cell(statusText, statusWidth, false),
			cell(nameStyle.Render(fmt.Sprintf("%d", row.Tasks)), taskWidth, true),
			nameStyle.Render(clip(row.Feature, featureWidth)),
		}, "  "))
	}
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
	runRoot := filepath.Join(root, "workspace", "runs", "cluster-jobs")
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
			rows = append(rows, jobRow{ID: entry.Name(), Status: "invalid", Feature: err.Error(), ModTime: info.ModTime()})
			counts["invalid"]++
			continue
		}
		var record jobRecord
		if err := json.Unmarshal(raw, &record); err != nil {
			rows = append(rows, jobRow{ID: entry.Name(), Status: "invalid", Feature: err.Error(), ModTime: info.ModTime()})
			counts["invalid"]++
			continue
		}
		if record.ID == "" {
			record.ID = entry.Name()
		}
		status := normalizeStatus(record.Status)
		counts[status]++
		rows = append(rows, jobRow{
			ID:      record.ID,
			Status:  status,
			Feature: firstLine(record.Feature),
			Tasks:   len(record.Tasks),
			ModTime: info.ModTime(),
		})
	}
	sort.Slice(rows, func(i, j int) bool {
		return rows[i].ModTime.After(rows[j].ModTime)
	})
	return jobsData{Rows: rows, Counts: counts, UpdatedAt: time.Now()}
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
