from discord.ext import commands

from cogs.utils.emojis import DONE


class Status(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def status(self, ctx):
        """Gets the current status for a user"""
        db = self.bot.get_cog("Database")
        if db is None:
            await ctx.send("Status is temporarily unavailable.")
            return
        user_hours = await db.get_user_hours(ctx.author.id)
        user_hours = round(user_hours, 2)  # rounding off to 2 decimal   places

        if user_hours < 1:
            await ctx.send(
                "You have not spent an hour yet on the server. Disconnect to refresh."
            )
        else:
            await ctx.send(
                f"You have spent **{user_hours}** hours in the server since 2024."
            )
        await ctx.message.clear_reactions()
        await ctx.message.add_reaction(DONE)


async def setup(bot):
    await bot.add_cog(Status(bot))
