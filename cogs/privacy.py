"""Privacy / data-subject commands.

The bot stores per-user data (voice-channel time and song requests). For a
commercial product these commands give users visibility into, and control
over, that data (GDPR access & erasure rights).
"""

import discord
from discord.ext import commands


class Privacy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(aliases=["mydata"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def my_data(self, ctx):
        """Shows what personal data the bot stores about you."""
        db = self.bot.get_cog("Database")
        if db is None:
            await ctx.send("Data storage is not available right now.")
            return
        data = await db.get_user_data(ctx.author.id)
        hours = round(data["tracked_seconds"] / 3600, 2)
        embed = discord.Embed(title="Your stored data", color=0x5865F2)
        embed.add_field(name="Voice time tracked", value=f"{hours} hours", inline=False)
        embed.add_field(
            name="Songs requested", value=str(data["songs_requested"]), inline=False
        )
        embed.set_footer(text="Use `forget_me` to erase this data.")
        await ctx.send(embed=embed)

    @commands.hybrid_command(aliases=["forgetme"])
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def forget_me(self, ctx):
        """Erases all personal data the bot stores about you."""
        db = self.bot.get_cog("Database")
        if db is None:
            await ctx.send("Data storage is not available right now.")
            return
        # Drop in-memory voice tracking first so the hourly duration flush
        # (or a disconnect racing with this command) can't resurrect a row
        # for this user right after the delete below.
        self.bot.online_users.pop(ctx.author.id, None)
        await db.delete_user_data(ctx.author.id)
        await ctx.send("Your stored data has been erased.")


async def setup(bot):
    await bot.add_cog(Privacy(bot))
