import html
import os
import re
from bs4 import BeautifulSoup
import discord
import time

import requests

from services.file_service import FileService
from services.job_service.job import Job
from services.job_service.job_types import JobType
from services.music_service.song import Song


class MusicService:
    def __init__(self, client):
        self.client = client
        self.queue = []
        self.dl_queue = []
        self.current_song = None
        self.voice_client = None
        self.loop = False
        self.file_service = FileService()
        self.last_song = None
        self.disconnect_timer = None

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
        song.message_to_delete = []

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

        if not "spotify.com" in query and not "list=" in query:
            lyrics = await self.fetch_lyrics(query)

        song = Song(song_path, song_info, message, lyrics)

        if not self.is_playing():
            await self.join_voice_channel(message)

        self.queue.append(song)
        self.disconnect_timer = None  # Reset timer when a new song is added

    async def play_song(self, song: Song, silent=False):
        if self.is_playing() or self.file_service.is_downloading():
            return

        for file_name in os.listdir("."):
            if (
                file_name.endswith(".mp3")
                and file_name != song.path
                and all(file_name != s.path for s in self.queue)
            ):
                self.file_service.delete_file(file_name)

        source = discord.FFmpegPCMAudio(song.path)
        self.voice_client.play(source)
        self.current_song = song

        if not silent:
            embed = song.to_embed()
            msg = await song.message.channel.send(embed=embed)
            song.messages_to_delete.append(msg)

            if song.lyrics:
                lyrics_file_name = "lyrics.txt"
                with open(lyrics_file_name, "w", encoding="utf-8") as file:
                    file.write(song.lyrics)

                with open(lyrics_file_name, "rb") as file:
                    lyrics_msg = await song.message.channel.send(
                        file=discord.File(file, lyrics_file_name)
                    )
                    song.messages_to_delete.append(lyrics_msg)

                # Remove the temporary file after sending
                os.remove(lyrics_file_name)

        self.last_song = song

    def is_playing(self):
        return self.voice_client and self.voice_client.is_playing()

    async def skip_song(self):
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()

    def get_queue_info(self):
        if not self.queue:
            return "The queue is empty."

        queue_info = "Current Queue:\n"
        for index, song in enumerate(self.queue, 1):
            if index < 20:
                queue_info += f"{index}. **{song.title}** \n"
            if index == 19:
                queue_info += f"rest of the queue..."

        return queue_info

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
