import pytest
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands


@pytest.fixture
def bot():
    return AsyncMock(spec=commands.Bot)


@pytest.fixture
def cog(bot):
    with patch(
        "cogs.football.load_config",
        return_value={"secrets": {"apiSportsKey": "test_api_key"}},
    ):
        from cogs.football import Football

        return Football(bot)


def mock_ctx():
    ctx = MagicMock(spec=commands.Context)
    ctx.message = MagicMock(spec=discord.Message)
    ctx.message.add_reaction = AsyncMock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.send = AsyncMock()
    return ctx


LEAGUE_RESPONSE = {
    "response": [
        {
            "league": {"logo": "http://example.com/logo.png"},
            "seasons": [{"year": 2023}],
        }
    ]
}

FIXTURES_RESPONSE = {
    "response": [
        {
            "fixture": {
                "date": "2023-10-10T15:00:00+00:00",
                "venue": {"name": "Anfield"},
            },
            "teams": {
                "home": {"name": "Liverpool"},
                "away": {"name": "Manchester United"},
            },
        },
        {
            "fixture": {
                "date": "2023-10-13T15:00:00+00:00",
                "venue": {"name": "Stadium"},
            },
            "teams": {"home": {"name": "Norwich"}, "away": {"name": "Leeds"}},
        },
    ]
}


@pytest.mark.asyncio
async def test_premier_success(cog):
    ctx = mock_ctx()

    async def fake_get_json(url, headers=None):
        return LEAGUE_RESPONSE if "leagues" in url else FIXTURES_RESPONSE

    with patch("cogs.football.get_json", side_effect=fake_get_json), patch(
        "cogs.football.add_white_background",
        new=AsyncMock(return_value=BytesIO(b"img")),
    ):
        await cog.premier.callback(cog, ctx)

    ctx.message.add_reaction.assert_any_call("⌛")
    ctx.message.add_reaction.assert_any_call("✅")
    ctx.send.assert_awaited_once()
    _, kwargs = ctx.send.call_args
    assert isinstance(kwargs.get("embed"), discord.Embed)
    assert kwargs["embed"].title == "Premier League Upcoming Fixtures"
    # Only the priority-team fixture should appear.
    assert len(kwargs["embed"].fields) == 1


@pytest.mark.asyncio
async def test_premier_error(cog):
    ctx = mock_ctx()
    with patch("cogs.football.get_json", side_effect=Exception("API Error")):
        await cog.premier.callback(cog, ctx)
    ctx.message.add_reaction.assert_any_call("❌")
    ctx.send.assert_awaited_with(
        "Could not retrieve Premier League fixtures right now."
    )


@pytest.mark.asyncio
async def test_premier_no_season_data_clears_processing_reaction(cog):
    ctx = mock_ctx()
    no_season_response = {"response": [{"league": {"logo": "http://x/logo.png"}, "seasons": []}]}
    with patch("cogs.football.get_json", new=AsyncMock(return_value=no_season_response)):
        await cog.premier.callback(cog, ctx)

    ctx.send.assert_awaited_once_with("No season data available for the Premier League.")
    ctx.message.add_reaction.assert_any_call("⌛")
    ctx.message.add_reaction.assert_any_call("✅")
    ctx.message.clear_reactions.assert_awaited_once()
