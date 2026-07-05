"""Small shared presentation helpers used across cogs."""

import datetime

import pytz

# Default display timezone. Previously three separate sports cogs hardcoded
# "America/Montevideo"; keep the same default but in one place so it can later
# become a per-guild setting.
DEFAULT_TIMEZONE = "America/Montevideo"


def to_local(date_str: str, tz_name: str = DEFAULT_TIMEZONE) -> datetime.datetime:
    """Parse an ISO-8601 string with offset and convert to the target tz."""
    utc_time = datetime.datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S%z")
    return utc_time.astimezone(pytz.timezone(tz_name))


def format_local(
    date_str: str, fmt: str = "%Y-%m-%d, %H:%M", tz_name: str = DEFAULT_TIMEZONE
) -> str:
    """Parse and format an ISO-8601 string in the target timezone."""
    return to_local(date_str, tz_name).strftime(fmt)


def split_message(text: str, limit: int = 2000) -> list[str]:
    """Split text into Discord-sized chunks, preferring line boundaries."""
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            # A single line longer than the limit must be hard-split.
            while len(line) > limit:
                chunks.append(line[:limit])
                line = line[limit:]
        current += line
    if current:
        chunks.append(current)
    return chunks
