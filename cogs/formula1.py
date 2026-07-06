import logging
from urllib.parse import urlparse

import discord
from discord.ext import commands

from cogs.utils.config import load_config
from cogs.utils.emojis import DONE, ERROR, PROCESSING
from cogs.utils.endpoints import FORMULA1_API_BASE_URL
from cogs.utils.formatting import format_local
from cogs.utils.http import get_json
from cogs.utils.images import add_white_background


class Formula1(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("discord")
        self.api_key = load_config()["secrets"].get("apiSportsKey")
        self.base_url = FORMULA1_API_BASE_URL

    def get_headers(self):
        return {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": urlparse(self.base_url).netloc,
        }

    @commands.hybrid_command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def f1(self, ctx: commands.Context):
        """Get upcoming Formula 1 race sessions."""
        await ctx.message.add_reaction(PROCESSING)
        try:
            data = await get_json(
                f"{self.base_url}/races?next=10", headers=self.get_headers()
            )
            if not data["response"]:
                await ctx.send("No upcoming races found for Formula 1.")
                await ctx.message.clear_reactions()
                await ctx.message.add_reaction(DONE)
                return

            race_sessions = data["response"]
            competition_name = race_sessions[0]["competition"]["name"]
            circuit_name = race_sessions[0]["circuit"]["name"]
            circuit_image = race_sessions[0]["circuit"]["image"]

            embed = discord.Embed(
                title=f":checkered_flag: {competition_name} :checkered_flag:",
                color=discord.Color.red(),
            )

            for session in race_sessions:
                race_type = session["type"]
                is_race = race_type.lower() == "race"
                race_date = format_local(session["date"])
                title = f"🏁 {race_type} 🏁" if is_race else race_type
                embed.add_field(
                    name=title,
                    value=(
                        f":calendar_spiral: {race_date} \n"
                        f":racing_car: {circuit_name} \n"
                    ),
                    inline=False,
                )
                if is_race:
                    break

            file = None
            if circuit_image:
                circuit_bytes = await add_white_background(circuit_image)
                file = discord.File(fp=circuit_bytes, filename="circuit.png")
                embed.set_thumbnail(url="attachment://circuit.png")

            embed.set_footer(text="Formula 1 Sessions provided by API-Sports")
            await ctx.send(embed=embed, file=file)
            await ctx.message.clear_reactions()
            await ctx.message.add_reaction(DONE)
        except Exception:
            self.logger.exception("Failed to retrieve Formula 1 sessions")
            await ctx.message.clear_reactions()
            await ctx.message.add_reaction(ERROR)
            await ctx.send("Could not retrieve Formula 1 sessions right now.")


async def setup(bot):
    await bot.add_cog(Formula1(bot))
