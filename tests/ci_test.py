from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord.ext import commands

from cogs.ci import CedulaInfo


@pytest.fixture
def bot():
    return AsyncMock(spec=commands.Bot)


@pytest.fixture
def cog(bot):
    return CedulaInfo(bot)


def mock_ctx():
    ctx = MagicMock(spec=commands.Context)
    ctx.message = MagicMock(spec=discord.Message)
    ctx.message.add_reaction = AsyncMock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.send = AsyncMock()
    return ctx


CEDULA_RESPONSE = {
    "resp": {
        "nombre_raw": "Juan Perez",
        "cedula": "1.234.567-8",
        "fechaNacimiento_raw": "01/01/1990",
        "seccionJudicial": "1a",
        "primerApellido": "Perez",
        "segundoApellido": "Gomez",
        "genero": "M",
    }
}


@pytest.mark.asyncio
async def test_cedula_non_numeric_id_rejected(cog):
    ctx = mock_ctx()
    await cog.cedula.callback(cog, ctx, "abc123")

    ctx.send.assert_awaited_once_with("Cedula ID must be numeric.")
    ctx.message.add_reaction.assert_not_awaited()


@pytest.mark.asyncio
async def test_cedula_success(cog):
    ctx = mock_ctx()
    with patch("cogs.ci.get_json", new=AsyncMock(return_value=CEDULA_RESPONSE)):
        await cog.cedula.callback(cog, ctx, "12345678")

    ctx.message.add_reaction.assert_any_call("⌛")
    ctx.message.add_reaction.assert_any_call("✅")
    ctx.send.assert_awaited_once()
    _, kwargs = ctx.send.call_args
    embed = kwargs["embed"]
    assert isinstance(embed, discord.Embed)
    assert embed.fields[0].value == "Juan Perez"
    assert embed.fields[1].value == "1.234.567-8"


@pytest.mark.asyncio
async def test_cedula_missing_gender_defaults_to_none_text(cog):
    data = {"resp": {**CEDULA_RESPONSE["resp"], "genero": None}}
    embed = cog.create_cedula_embed(data)
    gender_field = next(f for f in embed.fields if f.name == "Gender")
    assert gender_field.value == "None"


@pytest.mark.asyncio
async def test_cedula_not_found_sets_error_reaction(cog):
    ctx = mock_ctx()
    with patch("cogs.ci.get_json", new=AsyncMock(return_value={})):
        await cog.cedula.callback(cog, ctx, "12345678")

    ctx.message.add_reaction.assert_any_call("❌")
    ctx.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_cedula_fetch_raises_is_caught_and_returns_none(cog):
    ctx = mock_ctx()
    with patch("cogs.ci.get_json", side_effect=Exception("boom")):
        await cog.cedula.callback(cog, ctx, "12345678")

    ctx.message.add_reaction.assert_any_call("❌")
    ctx.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_cedula_embed_build_failure_sets_error_reaction(cog):
    ctx = mock_ctx()
    # Missing expected keys inside "resp" triggers a KeyError while building the embed.
    with patch(
        "cogs.ci.get_json", new=AsyncMock(return_value={"resp": {"nombre_raw": "X"}})
    ):
        await cog.cedula.callback(cog, ctx, "12345678")

    ctx.message.add_reaction.assert_any_call("❌")
    ctx.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_cedula_info_returns_data_on_success(cog):
    with patch("cogs.ci.get_json", new=AsyncMock(return_value=CEDULA_RESPONSE)):
        result = await cog.fetch_cedula_info("12345678")
    assert result == CEDULA_RESPONSE


@pytest.mark.asyncio
async def test_fetch_cedula_info_returns_none_on_exception(cog):
    with patch("cogs.ci.get_json", side_effect=Exception("network down")):
        result = await cog.fetch_cedula_info("12345678")
    assert result is None
