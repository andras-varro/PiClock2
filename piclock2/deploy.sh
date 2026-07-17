#!/bin/bash
# Deploy PiClock 2 to the Pi via rsync over ssh.
#
#   ./deploy.sh                       # default target below
#   ./deploy.sh pi@host:/path         # override target
#
# The on-device config.toml (holding the Mapbox key) and runtime logs/caches are
# excluded, so a deploy never clobbers device-local state.

set -euo pipefail

TARGET="${1:-pi@192.168.50.56:/home/pi/piclock2}"
SRC="$(cd "$(dirname "$0")" && pwd)/"

echo "Deploying $SRC -> $TARGET"
rsync -avz --delete \
	--exclude 'config.toml' \
	--exclude '__pycache__/' \
	--exclude '*.pyc' \
	--exclude '*.log' \
	--exclude '_*.png' \
	--exclude '_*.jpg' \
	--exclude 'one-call-4.txt' \
	--exclude '.git/' \
	"$SRC" "$TARGET"

echo "Done. Restart the app on the Pi to pick up changes."
