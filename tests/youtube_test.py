import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def youtube_api(tmp_path, monkeypatch):
    monkeypatch.setenv("DZ_DOWNLOAD_DIR", str(tmp_path))
    import importlib
    import cogs.api.youtube as youtube_module

    importlib.reload(youtube_module)
    return youtube_module.YouTubeAPI({"max_duration": "1200"})


def make_ydl(extract_info_return):
    ydl = MagicMock()
    ydl.__enter__.return_value = ydl
    ydl.__exit__.return_value = False
    ydl.extract_info.return_value = extract_info_return
    return ydl


@patch("cogs.api.youtube.yt_dlp.YoutubeDL")
def test_is_video_playable_true_for_normal_video(mock_youtube_dl, youtube_api):
    mock_youtube_dl.return_value = make_ydl({"duration": 200})

    assert youtube_api.is_video_playable("https://youtu.be/abc123") is True


@patch("cogs.api.youtube.yt_dlp.YoutubeDL")
def test_is_video_playable_false_when_too_long(mock_youtube_dl, youtube_api):
    mock_youtube_dl.return_value = make_ydl({"duration": 5000})

    assert youtube_api.is_video_playable("https://youtu.be/abc123") is False


@patch("cogs.api.youtube.yt_dlp.YoutubeDL")
def test_is_video_playable_true_for_livestream_with_no_duration(
    mock_youtube_dl, youtube_api
):
    # Livestreams report duration=None; that must not be treated as "too long".
    mock_youtube_dl.return_value = make_ydl({"duration": None})

    assert youtube_api.is_video_playable("https://youtu.be/live123") is True


@patch("cogs.api.youtube.yt_dlp.YoutubeDL")
def test_is_video_playable_search_query_uses_first_entry(mock_youtube_dl, youtube_api):
    mock_ydl = make_ydl({"entries": [{"duration": 100}, {"duration": 9999}]})
    mock_youtube_dl.return_value = mock_ydl

    assert youtube_api.is_video_playable("some search text") is True
    called_url = mock_ydl.extract_info.call_args.args[0]
    assert called_url == "ytsearch:some search text"


@patch("cogs.api.youtube.yt_dlp.YoutubeDL")
def test_is_video_playable_search_with_no_results_is_not_playable(
    mock_youtube_dl, youtube_api
):
    mock_youtube_dl.return_value = make_ydl({"entries": []})

    assert youtube_api.is_video_playable("no results for this query") is False


@patch("cogs.api.youtube.yt_dlp.YoutubeDL")
def test_download_direct_url_returns_path_and_info(mock_youtube_dl, youtube_api):
    mock_youtube_dl.return_value = make_ydl({"title": "a song", "duration": 42})

    file_path, info = youtube_api.download("https://youtu.be/abc123")

    assert file_path.endswith(".mp3")
    assert info["title"] == "a song"


@patch("cogs.api.youtube.yt_dlp.YoutubeDL")
def test_download_search_query_uses_first_entry(mock_youtube_dl, youtube_api):
    mock_youtube_dl.return_value = make_ydl(
        {"entries": [{"title": "first result"}]}
    )

    _, info = youtube_api.download("some search text")

    assert info["title"] == "first result"


@patch("cogs.api.youtube.yt_dlp.YoutubeDL")
def test_download_search_with_no_results_raises_lookup_error(
    mock_youtube_dl, youtube_api
):
    mock_youtube_dl.return_value = make_ydl({"entries": []})

    with pytest.raises(LookupError):
        youtube_api.download("no results for this query")


@patch("cogs.api.youtube.yt_dlp.YoutubeDL")
def test_download_non_youtube_url_is_not_turned_into_a_search(
    mock_youtube_dl, youtube_api
):
    # A SoundCloud/Bandcamp/direct-audio URL is not "youtube.com"/"youtu.be"
    # but is still a real URL - it must be handed to yt-dlp as-is, not
    # search-ified into "ytsearch:<url>".
    mock_ydl = make_ydl({"title": "a song", "duration": 42})
    mock_youtube_dl.return_value = mock_ydl

    youtube_api.download("https://soundcloud.com/artist/track")

    called_url = mock_ydl.extract_info.call_args.args[0]
    assert called_url == "https://soundcloud.com/artist/track"


@patch("cogs.api.youtube.yt_dlp.YoutubeDL")
def test_download_resets_downloading_flag_on_exception(mock_youtube_dl, youtube_api):
    mock_ydl = make_ydl(None)
    mock_ydl.extract_info.side_effect = Exception("network error")
    mock_youtube_dl.return_value = mock_ydl

    with pytest.raises(Exception):
        youtube_api.download("https://youtu.be/abc123")

    assert youtube_api.downloading is False


@patch("cogs.api.youtube.yt_dlp.YoutubeDL")
def test_download_rejects_url_resolving_to_private_ip(mock_youtube_dl, youtube_api, monkeypatch):
    # Regression test (SSRF): a URL that resolves to an internal/private
    # address (e.g. cloud metadata, LAN services) must be rejected before
    # yt-dlp's generic extractor is allowed to fetch it, and the "downloading"
    # guard flag must still be reset.
    import cogs.api.youtube as youtube_module

    monkeypatch.setattr(
        youtube_module.socket,
        "getaddrinfo",
        lambda host, port: [(None, None, None, None, ("169.254.169.254", 0))],
    )
    mock_youtube_dl.return_value = make_ydl({"title": "a song"})

    with pytest.raises(ValueError):
        youtube_api.download("https://metadata.internal/latest/meta-data/")

    assert youtube_api.downloading is False
    mock_youtube_dl.return_value.extract_info.assert_not_called()


@patch("cogs.api.youtube.yt_dlp.YoutubeDL")
def test_is_video_playable_rejects_url_resolving_to_private_ip(
    mock_youtube_dl, youtube_api, monkeypatch
):
    import cogs.api.youtube as youtube_module

    monkeypatch.setattr(
        youtube_module.socket,
        "getaddrinfo",
        lambda host, port: [(None, None, None, None, ("127.0.0.1", 0))],
    )
    mock_youtube_dl.return_value = make_ydl({"duration": 200})

    with pytest.raises(ValueError):
        youtube_api.is_video_playable("https://localhost.example/secret")

    assert youtube_api.downloading is False
    mock_youtube_dl.return_value.extract_info.assert_not_called()


def test_download_rejects_url_with_no_hostname(youtube_api):
    with pytest.raises(ValueError):
        youtube_api.download("https:///no-host-here")


def test_download_rejects_url_that_fails_to_resolve(youtube_api, monkeypatch):
    import socket

    import cogs.api.youtube as youtube_module

    def raise_gaierror(host, port):
        raise socket.gaierror("Name or service not known")

    monkeypatch.setattr(youtube_module.socket, "getaddrinfo", raise_gaierror)

    with pytest.raises(ValueError):
        youtube_api.download("https://this-does-not-resolve.invalid/track")


@patch("cogs.api.youtube.yt_dlp.YoutubeDL")
def test_extract_playlist_songs_returns_titles(mock_youtube_dl, youtube_api):
    mock_youtube_dl.return_value = make_ydl(
        {
            "_type": "playlist",
            "entries": [
                {"title": "Song A"},
                {"title": "Song B"},
                None,
                {"title": ""},
            ],
        }
    )

    songs = youtube_api._extract_playlist_songs("https://youtube.com/playlist?list=x")

    assert songs == ["Song A", "Song B"]


@patch("cogs.api.youtube.yt_dlp.YoutubeDL")
def test_extract_playlist_songs_returns_empty_for_non_playlist(
    mock_youtube_dl, youtube_api
):
    mock_youtube_dl.return_value = make_ydl({"_type": "video", "entries": []})

    songs = youtube_api._extract_playlist_songs("https://youtube.com/watch?v=x")

    assert songs == []


@pytest.mark.asyncio
@patch("cogs.api.youtube.yt_dlp.YoutubeDL")
async def test_get_playlist_songs_runs_in_thread(mock_youtube_dl, youtube_api):
    mock_youtube_dl.return_value = make_ydl(
        {"_type": "playlist", "entries": [{"title": "Song A"}]}
    )

    songs = await youtube_api.get_playlist_songs(
        "https://youtube.com/playlist?list=x"
    )

    assert songs == ["Song A"]
