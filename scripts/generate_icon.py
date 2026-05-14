#!/usr/bin/env python3
"""
Icon Generation Script for open-daily-stock
Creates ODS logo with purple-blue gradient

Outputs:
- assets/icon.png (1024x1024)
- assets/icon.icns (macOS)
- assets/icon.ico (Windows)
"""

import math
from PIL import Image, ImageDraw


def lerp_color(color1: tuple, color2: tuple, t: float) -> tuple:
    """Linear interpolate between two colors."""
    return tuple(int(c1 + (c2 - c1) * t) for c1, c2 in zip(color1, color2))


def draw_ods_letter(img: Image.Image, draw: ImageDraw.ImageDraw, center_x: float, center_y: float, size: float, color):
    """Draw ODS letters with stock chart motif inside O."""
    # Purple to blue gradient colors
    purple = (139, 92, 246)   # #8B5CF6
    blue = (59, 130, 246)     # #3B82F6

    # O - outer circle with stock chart line inside
    o_center_x = center_x - size * 0.5
    o_radius = size * 0.35
    # Draw O circle
    bbox = [
        o_center_x - o_radius,
        center_y - o_radius,
        o_center_x + o_radius,
        center_y + o_radius
    ]
    draw.ellipse(bbox, fill=color)

    # Stock chart line inside O (candlestick-like bars)
    chart_height = o_radius * 0.6
    chart_width = o_radius * 0.5
    chart_center_x = o_center_x
    chart_center_y = center_y

    # Draw simplified stock chart bars
    bar_width = chart_width / 5
    bar_colors = [
        lerp_color(purple, blue, 0.2),
        lerp_color(purple, blue, 0.4),
        lerp_color(purple, blue, 0.6),
        lerp_color(purple, blue, 0.8),
        blue
    ]
    bar_heights = [0.4, 0.7, 0.3, 0.9, 0.5]

    for i, (bar_color, bar_h) in enumerate(zip(bar_colors, bar_heights)):
        bar_x = chart_center_x - chart_width/2 + i * bar_width + bar_width/2
        bar_top = chart_center_y - chart_height/2 + chart_height * (1 - bar_h)
        bar_bottom = chart_center_y + chart_height/2

        # Draw small vertical bar
        draw.rectangle(
            [bar_x - bar_width/4, bar_top, bar_x + bar_width/4, bar_bottom],
            fill=(255, 255, 255)
        )

    # D - vertical bar with curve
    d_center_x = center_x + size * 0.0
    d_top = center_y - size * 0.35
    d_bottom = center_y + size * 0.35
    d_width = size * 0.08

    # Vertical bar of D
    draw.rectangle(
        [d_center_x - d_width/2, d_top, d_center_x + d_width/2, d_bottom],
        fill=color
    )

    # Curve of D (as an arc on the right side)
    curve_bbox = [
        d_center_x - d_width/2,
        d_top,
        d_center_x + size * 0.25,
        d_bottom
    ]
    draw.arc(curve_bbox, start=270, end=90, fill=color, width=int(d_width))

    # S - S shape (drawn as two arcs and a connecting segment)
    s_center_x = center_x + size * 0.5
    s_radius = size * 0.2

    # Top arc of S
    top_arc_bbox = [
        s_center_x - s_radius,
        center_y - size * 0.35,
        s_center_x + s_radius,
        center_y - size * 0.05
    ]
    draw.arc(top_arc_bbox, start=180, end=0, fill=color, width=int(size * 0.08))

    # Bottom arc of S
    bottom_arc_bbox = [
        s_center_x - s_radius,
        center_y + size * 0.05,
        s_center_x + s_radius,
        center_y + size * 0.35
    ]
    draw.arc(bottom_arc_bbox, start=180, end=0, fill=color, width=int(size * 0.08))

    # Middle connecting segment
    draw.line(
        [s_center_x - s_radius, center_y, s_center_x + s_radius, center_y],
        fill=color,
        width=int(size * 0.08)
    )


def create_icon(size: int = 1024) -> Image.Image:
    """Create a 1024x1024 icon with ODS logo and gradient background."""
    # Create base image with gradient background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.ImageDraw(img)

    purple = (139, 92, 246)   # #8B5CF6
    blue = (59, 130, 246)     # #3B82F6

    # Draw gradient background
    for y in range(size):
        t = y / size
        color = lerp_color(purple, blue, t)
        draw.rectangle([0, y, size, y + 1], fill=color + (255,))

    # Add subtle radial glow in center
    center_x, center_y = size // 2, size // 2
    max_radius = size * 0.4

    for r in range(int(max_radius), 0, -1):
        alpha = int(30 * (1 - r / max_radius))
        bbox = [center_x - r, center_y - r, center_x + r, center_y + r]
        draw.ellipse(bbox, fill=(255, 255, 255, alpha))

    # Draw ODS letters
    letter_size = size * 0.6
    letter_center_x = size // 2
    letter_center_y = size // 2

    draw_ods_letter(img, draw, letter_center_x, letter_center_y, letter_size, (255, 255, 255, 255))

    return img


def save_as_png(img: Image.Image, path: str) -> None:
    """Save image as PNG."""
    img.save(path, 'PNG')
    print(f"Saved: {path}")


def save_as_icns(img: Image.Image, path: str) -> None:
    """Save as ICNS format for macOS."""
    # ICNS requires icon family with multiple sizes
    # For simplicity, we save as PNG and use iconutil if available, otherwise save as 512x512 PNG
    try:
        # Try using iconutil to convert PNG to ICNS
        import subprocess
        import tempfile
        import os

        # Create a temporary directory for icon set
        with tempfile.TemporaryDirectory() as tmpdir:
            icon_set_dir = os.path.join(tmpdir, 'icon.iconset')
            os.makedirs(icon_set_dir)

            # Save various sizes for icns
            sizes = [16, 32, 64, 128, 256, 512]
            for s in sizes:
                resized = img.resize((s, s), Image.LANCZOS)
                resized.save(os.path.join(icon_set_dir, f'icon_{s}x{s}.png'), 'PNG')
                # Also save 2x versions
                if s * 2 <= 1024:
                    resized2x = img.resize((s * 2, s * 2), Image.LANCZOS)
                    resized2x.save(os.path.join(icon_set_dir, f'icon_{s}x{s}@2x.png'), 'PNG')

            # Use iconutil to create icns
            result = subprocess.run(
                ['iconutil', '-c', 'icns', '-o', path, icon_set_dir],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print(f"Saved: {path}")
            else:
                raise Exception(result.stderr)
    except FileNotFoundError:
        # iconutil not available, save as 512x512 PNG as fallback
        fallback = img.resize((512, 512), Image.LANCZOS)
        fallback.save(path.replace('.icns', '_512.png'), 'PNG')
        print(f"Saved fallback PNG (iconutil not available): {path.replace('.icns', '_512.png')}")
        print(f"Note: True ICNS requires macOS with iconutil. Created 512x512 PNG instead.")


def save_as_ico(img: Image.Image, path: str) -> None:
    """Save as ICO format for Windows."""
    # ICO supports multiple sizes, include 256, 128, 64, 48, 32, 16
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(path, 'ICO', sizes=sizes)
    print(f"Saved: {path}")


def main():
    """Generate all icon files."""
    base_dir = '/Users/doug/code/python/open-daily-stock/assets'
    os.makedirs(base_dir, exist_ok=True)

    print("Generating ODS icon...")
    icon = create_icon(1024)

    # Save PNG
    png_path = os.path.join(base_dir, 'icon.png')
    save_as_png(icon, png_path)

    # Save ICNS (macOS)
    icns_path = os.path.join(base_dir, 'icon.icns')
    save_as_icns(icon, icns_path)

    # Save ICO (Windows)
    ico_path = os.path.join(base_dir, 'icon.ico')
    save_as_ico(icon, ico_path)

    print("\nIcon generation complete!")


if __name__ == '__main__':
    import os
    main()