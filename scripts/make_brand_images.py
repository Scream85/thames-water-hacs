"""Draw the integration's icon into custom_components/thames_water_meter/brand/.

Home Assistant 2026.3 and later show images from a `brand/` folder inside a custom
integration. The icon is original artwork (a water drop on a blue disc), not a Thames
Water or Home Assistant logo, which custom integrations must not imitate.

    .venv/bin/python scripts/make_brand_images.py

Needs Pillow, which Home Assistant brings with it.
"""

from __future__ import annotations

import math
import pathlib

from PIL import Image, ImageDraw

BRAND_DIR = (
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components"
    / "thames_water_meter"
    / "brand"
)
SUPERSAMPLE = 2048  # drawn large, then shrunk, for smooth edges
DISC = (25, 118, 210, 255)
DROP = (255, 255, 255, 255)


def draw_icon() -> Image.Image:
    size = SUPERSAMPLE
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((0, 0, size - 1, size - 1), fill=DISC)

    # A water drop: a circle with a point on top, joined along the two tangent lines.
    cx, cy = size * 0.5, size * 0.60
    radius = size * 0.20
    tip = (cx, size * 0.20)
    distance = cy - tip[1]
    gamma = math.acos(radius / distance)
    left = (cx - radius * math.sin(gamma), cy - radius * math.cos(gamma))
    right = (cx + radius * math.sin(gamma), cy - radius * math.cos(gamma))
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=DROP)
    draw.polygon([tip, left, right], fill=DROP)
    return image


def main() -> None:
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    icon = draw_icon()
    # 256x256 for the normal icon and 512x512 for the hDPI one, as the brands rules ask.
    icon.resize((256, 256), Image.LANCZOS).save(BRAND_DIR / "icon.png", optimize=True)
    icon.resize((512, 512), Image.LANCZOS).save(BRAND_DIR / "icon@2x.png", optimize=True)
    print(f"wrote {BRAND_DIR / 'icon.png'} and icon@2x.png")


if __name__ == "__main__":
    main()
