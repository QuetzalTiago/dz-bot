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
import pytz

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
        self.search_results = []
        self.main_channel_id = 378245223853064199

    async def join_voice_channel(self, message):
        # Get the voice channel that the user is in
        voice_channel = message.author.voice.channel

        # Join the voice channel
        self.voice_client = await voice_channel.connect()

    async def time_checker(self):
        channel = self.get_channel(self.main_channel_id)
        spotify_role_id = 1134271094006755438
        while True:
            now = datetime.now(pytz.timezone("Etc/GMT+3"))
            if (now.hour == 4 or now.hour == 16) and now.minute == 20:
                gifs = [
                    "https://tenor.com/qBaO.gif",
                    "https://tenor.com/bUc6T.gif",
                    "https://tenor.com/bWGTx.gif",
                    "https://tenor.com/7M09.gif",
                    "https://tenor.com/bEZC5.gif",
                    "https://tenor.com/bDYTg.gif",
                ]
                index = random.randrange(len(gifs))
                response = gifs[index]
                await channel.send(":four: :two: :zero: ")
                await channel.send(response)
                await asyncio.sleep(60)
            if now.day == 27 and now.hour == 20 and now.minute == 0:
                await channel.send(
                    f"<@&{spotify_role_id}> PAY UP NIGGA \n https://docs.google.com/spreadsheets/d/1TPG7yqK5DoiZ61HoyZXi2GZMBlJ5O8wdsXiZgt9mWj4/edit?usp=sharing"
                )
                await channel.send(
                    "https://tenor.com/view/mc-gregor-pay-up-gif-8865194"
                )
                await asyncio.sleep(60)
            await asyncio.sleep(10)

    async def on_ready(self):
        await self.time_checker()
        print("Logged on as", self.user)

    async def play_music(self, message, song_name, song_id):
        async def play_song(info):
            try:
                await self.join_voice_channel(message)
            except:
                pass

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

            # Delete 'Downloading...' message
            await message.channel.purge(
                limit=1,
                check=lambda m: m.author == self.user
                and m.content.startswith("Downloading"),
            )

            # Send a message with song information
            await message.channel.send(
                f"Now playing: **{info['title']}** as requested by <@{message.author.id}> \n"
                f"Views: **{'{:,}'.format(info['view_count'])}** \n"
                f"Duration: **{duration_readable}**"
            )

        # Check if the bot is already playing music
        if self.voice_client and self.voice_client.is_playing():
            self.queue.append(
                {
                    "message": message,
                    "song_name": song_name,
                    "song_id": song_id,
                }
            )
            if "youtube.com" in song_name or "youtu.be" in song_name:
                await message.channel.send("Song added to the queue.")
            else:
                await message.channel.send(f"**{song_name}** added to the queue.")
            return

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

                async def download(query):
                    info = ydl.extract_info(query, download=False)

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

                    await message.channel.send(f"Downloading **{info['title']}**...")

                    info = ydl.extract_info(query, download=True)

                    await play_song(info)

                if "youtube.com" in song_name or "youtu.be" in song_name:
                    await download(song_name)
                else:
                    results = json.loads(
                        YoutubeSearch(song_name, max_results=5).to_json()
                    )

                    url_suffix = results["videos"][0]["url_suffix"]
                    url = f"https://www.youtube.com{url_suffix}"

                    await download(url)

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

    async def on_message(self, message):
        lowerMessageContent = message.content.lower()

        if message.author == self.user:
            return

        if self.search_results:
            try:
                choice = int(lowerMessageContent.strip())
                if choice >= 1 and choice <= len(self.search_results) + 1:
                    chosen_query = self.search_results[choice - 1]
                    self.search_results.clear()
                    await self.play_music(message, chosen_query, uuid.uuid4().int)
                    await message.channel.purge(
                        limit=3,
                        check=lambda m: m.author == self.user and m.content.isdigit(),
                    )
                else:
                    await message.channel.send(
                        f"Please select a valid number between 1 and {len(self.search_results) + 1} and search again."
                    )
                    self.search_results.clear()
            except:
                await message.channel.send(
                    "Please send a valid number corresponding to a search result and search again."
                )
                self.search_results.clear()

        if lowerMessageContent.startswith("play") or lowerMessageContent.startswith(
            "p "
        ):
            await message.add_reaction("👍")

            if lowerMessageContent.startswith("play"):
                song_name = lowerMessageContent[5:].strip()
            else:
                song_name = lowerMessageContent[2:].strip()

            if "spotify.com" in lowerMessageContent:
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

        elif lowerMessageContent.startswith(
            "search "
        ) or lowerMessageContent.startswith("ps "):
            await message.add_reaction("👍")

            if lowerMessageContent.startswith("search "):
                song_name = lowerMessageContent[7:].strip()
            else:
                song_name = lowerMessageContent[3:].strip()
            results = json.loads(YoutubeSearch(song_name, max_results=10).to_json())

            embed = discord.Embed(
                title=f"Search results for '{song_name}'", color=0x0062FF
            )

            for index, video in enumerate(results["videos"], 1):
                url_suffix = video["url_suffix"]
                url = f"https://www.youtube.com{url_suffix}"

                self.search_results.append(url)
                embed.add_field(
                    name=f"{index}. {video['title']}",
                    value=f"Views: **{video['views'].split(' ')[0]}**\nDuration: **{video['duration']}**",
                    inline=False,
                )

            await message.channel.send(embed=embed)

        elif lowerMessageContent == "help":
            await message.add_reaction("👍")
            help_message = """
        Here are all the commands you can use:
        **play** <song name> or **p** <song name>: Searches for the song on YouTube and plays it in the current voice channel.
        **search** <song name> or **ps** <song name>: Searches first 10 results and lets you choose which one.
        **skip** or **s**: Skips the current song.
        **skip to** <number> or **s to** <number>: Skips to the specified song in the queue.
        **stop**: Stops playing music and leaves the voice channel.
        **queue** or **q**: Displays the current queue of songs.
        **shuffle**: Toggles shuffle mode on or off.
        **loop**: Toggles loop mode on or off. (Must be activated before playing the song)
        **clear**: Clears the current queue of songs.
        **chess** <time (in minutes)>: Creates an open chess challenge on Lichess.
        **btc**: Returns the current price of Bitcoin.
        **emoji** <text>: Converts the input text into emoji letters.
        **purge**: Clears all messages.
                """
            await message.channel.send(help_message)

        elif lowerMessageContent == "skip" or lowerMessageContent == "s":
            await message.add_reaction("👍")
            if self.voice_client.is_playing():
                await message.channel.send("Skipping...")
                self.voice_client.stop()

        elif lowerMessageContent.startswith(
            "skip to"
        ) or lowerMessageContent.startswith("s to"):
            await message.add_reaction("👍")
            if self.voice_client.is_playing():
                index = int(lowerMessageContent.split("to")[1])
                await message.channel.send(f"Skipping to song #{index}")
                self.queue = self.queue[index - 1 :]
                await message.channel.send(f"The queue has been updated.")
                self.voice_client.stop()

        elif lowerMessageContent == "stop":
            await message.add_reaction("👍")
            if self.voice_client and self.voice_client.is_connected():
                self.voice_client.stop()
                self.queue = []
                await self.voice_client.disconnect()

        elif lowerMessageContent == "loop":
            await message.add_reaction("👍")
            self.song_loop = not self.song_loop
            await message.channel.send(f"Loop is now set on **{self.song_loop}**")

        elif lowerMessageContent == "queue" or lowerMessageContent == "q":
            await message.add_reaction("👍")

            if len(self.queue) > 0:
                try:
                    embed = discord.Embed(color=0x0062FF)

                    for i, item in enumerate(self.queue):
                        embed.add_field(
                            name=f"**{i+1}. {item['song_name']}**",
                            value="",
                            inline=False,
                        )

                    await message.channel.send(embed=embed)
                except Exception as e:
                    await message.channel.send("Error displaying the queue.")
                    await message.channel.send(f"**Error**: {e}")
            else:
                await message.channel.send("Queue is empty.")

        elif lowerMessageContent == "shuffle":
            await message.add_reaction("👍")
            self.shuffle = not self.shuffle
            await message.channel.send(f"Shuffle is now set on **{self.shuffle}**")

        elif lowerMessageContent == "clear":
            await message.add_reaction("👍")
            self.queue = []
            await message.channel.send(f"Queue cleared.")

        elif lowerMessageContent.startswith("chess"):
            await message.add_reaction("👍")

            lichess_token = config["secrets"]["lichessToken"]
            headers = {"Authorization": "Bearer " + lichess_token}

            time_control = None

            message_parts = lowerMessageContent.split(" ")

            if len(message_parts) > 1:
                time_control = int(message_parts[1])
                if time_control < 1 or time_control > 60:
                    await message.channel.send(
                        "Invalid time control. Please specify a number of minutes between 1 and 60."
                    )
                    return

            payload = {}
            if time_control is not None:
                payload["clock"] = {
                    "increment": 2,
                    "limit": time_control * 60,
                }

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

        elif lowerMessageContent == "btc":
            await message.add_reaction("👍")

            response = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot")
            data = response.json()
            channel_response = f"Current Bitcoin price: **{(format (int(float(data['data']['amount'])), ',d'))} USD**"
            await message.channel.send(channel_response)

        elif lowerMessageContent.startswith("emoji "):
            await message.add_reaction("👍")
            text = lowerMessageContent[6:].strip()
            emoji_text = await self.text_to_emoji(text)
            await message.channel.send(emoji_text)

        elif lowerMessageContent == "purge":
            await message.add_reaction("👍")
            await message.channel.send("Purging messages...")
            await message.channel.purge(
                limit=100,
                check=lambda m: m.author == self.user
                or m.content.lower() == "s"
                or m.content.lower() == "skip"
                or m.content.lower() == "stop"
                or m.content.lower() == "loop"
                or m.content.lower() == "q"
                or m.content.lower() == "shuffle"
                or m.content.lower() == "clear"
                or m.content.lower() == "queue"
                or m.content.lower() == "chess"
                or m.content.lower() == "btc"
                or m.content.lower() == "help"
                or m.content.lower() == "purge"
                or m.content.lower().isdigit()
                or m.content.lower().startswith(
                    (
                        "play ",
                        "p ",
                        "search ",
                        "ps ",
                        "chess ",
                        "emoji ",
                        "s to ",
                        "skip to ",
                    )
                ),
            )

        if "apex" in lowerMessageContent:
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
