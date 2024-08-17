import requests
import json
from discord.ext import commands
import discord
import datetime
from io import BytesIO
from PIL import Image, ImageOps
import pytz  # You need to install pytz for timezone conversions


class Formula1(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = None  # Placeholder for the API key
        self.base_url = "https://v1.formula-1.api-sports.io"

    async def cog_load(self):
        """Load the API key from the config file when the cog is loaded."""
        with open("config.json") as f:
            config = json.load(f)
            self.api_key = config["secrets"]["apiFootballKey"]  # Same key for F1
        print("API-Football/Formula1 key loaded successfully")

    def get_headers(self):
        """Get the headers for the API requests."""
        return {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": "v1.formula-1.api-sports.io",
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

    def convert_to_montevideo_time(self, date_str):
        """Convert the given date string to Montevideo time."""
        utc_time = datetime.datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S%z")
        montevideo_tz = pytz.timezone("America/Montevideo")
        return utc_time.astimezone(montevideo_tz).strftime("%Y-%m-%d, %H:%M")

    @commands.hybrid_command()
    async def f1(self, ctx: commands.Context):
        """Get upcoming Formula 1 race sessions"""
        await ctx.message.add_reaction("⌛")
        try:
            # Get the next 10 upcoming sessions (practice, qualifying, race)
            response = requests.get(
                f"{self.base_url}/races?next=10", headers=self.get_headers()
            )
            data = response.json()
            if not data["response"]:
                await ctx.send("No upcoming races found for Formula 1.")
                return

            race_sessions = data["response"]
            competition_name = race_sessions[0]["competition"]["name"]
            circuit_name = race_sessions[0]["circuit"]["name"]
            circuit_image = race_sessions[0]["circuit"]["image"]

            # Create an embed for the race
            embed = discord.Embed(
                title=f":checkered_flag: {competition_name} :checkered_flag:",
                color=discord.Color.red(),
                timestamp=datetime.datetime.utcnow(),
            )

            # Add details for each session
            for session in race_sessions:
                race_type = session["type"]
                is_race = race_type.lower() == "race"
                race_date = self.convert_to_montevideo_time(session["date"])

                session_description = (
                    f":calendar_spiral: {race_date} \n"
                    f":racing_car: {circuit_name} \n"
                )

                title = f"{race_type}"
                if is_race:
                    title = f"🏁 {race_type} 🏁"

                embed.add_field(
                    name=title,
                    value=session_description,
                    inline=False,
                )

                # Stop processing if the session type is "Race"
                if is_race:
                    break

            if circuit_image:
                # Add white background to the circuit image
                circuit_image_bytes = self.add_white_background(circuit_image)
                file = discord.File(fp=circuit_image_bytes, filename="circuit.png")
                embed.set_thumbnail(url="attachment://circuit.png")

            embed.set_footer(text="Formula 1 Sessions provided by API-Sports")
            await ctx.send(embed=embed, file=file if circuit_image else None)

        except Exception as e:
            await ctx.send(f"Failed to retrieve Formula 1 sessions: {str(e)}")

        await ctx.message.clear_reactions()
        await ctx.message.add_reaction("✅")


async def setup(bot):
    await bot.add_cog(Formula1(bot))
