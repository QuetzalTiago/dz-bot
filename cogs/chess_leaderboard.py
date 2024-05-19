from collections import defaultdict
from discord import Embed

from discord.ext import commands


class ChessLeaderboard(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(aliases=["clb", "chess leaderboard"])
    async def chess_leaderboard(self, ctx):
        """Shows the top 5 players on the chess leaderboard, including their win rates."""
        matches = self.bot.get_cog("Database").get_chess_games()
        leaderboard = self.calculate_leaderboard(matches)

        if not leaderboard:
            # Send a message if the leaderboard is empty
            await ctx.send("No games are available for the leaderboard.")
        else:
            embed = self.get_leaderboard_embed(leaderboard)
            await ctx.send(embed=embed)

    def calculate_leaderboard(self, chess_games):
        player_stats = defaultdict(lambda: {"wins": 0, "games": 0})

        for game in chess_games:
            # Skip if no winner
            if not game.winner:
                continue

            # Check if players exist and increment stats
            for color in ["white", "black"]:
                if color in game.players and "user" in game.players[color]:
                    player = game.players[color]["user"]["name"]
                    player_stats[player]["games"] += 1
                    if game.winner == color:
                        player_stats[player]["wins"] += 1

        # Calculate win rates and get top 5 players
        leaderboard = []
        for player, stats in player_stats.items():
            if stats["games"] > 0:
                win_rate = (stats["wins"] / stats["games"]) * 100
                leaderboard.append((player, stats["wins"], win_rate))

        leaderboard.sort(key=lambda x: (-x[1], -x[2]))  # Sort by wins, then by win rate
        return leaderboard[:5]  # Top 5 players

    def get_leaderboard_embed(self, leaderboard):
        embed = Embed(
            title="Chess Leaderboard",
            description="Top 5 players by win count and win rate",
            color=0x00FF00,  # You can adjust the color as needed
        )

        for username, wins, win_rate in leaderboard:
            description = f"Wins: {wins}, Win Rate: {win_rate:.2f}%"
            embed.add_field(name=username, value=description, inline=False)

        return embed


async def setup(bot):
    await bot.add_cog(ChessLeaderboard(bot))
