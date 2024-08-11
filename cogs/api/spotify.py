import spotipy
from spotipy.oauth2 import SpotifyClientCredentials


class SpotifyAPI:
    def __init__(self, config):
        self.spotify = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=config["secrets"]["spotifyClientId"],
                client_secret=config["secrets"]["spotifyClientSecret"],
            )
        )

    async def get_track_name(self, track_url):
        track_id = track_url.split("/")[-1].split("?")[0]
        track = self.spotify.track(track_id)

        artist = track["artists"][0]["name"]
        song_name = track["name"]

        return f"{artist} - {song_name}"

    async def get_playlist_songs(self, playlist_url):
        playlist_id = playlist_url.split("/")[-1].split("?")[0]
        results = self.spotify.playlist_tracks(playlist_id)
        songs = []
        for item in results["items"]:
            track = item["track"]
            artist = track["artists"][0]["name"]
            song_name = track["name"]
            songs.append(f"{artist} - {song_name}")

        return songs

    async def get_album_songs(self, album_url):
        album_id = album_url.split("/")[-1].split("?")[0]
        results = self.spotify.album_tracks(album_id)
        songs = []

        for item in results["items"]:
            artist = item["artists"][0]["name"]
            song_name = item["name"]
            songs.append(f"{artist} - {song_name}")

        return songs
