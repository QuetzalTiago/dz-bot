import datetime
import os
import discord

from services.file_service import FileService


class MusicService:
    def __init__(self, client):
        self.client = client
        self.queue = []
        self.current_song = None
        self.voice_client = None
        self.loop = False
        self.file_service = FileService()

    async def join_voice_channel(self, message):
        voice_channel = message.author.voice.channel

        try:
            self.voice_client = await voice_channel.connect()
        except:
            pass

    async def add_to_queue(self, song_path, song_info, message):
        self.queue.append((song_path, song_info, message))

        if self.is_playing():
            await message.channel.send(
                f"**{song_info['title']}** has been added to the queue!"
            )
        else:
            await self.play_next_song()

    async def play_song(self, song_path, song_info, message):
        for file_name in os.listdir("."):
            if (
                file_name.endswith(".mp3")
                and file_name not in [item[0] for item in self.queue]
                and file_name != song_path
            ):
                self.file_service.delete_file(file_name)

        source = discord.FFmpegPCMAudio(song_path)

        self.voice_client.play(source, after=self.after_song_played)
        self.current_song = song_path

        duration = str(datetime.timedelta(seconds=song_info["duration"]))
        views = "{:,}".format(song_info["view_count"])
        title = song_info["title"]

        await message.channel.send(
            f"Now playing: **{title}** as requested by <@{message.author.id}> \n"
            f"Views: **{views}** \n"
            f"Duration: **{duration}**"
        )

    def after_song_played(self, error):
        if error:
            print(f"Error in playback: {error}")
        if not self.loop:  # Check if loop is False
            self.file_service.delete_file(self.current_song)
            self.client.loop.create_task(self.play_next_song())
        else:
            self.client.loop.create_task(self.play_song(self.current_song))

    async def play_next_song(self):
        if self.queue:
            next_song = self.queue.pop(0)

            path, info, message = next_song
            await self.play_song(path, info, message)
        else:
            self.current_song = None
            if self.voice_client:
                await self.voice_client.disconnect()

    def is_playing(self):
        return self.voice_client and self.voice_client.is_playing()

    async def skip_song(self):
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()

    async def toggle_loop(self):
        self.loop = not self.loop
        return self.loop

    def get_queue_info(self):
        if not self.queue:
            return "The queue is empty."

        queue_info = "Current Queue:\n"
        for index, (path, info, message) in enumerate(self.queue, 1):
            title = info["title"]

            queue_info += f"{index}. **{title}** \n"

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
