# dz-bot — Enterprise-Readiness Review

A full audit of the codebase (bot core, music subsystem, feature cogs, database layer, deployment pipeline) with the goal of turning this bot into a commercial, enterprise-grade product. Findings are ordered by severity, each with file/line references. A phased remediation roadmap closes the report.

**TL;DR:** the bot is a solid hobby project, but today it leaks every secret into its logs, lets any Discord user restart it or bulk-delete messages, can only serve one guild's music at a time, freezes its entire event loop on nearly every API call, ships to production with zero tests run, and has several verified crash-on-boot / crash-on-use bugs. None of these are unfixable — the roadmap below sequences them.

---

## 1. CRITICAL — Security & data protection

### 1.1 Every secret is logged in plaintext
`bot.py:162`

```python
config = json.load(f)
logger.info(f"Loaded config: {config}")
```

This dumps the **entire config** — Discord token, OpenAI/Gemini key, Spotify client secret, Lichess token, Steam key, Genius key, weather key — to `discord.log` (rotated on disk) and stdout, which docker-compose captures into json-file logs. Anyone with log access owns every credential. **Remove this line immediately and rotate all keys** (they must be assumed compromised).

### 1.2 No authorization on dangerous commands
There is not a single `@commands.has_permissions`, `@commands.is_owner`, or role check in the whole repository.

- `cogs/restart.py:11` — **any user** can run `restart`, which shells out to `aws/scripts/application-start.sh` via `subprocess.call` and kills the bot.
- `cogs/purge.py:30` — **any user** can run `purge`, deleting up to 100 messages (two `purge(limit=50)` calls). Additionally, `purge_job` (`purge.py:39`) auto-deletes messages in the "main channel" every 2 hours with no opt-in — a destructive default (see 3.4).

### 1.3 PII lookup command against a leak site
`cogs/ci.py` — the `cedula`/`ci` command lets any user query **Uruguayan national ID numbers** against `https://ci-uy.checkleaked.cc/{id}`. For a commercial product this is a privacy/compliance liability (GDPR-equivalent exposure, third-party leak-data sourcing). It is also unauthenticated, unthrottled, uses blocking `requests.get` with no timeout (`ci.py:29`), and has no error handling. **Recommend removing this command entirely** from any commercial offering.

### 1.4 Hardcoded root database credentials
- `cogs/database.py:242` — `db_url = "mysql+pymysql://root:root@db"` in source.
- `docker-compose.yml` — `MYSQL_ROOT_PASSWORD: root`.

The application connects as MySQL **root** with a trivial password baked into the repo. Create a dedicated least-privilege DB user and inject credentials via environment/secret manager.

### 1.5 Deployment scripts undermine host security
- `aws/scripts/install.sh` — `chmod -R 777 /dz-bot/` makes the SSM-fetched `config.json` (all secrets) world-readable/writable on the host.
- `aws/scripts/application-stop.sh` — `pkill python` kills **every Python process on the host**, not just the bot; `rm -rf /dz-bot/` wipes the app dir on every stop.
- `aws/scripts/application-start.sh` — backgrounds `python3 bot.py &` with no supervisor: no restart on crash, PID untracked.

### 1.6 Internal errors leaked to users
`football.py:137`, `ufc.py:196`, `formula1.py:114` send raw exception text (`f"Failed...: {e}"`) into Discord channels — information disclosure and a bad user experience. Log the traceback server-side; show users a generic message with a correlation ID.

---

## 2. CRITICAL — Verified crash bugs

These were verified by direct code reading this session; several fire on every boot or on first use.

| # | Location | Bug |
|---|----------|-----|
| 2.1 | `bot.py:45` | Calls `btc.check_and_notify_bitcoin_price_change.start()` — **no such attribute exists** (the task is `btc_price_task` in `btc.py:37`). `on_ready` raises `AttributeError` **on every startup**, so the presence-setting and restart-notification code after it never runs. |
| 2.2 | `bot.py:60` | `await db.set_startup_notification(None, None)` — the method is synchronous (`database.py:121`), so this raises `TypeError`. Worse, the method **always sets `notify_on_startup=True`**, so the flag can never be cleared even once fixed. |
| 2.3 | `state_machine.py:80,84` | `await player.pause()` / `await player.resume()` — both are sync methods (`player.py:87,92`), so pausing raises `TypeError` **inside the 2-second `tasks.loop`**, which has no error handler → **the music engine dies permanently the first time anyone pauses**. |
| 2.4 | Multiple | Un-awaited coroutines: `player.py:131` (`playlist.clear()` — the async `clear` at `playlist.py:169` shadows the sync one, so **the playlist is never actually cleared on stop**), `downloader.py:159` (`self.clear()` — queue never cleared), `downloader.py:112` (`state_machine.stop()`), `music.py:183` (`cog_failure(...)` in `skip_song`), `bot.py:102` (`self.close()` in `reset`). |
| 2.5 | `downloader.py:42-57` | `return songs` — `songs` is only assigned inside `if song_names:`; an empty Spotify result raises `UnboundLocalError` and kills the enqueue. Also returns a one-shot `map` object. |
| 2.6 | `bot.py:200-201` | `await bot.tree.sync()` is placed **after** `bot.start(token)`, which blocks until shutdown — **slash commands are never synced**. Combined with 3.6, slash invocation is broken bot-wide. |
| 2.7 | `bot.py:85` | `if member == self.user and after is None` — `after` is a `VoiceState`, never `None` (its `.channel` is). The "bot kicked from voice → stop music" path **never fires**, and there is no other voice-state reconciliation (see 3.2). |
| 2.8 | `player.py:41-43` | `all(song.message is not song.message for song in playlist.songs)` — the comprehension variable shadows the outer `song`; the expression is tautologically `False` whenever the playlist is non-empty. The intended message-cleanup check is broken. |

### 2.9 Background loops die silently and stay dead
No `tasks.loop` in the repo has an `@loop.error` handler (`handle_state`, `process_queue`, `update_user_durations`, `btc_price_task`, `purge_job`, `save_match`). In `discord.ext.tasks`, an unhandled exception **stops the loop permanently**. Any transient failure — a Discord 5xx, a `None` voice client, a yt-dlp hiccup — kills the state machine or the stats loop for the life of the process with no signal. This is the single most likely "the bot just stopped working" failure mode in production.

---

## 3. HIGH — Architecture blockers for a multi-tenant product

### 3.1 The music engine is single-guild
One `Music` cog instance holds **all** state for the whole process: one `Player.voice_client` (`player.py:16`), one `Playlist` (`playlist.py`), one `Downloader.queue` (`downloader.py:15`), one `StateMachine` state (`state_machine.py:17`). Consequences:

- The bot can play in **one guild at a time**. A `play` from guild B while guild A is active won't connect (join is gated on `State.DISCONNECTED`, `player.py:55`) and B's songs are appended to **guild A's playlist and voice channel**.
- Nothing is keyed by `guild_id`. An enterprise bot needs a `guild_id → GuildMusicState` map (or, better, a purpose-built audio node — see roadmap).

### 3.2 The state machine polls and desyncs from reality
- Playback is driven by a 2-second polling loop (`state_machine.py:55`) instead of discord.py's event-driven `after=` callback in `voice_client.play()`. Pause/resume take up to 2 s to apply; the "now playing" embed is edited every 2 s per song (`playlist.py:110-114`), hammering Discord's edit rate limits with a fake progress counter that drifts.
- State is tracked independently of the real `VoiceClient`. If Discord disconnects/moves the bot mid-song, `idle()` sees "not playing", transitions to `STOPPED`, and the next tick calls `voice_client.play()` on a dead/`None` client → `AttributeError` → loop dead (see 2.9).
- The transition table forbids `PLAYING → DISCONNECTED` (`state_machine.py:20-26`), so `player.stop()`'s own transition is silently rejected and correctness depends on call ordering in `music.stop` (`music.py:233-235`).
- If `voice_channel.connect()` fails, no transition happens and there is no `DISCONNECTED` case in the loop — songs download into a playlist that will never play (silent hang).

### 3.3 Blocking I/O throughout the async event loop
Every synchronous network/CPU call freezes the **entire bot** — all guilds, all commands, heartbeats:

- Sync `requests` in async handlers: `weather.py:32`, `btc.py:55` (also called from a **10-second task loop** — the loop blocks the bot every 10 s indefinitely), `steam.py:39,57`, `div.py:35`, `chess.py:83,145`, `football.py:41,64,80`, `formula1.py:32,61`, `ufc.py:40,52,69-72`, `ci.py:29`, `genius.py:18,26`.
- Blocking `spotipy` calls inside async methods (`spotify.py:16,25,37`) and blocking `ydl.extract_info` in `youtube.py:101`. (The heavy yt-dlp download *is* correctly offloaded via `run_in_executor` at `downloader.py:78,94` — the pattern was known but not applied elsewhere.)
- Synchronous PIL image work on the loop (`football.py:39-56`, `formula1.py:30-47`, `ufc.py combine_fighter_logos`).
- **No `timeout=` on a single request in the repo** — one hung upstream connection stalls the bot forever.
- `ufc.py:33-38` — `while True` issuing blocking requests with no iteration cap: if the API returns empty, the bot livelocks.

Fix: `aiohttp` (only `ai.py` uses it today) with timeouts, and `asyncio.to_thread` for PIL/yt-dlp.

### 3.4 Multi-guild assumptions broken in the core
`bot.py:88-97` sets `self.main_channel` to the first text channel **of the first guild** and stops. The 2-hour auto-purge (`purge.py:39-46`) then silently deletes messages there. Single-market assumptions also appear as a hardcoded `America/Montevideo` timezone in three cogs (`football.py:97-103`, `ufc.py:142-164`, `formula1.py:49-53`).

### 3.5 Database layer
- **Entirely synchronous SQLAlchemy on the event loop** (`cogs/database.py`) — every query blocks all guilds. Use async SQLAlchemy or executor offload.
- **Voice-hours tracking double-counts quadratically**: `update_user_durations` (`database.py:100-107`) adds the full elapsed-since-join **every hour without resetting the join time** — a user online 3 h is credited 1+2+3 = 6 h. Disconnects between ticks lose all accrued time (`bot.py:73-79` just deletes the entry). The leaderboard data is wrong.
- Task started in `__init__` (`database.py:25`) before `cog_load` creates `self.Session` — startup race → `AttributeError`.
- Session leaks: `update_user_duration` and `get_user_hours` have no `try/finally`; an exception leaks the connection.
- Errors logged at `INFO` level throughout; `get_chess_games` swallows exceptions and implicitly returns `None` (callers expecting a list crash).
- f-string DDL (`database.py:35,40`) — not exploitable today (constant `db_name`) but the injection anti-pattern.
- **No migrations** — schema managed only by `create_all`; any column change is silently ignored. Adopt Alembic.
- `Base.metadata.bind` (`database.py:51`) is deprecated; `StartupNotification` stores snowflake IDs as `Text` and re-casts to `int` (`bot.py:107-108`) — use `BigInteger`.

### 3.6 Hybrid/slash commands are structurally broken
Multiple cogs parse `ctx.message.content` with hardcoded slice offsets instead of declared parameters: `music.py:80-88` (assumes `play ` literally), `div.py:13`, `emoji.py:12` (hardcodes 6 characters — wrong for any other prefix), `chess.py:31`. For slash invocations `message.content` is empty, so these commands fail outright; they also break whenever the prefix length changes. Declare typed parameters and let discord.py parse.

### 3.7 AI cog — cost, abuse, and correctness
- **Prompt injection by design**: `ai.py:163` concatenates the system prompt and untrusted user text into a single user-role message. Use a proper `system` role message.
- **Conversation key mismatch (bug)**: stored by `ctx.message.author.id` (`ai.py:137`) but cleared by `ctx.channel.id` (`ai.py:147`) — **`newchat` never clears anything**, and the dict never shrinks (memory leak).
- **Unbounded growth**: `chat` appends every turn with no trimming or token cap — per-user cost grows without limit for the life of the process.
- No rate limiting, no spend caps, no content moderation, no handling of Discord's 2,000-character message limit (long completions raise HTTP 400), and errors go to `print()` (`ai.py:190,234`) instead of the logger.

### 3.8 Zero rate limiting anywhere
No `@commands.cooldown` or `max_concurrency` exists in the repo. Every command is spammable; the AI cog is unbounded spend. `btc` starts an **infinite 10-second loop** editing one message and polling Coinbase forever (`btc.py:36-45`), with `self.sent_message`/`self.request_message` as shared instance state that concurrent users clobber (`btc.py:18,24`).

### 3.9 Legal / ToS exposure (blocking for a paid product)
- Ripping YouTube audio with yt-dlp (`youtube.py:14-47`) violates YouTube ToS; commercializing it is a real enforcement risk.
- The Spotify-URL → YouTube-download flow (`downloader.py:42-57`) is textbook "stream-ripping" — DMCA exposure.
- Genius lyrics are **scraped from HTML** (`genius.py:26-45`), not licensed — publisher-rights violation.

Get legal review before charging money; the practical engineering answer is a licensed audio pipeline (e.g., Lavalink/Wavelink against permitted sources) — which also solves 3.1/3.2.

---

## 4. HIGH — Operations & delivery

- **CI deploys with zero verification**: `.github/workflows/deploy.yml` triggers AWS CodeDeploy on every push to `main` — no tests, no lint, and `--ignore-application-stop-failures` masks stop-hook errors. ~1,400 lines of tests exist but never run; `tests/purge_test.py:170` imports a nonexistent `purge_cog` module (broken at collection), and there is no pytest/pytest-asyncio configuration at all.
- **Unpinned dependencies**: `requirements.txt` pins nothing except `proto-plus==1.24.0.dev1` — a **dev pre-release**. Builds are non-reproducible. `ffmpeg` and `ffprobe` on PyPI are not the media binaries (those come from apt in the Dockerfile) — remove them.
- **Dev workflow shipped as production**: the Docker `ENTRYPOINT` is `watchmedo auto-restart` (a file-watching dev reloader), `docker-compose.yml` bind-mounts `./:/app` over the image, the container runs as **root**, there is no app healthcheck, and the compose file depends on a manually pre-created external network.
- **No global error handling or observability**: no `on_command_error` (command failures surface as raw tracebacks), no metrics, no alerting, no error tracker (e.g., Sentry). MP3s, `lyrics.txt`, and logs are written into the repo working directory; downloaded files are only cleaned up on the happy path (`music.py:47-57`), so disk usage grows unbounded across failures/restarts.
- Config handling: every cog independently opens and parses `config.json` (8+ copies of the same code); no environment-variable support; missing keys crash cog load with bare `KeyError`.

---

## 5. MEDIUM — Correctness & quality

- **weather.py**: rain **volume in mm** displayed as a probability — 2 mm renders as "200 %" (`weather.py:49,108`); `%H:%M %p` mixes 24-hour and AM/PM (`weather.py:117`); `fromtimestamp` uses the *server's* timezone for a queried city's sunrise/sunset; success reaction added even when the city isn't found; user input interpolated into the URL unencoded (`weather.py:31`, same in `div.py:36` — no `urlencode` anywhere in `cogs/`).
- **chess.py**: `save_match.start()` per game (`chess.py:77`) — a second concurrent game raises `RuntimeError: task is already launched`; `cog_load` cancels a task that was never started (`chess.py:15`).
- **Spotify**: playlists/albums silently truncated at 100 tracks — only the first `results["items"]` page is read (`spotify.py:25,37`); each song is resolved twice via yt-dlp (`youtube.py:73` then `:38`) — double the network cost.
- **downloader.py**: `enqueue` race — two near-simultaneous `play`s both see `process_queue` not running, both call `.start()` → unhandled `RuntimeError`; the direct `download_next_song()` call can also overlap a loop tick and double-pop the queue (`downloader.py:145-147`). Bare `except:` at `downloader.py:73,81,98` (also `music.py:264`) swallow everything including `CancelledError`.
- **song.py**: duplicate `upload_date` property (`song.py:50` vs `:66` — first is dead code, different return types); `get_progress_bar` divides by `info["duration"]` — livestreams/None → `ZeroDivisionError`.
- **playlist/UX**: shuffle picks a random index but the embed always shows `songs[0]` as "Next"; fixed `lyrics.txt` filename races across concurrent invocations and leaks on error (`music.py:159-167`).
- **div.py**: the `if not divine: raise` guard is unreachable — `next()` raises `StopIteration` first, swallowed by the broad `except` (`div.py:27,40-43`).
- **Deprecated/dated APIs**: `datetime.utcnow()` throughout (`bot.py:67,82`, `database.py:104`, `ufc.py:33`); `logger.warn` (`player.py:24`); `compose version: '3.8'` key is obsolete.
- **Duplication to consolidate**: config loading ×8 cogs; `add_white_background` copy-pasted verbatim (`football.py:39-56`, `formula1.py:30-47`); api-sports header builder ×3; Montevideo tz conversion ×3; the ⌛→✅/❌ reaction lifecycle hand-rolled in ~10 cogs (a decorator/context manager would standardize it); `leaderboard.py:26` does N+1 sequential `fetch_user` calls per render.
- **bot.py**: `initial_extensions` wrapped in a tuple then unwrapped with `[0]` (`bot.py:19,37`); `on_ready` uses `get_cog(...)` results without `None` checks; `tests/cog_template.py` is 41 lines of commented-out boilerplate committed to the repo.

---

## 6. Remediation roadmap

### Phase 0 — Stop the bleeding (hours)
1. Delete `bot.py:162` (config logging) and **rotate every credential**.
2. Add `@commands.is_owner()` / `has_permissions(administrator=True)` gates to `restart` and `purge`; disable the 2-hour auto-purge by default.
3. Remove (or hard-gate) the `cedula` PII command.
4. Fix the verified crashers: 2.1 (btc task name), 2.2 (`set_startup_notification` await + always-True flag), 2.3 (pause/resume awaits), 2.4 (five un-awaited coroutines), 2.5 (Spotify `UnboundLocalError`), 2.6 (move `tree.sync()` into `setup_hook`).
5. Pin `requirements.txt` (and drop `proto-plus` dev pin, fake `ffmpeg`/`ffprobe` entries).
6. Fix `application-stop.sh` (`pkill -f bot.py` at most; stop deleting the app dir) and drop `chmod -R 777`.

### Phase 1 — Reliability (days)
1. Replace all sync `requests`/spotipy/PIL/yt-dlp-metadata calls with `aiohttp` + `asyncio.to_thread`, **with timeouts everywhere**.
2. Move DB access to async SQLAlchemy (or executor), fix the voice-hours double-counting, add `try/finally` session handling, adopt Alembic.
3. Add `@loop.error` handlers with restart logic to every `tasks.loop`; add a global `on_command_error`.
4. Add `@commands.cooldown` to every command; cap AI conversation length and per-user spend; split messages >2,000 chars.
5. Centralize config into one loader with env-var overrides; move secrets to env/secret manager; dedicated non-root DB user.
6. Production Docker: non-root `USER`, plain `python bot.py` entrypoint (no watchmedo, no bind-mount), healthcheck, slim base image.
7. CI: run pytest + a linter (ruff) as a required gate **before** deploy; fix the broken `purge_test.py` import; add pytest-asyncio config.

### Phase 2 — Product architecture (weeks)
1. Per-guild music state (`guild_id → player/playlist/queue`); recommended: migrate playback to Lavalink/Wavelink — event-driven, battle-tested, multi-guild, and sidesteps the local-download model.
2. Replace the 2-second polling state machine with event-driven playback (`after=` callback) and reconcile against `on_voice_state_update`.
3. Per-guild configuration (prefix, announcement channel, purge opt-in, timezone) stored in the DB — remove `main_channel` and hardcoded Montevideo tz.
4. Observability: structured logging, Sentry (or equivalent), uptime/latency metrics, alerting.
5. Test coverage for the highest-risk paths: database, permissions, restart, music state transitions.

### Phase 3 — Commercial readiness
1. Legal review of audio sourcing and lyrics (3.9); switch to licensed sources.
2. Terms of service, privacy policy, and data-retention/erasure workflow for the user-tracking data (GDPR).
3. Gateway sharding (required beyond ~2,500 guilds) and horizontal scale-out plan.
4. Billing/entitlement layer (per-guild plans, feature flags) and an admin dashboard.

---

*Line numbers reference the repository state at the time of this review (branch point: commit `39c5472`). Items 2.1–2.8 were verified by direct source reading; the remainder were confirmed across three independent review passes.*
