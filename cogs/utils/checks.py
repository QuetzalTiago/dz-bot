"""Authorization helpers for privileged commands.

The bot previously shipped several destructive commands (``restart``,
``purge``) with no permission checks at all — any user in any guild could run
them. These decorators gate such commands behind Discord permissions or the
bot owner(s).

Bot owners can be configured via the ``owners`` list in ``config.json`` (or the
``DZ_OWNERS`` env var, comma-separated user IDs); otherwise discord.py falls
back to the application owner reported by the Discord API.
"""

from discord.ext import commands


def is_owner_or_admin():
    """Allow the command only for the bot owner or a guild administrator."""

    async def predicate(ctx: commands.Context) -> bool:
        if await ctx.bot.is_owner(ctx.author):
            return True
        perms = getattr(ctx.author, "guild_permissions", None)
        if perms is not None and perms.administrator:
            return True
        raise commands.CheckFailure(
            "You need to be the bot owner or a server administrator to use this command."
        )

    return commands.check(predicate)


def require_manage_messages():
    """Allow the command only for members who can manage messages."""

    async def predicate(ctx: commands.Context) -> bool:
        if await ctx.bot.is_owner(ctx.author):
            return True
        perms = getattr(ctx.author, "guild_permissions", None)
        if perms is not None and perms.manage_messages:
            return True
        raise commands.CheckFailure(
            "You need the Manage Messages permission to use this command."
        )

    return commands.check(predicate)
