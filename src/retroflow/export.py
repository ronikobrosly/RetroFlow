"""
File export functionality for flowcharts.

This module handles exporting generated flowcharts to various file formats:
- Text files (.txt) - Plain ASCII art
- PNG images - High-resolution rasterized output with customizable fonts

The FlowchartExporter class provides methods for saving flowcharts and handles
font loading, image rendering, and file I/O.
"""

from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont


class FlowchartExporter:
    """
    Exports flowcharts to various file formats.

    Handles text and PNG export with customizable options for fonts,
    colors, and resolution.

    Attributes:
        default_font: Default font name for PNG export.
    """

    def __init__(self, default_font: Optional[str] = None):
        """
        Initialize the flowchart exporter.

        Args:
            default_font: Default font name for PNG export (e.g., "Cascadia Code").
        """
        self.default_font = default_font

    def save_txt(self, flowchart: str, filename: str) -> None:
        """
        Save flowchart to a text file.

        Args:
            flowchart: The ASCII flowchart string to save.
            filename: Output filename (should end in .txt).
        """
        output_path = Path(filename)
        output_path.write_text(flowchart, encoding="utf-8")

    def save_png(
        self,
        flowchart: str,
        filename: str,
        font_size: int = 16,
        bg_color: str = "#FFFFFF",
        fg_color: str = "#000000",
        padding: int = 20,
        font: Optional[str] = None,
        scale: int = 2,
    ) -> None:
        """
        Save flowchart as a high-resolution PNG image.

        The PNG rendering is faithful to the ASCII version, using a monospace
        font to preserve the exact character layout and box-drawing characters.

        Args:
            flowchart: The ASCII flowchart string to render.
            filename: Output filename (should end in .png).
            font_size: Font size in points (higher = higher resolution).
            bg_color: Background color as hex string (e.g., "#FFFFFF").
            fg_color: Foreground/text color as hex string (e.g., "#000000").
            padding: Padding around the diagram in pixels.
            font: Font name to use (overrides default_font if provided).
            scale: Resolution multiplier for crisp output (default 2 for retina).

        Example:
            >>> exporter = FlowchartExporter(default_font="Cascadia Code")
            >>> exporter.save_png(flowchart, "output.png", font_size=24)
        """
        lines = flowchart.split("\n")

        # Use provided font, fall back to default font, then system defaults
        font_name = font or self.default_font
        # Apply scale multiplier to font size for higher resolution output
        scaled_font_size = font_size * scale
        loaded_font = self._load_monospace_font(scaled_font_size, font_name)

        # Calculate character dimensions using a reference character
        bbox = loaded_font.getbbox("M")
        char_width = bbox[2] - bbox[0]
        char_height = bbox[3] - bbox[1]
        line_height = int(char_height * 1.2)  # Add some line spacing

        # Scale padding to match resolution
        scaled_padding = padding * scale

        # Calculate image dimensions
        max_line_len = max(len(line) for line in lines) if lines else 0
        img_width = char_width * max_line_len + scaled_padding * 2
        img_height = line_height * len(lines) + scaled_padding * 2

        # Ensure minimum dimensions (scaled)
        img_width = max(img_width, 100 * scale)
        img_height = max(img_height, 100 * scale)

        # Create image and draw text
        img = Image.new("RGB", (img_width, img_height), bg_color)
        draw = ImageDraw.Draw(img)

        y = scaled_padding
        for line in lines:
            draw.text((scaled_padding, y), line, font=loaded_font, fill=fg_color)
            y += line_height

        # Save the image
        output_path = Path(filename)
        img.save(output_path, "PNG")

    def _load_monospace_font(
        self, font_size: int, font_name: Optional[str] = None
    ) -> ImageFont.FreeTypeFont:
        """
        Load a monospace font for PNG rendering.

        Tries the following in order:
        1. User-specified font name if provided
        2. Common system monospace fonts
        3. Pillow's default font

        Args:
            font_size: Font size in points.
            font_name: Optional font name (e.g., "Cascadia Code", "Monaco").

        Returns:
            A PIL ImageFont object.
        """
        # Build list of fonts to try
        fonts_to_try = []

        # Add user-specified font first
        if font_name:
            fonts_to_try.append(font_name)

        # Common monospace fonts across different systems
        fonts_to_try.extend(
            [
                # Linux
                "DejaVuSansMono",
                "DejaVu Sans Mono",
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                # macOS
                "Monaco",
                "Menlo",
                "/System/Library/Fonts/Monaco.ttf",
                "/System/Library/Fonts/Menlo.ttc",
                # Windows
                "Consolas",
                "Cascadia Code",
                "Courier New",
                "C:/Windows/Fonts/consola.ttf",
            ]
        )

        for font in fonts_to_try:
            try:
                return ImageFont.truetype(font, font_size)
            except OSError:
                continue

        # Fall back to Pillow's default font
        try:
            return ImageFont.load_default(size=font_size)
        except TypeError:
            # Older Pillow versions don't support size parameter
            return ImageFont.load_default()
