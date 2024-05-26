from discord.ext import commands


class Status(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command()
    async def status(self, ctx):
        """Gets the current status for a user"""
        user_hours = self.bot.get_cog("Database").get_user_hours(ctx.author.id)
        user_hours = round(user_hours, 2)  # rounding off to 2 decimal   places

        if user_hours < 1:
            await ctx.send(
                f"You have not spent an hour yet on the server. Disconnect to refresh."
            )
        else:
            await ctx.send(
                f"You have spent **{user_hours}** hours in the server since 2024."
            )
        await ctx.message.channel.clear_reactions()
        await ctx.message.channel.add_reaction("✅")


async def setup(bot):
    await bot.add_cog(Status(bot))
