import json
import os
import uuid
import datetime
import yt_dlp
from youtube_search import YoutubeSearch
from discord.ext import commands


class Files(commands.Cog):
    def __init__(self, bot):
        self.audio_quality = 96  # kb/s, max discord channel quality is
        self.audio_format = "mp3"
        self.downloading = False
        self.bot = bot

    async def download_from_youtube(self, song_url, message):
        file_name = f"{uuid.uuid4().int}"

        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": self.audio_format,
                    "preferredquality": self.audio_quality,
                },
            ],
            "outtmpl": f"{file_name}",
            "noplaylist": True,
        }

        self.downloading = True

        if "youtube.com" not in song_url or "youtu.be" not in song_url:
            results = json.loads(YoutubeSearch(song_url, max_results=5).to_json())
            url_suffix = results["videos"][0]["url_suffix"]
            song_url = f"https://www.youtube.com{url_suffix}"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(song_url, download=False)

            if info["duration"] > self.bot.max_duration:
                duration_readable = str(datetime.timedelta(seconds=info["duration"]))
                max_duration_readable = str(
                    datetime.timedelta(seconds=self.bot.max_duration)
                )
                song_title = info["title"]

                await message.channel.send(
                    f"**{song_title}** is too long. Duration: **{duration_readable}**.\nMax duration allowed is **{max_duration_readable}**."
                )
                await message.clear_reactions()
                await message.add_reaction("❌")

                self.downloading = False
                return

            info = ydl.extract_info(song_url, download=True)

        self.downloading = False

        return f"{file_name}.{self.audio_format}", info

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