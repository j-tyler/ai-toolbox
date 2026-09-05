#!/bin/sh
# Combine race-enabled Go tests with instrumented production CLI subprocesses.
set -eu
cd "$(dirname "$0")/.."
mkdir -p .tools
work=$(mktemp -d .tools/coverage.XXXXXX)
work=$(cd "$work" && pwd)
mkdir "$work/unit" "$work/cli" "$work/merged"
go test -race -covermode=atomic -coverprofile="$work/unit.out" ./... -args -test.gocoverdir="$work/unit"
SENDY_COVERAGE_DIR="$work/cli" GOFLAGS="${GOFLAGS:-} -covermode=atomic" python3 tests/interface.py
go tool covdata merge -pcombine -i="$work/unit,$work/cli" -o="$work/merged"
go tool covdata textfmt -i="$work/merged" -o="$work/combined.out"
go tool cover -func="$work/combined.out"
printf '\nCoverage evidence: %s\n' "$work"
