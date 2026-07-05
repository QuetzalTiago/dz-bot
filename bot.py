import asyncio
import datetime
import logging
import logging.handlers
import os
import random
from typing import List

import discord
from discord.ext import commands

from cogs.utils.config import load_config
from cogs.utils.emojis import ACK, DONE
from cogs.utils.http import close_session


class Khaled(commands.AutoShardedBot):

    def __init__(self, *args, initial_extensions: List[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.initial_extensions = initial_extensions
        self.online_users = {}
        self.main_channel = None
        self.dj_khaled_quotes = [
            "Another one",
            "We the best",
            "Major key",
            "They don't want us to win",
            "Bless up",
            "You loyal",
            "God did",
            "They ain't believe in us",
        ]

        self.logger = logging.getLogger("discord")

    async def setup_hook(self):
        for extension in self.initial_extensions:
            try:
                await self.load_extension(extension)
            except Exception:
                self.logger.exception("Failed to load extension %s", extension)
        # Sync application (slash) commands once extensions are loaded.
        try:
            await self.tree.sync()
        except Exception:
            self.logger.exception("Failed to sync application commands")

    async def close(self):
        await close_session()
        await super().close()

    async def on_ready(self):
        await self.set_first_text_channel_as_main()
        self.logger.info(f"Logged on as {self.user} (ID: {self.user.id})")

        btc = self.get_cog("Btc")
        if btc is not None and not btc.btc_price_task.is_running():
            btc.btc_price_task.start()

        quote = random.choice(self.dj_khaled_quotes)
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.playing, name=quote)
        )
        await self.update_online_users()

        # Notify after a restart triggered by the `restart` command.
        db = self.get_cog("Database")
        if db is None:
            return
        message_id, channel_id = db.get_startup_notification()
        if message_id and channel_id:
            message = await self.fetch_message_by_id(channel_id, message_id)
            if message:
                await message.clear_reactions()
                await message.add_reaction(DONE)
                await db.clear_startup_notification()

    async def on_command_error(self, ctx, error):
        """Global command error handler.

        Keeps internal errors out of user-facing channels while still logging
        the full traceback for operators.
        """
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.CheckFailure):
            await ctx.send(str(error) or "You are not allowed to use this command.")
            return
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"This command is on cooldown. Try again in {error.retry_after:.1f}s."
            )
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Missing argument: `{error.param.name}`.")
            return
        if isinstance(error, commands.UserInputError):
            await ctx.send("Invalid input. Check the command usage and try again.")
            return

        self.logger.exception(
            "Unhandled error in command %s", getattr(ctx.command, "name", "unknown"),
            exc_info=error,
        )
        try:
            await ctx.send("Something went wrong while running that command.")
        except discord.DiscordException:
            pass

    async def update_online_users(self):
        for guild in self.guilds:
            for voice_channel in guild.voice_channels:
                for member in voice_channel.members:
                    if not member.bot:
                        self.online_users[member.id] = datetime.datetime.now(
                            datetime.timezone.utc
                        )

    async def on_voice_state_update(self, member, before, after):
        if before.channel and not after.channel:  # User disconnected
            join_time = self.online_users.pop(member.id, None)
            db = self.get_cog("Database")
            if join_time is not None and db is not None:
                await db.flush_user_duration(member.id, join_time)

        elif not before.channel and after.channel:  # User connected
            if not member.bot:
                self.online_users[member.id] = datetime.datetime.now(
                    datetime.timezone.utc
                )

        # The bot itself was disconnected/kicked from a voice channel.
        if member.id == self.user.id and before.channel and not after.channel:
            music = self.get_cog("Music")
            if music is not None:
                await music.handle_forced_disconnect(before.channel.guild)

    async def set_first_text_channel_as_main(self):
        for guild in self.guilds:
            text_channels = sorted(guild.text_channels, key=lambda x: x.position)
            if text_channels:
                self.main_channel = text_channels[0]
                self.logger.info(
                    f"Main channel set to: {self.main_channel.name} "
                    f"(ID: {self.main_channel.id}) in guild {guild.name}"
                )
                break

    async def fetch_message_by_id(self, channel_id, message_id):
        try:
            channel_id = int(channel_id)
            message_id = int(message_id)
        except (ValueError, TypeError):
            self.logger.error("Invalid channel or message ID; must be integers.")
            return None

        channel = self.get_channel(channel_id)
        if not channel:
            self.logger.error(f"Channel with ID {channel_id} not found.")
            return None
        try:
            return await channel.fetch_message(message_id)
        except discord.DiscordException as e:
            self.logger.error(f"Failed to fetch message: {e}")
            return None


def _configure_logging() -> logging.Logger:
    logger = logging.getLogger("discord")
    level = os.environ.get("DZ_LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, level, logging.INFO))

    file_handler = logging.handlers.RotatingFileHandler(
        filename="discord.log",
        encoding="utf-8",
        maxBytes=32 * 1024 * 1024,
        backupCount=5,
    )
    console_handler = logging.StreamHandler()

    dt_fmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(
        "[{asctime}] [{levelname:<8}] {name}: {message}", dt_fmt, style="{"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def _init_observability(logger):
    """Initialize Sentry error tracking if configured and available.

    Enabled by setting DZ_SENTRY_DSN. Kept optional so the bot has no hard
    dependency on Sentry.
    """
    dsn = os.environ.get("DZ_SENTRY_DSN")
    if not dsn:
        return
    try:
        import sentry_sdk

        sentry_sdk.init(dsn=dsn, traces_sample_rate=0.0)
        logger.info("Sentry error tracking initialized.")
    except ImportError:
        logger.warning("DZ_SENTRY_DSN set but sentry_sdk is not installed.")


async def main():
    logger = _configure_logging()
    _init_observability(logger)

    async def show_cmd_confirmation(ctx):
        command_name = ctx.command.name if ctx.command else "Unknown command"
        logger.info(f"{command_name} command invoked by {ctx.author}")
        try:
            await ctx.message.add_reaction(ACK)
        except discord.DiscordException:
            pass

    config = load_config()
    # NOTE: never log `config` — it contains the bot token and every API key.
    token = config.get("secrets", {}).get("discordToken") or os.environ.get(
        "DZ_SECRET_DISCORD_TOKEN"
    )
    if not token:
        raise SystemExit(
            "No Discord token configured. Set secrets.discordToken in config.json "
            "or the DZ_SECRET_DISCORD_TOKEN environment variable."
        )
    prefix = config.get("prefix", "")
    if prefix:
        logger.info(f"Prefix '{prefix}' set")
    else:
        logger.warning("No prefix set")

    exts = [
        "cogs.btc",
        "cogs.chess_leaderboard",
        "cogs.chess",
        "cogs.database",
        "cogs.div",
        "cogs.emoji",
        "cogs.leaderboard",
        "cogs.music",
        "cogs.restart",
        "cogs.status",
        "cogs.ai",
        "cogs.football",
        "cogs.formula1",
        "cogs.ufc",
        "cogs.steam",
        "cogs.weather",
        "cogs.privacy",
        # should be the last one
        "cogs.purge",
    ]
    if os.environ.get("DZ_ENABLE_CEDULA", "").lower() in ("1", "true", "yes"):
        # Disabled by default: looks up national-ID PII from a third party.
        exts.insert(-1, "cogs.ci")

    intents = discord.Intents.default()
    intents.message_content = True
    intents.voice_states = True

    async with Khaled(
        prefix, case_insensitive=True, intents=intents, initial_extensions=exts
    ) as bot:
        bot.before_invoke(show_cmd_confirmation)
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
