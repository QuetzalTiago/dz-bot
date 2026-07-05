#!/bin/bash
# Stop only this bot's process, identified by its script path. The previous
# `pkill python` killed every Python process on the host, and `rm -rf /dz-bot/`
# wiped the whole application directory on every stop.
set -u

pkill -f "python3 bot.py" || true

# Give it a moment to exit gracefully, then force-kill if still running.
sleep 3
pkill -9 -f "python3 bot.py" || true

exit 0
