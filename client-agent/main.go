package main

import (
	"bytes"
	"crypto/ed25519"
	"crypto/rand"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"time"
)

const agentVersion = "0.1.0"

type agentState struct {
	Server     string
	PrivateKey string
	PublicKey  string
	PairedAt   string
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: makia-client-agent install | makia://...")
		os.Exit(2)
	}
	arg := strings.TrimSpace(os.Args[1])
	if arg == "install" {
		if err := installAgent(); err != nil {
			fatal(err)
		}
		fmt.Println("Makia Client Agent installed for the current Windows user.")
		return
	}
	if strings.HasPrefix(strings.ToLower(arg), "makia://") {
		if err := handleURI(arg); err != nil {
			fatal(err)
		}
		return
	}
	fatal(errors.New("unsupported command"))
}

func fatal(err error) {
	fmt.Fprintln(os.Stderr, "Makia Client Agent:", err)
	os.Exit(1)
}

func handleURI(raw string) error {
	u, err := url.Parse(raw)
	if err != nil {
		return fmt.Errorf("invalid Makia URI: %w", err)
	}
	switch strings.ToLower(u.Host) {
	case "pair":
		return handlePair(u)
	case "connect":
		return handleConnect(u)
	default:
		return fmt.Errorf("unsupported Makia action %q", u.Host)
	}
}

func normalizeServer(raw string) (string, error) {
	u, err := url.Parse(strings.TrimSpace(raw))
	if err != nil || u.Hostname() == "" {
		return "", errors.New("invalid control-plane URL")
	}
	if u.User != nil || u.RawQuery != "" || u.Fragment != "" {
		return "", errors.New("control-plane URL contains unsupported components")
	}
	if u.Scheme != "https" {
		ip := net.ParseIP(u.Hostname())
		loopback := u.Hostname() == "localhost" || (ip != nil && ip.IsLoopback())
		if u.Scheme != "http" || !loopback {
			return "", errors.New("control plane must use HTTPS; HTTP is allowed only for localhost development")
		}
	}
	u.Path = ""
	u.RawPath = ""
	return strings.TrimRight(u.String(), "/"), nil
}

func statePath() (string, error) {
	root, err := os.UserConfigDir()
	if err != nil {
		return "", err
	}
	dir := filepath.Join(root, "MakiaClient")
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return "", err
	}
	return filepath.Join(dir, "agent.json"), nil
}

func loadOrCreateState() (*agentState, error) {
	path, err := statePath()
	if err != nil {
		return nil, err
	}
	raw, err := os.ReadFile(path)
	if err == nil {
		var state agentState
		if json.Unmarshal(raw, &state) == nil && state.PrivateKey != "" && state.PublicKey != "" {
			return &state, nil
		}
	}
	pub, priv, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		return nil, err
	}
	state := &agentState{
		PrivateKey: base64.RawURLEncoding.EncodeToString(priv),
		PublicKey:  base64.RawURLEncoding.EncodeToString(pub),
	}
	if err := saveState(state); err != nil {
		return nil, err
	}
	return state, nil
}

func saveState(state *agentState) error {
	path, err := statePath()
	if err != nil {
		return err
	}
	raw, err := json.MarshalIndent(state, "", "  ")
	if err != nil {
		return err
	}
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, raw, 0o600); err != nil {
		return err
	}
	if err := os.Rename(tmp, path); err != nil {
		_ = os.Remove(tmp)
		return err
	}
	return nil
}

func decodePrivate(state *agentState) (ed25519.PrivateKey, error) {
	raw, err := base64.RawURLEncoding.DecodeString(state.PrivateKey)
	if err != nil || len(raw) != ed25519.PrivateKeySize {
		return nil, errors.New("stored device key is invalid")
	}
	return ed25519.PrivateKey(raw), nil
}

func handlePair(u *url.URL) error {
	server, err := normalizeServer(u.Query().Get("server"))
	if err != nil {
		return err
	}
	token := strings.TrimSpace(u.Query().Get("token"))
	if !strings.HasPrefix(token, "mkp_") {
		return errors.New("invalid pairing token")
	}
	state, err := loadOrCreateState()
	if err != nil {
		return err
	}
	request := map[string]any{
		"pairing_token": token,
		"public_key":    state.PublicKey,
		"agent_version": agentVersion,
		"platform":      runtime.GOOS + "-" + runtime.GOARCH,
	}
	var response map[string]any
	if err := postJSON(server+"/api/client-agent/pair", request, &response); err != nil {
		return err
	}
	state.Server = server
	state.PairedAt = time.Now().UTC().Format(time.RFC3339)
	if err := saveState(state); err != nil {
		return err
	}
	fmt.Println("Makia Client Agent paired successfully.")
	return nil
}

func signatureMessage(grant, nonce string, timestamp int64) []byte {
	return []byte("makia-agent-v1\n" + grant + "\n" + nonce + "\n" + strconv.FormatInt(timestamp, 10))
}

func handleConnect(u *url.URL) error {
	server, err := normalizeServer(u.Query().Get("server"))
	if err != nil {
		return err
	}
	grant := strings.TrimSpace(u.Query().Get("grant"))
	if !strings.HasPrefix(grant, "mkg_") {
		return errors.New("invalid connect grant")
	}
	state, err := loadOrCreateState()
	if err != nil {
		return err
	}
	if state.Server == "" {
		return errors.New("Makia Agent is not paired")
	}
	if state.Server != server {
		return errors.New("connect grant belongs to a different Makia control plane")
	}
	priv, err := decodePrivate(state)
	if err != nil {
		return err
	}
	nonceRaw := make([]byte, 16)
	if _, err := rand.Read(nonceRaw); err != nil {
		return err
	}
	nonce := hex.EncodeToString(nonceRaw)
	timestamp := time.Now().Unix()
	signature := ed25519.Sign(priv, signatureMessage(grant, nonce, timestamp))
	request := map[string]any{
		"grant":     grant,
		"nonce":     nonce,
		"timestamp": timestamp,
		"signature": base64.RawURLEncoding.EncodeToString(signature),
	}
	var response map[string]any
	if err := postJSON(server+"/api/client-agent/redeem", request, &response); err != nil {
		return err
	}
	access, ok := response["access"].(map[string]any)
	if !ok {
		return errors.New("control plane returned an invalid access payload")
	}
	kind := strings.ToLower(stringValue(access["kind"]))
	if kind != "wireguard" {
		return fmt.Errorf("native adapter for %s is not enabled in this Agent build", kind)
	}
	profile, cleanup, err := materializeWireGuardProfile(access)
	if err != nil {
		return err
	}
	defer cleanup()
	if runtime.GOOS != "windows" {
		fmt.Println("WireGuard grant verified; Windows tunnel start is unavailable on this platform.")
		return nil
	}
	if err := connectWireGuardWindows(profile); err != nil {
		return fmt.Errorf("WireGuard adapter failed: %w", err)
	}
	fmt.Println("WireGuard tunnel service installed successfully.")
	return nil
}

func materializeWireGuardProfile(access map[string]any) (string, func(), error) {
	name := safeFilename(stringValue(access["native_filename"]))
	if name == "" || !strings.HasSuffix(strings.ToLower(name), ".conf") {
		name = "makia-wireguard.conf"
	}
	encoded := stringValue(access["native_content_b64"])
	if encoded == "" {
		return "", func() {}, errors.New("WireGuard profile content is missing")
	}
	data, err := base64.StdEncoding.DecodeString(encoded)
	if err != nil {
		return "", func() {}, errors.New("invalid WireGuard profile payload")
	}
	if len(data) == 0 || len(data) > 1024*1024 {
		return "", func() {}, errors.New("invalid WireGuard profile size")
	}
	tmpDir, err := os.MkdirTemp("", "makia-agent-*")
	if err != nil {
		return "", func() {}, err
	}
	cleanup := func() { _ = os.RemoveAll(tmpDir) }
	path := filepath.Join(tmpDir, name)
	if err := os.WriteFile(path, data, 0o600); err != nil {
		cleanup()
		return "", func() {}, err
	}
	return path, cleanup, nil
}

var safeNamePattern = regexp.MustCompile("[^A-Za-z0-9_.-]+")

func safeFilename(value string) string {
	name := safeNamePattern.ReplaceAllString(filepath.Base(strings.TrimSpace(value)), "-")
	name = strings.Trim(name, ".-")
	if len(name) > 96 {
		name = name[:96]
	}
	return name
}

func stringValue(value any) string {
	text, _ := value.(string)
	return text
}

func connectWireGuardWindows(profile string) error {
	wireguard := filepath.Join(os.Getenv("ProgramFiles"), "WireGuard", "wireguard.exe")
	if _, err := os.Stat(wireguard); err != nil {
		found, lookErr := exec.LookPath("wireguard.exe")
		if lookErr != nil {
			return errors.New("WireGuard for Windows is not installed")
		}
		wireguard = found
	}
	escapePS := func(value string) string { return strings.ReplaceAll(value, "'", "''") }
	script := fmt.Sprintf(
		"Start-Process -FilePath '%s' -ArgumentList '/installtunnelservice','%s' -Verb RunAs -Wait",
		escapePS(wireguard),
		escapePS(profile),
	)
	return exec.Command("powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script).Run()
}

func installAgent() error {
	if runtime.GOOS != "windows" {
		return errors.New("automatic makia:// registration is implemented for Windows only")
	}
	current, err := os.Executable()
	if err != nil {
		return err
	}
	root := os.Getenv("LOCALAPPDATA")
	if root == "" {
		root, err = os.UserConfigDir()
		if err != nil {
			return err
		}
	}
	dir := filepath.Join(root, "MakiaClient")
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return err
	}
	target := filepath.Join(dir, "makia-client-agent.exe")
	if !samePath(current, target) {
		raw, err := os.ReadFile(current)
		if err != nil {
			return err
		}
		tmp := target + ".tmp"
		if err := os.WriteFile(tmp, raw, 0o700); err != nil {
			return err
		}
		if err := os.Rename(tmp, target); err != nil {
			_ = os.Remove(tmp)
			return err
		}
	}
	return registerWindowsURIHandler(target)
}

func samePath(left, right string) bool {
	a, errA := filepath.Abs(left)
	b, errB := filepath.Abs(right)
	return errA == nil && errB == nil && strings.EqualFold(filepath.Clean(a), filepath.Clean(b))
}

func registerWindowsURIHandler(exe string) error {
	key := "HKCU\\Software\\Classes\\makia"
	commandValue := fmt.Sprintf("\"%s\" \"%%1\"", exe)
	commands := [][]string{
		{"ADD", key, "/ve", "/d", "URL:Makia Client Protocol", "/f"},
		{"ADD", key, "/v", "URL Protocol", "/d", "", "/f"},
		{"ADD", key + "\\DefaultIcon", "/ve", "/d", exe + ",0", "/f"},
		{"ADD", key + "\\shell\\open\\command", "/ve", "/d", commandValue, "/f"},
	}
	for _, args := range commands {
		out, err := exec.Command("reg.exe", args...).CombinedOutput()
		if err != nil {
			return fmt.Errorf("register makia URI handler: %s: %w", strings.TrimSpace(string(out)), err)
		}
	}
	return nil
}

func postJSON(endpoint string, request any, response any) error {
	body, err := json.Marshal(request)
	if err != nil {
		return err
	}
	req, err := http.NewRequest(http.MethodPost, endpoint, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", "MakiaClientAgent/"+agentVersion)
	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(io.LimitReader(resp.Body, 5*1024*1024))
	if err != nil {
		return err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		var detail map[string]any
		_ = json.Unmarshal(raw, &detail)
		if text := stringValue(detail["detail"]); text != "" {
			return errors.New(text)
		}
		return fmt.Errorf("control plane returned HTTP %d", resp.StatusCode)
	}
	if response != nil {
		if err := json.Unmarshal(raw, response); err != nil {
			return err
		}
	}
	return nil
}
