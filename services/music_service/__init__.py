import html
import json
import os
import re
import uuid
from bs4 import BeautifulSoup
import discord
import time

import requests
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from services.file_service import FileService
from services.job_service.job import Job
from services.job_service.job_types import JobType
from services.music_service.song import Song

with open("config.json") as f:
    config = json.load(f)


class MusicService:
    def __init__(self, client):
        self.client = client
        self.queue = []
        self.dl_queue = []
        self.current_song = None
        self.voice_client = None
        self.loop = False
        self.file_service = FileService(client)
        self.last_song = None
        self.disconnect_timer = None
        self.spotify = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=config["secrets"]["spotifyClientId"],
                client_secret=config["secrets"]["spotifyClientSecret"],
            )
        )

    async def initialize(self):
        music_job = Job(lambda: self.background_task(), 1, JobType.MUSIC)
        self.client.job_service.add_job(music_job)
        print("Music service initialized.")

    async def background_task(self):
        if not self.is_playing() and not self.file_service.is_downloading():
            if self.last_song and self.last_song.message:
                await self.delete_song_log(self.last_song)
                self.last_song = None
            if self.loop and self.current_song:
                await self.play_song(self.current_song, True)
            elif self.queue:
                next_song = self.queue.pop(0)
                await self.play_song(next_song)
            elif (
                self.voice_client
                and self.voice_client.is_connected()
                and not self.queue
            ):
                if self.disconnect_timer is None:
                    self.disconnect_timer = time.time()
                elif time.time() - self.disconnect_timer >= 300:
                    await self.stop()
                    self.disconnect_timer = None
            else:
                self.disconnect_timer = None

        if self.voice_client and self.voice_client.channel:
            members_in_channel = len(self.voice_client.channel.members)
            if members_in_channel == 1:
                await self.stop()

    async def delete_song_log(self, song):
        for message in song.messages_to_delete:
            try:
                await message.delete()
            except:
                pass
        song.messages_to_delete = []

    async def join_voice_channel(self, message):
        voice_channel = message.author.voice.channel
        try:
            self.voice_client = await voice_channel.connect()
        except:
            pass

        return self.voice_client

    async def add_to_queue(self, song_path, song_info, message):
        if message.content.startswith("play"):
            query = message.content[5:].strip()
        else:
            query = message.content[2:].strip()

        if "spotify.com" and "track" in query:
            query = await self.get_spotify_name(query)
            query = re.sub(r"\([^)]*\)", "", query)

        lyrics = await self.fetch_lyrics(query)

        song = Song(song_path, song_info, message, lyrics)

        if not self.is_playing():
            await self.join_voice_channel(message)

        self.queue.append(song)
        self.disconnect_timer = None  # Reset timer when a new song is added

    async def check_play_state(self):
        return self.is_playing() or self.file_service.is_downloading()

    def cleanup_files(self, current_song, queue):
        for file_name in os.listdir("."):
            if (
                file_name.endswith(".mp3")
                and file_name != current_song.path
                and all(file_name != s.path for s in queue)
            ):
                self.file_service.delete_file(file_name)

    def play_audio(self, song_path):
        source = discord.FFmpegPCMAudio(song_path)
        self.voice_client.play(source)

    async def send_song_embed(self, song: Song):
        embed = song.to_embed()
        msg = await song.message.channel.send(embed=embed)
        return msg

    async def handle_lyrics(self, song: Song):
        if song.lyrics:
            lyrics_file_name = "lyrics.txt"
            with open(lyrics_file_name, "w", encoding="utf-8") as file:
                file.write(song.lyrics)
            lyrics_msg = await self.send_lyrics_file(
                song.message.channel, lyrics_file_name
            )
            os.remove(lyrics_file_name)
            return lyrics_msg

    async def send_lyrics_file(self, channel, file_name):
        with open(file_name, "rb") as file:
            return await channel.send(file=discord.File(file, file_name))

    async def play_song(self, song: Song):
        if await self.check_play_state():
            return

        self.cleanup_files(song, self.queue)
        self.play_audio(song.path)
        self.current_song = song

        embed_msg = await self.send_song_embed(song)
        song.messages_to_delete.append(embed_msg)
        song.messages_to_delete.append(song.message)

        if song.lyrics:
            await embed_msg.add_reaction("📖")

            send_lyrics_job = Job(
                lambda: self.check_reaction(embed_msg, song),
                1,
                JobType.SEND_LYRICS,
                self.client.max_duration,
            )

            self.client.job_service.add_job(send_lyrics_job)
        self.last_song = song

    def is_playing(self):
        return self.voice_client and self.voice_client.is_playing()

    async def skip_song(self):
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()

    def get_queue_info_embed(self):
        embed = discord.Embed(color=0x1ABC9C)
        embed.title = "Current Queue"

        if not self.queue:
            embed.description = "The queue is empty."
            return embed

        description = ""
        for index, song in enumerate(self.queue, 1):
            if index < 20:
                description += f"{index}. **{song.title}**\n"
            elif index == 20:
                description += f"and more..."
                break

        embed.description = description
        return embed

    async def stop(self, message=None):
        if self.last_song and self.last_song.messages_to_delete:
            await self.delete_song_log(self.last_song)
            self.last_song = None

        if self.voice_client and self.voice_client.is_connected():
            if self.voice_client.is_playing():
                self.voice_client.stop()

            if self.voice_client:
                await self.voice_client.disconnect()
        else:
            if message:
                await message.channel.send("DJ Khaled is not playing anything!")

        self.queue = []
        self.current_song = None
        self.last_song = None
        self.disconnect_timer = None  # Reset timer when stopped

    async def clear(self, message):
        self.dl_queue = []
        self.queue = []
        await message.channel.send("Queue has been cleared!")

    async def toggle_loop(self):
        self.loop = not self.loop
        return "on" if self.loop else "off"

    async def process_dl_queue(self, message):
        if self.dl_queue.__len__() == 0:
            self.client.job_service.remove_job(JobType.PROCESS_DB_QUEUE)
            return

        next_song_name = self.dl_queue.pop(0)
        (
            next_song_path,
            next_song_info,
        ) = await self.file_service.download_from_youtube(next_song_name, message)

        await self.add_to_queue(next_song_path, next_song_info, message)

    async def fetch_lyrics(self, song_name):
        if "/playlist/" in song_name or "list=" in song_name:
            return None

        base_url = "https://api.genius.com"
        headers = {
            "Authorization": "Bearer "
            + "bnYy6f7T2v_YPfhmT9nvkXHZd5SIsSQ8gDKRQrMmz4ipZ6C_aM8dpTMPb3GDkm4p"
        }

        # Search for the song
        search_url = base_url + f"/search?q={song_name}"
        response = requests.get(search_url, headers=headers)
        json = response.json()

        # Check if there are any hits
        if not json["response"]["hits"]:
            return None

        # Extract the first song's page URL
        song_url = json["response"]["hits"][0]["result"]["url"]

        # Scrape the lyrics from the song's page
        page = requests.get(song_url)
        html_content = BeautifulSoup(page.text, "html.parser")

        lyrics = self.format_lyrics(html_content)

        if "\n" not in lyrics[:35]:
            return None

        return lyrics

    def format_lyrics(self, html_content):
        # Remove scripts from HTML content
        [h.extract() for h in html_content("script")]

        # Extracting lyrics from the divs
        lyrics = ""
        lyrics_divs = html_content.find_all("div", {"data-lyrics-container": "true"})
        for div in lyrics_divs:
            lyrics += div.get_text(separator="\n") + "\n\n"

        # Convert HTML entities to normal text
        lyrics = html.unescape(lyrics)

        # Remove new lines after '(' and '&'
        lyrics = re.sub(r"([&\(])\n", r"\1", lyrics)

        # Remove new lines before ')'
        lyrics = re.sub(r"\n(\))", r"\1", lyrics)

        # Add a new line after ']'
        lyrics = re.sub(r"(\])", r"\1\n", lyrics)

        # Add a new line before '['
        lyrics = re.sub(r"(\[)", r"\n\1", lyrics)

        return lyrics

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

    async def get_spotify_album_songs(self, album_url):
        album_id = album_url.split("/")[-1].split("?")[0]
        results = self.spotify.album_tracks(album_id)
        songs = []

        for item in results["items"]:
            artist = item["artists"][0]["name"]
            song_name = item["name"]
            songs.append(f"{artist} - {song_name}")

        return songs

    async def check_reaction(self, message, song):
        # Check reactions
        msg = await message.channel.fetch_message(message.id)
        if msg:
            for reaction in msg.reactions:
                if str(reaction.emoji) == "📖":
                    users = [user async for user in reaction.users()]
                    if any(user != self.client.user for user in users):
                        lyrics_msg = await self.handle_lyrics(song)
                        if lyrics_msg:
                            song.messages_to_delete.append(lyrics_msg)
                        self.client.job_service.remove_job(JobType.SEND_LYRICS)
                        break
