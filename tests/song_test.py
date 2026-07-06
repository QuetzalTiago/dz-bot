import datetime
from unittest.mock import MagicMock

from cogs.models.song import Song


def make_song(info=None, message=None):
    info = info or {"title": "Test Song", "original_url": "https://youtu.be/abc"}
    if message is None:
        message = MagicMock()
        message.author.id = 123
    return Song("path", info, message)


def test_title_and_url_read_from_info():
    song = make_song(
        info={"title": "My Title", "original_url": "https://youtu.be/xyz"}
    )
    assert song.title == "My Title"
    assert song.url == "https://youtu.be/xyz"


def test_duration_seconds_defaults_to_zero_when_missing_or_none():
    assert make_song(info={"title": "t", "original_url": "u"}).duration_seconds == 0
    assert (
        make_song(
            info={"title": "t", "original_url": "u", "duration": None}
        ).duration_seconds
        == 0
    )


def test_duration_formats_minutes_and_seconds():
    song = make_song(
        info={"title": "t", "original_url": "u", "duration": 125}
    )
    assert song.duration == "2:05"


def test_progress_formats_current_seconds():
    song = make_song()
    song.current_seconds = 65
    assert song.progress == "1:05"


def test_views_formats_with_commas_and_defaults_to_zero():
    assert make_song().views == "0"
    song = make_song(
        info={"title": "t", "original_url": "u", "view_count": 1234567}
    )
    assert song.views == "1,234,567"


def test_thumbnail_url_defaults_to_none():
    assert make_song().thumbnail_url is None
    song = make_song(
        info={"title": "t", "original_url": "u", "thumbnail": "http://thumb"}
    )
    assert song.thumbnail_url == "http://thumb"


def test_uploader_defaults_to_na():
    assert make_song().uploader == "N/A"
    song = make_song(info={"title": "t", "original_url": "u", "uploader": "Someone"})
    assert song.uploader == "Someone"


def test_like_count_formats_with_commas_and_defaults_to_zero():
    assert make_song().like_count == "0"
    song = make_song(info={"title": "t", "original_url": "u", "like_count": 4200})
    assert song.like_count == "4,200"


def test_comment_count_defaults_to_zero_and_handles_none():
    assert make_song().comment_count == "0"
    song = make_song(
        info={"title": "t", "original_url": "u", "comment_count": None}
    )
    assert song.comment_count == "N/A"
    song = make_song(info={"title": "t", "original_url": "u", "comment_count": 12})
    assert song.comment_count == "12"


def test_upload_date_parses_yyyymmdd_and_defaults_to_none():
    assert make_song().upload_date is None
    song = make_song(
        info={"title": "t", "original_url": "u", "upload_date": "20200115"}
    )
    assert song.upload_date == datetime.date(2020, 1, 15)


def test_time_since_upload_na_when_no_upload_date():
    assert make_song().time_since_upload == "N/A"


def test_time_since_upload_today():
    today = datetime.date.today().strftime("%Y%m%d")
    song = make_song(info={"title": "t", "original_url": "u", "upload_date": today})
    assert song.time_since_upload == "today"


def test_time_since_upload_days_ago():
    five_days_ago = (datetime.date.today() - datetime.timedelta(days=5)).strftime(
        "%Y%m%d"
    )
    song = make_song(
        info={"title": "t", "original_url": "u", "upload_date": five_days_ago}
    )
    assert song.time_since_upload == "5 days ago"


def test_time_since_upload_one_day_ago_singular():
    one_day_ago = (datetime.date.today() - datetime.timedelta(days=1)).strftime(
        "%Y%m%d"
    )
    song = make_song(
        info={"title": "t", "original_url": "u", "upload_date": one_day_ago}
    )
    assert song.time_since_upload == "1 day ago"


def test_time_since_upload_months_ago():
    two_months_ago = (datetime.date.today() - datetime.timedelta(days=65)).strftime(
        "%Y%m%d"
    )
    song = make_song(
        info={"title": "t", "original_url": "u", "upload_date": two_months_ago}
    )
    assert song.time_since_upload == "2 months ago"


def test_time_since_upload_years_ago():
    two_years_ago = (datetime.date.today() - datetime.timedelta(days=800)).strftime(
        "%Y%m%d"
    )
    song = make_song(
        info={"title": "t", "original_url": "u", "upload_date": two_years_ago}
    )
    assert song.time_since_upload == "2 years ago"


def test_lyrics_defaults_to_none_and_reflects_constructor_arg():
    song = make_song()
    assert song.lyrics is None
    song._lyrics = "la la la"
    assert song.lyrics == "la la la"


def test_get_progress_bar_without_duration_shows_progress_only():
    song = make_song()
    song.current_seconds = 30
    bar = song.get_progress_bar()
    assert bar == "**0:30**          \n"


def test_get_progress_bar_clamps_current_seconds_to_duration():
    song = make_song(info={"title": "t", "original_url": "u", "duration": 100})
    song.current_seconds = 500
    bar = song.get_progress_bar()
    assert song.current_seconds == 100
    assert "1:40/1:40" in bar


def test_get_progress_bar_fills_proportionally():
    song = make_song(info={"title": "t", "original_url": "u", "duration": 100})
    song.current_seconds = 50
    bar = song.get_progress_bar(bar_length=10)
    assert bar.startswith("█████▒▒▒▒▒")


def test_to_embed_shows_next_song_when_queue_present():
    message = MagicMock()
    message.author.id = 999
    song = make_song(
        info={
            "title": "Now Playing",
            "original_url": "u",
            "thumbnail": "http://thumb",
        },
        message=message,
    )
    next_song = make_song(info={"title": "Next Up", "original_url": "u2"})
    embed = song.to_embed(queue=[next_song])
    field_names = [f.name for f in embed.fields]
    field_values = [f.value for f in embed.fields]
    assert "Next:" in field_names
    assert "**Next Up**" in field_values
    assert embed.thumbnail.url == "http://thumb"
    assert "<@999>" in embed.fields[0].value


def test_to_embed_loop_takes_priority_over_shuffle_and_queue():
    song = make_song()
    next_song = make_song(info={"title": "Next Up", "original_url": "u2"})
    embed = song.to_embed(queue=[next_song], shuffle=True, loop=True)
    field_values = [f.value for f in embed.fields]
    assert any("Loop* is **ON**" in v for v in field_values)
    assert not any("Shuffle" in v for v in field_values)
    assert not any("Next Up" in v for v in field_values)


def test_to_embed_shuffle_takes_priority_over_queue():
    song = make_song()
    next_song = make_song(info={"title": "Next Up", "original_url": "u2"})
    embed = song.to_embed(queue=[next_song], shuffle=True)
    field_values = [f.value for f in embed.fields]
    assert any("Shuffle* is **ON**" in v for v in field_values)
    assert not any("Next Up" in v for v in field_values)


def test_to_embed_sets_lyrics_footer_when_lyrics_present():
    song = make_song()
    song._lyrics = "some lyrics"
    embed = song.to_embed(queue=[])
    assert embed.footer.text == "Lyrics are available! (beta)"


def test_to_embed_no_footer_without_lyrics():
    song = make_song()
    embed = song.to_embed(queue=[])
    assert embed.footer.text is None
