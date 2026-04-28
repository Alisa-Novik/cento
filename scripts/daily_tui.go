package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
	"unicode/utf8"

	tea "charm.land/bubbletea/v2"
	"charm.land/lipgloss/v2"
)

const schemaVersion = "1.0"

type BriefSection struct {
	Key     string `json:"key"`
	Title   string `json:"title"`
	Content string `json:"content"`
}

type UserDecision struct {
	Choice    string `json:"choice"`
	Note      string `json:"note"`
	CreatedAt string `json:"created_at"`
}

type DailyBrief struct {
	Date      string         `json:"date"`
	Sections  []BriefSection `json:"sections"`
	Decision  UserDecision   `json:"decision"`
	Accepted  bool           `json:"accepted"`
	CreatedAt string         `json:"created_at"`
	UpdatedAt string         `json:"updated_at"`
}

type MiddayCheckIn struct {
	Date              string `json:"date"`
	AlreadyDone       string `json:"already_done"`
	StillMatters      string `json:"still_matters"`
	DropOrMove        string `json:"drop_or_move"`
	Next45MinuteBlock string `json:"next_45_minute_block"`
	CreatedAt         string `json:"created_at"`
	UpdatedAt         string `json:"updated_at"`
}

type EveningWrapUp struct {
	Date                 string `json:"date"`
	Completed            string `json:"completed"`
	Blocked              string `json:"blocked"`
	CarryOver            string `json:"carry_over"`
	ExecutionSummary     string `json:"execution_summary"`
	FirstStepForTomorrow string `json:"first_step_for_tomorrow"`
	CreatedAt            string `json:"created_at"`
	UpdatedAt            string `json:"updated_at"`
}

type DailySettings struct {
	MorningReminder                 string `json:"morning_reminder"`
	MiddayReminder                  string `json:"midday_reminder"`
	EveningReminder                 string `json:"evening_reminder"`
	MotivationalTone                string `json:"motivational_tone"`
	MiddayRecalibrationEnabled      bool   `json:"midday_recalibration_enabled"`
	ShowProcessImprovementQuestions bool   `json:"show_process_improvement_questions"`
}

type DailyRecord struct {
	Date    string        `json:"date"`
	Brief   DailyBrief    `json:"brief"`
	Midday  MiddayCheckIn `json:"midday_check_in"`
	Evening EveningWrapUp `json:"evening_wrap_up"`
}

type ExecutionHistory struct {
	SchemaVersion string        `json:"schema_version"`
	UpdatedAt     string        `json:"updated_at"`
	Settings      DailySettings `json:"settings"`
	Records       []DailyRecord `json:"records"`
}

type BriefGenerator interface {
	Generate(history ExecutionHistory, settings DailySettings, date time.Time) DailyBrief
}

type MockBriefGenerator struct{}

type paths struct {
	root        string
	historyPath string
	docsPath    string
}

type screen int

const (
	screenToday screen = iota
	screenHistory
	screenSettings
)

type focusMode int

const (
	modeNormal focusMode = iota
	modeEditBrief
	modeRewriteBrief
	modeMidday
	modeEvening
	modeSettings
)

type formField struct {
	Label string
	Value string
}

type model struct {
	paths       paths
	history     ExecutionHistory
	today       string
	screen      screen
	mode        focusMode
	cursor      int
	fieldCursor int
	fields      []formField
	status      string
	width       int
	height      int
	scroll      int
	quitting    bool
	generator   BriefGenerator
}

var (
	frameStyle       = lipgloss.NewStyle().Padding(1, 2)
	titleStyle       = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#F8EEDC")).Background(lipgloss.Color("#243C2F")).Padding(0, 1)
	tabStyle         = lipgloss.NewStyle().Foreground(lipgloss.Color("#6D7C72")).Padding(0, 1)
	activeTabStyle   = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#FFF8EA")).Background(lipgloss.Color("#9B542C")).Padding(0, 1)
	panelStyle       = lipgloss.NewStyle().Border(lipgloss.RoundedBorder()).BorderForeground(lipgloss.Color("#456456")).Padding(1, 1)
	hotStyle         = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#C8672F"))
	subtleStyle      = lipgloss.NewStyle().Foreground(lipgloss.Color("#728178"))
	okStyle          = lipgloss.NewStyle().Foreground(lipgloss.Color("#2E7552")).Bold(true)
	warnStyle        = lipgloss.NewStyle().Foreground(lipgloss.Color("#B86A28")).Bold(true)
	fieldStyle       = lipgloss.NewStyle().Padding(0, 1)
	activeFieldStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("#FFF8EA")).Background(lipgloss.Color("#2F604D")).Padding(0, 1)
)

func nowISO() string {
	return time.Now().Format(time.RFC3339)
}

func todayKey() string {
	return time.Now().Format("2006-01-02")
}

func defaultSettings() DailySettings {
	return DailySettings{
		MorningReminder:                 "08:30",
		MiddayReminder:                  "12:30",
		EveningReminder:                 "17:30",
		MotivationalTone:                "direct",
		MiddayRecalibrationEnabled:      true,
		ShowProcessImprovementQuestions: true,
	}
}

func defaultHistory() ExecutionHistory {
	return ExecutionHistory{
		SchemaVersion: schemaVersion,
		UpdatedAt:     nowISO(),
		Settings:      defaultSettings(),
		Records:       []DailyRecord{},
	}
}

func initPaths() (paths, error) {
	root := os.Getenv("CENTO_ROOT_DIR")
	if root == "" {
		cwd, err := os.Getwd()
		if err == nil {
			candidate := filepath.Clean(cwd)
			if _, statErr := os.Stat(filepath.Join(candidate, "data", "tools.json")); statErr == nil {
				root = candidate
			}
		}
	}
	if root == "" {
		exe, err := os.Executable()
		if err != nil {
			return paths{}, err
		}
		root = filepath.Clean(filepath.Join(filepath.Dir(exe), "..", "..", ".."))
	}
	return paths{
		root:        root,
		historyPath: filepath.Join(root, "workspace", "runs", "daily", "history.json"),
		docsPath:    filepath.Join(root, "docs", "daily.md"),
	}, nil
}

func loadHistory(path string) ExecutionHistory {
	history := defaultHistory()
	data, err := os.ReadFile(path)
	if err != nil {
		return history
	}
	var parsed ExecutionHistory
	if err := json.Unmarshal(data, &parsed); err != nil {
		return history
	}
	if parsed.SchemaVersion != "" {
		history.SchemaVersion = parsed.SchemaVersion
	}
	if parsed.UpdatedAt != "" {
		history.UpdatedAt = parsed.UpdatedAt
	}
	if parsed.Settings.MorningReminder != "" {
		history.Settings = parsed.Settings
	}
	if parsed.Records != nil {
		history.Records = parsed.Records
	}
	return history
}

func saveHistory(path string, history ExecutionHistory) error {
	history.SchemaVersion = schemaVersion
	history.UpdatedAt = nowISO()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(history, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(data, '\n'), 0o644)
}

func (h ExecutionHistory) recordFor(date string) (DailyRecord, bool) {
	for _, record := range h.Records {
		if record.Date == date {
			return record, true
		}
	}
	return DailyRecord{Date: date}, false
}

func (h *ExecutionHistory) upsert(record DailyRecord) {
	for i := range h.Records {
		if h.Records[i].Date == record.Date {
			h.Records[i] = record
			return
		}
	}
	h.Records = append([]DailyRecord{record}, h.Records...)
}

func (h ExecutionHistory) previousRecord(date time.Time) (DailyRecord, bool) {
	key := date.AddDate(0, 0, -1).Format("2006-01-02")
	return h.recordFor(key)
}

func sectionValue(brief DailyBrief, key string) string {
	for _, section := range brief.Sections {
		if section.Key == key {
			return section.Content
		}
	}
	return ""
}

func setSection(brief *DailyBrief, key string, value string) {
	for i := range brief.Sections {
		if brief.Sections[i].Key == key {
			brief.Sections[i].Content = value
			return
		}
	}
}

func (MockBriefGenerator) Generate(history ExecutionHistory, settings DailySettings, date time.Time) DailyBrief {
	previous, ok := history.previousRecord(date)
	goal := "Create visible momentum on the highest-leverage work."
	top := "1. Ship one concrete improvement.\n2. Clear one blocker.\n3. Leave tomorrow easier than today."
	firstStep := "Open the most important project and define the next commit-sized action."
	risk := "Risk: diffuse attention. Countermeasure: run one focused block before checking feeds."
	notDoing := "No speculative redesigns, low-value inbox sweeps, or extra tooling detours."
	prev := "No previous execution record found. Start clean and create the first data point."
	if ok {
		if previous.Evening.ExecutionSummary != "" {
			prev = previous.Evening.ExecutionSummary
		} else if previous.Brief.Accepted {
			prev = "Yesterday's accepted brief is assumed executed. Carry forward only what still matters."
		}
		if previous.Evening.CarryOver != "" {
			goal = previous.Evening.CarryOver
		}
		if previous.Evening.FirstStepForTomorrow != "" {
			firstStep = previous.Evening.FirstStepForTomorrow
		}
	}
	motivation := "Keep it narrow. Execution beats a bigger plan today."
	if settings.MotivationalTone == "calm" {
		motivation = "Move steadily. A clean next step is enough to restart momentum."
	}
	if settings.MotivationalTone == "hard" {
		motivation = "Make the day prove itself in shipped outcomes, not intentions."
	}
	process := "What one friction point should be removed before tomorrow?"
	if !settings.ShowProcessImprovementQuestions {
		process = "Disabled in settings."
	}
	stamp := nowISO()
	return DailyBrief{
		Date: date.Format("2006-01-02"),
		Sections: []BriefSection{
			{Key: "goal", Title: "Goal of the day", Content: goal},
			{Key: "top_results", Title: "Top 3 results", Content: top},
			{Key: "first_step", Title: "First 10-minute step", Content: firstStep},
			{Key: "risk", Title: "One risk + countermeasure", Content: risk},
			{Key: "not_doing", Title: "Not doing today", Content: notDoing},
			{Key: "previous_summary", Title: "Previous day summary", Content: prev},
			{Key: "motivational_note", Title: "Motivational note", Content: motivation},
			{Key: "process_question", Title: "Process improvement question", Content: process},
		},
		CreatedAt: stamp,
		UpdatedAt: stamp,
	}
}

func ensureToday(history *ExecutionHistory, generator BriefGenerator, date time.Time) DailyRecord {
	key := date.Format("2006-01-02")
	record, ok := history.recordFor(key)
	if ok && record.Brief.Date != "" {
		return record
	}
	record.Date = key
	record.Brief = generator.Generate(*history, history.Settings, date)
	history.upsert(record)
	return record
}

func newModel(appPaths paths) model {
	history := loadHistory(appPaths.historyPath)
	gen := MockBriefGenerator{}
	record := ensureToday(&history, gen, time.Now())
	_ = saveHistory(appPaths.historyPath, history)
	status := "Morning brief generated. Choose A accept, B adjust, or C rewrite."
	if record.Brief.Accepted {
		status = "Today is active. Use M for midday and E for evening."
	}
	return model{
		paths:     appPaths,
		history:   history,
		today:     todayKey(),
		screen:    screenToday,
		status:    status,
		generator: gen,
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
		if m.mode != modeNormal {
			return m.updateForm(msg)
		}
		switch msg.String() {
		case "ctrl+c", "q":
			m.quitting = true
			return m, tea.Quit
		case "1":
			m.screen = screenToday
			m.cursor = 0
			m.scroll = 0
		case "2":
			m.screen = screenHistory
			m.cursor = 0
			m.scroll = 0
		case "3":
			m.screen = screenSettings
			m.cursor = 0
			m.scroll = 0
		case "up", "k":
			if m.cursor > 0 {
				m.cursor--
			}
		case "down", "j":
			if m.cursor < m.maxCursor() {
				m.cursor++
			}
		case "pgdown", "f":
			m.scroll += 8
		case "pgup":
			m.scroll -= 8
			if m.scroll < 0 {
				m.scroll = 0
			}
		case "a", "A":
			if m.screen == screenToday {
				m.acceptBrief()
			}
		case "b", "B":
			if m.screen == screenToday {
				m.startBriefForm(modeEditBrief)
			}
		case "c", "C":
			if m.screen == screenToday {
				m.startBriefForm(modeRewriteBrief)
			}
		case "enter", " ":
			m.activateSelection()
		case "m", "M":
			if m.screen == screenToday && m.history.Settings.MiddayRecalibrationEnabled {
				m.startMiddayForm()
			}
		case "e", "E":
			if m.screen == screenToday {
				m.startEveningForm()
			}
		case "s", "S":
			m.screen = screenSettings
			m.startSettingsForm()
		}
	}
	return m, nil
}

func (m model) updateForm(msg tea.KeyPressMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case "ctrl+c":
		m.quitting = true
		return m, tea.Quit
	case "esc":
		m.mode = modeNormal
		m.fields = nil
		m.status = "Edit cancelled."
	case "tab", "down":
		if m.fieldCursor < len(m.fields)-1 {
			m.fieldCursor++
		}
	case "shift+tab", "up":
		if m.fieldCursor > 0 {
			m.fieldCursor--
		}
	case "enter":
		if m.fieldCursor < len(m.fields)-1 {
			m.fieldCursor++
		} else {
			m.commitForm()
		}
	case "backspace":
		if len(m.fields) > 0 {
			value := []rune(m.fields[m.fieldCursor].Value)
			if len(value) > 0 {
				m.fields[m.fieldCursor].Value = string(value[:len(value)-1])
			}
		}
	case "ctrl+u":
		if len(m.fields) > 0 {
			m.fields[m.fieldCursor].Value = ""
		}
	default:
		if len(m.fields) > 0 {
			text := msg.String()
			if utf8.RuneCountInString(text) == 1 && text >= " " {
				m.fields[m.fieldCursor].Value += text
			}
		}
	}
	return m, nil
}

func (m *model) activateSelection() {
	switch m.screen {
	case screenToday:
		switch m.cursor {
		case 0:
			m.acceptBrief()
		case 1:
			m.startBriefForm(modeEditBrief)
		case 2:
			m.startBriefForm(modeRewriteBrief)
		case 3:
			if m.history.Settings.MiddayRecalibrationEnabled {
				m.startMiddayForm()
			} else {
				m.status = "Midday recalibration is disabled in settings."
			}
		case 4:
			m.startEveningForm()
		}
	case screenSettings:
		m.startSettingsForm()
	}
}

func (m model) maxCursor() int {
	switch m.screen {
	case screenToday:
		return 4
	case screenHistory:
		if len(m.history.Records) == 0 {
			return 0
		}
		return len(m.history.Records) - 1
	case screenSettings:
		return 0
	default:
		return 0
	}
}

func (m *model) acceptBrief() {
	record, _ := m.history.recordFor(m.today)
	record.Brief.Accepted = true
	record.Brief.Decision = UserDecision{Choice: "accept", CreatedAt: nowISO()}
	record.Brief.UpdatedAt = nowISO()
	m.history.upsert(record)
	if err := saveHistory(m.paths.historyPath, m.history); err != nil {
		m.status = "Save failed: " + err.Error()
		return
	}
	m.status = "Brief accepted. Execute the first 10-minute step."
}

func (m *model) startBriefForm(mode focusMode) {
	record, _ := m.history.recordFor(m.today)
	values := []formField{
		{Label: "Goal of the day", Value: sectionValue(record.Brief, "goal")},
		{Label: "Top 3 results", Value: sectionValue(record.Brief, "top_results")},
		{Label: "First 10-minute step", Value: sectionValue(record.Brief, "first_step")},
		{Label: "One risk + countermeasure", Value: sectionValue(record.Brief, "risk")},
		{Label: "Not doing today", Value: sectionValue(record.Brief, "not_doing")},
		{Label: "Previous day summary", Value: sectionValue(record.Brief, "previous_summary")},
		{Label: "Motivational note", Value: sectionValue(record.Brief, "motivational_note")},
		{Label: "Process improvement question", Value: sectionValue(record.Brief, "process_question")},
	}
	if mode == modeRewriteBrief {
		for i := range values {
			values[i].Value = ""
		}
	}
	m.mode = mode
	m.fields = values
	m.fieldCursor = 0
	m.status = "Editing brief. Enter advances, final Enter saves, Esc cancels, Ctrl+U clears field."
}

func (m *model) startMiddayForm() {
	record, _ := m.history.recordFor(m.today)
	m.mode = modeMidday
	m.fields = []formField{
		{Label: "What is already done?", Value: record.Midday.AlreadyDone},
		{Label: "What still matters today?", Value: record.Midday.StillMatters},
		{Label: "What should be dropped or moved?", Value: record.Midday.DropOrMove},
		{Label: "Next 45-minute execution block", Value: record.Midday.Next45MinuteBlock},
	}
	m.fieldCursor = 0
	m.status = "Midday recalibration. Keep it surgical."
}

func (m *model) startEveningForm() {
	record, _ := m.history.recordFor(m.today)
	m.mode = modeEvening
	m.fields = []formField{
		{Label: "What was completed?", Value: record.Evening.Completed},
		{Label: "What was blocked?", Value: record.Evening.Blocked},
		{Label: "What should carry over?", Value: record.Evening.CarryOver},
		{Label: "One-sentence execution summary", Value: record.Evening.ExecutionSummary},
		{Label: "First suggested step for tomorrow", Value: record.Evening.FirstStepForTomorrow},
	}
	m.fieldCursor = 0
	m.status = "Evening wrap-up. Capture continuity, not a diary."
}

func (m *model) startSettingsForm() {
	s := m.history.Settings
	m.mode = modeSettings
	m.fields = []formField{
		{Label: "Morning reminder time", Value: s.MorningReminder},
		{Label: "Midday reminder time", Value: s.MiddayReminder},
		{Label: "Evening reminder time", Value: s.EveningReminder},
		{Label: "Motivational tone", Value: s.MotivationalTone},
		{Label: "Midday recalibration enabled", Value: boolText(s.MiddayRecalibrationEnabled)},
		{Label: "Show process improvement questions", Value: boolText(s.ShowProcessImprovementQuestions)},
	}
	m.fieldCursor = 0
	m.status = "Settings edit. Use true/false for toggles."
}

func (m *model) commitForm() {
	record, _ := m.history.recordFor(m.today)
	stamp := nowISO()
	switch m.mode {
	case modeEditBrief, modeRewriteBrief:
		keys := []string{"goal", "top_results", "first_step", "risk", "not_doing", "previous_summary", "motivational_note", "process_question"}
		for i, key := range keys {
			setSection(&record.Brief, key, m.fields[i].Value)
		}
		choice := "adjust"
		if m.mode == modeRewriteBrief {
			choice = "rewrite"
		}
		record.Brief.Accepted = true
		record.Brief.Decision = UserDecision{Choice: choice, CreatedAt: stamp}
		record.Brief.UpdatedAt = stamp
		m.status = "Brief saved and accepted."
	case modeMidday:
		record.Midday = MiddayCheckIn{
			Date:              m.today,
			AlreadyDone:       m.fields[0].Value,
			StillMatters:      m.fields[1].Value,
			DropOrMove:        m.fields[2].Value,
			Next45MinuteBlock: m.fields[3].Value,
			CreatedAt:         keepCreated(record.Midday.CreatedAt, stamp),
			UpdatedAt:         stamp,
		}
		m.status = "Midday recalibration saved. Run the next 45-minute block."
	case modeEvening:
		record.Evening = EveningWrapUp{
			Date:                 m.today,
			Completed:            m.fields[0].Value,
			Blocked:              m.fields[1].Value,
			CarryOver:            m.fields[2].Value,
			ExecutionSummary:     m.fields[3].Value,
			FirstStepForTomorrow: m.fields[4].Value,
			CreatedAt:            keepCreated(record.Evening.CreatedAt, stamp),
			UpdatedAt:            stamp,
		}
		m.status = "Evening wrap-up saved. Tomorrow's brief will use this."
	case modeSettings:
		m.history.Settings = DailySettings{
			MorningReminder:                 valueOr(m.fields[0].Value, "08:30"),
			MiddayReminder:                  valueOr(m.fields[1].Value, "12:30"),
			EveningReminder:                 valueOr(m.fields[2].Value, "17:30"),
			MotivationalTone:                valueOr(m.fields[3].Value, "direct"),
			MiddayRecalibrationEnabled:      parseBoolDefault(m.fields[4].Value, true),
			ShowProcessImprovementQuestions: parseBoolDefault(m.fields[5].Value, true),
		}
		m.status = "Settings saved."
	}
	m.history.upsert(record)
	if err := saveHistory(m.paths.historyPath, m.history); err != nil {
		m.status = "Save failed: " + err.Error()
	}
	m.mode = modeNormal
	m.fields = nil
	m.fieldCursor = 0
}

func keepCreated(existing string, fallback string) string {
	if existing != "" {
		return existing
	}
	return fallback
}

func valueOr(value, fallback string) string {
	if strings.TrimSpace(value) == "" {
		return fallback
	}
	return strings.TrimSpace(value)
}

func parseBoolDefault(value string, fallback bool) bool {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case "true", "yes", "y", "1", "on":
		return true
	case "false", "no", "n", "0", "off":
		return false
	default:
		return fallback
	}
}

func boolText(value bool) string {
	if value {
		return "true"
	}
	return "false"
}

func (m model) View() tea.View {
	if m.quitting {
		return tea.NewView("\n  Daily closed.\n")
	}
	if m.width == 0 {
		m.width = 110
	}
	header := lipgloss.JoinVertical(lipgloss.Left,
		titleStyle.Render(" cento daily "),
		subtleStyle.Render("Daily Execution Support: brief, recalibrate, wrap up."),
		renderTabs(m.screen),
		statusLine(m.status),
	)
	body := m.renderBody()
	return tea.NewView(frameStyle.Render(lipgloss.JoinVertical(lipgloss.Left, header, "\n", body)))
}

func renderTabs(active screen) string {
	tabs := []string{"1 Today", "2 History", "3 Settings"}
	parts := make([]string, len(tabs))
	for i, tab := range tabs {
		if screen(i) == active {
			parts[i] = activeTabStyle.Render(tab)
		} else {
			parts[i] = tabStyle.Render(tab)
		}
	}
	return strings.Join(parts, " ")
}

func statusLine(status string) string {
	if strings.Contains(strings.ToLower(status), "failed") {
		return warnStyle.Render(status)
	}
	return okStyle.Render(status)
}

func (m model) renderBody() string {
	if m.mode != modeNormal {
		return m.renderForm()
	}
	switch m.screen {
	case screenToday:
		return m.renderToday()
	case screenHistory:
		return m.renderHistory()
	case screenSettings:
		return m.renderSettings()
	default:
		return ""
	}
}

func (m model) renderToday() string {
	record, _ := m.history.recordFor(m.today)
	leftWidth := 34
	rightWidth := max(48, m.width-leftWidth-10)
	actions := []string{
		"A Accept proposed brief",
		"B Adjust fields",
		"C Rewrite brief",
		"M Midday recalibration",
		"E Evening wrap-up",
	}
	var menu []string
	for i, action := range actions {
		line := action
		if i == m.cursor {
			line = activeFieldStyle.Width(leftWidth - 6).Render(line)
		} else {
			line = fieldStyle.Width(leftWidth - 6).Render(line)
		}
		menu = append(menu, line)
	}
	state := "proposed"
	if record.Brief.Accepted {
		state = "accepted via " + record.Brief.Decision.Choice
	}
	left := panelStyle.Width(leftWidth).Render(strings.Join([]string{
		hotStyle.Render("Execution Loop"),
		subtleStyle.Render("state: " + state),
		"",
		strings.Join(menu, "\n"),
		"",
		subtleStyle.Render("q quit  enter select"),
	}, "\n"))
	right := panelStyle.Width(rightWidth).Render(m.briefText(record))
	return lipgloss.JoinHorizontal(lipgloss.Top, left, "  ", right)
}

func (m model) briefText(record DailyRecord) string {
	lines := []string{
		hotStyle.Render("Morning Brief") + "  " + subtleStyle.Render(record.Date),
		"",
	}
	for _, section := range record.Brief.Sections {
		lines = append(lines, hotStyle.Render(section.Title))
		lines = append(lines, wrapBlock(section.Content, m.width-54)...)
		lines = append(lines, "")
	}
	if record.Midday.Date != "" {
		lines = append(lines, hotStyle.Render("Midday Recalibration"))
		lines = append(lines, "Done: "+record.Midday.AlreadyDone)
		lines = append(lines, "Still matters: "+record.Midday.StillMatters)
		lines = append(lines, "Drop/move: "+record.Midday.DropOrMove)
		lines = append(lines, "Next block: "+record.Midday.Next45MinuteBlock)
		lines = append(lines, "")
	}
	if record.Evening.Date != "" {
		lines = append(lines, hotStyle.Render("Evening Wrap-up"))
		lines = append(lines, "Completed: "+record.Evening.Completed)
		lines = append(lines, "Blocked: "+record.Evening.Blocked)
		lines = append(lines, "Carry over: "+record.Evening.CarryOver)
		lines = append(lines, "Summary: "+record.Evening.ExecutionSummary)
		lines = append(lines, "Tomorrow: "+record.Evening.FirstStepForTomorrow)
	}
	return strings.Join(lines, "\n")
}

func (m model) renderHistory() string {
	width := max(70, m.width-8)
	if len(m.history.Records) == 0 {
		return panelStyle.Width(width).Render("No daily records yet.")
	}
	var rows []string
	for i, record := range m.history.Records {
		marker := " "
		if i == m.cursor {
			marker = ">"
		}
		summary := record.Evening.ExecutionSummary
		if summary == "" {
			summary = sectionValue(record.Brief, "goal")
		}
		rows = append(rows, fmt.Sprintf("%s %s  %s", marker, record.Date, summary))
	}
	selected := m.history.Records[min(m.cursor, len(m.history.Records)-1)]
	detail := m.briefText(selected)
	return lipgloss.JoinVertical(lipgloss.Left,
		panelStyle.Width(width).Render(hotStyle.Render("History")+"\n\n"+strings.Join(rows, "\n")),
		"\n",
		panelStyle.Width(width).Render(detail),
	)
}

func (m model) renderSettings() string {
	s := m.history.Settings
	lines := []string{
		hotStyle.Render("Settings"),
		"",
		"Morning reminder: " + s.MorningReminder,
		"Midday reminder: " + s.MiddayReminder,
		"Evening reminder: " + s.EveningReminder,
		"Motivational tone: " + s.MotivationalTone,
		"Midday recalibration: " + boolText(s.MiddayRecalibrationEnabled),
		"Process improvement question: " + boolText(s.ShowProcessImprovementQuestions),
		"",
		subtleStyle.Render("Press S or Enter to edit. Settings are local and stored with daily history."),
		"",
		"History path: " + m.paths.historyPath,
	}
	return panelStyle.Width(max(70, m.width-8)).Render(strings.Join(lines, "\n"))
}

func (m model) renderForm() string {
	title := "Edit"
	switch m.mode {
	case modeEditBrief:
		title = "Adjust Brief"
	case modeRewriteBrief:
		title = "Rewrite Brief"
	case modeMidday:
		title = "Midday Recalibration"
	case modeEvening:
		title = "Evening Wrap-up"
	case modeSettings:
		title = "Settings"
	}
	var lines []string
	for i, field := range m.fields {
		value := field.Value
		if value == "" {
			value = subtleStyle.Render("(empty)")
		}
		line := field.Label + "\n" + value
		if i == m.fieldCursor {
			line = activeFieldStyle.Width(max(64, m.width-16)).Render(line)
		} else {
			line = fieldStyle.Width(max(64, m.width-16)).Render(line)
		}
		lines = append(lines, line)
	}
	legend := subtleStyle.Render("type to edit  backspace delete  ctrl+u clear  enter next/save  esc cancel")
	return panelStyle.Width(max(74, m.width-8)).Render(hotStyle.Render(title) + "\n\n" + strings.Join(lines, "\n\n") + "\n\n" + legend)
}

func wrapBlock(input string, width int) []string {
	if width < 30 {
		width = 30
	}
	var out []string
	for _, raw := range strings.Split(input, "\n") {
		if raw == "" {
			out = append(out, "")
			continue
		}
		words := strings.Fields(raw)
		if len(words) == 0 {
			out = append(out, "")
			continue
		}
		line := words[0]
		for _, word := range words[1:] {
			if utf8.RuneCountInString(line+" "+word) <= width {
				line += " " + word
				continue
			}
			out = append(out, line)
			line = word
		}
		out = append(out, line)
	}
	return out
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
	if (info.Mode() & os.ModeCharDevice) == 0 {
		return false
	}
	tty, err := os.OpenFile("/dev/tty", os.O_RDWR, 0)
	if err != nil {
		return false
	}
	_ = tty.Close()
	return true
}

func runNonInteractive(appPaths paths) error {
	history := loadHistory(appPaths.historyPath)
	record := ensureToday(&history, MockBriefGenerator{}, time.Now())
	if err := saveHistory(appPaths.historyPath, history); err != nil {
		return err
	}
	fmt.Println("cento daily")
	fmt.Println("date:", record.Date)
	fmt.Println("history:", appPaths.historyPath)
	fmt.Println("goal:", sectionValue(record.Brief, "goal"))
	return nil
}

func main() {
	appPaths, err := initPaths()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if !isTTY() {
		if err := runNonInteractive(appPaths); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		return
	}
	program := tea.NewProgram(newModel(appPaths))
	if _, err := program.Run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
