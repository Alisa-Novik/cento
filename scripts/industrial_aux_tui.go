package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
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
	command string
	output  string
	err     error
}

type activityEntry struct {
	Stamp string
	Label string
	Badge string
	Hot   bool
}

type quickAction struct {
	Command string
	Label   string
}

type auxModel struct {
	root     string
	mode     string
	width    int
	height   int
	interval time.Duration
	entries  []activityEntry
	actions  []quickAction
	selected int
	running  string
	output   string
}

var (
	auxOrange     = lipgloss.Color("#FF4B00")
	auxAmber      = lipgloss.Color("#FF9A3D")
	auxGreen      = lipgloss.Color("#A0D76E")
	auxPurple     = lipgloss.Color("#B68CFF")
	auxText       = lipgloss.Color("#D8D0C4")
	auxMuted      = lipgloss.Color("#77706A")
	auxDark       = lipgloss.Color("#080909")
	auxPanel      = lipgloss.NewStyle().Foreground(auxText).Padding(1, 1)
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

func newModel(root, mode string, interval time.Duration) auxModel {
	return auxModel{
		root:     root,
		mode:     mode,
		interval: interval,
		actions: []quickAction{
			{Command: "cento act jobs", Label: "Jobs dashboard"},
			{Command: "cento cluster health", Label: "Cluster status"},
			{Command: "cento replay demo", Label: "Replay last demo"},
			{Command: "cento codex status", Label: "Codex usage"},
		},
	}
}

func (m auxModel) Init() tea.Cmd {
	if m.mode == "activity" {
		return tea.Batch(loadActivityCmd(m.root), tickCmd(m.interval))
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
		case "up", "k":
			if m.mode == "actions" && m.selected > 0 {
				m.selected--
			}
		case "down", "j":
			if m.mode == "actions" && m.selected < len(m.actions)-1 {
				m.selected++
			}
		case "enter":
			if m.mode == "actions" && len(m.actions) > 0 {
				action := m.actions[m.selected]
				m.running = action.Command
				m.output = "running..."
				return m, runActionCmd(m.root, action.Command)
			}
		}
	case tickMsg:
		if m.mode == "activity" {
			return m, tea.Batch(loadActivityCmd(m.root), tickCmd(m.interval))
		}
		return m, tickCmd(m.interval)
	case activityLoadedMsg:
		m.entries = msg.entries
	case actionDoneMsg:
		m.running = ""
		if msg.err != nil {
			m.output = fmt.Sprintf("%v: %s", msg.err, msg.output)
		} else {
			m.output = msg.output
			if strings.TrimSpace(m.output) == "" {
				m.output = "completed: " + msg.command
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
	entries := m.entries
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
	rows = append(rows, "", auxMutedStyle.Render(clip("+  View all activity logs", width)))
	return lipgloss.JoinVertical(lipgloss.Left, rows...)
}

func (m auxModel) renderActions(width int) string {
	rows := []string{auxTitle.Render("QUICK ACTIONS"), ""}
	cardWidth := max(20, width-4)
	for index, action := range m.actions {
		prefix := auxAmberStyle().Render("›")
		textWidth := max(8, cardWidth-5)
		command := auxTextStyle.Render(clip(action.Command, textWidth))
		label := auxMutedStyle.Render(clip(action.Label, textWidth))
		cardBody := lipgloss.JoinVertical(lipgloss.Left, prefix+"  "+command, "   "+label)
		style := auxActionCard.Width(cardWidth)
		if index == m.selected {
			style = auxActiveCard.Width(cardWidth - 1)
		}
		rows = append(rows, style.Render(cardBody))
	}
	prompt := "› _"
	if m.running != "" {
		prompt = "› " + m.running
	} else if m.output != "" {
		prompt = "› " + clip(strings.TrimSpace(m.output), width-3)
	}
	rows = append(rows, auxMutedStyle.Render(prompt))
	rows = append(rows, auxMutedStyle.Render("j/k move · enter run · q quit"))
	return lipgloss.JoinVertical(lipgloss.Left, rows...)
}

func loadActivityCmd(root string) tea.Cmd {
	return func() tea.Msg {
		return activityLoadedMsg{entries: recentActivity(filepath.Join(root, "logs"), 7)}
	}
}

func activityLine(entry activityEntry, width int) string {
	dot := auxQuietDot
	if entry.Hot {
		dot = auxHotDot
	}
	badge := badgeStyle(entry.Badge).Render(entry.Badge)
	stamp := clip(entry.Stamp, 8)
	labelWidth := max(4, width-30)
	var line string
	for {
		line = strings.Join([]string{
			"  " + dot,
			"  ",
			cell(auxMutedStyle.Render(stamp), 8, false),
			" ",
			cell(auxTextStyle.Render(clip(entry.Label, labelWidth)), labelWidth, false),
			" ",
			badge,
		}, "")
		if lipgloss.Width(line) <= width || labelWidth <= 4 {
			return line
		}
		labelWidth--
	}
}

func tickCmd(interval time.Duration) tea.Cmd {
	return tea.Tick(interval, func(t time.Time) tea.Msg {
		return tickMsg(t)
	})
}

func runActionCmd(root, command string) tea.Cmd {
	return func() tea.Msg {
		ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
		defer cancel()
		cmd := exec.CommandContext(ctx, "bash", "-lc", command)
		cmd.Dir = root
		cmd.Env = append(os.Environ(), "CENTO_ROOT_DIR="+root)
		out, err := cmd.CombinedOutput()
		if ctx.Err() != nil {
			err = ctx.Err()
		}
		return actionDoneMsg{command: command, output: strings.TrimSpace(string(out)), err: err}
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
	mode := fs.String("mode", "activity", "panel mode: activity or actions")
	once := fs.Bool("once", false, "render once and exit")
	interval := fs.Duration("interval", 5*time.Second, "refresh interval")
	fs.Parse(os.Args[1:])
	if fs.NArg() > 0 {
		*mode = fs.Arg(0)
	}
	if *mode != "activity" && *mode != "actions" {
		fmt.Fprintln(os.Stderr, "mode must be activity or actions")
		os.Exit(2)
	}

	model := newModel(root, *mode, *interval)
	if *mode == "activity" {
		model.entries = recentActivity(filepath.Join(root, "logs"), 7)
	}
	if *once || !isTTY() {
		view := model
		view.width = 46
		if *mode == "actions" {
			fmt.Println(view.renderActions(42))
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
