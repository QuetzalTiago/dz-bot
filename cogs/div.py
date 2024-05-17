import requests
from discord.ext import commands


class Div(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.description = "Returns the current price of the Divine in the current leangue."

    @commands.command()
    async def div(self, ctx):
        await ctx.message.add_reaction("⌛")
        div_price = await self.fetch_div_price()
        await ctx.message.channel.send(f"Current Divine price: **{div_price} Chaos**")
        await ctx.message.clear_reactions()
        await ctx.message.add_reaction("✅")

    async def fetch_div_price(self):
        response = requests.get("https://poe.ninja/api/data/currencyoverview?league=Necropolis&type=Currency")
        data = response.json()
        divine = next(x for x in data.get("lines", []) if x['currencyTypeName'] == 'Divine Orb')
        return format(int(float(divine.get('chaosEquivalent'))), ",d")
    
async def setup(bot):
    await bot.add_cog(Div(bot))