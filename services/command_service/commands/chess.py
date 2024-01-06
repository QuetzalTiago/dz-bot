import json
import requests
from .base import BaseCommand

with open("config.json") as f:
    config = json.load(f)

lichess_token = config["secrets"]["lichessToken"]
headers = {"Authorization": "Bearer " + lichess_token}


class ChessCommand(BaseCommand):
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
        await self.message.channel.send(match_url)
        await self.message.clear_reactions()
        await self.message.add_reaction("✅")

    async def fetch_match_url(self, payload):
        response = requests.post(
            "https://lichess.org/api/challenge/open", headers=headers, json=payload
        )
        if response.status_code == 200:
            challenge_data = response.json()
            return challenge_data["challenge"]["url"]
        else:
            await self.message.channel.send(
                "There was a problem creating the challenge."
            )
            await self.message.channel.send(response)
