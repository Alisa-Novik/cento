package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	tea "charm.land/bubbletea/v2"
	"charm.land/lipgloss/v2"
)

type commandResult struct {
	ReturnCode *int   `json:"returncode"`
	Stdout     string `json:"stdout"`
	Stderr     string `json:"stderr"`
}

type hostInfo struct {
	Hostname string `json:"hostname"`
	Platform string `json:"platform"`
	User     string `json:"user"`
	Home     string `json:"home"`
}

type repoInfo struct {
	Root      string        `json:"root"`
	Exists    bool          `json:"exists"`
	GitStatus commandResult `json:"git_status"`
	Head      commandResult `json:"head"`
}

type toolsInfo struct {
	Count     int      `json:"count"`
	MacOS     []string `json:"macos"`
	Linux     []string `json:"linux"`
	Both      []string `json:"both"`
	LinuxOnly []string `json:"linux_only"`
	MacOSOnly []string `json:"macos_only"`
}

type configInfo struct {
	EnvMCP             string `json:"env_mcp"`
	EnvMCPExists       bool   `json:"env_mcp_exists"`
	CentoRootEnv       string `json:"cento_root_env"`
	GitHubTokenPresent bool   `json:"github_token_present"`
}

type healthInfo struct {
	Tmux               commandResult `json:"tmux"`
	MeshStatus         commandResult `json:"mesh_status"`
	LinuxBridgeService commandResult `json:"linux_bridge_service"`
	Activity           activityInfo  `json:"activity"`
	AppleWatch         watchInfo     `json:"apple_watch"`
}

type activityInfo struct {
	State   string `json:"state"`
	Summary string `json:"summary"`
	Count   int    `json:"count"`
}

type watchInfo struct {
	Name       string `json:"name"`
	Connection string `json:"connection"`
	Activity   string `json:"activity"`
	Detail     string `json:"detail"`
}

type localInfo struct {
	Host     hostInfo          `json:"host"`
	Repo     repoInfo          `json:"repo"`
	Commands map[string]string `json:"commands"`
	Config   configInfo        `json:"config"`
	Tools    toolsInfo         `json:"tools"`
	Health   healthInfo        `json:"health"`
}

type remoteInfo struct {
	Connection map[string]string `json:"connection"`
	Raw        commandResult     `json:"raw"`
	Parsed     map[string]string `json:"parsed"`
}

type contextPayload struct {
	GeneratedAt string      `json:"generated_at"`
	Local       localInfo   `json:"local"`
	Remote      *remoteInfo `json:"remote"`
}

type loadedMsg struct {
	payload contextPayload
	err     error
}

type tickMsg time.Time
type actionMsg struct {
	name   string
	output string
	err    error
}

type model struct {
	root         string
	noRemote     bool
	payload      contextPayload
	err          error
	loading      bool
	action       string
	actionOutput string
	width        int
	height       int
	updatedAt    time.Time
}

var (
	frameStyle  = lipgloss.NewStyle().Padding(1, 2)
	titleStyle  = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#F8F5EA")).Background(lipgloss.Color("#214E5A")).Padding(0, 1)
	panelStyle  = lipgloss.NewStyle().Border(lipgloss.RoundedBorder()).BorderForeground(lipgloss.Color("#52645D")).Padding(1, 2)
	cardStyle   = lipgloss.NewStyle().Border(lipgloss.RoundedBorder()).BorderForeground(lipgloss.Color("#52645D")).Padding(1, 2)
	goodStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("#3D8B62")).Bold(true)
	warnStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("#C3833A")).Bold(true)
	badStyle    = lipgloss.NewStyle().Foreground(lipgloss.Color("#C24C43")).Bold(true)
	blueStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("#2F6F95")).Bold(true)
	subtleStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("#68787C"))
)

func initRoot() string {
	if root := os.Getenv("CENTO_ROOT_DIR"); root != "" {
		return root
	}
	if cwd, err := os.Getwd(); err == nil {
		if _, statErr := os.Stat(filepath.Join(cwd, "data", "tools.json")); statErr == nil {
			return cwd
		}
	}
	exe, err := os.Executable()
	if err == nil {
		return filepath.Clean(filepath.Join(filepath.Dir(exe), "..", "..", ".."))
	}
	return "."
}

func gatherCmd(root string, noRemote bool) tea.Cmd {
	return func() tea.Msg {
		args := []string{filepath.Join(root, "scripts", "gather_context.py"), "--root", root, "--json"}
		if noRemote {
			args = append(args, "--no-remote")
		}
		cmd := exec.Command("python3", args...)
		cmd.Dir = root
		out, err := cmd.CombinedOutput()
		if err != nil {
			return loadedMsg{err: fmt.Errorf("%v: %s", err, strings.TrimSpace(string(out)))}
		}
		var payload contextPayload
		if err := json.Unmarshal(out, &payload); err != nil {
			return loadedMsg{err: err}
		}
		return loadedMsg{payload: payload}
	}
}

func tickCmd() tea.Cmd {
	return tea.Tick(10*time.Second, func(t time.Time) tea.Msg {
		return tickMsg(t)
	})
}

func actionCmd(root string, name string, args ...string) tea.Cmd {
	return func() tea.Msg {
		cmdArgs := append([]string{filepath.Join(root, "scripts", "cento.sh"), "cluster"}, args...)
		cmd := exec.Command(cmdArgs[0], cmdArgs[1:]...)
		cmd.Dir = root
		out, err := cmd.CombinedOutput()
		return actionMsg{name: name, output: strings.TrimSpace(string(out)), err: err}
	}
}

func (m model) Init() tea.Cmd {
	return tea.Batch(gatherCmd(m.root, m.noRemote), tickCmd())
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
			return m, gatherCmd(m.root, m.noRemote)
		case "s":
			m.action = "sync"
			m.actionOutput = "running git drift check..."
			return m, actionCmd(m.root, "sync", "sync")
		case "h":
			m.action = "heal"
			m.actionOutput = "running cluster heal..."
			return m, actionCmd(m.root, "heal", "heal")
		}
	case tickMsg:
		m.loading = true
		return m, tea.Batch(gatherCmd(m.root, m.noRemote), tickCmd())
	case loadedMsg:
		m.loading = false
		m.err = msg.err
		if msg.err == nil {
			m.payload = msg.payload
			m.updatedAt = time.Now()
		}
	case actionMsg:
		m.action = msg.name
		if msg.err != nil {
			m.actionOutput = fmt.Sprintf("%v: %s", msg.err, msg.output)
		} else {
			m.actionOutput = msg.output
			m.loading = true
			return m, gatherCmd(m.root, m.noRemote)
		}
	}
	return m, nil
}

func statusLabel(ok bool, text string) string {
	if ok {
		return goodStyle.Render("ok") + " " + text
	}
	return badStyle.Render("fail") + " " + text
}

func stateBadge(level string, text string) string {
	switch level {
	case "ok":
		return goodStyle.Render(text)
	case "warn":
		return warnStyle.Render(text)
	default:
		return badStyle.Render(text)
	}
}

func levelForBool(ok bool) string {
	if ok {
		return "ok"
	}
	return "fail"
}

func firstLine(text string) string {
	text = strings.TrimSpace(text)
	if text == "" {
		return "unknown"
	}
	return strings.Split(text, "\n")[0]
}

func valueOr(value string, fallback string) string {
	if strings.TrimSpace(value) == "" {
		return fallback
	}
	return value
}

func commandOK(result commandResult) bool {
	return result.ReturnCode != nil && *result.ReturnCode == 0
}

func commandStatus(result commandResult) string {
	if commandOK(result) {
		return "ok"
	}
	if result.ReturnCode == nil {
		return "warn"
	}
	return "fail"
}

func remoteOK(remote *remoteInfo) bool {
	return remote != nil && commandOK(remote.Raw)
}

func socketSeen(mesh string, socket string) bool {
	return strings.Contains(mesh, socket)
}

func tmuxSummary(text string) string {
	text = strings.TrimSpace(text)
	if text == "" {
		return "no sessions"
	}
	return firstLine(text)
}

func serviceSummary(value string) string {
	value = strings.TrimSpace(value)
	if value == "" {
		return "unknown"
	}
	return firstLine(value)
}

type nodeRow struct {
	Name       string
	Platform   string
	Connection string
	Activity   string
	Detail     string
	Repo       string
	RepoDirty  int
	RepoHead   string
	Service    string
	Tmux       string
	Agent      string
	Level      string
}

func connectionLevel(connection string) string {
	switch strings.ToLower(strings.TrimSpace(connection)) {
	case "connected", "local":
		return "ok"
	case "unknown", "disabled":
		return "warn"
	default:
		return "fail"
	}
}

func activityLevel(activity string) string {
	if strings.Contains(strings.ToLower(activity), "executing") {
		return "warn"
	}
	return "ok"
}

func localActivity(local localInfo) string {
	if local.Health.Activity.State != "" {
		return local.Health.Activity.State
	}
	if commandOK(local.Health.Tmux) {
		return "idle"
	}
	return "unknown"
}

func activityShort(activity string) string {
	lowered := strings.ToLower(strings.TrimSpace(activity))
	if strings.Contains(lowered, "executing") {
		return "agent running"
	}
	if lowered == "" || lowered == "unknown" {
		return "unknown"
	}
	return lowered
}

func remoteActivity(remote *remoteInfo) string {
	if remote == nil {
		return "unknown"
	}
	return valueOr(remote.Parsed["activity"], "idle")
}

func agentSummary(text string) string {
	text = strings.TrimSpace(text)
	if text == "" || text == "idle" {
		return "none"
	}
	lowered := strings.ToLower(text)
	if strings.Contains(lowered, "codex") {
		return "codex"
	}
	return firstLine(text)
}

func tmuxSessionCount(text string) string {
	text = strings.TrimSpace(text)
	if text == "" || strings.Contains(strings.ToLower(text), "no server") {
		return "0"
	}
	if strings.Contains(strings.ToLower(text), "error") {
		return "unknown"
	}
	parts := strings.Split(text, ";")
	count := 0
	for _, part := range parts {
		if strings.TrimSpace(part) != "" {
			count++
		}
	}
	if count == 0 {
		count = len(strings.Split(text, "\n"))
	}
	return fmt.Sprintf("%d", count)
}

func remoteAgent(remote *remoteInfo) string {
	if remote == nil {
		return "unknown"
	}
	if !remoteOK(remote) {
		return "unreachable"
	}
	return agentSummary(remote.Parsed["activity_detail"])
}

func gitDirtyCount(status string) int {
	lines := strings.Split(strings.TrimSpace(status), "\n")
	count := 0
	for _, line := range lines {
		if strings.TrimSpace(line) == "" || strings.HasPrefix(line, "## ") {
			continue
		}
		count++
	}
	return count
}

func repoSummary(branch string, head string, dirty int) string {
	if strings.TrimSpace(head) == "" {
		head = "unknown"
	}
	if dirty > 0 {
		return fmt.Sprintf("%d dirty", dirty)
	}
	return "clean"
}

func remoteDirty(remote *remoteInfo) int {
	if remote == nil {
		return 0
	}
	value := strings.TrimSpace(remote.Parsed["git_dirty_count"])
	if value == "" {
		return 0
	}
	parsed, err := strconv.Atoi(value)
	if err != nil {
		return 0
	}
	return parsed
}

func (m model) clusterRows() []nodeRow {
	local := m.payload.Local
	remote := m.payload.Remote
	var rows []nodeRow

	linuxConnection := "disconnected"
	linuxActivity := "unknown"
	linuxTmux := "unknown"
	linuxAgent := "unknown"
	linuxRepoDirty := 0
	linuxRepoHead := "unknown"
	if local.Host.Platform == "linux" {
		linuxConnection = "local"
		linuxActivity = localActivity(local)
		linuxTmux = tmuxSessionCount(local.Health.Tmux.Stdout)
		linuxAgent = agentSummary(local.Health.Activity.Summary)
		linuxRepoDirty = gitDirtyCount(local.Repo.GitStatus.Stdout)
		linuxRepoHead = valueOr(local.Repo.Head.Stdout, "unknown")
	} else if remote != nil && strings.Contains(remote.Connection["remote"], "cento-linux") {
		if remoteOK(remote) {
			linuxConnection = "connected"
		}
		linuxActivity = remoteActivity(remote)
		linuxTmux = tmuxSessionCount(remote.Parsed["tmux"])
		linuxAgent = remoteAgent(remote)
		linuxRepoDirty = remoteDirty(remote)
		linuxRepoHead = valueOr(remote.Parsed["git_head"], "unknown")
	}
	rows = append(rows, nodeRow{
		Name:       "node 1",
		Platform:   "linux",
		Connection: linuxConnection,
		Activity:   activityShort(linuxActivity),
		Detail:     remoteHostFor("linux", local, remote),
		Repo:       repoSummary("", linuxRepoHead, linuxRepoDirty),
		RepoDirty:  linuxRepoDirty,
		RepoHead:   linuxRepoHead,
		Service:    remoteServiceFor("linux", local, remote),
		Tmux:       linuxTmux,
		Agent:      linuxAgent,
		Level:      connectionLevel(linuxConnection),
	})

	watch := local.Health.AppleWatch
	watchName := valueOr(watch.Name, "apple watch")
	watchConnection := valueOr(watch.Connection, "unknown")
	rows = append(rows, nodeRow{
		Name:       "node 2",
		Platform:   "apple watch",
		Connection: watchConnection,
		Activity:   valueOr(watch.Activity, "idle"),
		Detail:     watchName,
		Repo:       "presence only",
		RepoDirty:  0,
		RepoHead:   "",
		Service:    "bluetooth",
		Tmux:       "-",
		Agent:      valueOr(watch.Detail, "presence"),
		Level:      connectionLevel(watchConnection),
	})

	macConnection := "disconnected"
	macActivity := "unknown"
	macTmux := "unknown"
	macAgent := "unknown"
	macRepoDirty := 0
	macRepoHead := "unknown"
	if local.Host.Platform == "macos" {
		macConnection = "local"
		macActivity = localActivity(local)
		macTmux = tmuxSessionCount(local.Health.Tmux.Stdout)
		macAgent = agentSummary(local.Health.Activity.Summary)
		macRepoDirty = gitDirtyCount(local.Repo.GitStatus.Stdout)
		macRepoHead = valueOr(local.Repo.Head.Stdout, "unknown")
	} else if remote != nil && strings.Contains(remote.Connection["remote"], "cento-mac") {
		if remoteOK(remote) {
			macConnection = "connected"
		}
		macActivity = remoteActivity(remote)
		macTmux = tmuxSessionCount(remote.Parsed["tmux"])
		macAgent = remoteAgent(remote)
		macRepoDirty = remoteDirty(remote)
		macRepoHead = valueOr(remote.Parsed["git_head"], "unknown")
	}
	rows = append(rows, nodeRow{
		Name:       "node 3",
		Platform:   "macos",
		Connection: macConnection,
		Activity:   activityShort(macActivity),
		Detail:     remoteHostFor("macos", local, remote),
		Repo:       repoSummary("", macRepoHead, macRepoDirty),
		RepoDirty:  macRepoDirty,
		RepoHead:   macRepoHead,
		Service:    remoteServiceFor("macos", local, remote),
		Tmux:       macTmux,
		Agent:      macAgent,
		Level:      connectionLevel(macConnection),
	})

	return rows
}

func remoteRepoFor(platform string, local localInfo, remote *remoteInfo) string {
	if local.Host.Platform == platform {
		return repoSummary(local.Repo.GitStatus.Stdout, local.Repo.Head.Stdout, gitDirtyCount(local.Repo.GitStatus.Stdout))
	}
	if remote != nil && remoteOK(remote) {
		if platform == "linux" && strings.Contains(remote.Connection["remote"], "cento-linux") {
			return repoSummary(remote.Parsed["git_status"], remote.Parsed["git_head"], remoteDirty(remote))
		}
		if platform == "macos" && strings.Contains(remote.Connection["remote"], "cento-mac") {
			return repoSummary(remote.Parsed["git_status"], remote.Parsed["git_head"], remoteDirty(remote))
		}
	}
	return "unknown"
}

func remoteServiceFor(platform string, local localInfo, remote *remoteInfo) string {
	if platform == "linux" {
		if local.Host.Platform == "linux" {
			return serviceSummary(local.Health.LinuxBridgeService.Stdout)
		}
		if remote != nil && strings.Contains(remote.Connection["remote"], "cento-linux") {
			return serviceSummary(remote.Parsed["linux_bridge_service"])
		}
		return "unknown"
	}
	if platform == "macos" {
		if local.Host.Platform == "macos" {
			return "launchd active"
		}
		return "launchd"
	}
	return "n/a"
}

func detailWithHost(host string, detail string) string {
	host = strings.TrimSpace(host)
	detail = strings.TrimSpace(detail)
	if host == "" {
		return valueOr(detail, "unknown")
	}
	if detail == "" {
		return host
	}
	return fmt.Sprintf("%s - %s", host, detail)
}

func remoteHostFor(platform string, local localInfo, remote *remoteInfo) string {
	if local.Host.Platform == platform {
		return local.Host.Hostname
	}
	if remote != nil && remoteOK(remote) {
		if platform == "linux" && strings.Contains(remote.Connection["remote"], "cento-linux") {
			return valueOr(remote.Parsed["hostname"], "")
		}
		if platform == "macos" && strings.Contains(remote.Connection["remote"], "cento-mac") {
			return valueOr(remote.Parsed["hostname"], "")
		}
	}
	return ""
}

func (m model) clusterPanel(width int) string {
	cardWidth := (width - 8) / 3
	if cardWidth < 28 {
		cardWidth = width
	}
	cards := make([]string, 0, 3)
	for _, row := range m.clusterRows() {
		cards = append(cards, nodeCard(row, cardWidth))
	}
	cardBlock := lipgloss.JoinHorizontal(lipgloss.Top, cards...)
	if cardWidth == width {
		cardBlock = lipgloss.JoinVertical(lipgloss.Left, cards...)
	}

	lines := []string{
		titleStyle.Render(" nodes "),
		cardBlock,
	}

	if m.noRemote {
		lines = append(lines, warnStyle.Render("remote checks disabled"))
	}
	return panelStyle.Width(width).Render(strings.Join(lines, "\n"))
}

func nodeCard(row nodeRow, width int) string {
	header := lipgloss.JoinHorizontal(
		lipgloss.Center,
		titleStyle.Render(" "+row.Name+" "),
		" ",
		subtleStyle.Render(row.Platform),
	)
	lines := []string{
		header,
		fmt.Sprintf("%-8s %s", "link", stateBadge(row.Level, row.Connection)),
		fmt.Sprintf("%-8s %s", "work", stateBadge(activityLevel(row.Activity), row.Activity)),
		fmt.Sprintf("%-8s %s", "agent", agentState(row.Agent)),
		fmt.Sprintf("%-8s %s", "tmux", tmuxState(row.Tmux)),
		fmt.Sprintf("%-8s %s", "repo", repoState(row.Repo)),
		fmt.Sprintf("%-8s %s", "svc", serviceState(row.Service)),
	}
	return cardStyle.Width(width).Render(strings.Join(lines, "\n"))
}

func agentState(agent string) string {
	level := "ok"
	if agent != "none" && agent != "-" && agent != "presence" {
		level = "warn"
	}
	return stateBadge(level, valueOr(agent, "none"))
}

func tmuxState(tmux string) string {
	level := "ok"
	if tmux == "unknown" {
		level = "warn"
	}
	label := tmux
	if tmux != "-" && tmux != "unknown" {
		label = tmux + " sessions"
	}
	return stateBadge(level, label)
}

func serviceState(service string) string {
	level := "ok"
	lowered := strings.ToLower(service)
	if strings.Contains(lowered, "inactive") || strings.Contains(lowered, "unknown") || strings.Contains(lowered, "failed") {
		level = "warn"
	}
	return stateBadge(level, valueOr(service, "unknown"))
}

func repoState(repo string) string {
	level := "ok"
	if strings.Contains(repo, "dirty") || strings.Contains(repo, "unknown") {
		level = "warn"
	}
	return stateBadge(level, repo)
}

func wrapDetail(text string, width int) string {
	text = strings.TrimSpace(text)
	if text == "" {
		return subtleStyle.Render("no details")
	}
	if width < 18 {
		width = 18
	}
	words := strings.Fields(text)
	var lines []string
	current := ""
	for _, word := range words {
		if current == "" {
			current = word
			continue
		}
		if len(current)+1+len(word) > width {
			lines = append(lines, current)
			current = word
			continue
		}
		current += " " + word
	}
	if current != "" {
		lines = append(lines, current)
	}
	if len(lines) > 3 {
		lines = append(lines[:3], "...")
	}
	return subtleStyle.Render(strings.Join(lines, "\n"))
}

func (m model) linkPanel(width int) string {
	local := m.payload.Local
	remote := m.payload.Remote
	lines := []string{titleStyle.Render(" links ")}
	lines = append(lines,
		fmt.Sprintf("local      %s / %s", local.Host.Platform, local.Host.Hostname),
		fmt.Sprintf("tmux       %s sessions", tmuxSessionCount(local.Health.Tmux.Stdout)),
	)
	if remote != nil {
		lines = append(lines,
			fmt.Sprintf("remote     %s", valueOr(remote.Connection["remote"], "unknown")),
			fmt.Sprintf("transport  %s", valueOr(remote.Connection["transport"], "unknown")),
			fmt.Sprintf("status     %s", stateBadge(commandStatus(remote.Raw), fmt.Sprintf("%v", remoteOK(remote)))),
		)
		if remoteService, ok := remote.Parsed["linux_bridge_service"]; ok {
			lines = append(lines, fmt.Sprintf("repair    %s", serviceSummary(remoteService)))
		}
	} else if m.noRemote {
		lines = append(lines, "remote     disabled")
	}
	return panelStyle.Width(width).Render(strings.Join(lines, "\n"))
}

func (m model) score() int {
	score := 100
	local := m.payload.Local
	if !commandOK(local.Health.MeshStatus) {
		score -= 25
	}
	for _, row := range m.clusterRows() {
		switch connectionLevel(row.Connection) {
		case "fail":
			score -= 20
		case "warn":
			score -= 8
		}
		if strings.Contains(strings.ToLower(row.Service), "inactive") || strings.Contains(strings.ToLower(row.Service), "unknown") {
			score -= 8
		}
		if row.RepoDirty > 0 {
			score -= 5
		}
	}
	if score < 0 {
		return 0
	}
	return score
}

func scoreLevel(score int) string {
	if score >= 85 {
		return "ok"
	}
	if score >= 65 {
		return "warn"
	}
	return "fail"
}

func (m model) commandCenter(width int) string {
	score := m.score()
	local := m.payload.Local
	remote := m.payload.Remote
	meshText := strings.TrimSpace(local.Health.MeshStatus.Stdout)
	meshLevel := commandStatus(local.Health.MeshStatus)
	linuxSocket := socketSeen(meshText, "/tmp/cento-linux.sock")
	macSocket := socketSeen(meshText, "/tmp/cento-mac.sock")
	remoteState := "disabled"
	if remote != nil {
		remoteState = fmt.Sprintf("%v via %s", remoteOK(remote), valueOr(remote.Connection["transport"], "unknown"))
	}
	lines := []string{
		titleStyle.Render(" command center "),
		fmt.Sprintf("health     %s", stateBadge(scoreLevel(score), fmt.Sprintf("%d%%", score))),
		fmt.Sprintf("local      %s / %s", local.Host.Platform, local.Host.Hostname),
		fmt.Sprintf("remote     %s", remoteState),
		fmt.Sprintf("mesh       %s linux=%t mac=%t", stateBadge(meshLevel, commandStatus(local.Health.MeshStatus)), linuxSocket, macSocket),
		fmt.Sprintf("updated    %s", m.updatedAt.Format("15:04:05")),
	}
	return panelStyle.Width(width).Render(strings.Join(lines, "\n"))
}

func (m model) actionPanel(width int) string {
	lines := []string{
		titleStyle.Render(" actions "),
		"r  refresh health",
		"s  run git drift",
		"h  heal bridges",
		"q  quit",
	}
	if m.actionOutput != "" {
		lines = append(lines, "", subtleStyle.Render("last "+m.action+":"))
		lines = append(lines, wrapDetail(m.actionOutput, width-4))
	}
	return panelStyle.Width(width).Render(strings.Join(lines, "\n"))
}

func (m model) attentionPanel(width int) string {
	var items []string
	local := m.payload.Local
	if !commandOK(local.Health.MeshStatus) {
		items = append(items, badStyle.Render("mesh unavailable: ")+firstLine(local.Health.MeshStatus.Stderr))
	}
	for _, row := range m.clusterRows() {
		if connectionLevel(row.Connection) == "fail" {
			items = append(items, badStyle.Render(row.Name+" offline: ")+row.Platform)
		}
		if strings.Contains(strings.ToLower(row.Service), "inactive") {
			items = append(items, warnStyle.Render(row.Name+" service inactive: ")+row.Service)
		}
		if row.RepoDirty > 0 {
			items = append(items, warnStyle.Render(row.Name+" repo: ")+fmt.Sprintf("%d dirty files", row.RepoDirty))
		}
		if strings.Contains(strings.ToLower(row.Activity), "executing") {
			items = append(items, blueStyle.Render(row.Name+" active: ")+row.Agent)
		}
	}
	if len(items) == 0 {
		items = append(items, goodStyle.Render("all clear"))
	}
	lines := []string{titleStyle.Render(" attention ")}
	lines = append(lines, items...)
	return panelStyle.Width(width).Render(strings.Join(lines, "\n"))
}

func (m model) repoPanel(width int) string {
	lines := []string{titleStyle.Render(" repos ")}
	for _, row := range m.clusterRows() {
		if row.Platform == "apple watch" {
			continue
		}
		lines = append(lines, fmt.Sprintf("%-6s %s @ %s", row.Platform, repoState(row.Repo), row.RepoHead))
	}
	return panelStyle.Width(width).Render(strings.Join(lines, "\n"))
}

func (m model) View() tea.View {
	if m.payload.GeneratedAt == "" && m.err == nil {
		return tea.NewView(frameStyle.Render("Loading Cento network context..."))
	}
	width := m.width
	if width < 100 {
		width = 100
	}
	panelWidth := (width - 10) / 2
	if panelWidth < 42 {
		panelWidth = 42
	}
	status := "ready"
	if m.loading {
		status = "refreshing"
	}
	if m.err != nil {
		status = badStyle.Render(m.err.Error())
	}
	header := lipgloss.JoinVertical(lipgloss.Left,
		titleStyle.Render(" cento cluster home "),
		subtleStyle.Render("r refresh · s sync check · h heal · q quit · auto-refresh 10s"),
		fmt.Sprintf("state %s", status),
	)
	clusterWidth := (panelWidth * 2) + 4
	sideWidth := panelWidth
	mainWidth := clusterWidth - sideWidth - 2
	if mainWidth < 50 {
		mainWidth = clusterWidth
		sideWidth = clusterWidth
	}
	topLeft := lipgloss.JoinVertical(lipgloss.Left, m.commandCenter(sideWidth), "\n", m.actionPanel(sideWidth))
	topRight := m.attentionPanel(mainWidth)
	top := lipgloss.JoinHorizontal(lipgloss.Top, topLeft, "  ", topRight)
	if mainWidth == clusterWidth {
		top = lipgloss.JoinVertical(lipgloss.Left, topLeft, "\n", topRight)
	}
	nodes := m.clusterPanel(clusterWidth)
	bottom := lipgloss.JoinHorizontal(lipgloss.Top, m.repoPanel(sideWidth), "  ", m.linkPanel(mainWidth))
	if mainWidth == clusterWidth {
		bottom = lipgloss.JoinVertical(lipgloss.Left, m.repoPanel(clusterWidth), "\n", m.linkPanel(clusterWidth))
	}
	return tea.NewView(frameStyle.Render(lipgloss.JoinVertical(lipgloss.Left, header, "\n", top, "\n", nodes, "\n", bottom)))
}

func isTTY() bool {
	stdin, err := os.Stdin.Stat()
	if err != nil {
		return false
	}
	stdout, err := os.Stdout.Stat()
	if err != nil {
		return false
	}
	return (stdin.Mode()&os.ModeCharDevice) != 0 && (stdout.Mode()&os.ModeCharDevice) != 0
}

func printSummary(root string, noRemote bool) error {
	msg := gatherCmd(root, noRemote)()
	loaded, ok := msg.(loadedMsg)
	if !ok {
		return fmt.Errorf("unexpected gather result")
	}
	if loaded.err != nil {
		return loaded.err
	}
	payload := loaded.payload
	summaryModel := model{payload: payload, noRemote: noRemote}
	for _, row := range summaryModel.clusterRows() {
		fmt.Printf("%s / %s / %s / %s\n", row.Name, row.Platform, row.Connection, row.Activity)
	}
	fmt.Printf("mesh / %s / %s\n", commandStatus(payload.Local.Health.MeshStatus), firstLine(payload.Local.Health.MeshStatus.Stdout))
	return nil
}

func main() {
	root := initRoot()
	fs := flag.NewFlagSet("network-tui", flag.ExitOnError)
	noRemote := fs.Bool("no-remote", false, "disable remote SSH checks")
	fs.Parse(os.Args[1:])

	if !isTTY() {
		if err := printSummary(root, *noRemote); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		return
	}

	program := tea.NewProgram(model{root: root, noRemote: *noRemote, loading: true})
	if _, err := program.Run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
