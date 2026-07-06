import logging

import discord
from discord.ext import commands

from cogs.utils.config import load_config
from cogs.utils.emojis import DONE, ERROR, SEARCHING
from cogs.utils.endpoints import STEAM_STORE_API_URL, STEAM_STORE_URL
from cogs.utils.http import get_session


class Steam(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("discord")
        config = load_config()
        self.steam_api_key = config["secrets"].get("steamApiKey")
        self.steam_store_api_url = STEAM_STORE_API_URL

    @commands.hybrid_command(aliases=["steam"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def gameinfo(self, ctx, *, game_name: str):
        """Fetches information about a Steam game."""
        await ctx.message.add_reaction(SEARCHING)
        try:
            game_id, game_details = await self.search_game(game_name)
        except Exception:
            self.logger.exception("Steam lookup failed for %s", game_name)
            await ctx.message.clear_reactions()
            await ctx.message.add_reaction(ERROR)
            await ctx.send("An error occurred while fetching Steam data.")
            return

        await ctx.message.clear_reactions()
        if game_id and game_details:
            await ctx.send(embed=self.create_game_embed(game_details))
            await ctx.message.add_reaction(DONE)
        else:
            await ctx.send("Game not found. Please check the name and try again.")
            await ctx.message.add_reaction(ERROR)

    async def search_game(self, game_name):
        session = get_session()
        params = {"term": game_name, "cc": "UY", "l": "en"}
        async with session.get(
            f"{self.steam_store_api_url}/storesearch/", params=params
        ) as response:
            if response.status != 200:
                return None, None
            games = (await response.json()).get("items", [])
        if not games:
            return None, None
        game_id = games[0]["id"]
        return game_id, await self.get_game_details(game_id)

    async def get_game_details(self, game_id):
        session = get_session()
        params = {"appids": game_id, "cc": "UY", "l": "en"}
        async with session.get(
            f"{self.steam_store_api_url}/appdetails/", params=params
        ) as response:
            if response.status != 200:
                return None
            data = await response.json()
        if str(game_id) in data and data[str(game_id)]["success"]:
            return data[str(game_id)]["data"]
        return None

    def create_game_embed(self, game_details):
        price_overview = game_details.get("price_overview", {})
        price = (
            f"${price_overview['final'] / 100:.2f}"
            if price_overview
            else "Free to Play"
        )
        developers = ", ".join(game_details.get("developers", []))
        release_date = game_details.get("release_date", {}).get("date", "Unknown")

        embed = discord.Embed(
            title=game_details["name"],
            description=game_details.get(
                "short_description", "No description available."
            ),
            color=0x1B2838,
            url=f"{STEAM_STORE_URL}/app/{game_details['steam_appid']}/",
        )
        embed.add_field(name="Price", value=price, inline=True)
        embed.add_field(name="Release Date", value=release_date, inline=True)
        embed.add_field(name="Developer", value=developers or "N/A", inline=True)
        embed.set_thumbnail(url=game_details["header_image"])
        return embed


async def setup(bot):
    await bot.add_cog(Steam(bot))
