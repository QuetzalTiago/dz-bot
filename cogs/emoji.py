from discord.ext import commands

from cogs.utils.emojis import DONE
from cogs.utils.formatting import split_message


class Emoji(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def emoji(self, ctx, *, text: str = ""):
        """Converts the input text into emoji letters."""
        text = text.strip()
        if not text:
            await ctx.send("Give me some text, for example: `emoji hello`")
            return
        emoji_text = self.text_to_emoji(text)
        # Each letter expands to a multi-char emoji code, so ordinary-length
        # input can easily blow past Discord's 2000-char message limit.
        for chunk in split_message(emoji_text):
            await ctx.send(chunk)
        await ctx.message.clear_reactions()
        await ctx.message.add_reaction(DONE)

    @staticmethod
    def text_to_emoji(text):
        emoji_text = ""
        for char in text:
            char = char.lower()
            if "a" <= char <= "z":
                emoji_text += f":regional_indicator_{char}: "
            elif char == "?":
                emoji_text += "❔ "
            elif char == "!":
                emoji_text += "❕ "
            else:
                emoji_text += char + " "
        return emoji_text


async def setup(bot):
    await bot.add_cog(Emoji(bot))
