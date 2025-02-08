import aiohttp
import json
import textwrap
from discord.ext import commands

initial_prompt = """You are DJ Khaled, a Discord bot that embodies DJ Khaled's iconic personality and energy. You respond without a command prefix and support music, chess (facilitating player connections), and utility functions. 

When a user asks how to use a command or requests an example (e.g., "Khaled, how do I play a song?"), provide a clear and accurate example of the command in the format they can use directly. 
Always match the user's language and maintain DJ Khaled's vibrant and charismatic style in your responses.

Supported commands include:

### Bitcoin:
- `btc`: Fetch the current Bitcoin price and provide updates.
  **Example**: `btc`

### Cedula Information:
- `cedula`: Retrieve information for a Uruguayan Cedula.
  **Example**: `cedula 12345678`

### Chess:
- `chess`: Create an open chess challenge on Lichess.
  **Example**: `chess`

- `chess_leaderboard`: Display the top 5 players on the chess leaderboard.
  **Example**: `chess_leaderboard`

### Div:
- `div`: Fetch the price of Divine in a specified currency.
  **Example**: `div USD`

### Emoji:
- `emoji`: Convert input text into emoji letters.
  **Example**: `emoji Hello Khaled!`

### Sports:
- `premier`: View upcoming Premier League fixtures.
  **Example**: `premier`

- `f1`: Get details on upcoming Formula 1 race sessions.
  **Example**: `f1`

- `ufc`: Find information about the next UFC event and main card.
  **Example**: `ufc`

### Music:
- `playlist` or `pl`: Show the current playlist.
  **Example**: `_playlist`

- `clear`: Clear the playlist.
  **Example**: `clear`

- `loop`: Toggle looping for the current song.
  **Example**: `loop`

- `lyrics`: Provide lyrics for the current song (beta).
  **Example**: `lyrics`

- `most_played`: Display the most played songs.
  **Example**: `most_played`

- `most_requested`: Show the top 5 users with the most song requests.
  **Example**: `most_requested`

- `pause`: Pause the audio.
  **Example**: `pause`

- `play` or `p`: Play a song from a query or URL.
  **Example**: `play Shape of You` or `p https://youtube.com/example`

- `resume`: Resume audio playback.
  **Example**: `resume`

- `shuffle`: Toggle shuffle for the playlist.
  **Example**: `shuffle`

- `skip` or `s`: Skip the current song.
  **Example**: `skip`

- `stop`: Stop playback and disconnect the bot.
  **Example**: `stop`

### Purge:
- `purge`: Remove bot messages and command queries from the current channel.
  **Example**: `purge`

### Restart:
- `restart`: Restart the bot and reset its state.
  **Example**: `restart`

### Status:
- `status`: Check the current status of a user.
  **Example**: `status @username`

### Steam:
- `steam`: Retrieve details about a Steam game.
  **Example**: `steam Counter-Strike`

### Weather:
- `get_weather`: Get weather information for a specific city.
  **Example**: `get_weather New York`

### Leaderboards:
- `leaderboard` or `lb`: Display the top 5 users with the most hours.
  **Example**: `leaderboard`

- `most_requested`: Show users with the highest song requests.
  **Example**: `most_requested`

### Help:
- `help`: Display this list of commands.
  **Example**: `help`

Your responses always match the user's language, reflect DJ Khaled's charisma, and avoid prefixes like `[DJ Khaled]:`. 
You respond to one query at a time, providing clear examples when users ask how to use commands or request guidance. 
As well as talking about any current topic from DJ Khaleds perspective.
Always keep the vibe funny and ironic. 
[user]:
"""


def to_markdown(text):
    text = text.replace("•", "  *")
    return textwrap.indent(text, "> ", predicate=lambda _: True)

class AI(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.api_key = config["secrets"]["openaiKey"]
        self.api_url = config["secrets"]["openaiUrl"]
        self.initial_prompt = initial_prompt
        self.conversations = {}

    def get_conversation(self, ctx):
        """Retrieve or create a conversation history for the user/channel."""
        key = ctx.message.author.id  # Use channel ID as the key (or ctx.author.id for user-specific conversations)
        if key not in self.conversations:
            self.conversations[key] = [{
              "role": "system",
              "content": self.initial_prompt
            }]
        return self.conversations[key]

    def clear_conversation(self, ctx):
        """Clear the conversation history for the user/channel."""
        key = ctx.channel.id  # Use channel ID as the key (or ctx.author.id for user-specific conversations)
        if key in self.conversations:
            del self.conversations[key]

    @commands.hybrid_command(aliases=["gpt", "ai", "gen", "khaled"])
    async def ask(self, ctx, *, question):
        """Returns an answer to a question"""
        await ctx.message.add_reaction("⌛")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = [{
            "role": "user",
            "content": self.initial_prompt + question
        }]

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json={
                        "model": "gemini_2_0_flash.google/gemini-2.0-flash-001",
                        "messages": messages
                    }
                ) as response:
                    if response.status != 200:
                        await ctx.send("There was an error processing your request!")
                        await ctx.message.clear_reactions()
                        await ctx.message.add_reaction("❌")
                        return

                    response_data = await response.json()
                    response_text = response_data['choices'][0]['message']['content']
                    
                    await ctx.send(to_markdown(response_text))
                    await ctx.message.clear_reactions()
                    await ctx.message.add_reaction("✅")

        except Exception as e:
            print(f"API Error: {e}")
            await ctx.send("There was an error connecting to the AI service.")
            await ctx.message.clear_reactions()
            await ctx.message.add_reaction("❌")

    @commands.hybrid_command()
    async def chat(self, ctx, *, prompt):
        """Start a conversation with the AI"""
        await ctx.message.add_reaction("⌛")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        conversation = self.get_conversation(ctx)
        conversation.append({"role": "user", "content": prompt})

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json={
                        "model": "gemini_2_0_flash.google/gemini-2.0-flash-001",
                        "messages": conversation
                    }
                ) as response:
                    if response.status != 200:
                        await ctx.send("There was an error processing your request!")
                        await ctx.message.clear_reactions()
                        await ctx.message.add_reaction("❌")
                        return

                    response_data = await response.json()
                    response_text = response_data['choices'][0]['message']['content']
                    
                    conversation.append({"role": "assistant", "content": response_text})
                    
                    await ctx.send(to_markdown(response_text))
                    await ctx.message.clear_reactions()
                    await ctx.message.add_reaction("✅")

        except Exception as e:
            print(f"API Error: {e}")
            await ctx.send("There was an error connecting to the AI service.")
            await ctx.message.clear_reactions()
            await ctx.message.add_reaction("❌")

    @commands.hybrid_command()
    async def newchat(self, ctx, *, prompt=None):
        """
        Start a new chat session (clears conversation history).
        Optionally, provide a prompt to start the new chat.
        """
        self.clear_conversation(ctx)
        if prompt:
            await ctx.send("🔄 Conversation history cleared. Starting a new chat!")
            await self.chat(ctx, prompt=prompt)
        else:
          await ctx.send("🔄 Conversation history cleared. Ready for a new chat!")
          await ctx.message.add_reaction("✅")


async def setup(bot):
    with open("config.json") as f:
        config = json.load(f)
    await bot.add_cog(AI(bot, config))
