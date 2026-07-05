"""Image helpers shared by the sports cogs.

Both the download and the PIL processing used to run synchronously on the event
loop. Here the download is async (shared aiohttp session) and the CPU-bound PIL
work is pushed to a worker thread via ``asyncio.to_thread``.
"""

import asyncio
from io import BytesIO

from PIL import Image, ImageOps

from cogs.utils.http import get_bytes


def _white_background(content: bytes) -> BytesIO:
    img = Image.open(BytesIO(content))
    background = Image.new("RGBA", img.size, (255, 255, 255, 255))
    background.paste(img, (0, 0), img)
    img_with_border = ImageOps.expand(background, border=20, fill="white")
    out = BytesIO()
    img_with_border.save(out, format="PNG")
    out.seek(0)
    return out


async def add_white_background(image_url: str) -> BytesIO:
    """Download an image and composite it on a white background (off-loop)."""
    content = await get_bytes(image_url)
    return await asyncio.to_thread(_white_background, content)


def _combine_logos(content1: bytes, content2: bytes, vs_image_path: str) -> BytesIO:
    logo1 = Image.open(BytesIO(content1)).convert("RGBA")
    logo2 = Image.open(BytesIO(content2)).convert("RGBA")

    height = min(logo1.height, logo2.height)
    logo1 = logo1.resize(
        (int(logo1.width * (height / logo1.height)), height), Image.Resampling.LANCZOS
    )
    logo2 = logo2.resize(
        (int(logo2.width * (height / logo2.height)), height), Image.Resampling.LANCZOS
    )

    combined = Image.new("RGBA", (logo1.width + logo2.width, height))
    combined.paste(logo1, (0, 0))
    combined.paste(logo2, (logo1.width, 0))

    vs_image = Image.open(vs_image_path).convert("RGBA")
    vs_aspect = vs_image.width / vs_image.height
    target_width = combined.width
    target_height = int(target_width / vs_aspect)
    if target_height > combined.height:
        target_height = combined.height
        target_width = int(target_height * vs_aspect)
    vs_image = vs_image.resize((target_width, target_height), Image.Resampling.LANCZOS)

    position = (
        (combined.width - target_width) // 2,
        (combined.height - target_height) // 2,
    )
    combined.paste(vs_image, position, vs_image)

    out = BytesIO()
    combined.save(out, format="PNG")
    out.seek(0)
    return out


async def combine_fighter_logos(
    logo_url1: str, logo_url2: str, vs_image_path: str
) -> BytesIO:
    """Download two logos and composite them side by side with a VS overlay."""
    content1 = await get_bytes(logo_url1)
    content2 = await get_bytes(logo_url2)
    return await asyncio.to_thread(
        _combine_logos, content1, content2, vs_image_path
    )
