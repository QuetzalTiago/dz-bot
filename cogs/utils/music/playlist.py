import logging
import random
from typing import List, Optional

import discord
from discord import Message

from cogs.models.song import Song


class Playlist:
    def __init__(self, state, max_size=25):
        # `state` is the per-guild GuildMusicState.
        self.state = state
        self.songs: List[Song] = []
        self.max_size: int = max_size
        self.shuffle: bool = False
        self.loop: bool = False
        self.last_song: Optional[Song] = None
        self.current_song: Optional[Song] = None
        self.sent_message: Optional[Message] = None
        self.user_req_message: Optional[Message] = None
        self.logger = logging.getLogger("discord")

    def _get_looped_song(self) -> Optional[Song]:
        if self.loop and self.current_song:
            self.current_song.current_seconds = 0
            return self.current_song
        return None

    async def clear_last(self):
        if self.last_song:
            await self.delete_song_log(self.last_song)
            self.last_song = None

    def _handle_index(self) -> int:
        if self.shuffle and self.songs:
            return random.randint(0, len(self.songs) - 1)
        return 0

    def toggle_loop(self):
        self.loop = not self.loop
        return "on" if self.loop else "off"

    def toggle_shuffle(self):
        self.shuffle = not self.shuffle
        return "on" if self.shuffle else "off"

    async def add(
        self,
        song_path: str,
        song_info: dict,
        message: Message,
        lyrics: Optional[str] = None,
    ):
        await self.state.player.join_voice_channel(message)
        self.songs.append(Song(song_path, song_info, message, lyrics))

    async def get_next(self) -> Optional[Song]:
        looped_song = self._get_looped_song()
        if looped_song:
            return looped_song

        await self.clear_last()

        if not self.songs:
            return None

        index = self._handle_index()
        next_song = self.songs.pop(index)
        self.set_current_song(next_song)
        return next_song

    def empty(self) -> bool:
        return len(self.songs) == 0

    def set_current_song(self, song: Optional[Song]):
        self.current_song = song

    def set_last_song(self, song: Optional[Song]):
        self.last_song = song

    async def delete_song_log(self, song: Song):
        for message in song.messages_to_delete:
            try:
                await message.delete()
            except Exception as e:
                self.logger.warning(f"Failed to delete message: {e}")
        song.messages_to_delete = []

    async def update_curr_song_message(self):
        song = self.current_song
        if song:
            song.current_seconds += 2
            embed = song.to_embed(self.songs, self.shuffle, self.loop)
            if song.embed_message:
                try:
                    await song.embed_message.edit(embed=embed)
                except Exception as e:
                    self.logger.warning(
                        "Exception while updating message for song %s: %s",
                        song.title,
                        e,
                    )

    async def update_message(self):
        if not self.sent_message:
            return
        try:
            await self.sent_message.edit(embed=self.get_embed())
        except Exception as e:
            self.logger.warning(f"Exception while updating playlist message: {e}")

    def get_embed(self) -> discord.Embed:
        dl_queue = self.state.downloader.queue
        embed = discord.Embed(color=0x1ABC9C)
        embed.title = "🎵 Current Playlist 🎵"
        if not self.songs:
            embed.description = "The playlist is empty."
            return embed

        description = ""
        for index, song in enumerate(self.songs, 1):
            if index < 20:
                description += f"{index}. **{song.title}**\n"
            else:
                description += "and more...\n"
                break

        if dl_queue:
            description += f"**{len(dl_queue)}** more in the download queue."
        embed.description = description
        return embed

    async def send_song_embed(self, song: Song) -> Optional[Message]:
        embed = song.to_embed(self.songs, self.shuffle)
        try:
            msg = await song.message.channel.send(embed=embed)
            song.embed_message = msg
            return msg
        except Exception as e:
            self.logger.warning(
                "Exception while sending embed for song %s: %s", song.title, e
            )
            return None

    async def clear(self):
        await self.clear_last()
        self.songs = []
        self.current_song = None
        self.last_song = None
