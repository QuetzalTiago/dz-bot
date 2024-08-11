import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
import random
import discord
import time
from discord.ext import commands, tasks
from .models.song import Song
from .api.genius import GeniusAPI
from .api.spotify import SpotifyAPI
from .api.youtube import YouTubeAPI


class Music(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.dl_queue = []
        self.dl_queue_cancelled = False
        self.playlist = []
        self.playlist_message = None
        self.playlist_request_message = None
        self.current_song = None
        self.voice_client = None
        self.loop = False
        self.shuffle = False
        self.last_song = None
        self.music_end_timestamp = None
        self.idle_timeout = 150
        self.audio_source = None
        self.config = config

        self.spotify = SpotifyAPI(config)
        self.youtube = YouTubeAPI(config)
        self.genius = GeniusAPI(config)

    # Background

    @tasks.loop(seconds=2)
    async def background_task(self):
        if self.current_song and self.is_playing():
            await self.update_song_message(self.current_song)

        if not self.is_playing():
            # Loop
            if self.loop and self.current_song:
                self.current_song.current_seconds = 0
                await self.play_song(self.current_song)
                return

            # Clear song log
            if self.last_song:
                await self.delete_song_log(self.last_song)
                self.last_song = None
                self.current_song = None

            # Handle playlist
            elif self.playlist:
                # Handle shuffle
                pop_index = 0
                if self.shuffle:
                    pop_index = random.randint(0, len(self.playlist) - 1)

                next_song = self.playlist.pop(pop_index)

                await self.play_song(next_song)

            # Handle idle
            elif (
                self.voice_client
                and self.voice_client.is_connected()
                and not self.playlist
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

    # This task cannot be forcefully cancelled, use self.dl_queue_cancelled = True
    @tasks.loop(seconds=30)
    async def process_dl_queue(self):
        if len(self.dl_queue) == 0:
            self.process_dl_queue.stop()
            return

        pop_index = 0
        if self.shuffle:
            pop_index = random.randint(0, len(self.dl_queue) - 1)

        next_song_name, message, spotify_req = self.dl_queue.pop(pop_index)

        try:
            await message.add_reaction("⌛")
        except:
            pass

        with ThreadPoolExecutor(max_workers=1) as executor:
            is_playable = await self.bot.loop.run_in_executor(
                executor, self.youtube.is_video_playable, next_song_name
            )

        if not is_playable:
            sent_message = await message.channel.send(
                f"**{next_song_name}** is too long. Try another query."
            )
            await self.cog_failure(sent_message, message)
            return

        lyrics = None
        if spotify_req:
            lyrics = await self.genius.fetch_lyrics(next_song_name)
            next_song_name = f"{next_song_name} audio"

        with ThreadPoolExecutor(max_workers=1) as executor:
            next_song_path, next_song_info = await self.bot.loop.run_in_executor(
                executor, self.youtube.download, next_song_name
            )

        # Mark download complete (playlist / single song)
        if all(message is not item[1] for item in self.dl_queue):
            await self.cog_success(message)

        if self.dl_queue_cancelled:
            self.dl_queue_cancelled = False
            self.process_dl_queue.stop()
            self.background_task.stop()
        else:
            await self.add_to_playlist(next_song_path, next_song_info, message, lyrics)

        await self.update_playlist_message()

    # Spotify
    async def handle_spotify_url(self, url, message):
        song_names = []

        if "/playlist/" in url:
            song_names = await self.spotify.get_playlist_songs(url)
        elif "/album/" in url:
            song_names = await self.spotify.get_album_songs(url)
        else:
            spotify_name = await self.spotify.get_track_name(url)
            song_names.append(spotify_name)

        if song_names:
            songs = map((lambda song_name: (song_name, message, True)), song_names)
            await self.download_songs(songs)

    # Playlist
    def get_playlist_embed(self):
        embed = discord.Embed(color=0x1ABC9C)
        embed.title = "🎵 Current Playlist 🎵"
        if not self.playlist:
            embed.description = "The playlist is empty."
            return embed

        description = ""
        for index, song in enumerate(self.playlist, 1):
            if index < 20:
                description += f"{index}. **{song.title}**\n"
            else:
                description += f"and more...\n"
                break

        if len(self.dl_queue) > 0:
            description += f"**{len(self.dl_queue)}** more in the download queue."

        embed.description = description
        return embed

    async def download_songs(self, songs):
        for song in songs:
            if song not in self.dl_queue:
                self.dl_queue.append(song)

        if not self.process_dl_queue.is_running():
            self.process_dl_queue.start()

        if not self.background_task.is_running():
            self.background_task.start()

    async def add_to_playlist(self, song_path, song_info, message, lyrics=None):
        if not self.is_playing():
            await self.join_voice_channel(message)

        song = Song(song_path, song_info, message, lyrics)
        self.playlist.append(song)
        self.music_end_timestamp = None

    async def update_playlist_message(self):
        if not self.playlist_message:
            return

        last_playlist_message = self.playlist_message
        updated_playlist_embed = self.get_playlist_embed()
        await last_playlist_message.edit(embed=updated_playlist_embed)

    # Playback
    def is_playing(self):
        return self.voice_client and self.voice_client.is_playing()

    def toggle_loop(self):
        self.loop = not self.loop
        return "on" if self.loop else "off"

    def toggle_shuffle(self):
        self.shuffle = not self.shuffle
        return "on" if self.shuffle else "off"

    async def play_song(self, song: Song):
        if self.is_playing():
            return

        self.play_audio(song.path)
        self.current_song = song

        if not song.messages_to_delete:
            embed = await self.send_song_embed(song)
            embed_msg = await song.message.channel.fetch_message(embed.id)
            song.messages_to_delete.append(embed_msg)

        if all(song.message is not item[1] for item in self.dl_queue) and all(
            song.message is not song.message for song in self.playlist
        ):
            song.messages_to_delete.append(song.message)

        self.last_song = song
        self.bot.get_cog("Database").save_song(song.info, song.message.author.id)
        self.cleanup_files(song, self.playlist)

    # Voice client
    async def join_voice_channel(self, message):
        voice_channel = message.author.voice.channel
        try:
            self.voice_client = await voice_channel.connect()
        except:
            pass

        return self.voice_client

    def play_audio(self, song_path):
        self.audio_source = discord.FFmpegPCMAudio(song_path)
        self.voice_client.play(self.audio_source)

    # Messaging
    async def update_song_message(self, song):
        song.current_seconds += 2
        embed = song.to_embed(self.playlist, self.shuffle, self.loop)
        if song.embed_message:
            try:
                await song.embed_message.edit(embed=embed)
            except:
                pass

    async def send_song_embed(self, song: Song):
        embed = song.to_embed(self.playlist, self.shuffle)
        msg = await song.message.channel.send(embed=embed)
        song.embed_message = msg
        return msg

    async def delete_song_log(self, song):
        for message in song.messages_to_delete:
            try:
                await message.delete()
            except Exception as e:
                continue
        song.messages_to_delete = []

    # Response Helpers
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

    async def send_lyrics_file(self, channel, file_name):
        with open(file_name, "rb") as file:
            return await channel.send(file=discord.File(file, file_name))

    # Cleanup
    def cleanup_files(self, current_song, queue):
        for file_name in os.listdir("."):
            if (
                (
                    file_name.endswith(self.youtube.audio_format)
                    or file_name.endswith("m4a")
                )
                and file_name != current_song.path
                and all(file_name != s.path for s in queue)
            ):
                delete_file(file_name)

    # Commands
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
            await self.download_songs([(song_url, ctx.message, False)])

    @commands.hybrid_command()
    async def loop(self, ctx):
        """Toggle loop for current song"""
        loop_state = self.toggle_loop()
        await ctx.send(f"Loop is now **{loop_state}**.")
        await self.cog_success(ctx.message)

    @commands.hybrid_command(aliases=["random"])
    async def shuffle(self, ctx):
        """Toggle shuffle for playlist"""
        shuffle_state = self.toggle_shuffle()
        await ctx.send(f"Shuffle is now **{shuffle_state}**.")
        await self.cog_success(ctx.message)

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

    @commands.hybrid_command(aliases=["skip", "s"])
    async def skip_song(self, ctx):
        """Skip current song"""
        if self.loop:
            sent_msg = await ctx.message.channel.send(
                "*Loop* is **ON**. Please disable *Loop* before skipping."
            )
            await self.cog_failure(sent_msg, ctx.message)
            return

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
        self.playlist = []
        if ctx:
            await ctx.send("The playlist has been cleared!")
            await self.cog_success(ctx.message)

    @commands.hybrid_command(aliases=["pl"])
    async def playlist(self, ctx):
        """Shows the current playlist"""
        playlist_embed = self.get_playlist_embed()
        message_sent = await ctx.send(embed=playlist_embed)

        try:
            if self.playlist_message:
                await self.playlist_message.delete()

            if self.playlist_request_message:
                await self.playlist_request_message.delete()
        except:
            pass

        self.playlist_message = message_sent
        self.playlist_request_message = ctx.message

        await self.cog_success(ctx.message)


async def setup(bot):
    with open("config.json") as f:
        config = json.load(f)
        await bot.add_cog(Music(bot, config))


def delete_file(file_path):
    try:
        os.remove(file_path)
        print(f"File {file_path} deleted successfully")
    except Exception as e:
        print(f"Error deleting file {file_path}. Error: {e}")
