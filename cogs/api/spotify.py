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

    def _format_track(self, track):
        # Local files embedded in a playlist/album can report an empty
        # "artists" list - a direct [0] index would abort the whole
        # pagination loop (and the entire import) on that one track.
        artists = track.get("artists") or []
        artist = artists[0]["name"] if artists else "Unknown Artist"
        return f"{artist} - {track['name']}"

    async def get_track_name(self, track_url):
        track_id = track_url.split("/")[-1].split("?")[0]
        # spotipy is blocking, so keep it off the event loop.
        track = await asyncio.to_thread(self.spotify.track, track_id)
        return self._format_track(track)

    async def get_playlist_songs(self, playlist_url):
        playlist_id = playlist_url.split("/")[-1].split("?")[0]
        results = await asyncio.to_thread(self.spotify.playlist_tracks, playlist_id)
        songs = []
        while results:
            for item in results["items"]:
                track = item.get("track")
                if not track:
                    continue
                songs.append(self._format_track(track))
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
                songs.append(self._format_track(item))
            if results.get("next"):
                results = await asyncio.to_thread(self.spotify.next, results)
            else:
                break
        return songs
