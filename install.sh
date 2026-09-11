#!/bin/sh
# Run as the desktop user; only system package installation uses sudo.
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$script_dir/scripts/setup.py" "$@"
