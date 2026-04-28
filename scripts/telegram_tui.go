package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
	"unicode/utf8"

	tea "charm.land/bubbletea/v2"
	"charm.land/lipgloss/v2"
)

const defaultParseMode = "Markdown"

var errQuit = errors.New("quit")

type toolConfig struct {
	SchemaVersion    string `json:"schema_version"`
	UpdatedAt        string `json:"updated_at"`
	BotToken         string `json:"bot_token"`
	DefaultChatID    string `json:"default_chat_id"`
	DefaultParseMode string `json:"default_parse_mode"`
	Notes            string `json:"notes"`
}

type item struct {
	Title       string
	Description string
	Run         func() (string, error)
}

type model struct {
	items        []item
	cursor       int
	output       string
	status       string
	width        int
	height       int
	scroll       int
	quitting     bool
	selectedOnce bool
}

type pathSet struct {
	root       string
	configPath string
	docsPath   string
	reportDir  string
}

var (
	appPaths pathSet

	frameStyle = lipgloss.NewStyle().Padding(1, 2)
	titleStyle = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#F5E7D0")).Background(lipgloss.Color("#24505A")).Padding(0, 1)
	subtleStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("#7F8C89"))
	menuStyle = lipgloss.NewStyle().Border(lipgloss.RoundedBorder()).BorderForeground(lipgloss.Color("#B88A53")).Padding(1, 1)
	bodyStyle = lipgloss.NewStyle().Border(lipgloss.RoundedBorder()).BorderForeground(lipgloss.Color("#4C6A5C")).Padding(1, 1)
	activeStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("#FFF8ED")).Background(lipgloss.Color("#B86B26")).Padding(0, 1)
	itemStyle = lipgloss.NewStyle().Padding(0, 1)
	statusStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("#24505A")).Bold(true)
)

func nowISO() string {
	return time.Now().Format(time.RFC3339)
}

func defaultConfig() toolConfig {
	return toolConfig{
		SchemaVersion:    "1.0",
		UpdatedAt:        nowISO(),
		BotToken:         "",
		DefaultChatID:    "",
		DefaultParseMode: defaultParseMode,
		Notes:            "Telegram actions and CRM integration are intentionally scaffolded first.",
	}
}

func initPaths() (pathSet, error) {
	root := os.Getenv("CENTO_ROOT_DIR")
	if root == "" {
		cwd, err := os.Getwd()
		if err == nil {
			candidate := filepath.Clean(cwd)
			if _, statErr := os.Stat(filepath.Join(candidate, "docs", "telegram-tui.md")); statErr == nil {
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
		home, homeErr := os.UserHomeDir()
		if homeErr != nil {
			return pathSet{}, homeErr
		}
		configHome = filepath.Join(home, ".config")
	}
	return pathSet{
		root:       root,
		configPath: filepath.Join(configHome, "cento", "telegram.json"),
		docsPath:   filepath.Join(root, "docs", "telegram-tui.md"),
		reportDir:  filepath.Join(root, "workspace", "runs", "telegram-tui"),
	}, nil
}

func readConfig() toolConfig {
	cfg := defaultConfig()
	data, err := os.ReadFile(appPaths.configPath)
	if err != nil {
		return cfg
	}
	var parsed toolConfig
	if err := json.Unmarshal(data, &parsed); err != nil {
		return cfg
	}
	if parsed.SchemaVersion != "" {
		cfg.SchemaVersion = parsed.SchemaVersion
	}
	if parsed.UpdatedAt != "" {
		cfg.UpdatedAt = parsed.UpdatedAt
	}
	if parsed.BotToken != "" {
		cfg.BotToken = parsed.BotToken
	}
	if parsed.DefaultChatID != "" {
		cfg.DefaultChatID = parsed.DefaultChatID
	}
	if parsed.DefaultParseMode != "" {
		cfg.DefaultParseMode = parsed.DefaultParseMode
	}
	if parsed.Notes != "" {
		cfg.Notes = parsed.Notes
	}
	return cfg
}

func writeConfig(cfg toolConfig) error {
	cfg.UpdatedAt = nowISO()
	if err := os.MkdirAll(filepath.Dir(appPaths.configPath), 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(appPaths.configPath, append(data, '\n'), 0o644)
}

func ensureDocs() (string, error) {
	data, err := os.ReadFile(appPaths.docsPath)
	if err != nil {
		return "", err
	}
	return string(data), nil
}

func writePlanReport() (string, error) {
	cfg := readConfig()
	if err := os.MkdirAll(appPaths.reportDir, 0o755); err != nil {
		return "", err
	}
	path := filepath.Join(appPaths.reportDir, fmt.Sprintf("telegram-plan-%s.md", time.Now().Format("20060102-150405")))
	lines := []string{
		"# Telegram Tool Plan",
		"",
		fmt.Sprintf("- recorded_at: `%s`", nowISO()),
		fmt.Sprintf("- config_path: `%s`", appPaths.configPath),
		fmt.Sprintf("- bot_token_configured: `%t`", cfg.BotToken != ""),
		fmt.Sprintf("- default_chat_id_configured: `%t`", cfg.DefaultChatID != ""),
		"",
		"## Registered command surface",
		"",
		"- `cento tui` launches the Bubble Tea TUI.",
		"- `cento tui status` prints scaffold status.",
		"- `cento tui config` manages local Telegram defaults.",
		"- `cento crm integration` is the registered CRM placeholder path.",
		"",
		"## Deferred implementation items",
		"",
		"- Send Telegram messages from a configured bot token.",
		"- Read and format recent bot updates.",
		"- Bridge CRM events into Telegram notifications.",
		"- Add richer chat routing and template-based message actions.",
		"",
	}
	if err := os.WriteFile(path, []byte(strings.Join(lines, "\n")), 0o644); err != nil {
		return "", err
	}
	return path, nil
}

func statusText() string {
	cfg := readConfig()
	return strings.Join([]string{
		"Telegram TUI status",
		fmt.Sprintf("config_path: %s", appPaths.configPath),
		fmt.Sprintf("bot_token_configured: %s", yesNo(cfg.BotToken != "")),
		fmt.Sprintf("default_chat_id_configured: %s", yesNo(cfg.DefaultChatID != "")),
		fmt.Sprintf("default_parse_mode: %s", cfg.DefaultParseMode),
		"current_scope: Bubble Tea scaffold only",
		"available_commands: cento tui, cento tui status, cento tui config, cento tui docs, cento tui plan",
		"crm_integration_status: placeholder registered under cento crm integration",
	}, "\n")
}

func yesNo(value bool) string {
	if value {
		return "yes"
	}
	return "no"
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

func newModel() model {
	items := []item{
		{
			Title:       "Status",
			Description: "Show current scaffold status and saved config summary.",
			Run: func() (string, error) {
				return statusText(), nil
			},
		},
		{
			Title:       "Docs",
			Description: "Show Telegram tool documentation from the repo docs folder.",
			Run: func() (string, error) {
				return ensureDocs()
			},
		},
		{
			Title:       "Config path",
			Description: "Show the local config file path used by the Telegram tool.",
			Run: func() (string, error) {
				return appPaths.configPath, nil
			},
		},
		{
			Title:       "Config JSON",
			Description: "Render the current local Telegram config as JSON.",
			Run: func() (string, error) {
				data, err := json.MarshalIndent(readConfig(), "", "  ")
				if err != nil {
					return "", err
				}
				return string(data), nil
			},
		},
		{
			Title:       "Write plan report",
			Description: "Write a future-work plan report under workspace/runs/telegram-tui/.",
			Run: func() (string, error) {
				path, err := writePlanReport()
				if err != nil {
					return "", err
				}
				return fmt.Sprintf("Plan report written:\n%s", path), nil
			},
		},
		{
			Title:       "Quit",
			Description: "Exit the Telegram TUI.",
			Run: func() (string, error) {
				return "Goodbye.", errQuit
			},
		},
	}
	return model{
		items:  items,
		output: "Bubble Tea Telegram TUI for cento. Use arrow keys or j/k to move, enter to run, pgup/pgdn to scroll details, and q to quit.",
		status: "Ready.",
	}
}

func (m model) Init() tea.Cmd {
	return nil
}

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
			if m.cursor < len(m.items)-1 {
				m.cursor++
				m.scroll = 0
			}
		case "pgdown", "f":
			m.scroll += detailHeight(m.height) - 2
		case "pgup", "b":
			m.scroll -= detailHeight(m.height) - 2
		case "enter", "space":
			result, err := m.items[m.cursor].Run()
			if err != nil {
				if errors.Is(err, errQuit) {
					m.quitting = true
					m.output = result
					return m, tea.Quit
				}
				m.status = fmt.Sprintf("Action failed: %v", err)
				m.output = result
				return m, nil
			}
			m.selectedOnce = true
			m.output = result
			m.status = fmt.Sprintf("Ran: %s", m.items[m.cursor].Title)
			m.scroll = 0
		}
		if m.scroll < 0 {
			m.scroll = 0
		}
	}
	return m, nil
}

func detailHeight(total int) int {
	if total <= 18 {
		return 8
	}
	return total - 14
}

func (m model) View() tea.View {
	if m.quitting {
		return tea.NewView("\n  Telegram TUI closed.\n")
	}

	menuWidth := 36
	if m.width > 0 && m.width < 92 {
		menuWidth = m.width - 10
		if menuWidth < 24 {
			menuWidth = 24
		}
	}
	bodyWidth := 76
	if m.width > 0 {
		bodyWidth = m.width - menuWidth - 12
		if bodyWidth < 30 {
			bodyWidth = 30
		}
	}

	var menuLines []string
	for idx, option := range m.items {
		line := option.Title + "\n" + subtleStyle.Render(option.Description)
		if idx == m.cursor {
			menuLines = append(menuLines, activeStyle.Width(menuWidth-6).Render(line))
		} else {
			menuLines = append(menuLines, itemStyle.Width(menuWidth-6).Render(line))
		}
	}
	menuBlock := menuStyle.Width(menuWidth).Render(strings.Join(menuLines, "\n\n"))

	detailLines := wrapText(m.output, bodyWidth-6)
	visibleHeight := detailHeight(m.height)
	if visibleHeight < 8 {
		visibleHeight = 8
	}
	if m.scroll > len(detailLines)-1 {
		m.scroll = max(0, len(detailLines)-1)
	}
	end := min(len(detailLines), m.scroll+visibleHeight)
	visible := strings.Join(detailLines[m.scroll:end], "\n")
	detailHeader := titleStyle.Render(" Telegram / Bubble Tea / cento ")
	footer := subtleStyle.Render(fmt.Sprintf("scroll %d-%d of %d  •  q quit  •  enter run", min(m.scroll+1, len(detailLines)), end, len(detailLines)))
	bodyBlock := bodyStyle.Width(bodyWidth).Render(detailHeader + "\n\n" + visible + "\n\n" + footer)

	header := lipgloss.JoinVertical(lipgloss.Left,
		titleStyle.Render(" cento tui "),
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

func runInteractive() error {
	if !isTTY() {
		fmt.Println(statusText())
		return nil
	}
	program := tea.NewProgram(newModel())
	_, err := program.Run()
	return err
}

func isTTY() bool {
	info, err := os.Stdin.Stat()
	if err != nil {
		return false
	}
	return (info.Mode() & os.ModeCharDevice) != 0
}

func runStatus() error {
	fmt.Println(statusText())
	return nil
}

func runDocs() error {
	text, err := ensureDocs()
	if err != nil {
		return err
	}
	fmt.Print(text)
	return nil
}

func runPlan() error {
	path, err := writePlanReport()
	if err != nil {
		return err
	}
	fmt.Println(path)
	return nil
}

func runConfig(args []string) error {
	fs := flag.NewFlagSet("config", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	showPath := fs.Bool("path", false, "print config path")
	showJSON := fs.Bool("show", false, "print config json")
	botToken := fs.String("bot-token", "", "save bot token")
	chatID := fs.String("chat-id", "", "save default chat id")
	parseMode := fs.String("parse-mode", "", "save default parse mode")
	notes := fs.String("notes", "", "save notes")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if *showPath {
		fmt.Println(appPaths.configPath)
		return nil
	}
	cfg := readConfig()
	changed := false
	if fs.Lookup("bot-token").Value.String() != "" {
		cfg.BotToken = *botToken
		changed = true
	}
	if fs.Lookup("chat-id").Value.String() != "" {
		cfg.DefaultChatID = *chatID
		changed = true
	}
	if fs.Lookup("parse-mode").Value.String() != "" {
		cfg.DefaultParseMode = *parseMode
		changed = true
	}
	if fs.Lookup("notes").Value.String() != "" {
		cfg.Notes = *notes
		changed = true
	}
	if changed {
		if err := writeConfig(cfg); err != nil {
			return err
		}
		fmt.Printf("Saved Telegram config to %s\n", appPaths.configPath)
		return nil
	}
	if *showJSON || !changed {
		data, err := json.MarshalIndent(cfg, "", "  ")
		if err != nil {
			return err
		}
		fmt.Println(string(data))
	}
	return nil
}

func main() {
	var err error
	appPaths, err = initPaths()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	args := os.Args[1:]
	if len(args) == 0 {
		err = runInteractive()
	} else {
		switch args[0] {
		case "status":
			err = runStatus()
		case "docs":
			err = runDocs()
		case "plan":
			err = runPlan()
		case "config":
			err = runConfig(args[1:])
		default:
			err = fmt.Errorf("unknown command: %s", args[0])
		}
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
