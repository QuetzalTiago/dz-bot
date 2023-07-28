import os
import discord
import asyncio
from youtube_search import YoutubeSearch
import yt_dlp
import json
import requests
import spotipy
import datetime as datetimedelta
from spotipy.oauth2 import SpotifyClientCredentials
import uuid
import random
from datetime import datetime

# Get credentials
with open("config.json") as f:
    config = json.load(f)

# Discord token
token = config["secrets"]["discordToken"]

spotify = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=config["secrets"]["spotifyClientId"],
        client_secret=config["secrets"]["spotifyClientSecret"],
    )
)

max_video_duration = 750


class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.voice_client = None
        self.queue = []
        self.song_loop = False
        self.shuffle = False

    async def join_voice_channel(self, message):
        # Get the voice channel that the user is in
        voice_channel = message.author.voice.channel

        # Join the voice channel
        self.voice_client = await voice_channel.connect()

    async def play_music(self, message, song_name, song_id):
        async def play_song(info):
            duration = info["duration"]
            duration_readable = str(datetimedelta.timedelta(seconds=duration))

            filename = f"{song_id}.mp3"

            for file_name in os.listdir("."):
                if file_name.endswith(".mp3") and filename not in file_name:
                    os.remove(file_name)

            # Get the audio stream for the song
            source = discord.FFmpegPCMAudio(filename)

            # Play the song in the voice channel
            self.voice_client.play(source)

            # Send a message with song information
            await message.channel.send(
                f"Now playing: **{info['title']}** as requested by <@{message.author.id}> \n"
                f"Views: **{'{:,}'.format(info['view_count'])}** \n"
                f"Duration: **{duration_readable}**"
            )

        # Check if the bot is already playing music
        if self.voice_client.is_playing():
            self.queue.append(
                {
                    "message": message,
                    "song_name": song_name,
                    "song_id": song_id,
                }
            )
            await message.channel.send("Song added to the queue.")
            return

        await message.channel.send(f"Downloading song...")

        # Create a YTDL downloader
        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "96",
                },
            ],
            "outtmpl": f"{song_id}",
            "noplaylist": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if "youtube.com" in song_name or "youtu.be" in song_name:
                    info = ydl.extract_info(song_name, download=False)

                    if info["duration"] > max_video_duration:
                        await message.channel.send(
                            "The video is too long. Try another query."
                        )
                        duration_readable = str(
                            datetimedelta.timedelta(seconds=info["duration"])
                        )
                        max_duration_readable = str(
                            datetimedelta.timedelta(seconds=max_video_duration)
                        )
                        await message.channel.send(
                            f"Video duration: **{duration_readable}**"
                        )
                        await message.channel.send(
                            f"Max duration is: **{max_duration_readable}**"
                        )
                        return

                    info = ydl.extract_info(song_name, download=True)

                    await play_song(info)

                else:
                    results = json.loads(
                        YoutubeSearch(song_name, max_results=5).to_json()
                    )

                    url_suffix = results["videos"][0]["url_suffix"]
                    url = f"https://www.youtube.com{url_suffix}"

                    info = ydl.extract_info(url, download=False)

                    if info["duration"] > max_video_duration:
                        await message.channel.send(
                            "The video is too long. Try another query."
                        )
                        duration_readable = str(
                            datetimedelta.timedelta(seconds=info["duration"])
                        )
                        max_duration_readable = str(
                            datetimedelta.timedelta(seconds=max_video_duration)
                        )
                        await message.channel.send(
                            f"Video duration: **{duration_readable}**"
                        )
                        await message.channel.send(
                            f"Max duration is: **{max_duration_readable}**"
                        )
                        return

                    info = ydl.extract_info(url, download=True)

                    await play_song(info)

        except Exception as e:
            self.voice_client.stop()
            await message.channel.send(
                "An error occurred while searching for the video."
            )
            await message.channel.send(f"**Error**: {e}")
            self.voice_client = None
            return

        # Start the timeout loop
        while True:
            await asyncio.sleep(3)
            if not self.voice_client.is_playing():
                if self.queue.__len__() <= 0:
                    await message.channel.send(
                        "Nothing left in the queue... disconnecting."
                    )
                    self.voice_client.stop()
                    await self.voice_client.disconnect()

                    break
                if self.song_loop:
                    next_item = self.queue[0]
                elif self.shuffle:
                    index = random.randrange(len(self.queue))
                    next_item = self.queue.pop(index)
                else:
                    next_item = self.queue.pop(0)

                await self.play_music(
                    next_item["message"],
                    next_item["song_name"],
                    next_item["song_id"],
                )
                break

    async def text_to_emoji(_, text):
        emoji_text = ""
        for char in text:
            char = char.lower()
            if char.isalpha():
                emoji_char = f":regional_indicator_{char}:"
                emoji_text += f"{emoji_char} "
            elif char == "?":
                emoji_text += "❔ "
            elif char == "!":
                emoji_text += "❕ "
            else:
                emoji_text += char + " "
        return emoji_text

    def get_date(self):
        return datetime.today().day

    async def date_checker(self):
        spotify_role_id = 1134271094006755438
        main_channel_id = 378245223853064199

        if self.get_date() == 27:
            channel = client.get_channel(main_channel_id)
            await channel.send(
                f"<@&{spotify_role_id}> PAY UP NIGGA \n https://docs.google.com/spreadsheets/d/1TPG7yqK5DoiZ61HoyZXi2GZMBlJ5O8wdsXiZgt9mWj4/edit?usp=sharing"
            )
            await channel.send("https://tenor.com/view/mc-gregor-pay-up-gif-8865194")

    async def on_ready(self):
        await self.date_checker()
        print("Logged on as", self.user)

    async def on_message(self, message):
        if message.author == self.user:
            return

        if message.content.startswith("play") or message.content.startswith("p "):
            await message.add_reaction("👍")

            # Try to join voice channel
            try:
                await self.join_voice_channel(message)
            except:
                pass

            # Get the song URL / name from the message
            if message.content.startswith("play"):
                song_name = message.content[5:].strip()
            else:
                song_name = message.content[2:].strip()

            if "spotify.com" in message.content:
                spotify_url = song_name
                if "track" in spotify_url:
                    # It's an individual track
                    track_id = spotify_url.split("/")[-1].split("?")[
                        0
                    ]  # extract track_id from URL
                    track = spotify.track(track_id)
                    artist = track["artists"][0]["name"]
                    song_name = track["name"]

                    self.queue.append(
                        {
                            "message": message,
                            "song_name": f"{artist} - {song_name}",
                            "song_id": uuid.uuid4().int,
                        }
                    )

                elif "album" in spotify_url:
                    # It's an album
                    album_id = spotify_url.split("/")[-1].split("?")[0]
                    album = spotify.album(album_id)
                    for track in album["tracks"]["items"]:
                        artist = track["artists"][0]["name"]
                        song_name = track["name"]

                        self.queue.append(
                            {
                                "message": message,
                                "song_name": f"{artist} - {song_name}",
                                "song_id": uuid.uuid4().int,
                            }
                        )

                else:
                    # Assume it's a playlist if it's neither track nor album
                    playlist_url = spotify_url
                    tracks = spotify.playlist_tracks(playlist_url)
                    for track in tracks["items"]:
                        artist = track["track"]["artists"][0]["name"]
                        song_name = track["track"]["name"]

                        self.queue.append(
                            {
                                "message": message,
                                "song_name": f"{artist} - {song_name}",
                                "song_id": uuid.uuid4().int,
                            }
                        )

                if not self.voice_client.is_playing():
                    next_item = self.queue.pop(0)
                    await self.play_music(
                        next_item["message"],
                        next_item["song_name"],
                        next_item["song_id"],
                    )

            else:
                await self.play_music(message, song_name, uuid.uuid4().int)
            if message.author == self.user:
                return

        elif message.content == "help":
            await message.add_reaction("👍")
            help_message = """
        Here are all the commands you can use:
        **play** <song name> or **p** <song name>: Searches for the song on YouTube and plays it in the current voice channel.
        **skip** or **s**: Skips the current song.
        **skip to** <number> or **s to** <number>: Skips to the specified song in the queue.
        **stop**: Stops playing music and leaves the voice channel.
        **queue** or **q**: Displays the current queue of songs.
        **shuffle**: Toggles shuffle mode on or off.
        **loop**: Toggles loop mode on or off. (Must be activated before playing the song)
        **clear**: Clears the current queue of songs.
        **chess**: Creates an open chess challenge on Lichess.
        **btc**: Returns the current price of Bitcoin.
        **emoji** <text>: Converts the input text into emoji letters.
        **purge**: Clears all messages.
                """
            await message.channel.send(help_message)

        elif message.content == "skip" or message.content == "s":
            await message.add_reaction("👍")
            if self.voice_client.is_playing():
                await message.channel.send("Skipping...")
                self.voice_client.stop()

        elif message.content.startswith("skip to") or message.content.startswith(
            "s to"
        ):
            await message.add_reaction("👍")
            if self.voice_client.is_playing():
                index = int(message.content.split("to")[1])
                await message.channel.send(f"Skipping to song {index + 1}")
                self.queue = self.queue[index:]
                await message.channel.send(f"The queue has been updated.")
                self.voice_client.stop()

        elif message.content == "stop":
            await message.add_reaction("👍")
            if self.voice_client and self.voice_client.is_connected():
                self.voice_client.stop()
                await self.voice_client.disconnect()

        elif message.content == "loop":
            await message.add_reaction("👍")
            self.song_loop = not self.song_loop
            await message.channel.send(f"Loop is now set on **{self.song_loop}**")

        elif message.content == "queue" or message.content == "q":
            await message.add_reaction("👍")
            if self.queue.__len__() > 0:
                queue_message = "Current queue:\n"
                for i, item in enumerate(self.queue):
                    queue_message += f"{i+1}. **{item['song_name']}**\n"

                if len(queue_message) <= 2000:
                    await message.channel.send(queue_message)
                else:
                    await message.channel.send("Queue is too long.")
            else:
                await message.channel.send("Queue is empty.")

        elif message.content == "shuffle":
            await message.add_reaction("👍")
            self.shuffle = not self.shuffle
            await message.channel.send(f"Shuffle is now set on **{self.shuffle}**")

        elif message.content == "clear":
            await message.add_reaction("👍")
            self.queue = []
            await message.channel.send(f"Queue cleared.")

        elif message.content.startswith("chess"):
            await message.add_reaction("👍")

            # Get the token from config file
            lichess_token = config["secrets"]["lichessToken"]
            headers = {"Authorization": "Bearer " + lichess_token}

            time_control = None

            # Get all the words in the message
            message_parts = message.content.split(" ")

            # Check if there's a second part, and if it can be converted to an integer
            if len(message_parts) > 1:
                try:
                    time_control = int(message_parts[2])
                    if not 30 <= time_control <= 3600:  # time in seconds
                        raise ValueError
                except ValueError:
                    await message.channel.send(
                        "Invalid time control. Please specify a number of seconds between 30 and 3600."
                    )
                    return

            payload = {}
            if time_control is not None:
                # Set the time control
                payload["clock"] = {
                    "limit": time_control,
                    "increment": 0,
                }  # No increment

            response = requests.post(
                "https://lichess.org/api/challenge/open", headers=headers, json=payload
            )

            if response.status_code == 200:
                challenge_data = response.json()
                await message.channel.send(challenge_data["challenge"]["url"])
            else:
                await message.channel.send(
                    "There was a problem creating the challenge."
                )
                await message.channel.send(response)

        elif message.content == "btc":
            await message.add_reaction("👍")

            response = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot")
            data = response.json()
            channel_response = f"Current Bitcoin price: **{(format (int(float(data['data']['amount'])), ',d'))} USD**"
            await message.channel.send(channel_response)

        elif message.content.startswith("emoji "):
            await message.add_reaction("👍")
            text = message.content[6:].strip()
            emoji_text = await self.text_to_emoji(text)
            await message.channel.send(emoji_text)

        elif message.content == "purge":
            await message.add_reaction("👍")
            await message.channel.purge(
                limit=100,
                check=lambda m: m.author == self.user
                or m.content.startswith(
                    (
                        "play",
                        "p ",
                        "skip",
                        "s",
                        "stop",
                        "loop",
                        "queue",
                        "q",
                        "shuffle",
                        "clear",
                        "chess",
                        "btc",
                        "emoji ",
                        "help",
                        "purge",
                    )
                ),
            )

        if "apex" in message.content.lower():
            gifs = [
                "https://tenor.com/view/apex-legends-apex-legends-fortnite-dance-apex-legends-funny-dance-apex-legends-dancing-horizon-dancing-gif-24410416",
                "https://tenor.com/view/apex-legends-fortnite-dance-apex-legends-funny-dance-apex-legends-dancing-bloodhound-dancing-gif-24410417",
                "https://tenor.com/view/revenant-fortnite-dance-apex-legends-dance-apex-legends-revenant-apex-legends-funny-apex-legends-dancing-gif-24410413",
                "https://tenor.com/view/apex-legends-fortnite-dance-apex-legends-funny-dance-apex-legends-dancing-bloodhound-dancing-gif-24410419",
                "https://tenor.com/view/apex-legends-pathfinder-apex-mirage-finisher-gif-21867795",
            ]
            index = random.randrange(len(gifs))
            response = gifs[index]
            await message.channel.send(response)


intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
client = MyClient(intents=intents)
client.run(token)
