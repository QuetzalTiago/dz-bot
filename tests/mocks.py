from unittest.mock import AsyncMock, MagicMock
from discord.ext import commands
import discord


def mock_ctx(bot, **kwargs):
    """
    Create a mock of discord.ext.commands.Context with specified attributes.
    Args:
        bot (commands.Bot): The bot instance.
        **kwargs: Additional attributes to customize the mocked context.
    Returns:
        MagicMock: A mocked discord.ext.commands.Context object.
    """
    ctx = MagicMock(spec=commands.Context)
    ctx.bot = bot
    ctx.guild = kwargs.get('guild', MagicMock(spec=discord.Guild))
    ctx.author = kwargs.get('author', MagicMock(spec=discord.Member))
    ctx.channel = kwargs.get('channel', MagicMock(spec=discord.TextChannel))
    ctx.message = kwargs.get('message', MagicMock(spec=discord.Message))
    ctx.voice_client = kwargs.get('voice_client', MagicMock(spec=discord.VoiceClient))

    # Customize the `author.voice` attribute
    ctx.author.voice = kwargs.get('voice', MagicMock())

    # Set message content or use a default
    ctx.message.content = kwargs.get('content', '')

    # Mock methods with AsyncMock for async behavior
    ctx.send = AsyncMock()
    ctx.send.return_value.delete = AsyncMock()
    ctx.message.delete = AsyncMock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.message.add_reaction = AsyncMock()
    ctx.reply = AsyncMock()

    # Ensure `ctx.message.author` and `ctx.message.channel` are linked correctly
    ctx.message.author = ctx.author
    ctx.message.channel = ctx.channel
    ctx.message.channel.send = AsyncMock()
    ctx.message.channel.send.return_value.delete = AsyncMock()

    # Mock DM sending behavior
    ctx.author.send = AsyncMock()
    ctx.author.send.return_value.delete = AsyncMock()

    return ctx
