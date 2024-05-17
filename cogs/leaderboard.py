from discord.ext import commands


class Leaderboard(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.description = "Gets the leaderboard for the top 5 users with most hours."

    @commands.command(aliases=["lb"])
    async def leaderboard(self, ctx):
        user_hours_list = self.bot.get_cog('Database').get_all_user_hours()

        # Filter out the bot's own user ID to prevent it from appearing in the leaderboard
        bot_user_id = self.bot.user.id
        user_hours_list = [
            user_hour for user_hour in user_hours_list if user_hour[0] != bot_user_id
        ]

        sorted_user_hours = sorted(user_hours_list, key=lambda x: x[1], reverse=True)[
            :5
        ]  # Get top 5

        leaderboard_message = "🏆 **Leaderboard** 🏆\n\n"
        for index, (user_id, hours) in enumerate(sorted_user_hours, start=1):
            member = await self.bot.fetch_user(user_id)
            username = member.name if member else f"ID: {user_id}"
            leaderboard_message += (
                f"**#{index} {username}** - {round(hours, 2)} hours\n"
            )

        await ctx.message.channel.send(leaderboard_message)
        await ctx.message.clear_reactions()
        await ctx.message.add_reaction("✅")

async def setup(bot):
    await bot.add_cog(Leaderboard(bot))
