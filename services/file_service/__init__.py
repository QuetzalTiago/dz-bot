import json
import os
import re
import uuid
import datetime
import yt_dlp
from youtube_search import YoutubeSearch
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

with open("config.json") as f:
    config = json.load(f)


class FileService:
    def __init__(self):
        self.spotify = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=config["secrets"]["spotifyClientId"],
                client_secret=config["secrets"]["spotifyClientSecret"],
            )
        )
        self.max_video_duration = 750

    async def download_from_youtube(self, song_name, message):
        file_name = f"{uuid.uuid4().int}"
        print(file_name)

        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "96",
                },
            ],
            "outtmpl": f"{file_name}",
            "noplaylist": True,
        }

        if "youtube.com" in song_name or "youtu.be" in song_name:
            pass
        else:
            results = json.loads(YoutubeSearch(song_name, max_results=5).to_json())
            url_suffix = results["videos"][0]["url_suffix"]
            song_name = f"https://www.youtube.com{url_suffix}"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(song_name, download=False)

            if info["duration"] > self.max_video_duration:
                duration_readable = str(datetime.timedelta(seconds=info["duration"]))
                max_duration_readable = str(
                    datetime.timedelta(seconds=self.max_video_duration)
                )
                await message.channel.send(
                    f"Video too long. Duration: **{duration_readable}**"
                )
                return

            info = ydl.extract_info(song_name, download=True)

        return f"{file_name}.mp3", info

    async def download_from_spotify(self, song_name, message):
        # TODO
        pass

    def delete_file(self, file_path):
        try:
            os.remove(file_path)
            print(f"File {file_path} deleted successfully")
        except Exception as e:
            print(f"Error deleting file {file_path}. Error: {e}")
