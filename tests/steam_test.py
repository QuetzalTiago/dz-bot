import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands

from cogs.steam import Steam


class FakeResponse:
    def __init__(self, status, json_data=None):
        self.status = status
        self._json = json_data or {}

    async def json(self):
        return self._json

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


@pytest.fixture
def bot():
    return MagicMock(spec=commands.Bot)


@pytest.fixture
def cog(bot):
    with patch(
        "cogs.steam.load_config",
        return_value={"secrets": {"steamApiKey": "test_key"}},
    ):
        return Steam(bot)


def mock_ctx():
    ctx = MagicMock(spec=commands.Context)
    ctx.message = MagicMock(spec=discord.Message)
    ctx.message.add_reaction = AsyncMock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.send = AsyncMock()
    return ctx


GAME_DETAILS = {
    "name": "Portal 2",
    "steam_appid": 620,
    "short_description": "A puzzle game.",
    "header_image": "http://example.com/header.jpg",
    "price_overview": {"final": 999},
    "developers": ["Valve"],
    "release_date": {"date": "18 Apr, 2011"},
}


@pytest.mark.asyncio
async def test_gameinfo_success(cog):
    ctx = mock_ctx()
    with patch.object(
        cog, "search_game", new=AsyncMock(return_value=(620, GAME_DETAILS))
    ):
        await cog.gameinfo.callback(cog, ctx, game_name="Portal 2")

    ctx.send.assert_awaited_once()
    _, kwargs = ctx.send.call_args
    embed = kwargs["embed"]
    assert embed.title == "Portal 2"
    assert "$9.99" in embed.fields[0].value
    ctx.message.add_reaction.assert_any_call("🔍")
    ctx.message.add_reaction.assert_any_call("✅")


@pytest.mark.asyncio
async def test_gameinfo_free_to_play(cog):
    ctx = mock_ctx()
    details = {**GAME_DETAILS, "price_overview": {}, "is_free": True}
    with patch.object(
        cog, "search_game", new=AsyncMock(return_value=(620, details))
    ):
        await cog.gameinfo.callback(cog, ctx, game_name="Portal 2")

    _, kwargs = ctx.send.call_args
    assert kwargs["embed"].fields[0].value == "Free to Play"


def test_create_game_embed_missing_price_and_not_free_shows_na(cog):
    # A paid game unavailable/delisted for the queried country omits
    # price_overview without being free - must not be reported as free.
    details = {**GAME_DETAILS, "price_overview": {}, "is_free": False}
    embed = cog.create_game_embed(details)
    assert embed.fields[0].value == "N/A"


@pytest.mark.asyncio
async def test_gameinfo_not_found(cog):
    ctx = mock_ctx()
    with patch.object(cog, "search_game", new=AsyncMock(return_value=(None, None))):
        await cog.gameinfo.callback(cog, ctx, game_name="not a real game")

    ctx.send.assert_awaited_once_with(
        "Game not found. Please check the name and try again."
    )


@pytest.mark.asyncio
async def test_gameinfo_search_raises_is_caught(cog):
    ctx = mock_ctx()
    with patch.object(
        cog, "search_game", new=AsyncMock(side_effect=Exception("network down"))
    ):
        await cog.gameinfo.callback(cog, ctx, game_name="Portal 2")

    ctx.send.assert_awaited_once_with("Could not retrieve Steam game info right now.")
    ctx.message.add_reaction.assert_any_call("❌")


@pytest.mark.asyncio
async def test_gameinfo_error_clears_reaction_before_a_failing_send(cog):
    # Regression test: the ERROR reaction must be applied before ctx.send, not
    # after - otherwise a failing/rate-limited ctx.send (the exact scenario
    # this except block exists to report) leaves the SEARCHING reaction stuck
    # forever with no error indicator, matching every sibling API cog's order.
    ctx = mock_ctx()
    ctx.send = AsyncMock(side_effect=Exception("discord is down"))
    with patch.object(
        cog, "search_game", new=AsyncMock(side_effect=Exception("network down"))
    ):
        with pytest.raises(Exception, match="discord is down"):
            await cog.gameinfo.callback(cog, ctx, game_name="Portal 2")

    ctx.message.clear_reactions.assert_awaited_once()
    ctx.message.add_reaction.assert_any_call("❌")


@pytest.mark.asyncio
async def test_gameinfo_malformed_details_does_not_crash(cog):
    # Regression test: create_game_embed used to run outside the try/except
    # wrapping search_game, so a Steam response missing an expected key (a
    # real possibility for an unofficial/undocumented API) raised an
    # unhandled KeyError - the SEARCHING reaction was never cleared and the
    # user got no reply at all.
    ctx = mock_ctx()
    malformed_details = {"steam_appid": 620}  # missing "name", "header_image"
    with patch.object(
        cog, "search_game", new=AsyncMock(return_value=(620, malformed_details))
    ):
        await cog.gameinfo.callback(cog, ctx, game_name="Portal 2")

    ctx.send.assert_awaited_once_with("Could not retrieve Steam game info right now.")
    ctx.message.clear_reactions.assert_awaited_once()
    ctx.message.add_reaction.assert_any_call("❌")


@pytest.mark.asyncio
async def test_search_game_returns_none_on_non_200(cog):
    fake_session = MagicMock()
    fake_session.get = MagicMock(return_value=FakeResponse(500))
    with patch("cogs.steam.get_session", return_value=fake_session):
        result = await cog.search_game("Portal 2")
    assert result == (None, None)


@pytest.mark.asyncio
async def test_search_game_returns_none_when_no_items(cog):
    fake_session = MagicMock()
    fake_session.get = MagicMock(return_value=FakeResponse(200, {"items": []}))
    with patch("cogs.steam.get_session", return_value=fake_session):
        result = await cog.search_game("a game with no results")
    assert result == (None, None)


@pytest.mark.asyncio
async def test_search_game_success_looks_up_details(cog):
    search_response = FakeResponse(200, {"items": [{"id": 620}]})
    details_response = FakeResponse(
        200, {"620": {"success": True, "data": GAME_DETAILS}}
    )
    fake_session = MagicMock()
    fake_session.get = MagicMock(side_effect=[search_response, details_response])
    with patch("cogs.steam.get_session", return_value=fake_session):
        game_id, details = await cog.search_game("Portal 2")
    assert game_id == 620
    assert details == GAME_DETAILS


@pytest.mark.asyncio
async def test_get_game_details_returns_none_when_not_successful(cog):
    fake_session = MagicMock()
    fake_session.get = MagicMock(
        return_value=FakeResponse(200, {"620": {"success": False}})
    )
    with patch("cogs.steam.get_session", return_value=fake_session):
        result = await cog.get_game_details(620)
    assert result is None


def test_create_game_embed_uses_na_for_missing_developers(cog):
    details = {**GAME_DETAILS, "developers": []}
    embed = cog.create_game_embed(details)
    assert embed.fields[2].value == "N/A"


@pytest.mark.asyncio
async def test_cog_setup():
    bot = MagicMock(spec=commands.Bot)
    bot.add_cog = AsyncMock()
    with patch(
        "cogs.steam.load_config",
        return_value={"secrets": {"steamApiKey": "test_key"}},
    ):
        from cogs import steam

        await steam.setup(bot)
    bot.add_cog.assert_awaited_once()
