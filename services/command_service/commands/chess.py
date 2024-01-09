import asyncio
import json
from discord import Message
import requests
import ndjson
from services.job_service import JobService
from services.job_service.job import Job
from services.job_service.job_types import JobType
from .base import BaseCommand

with open("config.json") as f:
    config = json.load(f)

lichess_token = config["secrets"]["lichessToken"]
headers = {"Authorization": "Bearer " + lichess_token}


class ChessCommand(BaseCommand):
    def __init__(self, client, message: Message, job_service: JobService):
        super().__init__(client, message)
        self.job_service = job_service

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

        await self.save_match(match_id)

        # create job to check on game aftewards
        # save_match_job = Job(
        #     lambda: self.save_match(match_id),
        #     10,
        #     JobType.SAVE_MATCH,
        #     False,  # 50 minutes
        # )

        # self.job_service.add_job(save_match_job)

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
        ]
        game_ended = False

        while not game_ended:
            response = requests.get(
                f"https://lichess.org/game/export/{match_id}", headers=headers
            )
            print(response)
            if response.status_code == 200:
                decoder = ndjson.Decoder()
                for line in response.iter_lines():
                    if line:  # Check if line is not empty
                        data = decoder.decode(line.decode("utf-8"))
                        print(data)  # Handle the json data as needed)

                game_status = data.get("status", "")

                if game_status in game_ended_statuses:
                    game_ended = True
                    winner = data.get("winner", None)
                    end_message = f"Game ended with status: {game_status}."
                    if winner:
                        winner_side = "White" if winner == "white" else "Black"
                        end_message += f" Winner: {winner_side}"
                    await self.message.channel.send(end_message)
                    await self.message.channel.send(data)  # Send game data
            else:
                await asyncio.sleep(5)  # Wait for some time before checking again
