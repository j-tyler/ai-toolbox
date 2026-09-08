package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"
	"unicode/utf8"
)

// Keep assignments ordered: decoding into a map would silently lose duplicates.
type parameter struct{ key, value string }

func readParamsFile(path string) ([]parameter, error) {
	invalid := func(err error) ([]parameter, error) {
		return nil, advise(fmt.Errorf("invalid file %q: %w", path, err), "Check the parameter file path, permissions, and content. Supply a UTF-8 JSON object of strings or dotenv assignments; see sendy help template render. Use --params-file PATH once, without --set.")
	}
	info, err := os.Stat(path)
	if err != nil {
		return invalid(err)
	}
	if !info.Mode().IsRegular() {
		return invalid(errors.New("expected a regular file"))
	}
	b, err := os.ReadFile(path)
	if err != nil {
		return invalid(err)
	}
	if !utf8.Valid(b) {
		return invalid(errors.New("text must be valid UTF-8"))
	}
	source := strings.TrimLeft(string(b), " \t\r\n")
	var parameters []parameter
	// JSON-looking content is never retried as dotenv after a JSON error.
	if source != "" && strings.ContainsRune("{[\"", rune(source[0])) {
		parameters, err = jsonParameters(source)
	} else {
		parameters, err = dotenvParameters(string(b))
	}
	if err != nil {
		return invalid(err)
	}
	return parameters, nil
}

func jsonParameters(source string) ([]parameter, error) {
	d := json.NewDecoder(strings.NewReader(source))
	opening, err := d.Token()
	if err != nil {
		return nil, err
	}
	if opening != json.Delim('{') {
		return nil, errors.New("JSON must be a flat object with string values")
	}
	parameters := []parameter{}
	for d.More() {
		key, err := d.Token()
		if err != nil {
			return nil, err
		}
		var raw json.RawMessage
		if err = d.Decode(&raw); err != nil {
			return nil, err
		}
		// Unmarshalling null directly into a string would silently accept it.
		if len(raw) == 0 || raw[0] != '"' {
			return nil, fmt.Errorf("JSON field %q must have a string value", key)
		}
		var value string
		if err = json.Unmarshal(raw, &value); err != nil {
			return nil, err
		}
		parameters = append(parameters, parameter{key.(string), value})
	}
	if _, err = d.Token(); err != nil {
		return nil, err
	}
	if _, err = d.Token(); err != io.EOF {
		return nil, errors.New("unexpected content after JSON object")
	}
	return parameters, nil
}

func dotenvParameters(source string) ([]parameter, error) {
	source = strings.ReplaceAll(source, "\r\n", "\n")
	if strings.ContainsAny(source, "\r\x00\ufeff") {
		return nil, errors.New("dotenv does not allow bare CR, NUL, or a UTF-8 BOM")
	}
	lines := strings.Split(source, "\n")
	parameters := []parameter{}
	for i := 0; i < len(lines); i++ {
		line := strings.TrimLeft(lines[i], " \t")
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		lineNumber := i + 1
		invalid := func(reason string) ([]parameter, error) {
			return nil, fmt.Errorf("dotenv line %d: %s", lineNumber, reason)
		}
		key, value, ok := strings.Cut(line, "=")
		if !ok || strings.ContainsAny(key, "#\"'") {
			return invalid("expected KEY=VALUE")
		}
		key = strings.Trim(key, " \t")
		// Trim first so a field named export is not mistaken for the prefix.
		if strings.HasPrefix(key, "export ") || strings.HasPrefix(key, "export\t") {
			key = strings.TrimLeft(key[len("export"):], " \t")
		}
		value = strings.TrimLeft(value, " \t")
		if value == "" || (value[0] != '\'' && value[0] != '"') {
			value, _, _ = strings.Cut(value, "#")
			parameters = append(parameters, parameter{key, strings.TrimRight(value, " \t")})
			continue
		}
		quote := value[0]
		var decoded strings.Builder
		for pos := 1; ; pos++ {
			if pos == len(value) {
				i++
				if i == len(lines) {
					return invalid("unterminated quoted value")
				}
				decoded.WriteByte('\n')
				value, pos = lines[i], -1
				continue
			}
			c := value[pos]
			if c == quote {
				tail := strings.TrimLeft(value[pos+1:], " \t")
				if tail != "" && tail[0] != '#' {
					return invalid("only whitespace or a # comment may follow a quoted value")
				}
				break
			}
			if quote == '"' && c == '\\' {
				pos++
				if pos == len(value) {
					return invalid("incomplete escape in double-quoted value; line continuation is unsupported")
				}
				switch value[pos] {
				case '\\', '"':
					c = value[pos]
				case 'n':
					c = '\n'
				case 'r':
					c = '\r'
				case 't':
					c = '\t'
				default:
					return invalid(fmt.Sprintf("unsupported double-quoted escape \\%c", value[pos]))
				}
			}
			decoded.WriteByte(c)
		}
		parameters = append(parameters, parameter{key, decoded.String()})
	}
	return parameters, nil
}
