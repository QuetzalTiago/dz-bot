from discord.ext import commands, tasks


class Purge(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.cmd_list = []
        self.set_cmd_list()

    def set_cmd_list(self):
        for cmd in self.bot.walk_commands():
            self.cmd_list.append(cmd.name)
            for alias in cmd.aliases:
                self.cmd_list.append(alias)

    def is_bot_or_command(self, m):
        return m.author == self.bot.user or any(
            m.content.lower().startswith(cmd) for cmd in self.cmd_list
        )

    @commands.hybrid_command()
    async def purge(self, ctx):
        """Purges bot messages and command queries in the current channel."""
        await ctx.message.add_reaction("⌛")
        await ctx.channel.purge(limit=50, check=self.is_bot_or_command)

    @tasks.loop(hours=2)
    async def purge_job(self):
        if hasattr(self, "main_channel"):
            await self.main_channel.purge(limit=50, check=self.is_bot_or_command)


async def setup(bot):
    await bot.add_cog(Purge(bot))
