import logging

from discord.ext import commands

from cogs.utils.emojis import DONE, ERROR, PROCESSING
from cogs.utils.endpoints import POE_NINJA_CURRENCY_OVERVIEW_URL
from cogs.utils.http import get_session


class Div(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("discord")

    @commands.hybrid_command()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def div(self, ctx, *, league: str = None):
        """Returns the current Divine Orb price (in Chaos) for a PoE league."""
        if not league:
            await ctx.send("Specify the league, for example: 'div necropolis'")
            return

        league = league.strip().title()
        await ctx.message.add_reaction(PROCESSING)
        try:
            div_price = await self.fetch_div_price(league)
        except LookupError:
            await ctx.message.clear_reactions()
            await ctx.message.add_reaction(ERROR)
            await ctx.send(f"Divine Orb not found for league: {league}")
            return
        except Exception:
            self.logger.exception("Failed to fetch Divine price for %s", league)
            await ctx.message.clear_reactions()
            await ctx.message.add_reaction(ERROR)
            await ctx.send(
                "Error fetching data for that league. Check the name and try again."
            )
            return

        await ctx.send(
            f"Current Divine price in {league} league: **{div_price} Chaos**"
        )
        await ctx.message.add_reaction(DONE)

    async def fetch_div_price(self, league):
        session = get_session()
        params = {"league": league, "type": "Currency"}
        async with session.get(
            POE_NINJA_CURRENCY_OVERVIEW_URL, params=params
        ) as response:
            response.raise_for_status()
            data = await response.json()
        # Raise LookupError (not StopIteration, which PEP 479 turns into a
        # RuntimeError across the coroutine boundary) when the orb is missing.
        divine = next(
            (
                x
                for x in data.get("lines", [])
                if x["currencyTypeName"] == "Divine Orb"
            ),
            None,
        )
        if divine is None:
            raise LookupError(f"Divine Orb not found for league: {league}")
        return format(int(float(divine["chaosEquivalent"])), ",d")


async def setup(bot):
    await bot.add_cog(Div(bot))
