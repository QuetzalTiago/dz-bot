import requests
from discord.ext import commands


class Div(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command()
    async def div(self, ctx):
        """Returns the current price of the Divine in the specified league from the message."""
        await ctx.message.add_reaction("⌛")
        league = ctx.message.content.split("div", 1)[1].strip()
        div_price = await self.fetch_div_price(league)
        await ctx.send(
            f"Current Divine price in {league.title()} league: **{div_price} Chaos**"
        )
        await ctx.message.clear_reactions()
        await ctx.message.add_reaction("✅")

    async def fetch_div_price(self, league):
        league = league.title()
        response = requests.get(
            f"https://poe.ninja/api/data/currencyoverview?league={league}&type=Currency"
        )
        data = response.json()
        divine = next(
            x for x in data.get("lines", []) if x["currencyTypeName"] == "Divine Orb"
        )
        return format(int(float(divine.get("chaosEquivalent"))), ",d")


async def setup(bot):
    await bot.add_cog(Div(bot))
