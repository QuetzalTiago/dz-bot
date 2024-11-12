import requests

from discord.ext import commands, tasks


class Btc(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command()
    async def btc(self, ctx):
        """Returns the current price of Bitcoin"""
        await ctx.message.add_reaction("⌛")
        btc_price = await self.fetch_btc_price()
        await ctx.send(f"Current Bitcoin price: **{btc_price} USD**")
        await ctx.message.clear_reactions()
        await ctx.message.add_reaction("✅")

    @tasks.loop(minutes=50)  # 50 minute interval
    async def check_and_notify_bitcoin_price_change(self):
        response = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot")
        data = response.json()
        current_price = float(data["data"]["amount"])

        last_price = self.bot.get_cog("Database").get_bitcoin_price()

        threshold = 0.020  # 2.0% change threshold

        if last_price is not None:
            price_change = current_price - last_price
            percentage_change = (price_change / last_price) * 100

            if abs(percentage_change) >= threshold * 100:
                formatted_current_price = format(int(current_price), ",d")
                formatted_price_change = format(int(abs(price_change)), ",d")

                change_direction = "increased" if price_change > 0 else "decreased"
                notification_message = (
                    f"Bitcoin price has {change_direction} to **{formatted_current_price} USD** "
                    f"({formatted_price_change} USD, {abs(percentage_change):.2f}% change)."
                )

                await self.bot.main_channel.send(notification_message)

        self.bot.get_cog("Database").update_bitcoin_price(current_price)

    async def fetch_btc_price(self):
        response = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot")
        data = response.json()
        return format(int(float(data["data"]["amount"])), ",d")


async def setup(bot):
    await bot.add_cog(Btc(bot))
