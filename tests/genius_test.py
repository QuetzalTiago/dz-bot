from unittest.mock import MagicMock, patch

import pytest

from cogs.api.genius import GeniusAPI


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
def config():
    return {"secrets": {"geniusApiKey": "test_key"}}


@pytest.fixture
def api(config):
    return GeniusAPI(config)


def test_init_does_not_raise_when_secret_missing():
    # Regression test: Genius lyrics are optional. Downloader unconditionally
    # constructs GeniusAPI for every guild, so a direct
    # `config["secrets"]["geniusApiKey"]` index (raising KeyError when the
    # deployment skips the optional Genius integration) used to break every
    # music command, not just lyrics ones - matching every sibling API-key cog
    # (football/formula1/ufc/steam/weather), this must use `.get(...)`.
    api = GeniusAPI({"secrets": {}})
    assert api.headers == {"Authorization": "Bearer None"}


LYRICS_HTML = """
<html><body>
<script>ignore me</script>
<div data-lyrics-container="true">[Verse 1]
Hello world
</div>
<div data-lyrics-container="true">[Chorus]
La la la
</div>
</body></html>
"""


def test_init_sets_base_url_and_auth_header(config):
    api = GeniusAPI(config)
    assert api.base_url == "https://api.genius.com"
    assert api.headers == {"Authorization": "Bearer test_key"}


@pytest.mark.asyncio
async def test_fetch_lyrics_rejects_playlist_urls(api):
    assert await api.fetch_lyrics("some song /playlist/ abc") is None
    assert await api.fetch_lyrics("song list=PL123") is None


@pytest.mark.asyncio
async def test_fetch_lyrics_returns_none_when_search_fails(api):
    fake_session = MagicMock()
    fake_session.get = MagicMock(return_value=FakeResponse(500))
    with patch("cogs.api.genius.get_session", return_value=fake_session):
        result = await api.fetch_lyrics("Some Song")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_lyrics_returns_none_when_no_hits(api):
    fake_session = MagicMock()
    fake_session.get = MagicMock(
        return_value=FakeResponse(200, {"response": {"hits": []}})
    )
    with patch("cogs.api.genius.get_session", return_value=fake_session):
        result = await api.fetch_lyrics("Obscure Song")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_lyrics_success_parses_and_formats_lyrics(api):
    fake_session = MagicMock()
    fake_session.get = MagicMock(
        return_value=FakeResponse(
            200,
            {
                "response": {
                    "hits": [
                        {"result": {"url": "https://genius.com/some-song-lyrics"}}
                    ]
                }
            },
        )
    )
    with patch("cogs.api.genius.get_session", return_value=fake_session), patch(
        "cogs.api.genius.get_text", return_value=LYRICS_HTML
    ):
        result = await api.fetch_lyrics("Some Song (Live)")

    assert result is not None
    assert "Hello world" in result
    assert "La la la" in result
    assert "ignore me" not in result
    # query for search must strip the parenthetical suffix
    _, kwargs = fake_session.get.call_args
    assert kwargs["params"]["q"] == "Some Song "


@pytest.mark.asyncio
async def test_fetch_lyrics_uses_auth_header(api):
    fake_session = MagicMock()
    fake_session.get = MagicMock(
        return_value=FakeResponse(200, {"response": {"hits": []}})
    )
    with patch("cogs.api.genius.get_session", return_value=fake_session):
        await api.fetch_lyrics("Some Song")

    _, kwargs = fake_session.get.call_args
    assert kwargs["headers"] == {"Authorization": "Bearer test_key"}


@pytest.mark.asyncio
async def test_fetch_lyrics_returns_none_on_missing_lyrics_container(api):
    fake_session = MagicMock()
    fake_session.get = MagicMock(
        return_value=FakeResponse(
            200,
            {"response": {"hits": [{"result": {"url": "https://genius.com/x"}}]}},
        )
    )
    with patch("cogs.api.genius.get_session", return_value=fake_session), patch(
        "cogs.api.genius.get_text", return_value="<html><body>no lyrics here</body></html>"
    ):
        result = await api.fetch_lyrics("Some Song")

    assert result is None


@pytest.mark.asyncio
async def test_fetch_lyrics_returns_none_when_parsing_raises(api):
    # Regression test: format_lyrics()/BeautifulSoup parsing used to run
    # outside the try/except that wraps the network calls, so a parse-time
    # exception would propagate uncaught instead of degrading to None like
    # every other failure path in fetch_lyrics.
    fake_session = MagicMock()
    fake_session.get = MagicMock(
        return_value=FakeResponse(
            200,
            {"response": {"hits": [{"result": {"url": "https://genius.com/x"}}]}},
        )
    )
    with patch("cogs.api.genius.get_session", return_value=fake_session), patch(
        "cogs.api.genius.get_text", return_value=LYRICS_HTML
    ), patch.object(
        GeniusAPI, "format_lyrics", side_effect=RuntimeError("malformed markup")
    ):
        result = await api.fetch_lyrics("Some Song")

    assert result is None


@pytest.mark.asyncio
async def test_fetch_lyrics_returns_none_on_missing_result_key(api):
    # Malformed hit shape (missing "result"/"url") must be caught, not raise.
    fake_session = MagicMock()
    fake_session.get = MagicMock(
        return_value=FakeResponse(200, {"response": {"hits": [{"result": {}}]}})
    )
    with patch("cogs.api.genius.get_session", return_value=fake_session):
        result = await api.fetch_lyrics("Some Song")

    assert result is None


def test_format_lyrics_strips_scripts_and_adds_newlines_around_brackets(api):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(LYRICS_HTML, "html.parser")
    result = api.format_lyrics(soup)

    assert result is not None
    assert "\n[Verse 1]" in result
    assert "[Chorus]" in result
