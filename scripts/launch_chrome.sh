#!/usr/bin/env bash
# Launches Chrome with remote debugging enabled so the agent can attach to it.
set -euo pipefail

PORT="${CHROME_REMOTE_DEBUG_PORT:-9222}"

OS="$(uname -s)"
case "$OS" in
  Darwin)
    open -a "Google Chrome" --args --remote-debugging-port="$PORT"
    ;;
  Linux)
    google-chrome --remote-debugging-port="$PORT" &
    ;;
  *)
    echo "Unsupported OS: $OS. On Windows, run: chrome.exe --remote-debugging-port=$PORT"
    exit 1
    ;;
esac

echo "Chrome launched with remote debugging on port $PORT"
