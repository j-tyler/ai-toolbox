package main

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"text/template"
	"unicode/utf8"
)

var namePattern = regexp.MustCompile(`^[a-z0-9][a-z0-9_-]*$`)
var fieldPattern = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]*$`)
var actionPattern = regexp.MustCompile(`^\{\{[ \t\r\n]*\.([A-Za-z_][A-Za-z0-9_]*)[ \t\r\n]*\}\}$`)

func templateFiles() (string, []os.DirEntry, error) {
	cwd, err := os.Getwd()
	if err != nil {
		return "", nil, err
	}
	dir := filepath.Join(cwd, ".sendy", "templates")
	entries, err := os.ReadDir(dir)
	if errors.Is(err, os.ErrNotExist) {
		return dir, nil, fmt.Errorf("template directory %s is missing; run from the project root (and run make sendy)", dir)
	}
	return dir, entries, err
}
func loadTemplate(path string) (*template.Template, []string, error) {
	info, err := os.Stat(path)
	if err != nil {
		return nil, nil, fmt.Errorf("template file %s: %w", path, err)
	}
	if !info.Mode().IsRegular() {
		return nil, nil, fmt.Errorf("template file %s: expected a regular file", path)
	}
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, nil, fmt.Errorf("template file %s: %w", path, err)
	}
	source := string(b)
	invalid := func(offset int, reason string) (*template.Template, []string, error) {
		line := strings.Count(source[:offset], "\n") + 1
		last := strings.LastIndex(source[:offset], "\n")
		return nil, nil, fmt.Errorf("invalid template %s:%d:%d: %s", path, line, offset-last, reason)
	}
	if len(b) == 0 {
		return invalid(0, "text must not be empty")
	}
	if !utf8.Valid(b) {
		return invalid(0, "text must be valid UTF-8")
	}
	fields := map[string]bool{}
	for pos := 0; pos < len(source); {
		start := strings.Index(source[pos:], "{{")
		if start < 0 {
			break
		}
		start += pos
		end := strings.Index(source[start+2:], "}}")
		if end < 0 {
			return invalid(start, "unclosed template action")
		}
		end += start + 4
		match := actionPattern.FindStringSubmatch(source[start:end])
		if match == nil {
			return invalid(start, "unsupported action; only simple named substitutions such as {{.filename}} are allowed")
		}
		fields[match[1]] = true
		pos = end
	}
	t, err := template.New(filepath.Base(path)).Option("missingkey=error").Parse(source)
	if err != nil {
		return invalid(0, err.Error())
	}
	names := make([]string, 0, len(fields))
	for name := range fields {
		names = append(names, name)
	}
	sort.Strings(names)
	return t, names, nil
}
func fieldList(fields []string) string {
	if len(fields) == 0 {
		return "(none)"
	}
	return strings.Join(fields, ", ")
}
func namedTemplate(name string) (*template.Template, []string, error) {
	dir, entries, err := templateFiles()
	if err != nil {
		return nil, nil, err
	}
	available := []string{}
	found := false
	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".txt") {
			continue
		}
		n := strings.TrimSuffix(entry.Name(), ".txt")
		if namePattern.MatchString(n) {
			available = append(available, n)
			if n == name {
				found = true
			}
		}
	}
	if !found {
		return nil, nil, fmt.Errorf("unknown template %q in %s; available templates: %s", name, dir, fieldList(available))
	}
	return loadTemplate(filepath.Join(dir, name+".txt"))
}
func renderTemplate(name string, sets []string, sending bool) (string, error) {
	ending := "No output was produced."
	if sending {
		ending = "No message was sent."
	}
	fail := func(err error) (string, error) { return "", fmt.Errorf("%w\n%s", err, ending) }
	t, expected, err := namedTemplate(name)
	if err != nil {
		return fail(err)
	}
	values := map[string]string{}
	duplicates := map[string]bool{}
	malformed := []string{}
	for _, set := range sets {
		key, value, ok := strings.Cut(set, "=")
		if !ok || !fieldPattern.MatchString(key) {
			malformed = append(malformed, set)
			continue
		}
		if _, ok = values[key]; ok {
			duplicates[key] = true
		}
		values[key] = value
	}
	missing, unexpected, duplicate := []string{}, []string{}, []string{}
	required := map[string]bool{}
	for _, key := range expected {
		required[key] = true
		if _, ok := values[key]; !ok {
			missing = append(missing, key)
		}
	}
	for key := range values {
		if !required[key] {
			unexpected = append(unexpected, key)
		}
	}
	for key := range duplicates {
		duplicate = append(duplicate, key)
	}
	sort.Strings(unexpected)
	sort.Strings(duplicate)
	if len(missing)+len(unexpected)+len(duplicate)+len(malformed) > 0 {
		detail := fmt.Sprintf("template %q could not be rendered.\nMissing fields: %s\nUnexpected fields: %s\nDuplicate fields: %s\nExpected fields: %s", name, fieldList(missing), fieldList(unexpected), fieldList(duplicate), fieldList(expected))
		if len(malformed) > 0 {
			detail += fmt.Sprintf("\nMalformed assignments (expected KEY=VALUE with a valid field name): %q", malformed)
		}
		return fail(errors.New(detail))
	}
	var out bytes.Buffer
	if err = t.Execute(&out, values); err != nil {
		return fail(err)
	}
	if err = validMessage(out.String()); err != nil {
		return fail(err)
	}
	return out.String(), nil
}
func validateTemplates() error {
	dir, entries, err := templateFiles()
	if err != nil {
		return err
	}
	problems := []string{}
	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".txt") {
			continue
		}
		path := filepath.Join(dir, entry.Name())
		name := strings.TrimSuffix(entry.Name(), ".txt")
		if !namePattern.MatchString(name) {
			problems = append(problems, fmt.Sprintf("invalid template filename %s: use lowercase letters, digits, hyphens or underscores, starting with a letter or digit", path))
		}
		if _, _, err = loadTemplate(path); err != nil {
			problems = append(problems, err.Error())
		}
	}
	if len(problems) > 0 {
		return errors.New(strings.Join(problems, "\n"))
	}
	return nil
}
