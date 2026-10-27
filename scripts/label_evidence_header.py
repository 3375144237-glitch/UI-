#!/usr/bin/env python3
"""Add a labeled header strip above an evidence image without covering its pixels."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
)


def color_value(value: str) -> tuple[int, int, int]:
    normalized = value.removeprefix("#")
    if len(normalized) != 6:
        raise argparse.ArgumentTypeError("Color must be a 6-digit hex value, such as #EFF1F4")
    try:
        return tuple(int(normalized[index : index + 2], 16) for index in (0, 2, 4))
    except ValueError as error:
        raise argparse.ArgumentTypeError("Color must be a 6-digit hex value") from error


def load_font(path: Path | None, size: int, text: str) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if path:
        try:
            return ImageFont.truetype(str(path.expanduser()), size=size)
        except OSError as error:
            raise ValueError(f"Unable to load font: {path}") from error
    for candidate in FONT_CANDIDATES:
        if Path(candidate).is_file():
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                continue
    if any(not character.isascii() for character in text):
        raise ValueError("No Unicode font was found; pass a CJK-capable font with --font")
    return ImageFont.load_default()


def wrap_label(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        current = ""
        for character in paragraph:
            candidate = current + character
            bounds = draw.textbbox((0, 0), candidate, font=font)
            if current and bounds[2] - bounds[0] > max_width:
                lines.append(current)
                current = character
            else:
                current = candidate
        lines.append(current)
    return lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Source evidence image")
    parser.add_argument("--output", type=Path, required=True, help="New labeled image path")
    parser.add_argument("--label", required=True, help="Text to place in the header")
    parser.add_argument("--font", type=Path, help="Optional font file; useful for Chinese text on Linux")
    parser.add_argument("--font-size", type=int, default=18, help="Header text size (default: 18)")
    parser.add_argument("--header-height", type=int, default=42, help="Minimum header height in pixels (default: 42)")
    parser.add_argument("--padding", type=int, default=18, help="Horizontal and vertical text padding (default: 18)")
    parser.add_argument("--background", type=color_value, default=color_value("#EFF1F4"), help="Header color")
    parser.add_argument("--foreground", type=color_value, default=color_value("#20272E"), help="Text color")
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing an existing output file")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    source = args.input.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not source.is_file():
        parser.error(f"Input image not found: {source}")
    if source == output:
        parser.error("Output must differ from the source image")
    if output.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        parser.error("Output extension must be .png, .jpg, .jpeg, or .webp")
    if output.exists() and not args.overwrite:
        parser.error(f"Output already exists; pass --overwrite to replace it: {output}")
    if args.font_size <= 0 or args.header_height <= 0 or args.padding < 0:
        parser.error("Font size and header height must be positive; padding cannot be negative")

    try:
        with Image.open(source) as original:
            evidence = ImageOps.exif_transpose(original).convert("RGB")
        font = load_font(args.font, args.font_size, args.label)
        text_layer = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        lines = wrap_label(text_layer, args.label, font, max(1, evidence.width - args.padding * 2))
        line_heights = [
            max(1, bounds[3] - bounds[1])
            for bounds in (text_layer.textbbox((0, 0), line, font=font) for line in lines)
        ]
        line_gap = max(2, args.font_size // 5)
        content_height = sum(line_heights) + line_gap * max(0, len(lines) - 1)
        header_height = max(args.header_height, content_height + args.padding * 2)

        canvas = Image.new(
            "RGB",
            (evidence.width, evidence.height + header_height),
            args.background,
        )
        draw = ImageDraw.Draw(canvas)
        top = (header_height - content_height) // 2
        for line, line_height in zip(lines, line_heights):
            bounds = draw.textbbox((0, 0), line, font=font)
            draw.text((args.padding - bounds[0], top - bounds[1]), line, font=font, fill=args.foreground)
            top += line_height + line_gap
        canvas.paste(evidence, (0, header_height))

        output.parent.mkdir(parents=True, exist_ok=True)
        save_options = {"quality": 95} if output.suffix.lower() in {".jpg", ".jpeg", ".webp"} else {}
        canvas.save(output, **save_options)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    print(f"Saved labeled evidence image: {output}")


if __name__ == "__main__":
    main()
