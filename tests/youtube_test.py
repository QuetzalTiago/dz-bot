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
