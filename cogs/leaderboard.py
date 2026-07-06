import asyncio

from discord.ext import commands

from cogs.utils.emojis import DONE


class Leaderboard(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(aliases=["lb"])
    @commands.cooldown(1, 5, commands.BucketType.channel)
    async def leaderboard(self, ctx):
        """Gets the leaderboard for the top 5 users with most hours."""
        db = self.bot.get_cog("Database")
        if db is None:
            await ctx.send("Leaderboard is temporarily unavailable.")
            return
        user_hours_list = await db.get_all_user_hours()

        bot_user_id = self.bot.user.id
        user_hours_list = [uh for uh in user_hours_list if uh[0] != bot_user_id]
        top = sorted(user_hours_list, key=lambda x: x[1], reverse=True)[:5]

        # Resolve the (few) needed users concurrently instead of one-by-one.
        members = await asyncio.gather(
            *(self._resolve_user(uid) for uid, _ in top), return_exceptions=True
        )

        leaderboard_message = "🏆 **Leaderboard** 🏆\n\n"
        for index, ((user_id, hours), member) in enumerate(zip(top, members), start=1):
            username = (
                member.name
                if member and not isinstance(member, Exception)
                else f"ID: {user_id}"
            )
            leaderboard_message += f"**#{index} {username}** - {round(hours, 2)} hours\n"

        await ctx.send(leaderboard_message)
        await ctx.message.clear_reactions()
        await ctx.message.add_reaction(DONE)

    async def _resolve_user(self, user_id):
        user = self.bot.get_user(user_id)
        if user is not None:
            return user
        return await self.bot.fetch_user(user_id)


async def setup(bot):
    await bot.add_cog(Leaderboard(bot))
