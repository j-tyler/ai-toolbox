package main

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestTemplateFields(t *testing.T) {
	dir := isolated(t)
	home := filepath.Join(dir, "home")
	t.Setenv("HOME", home)
	put(t, ".sendy/templates/review.txt", "{{.name}} {{ .filename }} {{.name}} {{.Z}} {{._x}} {{.a}}")
	put(t, ".sendy/templates/plain.txt", "Only fixed text.\n")
	for name, want := range map[string]string{
		"review": "[\"Z\",\"_x\",\"a\",\"filename\",\"name\"]\n",
		"plain":  "[]\n",
	} {
		var out, diag bytes.Buffer
		code := run([]string{"template", "fields", name}, brokenIO{}, &out, &diag)
		if code != 0 || out.String() != want || diag.Len() != 0 {
			t.Fatalf("fields %s: (%d, %q, %q), want %q", name, code, out.String(), diag.String(), want)
		}
	}
	checkError(t, execute([]string{"template", "fields", "review"}, brokenIO{}, brokenIO{}), "write failed")
	if _, err := os.Stat(home); !os.IsNotExist(err) {
		t.Fatalf("fields created state: %v", err)
	}
}

func TestTemplateFieldsErrors(t *testing.T) {
	dir := isolated(t)
	home := filepath.Join(dir, "home")
	t.Setenv("HOME", home)
	check := func(name, fragment string) {
		t.Helper()
		code, out, diag := call(t, "ignored", "template", "fields", name)
		_, _, renderDiag := call(t, "", "template", "render", name)
		if code != 1 || out != "" || !strings.Contains(diag, fragment) || diag != renderDiag {
			t.Fatalf("fields %q: (%d, %q, %q), render diagnostic %q", name, code, out, diag, renderDiag)
		}
	}
	check("review", "project root")
	put(t, ".sendy/templates/review.txt", "{{.filename}}")
	put(t, ".sendy/templates/plain.txt", "fixed")
	put(t, ".sendy/templates/IGNORE.md", "not a template")
	put(t, ".sendy/templates/nested/hidden.txt", "not a direct child")
	for _, name := range []string{"missing", "../review", "Review", ""} {
		check(name, "available templates: plain, review")
	}
	for _, source := range []string{"", string([]byte{255}), "line one\n{{.x", "line one\n{{if .x}}yes{{end}}"} {
		put(t, ".sendy/templates/invalid.txt", source)
		check("invalid", "invalid template")
	}
	for _, args := range [][]string{
		{"template", "fields"},
		{"template", "fields", "review", "extra"},
		{"template", "fields", "review", "--set", "filename=x"},
		{"template", "fields", "review", "--template", "plain"},
	} {
		code, out, diag := call(t, "ignored", args...)
		if code != 1 || out != "" || !strings.Contains(diag, "template fields NAME") || !strings.HasPrefix(diag, "sendy: usage:") {
			t.Fatalf("%v: (%d, %q, %q)", args, code, out, diag)
		}
	}
	if _, err := os.Stat(home); !os.IsNotExist(err) {
		t.Fatalf("fields errors created state: %v", err)
	}
}

func TestTemplateWithoutArguments(t *testing.T) {
	isolated(t)
	const result = "Review complete. No correctness issues found.\n"
	const instruction = "Review the staged files for missing tests."
	put(t, ".sendy/templates/result.txt", result)
	put(t, ".sendy/templates/next-task.txt", instruction)
	mustCall(t, "", "template", "validate")
	for name, want := range map[string]string{"result": result, "next-task": instruction} {
		if got := mustCall(t, "", "template", "render", name); got != want {
			t.Fatalf("render %s: got %q, want %q", name, got, want)
		}
	}

	id := strings.TrimSpace(mustCall(t, "", "create", "1"))
	s := testStore(t)
	done := make(chan struct{})
	var code int
	var out, diag string
	go func() {
		code, out, diag = call(t, "", "submit", id, "--template", "result")
		close(done)
	}()
	t.Cleanup(func() {
		if err := s.close([]string{id}); err != nil {
			t.Error(err)
		}
		select {
		case <-done:
		case <-time.After(5 * time.Second):
			t.Error("submission did not exit after cleanup")
		}
	})
	ready(t, s, []string{id})
	snap, err := s.snapshot([]string{id})
	if err != nil || len(snap.Results) != 1 || snap.Results[0].Message != result {
		t.Fatalf("submitted result: %+v, error: %v", snap, err)
	}
	select {
	case <-done:
		t.Fatal("submit returned before a reply")
	default:
	}
	mustCall(t, "", "reply", id, "--template", "next-task")
	select {
	case <-done:
		if code != 0 || out != instruction || diag != "" {
			t.Fatalf("submit returned (%d, %q, %q)", code, out, diag)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("submit did not receive the reply")
	}
}

func TestTemplateRendering(t *testing.T) {
	dir := isolated(t)
	code, out, diag := call(t, "", "template", "render", "review")
	if code != 1 || out != "" || !strings.Contains(diag, filepath.Join(dir, ".sendy", "templates")) || !strings.Contains(diag, "project root") {
		t.Fatal(code, out, diag)
	}
	put(t, ".sendy/templates/review.txt", "Review {{.filename}} by {{ .name }}. {{.filename}} | {{.Optional_2}}")
	put(t, ".sendy/templates/plain.txt", "plain text without fields\n")
	put(t, ".sendy/templates/IGNORE.md", "{{bad}}")
	put(t, ".sendy/templates/nested/x.txt", "{{bad}}")
	mustCall(t, "", "template", "validate")
	got := mustCall(t, "", "template", "render", "review", "--set", "filename=a=b", "--set", "name={{.literal}} $100 \"世界\"", "--set", "Optional_2=")
	want := "Review a=b by {{.literal}} $100 \"世界\". a=b | "
	if got != want {
		t.Fatalf("%q != %q", got, want)
	}
	if got = mustCall(t, "", "template", "render", "plain"); got != "plain text without fields\n" {
		t.Fatal(got)
	}
	code, out, diag = call(t, "", "template", "render", "review", "--set", "filenmae=x", "--set", "name=a", "--set", "name=b", "--set", "bad", "--set", "1key=x")
	for _, fragment := range []string{`template "review" could not be rendered.`, "Missing fields: Optional_2, filename", "Unexpected fields: filenmae", "Duplicate fields: name", "Expected fields: Optional_2, filename, name", "Malformed assignments", "No output was produced."} {
		if !strings.Contains(diag, fragment) {
			t.Errorf("missing %q in %s", fragment, diag)
		}
	}
	if code != 1 || out != "" {
		t.Fatal(code, out)
	}
	code, out, diag = call(t, "", "template", "render", "../review")
	if code != 1 || out != "" || !strings.Contains(diag, `unknown template "../review"`) || !strings.Contains(diag, "available templates: plain, review") {
		t.Fatal(code, out, diag)
	}
	id := strings.TrimSpace(mustCall(t, "", "create", "1"))
	s := testStore(t)
	code, out, diag = call(t, "ignored", "submit", id, "--template", "review", "--set", "filenmae=x")
	if code != 1 || out != "" || !strings.Contains(diag, "No message was sent.") {
		t.Fatal(code, out, diag)
	}
	snap, err := s.snapshot([]string{id})
	if err != nil || len(snap.Pending) != 1 {
		t.Fatal(snap, err)
	}
	// Template mode does not even read a deliberately failing input stream.
	done := make(chan error, 1)
	go func() { done <- execute([]string{"submit", id, "--template", "plain"}, brokenIO{}, brokenIO{}) }()
	ready(t, s, []string{id})
	put(t, ".sendy/templates/plain.txt", "edited")
	snap, err = s.snapshot([]string{id})
	if err != nil || snap.Results[0].Message != "plain text without fields\n" {
		t.Fatal(snap, err)
	}
	mustCall(t, "stdin ignored", "reply", id, "--template", "plain")
	checkError(t, <-done, "write failed")
	checkError(t, execute([]string{"template", "render", "plain"}, brokenIO{}, brokenIO{}), "write failed")
	put(t, ".sendy/templates/empty.txt", "{{.value}}")
	code, out, diag = call(t, "", "template", "render", "empty", "--set", "value=")
	if code != 1 || out != "" || !strings.Contains(diag, "message must not be empty") {
		t.Fatal(code, out, diag)
	}
	code, out, diag = call(t, "", "template", "render", "empty", "--set", "value="+string([]byte{255}))
	if code != 1 || out != "" || !strings.Contains(diag, "valid UTF-8") {
		t.Fatal(code, out, diag)
	}
}

func TestTemplateValidation(t *testing.T) {
	isolated(t)
	checkError(t, validateTemplates(), "missing")
	if err := os.MkdirAll(".sendy/templates", 0700); err != nil {
		t.Fatal(err)
	}
	if err := validateTemplates(); err != nil {
		t.Fatal(err)
	}
	cases := map[string]string{
		"empty": "", "utf8": string([]byte{255}), "unclosed": "line one\n{{.x", "if": "{{if .x}}yes{{end}}", "range": "{{range .x}}{{.x}}{{end}}", "nested": "{{.x.y}}", "function": "{{printf \"x\"}}", "include": "{{template \"x\"}}", "define": "{{define \"x\"}}x{{end}}", "comment": "{{/* comment */}}", "pipe": "{{.x | html}}", "trim": "{{- .x}}", "variable": "{{$x}}", "unicode": "{{.é}}", "index": "{{index . \"x\"}}", "dot": "{{.}}", "literal": "{{\"text\"}}", "assignment": "{{$x := .x}}", "block": "{{block \"x\" .}}x{{end}}",
	}
	for name, value := range cases {
		put(t, ".sendy/templates/"+name+".txt", value)
		_, _, err := loadTemplate(".sendy/templates/" + name + ".txt")
		checkError(t, err, "invalid template")
	}
	put(t, ".sendy/templates/Bad_Name.txt", "valid text")
	put(t, ".sendy/templates/-bad.txt", "{{bad}}")
	err := validateTemplates()
	for name := range cases {
		checkError(t, err, name+".txt")
	}
	checkError(t, err, "invalid template filename")
	checkError(t, err, "unclosed.txt:2:1")
	_, _, err = loadTemplate(".sendy/templates/missing.txt")
	checkError(t, err, "template file")
	_, err = renderTemplate("if", nil)
	checkError(t, err, "unsupported action")
	if err = os.RemoveAll(".sendy/templates"); err != nil {
		t.Fatal(err)
	}
	put(t, ".sendy/templates", "file")
	if err = validateTemplates(); err == nil {
		t.Fatal("not-directory accepted")
	}
}
