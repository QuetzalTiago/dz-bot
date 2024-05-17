import subprocess
from discord.ext import commands, tasks


class Restart(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.description = "Restarts the bot and resets its state."

    @tasks.loop(hours=6)
    async def restart(self, ctx):
        await ctx.message.add_reaction("⌛")

        self.bot.get_cog('Database').set_startup_notification(
            ctx.message.id, ctx.message.channel.id
        )
        subprocess.call(["aws/scripts/application-start.sh"])
        await self.bot.close()

async def setup(bot):
    await bot.add_cog(Restart(bot))