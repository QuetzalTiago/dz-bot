import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands

from cogs.weather import Weather


class FakeResponse:
    def __init__(self, status, json_data=None):
        self.status = status
        self._json = json_data or {}

    async def json(self):
        return self._json

    def raise_for_status(self):
        if self.status >= 400:
            raise Exception(f"HTTP {self.status}")

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
        "cogs.weather.load_config",
        return_value={"secrets": {"weatherApiKey": "test_key"}},
    ):
        return Weather(bot)


def mock_ctx():
    ctx = MagicMock(spec=commands.Context)
    ctx.message = MagicMock(spec=discord.Message)
    ctx.message.add_reaction = AsyncMock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.send = AsyncMock()
    return ctx


WEATHER_DATA = {
    "timezone": -18000,
    "sys": {"sunset": 1700000000, "sunrise": 1699960000},
    "wind": {"speed": 3.5, "deg": 180},
    "main": {"humidity": 55, "pressure": 1012, "temp": 21.456},
    "weather": [{"description": "clear sky"}],
    "visibility": 10000,
}


@pytest.mark.asyncio
async def test_get_weather_success(cog):
    ctx = mock_ctx()
    fake_session = MagicMock()
    fake_session.get = MagicMock(return_value=FakeResponse(200, WEATHER_DATA))
    with patch("cogs.weather.get_session", return_value=fake_session):
        await cog.get_weather.callback(cog, ctx, city="Montevideo")

    ctx.send.assert_awaited_once()
    _, kwargs = ctx.send.call_args
    embed = kwargs["embed"]
    assert embed.title == "Weather in Montevideo"
    assert "21.5" in embed.fields[6].value
    ctx.message.add_reaction.assert_any_call("⌛")
    ctx.message.add_reaction.assert_any_call("✅")


@pytest.mark.asyncio
async def test_get_weather_uses_default_city_when_none_given(cog):
    cog.default_city = "Montevideo"
    ctx = mock_ctx()
    fake_session = MagicMock()
    fake_session.get = MagicMock(return_value=FakeResponse(200, WEATHER_DATA))
    with patch("cogs.weather.get_session", return_value=fake_session):
        await cog.get_weather.callback(cog, ctx, city=None)

    fake_session.get.assert_called_once()
    _, kwargs = fake_session.get.call_args
    assert kwargs["params"]["q"] == "Montevideo"


@pytest.mark.asyncio
async def test_get_weather_no_city_and_no_default(cog):
    cog.default_city = None
    ctx = mock_ctx()

    await cog.get_weather.callback(cog, ctx, city=None)

    ctx.send.assert_awaited_once_with(
        "Please provide a city name or configure a default city."
    )
    ctx.message.add_reaction.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_weather_city_not_found(cog):
    ctx = mock_ctx()
    fake_session = MagicMock()
    fake_session.get = MagicMock(return_value=FakeResponse(404))
    with patch("cogs.weather.get_session", return_value=fake_session):
        await cog.get_weather.callback(cog, ctx, city="Nowhereville")

    ctx.send.assert_awaited_once_with("City not found. Check the name and try again.")
    ctx.message.add_reaction.assert_any_call("❌")


@pytest.mark.asyncio
async def test_get_weather_http_error_is_caught(cog):
    ctx = mock_ctx()
    fake_session = MagicMock()
    fake_session.get = MagicMock(return_value=FakeResponse(500))
    with patch("cogs.weather.get_session", return_value=fake_session):
        await cog.get_weather.callback(cog, ctx, city="Montevideo")

    ctx.send.assert_awaited_once_with(
        "Could not retrieve weather right now. Try again later."
    )
    ctx.message.add_reaction.assert_any_call("❌")


@pytest.mark.asyncio
async def test_get_weather_malformed_response_does_not_leave_reaction_stuck(cog):
    # Regression test: create_weather_embed used to run after the
    # try/except wrapping the fetch, so a response missing an expected key
    # (OpenWeatherMap omits "wind.deg" for calm-wind reports) raised an
    # unhandled KeyError, leaving the PROCESSING reaction stuck forever with
    # no error message sent.
    ctx = mock_ctx()
    malformed_data = {**WEATHER_DATA, "wind": {"speed": 0.0}}  # no "deg"
    fake_session = MagicMock()
    fake_session.get = MagicMock(return_value=FakeResponse(200, malformed_data))
    with patch("cogs.weather.get_session", return_value=fake_session):
        await cog.get_weather.callback(cog, ctx, city="Calmville")

    ctx.send.assert_awaited_once_with(
        "Could not retrieve weather right now. Try again later."
    )
    ctx.message.clear_reactions.assert_awaited_once()
    ctx.message.add_reaction.assert_any_call("❌")


def test_create_weather_embed_defaults_rain_to_zero(cog):
    embed = cog.create_weather_embed("Montevideo", WEATHER_DATA)
    rain_field = next(f for f in embed.fields if f.name == "Rain (last 1h)")
    assert rain_field.value == "0 mm"


def test_format_time_applies_timezone_offset():
    from cogs.weather import Weather

    result = Weather.format_time(MagicMock(), 1700000000, -18000)
    assert isinstance(result, str)
    assert ":" in result


@pytest.mark.asyncio
async def test_cog_setup():
    bot = MagicMock(spec=commands.Bot)
    bot.add_cog = AsyncMock()
    with patch(
        "cogs.weather.load_config",
        return_value={"secrets": {"weatherApiKey": "test_key"}},
    ):
        from cogs import weather

        await weather.setup(bot)
    bot.add_cog.assert_awaited_once()
