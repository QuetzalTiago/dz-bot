"""Per-guild music state.

The music engine used to keep a single player, playlist, download queue and
state machine for the whole process, so the bot could only play in one guild at
a time and a second guild's songs leaked into the first guild's channel. Each
guild now gets its own :class:`GuildMusicState`; the ``Music`` cog owns a
``guild_id -> GuildMusicState`` map and routes every command to the caller's
guild.
"""

import logging

from cogs.utils.music.downloader import Downloader
from cogs.utils.music.player import Player
from cogs.utils.music.playlist import Playlist
from cogs.utils.music.state_machine import State, StateMachine


class GuildMusicState:
    def __init__(self, cog, guild):
        self.cog = cog
        self.bot = cog.bot
        self.guild = guild
        self.config = cog.config
        self.logger = logging.getLogger("discord")

        self.playlist = Playlist(self)
        self.player = Player(self)
        self.state_machine = StateMachine(self)
        self.downloader = Downloader(self)

    # Presentation helpers proxied to the cog so the internal classes don't need
    # to know about Discord reaction plumbing.
    async def cog_success(self, message):
        await self.cog.cog_success(message)

    async def cog_failure(self, sent_message, query_message):
        await self.cog.cog_failure(sent_message, query_message)

    def cleanup_files(self, current_song, queue):
        self.cog.cleanup_files(current_song, queue)

    async def stop(self, ctx=None):
        # state_machine.stop() cancels the handle_state loop's own task, which
        # is the task running this code when called from an auto-stop tick
        # (idle timeout / alone-in-channel). Cancelling first meant the
        # CancelledError surfaced at player.stop()'s voice disconnect await
        # and skipped every cleanup step after it - so cancel the loop last,
        # once all other cleanup has actually run.
        await self.downloader.stop()
        await self.player.stop()
        await self.clear()
        await self.state_machine.stop()

    async def clear(self, ctx=None):
        await self.downloader.clear()
        await self.playlist.clear()

    async def teardown(self):
        """Fully tear down this guild's state (used on forced disconnect)."""
        await self.state_machine.stop()
        await self.downloader.clear()
        await self.player.stop()
        await self.playlist.clear()
        self.state_machine.set_state(State.DISCONNECTED)
