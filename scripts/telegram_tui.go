package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
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

type telegramAPIResponse struct {
	OK          bool             `json:"ok"`
	Description string           `json:"description"`
	Result      []telegramUpdate `json:"result"`
}

type telegramSendResponse struct {
	OK          bool            `json:"ok"`
	Description string          `json:"description"`
	Result      telegramMessage `json:"result"`
}

type telegramUpdate struct {
	UpdateID    int              `json:"update_id"`
	Message     *telegramMessage `json:"message"`
	ChannelPost *telegramMessage `json:"channel_post"`
}

type telegramMessage struct {
	MessageID int          `json:"message_id"`
	Date      int64        `json:"date"`
	Text      string       `json:"text"`
	Caption   string       `json:"caption"`
	Chat      telegramChat `json:"chat"`
	From      telegramUser `json:"from"`
}

type telegramChat struct {
	ID       int64  `json:"id"`
	Type     string `json:"type"`
	Title    string `json:"title"`
	Username string `json:"username"`
	First    string `json:"first_name"`
	Last     string `json:"last_name"`
}

type telegramUser struct {
	ID        int64  `json:"id"`
	Username  string `json:"username"`
	FirstName string `json:"first_name"`
	LastName  string `json:"last_name"`
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

	frameStyle  = lipgloss.NewStyle().Padding(1, 2)
	titleStyle  = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#F5E7D0")).Background(lipgloss.Color("#24505A")).Padding(0, 1)
	subtleStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("#7F8C89"))
	menuStyle   = lipgloss.NewStyle().Border(lipgloss.RoundedBorder()).BorderForeground(lipgloss.Color("#B88A53")).Padding(1, 1)
	bodyStyle   = lipgloss.NewStyle().Border(lipgloss.RoundedBorder()).BorderForeground(lipgloss.Color("#4C6A5C")).Padding(1, 1)
	activeStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("#FFF8ED")).Background(lipgloss.Color("#B86B26")).Padding(0, 1)
	itemStyle   = lipgloss.NewStyle().Padding(0, 1)
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
		"- `cento tg` launches the Bubble Tea TUI.",
		"- `cento tg status` prints scaffold status.",
		"- `cento tg config` manages local Telegram defaults.",
		"- `cento tg history` reads recent bot-visible conversation updates.",
		"- `cento crm integration` is the registered CRM placeholder path.",
		"",
		"## Deferred implementation items",
		"",
		"- Send Telegram messages from a configured bot token.",
		"- Expand history capture beyond bot-visible updates if MTProto/user auth is added later.",
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
		"current_scope: Bubble Tea UI, bot message posting, and bot-visible history",
		"available_commands: cento tg, cento tg status, cento tg config, cento tg post, cento tg history, cento tg docs, cento tg plan",
		"crm_integration_status: placeholder registered under cento crm integration",
	}, "\n")
}

func yesNo(value bool) string {
	if value {
		return "yes"
	}
	return "no"
}

func displayName(firstName, lastName, username, fallback string) string {
	parts := strings.TrimSpace(strings.Join([]string{firstName, lastName}, " "))
	if parts != "" {
		return parts
	}
	if username != "" {
		return "@" + username
	}
	return fallback
}

func chatName(chat telegramChat) string {
	return displayName(chat.First, chat.Last, chat.Username, fmt.Sprintf("%d", chat.ID))
}

func messageText(message *telegramMessage) string {
	if message == nil {
		return ""
	}
	if strings.TrimSpace(message.Text) != "" {
		return strings.TrimSpace(message.Text)
	}
	if strings.TrimSpace(message.Caption) != "" {
		return strings.TrimSpace(message.Caption)
	}
	return "[non-text message]"
}

func updateMessage(update telegramUpdate) *telegramMessage {
	if update.Message != nil {
		return update.Message
	}
	return update.ChannelPost
}

func fetchTelegramUpdates(cfg toolConfig, limit int) ([]telegramUpdate, error) {
	if cfg.BotToken == "" {
		return nil, fmt.Errorf("bot token is not configured; run `cento tg config --bot-token ...`")
	}
	if limit < 1 {
		limit = 20
	}
	if limit > 100 {
		limit = 100
	}
	endpoint := fmt.Sprintf("https://api.telegram.org/bot%s/getUpdates", cfg.BotToken)
	values := url.Values{}
	values.Set("limit", strconv.Itoa(limit))
	values.Set("allowed_updates", `["message","channel_post"]`)
	requestURL := endpoint + "?" + values.Encode()
	client := http.Client{Timeout: 15 * time.Second}
	resp, err := client.Get(requestURL)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	var payload telegramAPIResponse
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		return nil, err
	}
	if !payload.OK {
		if payload.Description == "" {
			payload.Description = fmt.Sprintf("Telegram API returned HTTP %s", resp.Status)
		}
		return nil, errors.New(payload.Description)
	}
	return payload.Result, nil
}

func sendTelegramMessage(cfg toolConfig, chatID string, text string, parseMode string) (telegramMessage, error) {
	if cfg.BotToken == "" {
		return telegramMessage{}, fmt.Errorf("bot token is not configured; run `cento tg config --bot-token ...`")
	}
	if strings.TrimSpace(chatID) == "" {
		return telegramMessage{}, fmt.Errorf("chat id is not configured; pass --chat-id or run `cento tg config --chat-id ...`")
	}
	if strings.TrimSpace(text) == "" {
		return telegramMessage{}, fmt.Errorf("message text cannot be empty")
	}
	if strings.TrimSpace(parseMode) == "" {
		parseMode = cfg.DefaultParseMode
	}
	endpoint := fmt.Sprintf("https://api.telegram.org/bot%s/sendMessage", cfg.BotToken)
	values := url.Values{}
	values.Set("chat_id", chatID)
	values.Set("text", text)
	if strings.TrimSpace(parseMode) != "" {
		values.Set("parse_mode", parseMode)
	}
	client := http.Client{Timeout: 15 * time.Second}
	resp, err := client.PostForm(endpoint, values)
	if err != nil {
		return telegramMessage{}, err
	}
	defer resp.Body.Close()
	var payload telegramSendResponse
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		return telegramMessage{}, err
	}
	if !payload.OK {
		if payload.Description == "" {
			payload.Description = fmt.Sprintf("Telegram API returned HTTP %s", resp.Status)
		}
		return telegramMessage{}, errors.New(payload.Description)
	}
	return payload.Result, nil
}

func formatHistory(updates []telegramUpdate, chatID string, limit int, save bool) (string, error) {
	var lines []string
	lines = append(lines, "# Telegram Conversation History")
	lines = append(lines, "")
	lines = append(lines, fmt.Sprintf("- recorded_at: `%s`", nowISO()))
	lines = append(lines, fmt.Sprintf("- source: `getUpdates`"))
	if chatID != "" {
		lines = append(lines, fmt.Sprintf("- chat_filter: `%s`", chatID))
	}
	lines = append(lines, fmt.Sprintf("- requested_limit: `%d`", limit))
	lines = append(lines, "")
	lines = append(lines, "## Messages")
	lines = append(lines, "")

	count := 0
	for _, update := range updates {
		message := updateMessage(update)
		if message == nil {
			continue
		}
		if chatID != "" && strconv.FormatInt(message.Chat.ID, 10) != chatID {
			continue
		}
		count++
		when := time.Unix(message.Date, 0).Format(time.RFC3339)
		author := displayName(message.From.FirstName, message.From.LastName, message.From.Username, "unknown")
		lines = append(lines, fmt.Sprintf("### %s | %s | %s", when, chatName(message.Chat), author))
		lines = append(lines, "")
		lines = append(lines, messageText(message))
		lines = append(lines, "")
	}
	if count == 0 {
		lines = append(lines, "No bot-visible messages matched the current filters.")
		lines = append(lines, "")
	}
	lines = append(lines, "> Telegram bots can only read bot-visible updates, not arbitrary personal account history.")
	output := strings.Join(lines, "\n")
	if !save {
		return output, nil
	}
	if err := os.MkdirAll(appPaths.reportDir, 0o755); err != nil {
		return "", err
	}
	path := filepath.Join(appPaths.reportDir, fmt.Sprintf("telegram-history-%s.md", time.Now().Format("20060102-150405")))
	if err := os.WriteFile(path, []byte(output+"\n"), 0o644); err != nil {
		return "", err
	}
	return output + "\n\nSaved report: " + path, nil
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
			Title:       "Conversation history",
			Description: "Read recent bot-visible Telegram updates and save a local report.",
			Run: func() (string, error) {
				cfg := readConfig()
				updates, err := fetchTelegramUpdates(cfg, 20)
				if err != nil {
					return "", err
				}
				return formatHistory(updates, cfg.DefaultChatID, 20, true)
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
		titleStyle.Render(" cento tg "),
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

func runHistory(args []string) error {
	fs := flag.NewFlagSet("history", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	limit := fs.Int("limit", 20, "maximum updates to read, 1-100")
	chatID := fs.String("chat-id", "", "filter to one chat id; defaults to configured chat id")
	jsonOut := fs.Bool("json", false, "print raw Telegram updates as JSON")
	noSave := fs.Bool("no-save", false, "do not write a Markdown report")
	if err := fs.Parse(args); err != nil {
		return err
	}
	cfg := readConfig()
	filterChatID := *chatID
	if filterChatID == "" {
		filterChatID = cfg.DefaultChatID
	}
	updates, err := fetchTelegramUpdates(cfg, *limit)
	if err != nil {
		return err
	}
	if *jsonOut {
		data, err := json.MarshalIndent(updates, "", "  ")
		if err != nil {
			return err
		}
		fmt.Println(string(data))
		return nil
	}
	output, err := formatHistory(updates, filterChatID, *limit, !*noSave)
	if err != nil {
		return err
	}
	fmt.Println(output)
	return nil
}

func runPost(args []string) error {
	fs := flag.NewFlagSet("post", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	text := fs.String("text", "", "message text to send")
	chatID := fs.String("chat-id", "", "target chat id; defaults to configured chat id")
	parseMode := fs.String("parse-mode", "", "Telegram parse mode; defaults to configured parse mode")
	if err := fs.Parse(args); err != nil {
		return err
	}
	messageText := strings.TrimSpace(*text)
	if messageText == "" {
		messageText = strings.TrimSpace(strings.Join(fs.Args(), " "))
	}
	cfg := readConfig()
	targetChatID := *chatID
	if targetChatID == "" {
		targetChatID = cfg.DefaultChatID
	}
	targetParseMode := *parseMode
	if targetParseMode == "" {
		targetParseMode = cfg.DefaultParseMode
	}
	message, err := sendTelegramMessage(cfg, targetChatID, messageText, targetParseMode)
	if err != nil {
		return err
	}
	fmt.Printf("sent chat=%d message_id=%d\n", message.Chat.ID, message.MessageID)
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
		case "history":
			err = runHistory(args[1:])
		case "post":
			err = runPost(args[1:])
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
