package main

import (
	"encoding/base64"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestNormalizeServerRequiresHTTPSOutsideLoopback(t *testing.T) {
	if _, err := normalizeServer("http://vpn.example.test"); err == nil {
		t.Fatal("expected remote HTTP control plane to be rejected")
	}
	got, err := normalizeServer("https://vpn.example.test/client-app/")
	if err != nil {
		t.Fatal(err)
	}
	if got != "https://vpn.example.test" {
		t.Fatalf("unexpected normalized server: %s", got)
	}
	local, err := normalizeServer("http://127.0.0.1:8787")
	if err != nil {
		t.Fatal(err)
	}
	if local != "http://127.0.0.1:8787" {
		t.Fatalf("unexpected localhost URL: %s", local)
	}
}

func TestNormalizeServerRejectsCredentialsAndQuery(t *testing.T) {
	for _, raw := range []string{
		"https://user:pass@example.test",
		"https://example.test?token=x",
		"https://example.test#fragment",
	} {
		if _, err := normalizeServer(raw); err == nil {
			t.Fatalf("expected rejection for %s", raw)
		}
	}
}

func TestSignatureMessageContract(t *testing.T) {
	got := string(signatureMessage("mkg_test", "nonce-001", 1700000000))
	want := "makia-agent-v1\nmkg_test\nnonce-001\n1700000000"
	if got != want {
		t.Fatalf("signature message mismatch:\n%s", got)
	}
}

func TestSafeFilename(t *testing.T) {
	cases := map[string]string{
		"client.conf":        "client.conf",
		"../../evil.conf":    "evil.conf",
		"my profile?.conf":   "my-profile-.conf",
		"..":                 "",
		"":                   "",
	}
	for input, want := range cases {
		if got := safeFilename(input); got != want {
			t.Fatalf("safeFilename(%q)=%q want %q", input, got, want)
		}
	}
}

func TestMaterializeWireGuardProfileIsTemporary(t *testing.T) {
	content := "[Interface]\nPrivateKey = secret\nAddress = 10.0.0.2/32\n"
	access := map[string]any{
		"native_filename":    "../../client.conf",
		"native_content_b64": base64.StdEncoding.EncodeToString([]byte(content)),
	}
	path, cleanup, err := materializeWireGuardProfile(access)
	if err != nil {
		t.Fatal(err)
	}
	if filepath.Base(path) != "client.conf" {
		t.Fatalf("unexpected profile name %s", path)
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if string(raw) != content {
		t.Fatal("profile content mismatch")
	}
	dir := filepath.Dir(path)
	cleanup()
	if _, err := os.Stat(dir); !os.IsNotExist(err) {
		t.Fatalf("temporary profile directory still exists: %v", err)
	}
}

func TestMaterializeWireGuardProfileRejectsOversizedPayload(t *testing.T) {
	raw := strings.Repeat("x", 1024*1024+1)
	_, _, err := materializeWireGuardProfile(map[string]any{
		"native_filename":    "large.conf",
		"native_content_b64": base64.StdEncoding.EncodeToString([]byte(raw)),
	})
	if err == nil {
		t.Fatal("expected oversized profile rejection")
	}
}

func TestStringValueDoesNotCoerceUnexpectedTypes(t *testing.T) {
	if got := stringValue(123); got != "" {
		t.Fatalf("unexpected coercion: %q", got)
	}
	if got := stringValue("wireguard"); got != "wireguard" {
		t.Fatalf("unexpected string value: %q", got)
	}
}
