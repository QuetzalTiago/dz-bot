from unittest.mock import MagicMock, patch

from cogs.api.youtube import YouTubeAPI, _is_youtube_url


def make_ydl_mock(extract_info_return):
    ydl_instance = MagicMock()
    ydl_instance.extract_info.return_value = extract_info_return
    ydl_cm = MagicMock()
    ydl_cm.__enter__.return_value = ydl_instance
    ydl_cm.__exit__.return_value = False
    return ydl_cm, ydl_instance


def test_is_youtube_url_accepts_real_youtube_hosts():
    assert _is_youtube_url("https://www.youtube.com/watch?v=abc123")
    assert _is_youtube_url("https://youtu.be/abc123")


def test_is_youtube_url_rejects_spoofed_url_containing_substring():
    # A crafted URL that merely *contains* the substring "youtube.com" must
    # not be treated as a real YouTube URL (SSRF guard regression test).
    assert not _is_youtube_url("http://internal-host.example/?x=youtube.com")
    assert not _is_youtube_url("http://169.254.169.254/latest/meta-data/youtu.be")


def test_is_youtube_url_rejects_plain_search_text():
    assert not _is_youtube_url("some song title")


def test_is_video_playable_treats_spoofed_url_as_search_query():
    api = YouTubeAPI({})
    ydl_cm, ydl_instance = make_ydl_mock(
        {"entries": [{"duration": 100}]}
    )

    with patch("cogs.api.youtube.yt_dlp.YoutubeDL", return_value=ydl_cm):
        result = api.is_video_playable("http://evil.example/?x=youtube.com")

    assert result is True
    called_url = ydl_instance.extract_info.call_args[0][0]
    assert called_url.startswith("ytsearch:")


def test_is_video_playable_uses_direct_url_for_real_youtube_link():
    api = YouTubeAPI({})
    ydl_cm, ydl_instance = make_ydl_mock({"duration": 100})

    with patch("cogs.api.youtube.yt_dlp.YoutubeDL", return_value=ydl_cm):
        result = api.is_video_playable("https://www.youtube.com/watch?v=abc123")

    assert result is True
    called_url = ydl_instance.extract_info.call_args[0][0]
    assert called_url == "https://www.youtube.com/watch?v=abc123"


def test_is_video_playable_rejects_video_over_max_duration():
    api = YouTubeAPI({"max_duration": "60"})
    ydl_cm, _ = make_ydl_mock({"duration": 120})

    with patch("cogs.api.youtube.yt_dlp.YoutubeDL", return_value=ydl_cm):
        result = api.is_video_playable("https://youtu.be/abc123")

    assert result is False


def test_is_video_playable_allows_none_duration_livestream():
    # Livestreams often report duration=None; that must not crash the
    # comparison and must not be rejected outright.
    api = YouTubeAPI({"max_duration": "60"})
    ydl_cm, _ = make_ydl_mock({"duration": None})

    with patch("cogs.api.youtube.yt_dlp.YoutubeDL", return_value=ydl_cm):
        result = api.is_video_playable("https://youtu.be/abc123")

    assert result is True
