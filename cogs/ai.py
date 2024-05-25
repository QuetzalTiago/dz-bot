import json
import textwrap
import google.generativeai as genai

from discord.ext import commands


class AI(commands.Cog):

    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.ai = genai.configure(api_key=config["secrets"]["google_api_ai"])
        self.model = genai.GenerativeModel("gemini-pro")
        self.initial_prompt = """You are DJ Khaled a Discord bot impersonating DJ Khaled, without a command prefix, designed for music, chess (this is not to play against you, but to facilitate a link for two players), and utility functionalities. 
        It recognizes and processes commands like play, skip, loop, stop, clear, queue, purge, restart (this is for the entire bot to restart not music), help, btc, emoji, and chess. 
        In every response, it includes aspects of DJ Khaled's personality, responds in the same language of the user. 
        Only gives one response, it doesnt make text for the user, when responding, it does not use '[DJ Khaled]:'. 
        [user]: """

    @staticmethod
    def to_markdown(text):
        text = text.replace("•", "  *")
        return textwrap.indent(text, "> ", predicate=lambda _: True)

    @commands.hybrid_command()
    async def ask(self, ctx, question):
        """Returns an answer to a question"""
        await ctx.message.add_reaction("⌛")
        user_prompt = ctx.message.content[4:]
        print(user_prompt)
        response = self.model.generate_content(self.initial_prompt + user_prompt)

        if not response.text:
            await ctx.send("There was an error with the query, please try again!")
            await ctx.message.clear_reactions()
            await ctx.message.add_reaction("❌")
            return

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
