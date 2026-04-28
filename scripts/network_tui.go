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

type localInfo struct {
	Host     hostInfo          `json:"host"`
	Repo     repoInfo          `json:"repo"`
	Commands map[string]string `json:"commands"`
	Config   configInfo        `json:"config"`
	Tools    toolsInfo         `json:"tools"`
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

type model struct {
	root      string
	noRemote  bool
	payload   contextPayload
	err       error
	loading   bool
	width     int
	height    int
	updatedAt time.Time
}

var (
	frameStyle  = lipgloss.NewStyle().Padding(1, 2)
	titleStyle  = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#F7F1E8")).Background(lipgloss.Color("#1C4E5E")).Padding(0, 1)
	panelStyle  = lipgloss.NewStyle().Border(lipgloss.RoundedBorder()).BorderForeground(lipgloss.Color("#496259")).Padding(1, 2)
	goodStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("#2F7D4F")).Bold(true)
	warnStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("#B1763A")).Bold(true)
	badStyle    = lipgloss.NewStyle().Foreground(lipgloss.Color("#B6423C")).Bold(true)
	subtleStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("#67767B"))
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
	return tea.Tick(30*time.Second, func(t time.Time) tea.Msg {
		return tickMsg(t)
	})
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
	}
	return m, nil
}

func statusLabel(ok bool, text string) string {
	if ok {
		return goodStyle.Render("ok") + " " + text
	}
	return badStyle.Render("fail") + " " + text
}

func warnLabel(ok bool, text string) string {
	if ok {
		return goodStyle.Render("ok") + " " + text
	}
	return warnStyle.Render("warn") + " " + text
}

func firstLine(text string) string {
	text = strings.TrimSpace(text)
	if text == "" {
		return "unknown"
	}
	return strings.Split(text, "\n")[0]
}

func commandLines(commands map[string]string) []string {
	keys := make([]string, 0, len(commands))
	for key := range commands {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	lines := make([]string, 0, len(keys))
	for _, key := range keys {
		value := commands[key]
		if value == "" {
			value = "missing"
		}
		lines = append(lines, fmt.Sprintf("%-8s %s", key, value))
	}
	return lines
}

func (m model) localPanel(width int) string {
	local := m.payload.Local
	lines := []string{
		titleStyle.Render(" local node "),
		fmt.Sprintf("host      %s", local.Host.Hostname),
		fmt.Sprintf("platform  %s", local.Host.Platform),
		fmt.Sprintf("user      %s", local.Host.User),
		fmt.Sprintf("repo      %s", local.Repo.Root),
		fmt.Sprintf("git       %s", firstLine(local.Repo.GitStatus.Stdout)),
		warnLabel(local.Config.EnvMCPExists, ".env.mcp"),
		warnLabel(local.Config.GitHubTokenPresent, "github token"),
	}
	return panelStyle.Width(width).Render(strings.Join(lines, "\n"))
}

func (m model) remotePanel(width int) string {
	lines := []string{titleStyle.Render(" remote node ")}
	if m.noRemote {
		lines = append(lines, subtleStyle.Render("remote checks disabled"))
		return panelStyle.Width(width).Render(strings.Join(lines, "\n"))
	}
	if m.payload.Remote == nil {
		lines = append(lines, warnStyle.Render("no remote data yet"))
		return panelStyle.Width(width).Render(strings.Join(lines, "\n"))
	}
	remote := m.payload.Remote
	ok := remote.Raw.ReturnCode != nil && *remote.Raw.ReturnCode == 0
	lines = append(lines,
		statusLabel(ok, fmt.Sprintf("%s via %s", remote.Connection["remote"], remote.Connection["jump"])),
		fmt.Sprintf("host      %s", valueOr(remote.Parsed["hostname"], "unknown")),
		fmt.Sprintf("user      %s", valueOr(remote.Parsed["user"], "unknown")),
		fmt.Sprintf("repo      %s", valueOr(remote.Parsed["repo"], "unknown")),
		fmt.Sprintf("git       %s", valueOr(remote.Parsed["git_status"], "unknown")),
		fmt.Sprintf("cento     %s", valueOr(remote.Parsed["cento"], "unknown")),
	)
	if !ok && remote.Raw.Stderr != "" {
		lines = append(lines, "", badStyle.Render(firstLine(remote.Raw.Stderr)))
	}
	return panelStyle.Width(width).Render(strings.Join(lines, "\n"))
}

func valueOr(value string, fallback string) string {
	if strings.TrimSpace(value) == "" {
		return fallback
	}
	return value
}

func (m model) toolsPanel(width int) string {
	tools := m.payload.Local.Tools
	lines := []string{
		titleStyle.Render(" platform support "),
		fmt.Sprintf("total       %d", tools.Count),
		fmt.Sprintf("macOS       %d", len(tools.MacOS)),
		fmt.Sprintf("Linux       %d", len(tools.Linux)),
		fmt.Sprintf("both        %d", len(tools.Both)),
		fmt.Sprintf("linux only  %d", len(tools.LinuxOnly)),
		fmt.Sprintf("macOS only  %d", len(tools.MacOSOnly)),
		"",
		"linux only:",
		strings.Join(tools.LinuxOnly, ", "),
	}
	return panelStyle.Width(width).Render(strings.Join(lines, "\n"))
}

func (m model) commandsPanel(width int) string {
	lines := []string{titleStyle.Render(" command paths ")}
	lines = append(lines, commandLines(m.payload.Local.Commands)...)
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
		titleStyle.Render(" cento network monitor "),
		subtleStyle.Render("q quit · r refresh · auto-refresh 30s"),
		fmt.Sprintf("updated %s · %s", m.updatedAt.Format("15:04:05"), status),
	)
	row1 := lipgloss.JoinHorizontal(lipgloss.Top, m.localPanel(panelWidth), "  ", m.remotePanel(panelWidth))
	row2 := lipgloss.JoinHorizontal(lipgloss.Top, m.toolsPanel(panelWidth), "  ", m.commandsPanel(panelWidth))
	return tea.NewView(frameStyle.Render(lipgloss.JoinVertical(lipgloss.Left, header, "\n", row1, "\n", row2)))
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
	fmt.Printf("local: %s %s %s\n", payload.Local.Host.Hostname, payload.Local.Host.Platform, firstLine(payload.Local.Repo.GitStatus.Stdout))
	fmt.Printf("tools: total=%d macos=%d linux=%d both=%d\n", payload.Local.Tools.Count, len(payload.Local.Tools.MacOS), len(payload.Local.Tools.Linux), len(payload.Local.Tools.Both))
	if payload.Remote != nil {
		ok := payload.Remote.Raw.ReturnCode != nil && *payload.Remote.Raw.ReturnCode == 0
		fmt.Printf("remote: ok=%v host=%s repo=%s git=%s\n", ok, payload.Remote.Parsed["hostname"], payload.Remote.Parsed["repo"], payload.Remote.Parsed["git_status"])
	}
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
