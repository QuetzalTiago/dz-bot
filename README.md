# Discord Bot

This Discord bot is designed to provide both entertainment and utility functionalities to the users of a Discord server. The bot is designed in Python using the Discord.py library and is highly modular with a distinct set of services handling its diverse functionalities.

## Features:

### 1. **Music Commands:**

- **Play**: The bot can play songs in a voice channel. Trigger this functionality with either `play [song_name/link]` or `p [song_name/link]`.
- **Skip**: If you're not in the mood for the current song, simply skip it with `skip` or `s`.

- **Loop**: Want to keep listening to the same song? Use `loop` to loop the current song.

- **Stop**: If you want the bot to stop playing music and leave the channel, use `stop`.

- **Clear**: Clear the current queue with the `clear` command.

- **Queue**: Check the current songs in the queue with `queue` or `q`.

### 2. **Utility Commands:**

- **Purge**: Need to clean up the chat? Use the `purge` command to clean up the bot's messages and commands requested.

- **Restart**: You can restart the bot using the `restart` command.

- **Help**: If you need a list of all the available commands and their functionalities, just type `help`.

- **Btc**: Check the current Bitcoin price with `btc`.

- **Emoji**: Enhance your messages with the `emoji` command.

- **Chess**: Challenge your friends to a game of chess with the `chess` command.

## Setup

1. Copy `config.example.json` to `config.json` and fill in your secrets, **or**
   provide them via environment variables (recommended for production). Every
   config value can be overridden by an env var:
   - Secrets: `DZ_SECRET_<UPPER_SNAKE>` (e.g. `DZ_SECRET_DISCORD_TOKEN`).
   - Top-level keys: `DZ_<UPPER_SNAKE>` (e.g. `DZ_PREFIX`).
   - Database: `DZ_DATABASE_URL` or `DZ_DB_HOST` / `DZ_DB_USER` /
     `DZ_DB_PASSWORD` / `DZ_DB_NAME`.
   - Optional: `DZ_LOG_LEVEL`, `DZ_SENTRY_DSN`, `DZ_AUTO_PURGE`,
     `DZ_ENABLE_CEDULA`.

2. Install dependencies and run:

   ```bash
   pip install -r requirements.txt
   python bot.py
   ```

   Or with Docker Compose (provide secrets via a `.env` file):

   ```bash
   docker compose up --build
   ```

## Development

```bash
pip install -r requirements-dev.txt
ruff check .
pytest
```

## Privileged commands

`restart` requires the bot owner or a server administrator. `purge` requires the
Manage Messages permission. The automatic channel purge is opt-in
(`DZ_AUTO_PURGE`). The national-ID (`cedula`) lookup is disabled by default and
must be explicitly enabled with `DZ_ENABLE_CEDULA`; it is restricted to the bot
owner. See `PRIVACY.md` for the data the bot stores and the `my_data` /
`forget_me` user controls.

## Legal / Terms of Service notice

The music features download audio via `yt-dlp` and resolve Spotify links to
YouTube, and lyrics are scraped from Genius. These approaches may violate the
terms of service of those platforms and are **not** suitable for a commercial
offering without licensed alternatives (e.g. a licensed audio provider). Review
with legal counsel before charging for the service.

## Diagram

![DZ-Bot Diagram](https://github.com/QuetzalTiago/dz-bot/blob/main/diagram.png)
