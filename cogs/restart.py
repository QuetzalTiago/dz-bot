import logging
import subprocess

from discord.ext import commands

from cogs.utils.checks import is_owner_or_admin
from cogs.utils.emojis import PROCESSING


class Restart(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("discord")

    @commands.hybrid_command()
    @commands.cooldown(1, 30, commands.BucketType.default)
    @is_owner_or_admin()
    async def restart(self, ctx):
        """Restarts the bot and resets its state (owner/admin only)."""
        await ctx.message.add_reaction(PROCESSING)

        db = self.bot.get_cog("Database")
        if db is not None:
            await db.set_startup_notification(ctx.message.id, ctx.message.channel.id)

        try:
            subprocess.Popen(["aws/scripts/application-start.sh"])
        except OSError:
            self.logger.exception("Failed to launch restart script")
            await ctx.send("Failed to trigger restart.")
            return
        await self.bot.close()


async def setup(bot):
    await bot.add_cog(Restart(bot))
