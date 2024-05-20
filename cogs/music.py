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
from discord.ext import commands, tasks
from spotipy.oauth2 import SpotifyClientCredentials
from .models.song import Song


class Music(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.queue = []
        self.dl_queue = []
        self.current_song = None
        self.voice_client = None
        self.loop = False
        self.last_song = None
        self.disconnect_timer = None
        self.files = self.bot.get_cog("Files")
        self.spotify = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=config["secrets"]["spotifyClientId"],
                client_secret=config["secrets"]["spotifyClientSecret"],
            )
        )

    @tasks.loop(seconds=1)
    async def background_task(self):
        if not self.is_playing() and not self.files.is_downloading():
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

    @background_task.before_loop
    async def before_background_task(self):
        await self.bot.wait_until_ready()

    async def handle_spotify_url(self, url, message):
        song_names = []

        if "/playlist/" in url:
            song_names = await self.get_spotify_playlist_songs(url)
        elif "/album/" in url:
            song_names = await self.get_spotify_album_songs(url)
        else:
            spotify_name = await self.get_spotify_name(url)
            song_names.append(spotify_name)

        songs = map((lambda song_name: (song_name, message)), song_names)

        if song_names:
            await self.enqueue_songs(songs)

        await message.clear_reactions()
        await message.add_reaction("✅")

    @commands.hybrid_command(aliases=["p"])
    async def play(self, ctx, song_url):
        """Plays a file from the local filesystem"""
        if ctx.message.author.voice is None:
            await ctx.send("You are not connected to a voice channel!")
            await ctx.message.clear_reactions()
            await ctx.message.add_reaction("❌")
            return

        if not song_url:
            await ctx.send(
                "Missing URL use command like: play https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            )
            return

        await ctx.message.add_reaction("⌛")

        if not self.background_task.is_running():
            self.background_task.start()

        if "spotify.com" in song_url:
            await self.handle_spotify_url(song_url, ctx.message)
            return

        elif "list=" in song_url:  # YouTube playlist
            await ctx.message.clear_reactions()
            await ctx.message.add_reaction("❌")
            await ctx.send(
                "Youtube playlists not yet supported. Try a spotify link instead."
            )
            return

        else:
            await self.enqueue_songs([(song_url, ctx.message)])

        await ctx.message.clear_reactions()
        await ctx.message.add_reaction("✅")

    @commands.hybrid_command()
    async def loop(self, ctx):
        """Toggle loop for current song"""
        loop_state = await self.toggle_loop()
        await ctx.send(f"Loop is now **{loop_state}**.")

    async def delete_song_log(self, song):
        for message in song.messages_to_delete:
            try:
                await message.delete()
            except Exception as e:
                continue
        song.messages_to_delete = []

    async def join_voice_channel(self, message):
        voice_channel = message.author.voice.channel
        try:
            self.voice_client = await voice_channel.connect()
        except:
            pass

        return self.voice_client

    async def add_to_queue(self, song_path, song_info, message):
        if not self.is_playing():
            await self.join_voice_channel(message)

        if message.content.startswith("play"):
            query = message.content[5:].strip()
        else:
            query = message.content[2:].strip()

        if "spotify.com" and "track" in query:
            query = await self.get_spotify_name(query)
            query = re.sub(r"\([^)]*\)", "", query)

        # lyrics = await self.fetch_lyrics(query)

        song = Song(song_path, song_info, message, None)

        self.queue.append(song)
        self.disconnect_timer = None

    async def check_play_state(self):
        return self.is_playing() or self.files.is_downloading()

    async def cleanup_files(self, current_song, queue):
        for file_name in os.listdir("."):
            if (
                file_name.endswith(".mp3")
                and file_name != current_song.path
                and all(file_name != s.path for s in queue)
            ):
                self.files.delete_file(file_name)

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
            song.lyrics_sent = True
            os.remove(lyrics_file_name)

            return lyrics_msg

    async def send_lyrics_file(self, channel, file_name):
        with open(file_name, "rb") as file:
            return await channel.send(file=discord.File(file, file_name))

    async def play_song(self, song: Song):
        if await self.check_play_state():
            return

        self.play_audio(song.path)
        self.current_song = song

        embed = await self.send_song_embed(song)
        embed_msg = await song.message.channel.fetch_message(embed.id)

        if self.last_song:
            await self.delete_song_log(self.last_song)

        song.messages_to_delete.append(embed_msg)
        song.messages_to_delete.append(song.message)

        self.last_song = song
        await self.cleanup_files(song, self.queue)

    def is_playing(self):
        return self.voice_client and self.voice_client.is_playing()

    @commands.hybrid_command(aliases=["skip", "s"])
    async def skip_song(self, ctx):
        """Skip current song"""
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()
            await ctx.message.delete()

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

    @commands.hybrid_command(aliases=["leave"])
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""
        if self.voice_client and self.voice_client.is_connected():
            if self.voice_client.is_playing():
                self.voice_client.stop()

            if self.voice_client:
                await self.voice_client.disconnect()

            if self.last_song and self.last_song.messages_to_delete:
                await self.delete_song_log(self.last_song)
                self.last_song = None

        else:
            if ctx and ctx.message:
                await ctx.send("DJ Khaled is not playing anything!")

        self.queue = []
        self.dl_queue = []
        self.current_song = None
        self.last_song = None
        self.disconnect_timer = None
        self.background_task.stop()
        self.process_dl_queue.stop()

    @commands.hybrid_command()
    async def clear(self, ctx):
        """Clears the queue."""
        self.dl_queue = []
        self.queue = []
        await ctx.send("Queue has been cleared!")

    @commands.hybrid_command(aliases=["q"])
    async def queue(self, ctx):
        """Prints the current queue."""
        queue_info_embed = self.get_queue_info_embed()
        await ctx.send(embed=queue_info_embed)
        if len(self.dl_queue) > 0:
            await ctx.send(f"**{len(self.dl_queue)}** in the download queue.")

    async def toggle_loop(self):
        self.loop = not self.loop
        return "on" if self.loop else "off"

    async def enqueue_songs(self, songs):
        for song in songs:
            if song not in self.dl_queue:
                self.dl_queue.append(song)

        self.process_dl_queue.start()

    @tasks.loop(seconds=30)
    async def process_dl_queue(self):
        if self.dl_queue.__len__() == 0:
            self.process_dl_queue.stop()
            return

        next_song_name, message = self.dl_queue.pop(0)
        (
            next_song_path,
            next_song_info,
        ) = await self.files.download_from_youtube(next_song_name, message)

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
        try:
            msg = await message.channel.fetch_message(message.id)
            if msg:
                for reaction in msg.reactions:
                    if str(reaction.emoji) == "📖":
                        users = [user async for user in reaction.users()]
                        if any(user != self.bot.user for user in users):
                            lyrics_msg = await self.handle_lyrics(song)
                            if lyrics_msg:
                                song.messages_to_delete.append(lyrics_msg)
                            break
        except Exception as e:
            print(e)


async def setup(bot):
    with open("config.json") as f:
        config = json.load(f)
        await bot.add_cog(Music(bot, config))