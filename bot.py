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
            "Another one.",
            "We the best.",
            "Major key.",
            "They don't want us to win.",
            "Bless up.",
            "Call me asparagus!",
        ]
        self.max_duration = 1200  # in seconds, 20 minutes

    async def setup_hook(self):
        for extension in self.initial_extensions[0]:
            await self.load_extension(extension)

    async def on_ready(self):
        print("Logged on as", self.user)
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
                        print(f"Tracking already connected user: {member.name}")

    async def on_voice_state_update(self, member, before, after):
        if before.channel and not after.channel:  # User has disconnected
            user_id = member.id
            if user_id in self.online_users:  # Check if the user was tracked
                del self.online_users[user_id]  # Remove the user from tracking

        elif not before.channel and after.channel:  # User has connected
            self.online_users[member.id] = datetime.datetime.utcnow()
            print(f"Tracking {member.name}")

        if member == self.user and after is None:
            self.get_cog("Music").stop()

    async def set_first_text_channel_as_main(self):
        for guild in self.guilds:
            text_channels = [channel for channel in guild.text_channels]
            text_channels.sort(key=lambda x: x.position)
            if text_channels:
                self.main_channel = text_channels[0]
                print(f"Main channel set to: {self.main_channel.name}")
                break

    def reset(self):
        subprocess.call(["aws/scripts/application-start.sh"])
        self.close()

    async def fetch_message_by_id(self, channel_id, message_id):
        try:
            # Convert the IDs to integers
            channel_id = int(channel_id)
            message_id = int(message_id)
        except ValueError:
            print("Invalid channel or message ID. IDs must be integers.")
            return None

        channel = self.get_channel(channel_id)
        if channel:
            try:
                message = await channel.fetch_message(message_id)
                return message
            except Exception as e:
                print(f"Failed to fetch message: {e}")
        else:
            print(f"Channel with ID {channel_id} not found.")
            return None


async def main():
    logger = logging.getLogger("discord")
    logger.setLevel(logging.INFO)

    handler = logging.handlers.RotatingFileHandler(
        filename="discord.log",
        encoding="utf-8",
        maxBytes=32 * 1024 * 1024,  # 32 MiB
        backupCount=5,  # Rotate through 5 files
    )
    dt_fmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(
        "[{asctime}] [{levelname:<8}] {name}: {message}", dt_fmt, style="{"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    async def show_cmd_confirmation(ctx):
        await ctx.message.add_reaction("👍")

    with open("config.json") as f:
        config = json.load(f)
        token = config["secrets"]["discordToken"]
        env = config.get("env", "")
        test_prefix = "?"
        prefix = test_prefix if env and env == "LOCAL" else ""
        exts = [
            "cogs.btc",
            "cogs.chess_leaderboard",
            "cogs.chess",
            "cogs.database",
            "cogs.div",
            "cogs.emoji",
            "cogs.files",
            "cogs.leaderboard",
            "cogs.music",
            "cogs.purge",
            "cogs.restart",
            "cogs.status",
        ]
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True

        async with Khaled(prefix, intents=intents, initial_extensions=exts) as bot:
            bot.before_invoke(show_cmd_confirmation)
            await bot.start(token)
            await bot.tree.sync()


asyncio.run(main())
