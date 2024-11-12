import requests
from discord.ext import commands


class Div(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command()
    async def div(self, ctx):
        """Returns the current price of the Divine in the specified league from the message"""
        league = ctx.message.content.split("div", 1)[1].strip().title()
        if not league:
            await ctx.message.clear_reactions()
            await ctx.message.add_reaction("❌")
            await ctx.send("Specify the league, for example: 'div necropolis'")
            return

        await ctx.message.add_reaction("⌛")
        try:
            div_price = await self.fetch_div_price(league)
            await ctx.send(
                f"Current Divine price in {league} league: **{div_price} Chaos**"
            )
            await ctx.message.add_reaction("✅")
        except Exception:
            await ctx.message.clear_reactions()
            await ctx.message.add_reaction("❌")
            await ctx.send(
                f"Error fetching data for the specified league. Please check the league name and try again."
            )

    async def fetch_div_price(self, league):
        response = requests.get(
            f"https://poe.ninja/api/data/currencyoverview?league={league}&type=Currency"
        )
        response.raise_for_status()  # Raise an error if the request was unsuccessful
        data = response.json()
        divine = next(
            x for x in data.get("lines", []) if x["currencyTypeName"] == "Divine Orb"
        )
        if not divine:
            raise Exception(f"Divine Orb not found for league: {league}")
        return format(int(float(divine.get("chaosEquivalent"))), ",d")


async def setup(bot):
    await bot.add_cog(Div(bot))
