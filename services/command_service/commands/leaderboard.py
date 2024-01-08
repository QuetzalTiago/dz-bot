from discord import Message, Client
from services.db_service.db_service import DatabaseService
from .base import BaseCommand


class LeaderboardCommand(BaseCommand):
    def __init__(self, client: Client, message: Message, db_service: DatabaseService):
        super().__init__(client, message)
        self.db_service = db_service

    @staticmethod
    def __str__():
        return "Gets the leaderboard for the top 5 users with most hours."

    async def execute(self):
        user_hours_list = self.db_service.get_all_user_hours()

        sorted_user_hours = sorted(user_hours_list, key=lambda x: x[1], reverse=True)[
            :5
        ]  # Get top 5

        leaderboard_message = "🏆 **Leaderboard** 🏆\n\n"

        for index, (user_id, hours) in enumerate(sorted_user_hours, start=1):
            member = await self.client.get_user(user_id)
            if member:
                username = member.name
            else:
                username = f"ID: {user_id}"

            leaderboard_message += (
                f"**#{index} {username}** - {round(hours, 2)} hours\n"
            )

        await self.message.channel.send(leaderboard_message)

        await self.message.clear_reactions()
        await self.message.add_reaction("✅")
