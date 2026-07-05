import datetime
import logging
import os

import discord
from discord.ext import commands

from cogs.utils.config import load_config
from cogs.utils.formatting import to_local
from cogs.utils.http import get_json
from cogs.utils.images import combine_fighter_logos

# Cap the forward search so a stale/empty upstream can never spin forever.
MAX_LOOKAHEAD_DAYS = 60


class UFC(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("discord")
        self.api_key = load_config()["secrets"].get("apiSportsKey")
        self.base_url = "https://v1.mma.api-sports.io"

    def get_headers(self):
        return {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": "v1.mma.api-sports.io",
        }

    async def _fights_on(self, date_str):
        data = await get_json(
            f"{self.base_url}/fights?date={date_str}", headers=self.get_headers()
        )
        return data.get("response", [])

    async def get_next_event(self):
        """Find the next UFC event within a bounded lookahead window."""
        current_date = datetime.datetime.now(datetime.timezone.utc)
        for _ in range(MAX_LOOKAHEAD_DAYS):
            formatted_date = current_date.strftime("%Y-%m-%d")
            fights = await self._fights_on(formatted_date)
            if fights:
                all_fights = list(fights)
                next_day = (current_date + datetime.timedelta(days=1)).strftime(
                    "%Y-%m-%d"
                )
                all_fights.extend(await self._fights_on(next_day))
                return all_fights, formatted_date
            current_date += datetime.timedelta(days=1)
        return [], None

    @commands.hybrid_command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def ufc(self, ctx: commands.Context):
        """Get the next upcoming UFC event with main card fight information."""
        await ctx.message.add_reaction("⌛")
        try:
            fights, event_date = await self.get_next_event()
            if not fights:
                await ctx.send("No upcoming UFC events found.")
                await ctx.message.clear_reactions()
                await ctx.message.add_reaction("✅")
                return

            main_card_fights = fights[-5:]
            main_event = main_card_fights[-1]

            embed = discord.Embed(
                title=f":boxing_glove: {main_event['slug']} :boxing_glove:",
                color=discord.Color.red(),
            )
            embed.add_field(
                name="",
                value=f":calendar_spiral: **{to_local(main_event['date']).strftime('%Y-%m-%d')}**\n",
                inline=False,
            )

            for fight in main_card_fights:
                fight_time = to_local(fight["date"]).strftime("%H:%M")
                fighter1 = fight["fighters"]["first"]
                fighter2 = fight["fighters"]["second"]
                embed.add_field(
                    name=f"{fighter1['name']} vs {fighter2['name']}",
                    value=f"{fight['category']}\n:clock2: **{fight_time}**\n",
                    inline=False,
                )

            vs_image_path = os.path.join(os.getcwd(), "assets", "vs.png")
            combined_image = await combine_fighter_logos(
                main_event["fighters"]["first"]["logo"],
                main_event["fighters"]["second"]["logo"],
                vs_image_path,
            )
            file = discord.File(combined_image, filename="main_event.png")
            embed.set_image(url="attachment://main_event.png")
            embed.set_footer(text="UFC Events provided by API-Sports")
            await ctx.send(embed=embed, file=file)
            await ctx.message.clear_reactions()
            await ctx.message.add_reaction("✅")
        except Exception:
            self.logger.exception("Failed to retrieve UFC events")
            await ctx.message.clear_reactions()
            await ctx.message.add_reaction("❌")
            await ctx.send("Could not retrieve UFC events right now.")


async def setup(bot):
    await bot.add_cog(UFC(bot))
