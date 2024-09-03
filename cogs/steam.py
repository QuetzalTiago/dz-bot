import json
import discord
import requests
from discord.ext import commands


class Steam(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        with open("config.json") as f:
            config = json.load(f)
            self.steam_api_key = config["secrets"]["steamApiKey"]
            self.steam_store_api_url = "https://store.steampowered.com/api"

    @commands.hybrid_command(aliases=["steam"])
    async def gameinfo(self, ctx, *, game_name: str):
        """Fetches information about a Steam game"""
        await ctx.message.add_reaction("🔍")
        game_id, game_details = await self.search_game(game_name)

        if game_id and game_details:
            embed = self.create_game_embed(game_details)
            await ctx.send(embed=embed)
        else:
            await ctx.send("Game not found. Please check the name and try again.")

        await ctx.message.clear_reactions()
        await ctx.message.add_reaction("✅")

    async def search_game(self, game_name):
        params = {
            "term": game_name,
            "cc": "US",
            "l": "en",
        }
        response = requests.get(
            f"{self.steam_store_api_url}/storesearch/", params=params
        )
        if response.status_code == 200:
            games = response.json().get("items", [])
            if games:
                # Get the first matching game
                game_id = games[0]["id"]
                game_details = await self.get_game_details(game_id)
                return game_id, game_details
        return None, None

    async def get_game_details(self, game_id):
        params = {
            "appids": game_id,
            "cc": "US",
            "l": "en",
        }
        response = requests.get(
            f"{self.steam_store_api_url}/appdetails/", params=params
        )
        if response.status_code == 200:
            data = response.json()
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

        genres = ", ".join(
            [genre["description"] for genre in game_details.get("genres", [])]
        )
        developers = ", ".join(game_details.get("developers", []))
        release_date = game_details.get("release_date", {}).get("date", "Unknown")

        # Handle Steam User Reviews
        reviews = game_details.get("reviews", "")
        recommendations = game_details.get("recommendations", {}).get("total", 0)
        review_summary = (
            f"{reviews} ({recommendations} total)"
            if reviews
            else "No reviews available"
        )

        platforms = ", ".join(
            [
                platform.capitalize()
                for platform, supported in game_details.get("platforms", {}).items()
                if supported
            ]
        )

        embed = discord.Embed(
            title=game_details["name"],
            description=game_details.get(
                "short_description", "No description available."
            ),
            color=0x1B2838,
            url=f"https://store.steampowered.com/app/{game_details['steam_appid']}/",
        )
        embed.add_field(name="Price", value=price, inline=True)
        embed.add_field(name="Release Date", value=release_date, inline=True)
        embed.add_field(name="Developer", value=developers or "N/A", inline=True)

        embed.set_thumbnail(url=game_details["header_image"])
        return embed


async def setup(bot):
    await bot.add_cog(Steam(bot))
