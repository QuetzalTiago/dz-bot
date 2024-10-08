import json
import discord
import requests
import logging
from discord.ext import commands, tasks


class Chess(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("discord")

    async def cog_load(self):
        self.save_match.cancel()
        with open("config.json") as f:
            config = json.load(f)
            self.lichess_token = config["secrets"]["lichessToken"]
            self.headers = {
                "Authorization": "Bearer " + self.lichess_token,
                "Accept": "application/json",
            }
        self.logger.info("Chess cog loaded and configured.")

    @commands.hybrid_command()
    async def chess(self, ctx):
        """Creates an open chess challenge on Lichess"""
        time_control = None
        increment = 3  # Default increment

        message_parts = ctx.message.content.split(" ")

        # Validate and set the time control
        if len(message_parts) > 1:
            try:
                time_control = int(message_parts[1])
                if time_control < 1 or time_control > 60:
                    await ctx.send(
                        "Invalid time control. Please specify a number of minutes between 1 and 60."
                    )
                    return
            except ValueError:
                await ctx.send("Time control must be an integer.")
                return

        # Validate and set the increment if provided
        if len(message_parts) > 2:
            try:
                increment = int(message_parts[2])
                if increment < 0 or increment > 60:  # Assuming 60 as maximum increment
                    await ctx.send(
                        "Invalid increment. Please specify a number of seconds between 0 and 60."
                    )
                    return
            except ValueError:
                await ctx.send("Increment must be an integer.")
                return

        payload = {}
        if time_control is not None:
            payload["clock"] = {
                "increment": increment,
                "limit": time_control * 60,  # Time control converted to seconds
            }

        await ctx.message.add_reaction("⌛")
        self.logger.debug(
            f"Creating chess match with time control {time_control} minutes and {increment} seconds increment."
        )
        match_url = await self.fetch_match_url(ctx, payload)
        if match_url:
            match_id = self.get_match_id(match_url)
            await ctx.send(match_url)
            await ctx.message.clear_reactions()
            await ctx.message.add_reaction("✅")
            self.logger.info(f"Chess match created: {match_url}")
            self.save_match.start(ctx, match_id)
        else:
            self.logger.error("Failed to create chess match.")

    async def fetch_match_url(self, ctx, payload):
        try:
            response = requests.post(
                "https://lichess.org/api/challenge/open",
                headers=self.headers,
                json=payload,
            )
            if response.status_code == 200:
                challenge_data = response.json()
                return challenge_data["url"]
            else:
                await ctx.send("There was a problem creating the challenge.")
                self.logger.error(
                    f"Error creating challenge: {response.status_code} - {response.text}"
                )
                return None
        except requests.RequestException as e:
            await ctx.send("An error occurred while connecting to Lichess.")
            self.logger.exception(f"RequestException during challenge creation: {e}")
            return None

    def get_match_id(self, url):
        return url.rsplit("/", 1)[-1]

    def create_game_summary_embed(
        self, game_id, game_status, white_username, black_username, winner
    ):
        title_message = f"Game ended with **{game_status}**"
        end_message = f"White: **{white_username}**\n"
        end_message += f"Black: **{black_username}**\n"
        end_message += f"https://lichess.org/{game_id}\n"

        if winner:
            winner_username = white_username if winner == "white" else black_username
            if winner_username == "Anonymous":
                winner_color = "White" if winner == "white" else "Black"
                title_message = f"{winner_color} wins!"
            else:
                title_message = f"{winner_username} wins!"

        if white_username == "Anonymous" and black_username == "Anonymous":
            end_message = f"https://lichess.org/{game_id}\n"

        embed = discord.Embed(
            title=title_message, description=end_message, color=0x00FF00
        )
        return embed

    @tasks.loop(seconds=20, count=270)
    async def save_match(self, ctx, match_id):
        game_ended_statuses = [
            "mate",
            "resign",
            "stalemate",
            "timeout",
            "draw",
            "outoftime",
            "cheat",
            "noStart",
            "unknownFinish",
            "variantEnd",
            "aborted",
        ]

        response = requests.get(
            f"https://lichess.org/game/export/{match_id}?moves=false&pgnInJson=false",
            headers=self.headers,
        )

        if response.status_code == 200:
            data = response.json()
            game_status = data.get("status", "")
            players = data.get("players", {})

            white_username = (
                players.get("white", {}).get("user", {}).get("name", "Anonymous")
            )
            black_username = (
                players.get("black", {}).get("user", {}).get("name", "Anonymous")
            )

            if game_status in game_ended_statuses:
                winner = data.get("winner", None)

                embed = self.create_game_summary_embed(
                    match_id,
                    game_status,
                    white_username,
                    black_username,
                    winner,
                )
                await ctx.send(embed=embed)
                self.bot.get_cog("Database").save_chess_game(data)
                self.logger.info(f"Chess game saved: {match_id}")
                self.save_match.cancel()
        else:
            self.logger.error(
                f"Failed to fetch game data for {match_id}: {response.status_code} - {response.text}"
            )


async def setup(bot):
    await bot.add_cog(Chess(bot))
