import requests
import html
import re
from bs4 import BeautifulSoup


class GeniusAPI:
    def __init__(self, config):
        self.base_url = "https://api.genius.com"
        self.headers = {
            "Authorization": f"Bearer {config['secrets']['genius_api_key']}"
        }

    async def fetch_lyrics(self, song_name):
        if "/playlist/" in song_name or "list=" in song_name:
            return None

        query = song_name.split("(")[0]
        search_url = f"{self.base_url}/search?q={query}"
        response = requests.get(search_url, headers=self.headers)
        json = response.json()

        if not json["response"]["hits"]:
            return None

        song_url = json["response"]["hits"][0]["result"]["url"]

        page = requests.get(song_url)
        html_content = BeautifulSoup(page.text, "html.parser")

        return self.format_lyrics(html_content)

    def format_lyrics(self, html_content):
        [h.extract() for h in html_content("script")]

        lyrics = ""
        lyrics_divs = html_content.find_all("div", {"data-lyrics-container": "true"})
        for div in lyrics_divs:
            lyrics += div.get_text(separator="\n") + "\n\n"

        lyrics = html.unescape(lyrics)
        lyrics = re.sub(r"([&\(])\n", r"\1", lyrics)
        lyrics = re.sub(r"\n(\))", r"\1", lyrics)
        lyrics = re.sub(r"(\])", r"\1\n", lyrics)
        lyrics = re.sub(r"(\[)", r"\n\1", lyrics)

        return lyrics
