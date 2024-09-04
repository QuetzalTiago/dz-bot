import logging
import discord
from discord import Message
import random
from typing import Optional, List

from cogs.models.song import Song


class Playlist:
    def __init__(self, music, max_size=25):
        self.music = music
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
        self.logger.info("Clearing last song")
        if self.last_song:
            await self.delete_song_log(self.last_song)
            self.last_song = None
            self.logger.info("Last song cleared")

    def _handle_index(self) -> int:
        if self.shuffle:
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
        await self.music.player.join_voice_channel(message)

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

    def clear(self):
        self.songs = []

    def set_current_song(self, song: Optional[Song]):
        self.current_song = song
        if song:
            self.logger.info(f"Current song set as {song.title}")
        else:
            self.logger.info("Current song cleared")

    def set_last_song(self, song: Optional[Song]):
        self.last_song = song
        if song:
            self.logger.info(f"Last song set as {song.title}")
        else:
            self.logger.info("Last song cleared")

    async def delete_song_log(self, song: Song):
        self.logger.info(f"Deleting song log for {song.title}")
        for message in song.messages_to_delete:
            try:
                await message.delete()
            except Exception as e:
                self.logger.warning(f"Failed to delete message: {e}")
        song.messages_to_delete = []

    async def update_curr_song_message(self):
        song = self.current_song

        if song:
            self.logger.debug(f"Updating message for song: {song.title}")
            song.current_seconds += 2
            embed = song.to_embed(self.songs, self.shuffle, self.loop)
            if song.embed_message:
                try:
                    await song.embed_message.edit(embed=embed)
                    self.logger.debug(f"Message updated for song {song.title}")
                except Exception as e:
                    self.logger.warning(
                        f"Exception while updating message for song: {song.title} - {e}"
                    )

    async def update_message(self):
        self.logger.info(f"Updating existing playlist message")
        if not self.sent_message:
            self.logger.warning(f"Cannot update playlist message, not found.")
            return
        try:
            updated_embed = self.get_embed()
            await self.sent_message.edit(embed=updated_embed)
        except Exception as e:
            self.logger.warning(f"Exception while updating playlist message: {e}")

    def get_embed(self) -> discord.Embed:
        dl_queue = self.music.downloader.queue
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
                description += f"and more...\n"
                break

        if dl_queue:
            description += f"**{len(dl_queue)}** more in the download queue."
        embed.description = description

        self.logger.info(f"Embed generated for playlist")
        return embed

    async def send_song_embed(self, song: Song) -> Optional[Message]:
        self.logger.info(f"Sending embed for song {song.title}")
        embed = song.to_embed(self.songs, self.shuffle)
        try:
            msg = await song.message.channel.send(embed=embed)
            song.embed_message = msg
            self.logger.info(f"Embed sent for song: {song.title}")
            return msg
        except Exception as e:
            self.logger.warning(
                f"Exception while sending embed for song: {song.title} - {e}"
            )
            return None

    async def clear(self):
        self.logger.info("Clearing the playlist")
        await self.clear_last()
        self.songs = []
        self.current_song = None
        self.last_song = None
        self.logger.info("Playlist cleared")
