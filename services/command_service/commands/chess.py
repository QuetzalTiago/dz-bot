import asyncio
import json
from discord import Message
import discord
import requests
from services.job_service import JobService
from services.job_service.job import Job
from services.job_service.job_types import JobType
from .base import BaseCommand

with open("config.json") as f:
    config = json.load(f)

lichess_token = config["secrets"]["lichessToken"]
headers = {"Authorization": "Bearer " + lichess_token, "Accept": "application/json"}


class ChessCommand(BaseCommand):
    def __init__(self, client, message: Message):
        super().__init__(client, message)

    @staticmethod
    def __str__():
        return "Creates an open chess challenge on Lichess."

    async def execute(self):
        time_control = None
        increment = 3  # Default increment

        message_parts = self.message.content.split(" ")

        # Validate and set the time control
        if len(message_parts) > 1:
            time_control = int(message_parts[1])
            if time_control < 1 or time_control > 60:
                await self.message.channel.send(
                    "Invalid time control. Please specify a number of minutes between 1 and 60."
                )
                return

        # Validate and set the increment if provided
        if len(message_parts) > 2:
            increment = int(message_parts[2])
            if increment < 0 or increment > 60:  # Assuming 60 as maximum increment
                await self.message.channel.send(
                    "Invalid increment. Please specify a number of seconds between 0 and 60."
                )
                return

        payload = {}
        if time_control is not None:
            payload["clock"] = {
                "increment": increment,
                "limit": time_control * 60,  # Time control converted to seconds
            }

        await self.message.add_reaction("⌛")
        match_url = await self.fetch_match_url(payload)
        match_id = self.get_match_id(match_url)
        await self.message.channel.send(match_url)
        await self.message.clear_reactions()
        await self.message.add_reaction("✅")

        print(match_id)

        # create job
        save_match_job = Job(
            lambda: self.save_match(match_id),
            10,
            JobType.SAVE_MATCH,
            5400,  # 90 minutes
        )

        self.client.job_service.add_job(save_match_job)

    async def fetch_match_url(self, payload):
        response = requests.post(
            "https://lichess.org/api/challenge/open", headers=headers, json=payload
        )
        if response.status_code == 200:
            challenge_data = response.json()
            print(challenge_data)
            return challenge_data["challenge"]["url"]
        else:
            await self.message.channel.send(
                "There was a problem creating the challenge."
            )
            await self.message.channel.send(response)

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

    async def save_match(self, match_id):
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
            headers=headers,
        )

        if response.status_code == 200:
            data = response.json()
            print(data)
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
                await self.message.channel.send(embed=embed)
                self.client.db_service.save_chess_game(data)
                print("Chess game saved in db")
                self.client.job_service.remove_job(JobType.SAVE_MATCH)
                print(f"{JobType.SAVE_MATCH} ended.")
