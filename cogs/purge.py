import os

from discord.ext import commands, tasks

from cogs.utils.checks import require_manage_messages
from cogs.utils.config import load_config
from cogs.utils.emojis import PROCESSING


class Purge(commands.Cog):

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.cmd_list = []
        # The scheduled auto-purge is opt-in; it silently deleted messages in a
        # guild's first text channel every two hours by default.
        self.auto_purge_enabled = os.environ.get(
            "DZ_AUTO_PURGE", ""
        ).lower() in ("1", "true", "yes")

    async def cog_load(self):
        # Task loops must not be started before there is a running event loop.
        self.set_cmd_list()
        if self.auto_purge_enabled:
            self.purge_job.start()

    async def cog_unload(self):
        if self.purge_job.is_running():
            self.purge_job.cancel()

    def set_cmd_list(self):
        self.cmd_list = []
        for cmd in self.bot.walk_commands():
            self.cmd_list.extend([cmd.name] + list(cmd.aliases))

    def is_bot_or_command(self, m, params=False):
        prefix = self.config.get("prefix", "")
        if params:
            return m.author == self.bot.user or any(
                m.content.lower().startswith(f"{prefix}{cmd} ") for cmd in self.cmd_list
            )
        return m.author == self.bot.user or any(
            m.content.lower() == f"{prefix}{cmd}" for cmd in self.cmd_list
        )

    @commands.hybrid_command()
    @commands.cooldown(1, 10, commands.BucketType.channel)
    @require_manage_messages()
    async def purge(self, ctx):
        """Purges bot messages and command queries in the current channel."""
        self.set_cmd_list()
        await ctx.message.add_reaction(PROCESSING)
        await ctx.channel.purge(limit=50, check=self.is_bot_or_command)
        await ctx.channel.purge(
            limit=50, check=lambda m: self.is_bot_or_command(m, params=True)
        )

    def _first_text_channel(self, guild):
        text_channels = sorted(guild.text_channels, key=lambda c: c.position)
        return text_channels[0] if text_channels else None

    @tasks.loop(hours=2)
    async def purge_job(self):
        # Every guild's own first text channel is purged, not just one cached
        # guild - a process-wide "main channel" silently skipped every other
        # guild the bot is in.
        self.set_cmd_list()
        for guild in self.bot.guilds:
            channel = self._first_text_channel(guild)
            if channel is None:
                continue
            try:
                await channel.purge(limit=50, check=self.is_bot_or_command)
                await channel.purge(
                    limit=50, check=lambda m: self.is_bot_or_command(m, params=True)
                )
            except Exception:
                # A single guild's purge failing (e.g. missing "Manage Messages")
                # must not kill the loop for every other guild.
                self.bot.logger.exception(
                    "Auto-purge failed for guild %s", guild.id
                )

    @purge_job.before_loop
    async def _before_purge_job(self):
        await self.bot.wait_until_ready()

    @purge_job.error
    async def _purge_job_error(self, error):
        self.bot.logger.exception("purge_job loop errored", exc_info=error)


async def setup(bot):
    await bot.add_cog(Purge(bot, load_config()))
