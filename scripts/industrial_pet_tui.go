package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"hash/fnv"
	"image"
	"image/color"
	_ "image/jpeg"
	_ "image/png"
	"os"
	"path/filepath"
	"strings"
	"time"

	tea "charm.land/bubbletea/v2"
	"charm.land/lipgloss/v2"
)

type tickMsg time.Time

type petDatabase struct {
	SchemaVersion int                 `json:"schema_version"`
	Activities    []petActivity       `json:"activities"`
	MoodComments  map[string][]string `json:"mood_comments"`
	IdleBarks     []string            `json:"idle_barks"`
	RareEvents    []rareEvent         `json:"rare_events"`
}

type petActivity struct {
	ID          string         `json:"id"`
	Name        string         `json:"name"`
	Description string         `json:"description"`
	Deltas      map[string]int `json:"deltas"`
	Comments    []string       `json:"comments"`
	Log         []string       `json:"log"`
}

type rareEvent struct {
	ID      string         `json:"id"`
	OneIn   int            `json:"one_in"`
	Text    string         `json:"text"`
	Deltas  map[string]int `json:"deltas"`
	Comment string         `json:"comment"`
}

type petState struct {
	Name          string         `json:"name"`
	CreatedAt     string         `json:"created_at"`
	LastSeen      string         `json:"last_seen"`
	UpdatedAt     string         `json:"updated_at"`
	Stats         map[string]int `json:"stats"`
	Selected      string         `json:"selected"`
	LatestComment string         `json:"latest_comment"`
	Mood          string         `json:"mood"`
	ActivityLog   []petLogEntry  `json:"activity_log"`
	ActionCount   int            `json:"action_count"`
}

type petLogEntry struct {
	At       string         `json:"at"`
	Activity string         `json:"activity"`
	Comment  string         `json:"comment"`
	Deltas   map[string]int `json:"deltas,omitempty"`
}

type loadResult struct {
	State            petState
	Recovered        bool
	Decayed          bool
	PreviousLastSeen time.Time
}

type statDef struct {
	Key   string
	Label string
}

type model struct {
	statePath    string
	databasePath string
	imagePath    string
	portraitMode string
	db           petDatabase
	state        petState
	now          time.Time
	lastSeen     time.Time
	portrait     []string
	portraitW    int
	portraitRows int
	selected     int
	width        int
	height       int
	interval     time.Duration
	err          error
	saveErr      error
}

var (
	statDefs = []statDef{
		{Key: "snack", Label: "SNACK"},
		{Key: "energy", Label: "REST"},
		{Key: "menace", Label: "MENACE"},
		{Key: "affection", Label: "LOYAL"},
	}

	red        = lipgloss.Color("#FF4B00")
	pink       = lipgloss.Color("#FF8ACB")
	amber      = lipgloss.Color("#FFB000")
	green      = lipgloss.Color("#7CFB8B")
	text       = lipgloss.Color("#F4E8DC")
	muted      = lipgloss.Color("#8B746F")
	dark       = lipgloss.Color("#080503")
	panelStyle = lipgloss.NewStyle().Foreground(text).Padding(1, 1)
	titleStyle = lipgloss.NewStyle().Foreground(pink).Bold(true)
	nameStyle  = lipgloss.NewStyle().Foreground(text)
	mutedStyle = lipgloss.NewStyle().Foreground(muted)
	ruleStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color("#7A2E3C"))
	valueStyle = lipgloss.NewStyle().Foreground(amber).Bold(true)
	badStyle   = lipgloss.NewStyle().Foreground(red).Bold(true)
	goodStyle  = lipgloss.NewStyle().Foreground(green).Bold(true)
	badgeStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("#FFF4F8")).Background(lipgloss.Color("#5B1735")).Bold(true).Padding(0, 1)
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

func defaultStatePath() string {
	if explicit := os.Getenv("CENTO_INDUSTRIAL_PET_STATE"); explicit != "" {
		return explicit
	}
	stateHome := os.Getenv("XDG_STATE_HOME")
	if stateHome == "" {
		home, err := os.UserHomeDir()
		if err != nil || home == "" {
			stateHome = "."
		} else {
			stateHome = filepath.Join(home, ".local", "state")
		}
	}
	return filepath.Join(stateHome, "cento", "industrial-os", "darth-lolipopus.json")
}

func defaultDatabasePath(root string) string {
	if explicit := os.Getenv("CENTO_INDUSTRIAL_PET_DATABASE"); explicit != "" {
		return explicit
	}
	return filepath.Join(root, "data", "industrial-pet.json")
}

func defaultImagePath(root string) string {
	if explicit := os.Getenv("CENTO_INDUSTRIAL_PET_IMAGE"); explicit != "" {
		return explicit
	}
	candidates := []string{
		filepath.Join(root, "assets", "industrial-os", "darth-lolipopus.png"),
	}
	if home, err := os.UserHomeDir(); err == nil && home != "" {
		candidates = append(candidates,
			filepath.Join(home, ".config", "polybar", "scripts", "rofi", "rainbow-reaper.png"),
			filepath.Join(home, ".config", "polybar2", "scripts", "rofi", "rainbow-reaper.png"),
		)
	}
	for _, path := range candidates {
		if info, err := os.Stat(path); err == nil && !info.IsDir() {
			return path
		}
	}
	return ""
}

func parseNow(value string) (time.Time, error) {
	if value == "" {
		value = os.Getenv("CENTO_INDUSTRIAL_PET_NOW")
	}
	if value == "" {
		return time.Now().UTC(), nil
	}
	parsed, err := time.Parse(time.RFC3339, value)
	if err != nil {
		return time.Time{}, err
	}
	return parsed.UTC(), nil
}

func loadDatabase(path string) (petDatabase, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return petDatabase{}, err
	}
	var db petDatabase
	if err := json.Unmarshal(raw, &db); err != nil {
		return petDatabase{}, err
	}
	if len(db.Activities) == 0 {
		return petDatabase{}, errors.New("pet database has no activities")
	}
	seen := map[string]bool{}
	for _, activity := range db.Activities {
		if activity.ID == "" || activity.Name == "" {
			return petDatabase{}, errors.New("pet database activity is missing id or name")
		}
		if seen[activity.ID] {
			return petDatabase{}, fmt.Errorf("duplicate activity id: %s", activity.ID)
		}
		seen[activity.ID] = true
	}
	return db, nil
}

func defaultState(now time.Time) petState {
	stamp := now.Format(time.RFC3339)
	return petState{
		Name:      "Darth Lolipopus",
		CreatedAt: stamp,
		LastSeen:  stamp,
		UpdatedAt: stamp,
		Stats: map[string]int{
			"snack":     72,
			"energy":    68,
			"menace":    54,
			"affection": 61,
		},
		Selected:      "sith_snack",
		LatestComment: "Darth Lolipopus adjusts a tiny cape and demands appropriate awe.",
		Mood:          "scheming",
		ActivityLog: []petLogEntry{
			{At: stamp, Activity: "summon", Comment: "Cute Sith nursery online."},
		},
	}
}

func loadState(path string, now time.Time) loadResult {
	raw, err := os.ReadFile(path)
	if err != nil || len(strings.TrimSpace(string(raw))) == 0 {
		state := defaultState(now)
		return loadResult{State: state, Recovered: true, PreviousLastSeen: now}
	}

	var state petState
	if err := json.Unmarshal(raw, &state); err != nil {
		state := defaultState(now)
		state.LatestComment = "The nursery holocron rebooted Darth Lolipopus cleanly."
		return loadResult{State: state, Recovered: true, PreviousLastSeen: now}
	}

	recovered := normalizeState(&state, now)
	previousLastSeen, ok := parseStamp(state.LastSeen)
	if !ok {
		previousLastSeen = now
		recovered = true
	}
	decayed := applyDecay(&state, previousLastSeen, now)
	state.Mood = computeMood(state.Stats)
	if decayed {
		state.LastSeen = now.Format(time.RFC3339)
		state.UpdatedAt = now.Format(time.RFC3339)
	}
	return loadResult{State: state, Recovered: recovered, Decayed: decayed, PreviousLastSeen: previousLastSeen}
}

func normalizeState(state *petState, now time.Time) bool {
	recovered := false
	stamp := now.Format(time.RFC3339)
	if strings.TrimSpace(state.Name) == "" {
		state.Name = "Darth Lolipopus"
		recovered = true
	}
	if _, ok := parseStamp(state.CreatedAt); !ok {
		state.CreatedAt = stamp
		recovered = true
	}
	if _, ok := parseStamp(state.LastSeen); !ok {
		state.LastSeen = stamp
		recovered = true
	}
	if _, ok := parseStamp(state.UpdatedAt); !ok {
		state.UpdatedAt = stamp
		recovered = true
	}
	if state.Stats == nil {
		state.Stats = map[string]int{}
		recovered = true
	}
	defaults := defaultState(now).Stats
	for _, stat := range statDefs {
		value, ok := state.Stats[stat.Key]
		if !ok {
			state.Stats[stat.Key] = defaults[stat.Key]
			recovered = true
			continue
		}
		state.Stats[stat.Key] = clamp(value, 0, 100)
	}
	if state.Selected == "" {
		state.Selected = "sith_snack"
		recovered = true
	}
	if state.LatestComment == "" {
		state.LatestComment = "Darth Lolipopus watches the cockpit with suspicious sweetness."
		recovered = true
	}
	if state.Mood == "" {
		state.Mood = computeMood(state.Stats)
		recovered = true
	}
	if state.ActivityLog == nil {
		state.ActivityLog = []petLogEntry{}
		recovered = true
	}
	if len(state.ActivityLog) > 8 {
		state.ActivityLog = state.ActivityLog[:8]
		recovered = true
	}
	return recovered
}

func parseStamp(value string) (time.Time, bool) {
	parsed, err := time.Parse(time.RFC3339, value)
	if err != nil {
		return time.Time{}, false
	}
	return parsed.UTC(), true
}

func applyDecay(state *petState, previousLastSeen time.Time, now time.Time) bool {
	if now.Before(previousLastSeen) {
		return false
	}
	hours := int(now.Sub(previousLastSeen).Hours())
	if hours <= 0 {
		return false
	}
	units := min(hours, 72)
	applyDeltas(state.Stats, map[string]int{
		"snack":     -4 * units,
		"energy":    -2 * units,
		"menace":    -1 * units,
		"affection": -1 * units,
	})
	if units >= 6 {
		state.LatestComment = "Darth Lolipopus waited in the shadows and now expects tribute."
	}
	return true
}

func saveState(path string, state petState) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	raw, err := json.MarshalIndent(state, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(raw, '\n'), 0o644)
}

func (m model) Init() tea.Cmd {
	return tickCmd(m.interval)
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
			m.reload(time.Now().UTC(), true)
		case "j", "down":
			if m.selected < len(m.db.Activities)-1 {
				m.selected++
				m.state.Selected = m.db.Activities[m.selected].ID
			}
		case "k", "up":
			if m.selected > 0 {
				m.selected--
				m.state.Selected = m.db.Activities[m.selected].ID
			}
		case "enter":
			m.performSelected(time.Now().UTC())
		case "1", "2", "3", "4", "5", "6":
			index := int(msg.String()[0] - '1')
			if index >= 0 && index < len(m.db.Activities) {
				m.selected = index
				m.state.Selected = m.db.Activities[index].ID
				m.performSelected(time.Now().UTC())
			}
		}
	case tickMsg:
		m.reload(time.Time(msg), true)
		return m, tickCmd(m.interval)
	}
	return m, nil
}

func (m *model) reload(now time.Time, persist bool) {
	result := loadState(m.statePath, now.UTC())
	m.state = result.State
	m.now = now.UTC()
	m.lastSeen = result.PreviousLastSeen
	m.selected = selectedIndex(m.db, m.state.Selected)
	if persist && (result.Recovered || result.Decayed) {
		m.saveErr = saveState(m.statePath, m.state)
	}
}

func (m *model) performSelected(now time.Time) {
	if len(m.db.Activities) == 0 {
		m.err = errors.New("pet database has no activities")
		return
	}
	if m.selected < 0 || m.selected >= len(m.db.Activities) {
		m.selected = 0
	}
	activity := m.db.Activities[m.selected]
	m.now = now.UTC()
	performActivity(&m.state, m.db, activity.ID, m.now)
	m.lastSeen = m.now
	m.saveErr = saveState(m.statePath, m.state)
}

func (m model) View() tea.View {
	width := m.width
	if width <= 0 {
		width = 50
	}
	width = clamp(width-2, 34, 110)
	body := m.renderBody(width - 2)
	view := tea.NewView(panelStyle.Width(width).Render(body))
	view.AltScreen = true
	return view
}

func (m model) renderBody(width int) string {
	width = clamp(width, 34, 110)
	now := m.now
	if now.IsZero() {
		now = time.Now().UTC()
	}
	mood := computeMood(m.state.Stats)
	comment := m.state.LatestComment
	if comment == "" {
		comment = choose(m.db.IdleBarks, "idle"+now.Format(time.RFC3339))
	}
	age := ageLabel(m.state.CreatedAt, now)
	lastSeen := agoLabel(m.lastSeen, now)
	if m.lastSeen.IsZero() {
		lastSeen = "new"
	}

	if m.portraitMode == "slot" && width >= 68 {
		return lipgloss.JoinVertical(lipgloss.Left, m.slotBody(mood, age, lastSeen, comment, width, now)...)
	}
	lines := []string{
		mutedStyle.Render(clip(now.Local().Format("15:04:05")+"  pet", width)),
		titleStyle.Render("> DARTH LOLIPOPUS"),
		ruleStyle.Render(strings.Repeat("-", width)),
	}
	if (len(m.portrait) > 0 || m.portraitMode == "slot") && width >= 68 {
		lines = append(lines, m.heroBlock(mood, age, lastSeen, width), "")
	} else {
		if len(m.portrait) > 0 {
			lines = append(lines, m.portrait...)
		}
		lines = append(lines, avatarLine(mood, age, lastSeen, width), "")
		for _, stat := range statDefs {
			lines = append(lines, statLine(stat.Label, m.state.Stats[stat.Key], width))
		}
	}
	lines = append(lines, "", valueStyle.Render("ACTIVITIES"))
	compact := m.height > 0 && m.height <= 26
	for index, activity := range m.db.Activities {
		if index >= 6 {
			break
		}
		prefix := " "
		if index == m.selected {
			prefix = ">"
		}
		row := fmt.Sprintf("%s %d %-16s %s", prefix, index+1, activity.Name, deltaSummary(activity.Deltas))
		row = clip(row, width)
		if index == m.selected {
			lines = append(lines, goodStyle.Render(row))
		} else {
			lines = append(lines, nameStyle.Render(row))
		}
	}

	selected := m.selectedActivity()
	if compact {
		lines = append(lines,
			"",
			valueStyle.Render("SELECTED")+" "+nameStyle.Render(clip(selected.Name, max(8, width-9))),
			valueStyle.Render("COMMENT")+" "+nameStyle.Render(clip(comment, max(8, width-8))),
		)
		if len(m.state.ActivityLog) > 0 {
			lines = append(lines, valueStyle.Render("LOG")+" "+mutedStyle.Render(clip(m.state.ActivityLog[0].Comment, max(8, width-4))))
		}
		lines = append(lines, mutedStyle.Render(clip("j/k select | 1-6 act | enter perform | r refresh | q quit", width)))
		return lipgloss.JoinVertical(lipgloss.Left, lines...)
	}
	lines = append(lines,
		"",
		valueStyle.Render("SELECTED")+" "+nameStyle.Render(clip(selected.Name, max(8, width-9))),
		mutedStyle.Render(clip(selected.Description, width)),
		"",
		valueStyle.Render("COMMENT"),
		nameStyle.Render(clip(comment, width)),
	)
	if m.err != nil {
		lines = append(lines, badStyle.Render(clip("error: "+m.err.Error(), width)))
	}
	if m.saveErr != nil {
		lines = append(lines, badStyle.Render(clip("save failed: "+m.saveErr.Error(), width)))
	}
	if m.err == nil && len(m.db.Activities) == 0 {
		lines = append(lines, badStyle.Render("database has no activities"))
	}

	logLines := m.logLines(width)
	lines = append(lines, "", valueStyle.Render("LOG"))
	lines = append(lines, logLines...)
	lines = append(lines, "", mutedStyle.Render(clip("j/k select | 1-6 act | enter perform | r refresh | q quit", width)))
	return lipgloss.JoinVertical(lipgloss.Left, lines...)
}

func (m model) slotBody(mood, age, lastSeen, comment string, width int, now time.Time) []string {
	leftW := max(22, m.portraitW)
	rightW := max(34, width-leftW-3)
	lines := []string{
		slotLine(leftW, mutedStyle.Render(clip(now.Local().Format("15:04:05")+"  pet", rightW))),
		slotLine(leftW, titleStyle.Render("> DARTH LOLIPOPUS")),
		slotLine(leftW, ruleStyle.Render(strings.Repeat("-", rightW))),
		slotLine(leftW, avatarLine(mood, age, lastSeen, rightW)),
		slotLine(leftW, ""),
	}
	for _, stat := range statDefs {
		lines = append(lines, slotLine(leftW, statLine(stat.Label, m.state.Stats[stat.Key], rightW)))
	}
	lines = append(lines, slotLine(leftW, ""), slotLine(leftW, valueStyle.Render("ACTIVITIES")))
	for index, activity := range m.db.Activities {
		if index >= 6 {
			break
		}
		prefix := " "
		if index == m.selected {
			prefix = ">"
		}
		row := activityRow(prefix, index+1, activity, rightW)
		row = clip(row, rightW)
		if index == m.selected {
			row = goodStyle.Render(row)
		} else {
			row = nameStyle.Render(row)
		}
		lines = append(lines, slotLine(leftW, row))
	}
	selected := m.selectedActivity()
	lines = append(lines,
		slotLine(leftW, ""),
		slotLine(leftW, valueStyle.Render("SELECTED")+" "+nameStyle.Render(clip(selected.Name, max(8, rightW-9)))),
		slotLine(leftW, valueStyle.Render("COMMENT")+" "+nameStyle.Render(clip(comment, max(8, rightW-8)))),
	)
	if len(m.state.ActivityLog) > 0 {
		lines = append(lines, slotLine(leftW, valueStyle.Render("LOG")+" "+mutedStyle.Render(clip(m.state.ActivityLog[0].Comment, max(8, rightW-4)))))
	}
	lines = append(lines, slotLine(leftW, mutedStyle.Render(clip("j/k select | 1-6 act | enter perform | r refresh | q quit", rightW))))
	return lines
}

func slotLine(leftWidth int, right string) string {
	return strings.Repeat(" ", leftWidth) + "   " + right
}

func activityRow(prefix string, index int, activity petActivity, width int) string {
	nameWidth := clamp(width-34, 12, 16)
	deltaBudget := max(0, width-5-nameWidth)
	name := padRight(clip(activity.Name, nameWidth), nameWidth)
	return fmt.Sprintf("%s %d %s %s", prefix, index, name, deltaSummaryForWidth(activity.Deltas, deltaBudget))
}

func padRight(value string, width int) string {
	padding := width - lipgloss.Width(value)
	if padding <= 0 {
		return value
	}
	return value + strings.Repeat(" ", padding)
}

func (m model) heroBlock(mood, age, lastSeen string, width int) string {
	portraitW := m.portraitW
	if portraitW <= 0 {
		portraitW = 22
	}
	rightW := max(34, width-portraitW-3)
	right := []string{
		avatarLine(mood, age, lastSeen, rightW),
		"",
	}
	for _, stat := range statDefs {
		right = append(right, statLine(stat.Label, m.state.Stats[stat.Key], rightW))
	}
	lines := []string{}
	count := max(max(len(m.portrait), m.portraitRows), len(right))
	for index := 0; index < count; index++ {
		left := strings.Repeat(" ", portraitW)
		if index < len(m.portrait) {
			left = m.portrait[index]
		}
		rhs := ""
		if index < len(right) {
			rhs = right[index]
		}
		lines = append(lines, left+"   "+rhs)
	}
	return lipgloss.JoinVertical(lipgloss.Left, lines...)
}

func avatarLine(mood, age, lastSeen string, width int) string {
	badge := badgeStyle.Render(strings.ToUpper(mood))
	left := " /-.-\\  "
	meta := fmt.Sprintf("age %s  last %s", age, lastSeen)
	plainBudget := max(4, width-lipgloss.Width(left)-lipgloss.Width(badge)-2)
	return left + badge + " " + mutedStyle.Render(clip(meta, plainBudget))
}

func (m model) selectedActivity() petActivity {
	if len(m.db.Activities) == 0 {
		return petActivity{Name: "none", Description: "No pet activities are loaded."}
	}
	index := m.selected
	if index < 0 || index >= len(m.db.Activities) {
		index = 0
	}
	return m.db.Activities[index]
}

func (m model) logLines(width int) []string {
	limit := 4
	if m.height > 0 && m.height < 22 {
		limit = 2
	}
	if len(m.state.ActivityLog) == 0 {
		return []string{mutedStyle.Render("no activity yet")}
	}
	lines := []string{}
	for index, entry := range m.state.ActivityLog {
		if index >= limit {
			break
		}
		when := "now"
		if parsed, ok := parseStamp(entry.At); ok {
			when = parsed.Local().Format("15:04")
		}
		label := entry.Activity
		if label == "" {
			label = "activity"
		}
		lines = append(lines, mutedStyle.Render(clip(fmt.Sprintf("%s %-15s %s", when, label, entry.Comment), width)))
	}
	return lines
}

func statLine(label string, value int, width int) string {
	value = clamp(value, 0, 100)
	barWidth := clamp(width-18, 8, 24)
	filled := (value*barWidth + 50) / 100
	empty := barWidth - filled
	style := goodStyle
	if value < 30 {
		style = badStyle
	} else if value < 55 {
		style = valueStyle
	}
	bar := style.Render(strings.Repeat("#", filled)) + mutedStyle.Render(strings.Repeat("-", empty))
	line := fmt.Sprintf("%-6s [%s] %3d", label, bar, value)
	if lipgloss.Width(line) > width {
		return clip(line, width)
	}
	return line
}

func buildPortrait(path string, cols int, rows int) ([]string, int) {
	if path == "" || cols <= 0 || rows <= 0 {
		return nil, 0
	}
	file, err := os.Open(path)
	if err != nil {
		return nil, 0
	}
	defer file.Close()
	img, _, err := image.Decode(file)
	if err != nil {
		return nil, 0
	}
	bounds := img.Bounds()
	if bounds.Dx() <= 0 || bounds.Dy() <= 0 {
		return nil, 0
	}
	targetH := rows * 2
	lines := make([]string, 0, rows)
	for row := 0; row < rows; row++ {
		var builder strings.Builder
		for col := 0; col < cols; col++ {
			top := sampleImage(img, bounds, col, row*2, cols, targetH)
			bottom := sampleImage(img, bounds, col, row*2+1, cols, targetH)
			tr, tg, tb := rgb(top)
			br, bg, bb := rgb(bottom)
			builder.WriteString(fmt.Sprintf("\x1b[38;2;%d;%d;%dm\x1b[48;2;%d;%d;%dm▀\x1b[0m", tr, tg, tb, br, bg, bb))
		}
		lines = append(lines, builder.String())
	}
	return lines, cols
}

func sampleImage(img image.Image, bounds image.Rectangle, x int, y int, width int, height int) color.Color {
	var srcX, srcY int
	if width <= 1 {
		srcX = bounds.Min.X + bounds.Dx()/2
	} else {
		srcX = bounds.Min.X + x*(bounds.Dx()-1)/(width-1)
	}
	if height <= 1 {
		srcY = bounds.Min.Y + bounds.Dy()/2
	} else {
		srcY = bounds.Min.Y + y*(bounds.Dy()-1)/(height-1)
	}
	return img.At(srcX, srcY)
}

func rgb(value color.Color) (uint32, uint32, uint32) {
	r, g, b, a := value.RGBA()
	if a == 0 {
		return 5, 4, 3
	}
	return r >> 8, g >> 8, b >> 8
}

func performActivity(state *petState, db petDatabase, activityID string, now time.Time) error {
	activity, ok := activityByID(db, activityID)
	if !ok {
		return fmt.Errorf("unknown activity: %s", activityID)
	}
	applyDeltas(state.Stats, activity.Deltas)
	state.ActionCount++
	state.Selected = activity.ID
	state.Mood = computeMood(state.Stats)
	comment := choose(activity.Comments, activity.ID+now.Format(time.RFC3339)+fmt.Sprint(state.ActionCount))
	if comment == "" {
		comment = choose(db.MoodComments[state.Mood], state.Mood+fmt.Sprint(state.ActionCount))
	}
	logText := choose(activity.Log, "log"+activity.ID+fmt.Sprint(state.ActionCount))
	if logText == "" {
		logText = comment
	}
	if rare := chooseRareEvent(db.RareEvents, now, state.ActionCount, activity.ID); rare != nil {
		applyDeltas(state.Stats, rare.Deltas)
		if rare.Comment != "" {
			comment = rare.Comment
		}
		if rare.Text != "" {
			logText = rare.Text
		}
		state.Mood = computeMood(state.Stats)
	}
	state.LatestComment = comment
	stamp := now.UTC().Format(time.RFC3339)
	state.LastSeen = stamp
	state.UpdatedAt = stamp
	entry := petLogEntry{At: stamp, Activity: activity.Name, Comment: logText, Deltas: activity.Deltas}
	state.ActivityLog = append([]petLogEntry{entry}, state.ActivityLog...)
	if len(state.ActivityLog) > 8 {
		state.ActivityLog = state.ActivityLog[:8]
	}
	return nil
}

func activityByID(db petDatabase, id string) (petActivity, bool) {
	for _, activity := range db.Activities {
		if activity.ID == id {
			return activity, true
		}
	}
	return petActivity{}, false
}

func selectedIndex(db petDatabase, id string) int {
	for index, activity := range db.Activities {
		if activity.ID == id {
			return index
		}
	}
	return 0
}

func resolveActivityID(db petDatabase, value string) (string, error) {
	value = strings.TrimSpace(value)
	if value == "" {
		return "", nil
	}
	if len(value) == 1 && value[0] >= '1' && value[0] <= '6' {
		index := int(value[0] - '1')
		if index < len(db.Activities) {
			return db.Activities[index].ID, nil
		}
	}
	if _, ok := activityByID(db, value); ok {
		return value, nil
	}
	return "", fmt.Errorf("unknown activity: %s", value)
}

func chooseRareEvent(events []rareEvent, now time.Time, count int, activityID string) *rareEvent {
	for index := range events {
		event := events[index]
		if event.OneIn <= 0 {
			continue
		}
		seed := fmt.Sprintf("%s:%d:%s:%s", event.ID, count, activityID, now.Format(time.RFC3339))
		if int(hashString(seed)%uint32(event.OneIn)) == 0 {
			return &events[index]
		}
	}
	return nil
}

func applyDeltas(stats map[string]int, deltas map[string]int) {
	if stats == nil {
		return
	}
	for key, delta := range deltas {
		stats[key] = clamp(stats[key]+delta, 0, 100)
	}
}

func computeMood(stats map[string]int) string {
	if stats == nil {
		return "mysterious"
	}
	switch {
	case stats["snack"] < 25:
		return "hangry"
	case stats["energy"] < 25:
		return "sleepy"
	case stats["affection"] < 30:
		return "sulking"
	case stats["menace"] > 82:
		return "dramatic"
	case stats["snack"] > 72 && stats["energy"] > 65:
		return "smug"
	default:
		return "scheming"
	}
}

func deltaSummary(deltas map[string]int) string {
	return deltaSummaryWithLabels(deltas, []string{"SNACK", "REST", "MENACE", "LOYAL"})
}

func deltaSummaryForWidth(deltas map[string]int, width int) string {
	for _, labels := range [][]string{
		{"SNACK", "REST", "MENACE", "LOYAL"},
		{"SNK", "RST", "MEN", "LOY"},
		{"S", "R", "M", "L"},
	} {
		summary := deltaSummaryWithLabels(deltas, labels)
		if lipgloss.Width(summary) <= width {
			return summary
		}
	}
	return clip(deltaSummaryWithLabels(deltas, []string{"S", "R", "M", "L"}), width)
}

func deltaSummaryWithLabels(deltas map[string]int, labels []string) string {
	parts := []string{}
	for index, stat := range statDefs {
		value := deltas[stat.Key]
		if value == 0 {
			continue
		}
		sign := "+"
		if value < 0 {
			sign = ""
		}
		label := stat.Label
		if index < len(labels) {
			label = labels[index]
		}
		parts = append(parts, fmt.Sprintf("%s%d %s", sign, value, label))
	}
	return strings.Join(parts, " ")
}

func choose(values []string, seed string) string {
	if len(values) == 0 {
		return ""
	}
	index := int(hashString(seed) % uint32(len(values)))
	return values[index]
}

func hashString(value string) uint32 {
	h := fnv.New32a()
	_, _ = h.Write([]byte(value))
	return h.Sum32()
}

func ageLabel(createdAt string, now time.Time) string {
	created, ok := parseStamp(createdAt)
	if !ok {
		return "new"
	}
	return durationLabel(now.Sub(created))
}

func agoLabel(stamp time.Time, now time.Time) string {
	if stamp.IsZero() {
		return "new"
	}
	return durationLabel(now.Sub(stamp))
}

func durationLabel(duration time.Duration) string {
	if duration < 0 {
		duration = 0
	}
	minutes := int(duration.Minutes())
	switch {
	case minutes < 1:
		return "now"
	case minutes < 60:
		return fmt.Sprintf("%dm", minutes)
	case minutes < 48*60:
		return fmt.Sprintf("%dh", minutes/60)
	default:
		return fmt.Sprintf("%dd", minutes/(24*60))
	}
}

func clip(value string, width int) string {
	if width <= 0 {
		return ""
	}
	if lipgloss.Width(value) <= width {
		return value
	}
	runes := []rune(value)
	if width <= 3 {
		if len(runes) <= width {
			return value
		}
		return string(runes[:width])
	}
	for lipgloss.Width(string(runes)) > width-3 && len(runes) > 0 {
		runes = runes[:len(runes)-1]
	}
	return string(runes) + "..."
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

func tickCmd(interval time.Duration) tea.Cmd {
	return tea.Tick(interval, func(t time.Time) tea.Msg {
		return tickMsg(t)
	})
}

func main() {
	root := initRoot()
	fs := flag.NewFlagSet("industrial-pet-tui", flag.ExitOnError)
	once := fs.Bool("once", false, "render once and exit")
	action := fs.String("action", "", "perform one activity id and save state")
	statePath := fs.String("state", defaultStatePath(), "pet state path")
	databasePath := fs.String("database", defaultDatabasePath(root), "pet interaction database path")
	imagePath := fs.String("image", defaultImagePath(root), "pet portrait image path")
	portraitMode := fs.String("portrait", "ansi", "portrait mode: ansi, slot, or none")
	reset := fs.Bool("reset", false, "reset Darth Lolipopus state")
	width := fs.Int("width", 98, "render width for --once")
	height := fs.Int("height", 24, "render height for --once")
	nowFlag := fs.String("now", "", "RFC3339 time override for deterministic validation")
	interval := fs.Duration("interval", 20*time.Second, "refresh interval")
	fs.Parse(os.Args[1:])

	now, err := parseNow(*nowFlag)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	db, dbErr := loadDatabase(*databasePath)

	var result loadResult
	if *reset {
		state := defaultState(now)
		result = loadResult{State: state, Recovered: true, PreviousLastSeen: now}
	} else {
		result = loadState(*statePath, now)
	}

	model := model{
		statePath:    *statePath,
		databasePath: *databasePath,
		imagePath:    *imagePath,
		portraitMode: *portraitMode,
		db:           db,
		state:        result.State,
		now:          now,
		lastSeen:     result.PreviousLastSeen,
		selected:     selectedIndex(db, result.State.Selected),
		width:        *width,
		height:       *height,
		interval:     *interval,
		err:          dbErr,
	}
	switch *portraitMode {
	case "ansi":
		model.portrait, model.portraitW = buildPortrait(model.imagePath, 18, 8)
		model.portraitRows = len(model.portrait)
	case "slot":
		model.portraitW = 26
		model.portraitRows = 14
	case "none":
	default:
		fmt.Fprintln(os.Stderr, "portrait mode must be ansi, slot, or none")
		os.Exit(2)
	}

	shouldSave := *reset || result.Recovered || result.Decayed
	if dbErr == nil && *action != "" {
		activityID, resolveErr := resolveActivityID(db, *action)
		if resolveErr != nil {
			fmt.Fprintln(os.Stderr, resolveErr)
			os.Exit(2)
		}
		model.selected = selectedIndex(db, activityID)
		model.state.Selected = activityID
		performActivity(&model.state, db, activityID, now)
		model.lastSeen = now
		shouldSave = true
	}
	if shouldSave && (!*once || *action != "" || *reset) {
		model.saveErr = saveState(*statePath, model.state)
	}

	if *once || !isTTY() || *action != "" {
		fmt.Println(model.renderBody(clamp(*width, 34, 110)))
		if model.err != nil || model.saveErr != nil {
			os.Exit(1)
		}
		return
	}

	if shouldSave {
		model.saveErr = saveState(*statePath, model.state)
	}
	program := tea.NewProgram(model)
	if _, err := program.Run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
