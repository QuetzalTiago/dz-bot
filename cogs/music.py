import asyncio
import json
import os
import discord
import logging
from discord.ext import commands
from cogs.utils.music.downloader import Downloader
from cogs.utils.music.player import Player
from cogs.utils.music.playlist import Playlist
from cogs.utils.music.state_machine import State, StateMachine


class Music(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.playlist = Playlist(self)
        self.player = Player(self)
        self.state_machine = StateMachine(self)
        self.downloader = Downloader(self)
        self.logger = logging.getLogger("discord")

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
                    file_name.endswith(self.downloader.youtube.audio_format)
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

        combined_total_playlist_len = len(self.downloader.queue) + len(
            self.playlist.songs
        )
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

        if "list=" in song_url:  # YouTube playlist
            sent_message = await ctx.send(
                "Youtube playlists not yet supported. Try a spotify link instead."
            )
            await self.cog_failure(sent_message, ctx.message)
            return

        else:
            await self.downloader.enqueue(song_url, ctx.message)

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
        if self.state_machine.state != State.PLAYING:
            sent_message = await ctx.send("DJ Khaled is not playing anything!")
            self.cog_failure(sent_message, ctx.message)

            return

        elif self.playlist.loop:
            sent_msg = await ctx.message.channel.send(
                "*Loop* is **ON**. Please disable *Loop* before skipping."
            )
            await self.cog_failure(sent_msg, ctx.message)
            return

        await self.player.skip(ctx.message)

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
        state = self.state_machine.state
        if state == State.DISCONNECTED:
            self.state_machine.stop()
            self.downloader.stop()
            self.player.stop()

            if ctx:
                await self.clear(None)
                await self.cog_success(ctx.message)

        else:
            if ctx and ctx.message:
                sent_message = await ctx.send("DJ Khaled is not playing anything!")
                self.cog_failure(sent_message, ctx.message)

    @commands.hybrid_command()
    async def clear(self, ctx):
        """Clears the playlist"""
        await self.downloader.clear()
        await self.playlist.clear()
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
