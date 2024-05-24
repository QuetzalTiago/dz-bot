import json
import textwrap
import google.generativeai as genai

from discord.ext import commands


class AI(commands.Cog):

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.ai = genai.configure(api_key=config["secrets"]["google_api_ai"])
        self.model = genai.GenerativeModel('gemini-pro')

    @staticmethod
    def to_markdown(text):
        text = text.replace('•', '  *')
        return textwrap.indent(text, '> ', predicate=lambda _: True)

    @commands.hybrid_command()
    async def ask(self, ctx, question):
        """Returns an answer to a question"""
        await ctx.message.add_reaction("⌛")
        response = self.model.generate_content(question)
        await ctx.send(self.to_markdown(response.text))
        await ctx.message.clear_reactions()
        await ctx.message.add_reaction("✅")

    @commands.hybrid_command()
    async def chat(self, ctx, prompt):
        """Create a thread to chat with DJ Khaled"""
        await ctx.message.add_reaction("⌛")
        response = self.model.generate_content(prompt)
        await ctx.send(self.to_markdown(response.text))
        await ctx.message.clear_reactions()
        await ctx.message.add_reaction("✅")


async def setup(bot):
    with open("config.json") as f:
        config = json.load(f)
    await bot.add_cog(AI(bot, config))
