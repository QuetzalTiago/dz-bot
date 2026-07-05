import logging

from discord import Embed
from discord.ext import commands, tasks

from cogs.utils.emojis import DONE, ERROR, PROCESSING
from cogs.utils.endpoints import COINBASE_BTC_SPOT_URL
from cogs.utils.http import get_json


class Btc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sent_message = None
        self.logger = logging.getLogger("discord")

    @commands.hybrid_command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def btc(self, ctx):
        """Returns the current price of Bitcoin and keeps the message updated."""
        await ctx.message.add_reaction(PROCESSING)
        try:
            btc_price = await self.fetch_btc_price()
        except Exception:
            self.logger.exception("Error in btc command")
            await ctx.message.clear_reactions()
            await ctx.message.add_reaction(ERROR)
            await ctx.send("An error occurred while fetching the Bitcoin price.")
            return

        embed = self.create_price_embed(btc_price)
        self.sent_message = await ctx.send(embed=embed)
        await ctx.message.clear_reactions()
        await ctx.message.add_reaction(DONE)

        if not self.btc_price_task.is_running():
            self.btc_price_task.start()

    @tasks.loop(seconds=30)
    async def btc_price_task(self):
        """Update the latest BTC price message.

        Exceptions are handled inside the loop body so a transient network or
        Discord error does not permanently kill the task (a bare `tasks.loop`
        stops for good on the first unhandled exception).
        """
        if self.sent_message is None:
            return
        try:
            btc_price = await self.fetch_btc_price()
            embed = self.create_price_embed(btc_price)
            await self.sent_message.edit(embed=embed)
        except Exception as e:
            self.logger.warning("Failed to update BTC price message: %s", e)

    @btc_price_task.before_loop
    async def before_btc_price_task(self):
        await self.bot.wait_until_ready()

    async def fetch_btc_price(self):
        data = await get_json(COINBASE_BTC_SPOT_URL)
        return format(int(float(data["data"]["amount"])), ",d")

    def create_price_embed(self, btc_price):
        embed = Embed(
            title="Bitcoin Price",
            description=f"Current Bitcoin price: 💰**{btc_price} USD**",
            color=0xF7931A,
        )
        embed.set_footer(text="Updated every 30 seconds")
        return embed

    async def cog_unload(self):
        self.btc_price_task.cancel()


async def setup(bot):
    await bot.add_cog(Btc(bot))
