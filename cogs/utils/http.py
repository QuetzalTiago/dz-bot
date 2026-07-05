"""Shared async HTTP client.

Most cogs used the blocking ``requests`` library directly inside async command
handlers, which freezes the entire bot (every guild, the voice heartbeat,
everything) for the duration of each call. This module provides a single
shared :class:`aiohttp.ClientSession` with a sane default timeout so all
network I/O stays off the event loop's critical path.
"""

import logging
from typing import Any, Optional

import aiohttp

logger = logging.getLogger("discord")

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=15)

_session: Optional[aiohttp.ClientSession] = None


def get_session() -> aiohttp.ClientSession:
    """Return the process-wide aiohttp session, creating it on first use."""
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(timeout=DEFAULT_TIMEOUT)
    return _session


async def close_session() -> None:
    """Close the shared session on shutdown."""
    global _session
    if _session is not None and not _session.closed:
        await _session.close()
        _session = None


async def get_json(url: str, **kwargs: Any) -> Any:
    """GET a URL and return parsed JSON, raising for non-2xx responses."""
    session = get_session()
    async with session.get(url, **kwargs) as resp:
        resp.raise_for_status()
        return await resp.json()


async def get_bytes(url: str, **kwargs: Any) -> bytes:
    """GET a URL and return the raw response body."""
    session = get_session()
    async with session.get(url, **kwargs) as resp:
        resp.raise_for_status()
        return await resp.read()


async def get_text(url: str, **kwargs: Any) -> str:
    """GET a URL and return the response body as text."""
    session = get_session()
    async with session.get(url, **kwargs) as resp:
        resp.raise_for_status()
        return await resp.text()
