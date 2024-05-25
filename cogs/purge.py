import json
from discord.ext import commands, tasks


class Purge(commands.Cog):

    def __init__(self, bot, config):
        self.bot = bot
        self.cmd_list = []
        self.set_cmd_list()
        self.purge_job.start()
        self.config = config

    def set_cmd_list(self):
        for cmd in self.bot.walk_commands():
            self.cmd_list.append(cmd.name)
            for alias in cmd.aliases:
                self.cmd_list.append(alias)

    def is_bot_or_command(self, m):
        env = self.config.get("env", "")
        test_prefix = self.config.get("test_prefix", "")
        prefix = test_prefix if env and env == "LOCAL" else ""

        return m.author == self.bot.user or any(
            m.content.lower().startswith(prefix + cmd) for cmd in self.cmd_list
        )

    @commands.hybrid_command()
    async def purge(self, ctx):
        self.set_cmd_list()
        """Purges bot messages and command queries in the current channel."""
        await ctx.message.add_reaction("⌛")
        await ctx.channel.purge(limit=50, check=self.is_bot_or_command)

    @tasks.loop(hours=2)
    async def purge_job(self):
        if self.bot.main_channel is not None:
            await self.bot.main_channel.purge(limit=50, check=self.is_bot_or_command)


async def setup(bot):
    with open("config.json") as f:
        config = json.load(f)
        await bot.add_cog(Purge(bot, config))
