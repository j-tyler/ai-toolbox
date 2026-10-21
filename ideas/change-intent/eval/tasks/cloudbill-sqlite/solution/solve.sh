#!/usr/bin/env bash
# Oracle solution: overlay the reference repository onto the workspace (the seed keeps every file the overlay does not replace).
set -euo pipefail
cp -r /solution/repo/. /app/
