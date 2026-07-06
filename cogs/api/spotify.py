import asyncio

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials


class SpotifyAPI:
    def __init__(self, config):
        self.spotify = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=config["secrets"].get("spotifyClientId"),
                client_secret=config["secrets"].get("spotifyClientSecret"),
            )
        )

    async def get_track_name(self, track_url):
        track_id = track_url.split("/")[-1].split("?")[0]
        # spotipy is blocking, so keep it off the event loop.
        track = await asyncio.to_thread(self.spotify.track, track_id)
        artist = track["artists"][0]["name"]
        return f"{artist} - {track['name']}"

    async def get_playlist_songs(self, playlist_url):
        playlist_id = playlist_url.split("/")[-1].split("?")[0]
        results = await asyncio.to_thread(self.spotify.playlist_tracks, playlist_id)
        songs = []
        while results:
            for item in results["items"]:
                track = item.get("track")
                if not track:
                    continue
                artist = track["artists"][0]["name"]
                songs.append(f"{artist} - {track['name']}")
            # Follow pagination so playlists over 100 tracks aren't truncated.
            if results.get("next"):
                results = await asyncio.to_thread(self.spotify.next, results)
            else:
                break
        return songs

    async def get_album_songs(self, album_url):
        album_id = album_url.split("/")[-1].split("?")[0]
        results = await asyncio.to_thread(self.spotify.album_tracks, album_id)
        songs = []
        while results:
            for item in results["items"]:
                artist = item["artists"][0]["name"]
                songs.append(f"{artist} - {item['name']}")
            if results.get("next"):
                results = await asyncio.to_thread(self.spotify.next, results)
            else:
                break
        return songs
