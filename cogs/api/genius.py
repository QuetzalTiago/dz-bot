import html
import logging
import re

from bs4 import BeautifulSoup

from cogs.utils.endpoints import GENIUS_BASE_URL
from cogs.utils.http import get_session, get_text

logger = logging.getLogger("discord")


class GeniusAPI:
    def __init__(self, config):
        self.base_url = GENIUS_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {config['secrets'].get('geniusApiKey')}"
        }

    async def fetch_lyrics(self, song_name):
        if "/playlist/" in song_name or "list=" in song_name:
            return None

        query = song_name.split("(")[0]
        try:
            session = get_session()
            async with session.get(
                f"{self.base_url}/search",
                params={"q": query},
                headers=self.headers,
            ) as response:
                if response.status != 200:
                    logger.warning("Genius search returned %s", response.status)
                    return None
                data = await response.json()

            hits = data.get("response", {}).get("hits", [])
            if not hits:
                return None

            song_url = hits[0]["result"]["url"]
            page_text = await get_text(song_url)
            return self.format_lyrics(BeautifulSoup(page_text, "html.parser"))
        except Exception:
            logger.exception("Failed to fetch lyrics for %s", song_name)
            return None

    def format_lyrics(self, html_content):
        for h in html_content("script"):
            h.extract()

        lyrics = ""
        lyrics_divs = html_content.find_all("div", {"data-lyrics-container": "true"})
        if not lyrics_divs:
            # Genius changed its markup if this ever happens; surface it in logs
            # rather than silently returning empty lyrics.
            logger.warning("No lyrics containers found; Genius markup may have changed.")
            return None

        for div in lyrics_divs:
            lyrics += div.get_text(separator="\n") + "\n\n"

        lyrics = html.unescape(lyrics)
        lyrics = re.sub(r"([&\(])\n", r"\1", lyrics)
        lyrics = re.sub(r"\n(\))", r"\1", lyrics)
        lyrics = re.sub(r"(\])", r"\1\n", lyrics)
        lyrics = re.sub(r"(\[)", r"\n\1", lyrics)
        return lyrics
