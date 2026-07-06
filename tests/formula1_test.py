from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord.ext import commands


@pytest.fixture
def bot():
    return AsyncMock(spec=commands.Bot)


@pytest.fixture
def cog(bot):
    with patch(
        "cogs.formula1.load_config",
        return_value={"secrets": {"apiSportsKey": "test_api_key"}},
    ):
        from cogs.formula1 import Formula1

        return Formula1(bot)


def mock_ctx():
    ctx = MagicMock(spec=commands.Context)
    ctx.message = MagicMock(spec=discord.Message)
    ctx.message.add_reaction = AsyncMock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.send = AsyncMock()
    return ctx


RACES_RESPONSE = {
    "response": [
        {
            "type": "Practice 1",
            "date": "2023-10-10T15:00:00+00:00",
            "competition": {"name": "Grand Prix"},
            "circuit": {"name": "Interlagos", "image": "http://example.com/c.png"},
        },
        {
            "type": "Race",
            "date": "2023-10-13T15:00:00+00:00",
            "competition": {"name": "Grand Prix"},
            "circuit": {"name": "Interlagos", "image": "http://example.com/c.png"},
        },
        {
            "type": "Sprint",
            "date": "2023-10-14T15:00:00+00:00",
            "competition": {"name": "Grand Prix"},
            "circuit": {"name": "Interlagos", "image": "http://example.com/c.png"},
        },
    ]
}


@pytest.mark.asyncio
async def test_f1_success_stops_after_race(cog):
    ctx = mock_ctx()
    with patch(
        "cogs.formula1.get_json", new=AsyncMock(return_value=RACES_RESPONSE)
    ), patch(
        "cogs.formula1.add_white_background",
        new=AsyncMock(return_value=BytesIO(b"img")),
    ):
        await cog.f1.callback(cog, ctx)

    ctx.message.add_reaction.assert_any_call("⌛")
    ctx.message.add_reaction.assert_any_call("✅")
    ctx.send.assert_awaited_once()
    _, kwargs = ctx.send.call_args
    embed = kwargs["embed"]
    assert isinstance(embed, discord.Embed)
    assert "Grand Prix" in embed.title
    # Practice 1 then Race - loop must stop once it hits the race, skipping Sprint.
    assert len(embed.fields) == 2
    assert embed.fields[1].name == "🏁 Race 🏁"
    assert isinstance(kwargs["file"], discord.File)


@pytest.mark.asyncio
async def test_f1_no_circuit_image_sends_no_file(cog):
    ctx = mock_ctx()
    response = {
        "response": [
            {
                "type": "Race",
                "date": "2023-10-13T15:00:00+00:00",
                "competition": {"name": "Grand Prix"},
                "circuit": {"name": "Interlagos", "image": None},
            }
        ]
    }
    with patch("cogs.formula1.get_json", new=AsyncMock(return_value=response)):
        await cog.f1.callback(cog, ctx)

    _, kwargs = ctx.send.call_args
    assert kwargs["file"] is None
    ctx.message.add_reaction.assert_any_call("✅")


@pytest.mark.asyncio
async def test_f1_no_upcoming_races(cog):
    ctx = mock_ctx()
    with patch(
        "cogs.formula1.get_json", new=AsyncMock(return_value={"response": []})
    ):
        await cog.f1.callback(cog, ctx)

    ctx.send.assert_awaited_once_with("No upcoming races found for Formula 1.")
    ctx.message.add_reaction.assert_any_call("✅")


@pytest.mark.asyncio
async def test_f1_error(cog):
    ctx = mock_ctx()
    with patch(
        "cogs.formula1.get_json", side_effect=Exception("API Error")
    ):
        await cog.f1.callback(cog, ctx)

    ctx.message.add_reaction.assert_any_call("❌")
    ctx.send.assert_awaited_with("Could not retrieve Formula 1 sessions right now.")
