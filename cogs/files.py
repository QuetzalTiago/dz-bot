import asyncio
from discord.ext import commands
import os
import uuid
import yt_dlp


class Files(commands.Cog):
    def __init__(self, bot):
        self.audio_quality = 96  # kb/s, max discord channel quality is
        self.audio_format = "opus"
        self.downloading = False
        self.bot = bot

    def download_from_youtube(self, video_url):
        file_name = f"{uuid.uuid4().int}"

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

            file_path = f"{file_name}.opus"

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

            if info["duration"] > self.bot.max_duration:
                return False

            return True

    def delete_file(self, file_path):
        try:
            os.remove(file_path)
            print(f"File {file_path} deleted successfully")
        except Exception as e:
            print(f"Error deleting file {file_path}. Error: {e}")

    def is_downloading(self):
        return self.downloading


async def setup(bot):
    await bot.add_cog(Files(bot))
