import asyncio
import logging

import discord
from discord.ext import commands

from cogs.utils.config import load_config
from cogs.utils.emojis import DONE, ERROR, PROCESSING
from cogs.utils.endpoints import LICHESS_BASE_URL, LICHESS_CHALLENGE_OPEN_URL
from cogs.utils.http import get_session

GAME_ENDED_STATUSES = {
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
}

POLL_INTERVAL_SECONDS = 20
MAX_POLLS = 270  # ~90 minutes


class Chess(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("discord")
        self.lichess_token = None
        self.headers = {}
        self._watch_tasks = set()

    async def cog_load(self):
        config = load_config()
        self.lichess_token = config["secrets"]["lichessToken"]
        self.headers = {
            "Authorization": "Bearer " + self.lichess_token,
            "Accept": "application/json",
        }
        self.logger.info("Chess cog loaded and configured.")

    async def cog_unload(self):
        for task in list(self._watch_tasks):
            task.cancel()

    @commands.hybrid_command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def chess(self, ctx, minutes: int = None, increment: int = 3):
        """Creates an open chess challenge on Lichess.

        Optional: `chess <minutes 1-60> <increment 0-60>`.
        """
        if minutes is not None and not (1 <= minutes <= 60):
            await ctx.send("Time control must be between 1 and 60 minutes.")
            return
        if not (0 <= increment <= 60):
            await ctx.send("Increment must be between 0 and 60 seconds.")
            return

        payload = {}
        if minutes is not None:
            payload["clock"] = {"increment": increment, "limit": minutes * 60}

        await ctx.message.add_reaction(PROCESSING)
        match_url = await self.fetch_match_url(ctx, payload)
        if not match_url:
            self.logger.error("Failed to create chess match.")
            await ctx.message.clear_reactions()
            await ctx.message.add_reaction(ERROR)
            return

        match_id = self.get_match_id(match_url)
        await ctx.send(match_url)
        await ctx.message.clear_reactions()
        await ctx.message.add_reaction(DONE)
        self.logger.info(f"Chess match created: {match_url}")

        # Each game gets its own watcher so concurrent games don't collide (the
        # old single cog-level task loop raised RuntimeError on the 2nd game).
        task = asyncio.create_task(self._watch_match(ctx, match_id))
        self._watch_tasks.add(task)
        task.add_done_callback(self._watch_tasks.discard)

    async def fetch_match_url(self, ctx, payload):
        try:
            session = get_session()
            async with session.post(
                LICHESS_CHALLENGE_OPEN_URL,
                headers=self.headers,
                json=payload,
            ) as response:
                if response.status == 200:
                    challenge_data = await response.json()
                    return challenge_data["url"]
                await ctx.send("There was a problem creating the challenge.")
                self.logger.error(
                    "Error creating challenge: %s - %s",
                    response.status,
                    await response.text(),
                )
                return None
        except Exception:
            await ctx.send("An error occurred while connecting to Lichess.")
            self.logger.exception("Exception during challenge creation")
            return None

    def get_match_id(self, url):
        return url.rsplit("/", 1)[-1]

    def create_game_summary_embed(
        self, game_id, game_status, white_username, black_username, winner
    ):
        title_message = f"Game ended with **{game_status}**"
        end_message = f"White: **{white_username}**\n"
        end_message += f"Black: **{black_username}**\n"
        end_message += f"{LICHESS_BASE_URL}/{game_id}\n"

        if winner:
            winner_username = white_username if winner == "white" else black_username
            if winner_username == "Anonymous":
                winner_color = "White" if winner == "white" else "Black"
                title_message = f"{winner_color} wins!"
            else:
                title_message = f"{winner_username} wins!"

        if white_username == "Anonymous" and black_username == "Anonymous":
            end_message = f"{LICHESS_BASE_URL}/{game_id}\n"

        return discord.Embed(
            title=title_message, description=end_message, color=0x00FF00
        )

    async def _watch_match(self, ctx, match_id):
        """Poll Lichess until the game ends, then post a summary and save it."""
        session = get_session()
        for _ in range(MAX_POLLS):
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            try:
                async with session.get(
                    f"{LICHESS_BASE_URL}/game/export/{match_id}"
                    "?moves=false&pgnInJson=false",
                    headers=self.headers,
                ) as response:
                    if response.status != 200:
                        self.logger.error(
                            "Failed to fetch game data for %s: %s",
                            match_id,
                            response.status,
                        )
                        continue
                    data = await response.json()
            except Exception:
                self.logger.exception("Error polling chess game %s", match_id)
                continue

            game_status = data.get("status", "")
            players = data.get("players", {})
            white_username = (
                players.get("white", {}).get("user", {}).get("name", "Anonymous")
            )
            black_username = (
                players.get("black", {}).get("user", {}).get("name", "Anonymous")
            )

            if game_status in GAME_ENDED_STATUSES:
                embed = self.create_game_summary_embed(
                    match_id,
                    game_status,
                    white_username,
                    black_username,
                    data.get("winner"),
                )
                await ctx.send(embed=embed)
                db = self.bot.get_cog("Database")
                if db is not None:
                    await db.save_chess_game(data)
                self.logger.info(f"Chess game saved: {match_id}")
                return


async def setup(bot):
    await bot.add_cog(Chess(bot))
