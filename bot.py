import asyncio
import random
import subprocess
import json
import datetime
import logging
import logging.handlers

from typing import List

import discord
from discord.ext import commands, tasks


class Khaled(commands.Bot):

    def __init__(self, *args, initial_extensions: List[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.initial_extensions = (initial_extensions,)
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
        self.logger.setLevel(logging.INFO)

    async def setup_hook(self):
        for extension in self.initial_extensions[0]:
            await self.load_extension(extension)

    async def on_ready(self):
        self.logger.info(f"Logged on as {self.user} (ID: {self.user.id})")
        db = self.get_cog("Database")
        await self.set_first_text_channel_as_main()
        quote = random.choice(self.dj_khaled_quotes)
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.playing, name=quote)
        )
        await self.update_online_users()
        # Notify after reset
        message_id, channel_id = db.get_startup_notification()
        if message_id and channel_id:
            message = await self.fetch_message_by_id(channel_id, message_id)
            if message:
                await message.clear_reactions()
                await message.add_reaction("✅")

                # Reset the notify_on_startup flag in the database
                await db.set_startup_notification(None, None)

    async def update_online_users(self):
        for guild in self.guilds:
            for voice_channel in guild.voice_channels:
                for member in voice_channel.members:
                    if not member.bot:
                        self.online_users[member.id] = datetime.datetime.utcnow()
                        self.logger.debug(
                            f"Tracking user: {member.name} (ID: {member.id}) already connected in voice channel {voice_channel.name} (ID: {voice_channel.id})"
                        )

    async def on_voice_state_update(self, member, before, after):
        if before.channel and not after.channel:  # User has disconnected
            user_id = member.id
            if user_id in self.online_users:  # Check if the user was tracked
                del self.online_users[user_id]  # Remove the user from tracking
                self.logger.info(
                    f"Stopped tracking user: {member.name} (ID: {member.id})"
                )

        elif not before.channel and after.channel:  # User has connected
            self.online_users[member.id] = datetime.datetime.utcnow()
            self.logger.info(f"Started tracking user: {member.name} (ID: {member.id})")

        if member == self.user and after is None:
            self.get_cog("Music").stop()

    async def set_first_text_channel_as_main(self):
        for guild in self.guilds:
            text_channels = [channel for channel in guild.text_channels]
            text_channels.sort(key=lambda x: x.position)
            if text_channels:
                self.main_channel = text_channels[0]
                self.logger.info(
                    f"Main channel set to: {self.main_channel.name} (ID: {self.main_channel.id}) in guild {guild.name} (ID: {guild.id})"
                )
                break

    def reset(self):
        self.logger.warning("Bot is resetting...")
        subprocess.call(["aws/scripts/application-start.sh"])
        self.close()

    async def fetch_message_by_id(self, channel_id, message_id):
        try:
            # Convert the IDs to integers
            channel_id = int(channel_id)
            message_id = int(message_id)
        except ValueError:
            self.logger.error("Invalid channel or message ID. IDs must be integers.")
            return None

        channel = self.get_channel(channel_id)
        if channel:
            try:
                message = await channel.fetch_message(message_id)
                return message
            except Exception as e:
                self.logger.error(f"Failed to fetch message: {e}")
        else:
            self.logger.error(f"Channel with ID {channel_id} not found.")
            return None


async def main():
    logger = logging.getLogger("discord")
    logger.setLevel(logging.DEBUG)

    # File handler for logging
    file_handler = logging.handlers.RotatingFileHandler(
        filename="discord.log",
        encoding="utf-8",
        maxBytes=32 * 1024 * 1024,  # 32 MiB
        backupCount=5,  # Rotate through 5 files
    )

    # Console handler for logging
    console_handler = logging.StreamHandler()

    dt_fmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(
        "[{asctime}] [{levelname:<8}] {name}: {message}", dt_fmt, style="{"
    )

    # Set the formatter for both handlers
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add both handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    async def show_cmd_confirmation(ctx):
        command_name = ctx.command.name if ctx.command else "Unknown command"

        logger.info(f"{command_name} command invoked by {ctx.author}")

        await ctx.message.add_reaction("👍")

    with open("config.json") as f:
        config = json.load(f)
        logger.info(f"Loaded config: {config}")
        token = config["secrets"]["discordToken"]
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
            "cogs.ci",
            "cogs.steam",
            # should be the last one
            "cogs.purge",
        ]
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True

        async with Khaled(
            prefix, case_insensitive=True, intents=intents, initial_extensions=exts
        ) as bot:
            bot.before_invoke(show_cmd_confirmation)
            await bot.start(token)
            await bot.tree.sync()


asyncio.run(main())
