package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"regexp"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"
)

var version = "v0.1.0-dev"
var idPattern = regexp.MustCompile(`^[a-z][0-9]{2}$`)
var decimal = regexp.MustCompile(`^[0-9]+$`)

func main() { os.Exit(run(os.Args[1:], os.Stdin, os.Stdout, os.Stderr)) }
func run(args []string, in io.Reader, out, diagnostics io.Writer) int {
	err := execute(args, in, out)
	if err == nil {
		return 0
	}
	fmt.Fprintln(diagnostics, "sendy: "+err.Error())
	if errors.Is(err, errClosed) && len(args) > 0 && args[0] == "submit" {
		return 2
	}
	return 1
}
func positive(value, label string) (int, error) {
	n, err := strconv.Atoi(value)
	if err != nil || !decimal.MatchString(value) || n <= 0 {
		return 0, fmt.Errorf("%s must be a positive decimal integer", label)
	}
	return n, nil
}
func identifiers(ids []string) error {
	if len(ids) == 0 {
		return errors.New("at least one conversation ID is required")
	}
	seen := map[string]bool{}
	for _, id := range ids {
		if !idPattern.MatchString(id) {
			return fmt.Errorf("invalid conversation ID %q: expected one lowercase letter and two digits", id)
		}
		if seen[id] {
			return fmt.Errorf("duplicate conversation ID %q", id)
		}
		seen[id] = true
	}
	return nil
}
func validMessage(message string) error {
	if message == "" {
		return errors.New("message must not be empty")
	}
	if !utf8.ValidString(message) {
		return errors.New("message must be valid UTF-8")
	}
	return nil
}

type messageOptions struct {
	name string
	sets []string
}

func options(args []string, render bool) (messageOptions, error) {
	o := messageOptions{}
	for len(args) > 0 {
		flag := args[0]
		if flag != "--template" && flag != "--set" {
			return o, fmt.Errorf("unexpected argument %q", flag)
		}
		if len(args) < 2 {
			return o, fmt.Errorf("%s requires a value", flag)
		}
		value := args[1]
		args = args[2:]
		if flag == "--template" {
			if render || o.name != "" {
				return o, errors.New("--template must occur once, on submit or reply")
			}
			if value == "" {
				return o, errors.New("--template requires a name")
			}
			o.name = value
		} else {
			o.sets = append(o.sets, value)
		}
	}
	if !render && o.name == "" && len(o.sets) > 0 {
		return o, errors.New("--set requires --template")
	}
	return o, nil
}

func execute(args []string, in io.Reader, out io.Writer) error {
	started := time.Now()
	if len(args) == 0 {
		return errors.New("usage: sendy create|submit|reply|wait|close|template (see README.md)")
	}
	cmd := args[0]
	args = args[1:]
	if cmd == "--version" && len(args) == 0 {
		_, err := fmt.Fprintln(out, "sendy "+version)
		return err
	}
	if cmd == "template" {
		if len(args) == 1 && args[0] == "validate" {
			return validateTemplates()
		}
		if len(args) == 2 && args[0] == "fields" {
			_, fields, err := namedTemplate(args[1])
			if err != nil {
				return fmt.Errorf("%w\nNo output was produced.", err)
			}
			return json.NewEncoder(out).Encode(fields)
		}
		if len(args) >= 2 && args[0] == "render" {
			o, err := options(args[2:], true)
			if err != nil {
				return err
			}
			message, err := renderTemplate(args[1], o.sets, false)
			if err != nil {
				return err
			}
			_, err = io.WriteString(out, message)
			return err
		}
		return errors.New("usage: sendy template render NAME [--set KEY=VALUE ...] | template fields NAME | template validate")
	}
	var count int
	var ids []string
	var message string
	var deadline time.Time
	var err error
	switch cmd {
	case "create":
		if len(args) != 1 {
			return errors.New("usage: sendy create COUNT")
		}
		count, err = positive(args[0], "COUNT")
		if err != nil {
			return err
		}
	case "submit", "reply":
		if len(args) < 1 {
			return fmt.Errorf("usage: sendy %s ID [--template NAME [--set KEY=VALUE ...]]", cmd)
		}
		ids = args[:1]
		if err = identifiers(ids); err != nil {
			return err
		}
		o, e := options(args[1:], false)
		if e != nil {
			return e
		}
		if o.name != "" {
			message, err = renderTemplate(o.name, o.sets, true)
		} else {
			var b []byte
			b, err = io.ReadAll(in)
			message = string(b)
		}
		if err != nil {
			return err
		}
		if err = validMessage(message); err != nil {
			return err
		}
	case "wait":
		if len(args) < 3 || args[len(args)-2] != "--timeout" {
			return errors.New("usage: sendy wait ID [ID ...] --timeout MINUTES")
		}
		minutes, e := positive(args[len(args)-1], "MINUTES")
		if e != nil {
			return e
		}
		if uint64(minutes) > uint64((1<<63-1)/int64(time.Minute)) {
			return errors.New("MINUTES is too large")
		}
		deadline = started.Add(time.Duration(minutes) * time.Minute)
		ids = args[:len(args)-2]
	case "close":
		ids = args
	default:
		return fmt.Errorf("unknown command %q", cmd)
	}
	if cmd != "create" {
		if err = identifiers(ids); err != nil {
			return err
		}
	}
	s, err := openStore()
	if err != nil {
		return err
	}
	defer s.db.Close()
	switch cmd {
	case "create":
		ids, err = s.create(count)
		if err == nil {
			_, err = fmt.Fprintln(out, strings.Join(ids, " "))
		}
	case "submit":
		var round int
		round, err = s.submit(ids[0], message)
		if err == nil {
			message, err = s.awaitReply(ids[0], round)
			if err == nil {
				_, err = io.WriteString(out, message)
			}
		}
	case "reply":
		err = s.reply(ids[0], message)
	case "close":
		err = s.close(ids)
	case "wait":
		var snap snapshot
		snap, err = s.wait(ids, deadline)
		if err == nil {
			err = json.NewEncoder(out).Encode(snap)
		}
	}
	return err
}
