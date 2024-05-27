import asyncio
from discord.ext import commands
import os
import uuid
import datetime
import yt_dlp
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
                }
            ],
            "outtmpl": f"{file_name}",
            "noplaylist": True,
            "no_warnings": True,
        }

        self.downloading = True

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            is_query = "youtube.com" not in song_url and "youtu.be" not in song_url
            if is_query:
                song_url = f"ytsearch:{song_url}"

            info = ydl.extract_info(song_url, download=False)
            if is_query:
                info = info["entries"][0]

            if info["duration"] > self.bot.max_duration:
                duration_readable = str(datetime.timedelta(seconds=info["duration"]))
                max_duration_readable = str(
                    datetime.timedelta(seconds=self.bot.max_duration)
                )
                song_title = info["title"]

                await message.clear_reactions()
                await message.add_reaction("❌")
                sent_message = await message.channel.send(
                    f"**{song_title}** is too long. Duration: **{duration_readable}**.\nMax duration allowed is **{max_duration_readable}**."
                )
                self.bot.loop.create_task(self.delete_log(message, sent_message))

                return None, None

            info = ydl.extract_info(song_url, download=True)

            if is_query:
                info = info["entries"][0]

            file_path = f"{file_name}.{self.audio_format}"

            self.downloading = False

            return file_path, info

    async def delete_log(self, message, sent_message, delay=30):
        await asyncio.sleep(delay)
        try:
            await sent_message.delete()
            await message.delete()
        except Exception as e:
            print(f"Failed to delete message: {e}")  # Log the exception if any

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
