#!/usr/bin/env bash
# Run the palette2theme test suite (stdlib unittest, no dependencies).
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
exec nice timeout 600 python3 -m unittest discover -s tests -t . "$@"
