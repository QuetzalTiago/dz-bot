import requests
from .base import BaseCommand


class DivCommand(BaseCommand):
    @staticmethod
    def __str__():
        return "Returns the current price of the Divine in the current leangue."

    async def execute(self):
        await self.message.add_reaction("⌛")
        div_price = await self.fetch_div_price()
        await self.message.channel.send(f"Current Divine price: **{div_price} Chaos**")
        await self.message.clear_reactions()
        await self.message.add_reaction("✅")

    async def fetch_div_price(self):
        response = requests.get("https://poe.ninja/api/data/currencyoverview?league=Affliction&type=Currency")
        data = response.json()
        divine = next(x for x in data.get("lines", []) if x['currencyTypeName'] == 'Divine Orb')
        return format(int(float(divine.get('chaosEquivalent'))), ",d")