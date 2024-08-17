import requests
import json
from discord.ext import commands
import discord
import datetime
import pytz


class UFC(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = None  # Placeholder for the API key
        self.base_url = "https://v1.mma.api-sports.io"  # Base URL for UFC/MMA API

    async def cog_load(self):
        """Load the API key from the config file when the cog is loaded."""
        with open("config.json") as f:
            config = json.load(f)
            self.api_key = config["secrets"]["apiFootballKey"]  # Same key for UFC/MMA
        print("API-Sports/MMA key loaded successfully")

    def get_headers(self):
        """Get the headers for the API requests."""
        return {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": "v1.mma.api-sports.io",
        }

    def get_next_event(self):
        """Find the next UFC event by checking each day from today onward."""
        current_date = datetime.datetime.utcnow()
        while True:
            formatted_date = current_date.strftime("%Y-%m-%d")
            response = requests.get(
                f"{self.base_url}/fights?date={formatted_date}",
                headers=self.get_headers(),
            )
            fights_data = response.json()
            fights = fights_data["response"]

            # Return fights if found for the current date
            if fights:
                return fights, formatted_date

            # Move to the next day
            current_date += datetime.timedelta(days=1)

    @commands.hybrid_command()
    async def ufc(self, ctx: commands.Context):
        """Get the next upcoming UFC event with main card fight information"""
        await ctx.message.add_reaction("⌛")
        try:
            # Get the next UFC event
            fights, event_date = self.get_next_event()

            # Focus on the last 5 fights and the main event
            main_card_fights = fights[-5:]  # Take the last 5 fights as main card
            main_event = main_card_fights[-1]  # The main event is the last fight

            # Create an embed for the upcoming event
            embed = discord.Embed(
                title=f":martial_arts_uniform: UFC Event: {main_event['slug']} :boxing_glove:",
                color=discord.Color.red(),
                timestamp=datetime.datetime.utcnow(),
            )

            # Montevideo timezone
            montevideo_tz = pytz.timezone("America/Montevideo")

            # General event details (e.g., date, location)
            event_date_utc = datetime.datetime.strptime(
                main_event["date"], "%Y-%m-%dT%H:%M:%S%z"
            )
            event_date_montevideo = event_date_utc.astimezone(montevideo_tz)
            formatted_event_date = event_date_montevideo.strftime("%Y-%m-%d")

            embed.add_field(
                name="Event Details",
                value=f":calendar_spiral: **{formatted_event_date}**\n",
                inline=False,
            )

            # Add each of the main card fights to the embed
            for fight in main_card_fights:
                # Convert fight date to Montevideo time
                fight_date_utc = datetime.datetime.strptime(
                    fight["date"], "%Y-%m-%dT%H:%M:%S%z"
                )
                fight_date_montevideo = fight_date_utc.astimezone(montevideo_tz)
                formatted_date = fight_date_montevideo.strftime("%H:%M")

                # Fighter details
                fighter1 = fight["fighters"]["first"]
                fighter2 = fight["fighters"]["second"]

                fight_title = f"{fighter1['name']} vs {fighter2['name']}"

                fight_description = (
                    f"**{fight['category']}**\n"
                    f":clock2: **{formatted_date}** Montevideo Time\n"
                )

                embed.add_field(
                    name=fight_title,
                    value=fight_description,
                    inline=False,
                )

            embed.set_footer(text="UFC Events provided by API-Sports")
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"Failed to retrieve UFC events: {str(e)}")

        await ctx.message.clear_reactions()
        await ctx.message.add_reaction("✅")


async def setup(bot):
    await bot.add_cog(UFC(bot))
