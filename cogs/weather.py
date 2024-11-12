import os
import json
import requests
from discord.ext import commands
import discord


class Weather(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        with open("config.json") as f:
            config = json.load(f)
            self.api_key = config["secrets"]["weather_api_key"]
            self.default_city = config.get("secrets", {}).get("default_city")

    @commands.hybrid_command(aliases=["w", "weather", "tiempo", "t"])
    async def get_weather(self, ctx, city: str = None):
        """Fetches weather information for a specified city"""

        if not city:
            if self.default_city:
                city = self.default_city
            else:
                await ctx.send(
                    "Please provide a city name or configure the default city in config.json."
                )
                return

        await ctx.message.add_reaction("⌛")
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={self.api_key}&units=metric"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()

            # Extracting the necessary information
            sunset_time = data["sys"]["sunset"]
            sunrise_time = data["sys"]["sunrise"]
            wind_speed = data["wind"]["speed"]
            wind_direction = f"{data['wind']['deg']}°"
            humidity = data["main"]["humidity"]
            pressure = data["main"]["pressure"]
            temperature = data["main"]["temp"]
            weather_status = data["weather"][0]["description"]
            visibility_distance = (
                data.get("visibility", 10000) / 1000
            )  # Convert meters to kilometers
            precipitation_probability = data.get("rain", {}).get("1h", 0)

            embed = self.create_weather_embed(
                city,
                sunset_time,
                sunrise_time,
                wind_speed,
                wind_direction,
                humidity,
                pressure,
                temperature,
                weather_status,
                visibility_distance,
                precipitation_probability,
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("City not found. Please check the city name and try again.")

        await ctx.message.clear_reactions()
        await ctx.message.add_reaction("✅")

    def create_weather_embed(
        self,
        city,
        sunset_time,
        sunrise_time,
        wind_speed,
        wind_direction,
        humidity,
        pressure,
        temperature,
        weather_status,
        visibility_distance,
        precipitation_probability,
    ):
        embed = discord.Embed(title=f"Weather in {city}", color=discord.Color.blue())

        embed.add_field(
            name="Sunset Time", value=self.format_time(sunset_time), inline=True
        )
        embed.add_field(
            name="Sunrise Time", value=self.format_time(sunrise_time), inline=True
        )
        embed.add_field(name="Wind Speed", value=f"{wind_speed} m/s", inline=True)
        embed.add_field(name="Wind Direction", value=wind_direction, inline=True)
        embed.add_field(name="Humidity", value=f"{humidity}%", inline=True)
        embed.add_field(name="Pressure", value=f"{pressure} hPa", inline=True)
        embed.add_field(name="Temperature", value=f"{temperature:.1f}°C", inline=True)
        embed.add_field(
            name="Weather Status", value=weather_status.capitalize(), inline=False
        )
        embed.add_field(
            name="Visibility Distance",
            value=f"{visibility_distance:.2f} km",
            inline=True,
        )
        embed.add_field(
            name="Precipitation",
            value=f"{precipitation_probability*100}%",
            inline=True,
        )

        return embed

    def format_time(self, timestamp):
        from datetime import datetime

        return datetime.fromtimestamp(timestamp).strftime("%H:%M %p")


async def setup(bot):
    await bot.add_cog(Weather(bot))
