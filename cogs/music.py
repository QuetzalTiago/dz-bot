import asyncio
import html
import json
import os
import random
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
from cogs.files import Files
from .models.song import Song


class Music(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.queue = []
        self.dl_queue = []
        self.current_song = None
        self.dl_queue_cancelled = False
        self.voice_client = None
        self.loop = False
        self.shuffle = False
        self.last_song = None
        self.music_end_timestamp = None
        self.idle_timeout = 150
        self.audio_source = None
        self.files: Files = self.bot.get_cog("Files")
        self.config = config
        self.spotify = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=config["secrets"]["spotifyClientId"],
                client_secret=config["secrets"]["spotifyClientSecret"],
            )
        )

    @tasks.loop(seconds=2)
    async def background_task(self):
        if self.current_song and self.is_playing():
            await self.update_song_message(self.current_song)

        if not self.is_playing() and not self.files.is_downloading():
            # Clear song log
            if self.last_song:
                await self.delete_song_log(self.last_song)
                self.last_song = None
                self.current_song = None

            # Loop
            if self.loop and self.current_song:
                await self.play_song(self.current_song)

            # Process music queue
            elif self.queue:
                # Handle shuffle
                pop_index = 0
                if self.shuffle:
                    pop_index = random.randint(0, len(self.queue) - 1)

                next_song = self.queue.pop(pop_index)

                await self.play_song(next_song)

            # Handle idle
            elif (
                self.voice_client
                and self.voice_client.is_connected()
                and not self.queue
            ):
                if self.music_end_timestamp is None:
                    self.music_end_timestamp = time.time()
                elif time.time() - self.music_end_timestamp >= self.idle_timeout:
                    await self.stop(None)
                    self.music_end_timestamp = None

        # Leave if alone in channel
        if self.voice_client and self.voice_client.channel:
            members_in_channel = len(self.voice_client.channel.members)
            if members_in_channel == 1:
                await self.stop(None)
                await self.clear(None)

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

        if song_names:
            songs = map((lambda song_name: (song_name, message, True)), song_names)
            await self.enqueue_songs(songs)

    @commands.hybrid_command(aliases=["p"])
    async def play(self, ctx):
        """Plays a song from either a query or url"""
        if ctx.message.author.voice is None:
            sent_message = await ctx.send("You are not connected to a voice channel!")
            await self.cog_failure(sent_message, ctx.message)
            return

        prefix = self.config.get("prefix", "")

        content = ctx.message.content

        command_length = (
            len(prefix) + 5
            if content.lower().startswith(f"{prefix}play ")
            else len(prefix) + 2
        )

        song_url = content[command_length:]

        if not song_url:
            sent_message = await ctx.send(
                "Missing URL use command like: play https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            )
            await self.cog_failure(sent_message, ctx.message)
            return

        self.dl_queue_cancelled = False

        if "spotify.com" in song_url:
            await self.handle_spotify_url(song_url, ctx.message)
            return

        elif "list=" in song_url:  # YouTube playlist
            sent_message = await ctx.send(
                "Youtube playlists not yet supported. Try a spotify link instead."
            )
            await self.cog_failure(sent_message, ctx.message)
            return

        else:
            await self.enqueue_songs([(song_url, ctx.message, False)])

    async def update_song_message(self, song):
        song.current_seconds += 2
        embed = song.to_embed(self.queue, self.shuffle)
        if song.embed_message:
            try:
                await song.embed_message.edit(embed=embed)
            except:
                pass

    @commands.hybrid_command()
    async def loop(self, ctx):
        """Toggle loop for current song"""
        loop_state = await self.toggle_loop()
        await ctx.send(f"Loop is now **{loop_state}**.")
        await self.cog_success(ctx.message)

    @commands.hybrid_command(aliases=["random"])
    async def shuffle(self, ctx):
        """Toggle shuffle for playlist"""
        shuffle_state = await self.toggle_shuffle()
        await ctx.send(f"Shuffle is now **{shuffle_state}**.")
        await self.cog_success(ctx.message)

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

    async def add_to_queue(self, song_path, song_info, message, lyrics=None):
        if not self.is_playing():
            await self.join_voice_channel(message)

        song = Song(song_path, song_info, message, lyrics)

        self.queue.append(song)
        self.music_end_timestamp = None

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
        self.audio_source = discord.FFmpegPCMAudio(song_path)
        self.voice_client.play(self.audio_source)

    async def send_song_embed(self, song: Song):
        embed = song.to_embed(self.queue, self.shuffle)
        msg = await song.message.channel.send(embed=embed)
        song.embed_message = msg
        return msg

    async def cog_success(self, message):
        await message.clear_reactions()
        await message.add_reaction("✅")

    async def cog_failure(self, sent_message, query_message):
        await query_message.clear_reactions()
        await query_message.add_reaction("❌")

        async def delete_error_log(sent_message, query_message):
            await asyncio.sleep(30)
            try:
                await sent_message.delete()
                await query_message.delete()
            except Exception as e:
                print(f"Failed to delete message: {e}")

        self.bot.loop.create_task(delete_error_log(sent_message, query_message))

    @commands.hybrid_command()
    async def lyrics(self, ctx):
        """Sends lyrics current song (beta)"""
        song = self.current_song

        if not song:
            sent_msg = await ctx.message.channel.send(
                f"DJ Khaled is not playing anything! Play a spotify url to get lyrics."
            )
            await self.cog_failure(
                sent_msg,
                ctx.message,
            )
            return

        if song.lyrics:
            lyrics_file_name = f"lyrics.txt"
            with open(lyrics_file_name, "w", encoding="utf-8") as file:
                file.write(song.lyrics)

            lyrics_msg = await self.send_lyrics_file(
                song.message.channel, lyrics_file_name
            )

            os.remove(lyrics_file_name)

            song.messages_to_delete.append(lyrics_msg)
            song.messages_to_delete.append(ctx.message)
            await self.cog_success(ctx.message)
        else:
            sent_msg = await song.message.channel.send(
                f"No lyrics available for **{song.title}**. Try using a spotify link instead."
            )
            await self.cog_failure(sent_msg, ctx.message)

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

        last_song = self.last_song

        if last_song:
            await self.delete_song_log(last_song)

        song.messages_to_delete.append(embed_msg)

        if all(song.message is not item[1] for item in self.dl_queue) and all(
            song.message is not song.message for song in self.queue
        ):
            song.messages_to_delete.append(song.message)

        self.last_song = song
        self.bot.get_cog("Database").save_song(song.info, song.message.author.id)
        await self.cleanup_files(song, self.queue)

    def is_playing(self):
        return self.voice_client and self.voice_client.is_playing()

    @commands.hybrid_command(aliases=["skip", "s"])
    async def skip_song(self, ctx):
        """Skip current song"""
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()
            await ctx.message.delete()

    @commands.hybrid_command(aliases=["top songs", "top", "mtop"])
    async def most_played(self, ctx):
        """Shows most played songs"""
        most_played_songs = self.bot.get_cog("Database").get_most_played_songs()

        embed = discord.Embed(title="Top 5 Most Played Songs 🎵", color=0x3498DB)
        for index, (url, title, total_plays) in enumerate(most_played_songs, start=1):
            embed.add_field(
                name=f"{index}.",
                value=f"[{title}]({url}) played **{total_plays}** time{'s' if total_plays > 1 else ''}",
                inline=False,
            )

        await ctx.send(embed=embed)

    @commands.hybrid_command(
        aliases=["top users", "topreq", "rtop", "topdj", "plays", "reqs"]
    )
    async def most_requested(self, ctx):
        """Shows the top 5 users with most song requests"""
        top_users = self.bot.get_cog("Database").get_most_song_requests()

        embed = discord.Embed(
            title="Top 5 users with most requested songs 🎵", color=0x3498DB
        )
        for index, (id, total_requests) in enumerate(top_users, start=1):
            embed.add_field(
                name=f"{index}.",
                value=f"<@{id}> **{total_requests}** song{'s' if total_requests > 1 else ''} requested",
                inline=False,
            )

        await ctx.send(embed=embed)

    def get_playlist_embed(self):
        embed = discord.Embed(color=0x1ABC9C)
        embed.title = "Current playlist 🎵"

        if not self.queue:
            embed.description = "The playlist is empty."
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

        if ctx:
            await self.clear(None)
            self.dl_queue_cancelled = True
            await self.cog_success(ctx.message)

        self.current_song = None
        self.last_song = None
        self.music_end_timestamp = None

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

    @commands.hybrid_command()
    async def clear(self, ctx):
        """Clears the playlist"""
        self.dl_queue = []
        self.queue = []
        if ctx:
            await ctx.send("The playlist has been cleared!")
            await self.cog_success(ctx.message)

    @commands.hybrid_command(aliases=["q", "queue", "pl"])
    async def playlist(self, ctx):
        """Shows the current playlist"""
        playlist_embed = self.get_playlist_embed()
        await ctx.send(embed=playlist_embed)
        if len(self.dl_queue) > 0:
            await ctx.send(f"**{len(self.dl_queue)}** in the download queue.")
        await self.cog_success(ctx.message)

    async def toggle_loop(self):
        self.loop = not self.loop
        return "on" if self.loop else "off"

    async def toggle_shuffle(self):
        self.shuffle = not self.shuffle
        return "on" if self.shuffle else "off"

    async def enqueue_songs(self, songs):
        for song in songs:
            if song not in self.dl_queue:
                self.dl_queue.append(song)

        if not self.process_dl_queue.is_running():
            self.process_dl_queue.start()

        if not self.background_task.is_running():
            self.background_task.start()

    # This task cannot be forcefully cancelled
    @tasks.loop(seconds=30)
    async def process_dl_queue(self):
        if len(self.dl_queue) == 0:
            self.process_dl_queue.stop()
            return

        pop_index = 0
        if self.shuffle:
            pop_index = random.randint(0, len(self.dl_queue) - 1)

        next_song_name, message, spotify_req = self.dl_queue.pop(pop_index)

        await message.add_reaction("⌛")

        lyrics = None

        if spotify_req:
            lyrics = await self.fetch_lyrics(next_song_name)
            next_song_name += " audio"

        (
            next_song_path,
            next_song_info,
        ) = await self.files.download_from_youtube(next_song_name, message)
        
        if all(message is not item[1] for item in self.dl_queue):
            await self.cog_success(message)

        if self.dl_queue_cancelled:
            self.dl_queue_cancelled = False
            self.process_dl_queue.stop()
            self.background_task.stop()
        else:
            await self.add_to_queue(next_song_path, next_song_info, message, lyrics)
    async def fetch_lyrics(self, song_name):
        if "/playlist/" in song_name or "list=" in song_name:
            return None

        base_url = "https://api.genius.com"
        headers = {
            "Authorization": "Bearer "
            + "bnYy6f7T2v_YPfhmT9nvkXHZd5SIsSQ8gDKRQrMmz4ipZ6C_aM8dpTMPb3GDkm4p"
        }

        # Search for the song
        query = song_name.split("(")[0]
        search_url = base_url + f"/search?q={query}"
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


async def setup(bot):
    with open("config.json") as f:
        config = json.load(f)
        await bot.add_cog(Music(bot, config))
