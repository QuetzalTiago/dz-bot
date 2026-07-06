"""National-ID (Uruguayan "cédula") lookup.

WARNING: this command queries personal data from a third-party leak-aggregator
service. It is DISABLED by default and only loaded when DZ_ENABLE_CEDULA is set
(see bot.py). Even then it is restricted to the bot owner. Do not enable this in
a commercial deployment without a lawful basis for processing personal data.
"""

import logging

import discord
from discord.ext import commands

from cogs.utils.emojis import DONE, ERROR, PROCESSING
from cogs.utils.endpoints import CEDULA_LOOKUP_BASE_URL
from cogs.utils.http import get_json


class CedulaInfo(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("discord")

    @commands.hybrid_command(aliases=["ci"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.is_owner()
    async def cedula(self, ctx, cedula_id: str):
        """Fetches information for a given Uruguayan Cedula ID (owner only)."""
        if not cedula_id.isdigit():
            await ctx.send("Cedula ID must be numeric.")
            return

        await ctx.message.add_reaction(PROCESSING)
        cedula_data = await self.fetch_cedula_info(cedula_id)

        try:
            if cedula_data and "resp" in cedula_data:
                embed = self.create_cedula_embed(cedula_data)
                await ctx.send(embed=embed)
                await ctx.message.clear_reactions()
                await ctx.message.add_reaction(DONE)
            else:
                await ctx.message.clear_reactions()
                await ctx.message.add_reaction(ERROR)
        except Exception:
            self.logger.exception("Failed to build cedula embed")
            await ctx.message.clear_reactions()
            await ctx.message.add_reaction(ERROR)

    async def fetch_cedula_info(self, cedula_id):
        try:
            return await get_json(f"{CEDULA_LOOKUP_BASE_URL}/{cedula_id}")
        except Exception:
            self.logger.exception("Failed to fetch cedula info")
            return None

    def create_cedula_embed(self, data):
        embed = discord.Embed(title="Cedula Info", color=0x1A73E8)
        resp = data["resp"]
        embed.add_field(name="Full Name", value=f"{resp['nombre_raw']}", inline=False)
        embed.add_field(name="Cedula", value=resp["cedula"], inline=True)
        embed.add_field(
            name="Birth Date", value=resp["fechaNacimiento_raw"], inline=True
        )
        embed.add_field(
            name="Sectional Court", value=resp["seccionJudicial"], inline=True
        )
        embed.add_field(name="First Surname", value=resp["primerApellido"], inline=True)
        embed.add_field(
            name="Second Surname", value=resp["segundoApellido"], inline=True
        )
        embed.add_field(name="Gender", value=(resp["genero"] or "None"), inline=True)
        return embed


async def setup(bot):
    await bot.add_cog(CedulaInfo(bot))
