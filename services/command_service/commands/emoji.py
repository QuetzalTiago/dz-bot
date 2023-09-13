from .base import BaseCommand


class EmojiCommand(BaseCommand):
    @staticmethod
    def __str__():
        return "Converts the input text into emoji letters."

    async def execute(self):
        text = self.message.content[6:].strip()
        emoji_text = await self.text_to_emoji(text)
        await self.message.channel.send(emoji_text)

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
