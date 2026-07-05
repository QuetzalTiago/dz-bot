"""Central registry of third-party API base URLs used across cogs.

Keeping these in one place means a provider's URL only needs to change in a
single spot, and makes it easy to see every external service the bot talks to.
"""

COINBASE_BTC_SPOT_URL = "https://api.coinbase.com/v2/prices/BTC-USD/spot"

OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"

POE_NINJA_CURRENCY_OVERVIEW_URL = "https://poe.ninja/api/data/currencyoverview"

CEDULA_LOOKUP_BASE_URL = "https://ci-uy.checkleaked.cc"

LICHESS_BASE_URL = "https://lichess.org"
LICHESS_CHALLENGE_OPEN_URL = f"{LICHESS_BASE_URL}/api/challenge/open"

GENIUS_BASE_URL = "https://api.genius.com"

FOOTBALL_API_BASE_URL = "https://v3.football.api-sports.io"

FORMULA1_API_BASE_URL = "https://v1.formula-1.api-sports.io"

MMA_API_BASE_URL = "https://v1.mma.api-sports.io"

STEAM_STORE_API_URL = "https://store.steampowered.com/api"
STEAM_STORE_URL = "https://store.steampowered.com"
