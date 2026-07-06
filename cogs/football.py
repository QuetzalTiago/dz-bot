import logging
from collections import defaultdict
from urllib.parse import urlparse

import discord
from discord.ext import commands

from cogs.utils.config import load_config
from cogs.utils.emojis import DONE, ERROR, PROCESSING
from cogs.utils.endpoints import FOOTBALL_API_BASE_URL
from cogs.utils.formatting import to_local
from cogs.utils.http import get_json
from cogs.utils.images import add_white_background


class Football(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("discord")
        self.api_key = load_config()["secrets"].get("apiSportsKey")
        self.base_url = FOOTBALL_API_BASE_URL
        self.priority_teams = {
            "Liverpool",
            "Manchester United",
            "Manchester City",
            "Chelsea",
            "Arsenal",
            "Tottenham",
        }

    def get_headers(self):
        return {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": urlparse(self.base_url).netloc,
        }

    @commands.hybrid_command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def premier(self, ctx: commands.Context):
        """Get upcoming fixtures for the Premier League."""
        await ctx.message.add_reaction(PROCESSING)
        try:
            league_data = await get_json(
                f"{self.base_url}/leagues?id=39", headers=self.get_headers()
            )
            league_info = league_data["response"][0]
            seasons = league_info["seasons"]
            if not seasons:
                await ctx.send("No season data available for the Premier League.")
                await ctx.message.clear_reactions()
                await ctx.message.add_reaction(DONE)
                return
            latest_season = seasons[-1]

            league_logo_bytes = await add_white_background(
                league_info["league"]["logo"]
            )

            fixtures_data = await get_json(
                f"{self.base_url}/fixtures?league=39&season={latest_season['year']}&next=12",
                headers=self.get_headers(),
            )
            fixtures = fixtures_data["response"]

            filtered_fixtures = [
                fixture
                for fixture in fixtures
                if fixture["teams"]["home"]["name"] in self.priority_teams
                or fixture["teams"]["away"]["name"] in self.priority_teams
            ]

            fixtures_by_date = defaultdict(list)
            for fixture in filtered_fixtures:
                local_dt = to_local(fixture["fixture"]["date"])
                home_team = fixture["teams"]["home"]["name"]
                away_team = fixture["teams"]["away"]["name"]
                venue = (fixture["fixture"]["venue"] or {}).get("name") or "Unknown"
                fixtures_by_date[local_dt.strftime("%Y-%m-%d")].append(
                    f"**{home_team} vs {away_team}**\n{venue}, **{local_dt.strftime('%H:%M')}**"
                )

            embed = discord.Embed(
                title="Premier League Upcoming Fixtures", color=discord.Color.blue()
            )
            file = discord.File(fp=league_logo_bytes, filename="logo.png")
            embed.set_thumbnail(url="attachment://logo.png")
            for date, fixtures_text in fixtures_by_date.items():
                embed.add_field(
                    name=f":calendar_spiral: {date} :calendar_spiral: ",
                    value="\n\n".join(fixtures_text),
                    inline=False,
                )
            embed.set_footer(text="Premier League Fixtures provided by API-Sports")
            await ctx.send(embed=embed, file=file)
            await ctx.message.clear_reactions()
            await ctx.message.add_reaction(DONE)
        except Exception:
            self.logger.exception("Failed to retrieve Premier League fixtures")
            await ctx.message.clear_reactions()
            await ctx.message.add_reaction(ERROR)
            await ctx.send("Could not retrieve Premier League fixtures right now.")


async def setup(bot):
    await bot.add_cog(Football(bot))
