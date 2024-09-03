import requests
import discord
from discord.ext import commands


class CedulaInfo(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(aliases=["ci"])
    async def cedula(self, ctx, cedula_id: str):
        """Fetches and displays information for a given Uruguayan Cedula ID"""
        if cedula_id:
            await ctx.message.add_reaction("⌛")
            cedula_data = self.fetch_cedula_info(cedula_id)

            if cedula_data and "resp" in cedula_data:
                embed = self.create_cedula_embed(cedula_data)
                await ctx.send(embed=embed)
                await ctx.message.clear_reactions()
                await ctx.message.add_reaction("✅")
            else:
                await ctx.message.clear_reactions()
                await ctx.message.add_reaction("❌")

    def fetch_cedula_info(self, cedula_id):
        url = f"https://ci-uy.checkleaked.cc/{cedula_id}"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
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
        embed.add_field(
            name="Gender",
            value=(resp["genero"] or "None"),
            inline=True,
        )

        return embed


async def setup(bot):
    await bot.add_cog(CedulaInfo(bot))
