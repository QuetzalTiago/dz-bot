import json
import os
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
        self.max_duration = 1200  # in seconds, 20 minutes
        self.audio_quality = 96  # kb/s, max discord channel quality is
        self.audio_format = "mp3"
        self.downloading = False

    async def download_from_youtube(self, song_name, message):
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

        if "youtube.com" in song_name or "youtu.be" in song_name:
            pass
        else:
            results = json.loads(YoutubeSearch(song_name, max_results=5).to_json())
            url_suffix = results["videos"][0]["url_suffix"]
            song_name = f"https://www.youtube.com{url_suffix}"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(song_name, download=False)

            if info["duration"] > self.max_duration:
                duration_readable = str(datetime.timedelta(seconds=info["duration"]))
                max_duration_readable = str(
                    datetime.timedelta(seconds=self.max_duration)
                )
                await message.channel.send(
                    f"Video too long. Duration: **{duration_readable}**\nMax duration is **{max_duration_readable}**."
                )
                await message.clear_reactions()
                await message.add_reaction("❌")

                self.downloading = False
                return

            info = ydl.extract_info(song_name, download=True)

        self.downloading = False

        return f"{file_name}.{self.audio_format}", info

    async def get_youtube_playlist_songs(self, playlist_url):
        song_names = []

        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": self.audio_format,
                    "preferredquality": str(self.audio_quality),
                },
            ],
            "outtmpl": f"%(title)s_{uuid.uuid4().int}.%(ext)s",
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            playlist_info = ydl.extract_info(playlist_url, download=False)
            if not playlist_info.get("_type", "") == "playlist":
                print(f"This doesn't seem like a playlist URL.")
                return []

            for entry in playlist_info["entries"]:
                song_names.append(entry["title"])

        return song_names

    async def get_spotify_name(self, song_name):
        track_id = song_name.split("/")[-1].split("?")[0]
        track = self.spotify.track(track_id)

        artist = track["artists"][0]["name"]
        song_name = track["name"]

        return f"{artist} - {song_name}"

    async def get_spotify_playlist_songs(self, playlist_url):
        playlist_id = playlist_url.split("/")[-1].split("?")[0]
        results = self.spotify.playlist_tracks(playlist_id)
        songs = []
        for item in results["items"]:
            track = item["track"]
            artist = track["artists"][0]["name"]
            song_name = track["name"]
            songs.append(f"{artist} - {song_name}")

        return songs

    def delete_file(self, file_path):
        try:
            os.remove(file_path)
            print(f"File {file_path} deleted successfully")
        except Exception as e:
            print(f"Error deleting file {file_path}. Error: {e}")

    def is_downloading(self):
        return self.downloading
