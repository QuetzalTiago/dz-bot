import os
import discord
import asyncio

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

    async def initialize(self):
        self.client.loop.create_task(self.background_task())
        print("Music service initialized.")

    async def background_task(self):
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            if not self.is_playing() and not self.file_service.is_downloading():
                if self.loop and self.current_song:
                    await self.play_song(self.current_song, True)
                elif self.queue:
                    next_song = self.queue.pop(0)
                    await self.play_song(next_song)
                elif self.voice_client and self.voice_client.is_connected():
                    await self.voice_client.disconnect()
            await asyncio.sleep(1)

    async def join_voice_channel(self, message):
        voice_channel = message.author.voice.channel
        try:
            self.voice_client = await voice_channel.connect()
        except:
            pass

    async def add_to_queue(self, song_path, song_info, message):
        song = Song(song_path, song_info, message)
        self.queue.append(song)

        if self.is_playing():
            await message.channel.send(f"**{song.title}** has been added to the queue!")

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
            await song.message.channel.send(
                f"Now playing: **{song.title}** as requested by <@{song.message.author.id}>"
            )

            embed = discord.Embed(title="More info", color=0x3498DB)
            embed.add_field(name="Views", value=f"**{song.views}**", inline=True)
            embed.add_field(name="Duration", value=f"**{song.duration}**", inline=True)

            await song.message.channel.send(embed=embed)

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

    async def stop(self, message):
        if self.voice_client and self.voice_client.is_connected():
            if self.voice_client.is_playing():
                self.voice_client.stop()

            self.queue = []

            if self.voice_client:
                await self.voice_client.disconnect()
        else:
            await message.channel.send("DJ Khaled is not playing anything!")

    async def clear(self, message):
        self.queue = []
        await message.channel.send("Queue has been cleared!")

    async def toggle_loop(self):
        self.loop = not self.loop
        return "on" if self.loop else "off"
