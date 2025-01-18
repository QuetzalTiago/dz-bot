# test_football_cog.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from discord.ext import commands
import discord
from io import BytesIO
from PIL import Image
import json

# Import the cog
from cogs.football import Football  # Replace 'your_cog_file' with the actual filename where the cog is located.

@pytest.fixture
def bot():
    """Fixture for creating a mock bot instance."""
    return AsyncMock(spec=commands.Bot)

@pytest.fixture
async def cog(bot):
    """Fixture for initializing the Football cog with a mock bot and loading the API key."""
    # Mock the open function to provide the config data
    config_data = {
        "secrets": {
            "apiSportsKey": "test_api_key"
        }
    }
    with patch("builtins.open", mock_open(read_data=json.dumps(config_data))):
        football_cog = Football(bot)
        await football_cog.cog_load()
        return football_cog

def mock_ctx():
    """Helper function to create a mock Discord Context object."""
    ctx = MagicMock(spec=commands.Context)
    ctx.message = MagicMock(spec=discord.Message)
    ctx.message.add_reaction = AsyncMock()
    ctx.message.clear_reactions = AsyncMock()
    ctx.send = AsyncMock()
    ctx.author = MagicMock(spec=discord.Member)
    ctx.channel = MagicMock(spec=discord.TextChannel)
    ctx.guild = MagicMock(spec=discord.Guild)
    return ctx

@pytest.mark.asyncio
async def test_premier_success(cog):
    """Test the premier command for successful execution."""
    ctx = mock_ctx()

    # Mock requests.get to return predefined responses
    with patch("requests.get") as mock_get:
        # Mock the league info response
        mock_league_response = MagicMock()
        mock_league_response.json.return_value = {
            "response": [
                {
                    "league": {
                        "logo": "http://example.com/logo.png"
                    },
                    "seasons": [
                        {"year": 2020},
                        {"year": 2021},
                        {"year": 2022},
                        {"year": 2023},
                    ]
                }
            ]
        }

        # Mock the fixtures response
        mock_fixtures_response = MagicMock()
        mock_fixtures_response.json.return_value = {
            "response": [
                {
                    "fixture": {
                        "date": "2023-10-10T15:00:00+00:00",
                        "venue": {"name": "Anfield"}
                    },
                    "teams": {
                        "home": {"name": "Liverpool"},
                        "away": {"name": "Manchester United"}
                    }
                },
                {
                    "fixture": {
                        "date": "2023-10-11T18:00:00+00:00",
                        "venue": {"name": None}  # Venue name is None
                    },
                    "teams": {
                        "home": {"name": "Chelsea"},
                        "away": {"name": "Arsenal"}
                    }
                },
                {
                    "fixture": {
                        "date": "2023-10-12T20:00:00+00:00",
                        "venue": {"name": "Tottenham Hotspur Stadium"}
                    },
                    "teams": {
                        "home": {"name": "Tottenham"},
                        "away": {"name": "Everton"}
                    }
                },
                # Fixture with non-priority teams (should be filtered out)
                {
                    "fixture": {
                        "date": "2023-10-13T15:00:00+00:00",
                        "venue": {"name": "Stadium"}
                    },
                    "teams": {
                        "home": {"name": "Norwich"},
                        "away": {"name": "Leeds"}
                    }
                },
            ]
        }

        # Setup the side effects of requests.get
        def side_effect(url, headers):
            if 'leagues' in url:
                return mock_league_response
            elif 'fixtures' in url:
                return mock_fixtures_response
            else:
                # For image download
                mock_image_response = MagicMock()
                # Return dummy image bytes
                img = Image.new('RGB', (100, 100))
                img_bytes = BytesIO()
                img.save(img_bytes, format='PNG')
                img_bytes.seek(0)
                mock_image_response.content = img_bytes.read()
                return mock_image_response

        mock_get.side_effect = side_effect

        # Run the command
        await cog.premier(ctx)

        # Assertions
        ctx.message.add_reaction.assert_any_call("⌛")
        ctx.message.clear_reactions.assert_called_once()
        ctx.message.add_reaction.assert_any_call("✅")

        # Ensure that ctx.send was called with an embed and file
        ctx.send.assert_called_once()
        args, kwargs = ctx.send.call_args
        embed = kwargs.get('embed')
        file = kwargs.get('file')
        assert embed is not None
        assert file is not None
        assert isinstance(embed, discord.Embed)
        assert isinstance(file, discord.File)

        # Ensure that the embed has the expected content
        assert embed.title == "Premier League Upcoming Fixtures"
        assert len(embed.fields) > 0  # Ensure fields were added to the embed

@pytest.mark.asyncio
async def test_premier_exception(cog):
    """Test the premier command when an exception occurs."""
    ctx = mock_ctx()

    # Mock requests.get to raise an exception
    with patch("requests.get", side_effect=Exception("API Error")):
        await cog.premier(ctx)

        # Assertions
        ctx.message.add_reaction.assert_any_call("⌛")
        ctx.message.clear_reactions.assert_called_once()
        ctx.message.add_reaction.assert_any_call("✅")

        # Check that an error message was sent
        ctx.send.assert_called_once()
        args, kwargs = ctx.send.call_args
        message = args[0]
        assert "Failed to retrieve Premier League fixtures: API Error" in message

def test_add_white_background(cog):
    """Test the add_white_background method."""
    # Mock requests.get to return image bytes
    with patch("requests.get") as mock_get:
        # Create a dummy image and get its bytes
        img = Image.new('RGBA', (100, 100), color=(255, 0, 0, 255))
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        mock_response = MagicMock()
        mock_response.content = img_bytes.read()
        mock_get.return_value = mock_response

        # Call the method
        result = cog.add_white_background("http://example.com/image.png")

        # Assertions
        assert isinstance(result, BytesIO)
        result.seek(0)
        # Load the image to verify it was processed correctly
        processed_img = Image.open(result)
        assert processed_img.mode == 'RGBA' or processed_img.mode == 'RGB'

def test_get_headers(cog):
    """Test the get_headers method."""
    headers = cog.get_headers()
    assert headers == {
        "x-rapidapi-key": "test_api_key",
        "x-rapidapi-host": "v3.football.api-sports.io",
    }

@pytest.mark.asyncio
async def test_cog_load():
    """Test the cog_load method."""
    bot = AsyncMock(spec=commands.Bot)
    config_data = {
        "secrets": {
            "apiSportsKey": "test_api_key"
        }
    }
    with patch("builtins.open", mock_open(read_data=json.dumps(config_data))):
        football_cog = Football(bot)
        await football_cog.cog_load()
        assert football_cog.api_key == "test_api_key"
