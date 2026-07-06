import asyncio
import os
import uuid
from urllib.parse import urlparse

import yt_dlp

# Downloaded audio is kept in a dedicated directory instead of the repo working
# directory, so cleanup is scoped and the source tree stays clean.
DOWNLOAD_DIR = os.environ.get("DZ_DOWNLOAD_DIR", "downloads")

# Hosts allowed to be treated as a direct video URL rather than a search
# query. A substring check (e.g. "youtube.com" in video_url) would let a
# crafted URL like "http://internal-host/?x=youtube.com" slip past as a
# "real" URL and get handed straight to yt-dlp's generic extractor, an SSRF
# vector -- so the actual hostname is matched instead.
_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}


def _is_youtube_url(video_url):
    try:
        host = urlparse(video_url).hostname
    except ValueError:
        return False
    return host is not None and host.lower() in _YOUTUBE_HOSTS


class YouTubeAPI:
    def __init__(self, config):
        self.audio_format = config.get("audio_format", "mp3")
        self.audio_quality = config.get("audio_quality", "192")
        self.downloading = False
        self.max_duration = int(
            config.get("max_duration", "1200")
        )  # in seconds, 20 minutes
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    def download(self, video_url):
        file_name = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4().int}")

        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": self.audio_format,
                    "preferredquality": self.audio_quality,
                }
            ],
            "outtmpl": f"{file_name}.%(ext)s",
            "noplaylist": True,
            "no_warnings": True,
        }

        self.downloading = True

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            is_query = not _is_youtube_url(video_url)
            if is_query:
                video_url = f"ytsearch:{video_url}"

            info = ydl.extract_info(video_url, download=True)

            if is_query:
                info = info["entries"][0]

            file_path = f"{file_name}.{self.audio_format}"

            self.downloading = False

            return file_path, info

    def is_video_playable(self, video_url):
        file_name = f"{uuid.uuid4().int}"

        self.downloading = True

        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": self.audio_format,
                    "preferredquality": self.audio_quality,
                }
            ],
            "outtmpl": f"{file_name}.%(ext)s",
            "noplaylist": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            is_query = not _is_youtube_url(video_url)
            if is_query:
                video_url = f"ytsearch:{video_url}"

            info = ydl.extract_info(video_url, download=False)

            self.downloading = False

            if is_query:
                info = info["entries"][0]

            duration = info.get("duration")
            if duration is not None and duration > self.max_duration:
                return False

            return True

    async def get_playlist_songs(self, playlist_url):
        # yt-dlp extraction is blocking network I/O; run it in a worker thread.
        return await asyncio.to_thread(self._extract_playlist_songs, playlist_url)

    def _extract_playlist_songs(self, playlist_url):
        song_names = []
        ydl_opts = {
            "extract_flat": True,
            "skip_download": True,
            "noplaylist": False,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            playlist_info = ydl.extract_info(playlist_url, download=False)
            if playlist_info.get("_type", "") != "playlist":
                return []
            for entry in playlist_info.get("entries", []):
                if entry and entry.get("title"):
                    song_names.append(entry["title"])
        return song_names
