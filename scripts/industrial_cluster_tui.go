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
	"sort"
	"strconv"
	"strings"
	"time"

	tea "charm.land/bubbletea/v2"
	"charm.land/lipgloss/v2"
)

type commandResult struct {
	OK     bool   `json:"ok"`
	Stdout string `json:"stdout"`
	Stderr string `json:"stderr"`
}

type clusterNode struct {
	ID       string `json:"id"`
	Platform string `json:"platform"`
	Role     string `json:"role"`
	Socket   string `json:"socket"`
}

type clusterSnapshot struct {
	UpdatedAt string         `json:"updated_at"`
	Nodes     []clusterNode  `json:"nodes"`
	Status    commandResult  `json:"status"`
	Mesh      commandResult  `json:"mesh"`
	Jobs      map[string]int `json:"jobs"`
}

type nodeRow struct {
	Name   string
	State  string
	CPU    string
	Mem    string
	Uptime string
}

type eventRow struct {
	Hot   bool
	Stamp string
	Label string
	Age   string
}

type clusterData struct {
	Rows      []nodeRow
	Events    []eventRow
	UpdatedAt time.Time
	Err       error
}

type snapshotMsg struct {
	data clusterData
}

type tickMsg time.Time

type model struct {
	root     string
	loading  bool
	data     clusterData
	width    int
	height   int
	interval time.Duration
}

var (
	orange      = lipgloss.Color("#FF4B00")
	amber       = lipgloss.Color("#FF9A3D")
	green       = lipgloss.Color("#62E886")
	blue        = lipgloss.Color("#8DB9C7")
	text        = lipgloss.Color("#D8D0C4")
	muted       = lipgloss.Color("#77706A")
	dark        = lipgloss.Color("#080909")
	panelStyle  = lipgloss.NewStyle().Foreground(text).Padding(1, 1)
	titleStyle  = lipgloss.NewStyle().Foreground(orange).Bold(true)
	nameStyle   = lipgloss.NewStyle().Foreground(text)
	headerStyle = lipgloss.NewStyle().Foreground(blue).Bold(true)
	valueStyle  = lipgloss.NewStyle().Foreground(amber).Bold(true)
	mutedStyle  = lipgloss.NewStyle().Foreground(muted)
	goodDot     = lipgloss.NewStyle().Foreground(green).Bold(true).Render("●")
	quietDot    = lipgloss.NewStyle().Foreground(muted).Render("●")
	hotDot      = lipgloss.NewStyle().Foreground(orange).Bold(true).Render("●")
	badgeGood   = lipgloss.NewStyle().Foreground(amber).Background(lipgloss.Color("#461709")).Bold(true).Padding(0, 1)
	badgeWarn   = lipgloss.NewStyle().Foreground(lipgloss.Color("#FFD166")).Background(lipgloss.Color("#4D3005")).Bold(true).Padding(0, 1)
	tableStyle  = lipgloss.NewStyle().Border(lipgloss.RoundedBorder()).BorderForeground(lipgloss.Color("#2C2D2E")).Padding(0, 1)
	ansiPattern = regexp.MustCompile(`\x1b\[[0-9;?]*[ -/]*[@-~]`)
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
	return tea.Batch(loadCmd(m.root), tickCmd(m.interval))
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
			return m, loadCmd(m.root)
		}
	case tickMsg:
		if m.loading {
			return m, tickCmd(m.interval)
		}
		m.loading = true
		return m, tea.Batch(loadCmd(m.root), tickCmd(m.interval))
	case snapshotMsg:
		m.loading = false
		m.data = msg.data
	}
	return m, nil
}

func (m model) View() tea.View {
	width := m.width
	if width <= 0 {
		width = 58
	}
	width = clamp(width-2, 46, 62)
	contentWidth := width - 4
	body := m.renderBody(contentWidth)
	view := tea.NewView(panelStyle.Width(width).Render(body))
	view.AltScreen = true
	return view
}

func (m model) renderBody(width int) string {
	rows := m.data.Rows
	online := 0
	for _, row := range rows {
		if row.State == "online" {
			online++
		}
	}
	health := "DEGRADED"
	badge := badgeWarn.Render(health)
	if len(rows) > 0 && online == len(rows) && m.data.Err == nil {
		health = "HEALTHY"
		badge = badgeGood.Render(health)
	}

	iconTitle := titleStyle.Render("▣ CLUSTER STATUS")
	clusterTitle := titleStyle.Render("CENTO-CLUSTER")
	statusLine := fmt.Sprintf("%s nodes online", mutedStyle.Render(fmt.Sprintf("%d/%d", online, len(rows))))
	if m.loading {
		statusLine += mutedStyle.Render("  refreshing")
	}
	if m.data.Err != nil {
		statusLine = mutedStyle.Render("cluster data unavailable")
	}
	headerPad := strings.Repeat(" ", max(1, width-lipgloss.Width(clusterTitle)-lipgloss.Width(badge)))
	parts := []string{
		iconTitle,
		"",
		clusterTitle + headerPad + badge,
		statusLine,
		"",
		m.renderTable(width, rows),
		"",
		titleStyle.Render("RECENT EVENTS"),
		"",
		m.renderEvents(width),
		"",
		mutedStyle.Render("r refresh · q quit · auto " + m.interval.String()),
	}
	if m.data.Err != nil {
		parts = append(parts[:4], append([]string{"", valueStyle.Render(m.data.Err.Error())}, parts[4:]...)...)
	}
	return lipgloss.JoinVertical(lipgloss.Left, parts...)
}

func (m model) renderTable(width int, rows []nodeRow) string {
	inner := width - 4
	header := strings.Join([]string{
		cell(headerStyle.Render("NODE"), 14, false),
		cell(headerStyle.Render("STATUS"), 10, false),
		cell(headerStyle.Render("CPU"), 4, true),
		cell(headerStyle.Render("MEM"), 4, true),
		cell(headerStyle.Render("UP"), 7, true),
	}, " ")
	lines := []string{header}
	if len(rows) == 0 {
		lines = append(lines, mutedStyle.Render("no operational nodes registered"))
	} else {
		for _, row := range rows {
			dot := quietDot
			if row.State == "online" {
				dot = goodDot
			}
			state := fmt.Sprintf("%s %s", dot, row.State)
			lines = append(lines, strings.Join([]string{
				cell(nameStyle.Render(clip(row.Name, 14)), 14, false),
				cell(state, 10, false),
				cell(valueStyle.Render(row.CPU), 4, true),
				cell(valueStyle.Render(row.Mem), 4, true),
				cell(nameStyle.Render(row.Uptime), 7, true),
			}, " "))
		}
	}
	return tableStyle.Width(inner).Render(lipgloss.JoinVertical(lipgloss.Left, lines...))
}

func (m model) renderEvents(width int) string {
	if len(m.data.Events) == 0 {
		return mutedStyle.Render("no recent events")
	}
	labelWidth := max(16, width-25)
	lines := make([]string, 0, min(len(m.data.Events), 5))
	for _, event := range m.data.Events[:min(len(m.data.Events), 5)] {
		dot := quietDot
		if event.Hot {
			dot = hotDot
		}
		lines = append(lines, strings.Join([]string{
			" " + dot,
			" ",
			cell(mutedStyle.Render(event.Stamp), 5, false),
			" ",
			cell(nameStyle.Render(clip(event.Label, labelWidth)), labelWidth, false),
			cell(nameStyle.Render(event.Age), 6, true),
		}, ""))
	}
	return lipgloss.JoinVertical(lipgloss.Left, lines...)
}

func loadCmd(root string) tea.Cmd {
	return func() tea.Msg {
		return snapshotMsg{data: loadData(root)}
	}
}

func tickCmd(interval time.Duration) tea.Cmd {
	return tea.Tick(interval, func(t time.Time) tea.Msg {
		return tickMsg(t)
	})
}

func loadData(root string) clusterData {
	snapshot, err := loadSnapshot(root)
	if err != nil {
		return clusterData{Err: err, UpdatedAt: time.Now()}
	}
	metrics := localMetrics()
	states := parseNodeStates(snapshot.Status.Stdout)
	localID := parseLocalID(snapshot.Status.Stdout)
	meshAges := parseMeshAges(snapshot.Mesh.Stdout)
	rows := make([]nodeRow, 0, len(snapshot.Nodes))
	for _, node := range snapshot.Nodes {
		if node.Role == "companion" {
			continue
		}
		state := states[node.ID]
		if state == "" {
			state = "registered"
		}
		if state == "connected" || state == "local" {
			state = "online"
		}
		cpu := "--"
		mem := "--"
		uptime := "--"
		if node.ID == localID {
			cpu = metrics.CPU
			mem = metrics.Mem
			uptime = metrics.Uptime
		} else if state == "online" {
			uptime = meshAges[node.Socket]
			if uptime == "" {
				uptime = "now"
			}
		}
		rows = append(rows, nodeRow{Name: node.ID, State: state, CPU: cpu, Mem: mem, Uptime: uptime})
	}
	return clusterData{
		Rows:      rows,
		Events:    recentEvents(filepath.Join(root, "logs"), 5),
		UpdatedAt: time.Now(),
	}
}

func parseLocalID(output string) string {
	for _, raw := range strings.Split(stripANSI(output), "\n") {
		parts := strings.Fields(strings.TrimSpace(raw))
		if len(parts) >= 2 && parts[0] == "local" {
			return parts[1]
		}
	}
	return "linux"
}

func loadSnapshot(root string) (clusterSnapshot, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	code := "import json, sys; sys.path.insert(0, 'scripts'); from network_web_server import cluster_snapshot; print(json.dumps(cluster_snapshot()))"
	cmd := exec.CommandContext(ctx, "python3", "-c", code)
	cmd.Dir = root
	out, err := cmd.CombinedOutput()
	if ctx.Err() != nil {
		return clusterSnapshot{}, ctx.Err()
	}
	if err != nil {
		return clusterSnapshot{}, fmt.Errorf("%v: %s", err, strings.TrimSpace(string(out)))
	}
	var snapshot clusterSnapshot
	if err := json.Unmarshal(out, &snapshot); err != nil {
		return clusterSnapshot{}, err
	}
	return snapshot, nil
}

func parseNodeStates(output string) map[string]string {
	states := map[string]string{}
	inNodes := false
	for _, raw := range strings.Split(stripANSI(output), "\n") {
		line := strings.TrimSpace(raw)
		if line == "nodes" {
			inNodes = true
			continue
		}
		if !inNodes || line == "" {
			continue
		}
		parts := strings.Fields(line)
		if len(parts) >= 2 {
			states[parts[0]] = parts[1]
		}
	}
	return states
}

func parseMeshAges(output string) map[string]string {
	ages := map[string]string{}
	now := time.Now()
	for _, raw := range strings.Split(stripANSI(output), "\n") {
		parts := strings.Fields(raw)
		if len(parts) < 9 {
			continue
		}
		socket := parts[len(parts)-1]
		month, day, clock := parts[len(parts)-4], parts[len(parts)-3], parts[len(parts)-2]
		parsed, err := time.ParseInLocation("Jan 2 15:04 2006", fmt.Sprintf("%s %s %s %d", month, day, clock, now.Year()), time.Local)
		if err != nil {
			continue
		}
		if parsed.After(now) {
			ages[socket] = "now"
		} else {
			ages[socket] = compactDuration(now.Sub(parsed))
		}
	}
	return ages
}

type metricsRow struct {
	CPU    string
	Mem    string
	Uptime string
}

func localMetrics() metricsRow {
	return metricsRow{
		CPU:    fmt.Sprintf("%d%%", cpuPercent()),
		Mem:    fmt.Sprintf("%d%%", memoryPercent()),
		Uptime: localUptime(),
	}
}

func cpuPercent() int {
	totalA, idleA, okA := readCPU()
	time.Sleep(60 * time.Millisecond)
	totalB, idleB, okB := readCPU()
	if !okA || !okB || totalB <= totalA {
		return 0
	}
	totalDelta := totalB - totalA
	idleDelta := idleB - idleA
	return clampInt(int((1-float64(idleDelta)/float64(totalDelta))*100+0.5), 0, 100)
}

func readCPU() (int64, int64, bool) {
	raw, err := os.ReadFile("/proc/stat")
	if err != nil {
		return 0, 0, false
	}
	fields := strings.Fields(strings.SplitN(string(raw), "\n", 2)[0])
	if len(fields) < 5 {
		return 0, 0, false
	}
	var values []int64
	for _, field := range fields[1:] {
		value, err := strconv.ParseInt(field, 10, 64)
		if err != nil {
			return 0, 0, false
		}
		values = append(values, value)
	}
	total := int64(0)
	for _, value := range values {
		total += value
	}
	idle := values[3]
	if len(values) > 4 {
		idle += values[4]
	}
	return total, idle, true
}

func memoryPercent() int {
	raw, err := os.ReadFile("/proc/meminfo")
	if err != nil {
		return 0
	}
	values := map[string]int64{}
	for _, line := range strings.Split(string(raw), "\n") {
		parts := strings.Fields(strings.Replace(line, ":", "", 1))
		if len(parts) >= 2 {
			value, _ := strconv.ParseInt(parts[1], 10, 64)
			values[parts[0]] = value
		}
	}
	total := values["MemTotal"]
	available := values["MemAvailable"]
	if total <= 0 {
		return 0
	}
	return clampInt(int((1-float64(available)/float64(total))*100+0.5), 0, 100)
}

func localUptime() string {
	raw, err := os.ReadFile("/proc/uptime")
	if err != nil {
		return "--"
	}
	fields := strings.Fields(string(raw))
	if len(fields) == 0 {
		return "--"
	}
	seconds, err := strconv.ParseFloat(fields[0], 64)
	if err != nil {
		return "--"
	}
	return compactDuration(time.Duration(seconds) * time.Second)
}

func recentEvents(logRoot string, limit int) []eventRow {
	entries, err := os.ReadDir(logRoot)
	if err != nil {
		return nil
	}
	type candidate struct {
		mod   time.Time
		event eventRow
	}
	var candidates []candidate
	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		dir := filepath.Join(logRoot, entry.Name())
		files, _ := filepath.Glob(filepath.Join(dir, "*.log"))
		for _, file := range files {
			info, err := os.Stat(file)
			if err != nil {
				continue
			}
			line := lastMeaningfulLine(file)
			label := cleanEventLabel(entry.Name(), line)
			candidates = append(candidates, candidate{
				mod: info.ModTime(),
				event: eventRow{
					Hot:   isHotSource(entry.Name()),
					Stamp: info.ModTime().Format("15:04"),
					Label: label,
					Age:   compactDuration(time.Since(info.ModTime())),
				},
			})
		}
	}
	sort.Slice(candidates, func(i, j int) bool {
		return candidates[i].mod.After(candidates[j].mod)
	})
	seen := map[string]bool{}
	events := make([]eventRow, 0, limit)
	for _, candidate := range candidates {
		if seen[candidate.event.Label] {
			continue
		}
		seen[candidate.event.Label] = true
		events = append(events, candidate.event)
		if len(events) >= limit {
			break
		}
	}
	return events
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

func isHotSource(source string) bool {
	switch source {
	case "cluster-jobs", "dashboard", "industrial-os", "industrial-workspace":
		return true
	default:
		return false
	}
}

func stripANSI(value string) string {
	return ansiPattern.ReplaceAllString(value, "")
}

func compactDuration(d time.Duration) string {
	if d < 0 {
		return "now"
	}
	if d < time.Minute {
		seconds := int(d.Seconds())
		if seconds < 1 {
			seconds = 1
		}
		return fmt.Sprintf("%ds", seconds)
	}
	if d < time.Hour {
		return fmt.Sprintf("%dm", int(d.Minutes()))
	}
	hours := int(d.Hours())
	minutes := int(d.Minutes()) % 60
	if hours < 24 {
		return fmt.Sprintf("%dh %02dm", hours, minutes)
	}
	return fmt.Sprintf("%dd", hours/24)
}

func clip(value string, width int) string {
	plain := stripANSI(value)
	if lipgloss.Width(plain) <= width {
		return plain
	}
	if width <= 1 {
		return plain[:width]
	}
	runes := []rune(plain)
	if len(runes) <= width {
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

func clampInt(value, low, high int) int {
	return clamp(value, low, high)
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
	fs := flag.NewFlagSet("industrial-cluster-tui", flag.ExitOnError)
	once := fs.Bool("once", false, "render once and exit")
	interval := fs.Duration("interval", 5*time.Second, "refresh interval")
	fs.Parse(os.Args[1:])

	if *once || !isTTY() {
		data := loadData(root)
		view := model{root: root, data: data, interval: *interval, width: 58}.renderBody(54)
		fmt.Println(view)
		if data.Err != nil {
			os.Exit(1)
		}
		return
	}

	program := tea.NewProgram(model{root: root, loading: true, interval: *interval})
	if _, err := program.Run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
