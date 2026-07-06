import pytest
from unittest.mock import AsyncMock, MagicMock

from discord.ext import commands

from cogs.utils.checks import is_owner_or_admin, require_manage_messages


def mock_ctx(is_owner=False, administrator=False, manage_messages=False, guild_permissions=True):
    ctx = MagicMock()
    ctx.bot = MagicMock()
    ctx.bot.is_owner = AsyncMock(return_value=is_owner)
    ctx.author = MagicMock()
    if guild_permissions:
        ctx.author.guild_permissions = MagicMock(
            administrator=administrator, manage_messages=manage_messages
        )
    else:
        del ctx.author.guild_permissions
    return ctx


@pytest.mark.asyncio
async def test_is_owner_or_admin_allows_bot_owner():
    predicate = is_owner_or_admin().predicate
    ctx = mock_ctx(is_owner=True)

    assert await predicate(ctx) is True


@pytest.mark.asyncio
async def test_is_owner_or_admin_allows_guild_administrator():
    predicate = is_owner_or_admin().predicate
    ctx = mock_ctx(is_owner=False, administrator=True)

    assert await predicate(ctx) is True


@pytest.mark.asyncio
async def test_is_owner_or_admin_denies_regular_member():
    predicate = is_owner_or_admin().predicate
    ctx = mock_ctx(is_owner=False, administrator=False)

    with pytest.raises(commands.CheckFailure):
        await predicate(ctx)


@pytest.mark.asyncio
async def test_is_owner_or_admin_denies_when_no_guild_permissions():
    # e.g. a DM context, where ctx.author has no guild_permissions attribute.
    predicate = is_owner_or_admin().predicate
    ctx = mock_ctx(is_owner=False, guild_permissions=False)

    with pytest.raises(commands.CheckFailure):
        await predicate(ctx)


@pytest.mark.asyncio
async def test_require_manage_messages_allows_bot_owner():
    predicate = require_manage_messages().predicate
    ctx = mock_ctx(is_owner=True)

    assert await predicate(ctx) is True


@pytest.mark.asyncio
async def test_require_manage_messages_allows_member_with_permission():
    predicate = require_manage_messages().predicate
    ctx = mock_ctx(is_owner=False, manage_messages=True)

    assert await predicate(ctx) is True


@pytest.mark.asyncio
async def test_require_manage_messages_denies_member_without_permission():
    predicate = require_manage_messages().predicate
    ctx = mock_ctx(is_owner=False, manage_messages=False)

    with pytest.raises(commands.CheckFailure):
        await predicate(ctx)
