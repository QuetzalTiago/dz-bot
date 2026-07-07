from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from cogs.utils.images import add_white_background, combine_fighter_logos


def _encode(mode, fmt):
    img = Image.new(mode, (10, 10), (255, 0, 0) if mode != "P" else 0)
    out = BytesIO()
    img.save(out, format=fmt)
    return out.getvalue()


@pytest.mark.asyncio
async def test_add_white_background_handles_non_alpha_jpeg():
    # Regression test: a JPEG (mode "RGB", no alpha channel) used to be passed
    # as its own paste mask, raising "ValueError: bad transparency mask".
    jpeg_bytes = _encode("RGB", "JPEG")
    with patch(
        "cogs.utils.images.get_bytes", new=AsyncMock(return_value=jpeg_bytes)
    ):
        result = await add_white_background("http://example.com/logo.jpg")

    out_img = Image.open(result)
    assert out_img.format == "PNG"


@pytest.mark.asyncio
async def test_add_white_background_handles_rgba_png():
    png_bytes = _encode("RGBA", "PNG")
    with patch(
        "cogs.utils.images.get_bytes", new=AsyncMock(return_value=png_bytes)
    ):
        result = await add_white_background("http://example.com/logo.png")

    out_img = Image.open(result)
    assert out_img.format == "PNG"


@pytest.mark.asyncio
async def test_combine_fighter_logos_composites_both(tmp_path):
    logo1 = _encode("RGBA", "PNG")
    logo2 = _encode("RGBA", "PNG")
    vs_path = tmp_path / "vs.png"
    Image.new("RGBA", (20, 10), (0, 0, 0, 255)).save(vs_path, format="PNG")

    with patch(
        "cogs.utils.images.get_bytes", new=AsyncMock(side_effect=[logo1, logo2])
    ):
        result = await combine_fighter_logos(
            "http://example.com/1.png", "http://example.com/2.png", str(vs_path)
        )

    out_img = Image.open(result)
    assert out_img.format == "PNG"
    assert out_img.width == 20


@pytest.mark.asyncio
async def test_combine_fighter_logos_shrinks_tall_vs_image(tmp_path):
    # combined is 20x10 (aspect 2.0); a square vs image (aspect 1.0) would
    # naively scale to 20x20, taller than combined - it must be shrunk to fit
    # combined's height instead of overflowing it.
    logo1 = _encode("RGBA", "PNG")
    logo2 = _encode("RGBA", "PNG")
    vs_path = tmp_path / "vs.png"
    Image.new("RGBA", (20, 20), (0, 0, 0, 255)).save(vs_path, format="PNG")

    with patch(
        "cogs.utils.images.get_bytes", new=AsyncMock(side_effect=[logo1, logo2])
    ):
        result = await combine_fighter_logos(
            "http://example.com/1.png", "http://example.com/2.png", str(vs_path)
        )

    out_img = Image.open(result)
    assert out_img.size == (20, 10)
