#!/bin/bash
# Fetch config from SSM and lock down its permissions. The previous version ran
# `chmod -R 777 /dz-bot/`, which made the secrets file world-readable/writable.
set -euo pipefail

APP_DIR="/dz-bot"
CONFIG_FILE="${APP_DIR}/config.json"
RUN_USER="ubuntu"

# Application code: owned by the run user, not world-writable.
chown -R "${RUN_USER}:${RUN_USER}" "${APP_DIR}"
chmod -R 750 "${APP_DIR}"

# Secrets from SSM (SecureString is decrypted with --with-decryption).
aws ssm get-parameter \
  --name "bot-config.json" \
  --with-decryption \
  --query "Parameter.Value" \
  --output text > "${CONFIG_FILE}"

# Only the run user may read the secrets file.
chown "${RUN_USER}:${RUN_USER}" "${CONFIG_FILE}"
chmod 600 "${CONFIG_FILE}"
