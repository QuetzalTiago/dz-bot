from unittest.mock import MagicMock, patch

import pytest

from cogs.utils import http


class FakeResponse:
    def __init__(self, status=200, json_data=None, text_data="", bytes_data=b""):
        self.status = status
        self._json = json_data
        self._text = text_data
        self._bytes = bytes_data

    def raise_for_status(self):
        if self.status >= 400:
            raise Exception(f"HTTP {self.status}")

    async def json(self):
        return self._json

    async def text(self):
        return self._text

    async def read(self):
        return self._bytes

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


@pytest.fixture(autouse=True)
async def reset_session():
    yield
    await http.close_session()


@pytest.mark.asyncio
async def test_get_session_returns_the_same_instance_on_repeated_calls():
    s1 = http.get_session()
    s2 = http.get_session()
    assert s1 is s2


@pytest.mark.asyncio
async def test_get_session_recreates_after_close_session():
    s1 = http.get_session()
    await http.close_session()
    s2 = http.get_session()
    assert s1 is not s2
    assert s1.closed
    assert not s2.closed


@pytest.mark.asyncio
async def test_get_session_recreates_when_session_was_closed_externally():
    s1 = http.get_session()
    await s1.close()
    s2 = http.get_session()
    assert s2 is not s1
    assert not s2.closed


@pytest.mark.asyncio
async def test_close_session_is_a_noop_when_no_session_exists():
    http._session = None
    await http.close_session()
    assert http._session is None


@pytest.mark.asyncio
async def test_close_session_is_a_noop_when_session_already_closed():
    http.get_session()
    await http.close_session()
    assert http._session is None
    # second call must not try to close an already-closed session again
    await http.close_session()


@pytest.mark.asyncio
async def test_get_json_returns_parsed_body():
    fake_session = MagicMock()
    fake_session.get = MagicMock(return_value=FakeResponse(200, json_data={"a": 1}))
    with patch("cogs.utils.http.get_session", return_value=fake_session):
        result = await http.get_json("http://example.com")
    assert result == {"a": 1}


@pytest.mark.asyncio
async def test_get_json_raises_for_error_status():
    fake_session = MagicMock()
    fake_session.get = MagicMock(return_value=FakeResponse(500))
    with patch("cogs.utils.http.get_session", return_value=fake_session):
        with pytest.raises(Exception, match="HTTP 500"):
            await http.get_json("http://example.com")


@pytest.mark.asyncio
async def test_get_bytes_returns_raw_body():
    fake_session = MagicMock()
    fake_session.get = MagicMock(return_value=FakeResponse(200, bytes_data=b"raw-bytes"))
    with patch("cogs.utils.http.get_session", return_value=fake_session):
        result = await http.get_bytes("http://example.com/file.bin")
    assert result == b"raw-bytes"


@pytest.mark.asyncio
async def test_get_bytes_raises_for_error_status():
    fake_session = MagicMock()
    fake_session.get = MagicMock(return_value=FakeResponse(404))
    with patch("cogs.utils.http.get_session", return_value=fake_session):
        with pytest.raises(Exception, match="HTTP 404"):
            await http.get_bytes("http://example.com/missing.bin")


@pytest.mark.asyncio
async def test_get_text_returns_body_text():
    fake_session = MagicMock()
    fake_session.get = MagicMock(return_value=FakeResponse(200, text_data="<html></html>"))
    with patch("cogs.utils.http.get_session", return_value=fake_session):
        result = await http.get_text("http://example.com/page")
    assert result == "<html></html>"


@pytest.mark.asyncio
async def test_get_text_raises_for_error_status():
    fake_session = MagicMock()
    fake_session.get = MagicMock(return_value=FakeResponse(503))
    with patch("cogs.utils.http.get_session", return_value=fake_session):
        with pytest.raises(Exception, match="HTTP 503"):
            await http.get_text("http://example.com/page")


@pytest.mark.asyncio
async def test_get_json_forwards_kwargs_to_session_get():
    fake_session = MagicMock()
    fake_session.get = MagicMock(return_value=FakeResponse(200, json_data={}))
    with patch("cogs.utils.http.get_session", return_value=fake_session):
        await http.get_json("http://example.com", params={"q": "x"}, headers={"H": "1"})
    _, kwargs = fake_session.get.call_args
    assert kwargs["params"] == {"q": "x"}
    assert kwargs["headers"] == {"H": "1"}
