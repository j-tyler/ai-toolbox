package main

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestParamsFileRendering(t *testing.T) {
	dir := isolated(t)
	home := filepath.Join(dir, "unused-home")
	t.Setenv("HOME", home)
	put(t, ".sendy/templates/fields.txt", "[{{.name}}]|[{{.value}}]")
	put(t, ".sendy/templates/plain.txt", "fixed text")
	cases := []struct{ name, content, want string }{
		{"collections", `{
  "name": {"items": ["世界", 9007199254740993, -0, 1.2300e+40, true, false, null], "meta": {}},
  "value": [{"escaped": "quote: \" slash: \\ newline: \n unicode: \u4e16", "literal": "{{.name}} <>&"}, [], {"key": 1, "key": 2}]
}`, `[{"items":["世界",9007199254740993,-0,1.2300e+40,true,false,null],"meta":{}}]|[[{"escaped":"quote: \" slash: \\ newline: \n unicode: \u4e16","literal":"{{.name}} <>&"},[],{"key":1,"key":2}]]`},
		{"empty-collections", `{"name": {}, "value": []}`, `[{}]|[[]]`},
		{"mixed-values", `{"name": "Alice\n世界", "value": {"deep": [[{"ready": true}]]}}`, "[Alice\n世界]|[{\"deep\":[[{\"ready\":true}]]}]"},
		{"json.env", " \r\n{\"name\":\"世界\",\"value\":\"a=b\\n\\t\\r\\\"\\\\\"}\n", "[世界]|[a=b\n\t\r\"\\]"},
		{"dotenv.json", "# heading\r\n export name = Alice # note\r\nvalue= a=b=c  #more\r\n", "[Alice]|[a=b=c]"},
		{"no-suffix", "name=''\nvalue=\n", "[]|[]"},
		{"quotes", "name=\"  #= $HOME ${USER} $(touch sentinel) {{.literal}}  \"\nvalue='\\n\\t'", "[  #= $HOME ${USER} $(touch sentinel) {{.literal}}  ]|[\\n\\t]"},
		{"multiline", "name='first  \r\n  second # part' # after\r\nvalue=\"one\\n\\t\\r\\\"\\\\\r\ntwo\"", "[first  \n  second # part]|[one\n\t\r\"\\\ntwo]"},
		{"prose", "name=don't expand $HOME\nvalue=C:\\path\\file", "[don't expand $HOME]|[C:\\path\\file]"},
		{"--help", "name=x\nvalue=y", "[x]|[y]"},
		{"-h", `{"name":"x","value":"y"}`, "[x]|[y]"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			put(t, tc.name, tc.content)
			var out, diag bytes.Buffer
			code := run([]string{"template", "render", "fields", "--params-file", tc.name}, brokenIO{}, &out, &diag)
			if code != 0 || out.String() != tc.want || diag.Len() != 0 {
				t.Fatalf("(%d, %q, %q), want %q", code, out.String(), diag.String(), tc.want)
			}
		})
	}
	for _, content := range []string{"", " \t\r\n# only comments\n", "{}"} {
		put(t, "empty", content)
		if got := mustCall(t, "", "template", "render", "plain", "--params-file", "empty"); got != "fixed text" {
			t.Fatal(got)
		}
		code, out, diag := call(t, "", "template", "render", "fields", "--params-file", "empty")
		if code != 1 || out != "" || !strings.Contains(diag, "Missing fields: name, value") {
			t.Fatal(code, out, diag)
		}
	}
	for _, path := range []string{home, "sentinel"} {
		if _, err := os.Stat(path); !os.IsNotExist(err) {
			t.Fatalf("unexpected file/state %s: %v", path, err)
		}
	}
}

func TestParamsFileExportField(t *testing.T) {
	isolated(t)
	put(t, ".sendy/templates/export.txt", "[{{.export}}]")
	for _, content := range []string{
		"export=Alice", "export = Alice", "export\t=Alice",
		"export export=Alice", "export\texport \t= Alice",
	} {
		t.Run(content, func(t *testing.T) {
			put(t, "parameters", content)
			if got := mustCall(t, "", "template", "render", "export", "--params-file", "parameters"); got != "[Alice]" {
				t.Fatal(got)
			}
		})
	}
	put(t, "parameters", "export = Alice\nexport export=Bob")
	code, out, diag := call(t, "", "template", "render", "export", "--params-file", "parameters")
	if code != 1 || out != "" || !strings.Contains(diag, "Duplicate fields: export") {
		t.Fatal(code, out, diag)
	}
}

func TestInvalidParamsFiles(t *testing.T) {
	dir := isolated(t)
	home := filepath.Join(dir, "unused-home")
	t.Setenv("HOME", home)
	put(t, ".sendy/templates/fields.txt", "[{{.name}}]|[{{.value}}]")
	cases := []struct{ content, detail string }{
		{`{"name":"x",}`, "invalid file"},
		{`{"name":"x"`, "invalid file"},
		{"{\nname=x\nvalue=y", "invalid file"},
		{`{"name":"x"} value=y`, "after JSON object"},
		{`{"name":"x"} {}`, "after JSON object"},
		{`{"name":null}`, "string, object, or array value"},
		{`{"name":12}`, "string, object, or array value"},
		{`{"name":true}`, "string, object, or array value"},
		{`{"name":false}`, "string, object, or array value"},
		{`{"name":{"inner":[1,]}}`, "invalid file"},
		{`{"name":[{"inner":}]}`, "invalid file"},
		{`{"name":[{"inner":true}]`, "invalid file"},
		{`[]`, "top-level object"},
		{`"name=x"`, "top-level object"},
		{`null`, "KEY=VALUE"},
		{`true`, "KEY=VALUE"},
		{`123`, "KEY=VALUE"},
		{`{"name":"x","na\u006de":"y","value":"z"}`, "Duplicate fields: name"},
		{`{"name":"x","na\u006de":{"inner":1},"value":[]}`, "Duplicate fields: name"},
		{`{"name":{},"name":[],"value":"z"}`, "Duplicate fields: name"},
		{`{"name":[],"name":"x","extra":{}}`, "Missing fields: value\nUnexpected fields: extra\nDuplicate fields: name"},
		{`{"name=x":{"inner":1},"value":[]}`, "Malformed assignments"},
		{`{"name=x":"y","value":"z"}`, "Malformed assignments"},
		{`{"1name":"x","value":"z"}`, "Malformed assignments"},
		{"name=x\nname=y\nvalue=z", "Duplicate fields: name"},
		{"name=x\nexport name=y\nvalue=z", "Duplicate fields: name"},
		{"name=x\nextra=z", "Missing fields: value\nUnexpected fields: extra"},
		{"1name=x\nvalue=y", "Malformed assignments"},
		{"name\nvalue=y", "dotenv line 1"},
		{"name='unclosed\nvalue=y", "unterminated"},
		{"name=\"unclosed", "unterminated"},
		{"name=\"x\" trailing\nvalue=y", "follow a quoted value"},
		{"name='x' 'y'\nvalue=z", "follow a quoted value"},
		{`name="x\q"`, "unsupported double-quoted escape"},
		{"name=\"x\\\ny\"", "line continuation"},
		{"# comment\nnot an assignment", "dotenv line 2"},
		{"name=x\rvalue=y", "bare CR"},
		{"\ufeffname=x\nvalue=y", "BOM"},
		{"name=\x00\nvalue=y", "NUL"},
		{"name=\xff\nvalue=y", "UTF-8"},
	}
	for _, tc := range cases {
		put(t, "parameters", tc.content)
		for _, args := range [][]string{
			{"template", "render", "fields", "--params-file", "parameters"},
			{"submit", "a1000", "--template", "fields", "--params-file", "parameters"},
			{"reply", "a1000", "--template", "fields", "--params-file", "parameters"},
		} {
			var out, diag bytes.Buffer
			code := run(args, brokenIO{}, &out, &diag)
			if code != 1 || out.Len() != 0 || !strings.Contains(diag.String(), `invalid file "parameters"`) || !strings.Contains(diag.String(), tc.detail) {
				t.Fatalf("%q %v: (%d, %q, %q), want %q", tc.content, args, code, out.String(), diag.String(), tc.detail)
			}
		}
	}
	for _, path := range []string{"missing", ".sendy/templates"} {
		code, out, diag := call(t, "", "template", "render", "fields", "--params-file", path)
		if code != 1 || out != "" || !strings.Contains(diag, "invalid file") || !strings.Contains(diag, path) {
			t.Fatal(code, out, diag)
		}
	}
	put(t, ".sendy/templates/empty.txt", "{{.name}}")
	put(t, "parameters", `{"name":""}`)
	code, out, diag := call(t, "", "submit", "a1000", "--template", "empty", "--params-file", "parameters")
	if code != 1 || out != "" || !strings.Contains(diag, "message must not be empty") {
		t.Fatal(code, out, diag)
	}
	if _, err := os.Stat(home); !os.IsNotExist(err) {
		t.Fatalf("validation created state: %v", err)
	}
}

func TestParamsFileOptions(t *testing.T) {
	isolated(t)
	cases := []struct {
		flags []string
		want  string
	}{
		{[]string{"--params-file"}, "requires a value"},
		{[]string{"--params-file", ""}, "requires a path"},
		{[]string{"--params-file", "one", "--params-file", "two"}, "must occur once"},
		{[]string{"--set", "name=x", "--params-file", "one"}, "cannot be mixed"},
		{[]string{"--params-file", "one", "--set", "name=x"}, "cannot be mixed"},
	}
	for _, prefix := range [][]string{{"template", "render", "fields"}, {"submit", "a1000", "--template", "fields"}, {"reply", "a1000", "--template", "fields"}} {
		for _, tc := range cases {
			args := append(append([]string{}, prefix...), tc.flags...)
			code, out, diag := call(t, "", args...)
			if code != 1 || out != "" || !strings.Contains(diag, tc.want) {
				t.Fatal(args, code, out, diag)
			}
		}
	}
	for _, cmd := range []string{"submit", "reply"} {
		code, out, diag := call(t, "", cmd, "a1000", "--params-file", "one")
		if code != 1 || out != "" || !strings.Contains(diag, "--params-file requires --template") {
			t.Fatal(code, out, diag)
		}
	}
}
