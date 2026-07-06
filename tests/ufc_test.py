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
        "cogs.ufc.load_config",
        return_value={"secrets": {"apiSportsKey": "test_api_key"}},
    ):
        from cogs.ufc import UFC

        return UFC(bot)


def mock_ctx():
    ctx = MagicMock(spec=commands.Context)
    ctx.message = MagicMock(spec=discord.Message)
    ctx.message.add_reaction = AsyncMock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.send = AsyncMock()
    return ctx


def make_fight(name1, name2, date, category="Main Card", slug="UFC 300"):
    return {
        "slug": slug,
        "date": date,
        "category": category,
        "fighters": {
            "first": {"name": name1, "logo": "http://example.com/1.png"},
            "second": {"name": name2, "logo": "http://example.com/2.png"},
        },
    }


@pytest.mark.asyncio
async def test_ufc_success_builds_embed_from_main_card(cog):
    ctx = mock_ctx()
    fights = [
        make_fight("A", "B", "2023-10-10T15:00:00+00:00"),
        make_fight("C", "D", "2023-10-10T16:00:00+00:00"),
        make_fight("E", "F", "2023-10-10T17:00:00+00:00", slug="UFC 300: Main"),
    ]
    with patch.object(
        cog, "get_next_event", new=AsyncMock(return_value=(fights, "2023-10-10"))
    ), patch(
        "cogs.ufc.combine_fighter_logos",
        new=AsyncMock(return_value=BytesIO(b"combined")),
    ):
        await cog.ufc.callback(cog, ctx)

    ctx.message.add_reaction.assert_any_call("⌛")
    ctx.message.add_reaction.assert_any_call("✅")
    ctx.send.assert_awaited_once()
    _, kwargs = ctx.send.call_args
    embed = kwargs["embed"]
    assert isinstance(embed, discord.Embed)
    # Main event is the last fight in the main card slice.
    assert "UFC 300: Main" in embed.title
    # One date field plus one field per main-card fight.
    assert len(embed.fields) == 1 + len(fights)
    assert embed.fields[1].name == "A vs B"
    assert isinstance(kwargs["file"], discord.File)


@pytest.mark.asyncio
async def test_ufc_no_events_found_within_lookahead(cog):
    ctx = mock_ctx()
    with patch("cogs.ufc.get_json", new=AsyncMock(return_value={"response": []})):
        await cog.ufc.callback(cog, ctx)

    ctx.send.assert_awaited_once_with("No upcoming UFC events found.")
    ctx.message.add_reaction.assert_any_call("✅")


@pytest.mark.asyncio
async def test_ufc_fetch_error_sets_error_reaction(cog):
    ctx = mock_ctx()
    with patch("cogs.ufc.get_json", side_effect=Exception("API down")):
        await cog.ufc.callback(cog, ctx)

    ctx.message.add_reaction.assert_any_call("❌")
    ctx.send.assert_awaited_once_with("Could not retrieve UFC events right now.")


@pytest.mark.asyncio
async def test_get_next_event_merges_next_day_fights(cog):
    fights_day1 = [make_fight("A", "B", "2023-10-10T15:00:00+00:00")]
    fights_day2 = [make_fight("C", "D", "2023-10-11T15:00:00+00:00")]
    responses = [fights_day1, fights_day2]

    async def fake_fights_on(date_str):
        return responses.pop(0)

    with patch.object(cog, "_fights_on", side_effect=fake_fights_on):
        all_fights, event_date = await cog.get_next_event()

    assert all_fights == fights_day1 + fights_day2
    assert event_date is not None


@pytest.mark.asyncio
async def test_get_next_event_gives_up_after_lookahead_window(cog):
    with patch.object(cog, "_fights_on", new=AsyncMock(return_value=[])) as fetch:
        all_fights, event_date = await cog.get_next_event()

    assert all_fights == []
    assert event_date is None
    from cogs.ufc import MAX_LOOKAHEAD_DAYS

    assert fetch.await_count == MAX_LOOKAHEAD_DAYS


@pytest.mark.asyncio
async def test_fights_on_returns_response_list(cog):
    with patch(
        "cogs.ufc.get_json",
        new=AsyncMock(return_value={"response": [{"id": 1}]}),
    ):
        result = await cog._fights_on("2023-10-10")

    assert result == [{"id": 1}]


@pytest.mark.asyncio
async def test_fights_on_missing_response_key_returns_empty_list(cog):
    with patch("cogs.ufc.get_json", new=AsyncMock(return_value={})):
        result = await cog._fights_on("2023-10-10")

    assert result == []


def test_get_headers_includes_api_key(cog):
    headers = cog.get_headers()
    assert headers["x-rapidapi-key"] == "test_api_key"
    assert headers["x-rapidapi-host"] == "v1.mma.api-sports.io"
