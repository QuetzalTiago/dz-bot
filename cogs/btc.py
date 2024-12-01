import requests
from discord.ext import commands, tasks
from discord import Message, Embed
import logging


class Btc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sent_message: Message = None
        self.request_message: Message = None
        self.logger = logging.getLogger("discord")

    @commands.hybrid_command()
    async def btc(self, ctx):
        """Returns the current price of Bitcoin and starts updating the message."""
        try:
            self.request_message = ctx.message  # Store the request message
            await ctx.message.add_reaction("⌛")
            btc_price = await self.fetch_btc_price()
            embed = self.create_price_embed(btc_price)

            # Send the initial message and start updating it
            self.sent_message = await ctx.send(embed=embed)
            await ctx.message.clear_reactions()
            await ctx.message.add_reaction("✅")

            # Start the updating task if not already running
            if not self.btc_price_task.is_running():
                self.btc_price_task.start()

        except Exception as e:
            self.logger.error(f"Error in btc command: {e}")
            await ctx.send("An error occurred while fetching the Bitcoin price.")

    @tasks.loop(seconds=10)
    async def btc_price_task(self):
        """Task to update the latest BTC price message."""
        try:
            btc_price = await self.fetch_btc_price()
            embed = self.create_price_embed(btc_price)
            await self.sent_message.edit(embed=embed)
        except Exception as e:
            self.logger.warning(f"Failed to update BTC price message: {e}")
            self.btc_price_task.stop()

    @btc_price_task.before_loop
    async def before_btc_price_task(self):
        """Ensure the bot is ready before starting the task."""
        await self.bot.wait_until_ready()

    async def fetch_btc_price(self):
        """Fetches the current Bitcoin price from Coinbase API."""
        try:
            response = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot")
            response.raise_for_status()
            data = response.json()
            return format(int(float(data["data"]["amount"])), ",d")
        except requests.RequestException as e:
            self.logger.error(f"Error fetching BTC price: {e}")
            raise

    def create_price_embed(self, btc_price):
        """Creates an embed for the current Bitcoin price."""
        embed = Embed(
            title="Bitcoin Price",
            description=f"Current Bitcoin price: 💰**{btc_price} USD**",
            color=0xF7931A,
        )
        embed.set_footer(text="Updated every 10 seconds")
        return embed

    async def cog_unload(self):
        """Stop the task when the cog is unloaded."""
        self.btc_price_task.cancel()


async def setup(bot):
    await bot.add_cog(Btc(bot))
