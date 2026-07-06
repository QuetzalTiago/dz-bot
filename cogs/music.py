import asyncio
import logging
import os
import uuid

import discord
from discord.ext import commands

from cogs.api.youtube import DOWNLOAD_DIR
from cogs.utils.config import load_config
from cogs.utils.emojis import DONE, ERROR
from cogs.utils.music.guild_state import GuildMusicState
from cogs.utils.music.state_machine import State


class Music(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.logger = logging.getLogger("discord")
        # One music state per guild so guilds don't share a voice client,
        # playlist or download queue.
        self.guild_states: dict[int, GuildMusicState] = {}

    def get_state(self, guild) -> GuildMusicState:
        if guild.id not in self.guild_states:
            self.guild_states[guild.id] = GuildMusicState(self, guild)
        return self.guild_states[guild.id]

    def _state_for_ctx(self, ctx) -> GuildMusicState:
        return self.get_state(ctx.guild)

    async def handle_forced_disconnect(self, guild):
        """Called when the bot is kicked/disconnected from a voice channel."""
        state = self.guild_states.get(guild.id)
        if state is not None:
            await state.teardown()

    # Response Helpers
    async def cog_success(self, message):
        try:
            await message.clear_reactions()
            await message.add_reaction(DONE)
        except discord.DiscordException:
            pass

    async def cog_failure(self, sent_message, query_message):
        try:
            await query_message.clear_reactions()
            await query_message.add_reaction(ERROR)
        except discord.DiscordException:
            pass

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

    # Cleanup: only touches the dedicated downloads directory.
    def cleanup_files(self, current_song, queue):
        if not os.path.isdir(DOWNLOAD_DIR):
            return
        keep = {current_song.path} | {s.path for s in queue}
        for file_name in os.listdir(DOWNLOAD_DIR):
            full_path = os.path.join(DOWNLOAD_DIR, file_name)
            if full_path in keep:
                continue
            delete_file(full_path, self.logger)

    def _require_voice(self, ctx):
        return ctx.message.author.voice is not None

    # Commands
    @commands.hybrid_command(aliases=["p"])
    @commands.guild_only()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def play(self, ctx, *, query: str = ""):
        """Plays a song from either a query or url."""
        if not self._require_voice(ctx):
            sent_message = await ctx.send("You are not connected to a voice channel!")
            await self.cog_failure(sent_message, ctx.message)
            return

        state = self._state_for_ctx(ctx)
        combined_len = len(state.downloader.queue) + len(state.playlist.songs)
        if combined_len + 1 > state.playlist.max_size:
            sent_message = await ctx.send(
                "Maximum playlist size reached. Please *skip* the current song "
                "or *clear* the list to add more."
            )
            await self.cog_failure(sent_message, ctx.message)
            return

        song_url = self._extract_query(ctx, query)
        if not song_url:
            sent_message = await ctx.send(
                "Missing URL use command like: play "
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            )
            await self.cog_failure(sent_message, ctx.message)
            return

        if "list=" in song_url:  # YouTube playlist
            sent_message = await ctx.send(
                "Youtube playlists not yet supported. Try a spotify link instead."
            )
            await self.cog_failure(sent_message, ctx.message)
            return

        await state.downloader.enqueue(song_url, ctx.message)

    def _extract_query(self, ctx, query):
        """Prefer the parsed argument; fall back to slicing prefix commands.

        Slash invocations provide `query` directly; classic prefix invocations
        may also carry it, but we fall back to the raw content for backwards
        compatibility with the historic parsing.
        """
        if query:
            return query.strip()
        content = ctx.message.content or ""
        prefix = self.config.get("prefix", "")
        for name in ("play ", "p "):
            token = f"{prefix}{name}"
            if content.lower().startswith(token):
                return content[len(token):].strip()
        return ""

    @commands.hybrid_command()
    @commands.guild_only()
    async def loop(self, ctx):
        """Toggle loop for current song."""
        loop_state = self._state_for_ctx(ctx).playlist.toggle_loop()
        await ctx.send(f"Loop is now **{loop_state}**.")
        await self.cog_success(ctx.message)

    @commands.hybrid_command(aliases=["random"])
    @commands.guild_only()
    async def shuffle(self, ctx):
        """Toggle shuffle for playlist."""
        shuffle_state = self._state_for_ctx(ctx).playlist.toggle_shuffle()
        await ctx.send(f"Shuffle is now **{shuffle_state}**.")
        await self.cog_success(ctx.message)

    @commands.hybrid_command()
    @commands.guild_only()
    async def pause(self, ctx):
        """Pauses audio."""
        state = self._state_for_ctx(ctx)
        if state.state_machine.get_state() == State.PLAYING:
            state.state_machine.transition_to(State.PAUSED)
            await self.cog_success(ctx.message)
        else:
            sent_message = await ctx.send("DJ Khaled is not playing anything!")
            await self.cog_failure(sent_message, ctx.message)

    @commands.hybrid_command()
    @commands.guild_only()
    async def resume(self, ctx):
        """Resumes audio."""
        state = self._state_for_ctx(ctx)
        if state.state_machine.get_state() == State.PAUSED:
            state.state_machine.transition_to(State.RESUMED)
            await self.cog_success(ctx.message)
        else:
            sent_message = await ctx.send("DJ Khaled is not paused!")
            await self.cog_failure(sent_message, ctx.message)

    @commands.hybrid_command()
    @commands.guild_only()
    async def lyrics(self, ctx):
        """Sends lyrics of the current song (beta)."""
        state = self._state_for_ctx(ctx)
        song = state.playlist.current_song

        if not song:
            sent_msg = await ctx.message.channel.send(
                "DJ Khaled is not playing anything! Play a spotify url to get lyrics."
            )
            await self.cog_failure(sent_msg, ctx.message)
            return

        if song.lyrics:
            lyrics_file_name = f"lyrics_{uuid.uuid4().hex}.txt"
            try:
                with open(lyrics_file_name, "w", encoding="utf-8") as file:
                    file.write(song.lyrics)
                lyrics_msg = await self.send_lyrics_file(
                    song.message.channel, lyrics_file_name
                )
            finally:
                if os.path.exists(lyrics_file_name):
                    os.remove(lyrics_file_name)

            song.messages_to_delete.append(lyrics_msg)
            song.messages_to_delete.append(ctx.message)
            await self.cog_success(ctx.message)
        else:
            sent_msg = await song.message.channel.send(
                f"No lyrics available for **{song.title}**. "
                "Try using a spotify link instead."
            )
            await self.cog_failure(sent_msg, ctx.message)

    @commands.hybrid_command(aliases=["skip", "s"])
    @commands.guild_only()
    async def skip_song(self, ctx):
        """Skip current song."""
        state = self._state_for_ctx(ctx)
        if state.state_machine.get_state() != State.PLAYING:
            sent_message = await ctx.send("DJ Khaled is not playing anything!")
            await self.cog_failure(sent_message, ctx.message)
            return

        if state.playlist.loop:
            sent_msg = await ctx.message.channel.send(
                "*Loop* is **ON**. Please disable *Loop* before skipping."
            )
            await self.cog_failure(sent_msg, ctx.message)
            return

        await state.player.skip(ctx.message)

    @commands.hybrid_command(aliases=["top songs", "top", "mtop"])
    @commands.guild_only()
    async def most_played(self, ctx):
        """Shows most played songs."""
        most_played_songs = await self.bot.get_cog("Database").get_most_played_songs()
        embed = discord.Embed(title="Top 5 Most Played Songs 🎵", color=0x3498DB)
        for index, (url, title, total_plays) in enumerate(most_played_songs, start=1):
            embed.add_field(
                name=f"{index}.",
                value=f"[{title}]({url}) played **{total_plays}** "
                f"time{'s' if total_plays > 1 else ''}",
                inline=False,
            )
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        aliases=["top users", "topreq", "rtop", "topdj", "plays", "reqs"]
    )
    @commands.guild_only()
    async def most_requested(self, ctx):
        """Shows the top 5 users with most song requests."""
        top_users = await self.bot.get_cog("Database").get_most_song_requests()
        embed = discord.Embed(
            title="Top 5 users with most requested songs 🎵", color=0x3498DB
        )
        for index, (user_id, total_requests) in enumerate(top_users, start=1):
            embed.add_field(
                name=f"{index}.",
                value=f"<@{user_id}> **{total_requests}** "
                f"song{'s' if total_requests > 1 else ''} requested",
                inline=False,
            )
        await ctx.send(embed=embed)

    @commands.hybrid_command(aliases=["leave"])
    @commands.guild_only()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice."""
        state = self._state_for_ctx(ctx)
        await state.state_machine.stop()
        await state.downloader.stop()
        await state.player.stop()

        await self._clear_state(state)
        await self.cog_success(ctx.message)
        await ctx.message.delete()

    async def _clear_state(self, state: GuildMusicState):
        await state.downloader.clear()
        await state.playlist.clear()

    @commands.hybrid_command()
    @commands.guild_only()
    async def clear(self, ctx):
        """Clears the playlist."""
        state = self._state_for_ctx(ctx)
        await self._clear_state(state)
        await ctx.send("The playlist has been cleared!")
        await self.cog_success(ctx.message)
        await ctx.message.delete()

    @commands.hybrid_command(aliases=["pl", "playlist"])
    @commands.guild_only()
    async def _playlist(self, ctx):
        """Shows the current playlist."""
        state = self._state_for_ctx(ctx)
        playlist_embed = state.playlist.get_embed()
        message_sent = await ctx.send(embed=playlist_embed)

        try:
            if state.playlist.sent_message:
                await state.playlist.sent_message.delete()
            if state.playlist.user_req_message:
                await state.playlist.user_req_message.delete()
        except discord.DiscordException:
            pass

        state.playlist.sent_message = message_sent
        state.playlist.user_req_message = ctx.message
        await self.cog_success(ctx.message)


async def setup(bot):
    await bot.add_cog(Music(bot, load_config()))


def delete_file(file_path, logger):
    try:
        os.remove(file_path)
        logger.info(f"File {file_path} deleted successfully")
    except Exception as e:
        logger.info(f"Error deleting file {file_path}. Error: {e}")
