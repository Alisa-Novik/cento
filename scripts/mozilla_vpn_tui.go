package main

import (
	"bufio"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"sync"
	"syscall"
	"time"

	tea "charm.land/bubbletea/v2"
	"charm.land/lipgloss/v2"
)

type tickMsg time.Time

type snapshotMsg struct {
	data vpnSnapshot
}

type commandDoneMsg struct {
	label  string
	output string
	err    error
}

type vpnSnapshot struct {
	Installed     bool
	Version       string
	Status        string
	DisplayStatus string
	Service       string
	ProxyService  string
	Processes     string
	Countries     []countryChoice
	CheckedAt     time.Time
	Err           string
}

type countryChoice struct {
	Name     string
	Hostname string
	Count    int
}

type serverChoice struct {
	Country  string
	City     string
	Hostname string
}

type model struct {
	width    int
	height   int
	interval time.Duration
	data     vpnSnapshot
	loading  bool
	running  string
	output   string
	selected int
}

var (
	orange    = lipgloss.Color("#FF4B00")
	amber     = lipgloss.Color("#FF9A3D")
	green     = lipgloss.Color("#A0D76E")
	warn      = lipgloss.Color("#FFD166")
	text      = lipgloss.Color("#FFFFFF")
	muted     = lipgloss.Color("#DCCFC4")
	panel     = lipgloss.NewStyle().Foreground(text).Background(lipgloss.Color("#050403")).Padding(1, 1)
	title     = lipgloss.NewStyle().Foreground(orange).Bold(true)
	label     = lipgloss.NewStyle().Foreground(amber).Bold(true)
	value     = lipgloss.NewStyle().Foreground(text)
	quiet     = lipgloss.NewStyle().Foreground(muted)
	goodBadge = lipgloss.NewStyle().Foreground(lipgloss.Color("#050403")).Background(green).Bold(true).Padding(0, 1)
	warnBadge = lipgloss.NewStyle().Foreground(lipgloss.Color("#050403")).Background(warn).Bold(true).Padding(0, 1)
	errBadge  = lipgloss.NewStyle().Foreground(lipgloss.Color("#050403")).Background(orange).Bold(true).Padding(0, 1)
	card      = lipgloss.NewStyle().Background(lipgloss.Color("#111315")).Padding(0, 1)
	urlPat    = regexp.MustCompile(`https?://\S+`)
)

func run(timeout time.Duration, name string, args ...string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	cmd := exec.CommandContext(ctx, name, args...)
	out, err := cmd.CombinedOutput()
	text := strings.TrimSpace(string(out))
	if ctx.Err() == context.DeadlineExceeded {
		return text, fmt.Errorf("%s timed out", name)
	}
	return text, err
}

func loadSnapshot() vpnSnapshot {
	snap := vpnSnapshot{CheckedAt: time.Now()}
	if _, err := exec.LookPath("mozillavpn"); err != nil {
		snap.Err = "mozillavpn command not found"
		return snap
	}
	snap.Installed = true
	if out, err := run(4*time.Second, "mozillavpn", "--version"); err == nil {
		snap.Version = out
	} else {
		snap.Version = strings.TrimSpace(out)
	}
	if out, err := run(6*time.Second, "mozillavpn", "status"); err == nil {
		snap.Status = out
		snap.DisplayStatus = summarizeStatus(out)
	} else {
		snap.Status = strings.TrimSpace(out)
		if snap.Status == "" {
			snap.Status = err.Error()
		}
		snap.DisplayStatus = summarizeStatus(snap.Status)
	}
	if out, err := run(3*time.Second, "systemctl", "is-active", "mozillavpn.service"); err == nil {
		snap.Service = out
	} else if strings.TrimSpace(out) != "" {
		snap.Service = strings.TrimSpace(out)
	}
	if out, err := run(3*time.Second, "systemctl", "is-active", "socksproxy.service"); err == nil {
		snap.ProxyService = out
	} else if strings.TrimSpace(out) != "" {
		snap.ProxyService = strings.TrimSpace(out)
	}
	if out, err := run(3*time.Second, "pgrep", "-a", "-f", "mozillavpn|socksproxy"); err == nil {
		snap.Processes = out
	}
	if snap.Installed && !strings.Contains(strings.ToLower(snap.Status), "not authenticated") {
		snap.Countries = loadCountries()
	}
	return snap
}

func loadCountries() []countryChoice {
	out, _ := run(8*time.Second, "mozillavpn", "servers", "--json", "--cache")
	if countries := countriesFromJSON(out); len(countries) > 0 {
		return countries
	}
	out, _ = run(10*time.Second, "mozillavpn", "servers", "--json")
	return countriesFromJSON(out)
}

func loadCmd() tea.Cmd {
	return func() tea.Msg {
		return snapshotMsg{data: loadSnapshot()}
	}
}

func tickCmd(interval time.Duration) tea.Cmd {
	return tea.Tick(interval, func(t time.Time) tea.Msg {
		return tickMsg(t)
	})
}

func nativeCmd(labelText string, args ...string) tea.Cmd {
	return func() tea.Msg {
		if len(args) == 0 {
			return commandDoneMsg{label: labelText, err: fmt.Errorf("missing mozillavpn command")}
		}
		if args[0] == "ui" {
			out, err := openMozillaVPNUI()
			return commandDoneMsg{label: labelText, output: out, err: err}
		}
		if args[0] == "login" {
			out, err := startLoginFlow()
			return commandDoneMsg{label: labelText, output: out, err: err}
		}
		out, err := run(25*time.Second, "mozillavpn", args...)
		return commandDoneMsg{label: labelText, output: out, err: err}
	}
}

func selectCountryCmd(choice countryChoice) tea.Cmd {
	return func() tea.Msg {
		if strings.TrimSpace(choice.Hostname) == "" {
			return commandDoneMsg{label: "select country", err: fmt.Errorf("no server hostname for %s", choice.Name)}
		}
		out, err := run(25*time.Second, "mozillavpn", "select", choice.Hostname)
		return commandDoneMsg{label: "select " + choice.Name, output: out, err: err}
	}
}

func (m model) Init() tea.Cmd {
	return tea.Batch(loadCmd(), tickCmd(m.interval))
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
		case "j", "J", "down":
			if len(m.data.Countries) > 0 {
				m.selected = min(m.selected+1, len(m.data.Countries)-1)
			}
		case "k", "K", "up":
			if len(m.data.Countries) > 0 {
				m.selected = max(m.selected-1, 0)
			}
		case "enter", "c", "C":
			if len(m.data.Countries) > 0 {
				choice := m.data.Countries[m.selected]
				m.running = "select " + choice.Name
				return m, selectCountryCmd(choice)
			}
		case "r", "R":
			m.loading = true
			return m, loadCmd()
		case "u", "U":
			m.running = "open ui"
			return m, nativeCmd("open ui", "ui")
		case "l", "L":
			m.running = "login"
			return m, nativeCmd("login", "login")
		case "a", "A":
			m.running = "activate"
			return m, nativeCmd("activate", "activate")
		case "d", "D":
			m.running = "deactivate"
			return m, nativeCmd("deactivate", "deactivate")
		}
	case tickMsg:
		if m.loading || m.running != "" {
			return m, tickCmd(m.interval)
		}
		m.loading = true
		return m, tea.Batch(loadCmd(), tickCmd(m.interval))
	case snapshotMsg:
		m.loading = false
		m.data = msg.data
		if len(m.data.Countries) == 0 {
			m.selected = 0
		} else if m.selected >= len(m.data.Countries) {
			m.selected = len(m.data.Countries) - 1
		}
	case commandDoneMsg:
		m.running = ""
		if msg.err != nil {
			m.output = fmt.Sprintf("%s failed: %s\n%s", msg.label, msg.err, strings.TrimSpace(msg.output))
		} else {
			m.output = fmt.Sprintf("%s: %s", msg.label, strings.TrimSpace(msg.output))
		}
		return m, loadCmd()
	}
	return m, nil
}

func (m model) View() tea.View {
	width := m.width
	if width <= 0 {
		width = 50
	}
	width = clamp(width-2, 42, 70)
	body := m.render(width - 4)
	view := tea.NewView(panel.Width(width).Render(body))
	view.AltScreen = true
	return view
}

func statusBadge(s vpnSnapshot) string {
	if !s.Installed || s.Err != "" {
		return errBadge.Render("MISSING")
	}
	lower := strings.ToLower(s.Status)
	if strings.Contains(lower, "not authenticated") {
		return warnBadge.Render("LOGIN")
	}
	if strings.Contains(lower, "connected") || strings.Contains(lower, "active") {
		return goodBadge.Render("ON")
	}
	return warnBadge.Render("READY")
}

func (m model) render(width int) string {
	s := m.data
	header := title.Render("> MOZILLA VPN")
	badge := statusBadge(s)
	headerGap := strings.Repeat(" ", max(1, width-lipgloss.Width(header)-lipgloss.Width(badge)))
	lines := []string{
		header + headerGap + badge,
		row("VERSION", emptyFallback(s.Version, "unknown"), width),
		row("DAEMON", emptyFallback(s.Service, "unknown"), width),
		row("PROXY", emptyFallback(s.ProxyService, "unknown"), width),
		row("CHECKED", s.CheckedAt.Format("15:04:05"), width),
		"",
		label.Render("STATUS"),
		card.Width(width).Render(wrap(emptyFallback(s.DisplayStatus, s.Err), width-2)),
	}
	if m.loading {
		lines = append(lines, "", quiet.Render("refreshing..."))
	}
	if m.running != "" {
		lines = append(lines, "", quiet.Render("running: "+m.running))
	}
	if strings.TrimSpace(m.output) != "" {
		lines = append(lines, "", label.Render("LAST"), card.Width(width).Render(wrap(m.output, width-2)))
	}
	lines = append(lines,
		"",
		label.Render("COUNTRIES"),
		m.renderCountries(width),
		"",
		label.Render("ACTIONS"),
		actionLine("u", "open ui", "l", "login", width),
		actionLine("a", "activate", "d", "deactivate", width),
		actionLine("j/k", "country", "c", "choose", width),
		actionLine("r", "refresh", "q", "quit", width),
	)
	return lipgloss.JoinVertical(lipgloss.Left, lines...)
}

func row(k, v string, width int) string {
	key := label.Width(10).Render(k)
	return key + " " + value.Render(truncate(v, max(8, width-12)))
}

func (m model) renderCountries(width int) string {
	if len(m.data.Countries) == 0 {
		return quiet.Render(wrap("Login, then refresh to load countries from Mozilla VPN servers.", width))
	}
	start := max(0, m.selected-2)
	if start+5 > len(m.data.Countries) {
		start = max(0, len(m.data.Countries)-5)
	}
	var lines []string
	for i := start; i < min(len(m.data.Countries), start+5); i++ {
		choice := m.data.Countries[i]
		cursor := " "
		style := quiet
		if i == m.selected {
			cursor = ">"
			style = value
		}
		line := fmt.Sprintf("%s %-26s %2d", cursor, truncate(choice.Name, 26), choice.Count)
		lines = append(lines, style.Render(truncate(line, width)))
	}
	return strings.Join(lines, "\n")
}

func actionLine(k1, v1, k2, v2 string, width int) string {
	left := fmt.Sprintf("%s %s", label.Render(k1), value.Render(v1))
	right := fmt.Sprintf("%s %s", label.Render(k2), value.Render(v2))
	gap := strings.Repeat(" ", max(2, width-lipgloss.Width(left)-lipgloss.Width(right)))
	return left + gap + right
}

func emptyFallback(valueText, fallback string) string {
	if strings.TrimSpace(valueText) == "" {
		return fallback
	}
	return strings.TrimSpace(valueText)
}

func wrap(s string, width int) string {
	width = max(12, width)
	words := strings.Fields(strings.ReplaceAll(s, "\n", " "))
	if len(words) == 0 {
		return ""
	}
	var lines []string
	line := ""
	for _, word := range words {
		if lipgloss.Width(line)+1+lipgloss.Width(word) > width && line != "" {
			lines = append(lines, line)
			line = word
		} else if line == "" {
			line = word
		} else {
			line += " " + word
		}
	}
	if line != "" {
		lines = append(lines, line)
	}
	return strings.Join(lines, "\n")
}

func truncate(s string, width int) string {
	s = strings.ReplaceAll(strings.TrimSpace(s), "\n", " ")
	if lipgloss.Width(s) <= width {
		return s
	}
	if width <= 3 {
		return s[:max(0, width)]
	}
	runes := []rune(s)
	out := ""
	for _, r := range runes {
		if lipgloss.Width(out)+lipgloss.Width(string(r))+1 > width {
			break
		}
		out += string(r)
	}
	return out + "..."
}

func firstLines(s string, limit int) string {
	var lines []string
	for _, line := range strings.Split(strings.TrimSpace(s), "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		lines = append(lines, line)
		if len(lines) >= limit {
			break
		}
	}
	return strings.Join(lines, "\n")
}

func processLines(s string, width int) string {
	var lines []string
	for _, line := range strings.Split(firstLines(s, 3), "\n") {
		lines = append(lines, truncate(line, width))
	}
	return strings.Join(lines, "\n")
}

func summarizeStatus(raw string) string {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return ""
	}
	fields := map[string]string{}
	for _, line := range strings.Split(raw, "\n") {
		key, valueText, ok := strings.Cut(line, ":")
		if !ok {
			continue
		}
		fields[strings.TrimSpace(key)] = strings.TrimSpace(valueText)
	}
	auth := fields["User status"]
	if auth == "" {
		return raw
	}
	parts := []string{"auth: " + auth}
	if vpnState := fields["VPN state"]; vpnState != "" {
		parts = append(parts, "vpn: "+vpnState)
	}
	if country := fields["Server country"]; country != "" {
		if city := fields["Server city"]; city != "" {
			country += " / " + city
		}
		parts = append(parts, "server: "+country)
	}
	if devices := fields["Active devices"]; devices != "" {
		parts = append(parts, "devices: "+devices)
	}
	return strings.Join(parts, "\n")
}

func openMozillaVPNUI() (string, error) {
	if out, err := run(2*time.Second, "pgrep", "-f", "^/usr/bin/mozillavpn ui$"); err == nil && strings.TrimSpace(out) != "" {
		go focusMozillaVPNWindow()
		return "focused existing native Mozilla VPN app", nil
	}
	candidates := [][]string{
		{"gtk-launch", "org.mozilla.vpn"},
		{"gio", "launch", "/usr/share/applications/org.mozilla.vpn.desktop"},
		{"mozillavpn", "ui"},
	}
	for _, candidate := range candidates {
		if _, err := exec.LookPath(candidate[0]); err != nil {
			continue
		}
		if err := startDetached(filepath.Join(os.TempDir(), "cento-mozilla-vpn-ui.log"), candidate[0], candidate[1:]...); err != nil {
			return "", err
		}
		go focusMozillaVPNWindow()
		return "launched native Mozilla VPN app via " + strings.Join(candidate, " "), nil
	}
	return "", fmt.Errorf("no launcher found for Mozilla VPN UI")
}

func startLoginFlow() (string, error) {
	if status, err := run(4*time.Second, "mozillavpn", "status"); err == nil {
		lower := strings.ToLower(status)
		if strings.Contains(lower, "user status: authenticated") && !strings.Contains(lower, "not authenticated") {
			out, focusErr := openMozillaVPNUI()
			if focusErr != nil {
				return "already authenticated", focusErr
			}
			return "already authenticated\n" + out, nil
		}
	}
	logPath := filepath.Join(os.TempDir(), "cento-mozilla-vpn-login.log")
	logFile, err := os.Create(logPath)
	if err != nil {
		return "", err
	}
	cmd := exec.Command("mozillavpn", "login")
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		logFile.Close()
		return "", err
	}
	stderr, err := cmd.StderrPipe()
	if err != nil {
		logFile.Close()
		return "", err
	}
	if err := cmd.Start(); err != nil {
		logFile.Close()
		return "", err
	}

	lines := make(chan string, 32)
	done := make(chan error, 1)
	var mu sync.Mutex
	writeLine := func(line string) {
		mu.Lock()
		defer mu.Unlock()
		fmt.Fprintln(logFile, line)
	}
	scan := func(reader io.Reader) {
		scanner := bufio.NewScanner(reader)
		scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)
		for scanner.Scan() {
			line := scanner.Text()
			writeLine(line)
			select {
			case lines <- line:
			default:
			}
		}
	}
	go scan(stdout)
	go scan(stderr)
	go func() {
		err := cmd.Wait()
		writeLine(fmt.Sprintf("[mozillavpn login exited: %v]", err))
		mu.Lock()
		logFile.Close()
		mu.Unlock()
		done <- err
	}()

	var seen []string
	timer := time.NewTimer(10 * time.Second)
	defer timer.Stop()
	for {
		select {
		case line := <-lines:
			seen = append(seen, line)
			if url := urlPat.FindString(line); url != "" {
				url = strings.TrimRight(url, ".,)")
				if err := openURL(url); err != nil {
					return fmt.Sprintf("auth URL ready\n%s\nlog: %s", url, logPath), err
				}
				return fmt.Sprintf("opened auth URL in browser\nlog: %s", logPath), nil
			}
		case err := <-done:
			text := strings.Join(seen, "\n")
			if text == "" {
				text = "mozillavpn login exited without an auth URL"
			}
			if err != nil {
				return text + "\nlog: " + logPath, err
			}
			return text + "\nlog: " + logPath, nil
		case <-timer.C:
			tail := strings.Join(lastN(seen, 3), "\n")
			if tail == "" {
				tail = "waiting for auth URL"
			}
			return "login process started\n" + tail + "\nlog: " + logPath, nil
		}
	}
}

func openURL(url string) error {
	candidates := [][]string{
		{"xdg-open", url},
		{"sensible-browser", url},
		{"firefox", url},
	}
	for _, candidate := range candidates {
		if _, err := exec.LookPath(candidate[0]); err != nil {
			continue
		}
		return startDetached(filepath.Join(os.TempDir(), "cento-mozilla-vpn-open-url.log"), candidate[0], candidate[1:]...)
	}
	return fmt.Errorf("no browser launcher found")
}

func startDetached(logPath string, name string, args ...string) error {
	logFile, err := os.OpenFile(logPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o600)
	if err != nil {
		return err
	}
	cmd := exec.Command(name, args...)
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	cmd.Stdout = logFile
	cmd.Stderr = logFile
	if err := cmd.Start(); err != nil {
		logFile.Close()
		return err
	}
	go func() {
		_ = cmd.Wait()
		_ = logFile.Close()
	}()
	return nil
}

func focusMozillaVPNWindow() {
	time.Sleep(900 * time.Millisecond)
	_, _ = run(2*time.Second, "i3-msg", `[class="(?i)^Mozilla VPN$"] focus`)
}

func lastN(lines []string, n int) []string {
	if len(lines) <= n {
		return lines
	}
	return lines[len(lines)-n:]
}

func countriesFromJSON(raw string) []countryChoice {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return nil
	}
	var payload any
	decoder := json.NewDecoder(strings.NewReader(raw))
	decoder.UseNumber()
	if err := decoder.Decode(&payload); err != nil {
		return nil
	}
	var servers []serverChoice
	collectServers(payload, serverChoice{}, &servers)
	return groupCountries(servers)
}

func collectServers(valueAny any, inherited serverChoice, out *[]serverChoice) {
	switch value := valueAny.(type) {
	case []any:
		for _, item := range value {
			collectServers(item, inherited, out)
		}
	case map[string]any:
		current := inherited
		hasCities := hasAnyKey(value, "cities", "city")
		hasServers := hasAnyKey(value, "servers")
		if text := firstString(value, "country", "countryName", "country_name", "countryCode", "country_code"); text != "" {
			current.Country = text
		}
		if text := firstString(value, "city", "cityName", "city_name"); text != "" {
			current.City = text
		}
		if text := firstString(value, "name"); text != "" {
			if hasCities || hasAnyKey(value, "countryCode", "country_code") {
				current.Country = text
			} else if hasServers || current.Country != "" {
				current.City = text
			}
		}
		if host := firstString(value, "hostname", "hostName", "host_name", "serverHostname", "server_hostname", "server"); host != "" && current.Country != "" {
			current.Hostname = host
			*out = append(*out, current)
		}
		for _, child := range value {
			collectServers(child, current, out)
		}
	}
}

func groupCountries(servers []serverChoice) []countryChoice {
	byName := map[string]countryChoice{}
	for _, server := range servers {
		name := strings.TrimSpace(server.Country)
		host := strings.TrimSpace(server.Hostname)
		if name == "" || host == "" {
			continue
		}
		choice := byName[name]
		if choice.Name == "" {
			choice.Name = name
			choice.Hostname = host
		}
		choice.Count++
		byName[name] = choice
	}
	countries := make([]countryChoice, 0, len(byName))
	for _, choice := range byName {
		countries = append(countries, choice)
	}
	sort.Slice(countries, func(i, j int) bool {
		return strings.ToLower(countries[i].Name) < strings.ToLower(countries[j].Name)
	})
	return countries
}

func firstString(values map[string]any, keys ...string) string {
	for _, key := range keys {
		for actual, value := range values {
			if normalizeKey(actual) == normalizeKey(key) {
				if text, ok := value.(string); ok {
					return strings.TrimSpace(text)
				}
			}
		}
	}
	return ""
}

func hasAnyKey(values map[string]any, keys ...string) bool {
	for actual := range values {
		for _, key := range keys {
			if normalizeKey(actual) == normalizeKey(key) {
				return true
			}
		}
	}
	return false
}

func normalizeKey(key string) string {
	key = strings.ToLower(key)
	key = strings.ReplaceAll(key, "_", "")
	key = strings.ReplaceAll(key, "-", "")
	return key
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

func printSummary() error {
	s := loadSnapshot()
	if s.Err != "" {
		return fmt.Errorf("%s", s.Err)
	}
	fmt.Println(emptyFallback(s.Version, "Mozilla VPN"))
	fmt.Println(emptyFallback(s.Status, "No status output."))
	fmt.Printf("mozillavpn.service: %s\n", emptyFallback(s.Service, "unknown"))
	return nil
}

func printCountries() error {
	countries := loadCountries()
	if len(countries) == 0 {
		return fmt.Errorf("no countries available; login and refresh Mozilla VPN server data first")
	}
	for _, country := range countries {
		fmt.Printf("%-28s %3d %s\n", country.Name, country.Count, country.Hostname)
	}
	return nil
}

func selectCountryByName(query string) error {
	query = strings.TrimSpace(strings.ToLower(query))
	if query == "" {
		return fmt.Errorf("country name is required")
	}
	countries := loadCountries()
	for _, country := range countries {
		if strings.Contains(strings.ToLower(country.Name), query) {
			out, err := run(30*time.Second, "mozillavpn", "select", country.Hostname)
			if strings.TrimSpace(out) != "" {
				fmt.Println(out)
			}
			return err
		}
	}
	return fmt.Errorf("country not found: %s", query)
}

func main() {
	args := os.Args[1:]
	if len(args) > 0 && !strings.HasPrefix(args[0], "-") {
		switch args[0] {
		case "status":
			if err := printSummary(); err != nil {
				fmt.Fprintln(os.Stderr, err)
				os.Exit(1)
			}
			return
		case "countries":
			if err := printCountries(); err != nil {
				fmt.Fprintln(os.Stderr, err)
				os.Exit(1)
			}
			return
		case "select", "country", "select-country":
			if err := selectCountryByName(strings.Join(args[1:], " ")); err != nil {
				fmt.Fprintln(os.Stderr, err)
				os.Exit(1)
			}
			return
		case "ui", "open-ui":
			out, err := openMozillaVPNUI()
			if out != "" {
				fmt.Println(out)
			}
			if err != nil {
				fmt.Fprintln(os.Stderr, err)
				os.Exit(1)
			}
			return
		case "login":
			out, err := startLoginFlow()
			if out != "" {
				fmt.Println(out)
			}
			if err != nil {
				fmt.Fprintln(os.Stderr, err)
				os.Exit(1)
			}
			return
		case "activate", "deactivate":
			out, err := run(30*time.Second, "mozillavpn", args[0])
			if strings.TrimSpace(out) != "" {
				fmt.Println(out)
			}
			if err != nil {
				fmt.Fprintln(os.Stderr, err)
				os.Exit(1)
			}
			return
		}
	}

	fs := flag.NewFlagSet("mozilla-vpn-tui", flag.ExitOnError)
	once := fs.Bool("once", false, "render once and exit")
	interval := fs.Duration("interval", 8*time.Second, "refresh interval")
	fs.Parse(args)

	model := model{interval: *interval, loading: true}
	if *once || !isTTY() {
		model.loading = false
		model.data = loadSnapshot()
		model.width = 52
		fmt.Println(model.render(48))
		return
	}

	program := tea.NewProgram(model)
	if _, err := program.Run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
