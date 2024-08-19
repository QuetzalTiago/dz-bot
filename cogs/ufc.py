import requests
import json
from discord.ext import commands
import discord
import datetime
import pytz
from PIL import Image
from io import BytesIO
import os


class UFC(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = None
        self.base_url = "https://v1.mma.api-sports.io"

    async def cog_load(self):
        """Load the API key from the config file when the cog is loaded."""
        with open("config.json") as f:
            config = json.load(f)
            self.api_key = config["secrets"]["apiSportsKey"]

    def get_headers(self):
        """Get the headers for the API requests."""
        return {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": "v1.mma.api-sports.io",
        }

    def get_next_event(self):
        """Find the next UFC event by checking each day from today onward."""
        current_date = datetime.datetime.utcnow()
        all_fights = []
        formatted_date = None

        # Check for the next event
        while True:
            formatted_date = current_date.strftime("%Y-%m-%d")
            response = requests.get(
                f"{self.base_url}/fights?date={formatted_date}",
                headers=self.get_headers(),
            )
            fights_data = response.json()
            fights = fights_data["response"]

            # If fights are found, add them to the list and check the next day
            if fights:
                all_fights.extend(fights)
                current_date += datetime.timedelta(days=1)
                formatted_date = current_date.strftime("%Y-%m-%d")
                response = requests.get(
                    f"{self.base_url}/fights?date={formatted_date}",
                    headers=self.get_headers(),
                )
                next_day_fights_data = response.json()
                next_day_fights = next_day_fights_data["response"]
                all_fights.extend(next_day_fights)
                break

            # Move to the next day
            current_date += datetime.timedelta(days=1)

        return all_fights, formatted_date

    def combine_fighter_logos(self, logo_url1, logo_url2, vs_image_path):
        """Combine two fighter logos into one image, side by side, with a 'VS' overlay."""
        # Download the fighter logos
        response1 = requests.get(logo_url1)
        response2 = requests.get(logo_url2)

        logo1 = Image.open(BytesIO(response1.content)).convert("RGBA")
        logo2 = Image.open(BytesIO(response2.content)).convert("RGBA")

        # Resize images to the same height
        height = min(logo1.height, logo2.height)
        logo1 = logo1.resize(
            (int(logo1.width * (height / logo1.height)), height),
            Image.Resampling.LANCZOS,
        )
        logo2 = logo2.resize(
            (int(logo2.width * (height / logo2.height)), height),
            Image.Resampling.LANCZOS,
        )

        # Create a new image with the width of both logos combined
        combined_image = Image.new("RGBA", (logo1.width + logo2.width, height))

        # Paste logos side by side
        combined_image.paste(logo1, (0, 0))
        combined_image.paste(logo2, (logo1.width, 0))

        # Load the VS overlay image from the local filesystem
        vs_image = Image.open(vs_image_path).convert("RGBA")

        # Maintain aspect ratio of the VS image while resizing
        vs_aspect_ratio = vs_image.width / vs_image.height
        target_width = combined_image.width
        target_height = int(target_width / vs_aspect_ratio)

        if target_height > combined_image.height:
            target_height = combined_image.height
            target_width = int(target_height * vs_aspect_ratio)

        vs_image = vs_image.resize(
            (target_width, target_height), Image.Resampling.LANCZOS
        )

        # Center the VS image on the combined logos
        position = (
            (combined_image.width - target_width) // 2,
            (combined_image.height - target_height) // 2,
        )
        combined_image.paste(vs_image, position, vs_image)

        # Save the combined image to a BytesIO object
        image_io = BytesIO()
        combined_image.save(image_io, format="PNG")
        image_io.seek(0)

        return image_io

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
                title=f":boxing_glove: {main_event['slug']} :boxing_glove:",
                color=discord.Color.red(),
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
                name="",
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
                    f"{fight['category']}\n" f":clock2: **{formatted_date}**\n"
                )

                embed.add_field(
                    name=fight_title,
                    value=fight_description,
                    inline=False,
                )

            vs_image_path = os.path.join(os.getcwd(), "assets", "vs.png")

            # Combine fighter logos and set as embed image
            combined_image = self.combine_fighter_logos(
                main_event["fighters"]["first"]["logo"],
                main_event["fighters"]["second"]["logo"],
                vs_image_path,
            )
            file = discord.File(combined_image, filename="main_event.png")
            embed.set_image(url="attachment://main_event.png")

            embed.set_footer(text="UFC Events provided by API-Sports")
            await ctx.send(embed=embed, file=file)

        except Exception as e:
            await ctx.send(f"Failed to retrieve UFC events: {str(e)}")

        await ctx.message.clear_reactions()
        await ctx.message.add_reaction("✅")


async def setup(bot):
    await bot.add_cog(UFC(bot))
