import asyncio
import os
import uuid

import yt_dlp

# Downloaded audio is kept in a dedicated directory instead of the repo working
# directory, so cleanup is scoped and the source tree stays clean.
DOWNLOAD_DIR = os.environ.get("DZ_DOWNLOAD_DIR", "downloads")


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
            is_query = "youtube.com" not in video_url and "youtu.be" not in video_url
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
            is_query = "youtube.com" not in video_url and "youtu.be" not in video_url
            if is_query:
                video_url = f"ytsearch:{video_url}"

            info = ydl.extract_info(video_url, download=False)

            self.downloading = False

            if is_query:
                info = info["entries"][0]

            if info["duration"] > self.max_duration:
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
