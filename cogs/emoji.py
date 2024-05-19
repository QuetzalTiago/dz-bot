from discord.ext import commands


class Emoji(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command()
    async def emoji(self, ctx):
        """Converts the input text into emoji letters."""
        text = ctx.message.content[6:].strip()
        emoji_text = await self.text_to_emoji(text)
        await ctx.message.channel.send(emoji_text)

    async def text_to_emoji(_, text):
        emoji_text = ""
        for char in text:
            char = char.lower()
            if char.isalpha():
                emoji_char = f":regional_indicator_{char}:"
                emoji_text += f"{emoji_char} "
            elif char == "?":
                emoji_text += "❔ "
            elif char == "!":
                emoji_text += "❕ "
            else:
                emoji_text += char + " "
        return emoji_text


async def setup(bot):
    await bot.add_cog(Emoji(bot))
