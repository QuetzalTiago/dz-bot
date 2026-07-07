import datetime
import logging

import discord
from discord.ext import commands

from cogs.utils.config import load_config
from cogs.utils.emojis import DONE, ERROR, PROCESSING
from cogs.utils.endpoints import OPENWEATHER_URL
from cogs.utils.http import get_session


class Weather(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("discord")
        config = load_config()
        self.api_key = config.get("secrets", {}).get("weatherApiKey")
        self.default_city = config.get("secrets", {}).get("defaultCity")

    @commands.hybrid_command(aliases=["w", "weather", "tiempo", "t"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def get_weather(self, ctx, *, city: str = None):
        """Fetches weather information for a specified city."""
        if not city:
            city = self.default_city
        if not city:
            await ctx.send(
                "Please provide a city name or configure a default city."
            )
            return

        await ctx.message.add_reaction(PROCESSING)
        # City is passed as a query parameter so aiohttp URL-encodes it.
        params = {"q": city, "appid": self.api_key, "units": "metric"}
        try:
            session = get_session()
            async with session.get(OPENWEATHER_URL, params=params) as response:
                if response.status == 404:
                    await ctx.message.clear_reactions()
                    await ctx.message.add_reaction(ERROR)
                    await ctx.send("City not found. Check the name and try again.")
                    return
                response.raise_for_status()
                data = await response.json()
            embed = self.create_weather_embed(city, data)
            await ctx.send(embed=embed)
            await ctx.message.clear_reactions()
            await ctx.message.add_reaction(DONE)
        except Exception:
            self.logger.exception("Weather lookup failed for %s", city)
            await ctx.message.clear_reactions()
            await ctx.message.add_reaction(ERROR)
            await ctx.send("Could not retrieve weather right now. Try again later.")
            return

    def create_weather_embed(self, city, data):
        # Timezone offset (seconds from UTC) is supplied by the API so
        # sunrise/sunset render in the queried city's local time, not the
        # server's. Rain is a volume in mm ("rain.1h"), not a probability.
        tz_offset = data.get("timezone", 0)
        rain_mm = data.get("rain", {}).get("1h", 0)

        embed = discord.Embed(title=f"Weather in {city}", color=discord.Color.blue())
        embed.add_field(
            name="Sunset Time",
            value=self.format_time(data["sys"]["sunset"], tz_offset),
            inline=True,
        )
        embed.add_field(
            name="Sunrise Time",
            value=self.format_time(data["sys"]["sunrise"], tz_offset),
            inline=True,
        )
        embed.add_field(
            name="Wind Speed", value=f"{data['wind']['speed']} m/s", inline=True
        )
        embed.add_field(
            name="Wind Direction", value=f"{data['wind']['deg']}°", inline=True
        )
        embed.add_field(
            name="Humidity", value=f"{data['main']['humidity']}%", inline=True
        )
        embed.add_field(
            name="Pressure", value=f"{data['main']['pressure']} hPa", inline=True
        )
        embed.add_field(
            name="Temperature", value=f"{data['main']['temp']:.1f}°C", inline=True
        )
        embed.add_field(
            name="Weather Status",
            value=data["weather"][0]["description"].capitalize(),
            inline=False,
        )
        embed.add_field(
            name="Visibility",
            value=f"{data.get('visibility', 10000) / 1000:.2f} km",
            inline=True,
        )
        embed.add_field(name="Rain (last 1h)", value=f"{rain_mm} mm", inline=True)
        return embed

    def format_time(self, timestamp, tz_offset):
        tz = datetime.timezone(datetime.timedelta(seconds=tz_offset))
        return datetime.datetime.fromtimestamp(timestamp, tz).strftime("%H:%M")


async def setup(bot):
    await bot.add_cog(Weather(bot))
