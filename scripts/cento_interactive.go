package main

import (
	"bufio"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"unicode/utf8"

	tea "charm.land/bubbletea/v2"
	"charm.land/lipgloss/v2"
)

type commandFlag struct {
	Name    string `json:"name"`
	Summary string `json:"summary"`
	Usage   string `json:"usage"`
}

type commandDoc struct {
	Name     string        `json:"name"`
	Summary  string        `json:"summary"`
	Usage    string        `json:"usage"`
	Flags    []commandFlag `json:"flags"`
	Examples []string      `json:"examples"`
}

type routingDoc struct {
	Name    string `json:"name"`
	Usage   string `json:"usage"`
	Summary string `json:"summary"`
}

type cliDocs struct {
	Name    string       `json:"name"`
	Summary string       `json:"summary"`
	Usage   string       `json:"usage"`
	Notes   []string     `json:"notes"`
	Routing []routingDoc `json:"routing"`
	Commands []commandDoc `json:"commands"`
}

type toolDoc struct {
	ID          string       `json:"id"`
	Name        string       `json:"name"`
	Kind        string       `json:"kind"`
	Entrypoint  string       `json:"entrypoint"`
	Description string       `json:"description"`
	Commands    []string     `json:"commands"`
	Notes       []string     `json:"notes"`
	Subcommands []commandDoc `json:"subcommands"`
}

type toolsRegistry struct {
	Tools []toolDoc `json:"tools"`
}

type entry struct {
	Type     string
	Name     string
	Summary  string
	Usage    string
	Details  []string
	Flags    []commandFlag
	Examples []string
	Run      string
	Section  string
}

type pathSet struct {
	root      string
	docsPath  string
	toolsPath string
	aliasPath string
	centoPath string
}

type model struct {
	entries      []entry
	section      string
	cursor       int
	width        int
	height       int
	scroll       int
	status       string
	selectedRun  string
	quitting     bool
}

var (
	appPaths pathSet
	frameStyle  = lipgloss.NewStyle().Padding(1, 2)
	titleStyle  = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#F7F1E8")).Background(lipgloss.Color("#1C4E5E")).Padding(0, 1)
	subtleStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("#67767B"))
	menuStyle   = lipgloss.NewStyle().Border(lipgloss.RoundedBorder()).BorderForeground(lipgloss.Color("#B1763A")).Padding(1, 1)
	bodyStyle   = lipgloss.NewStyle().Border(lipgloss.RoundedBorder()).BorderForeground(lipgloss.Color("#496259")).Padding(1, 1)
	activeStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("#FFF9F0")).Background(lipgloss.Color("#C0632A")).Padding(0, 1)
	itemStyle   = lipgloss.NewStyle().Padding(0, 1)
	statusStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("#1C4E5E")).Bold(true)
)

func initPaths() (pathSet, error) {
	root := os.Getenv("CENTO_ROOT_DIR")
	if root == "" {
		cwd, err := os.Getwd()
		if err == nil {
			candidate := filepath.Clean(cwd)
			if _, statErr := os.Stat(filepath.Join(candidate, "data", "cento-cli.json")); statErr == nil {
				root = candidate
			}
		}
	}
	if root == "" {
		exe, err := os.Executable()
		if err != nil {
			return pathSet{}, err
		}
		root = filepath.Clean(filepath.Join(filepath.Dir(exe), ".."))
	}
	configHome := os.Getenv("XDG_CONFIG_HOME")
	if configHome == "" {
		home, err := os.UserHomeDir()
		if err != nil {
			return pathSet{}, err
		}
		configHome = filepath.Join(home, ".config")
	}
	return pathSet{
		root:      root,
		docsPath:  filepath.Join(root, "data", "cento-cli.json"),
		toolsPath: filepath.Join(root, "data", "tools.json"),
		aliasPath: filepath.Join(configHome, "cento", "aliases.sh"),
		centoPath: filepath.Join(root, "scripts", "cento.sh"),
	}, nil
}

func loadCLI() (cliDocs, error) {
	var docs cliDocs
	data, err := os.ReadFile(appPaths.docsPath)
	if err != nil {
		return docs, err
	}
	err = json.Unmarshal(data, &docs)
	return docs, err
}

func loadTools() (toolsRegistry, error) {
	var reg toolsRegistry
	data, err := os.ReadFile(appPaths.toolsPath)
	if err != nil {
		return reg, err
	}
	err = json.Unmarshal(data, &reg)
	return reg, err
}

func parseAliases() []entry {
	file, err := os.Open(appPaths.aliasPath)
	if err != nil {
		return nil
	}
	defer file.Close()

	withDesc := regexp.MustCompile(`^cento_alias\s+([^\s]+)\s+--description\s+"([^"]+)"\s+--\s+(.+)$`)
	withoutDesc := regexp.MustCompile(`^cento_alias\s+([^\s]+)\s+--\s+(.+)$`)
	var entries []entry
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") || !strings.HasPrefix(line, "cento_alias ") {
			continue
		}
		if matches := withDesc.FindStringSubmatch(line); matches != nil {
			entries = append(entries, entry{
				Type:    "alias",
				Name:    matches[1],
				Summary: matches[2],
				Usage:   "cento " + matches[1],
				Details: []string{"Configured command: " + matches[3]},
				Examples: []string{"cento " + matches[1]},
				Run:     "cento " + matches[1],
				Section: "aliases",
			})
			continue
		}
		if matches := withoutDesc.FindStringSubmatch(line); matches != nil {
			entries = append(entries, entry{
				Type:    "alias",
				Name:    matches[1],
				Summary: "User alias",
				Usage:   "cento " + matches[1],
				Details: []string{"Configured command: " + matches[2]},
				Examples: []string{"cento " + matches[1]},
				Run:     "cento " + matches[1],
				Section: "aliases",
			})
		}
	}
	sort.Slice(entries, func(i, j int) bool { return entries[i].Name < entries[j].Name })
	return entries
}

func buildEntries() ([]entry, error) {
	cli, err := loadCLI()
	if err != nil {
		return nil, err
	}
	reg, err := loadTools()
	if err != nil {
		return nil, err
	}
	var entries []entry
	for _, cmd := range cli.Commands {
		entries = append(entries, entry{
			Type:     "builtin",
			Name:     cmd.Name,
			Summary:  cmd.Summary,
			Usage:    cmd.Usage,
			Flags:    cmd.Flags,
			Examples: cmd.Examples,
			Run:      cmd.Usage,
			Section:  "builtins",
		})
	}
	for _, tool := range reg.Tools {
		details := []string{
			"Name: " + tool.Name,
			"Kind: " + tool.Kind,
			"Entrypoint: " + tool.Entrypoint,
		}
		for _, note := range tool.Notes {
			details = append(details, "Note: "+note)
		}
		entries = append(entries, entry{
			Type:     "tool",
			Name:     tool.ID,
			Summary:  tool.Description,
			Usage:    "cento " + tool.ID,
			Details:  details,
			Examples: tool.Commands,
			Run:      "cento " + tool.ID,
			Section:  "tools",
		})
	}
	entries = append(entries, parseAliases()...)
	return entries, nil
}

func filterEntries(entries []entry, section string) []entry {
	if section == "all" || section == "" {
		return entries
	}
	var out []entry
	for _, e := range entries {
		if e.Section == section {
			out = append(out, e)
		}
	}
	return out
}

func wrapText(input string, width int) []string {
	if width < 20 {
		width = 20
	}
	var out []string
	for _, rawLine := range strings.Split(input, "\n") {
		if rawLine == "" {
			out = append(out, "")
			continue
		}
		words := strings.Fields(rawLine)
		if len(words) == 0 {
			out = append(out, "")
			continue
		}
		current := words[0]
		for _, word := range words[1:] {
			candidate := current + " " + word
			if utf8.RuneCountInString(candidate) <= width {
				current = candidate
				continue
			}
			out = append(out, current)
			current = word
		}
		out = append(out, current)
	}
	return out
}

func detailHeight(total int) int {
	if total <= 18 {
		return 8
	}
	return total - 14
}

func (m model) currentEntry() entry {
	if len(m.entries) == 0 {
		return entry{}
	}
	if m.cursor < 0 {
		m.cursor = 0
	}
	if m.cursor >= len(m.entries) {
		m.cursor = len(m.entries) - 1
	}
	return m.entries[m.cursor]
}

func renderEntry(e entry) string {
	lines := []string{
		fmt.Sprintf("%s: %s", e.Type, e.Name),
		"",
		"Summary: " + e.Summary,
		"Usage:   " + e.Usage,
	}
	if len(e.Flags) > 0 {
		lines = append(lines, "", "Flags:")
		for _, flag := range e.Flags {
			lines = append(lines, "  "+flag.Name)
			lines = append(lines, "    "+flag.Summary)
			if flag.Usage != "" {
				lines = append(lines, "    usage: "+flag.Usage)
			}
		}
	}
	if len(e.Details) > 0 {
		lines = append(lines, "", "Details:")
		for _, detail := range e.Details {
			lines = append(lines, "  - "+detail)
		}
	}
	if len(e.Examples) > 0 {
		lines = append(lines, "", "Examples:")
		for _, ex := range e.Examples {
			lines = append(lines, "  "+ex)
		}
	}
	return strings.Join(lines, "\n")
}

func newModel(section string, entries []entry) model {
	section = strings.TrimSpace(section)
	if section == "" {
		section = "all"
	}
	entries = filterEntries(entries, section)
	status := fmt.Sprintf("Section: %s · %d entries", section, len(entries))
	if len(entries) == 0 {
		status = fmt.Sprintf("Section: %s · no entries", section)
	}
	return model{entries: entries, section: section, status: status}
}

func (m model) Init() tea.Cmd { return nil }

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		return m, nil
	case tea.KeyPressMsg:
		switch msg.String() {
		case "ctrl+c", "q":
			m.quitting = true
			return m, tea.Quit
		case "up", "k":
			if m.cursor > 0 {
				m.cursor--
				m.scroll = 0
			}
		case "down", "j":
			if m.cursor < len(m.entries)-1 {
				m.cursor++
				m.scroll = 0
			}
		case "pgdown", "f":
			m.scroll += detailHeight(m.height) - 2
		case "pgup", "b":
			m.scroll -= detailHeight(m.height) - 2
		case "r":
			entry := m.currentEntry()
			if entry.Run != "" {
				m.selectedRun = entry.Run
				m.status = "Running: " + entry.Run
				return m, tea.Quit
			}
		case "a":
			m.section = "all"
		case "1":
			m.section = "builtins"
		case "2":
			m.section = "tools"
		case "3":
			m.section = "aliases"
		}
		if msg.String() == "a" || msg.String() == "1" || msg.String() == "2" || msg.String() == "3" {
			entries, err := buildEntries()
			if err != nil {
				m.status = fmt.Sprintf("Reload failed: %v", err)
				return m, nil
			}
			m.entries = filterEntries(entries, m.section)
			m.cursor = 0
			m.scroll = 0
			m.status = fmt.Sprintf("Section: %s · %d entries", m.section, len(m.entries))
		}
		if m.scroll < 0 {
			m.scroll = 0
		}
	}
	return m, nil
}

func (m model) View() tea.View {
	if m.quitting && m.selectedRun == "" {
		return tea.NewView("\n  cento interactive closed.\n")
	}

	menuWidth := 40
	if m.width > 0 && m.width < 100 {
		menuWidth = m.width - 10
		if menuWidth < 24 {
			menuWidth = 24
		}
	}
	bodyWidth := 78
	if m.width > 0 {
		bodyWidth = m.width - menuWidth - 12
		if bodyWidth < 30 {
			bodyWidth = 30
		}
	}

	var menuLines []string
	for idx, option := range m.entries {
		line := option.Name + "\n" + subtleStyle.Render("["+option.Type+"] "+option.Summary)
		if idx == m.cursor {
			menuLines = append(menuLines, activeStyle.Width(menuWidth-6).Render(line))
		} else {
			menuLines = append(menuLines, itemStyle.Width(menuWidth-6).Render(line))
		}
	}
	if len(menuLines) == 0 {
		menuLines = []string{subtleStyle.Render("No entries in this section.")}
	}
	menuBlock := menuStyle.Width(menuWidth).Render(strings.Join(menuLines, "\n\n"))

	detailText := "No entry selected."
	if len(m.entries) > 0 {
		detailText = renderEntry(m.currentEntry())
	}
	detailLines := wrapText(detailText, bodyWidth-6)
	visibleHeight := detailHeight(m.height)
	if visibleHeight < 8 {
		visibleHeight = 8
	}
	if m.scroll > len(detailLines)-1 {
		m.scroll = max(0, len(detailLines)-1)
	}
	end := min(len(detailLines), m.scroll+visibleHeight)
	visible := strings.Join(detailLines[m.scroll:end], "\n")
	detailHeader := titleStyle.Render(" cento interactive / Bubble Tea ")
	footer := subtleStyle.Render(fmt.Sprintf("scroll %d-%d of %d  •  q quit  •  r run  •  1 builtins  2 tools  3 aliases  a all", min(m.scroll+1, len(detailLines)), end, len(detailLines)))
	bodyBlock := bodyStyle.Width(bodyWidth).Render(detailHeader + "\n\n" + visible + "\n\n" + footer)

	header := lipgloss.JoinVertical(lipgloss.Left,
		titleStyle.Render(" cento interactive "),
		subtleStyle.Render("Bubble Tea v2 is the standard for interactive terminal apps in cento."),
		statusStyle.Render(m.status),
	)

	mainRow := lipgloss.JoinHorizontal(lipgloss.Top, menuBlock, "  ", bodyBlock)
	return tea.NewView(frameStyle.Render(lipgloss.JoinVertical(lipgloss.Left, header, "\n", mainRow)))
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
	info, err := os.Stdin.Stat()
	if err != nil {
		return false
	}
	return (info.Mode() & os.ModeCharDevice) != 0
}

func runSelected(command string) error {
	command = strings.TrimSpace(command)
	if command == "" {
		return nil
	}
	if strings.HasPrefix(command, "cento ") {
		command = appPaths.centoPath + command[len("cento"):]
	}
	cmd := exec.Command("bash", "-lc", command)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}

func runInteractive(section string) error {
	entries, err := buildEntries()
	if err != nil {
		return err
	}
	if !isTTY() {
		for _, entry := range filterEntries(entries, section) {
			fmt.Printf("%-7s  %-16s  %s\n", entry.Type, entry.Name, entry.Summary)
		}
		return nil
	}
	program := tea.NewProgram(newModel(section, entries))
	finalModel, err := program.Run()
	if err != nil {
		return err
	}
	m, ok := finalModel.(model)
	if ok && m.selectedRun != "" {
		return runSelected(m.selectedRun)
	}
	return nil
}

func main() {
	app, err := initPaths()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	appPaths = app

	fs := flag.NewFlagSet("cento-interactive", flag.ExitOnError)
	section := fs.String("section", "all", "limit the initial view to all, builtins, tools, or aliases")
	fs.Parse(os.Args[1:])

	if err := runInteractive(*section); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

}
