#!/usr/bin/env bash
# Oracle solution: overlay the reference repository onto the workspace (the seed's sample/ stays).
set -euo pipefail
cp -r /solution/repo/. /app/
