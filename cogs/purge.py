from discord.ext import commands, tasks


class Purge(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.description = "Purges bot messages and command queries in the current channel."

    @commands.command()
    async def purge(self, ctx):
        await ctx.message.add_reaction("⌛")
        await ctx.message.channel.purge(limit=50,check=lambda m: m.author == self.client.user)

    @tasks.loop(hours=2)
    async def purge_job(self):
        await self.main_channel.purge(limit=50,check=lambda m: m.author == self.client.user)

async def setup(bot):
    await bot.add_cog(Purge(bot))