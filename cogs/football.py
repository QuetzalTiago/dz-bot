import requests
import json
from discord.ext import commands
import discord
import datetime
import pytz
from io import BytesIO
from PIL import Image, ImageOps
from collections import defaultdict


class Football(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = None
        self.base_url = "https://v3.football.api-sports.io"
        self.priority_teams = {
            "Liverpool",
            "Manchester United",
            "Manchester City",
            "Chelsea",
            "Arsenal",
            "Tottenham",
        }

    async def cog_load(self):
        """Load the API key from the config file when the cog is loaded."""
        with open("config.json") as f:
            config = json.load(f)
            self.api_key = config["secrets"]["apiSportsKey"]

    def get_headers(self):
        """Get the headers for the API requests."""
        return {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": "v3.football.api-sports.io",
        }

    def add_white_background(self, image_url):
        """Download image, add white background, and return the image bytes."""
        response = requests.get(image_url)
        img = Image.open(BytesIO(response.content))

        # Create a white background image
        background = Image.new("RGBA", img.size, (255, 255, 255, 255))
        background.paste(img, (0, 0), img)

        # Optionally, add a border around the image
        img_with_border = ImageOps.expand(background, border=20, fill="white")

        # Save to BytesIO
        image_bytes = BytesIO()
        img_with_border.save(image_bytes, format="PNG")
        image_bytes.seek(0)

        return image_bytes

    @commands.hybrid_command()
    async def premier(self, ctx: commands.Context):
        """Get upcoming fixtures for the Premier League"""
        await ctx.message.add_reaction("⌛")
        try:
            # Get the latest season for the Premier League
            league_response = requests.get(
                f"{self.base_url}/leagues?id=39", headers=self.get_headers()
            )
            league_data = league_response.json()
            league_info = league_data["response"][0]
            seasons = league_info["seasons"]
            latest_season = seasons[-1]

            # Get the league logo
            league_logo_url = league_info["league"]["logo"]

            # Add white background to the logo
            league_logo_bytes = self.add_white_background(league_logo_url)

            # Get upcoming fixtures for the current season
            current_year = latest_season["year"]
            fixtures_response = requests.get(
                f"{self.base_url}/fixtures?league=39&season={current_year}&next=12",
                headers=self.get_headers(),
            )
            fixtures_data = fixtures_response.json()
            fixtures = fixtures_data["response"]

            # Filter out fixtures involving priority teams
            filtered_fixtures = [
                fixture
                for fixture in fixtures
                if fixture["teams"]["home"]["name"] in self.priority_teams
                or fixture["teams"]["away"]["name"] in self.priority_teams
            ]

            # Group fixtures by date
            fixtures_by_date = defaultdict(list)
            montevideo_tz = pytz.timezone("America/Montevideo")
            for fixture in filtered_fixtures:
                fixture_date_utc = datetime.datetime.strptime(
                    fixture["fixture"]["date"], "%Y-%m-%dT%H:%M:%S%z"
                )
                fixture_date_montevideo = fixture_date_utc.astimezone(montevideo_tz)
                formatted_date = fixture_date_montevideo.strftime("%Y-%m-%d")
                formatted_time = fixture_date_montevideo.strftime("%H:%M")

                home_team = fixture["teams"]["home"]["name"]
                away_team = fixture["teams"]["away"]["name"]
                venue = fixture["fixture"]["venue"]["name"] or "Unknown"

                fixture_description = (
                    f"**{home_team} vs {away_team}**\n" f"{venue}, **{formatted_time}**"
                )

                fixtures_by_date[formatted_date].append(fixture_description)

            # Create an embed for the fixtures
            embed = discord.Embed(
                title="Premier League Upcoming Fixtures",
                color=discord.Color.blue(),
            )

            # Upload the modified logo and set it as the thumbnail
            file = discord.File(fp=league_logo_bytes, filename="logo.png")
            embed.set_thumbnail(url="attachment://logo.png")

            # Add grouped fixtures to the embed with separators between dates
            for date, fixtures in fixtures_by_date.items():
                fixtures_text = "\n\n".join(fixtures)
                embed.add_field(
                    name=f":calendar_spiral: {date} :calendar_spiral: ",
                    value=fixtures_text,
                    inline=False,
                )

            embed.set_footer(text="Premier League Fixtures provided by API-Sports")
            await ctx.send(embed=embed, file=file)
        except Exception as e:
            await ctx.send(f"Failed to retrieve Premier League fixtures: {str(e)}")

        await ctx.message.clear_reactions()
        await ctx.message.add_reaction("✅")


async def setup(bot):
    await bot.add_cog(Football(bot))
