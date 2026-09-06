package main

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

type unreadableHelpInput struct{ t *testing.T }

func (r unreadableHelpInput) Read([]byte) (int, error) {
	r.t.Fatal("help attempted to read stdin")
	return 0, nil
}

func TestHelpDiscovery(t *testing.T) {
	dir := isolated(t)
	var reference string
	for _, args := range [][]string{{"help"}, {"--help"}, {"-h"}, {"help", "--help"}, {"help", "-h"}, {"--help", "--help"}, {"-h", "--help", "-h"}} {
		var out, diag bytes.Buffer
		code := run(args, unreadableHelpInput{t}, &out, &diag)
		if code != 0 || diag.Len() != 0 || out.Len() == 0 {
			t.Fatalf("%v: (%d, %q, %q)", args, code, out.String(), diag.String())
		}
		if reference == "" {
			reference = out.String()
		} else if reference != out.String() {
			t.Fatalf("help aliases differ: %v", args)
		}
	}
	for _, fragment := range []string{"sendy create COUNT", "sendy submit ID", "sendy reply ID", "sendy wait ID", "sendy close ID", "sendy template render NAME", "sendy template fields NAME", "sendy template validate", "sendy --version", "NO timeout", `"pending"`, "EXIT CODES", "jq -e -j", "--set KEY=VALUE"} {
		if !strings.Contains(reference, fragment) {
			t.Errorf("full reference missing %q", fragment)
		}
	}
	if entries, err := os.ReadDir(dir); err != nil || len(entries) != 0 {
		t.Fatalf("help created local state: %v, %v", entries, err)
	}
	// Discovery must also work when conversation storage cannot be opened.
	put(t, filepath.Join(dir, ".sendy"), "not a directory")
	for _, args := range [][]string{{"help"}, {"submit", "--help"}, {"template", "render", "--help"}} {
		var out, diag bytes.Buffer
		if code := run(args, unreadableHelpInput{t}, &out, &diag); code != 0 || diag.Len() != 0 {
			t.Fatalf("help requires usable storage: %v: %d %s", args, code, &diag)
		}
	}
}

func TestHelpTopics(t *testing.T) {
	isolated(t)
	for _, topic := range []string{"create", "submit", "reply", "wait", "close", "template", "template render", "template fields", "template validate"} {
		words := strings.Fields(topic)
		want := mustCall(t, "", append([]string{"help"}, words...)...)
		for _, flag := range []string{"--help", "-h"} {
			for _, prefix := range [][]string{nil, {"help"}, {"--help"}, {"help", flag}} {
				args := append(append(append([]string{}, prefix...), words...), flag)
				var out, diag bytes.Buffer
				code := run(args, unreadableHelpInput{t}, &out, &diag)
				if code != 0 || diag.Len() != 0 || out.String() != want {
					t.Fatalf("%v: (%d,%q,%q)", args, code, out.String(), diag.String())
				}
			}
		}
		if !strings.Contains(want, "Usage: sendy "+topic) {
			t.Fatalf("missing topic usage for %q", topic)
		}
	}
	if got := mustCall(t, "", "submit", "k1007", "--help"); got != mustCall(t, "", "help", "submit") {
		t.Fatal("help after positional ID differs")
	}
	for _, args := range [][]string{{"help", "bogus"}, {"help", "submit", "extra"}, {"bogus", "--help"}, {"template", "bogus", "--help"}, {"help", "bogus", "--help"}, {"help", "submit", "extra", "-h"}} {
		code, out, diag := call(t, "", args...)
		if code != 1 || out != "" || !strings.Contains(diag, "unknown help topic") || !strings.Contains(diag, "sendy help") {
			t.Fatalf("%v: (%d,%q,%q)", args, code, out, diag)
		}
	}
	var diag bytes.Buffer
	if code := run([]string{"--help"}, unreadableHelpInput{t}, brokenIO{}, &diag); code != 1 || !strings.Contains(diag.String(), "stdout") || !strings.Contains(diag.String(), "No state was changed") {
		t.Fatalf("help output error: %d, %s", code, &diag)
	}
}

func TestHelpDoesNotStealOptionValues(t *testing.T) {
	isolated(t)
	put(t, ".sendy/templates/literal.txt", "{{.value}}")
	if got := mustCall(t, "", "template", "render", "literal", "--set", "value=--help"); got != "--help" {
		t.Fatal(got)
	}
	for _, args := range [][]string{{"submit", "k1007", "--template", "--help"}, {"template", "render", "literal", "--set", "-h"}, {"wait", "k1007", "--timeout", "--help"}} {
		code, out, _ := call(t, "", args...)
		if code != 1 || out != "" {
			t.Fatalf("option value was treated as help: %v: %d %q", args, code, out)
		}
	}
}
