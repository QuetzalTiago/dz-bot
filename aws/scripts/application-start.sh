#!/bin/bash
# Install dependencies and launch the bot. Note: for a production deployment a
# process supervisor (systemd unit, or the Docker `restart: unless-stopped`
# policy in docker-compose.yml) should own the process lifecycle so it is
# restarted on crash. This script backgrounds the process for the CodeDeploy
# ApplicationStart hook, which must return promptly.
set -euo pipefail

APP_DIR="/dz-bot"
cd "${APP_DIR}"

python3 -m pip install --no-cache-dir -r requirements.txt

nohup python3 bot.py > output.txt 2> error.txt < /dev/null &
