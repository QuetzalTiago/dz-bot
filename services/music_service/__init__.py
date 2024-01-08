import os
import discord
import asyncio
import time

from services.file_service import FileService
from services.music_service.song import Song


class MusicService:
    def __init__(self, client):
        self.client = client
        self.queue = []
        self.current_song = None
        self.voice_client = None
        self.loop = False
        self.file_service = FileService()
        self.last_song = None
        self.disconnect_timer = None

    async def initialize(self):
        self.client.loop.create_task(self.background_task())
        print("Music service initialized.")

    async def background_task(self):
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            if not self.is_playing() and not self.file_service.is_downloading():
                if self.last_song and self.last_song.message:
                    await self.delete_song_log(self.last_song.message_to_delete)
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
                    elif time.time() - self.disconnect_timer >= 30:
                        await self.stop()
                        self.disconnect_timer = None
                else:
                    self.disconnect_timer = None

            if self.voice_client and self.voice_client.channel:
                members_in_channel = len(self.voice_client.channel.members)
                if members_in_channel == 1:
                    await self.stop()

            await asyncio.sleep(1)

    async def delete_song_log(self, message):
        try:
            await message.delete()
        except discord.NotFound:
            pass
        except discord.HTTPException:
            print("Failed to delete the song log message.")

    async def join_voice_channel(self, message):
        voice_channel = message.author.voice.channel
        try:
            self.voice_client = await voice_channel.connect()
        except:
            pass

        return self.voice_client

    async def add_to_queue(self, song_path, song_info, message):
        song = Song(song_path, song_info, message)
        self.queue.append(song)
        self.disconnect_timer = None  # Reset timer when a new song is added

    async def play_song(self, song, silent=False):
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
            song.message_to_delete = msg

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
            queue_info += f"{index}. **{song.title}** \n"

        return queue_info

    async def stop(self, message=None):
        if self.last_song and self.last_song.message_to_delete:
            await self.delete_song_log(self.last_song.message_to_delete)

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
        self.queue = []
        await message.channel.send("Queue has been cleared!")

    async def toggle_loop(self):
        self.loop = not self.loop
        return "on" if self.loop else "off"
