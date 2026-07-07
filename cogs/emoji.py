import logging

from discord.ext import commands

from cogs.utils.emojis import DONE, ERROR
from cogs.utils.formatting import split_message


class Emoji(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("discord")

    @commands.hybrid_command()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def emoji(self, ctx, *, text: str = ""):
        """Converts the input text into emoji letters."""
        text = text.strip()
        if not text:
            await ctx.send("Give me some text, for example: `emoji hello`")
            return
        emoji_text = self.text_to_emoji(text)
        try:
            # Each letter expands to a multi-char emoji code, so ordinary-length
            # input can easily blow past Discord's 2000-char message limit.
            for chunk in split_message(emoji_text):
                await ctx.send(chunk)
            await ctx.message.clear_reactions()
            await ctx.message.add_reaction(DONE)
        except Exception:
            self.logger.exception("Failed to send emoji response")
            try:
                await ctx.message.clear_reactions()
                await ctx.message.add_reaction(ERROR)
            except Exception:
                pass

    @staticmethod
    def text_to_emoji(text):
        emoji_text = ""
        for char in text:
            char = char.lower()
            # Some characters lowercase to more than one codepoint (e.g. the
            # Turkish dotted capital "İ" -> "i" + combining dot above) - the
            # range check below assumes a single character, so those must
            # fall through to the plain-text branch instead of producing a
            # corrupted ":regional_indicator_X:" shortcode.
            if len(char) == 1 and "a" <= char <= "z":
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
