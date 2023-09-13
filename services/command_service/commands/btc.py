import requests
from .base import BaseCommand


class BtcCommand(BaseCommand):
    @staticmethod
    def __str__():
        return "Returns the current price of Bitcoin."

    async def execute(self):
        await self.message.add_reaction("⌛")
        btc_price = await self.fetch_btc_price()
        await self.message.channel.send(f"Current Bitcoin price: **{btc_price} USD**")
        await self.message.clear_reactions()
        await self.message.add_reaction("✅")

    async def fetch_btc_price(self):
        response = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot")
        data = response.json()
        return format(int(float(data["data"]["amount"])), ",d")
