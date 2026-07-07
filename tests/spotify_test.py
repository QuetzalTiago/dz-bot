import pytest
from unittest.mock import MagicMock, patch

from cogs.api.spotify import SpotifyAPI


@pytest.fixture
def api():
    with patch("cogs.api.spotify.SpotifyClientCredentials"), patch(
        "cogs.api.spotify.spotipy.Spotify"
    ):
        return SpotifyAPI({"secrets": {"spotifyClientId": "id", "spotifyClientSecret": "secret"}})


@pytest.mark.asyncio
async def test_get_track_name_strips_query_string(api):
    api.spotify.track = MagicMock(
        return_value={"artists": [{"name": "Daft Punk"}], "name": "One More Time"}
    )

    result = await api.get_track_name("https://open.spotify.com/track/abc123?si=xyz")

    api.spotify.track.assert_called_once_with("abc123")
    assert result == "Daft Punk - One More Time"


@pytest.mark.asyncio
async def test_get_track_name_uses_first_artist_only(api):
    api.spotify.track = MagicMock(
        return_value={
            "artists": [{"name": "First"}, {"name": "Second"}],
            "name": "Collab Song",
        }
    )

    result = await api.get_track_name("https://open.spotify.com/track/xyz")

    assert result == "First - Collab Song"


@pytest.mark.asyncio
async def test_get_track_name_falls_back_when_artists_empty(api):
    # Regression test: a local file embedded in a playlist/album can report
    # an empty "artists" list - a direct [0] index would raise IndexError
    # and (for playlist/album imports) abort the entire batch on one track.
    api.spotify.track = MagicMock(
        return_value={"artists": [], "name": "Untitled Local File"}
    )

    result = await api.get_track_name("https://open.spotify.com/track/abc123")

    assert result == "Unknown Artist - Untitled Local File"


@pytest.mark.asyncio
async def test_get_playlist_songs_follows_pagination(api):
    page1 = {
        "items": [{"track": {"artists": [{"name": "A"}], "name": "Song A"}}],
        "next": "page2",
    }
    page2 = {
        "items": [{"track": {"artists": [{"name": "B"}], "name": "Song B"}}],
        "next": None,
    }
    api.spotify.playlist_tracks = MagicMock(return_value=page1)
    api.spotify.next = MagicMock(return_value=page2)

    songs = await api.get_playlist_songs("https://open.spotify.com/playlist/plid?si=1")

    api.spotify.playlist_tracks.assert_called_once_with("plid")
    api.spotify.next.assert_called_once_with(page1)
    assert songs == ["A - Song A", "B - Song B"]


@pytest.mark.asyncio
async def test_get_playlist_songs_skips_removed_tracks(api):
    # Spotify represents a removed/unavailable playlist track as {"track": None}.
    page = {
        "items": [
            {"track": None},
            {"track": {"artists": [{"name": "A"}], "name": "Song A"}},
        ],
        "next": None,
    }
    api.spotify.playlist_tracks = MagicMock(return_value=page)

    songs = await api.get_playlist_songs("https://open.spotify.com/playlist/plid")

    assert songs == ["A - Song A"]


@pytest.mark.asyncio
async def test_get_playlist_songs_falls_back_when_track_artists_empty(api):
    page = {
        "items": [{"track": {"artists": [], "name": "Local Track"}}],
        "next": None,
    }
    api.spotify.playlist_tracks = MagicMock(return_value=page)

    songs = await api.get_playlist_songs("https://open.spotify.com/playlist/plid")

    assert songs == ["Unknown Artist - Local Track"]


@pytest.mark.asyncio
async def test_get_album_songs_falls_back_when_artists_empty(api):
    page = {"items": [{"artists": [], "name": "Local Track"}], "next": None}
    api.spotify.album_tracks = MagicMock(return_value=page)

    songs = await api.get_album_songs("https://open.spotify.com/album/alid")

    assert songs == ["Unknown Artist - Local Track"]


def test_init_does_not_raise_when_secrets_missing():
    # Regression test: Spotify/Genius integration is optional. Downloader
    # unconditionally constructs SpotifyAPI for every guild, so a direct
    # `config["secrets"]["spotifyClientId"]` index (raising KeyError when the
    # deployment skips the optional Spotify integration) used to break every
    # music command, not just Spotify ones - matching every sibling API-key
    # cog (football/formula1/ufc/steam/weather), this must use `.get(...)`.
    with patch("cogs.api.spotify.SpotifyClientCredentials") as mock_creds, patch(
        "cogs.api.spotify.spotipy.Spotify"
    ):
        SpotifyAPI({"secrets": {}})

    mock_creds.assert_called_once_with(client_id=None, client_secret=None)


@pytest.mark.asyncio
async def test_get_album_songs_follows_pagination(api):
    page1 = {"items": [{"artists": [{"name": "A"}], "name": "Track 1"}], "next": "page2"}
    page2 = {"items": [{"artists": [{"name": "A"}], "name": "Track 2"}], "next": None}
    api.spotify.album_tracks = MagicMock(return_value=page1)
    api.spotify.next = MagicMock(return_value=page2)

    songs = await api.get_album_songs("https://open.spotify.com/album/alid?si=1")

    api.spotify.album_tracks.assert_called_once_with("alid")
    assert songs == ["A - Track 1", "A - Track 2"]
