import pytest
from unittest.mock import AsyncMock, Mock

import discord
from discord.ext import commands

from cogs.emoji import Emoji


def mock_ctx():
    ctx = Mock()
    ctx.send = AsyncMock()
    ctx.message = Mock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.message.add_reaction = AsyncMock()
    return ctx


@pytest.fixture
def bot():
    intents = discord.Intents.default()
    return commands.Bot(command_prefix="!", intents=intents)


@pytest.fixture
def emoji_cog(bot):
    return Emoji(bot)


@pytest.mark.parametrize(
    "input_text, expected_output",
    [
        (
            "abcXYZ",
            ":regional_indicator_a: :regional_indicator_b: "
            ":regional_indicator_c: :regional_indicator_x: :regional_indicator_y: "
            ":regional_indicator_z: ",
        ),
        ("123?!#", "1 2 3 ❔ ❕ # "),
        ("", ""),
        # Non-ASCII letters (e.g. "é") are alphabetic per str.isalpha() but
        # have no `regional_indicator_*` Discord emoji; they must fall
        # through to the literal-character branch instead of emitting a
        # broken shortcode.
        (
            "café",
            ":regional_indicator_c: :regional_indicator_a: "
            ":regional_indicator_f: é ",
        ),
    ],
)
def test_text_to_emoji(emoji_cog, input_text, expected_output):
    assert emoji_cog.text_to_emoji(input_text) == expected_output


@pytest.mark.asyncio
async def test_emoji_command_success(emoji_cog):
    ctx = mock_ctx()
    await emoji_cog.emoji.callback(emoji_cog, ctx, text="Hi!")
    ctx.send.assert_awaited_once_with(
        ":regional_indicator_h: :regional_indicator_i: ❕ "
    )
    ctx.message.add_reaction.assert_awaited_once_with("✅")


@pytest.mark.asyncio
async def test_emoji_command_empty(emoji_cog):
    ctx = mock_ctx()
    await emoji_cog.emoji.callback(emoji_cog, ctx, text="")
    ctx.send.assert_awaited_once_with("Give me some text, for example: `emoji hello`")
