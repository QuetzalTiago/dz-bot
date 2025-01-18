# # test_your_cog.py
# import pytest
# from unittest.mock import AsyncMock, MagicMock, patch
# from discord.ext import commands
# from discord import Intents
# from your_cog_module import YourCog  # Replace with your actual cog module and class
# import requests  # If you need to handle requests exceptions

# @pytest.fixture
# def bot():
#     intents = Intents.default()
#     intents.message_content = True  # Enable if your cog uses message content
#     return commands.Bot(command_prefix='!', intents=intents)

# @pytest.fixture
# def your_cog(bot):
#     return YourCog(bot)

# def mock_ctx(message_content):
#     ctx = MagicMock()
#     ctx.message.content = message_content
#     ctx.message.add_reaction = AsyncMock()
#     ctx.message.clear_reactions = AsyncMock()
#     ctx.send = AsyncMock()
#     ctx.message.guild = MagicMock()
#     ctx.message.author = MagicMock()
#     return ctx

# @pytest.mark.asyncio
# async def test_your_command_success(your_cog):
#     ctx = mock_ctx('your_command arg1 arg2')

#     with patch('your_cog_module.external_dependency') as mock_dependency:
#         mock_dependency.return_value = 'expected result'

#         await your_cog.your_command.callback(your_cog, ctx)

#     ctx.message.add_reaction.assert_any_call('✅')
#     ctx.send.assert_called_with('Success message')

# # Additional tests for different scenarios
