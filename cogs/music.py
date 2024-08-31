import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
import random
import discord
import logging
from discord.ext import commands, tasks
from cogs.utils.music.playlist import Playlist
from cogs.utils.music.state_machine import State, StateMachine
from .models.song import Song
from .api.genius import GeniusAPI
from .api.spotify import SpotifyAPI
from .api.youtube import YouTubeAPI


class Music(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.state_machine = StateMachine(self)
        self.playlist = Playlist()
        self.dl_queue = []
        self.dl_queue_cancelled = False
        self.voice_client = None
        self.music_end_timestamp = None
        self.idle_timeout = 150
        self.audio_source = None
        self.logger = logging.getLogger("discord")

        self.spotify = SpotifyAPI(config)
        self.youtube = YouTubeAPI(config)
        self.genius = GeniusAPI(config)

    async def download_next_song(self):
        if len(self.dl_queue) == 0:
            return

        pop_index = 0
        if self.playlist.shuffle:
            pop_index = random.randint(0, len(self.dl_queue) - 1)

        next_song_name, message, spotify_req = self.dl_queue.pop(pop_index)

        try:
            await message.add_reaction("⌛")
        except:
            pass

        with ThreadPoolExecutor(max_workers=1) as executor:
            try:
                is_playable = await self.bot.loop.run_in_executor(
                    executor, self.youtube.is_video_playable, next_song_name
                )
            except:
                is_playable = False

        if not is_playable:
            sent_message = await message.channel.send(
                f"**{next_song_name}** is too long or there was an error downloading the song. Try another query."
            )
            await self.cog_failure(sent_message, message)
            return

        lyrics = None
        if spotify_req:
            lyrics = await self.genius.fetch_lyrics(next_song_name)
            next_song_name = f"{next_song_name} audio"

        with ThreadPoolExecutor(max_workers=1) as executor:
            try:
                next_song_path, next_song_info = await self.bot.loop.run_in_executor(
                    executor, self.youtube.download, next_song_name
                )
            except:
                sent_message = await message.channel.send(
                    f"**{next_song_name}** is too long or there was an error downloading the song. Try another query."
                )
                await self.cog_failure(sent_message, message)
                return

        # Mark download complete if the song message is not on download queue
        if all(message is not item[1] for item in self.dl_queue):
            await self.cog_success(message)

        if self.dl_queue_cancelled:
            self.dl_queue_cancelled = False
            self.process_dl_queue.stop()
            self.state_machine.stop()
        else:
            await self.add_to_playlist(next_song_path, next_song_info, message, lyrics)

        await self.playlist.update_message(self.dl_queue)

    @tasks.loop(seconds=30)
    async def process_dl_queue(self):
        if len(self.dl_queue) == 0:
            self.process_dl_queue.stop()
            return

        await self.download_next_song()

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

    async def download_songs(self, songs):
        for song in songs:
            if song not in self.dl_queue:
                combined_total_song_len = len(self.dl_queue) + len(self.playlist.songs)

                if combined_total_song_len + 1 <= self.playlist.max_size:
                    self.dl_queue.append(song)

        if not self.process_dl_queue.is_running():
            await self.download_next_song()
            self.process_dl_queue.start()

        self.state_machine.start()

    async def add_to_playlist(self, song_path, song_info, message, lyrics=None):
        await self.join_voice_channel(message)

        await self.playlist.add(song_path, song_info, message, lyrics)
        self.music_end_timestamp = None

    async def play_song(self, song: Song):
        if self.state_machine.state == State.PLAYING:
            return

        self.state_machine.set_state(State.PLAYING)
        self.play_audio(song.path)
        self.playlist.set_current_song(song)
        self.logger.info(f"Playing song: {song.title}")
        await self.playlist.update_message(self.dl_queue)

        if not song.messages_to_delete:
            # Send embed
            embed = await self.playlist.send_song_embed(song)
            if embed:
                song.messages_to_delete.append(embed)

        if all(song.message is not item[1] for item in self.dl_queue) and all(
            song.message is not song.message for song in self.playlist.songs
        ):
            # Song/Playlist download completed
            song.messages_to_delete.append(song.message)

        # Set last song
        self.playlist.set_last_song(song)

        # Save statistics data on db
        self.bot.get_cog("Database").save_song(song.info, song.message.author.id)

        # Cleanup
        self.cleanup_files(song, self.playlist.songs)

    # Voice client
    async def join_voice_channel(self, message):
        if self.state_machine.state == State.DISCONNECTED:
            voice_channel = message.author.voice.channel
            try:
                self.voice_client = await voice_channel.connect()
            except:
                return

            self.state_machine.set_state(State.STOPPED)

            return self.voice_client

    def play_audio(self, song_path):
        self.audio_source = discord.FFmpegPCMAudio(song_path)
        self.voice_client.play(self.audio_source)

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
                self.logger.info(f"Failed to delete message: {e}")

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
                delete_file(file_name, self.logger)

    # Commands
    @commands.hybrid_command(aliases=["p"])
    async def play(self, ctx):
        """Plays a song from either a query or url"""
        if ctx.message.author.voice is None:
            sent_message = await ctx.send("You are not connected to a voice channel!")
            await self.cog_failure(sent_message, ctx.message)
            return

        combined_total_playlist_len = len(self.dl_queue) + len(self.playlist.songs)
        if combined_total_playlist_len + 1 > self.playlist.max_size:
            sent_message = await ctx.send(
                "Maximum playlist size reached. Please *skip* the current song or *clear* the list to add more."
            )
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
        loop_state = self.playlist.toggle_loop()
        await ctx.send(f"Loop is now **{loop_state}**.")
        await self.cog_success(ctx.message)

    @commands.hybrid_command(aliases=["random"])
    async def shuffle(self, ctx):
        """Toggle shuffle for playlist"""
        shuffle_state = self.playlist.toggle_shuffle()
        await ctx.send(f"Shuffle is now **{shuffle_state}**.")
        await self.cog_success(ctx.message)

    @commands.hybrid_command()
    async def pause(self, ctx):
        """Pauses audio"""
        if self.state_machine.state == State.PLAYING:
            self.state_machine.set_state(State.PAUSED)
            await self.cog_success(ctx.message)

        else:
            sent_message = await ctx.send("DJ Khaled is not playing anything!")
            await self.cog_failure(sent_message, ctx.message)

    @commands.hybrid_command()
    async def resume(self, ctx):
        """Resumes audio"""
        if self.state_machine.state == State.PAUSED:
            self.state_machine.set_state(State.RESUMED)
            await self.cog_success(ctx.message)

        else:
            sent_message = await ctx.send("DJ Khaled is not paused!")
            await self.cog_failure(sent_message, ctx.message)

    @commands.hybrid_command()
    async def lyrics(self, ctx):
        """Sends lyrics current song (beta)"""
        song = self.playlist.current_song

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
        if self.playlist.loop:
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

        if self.last_song:
            await self.delete_song_log(self.last_song)

        self.playlist.set_current_song(None)
        self.playlist.set_last_song(None)
        self.music_end_timestamp = None
        self.state_machine.stop()
        self.dl_queue_cancelled = True

        if self.voice_client and self.voice_client.is_connected():
            if self.voice_client.is_playing():
                self.voice_client.stop()

            if self.voice_client:
                await self.voice_client.disconnect()

            await self.playlist.clear_last()
            self.state_machine.set_state(State.DISCONNECTED)
        else:
            if ctx and ctx.message:
                sent_message = await ctx.send("DJ Khaled is not playing anything!")
                self.cog_failure(sent_message, ctx.message)

    @commands.hybrid_command()
    async def clear(self, ctx):
        """Clears the playlist"""
        self.dl_queue = []
        self.playlist.clear()
        if ctx:
            await ctx.send("The playlist has been cleared!")
            await self.cog_success(ctx.message)

    @commands.hybrid_command(aliases=["pl", "playlist"])
    async def _playlist(self, ctx):
        """Shows the current playlist"""
        playlist_embed = self.playlist.get_embed()
        message_sent = await ctx.send(embed=playlist_embed)

        try:
            if self.playlist.sent_message:
                await self.playlist.sent_message.delete()

            if self.playlist.user_req_message:
                await self.playlist.user_req_message.delete()
        except:
            pass

        self.playlist.sent_message = message_sent
        self.playlist.user_req_message = ctx.message

        await self.cog_success(ctx.message)


async def setup(bot):
    with open("config.json") as f:
        config = json.load(f)
        await bot.add_cog(Music(bot, config))


def delete_file(file_path, logger):
    try:
        os.remove(file_path)
        logger.info(f"File {file_path} deleted successfully")
    except Exception as e:
        logger.info(f"Error deleting file {file_path}. Error: {e}")
