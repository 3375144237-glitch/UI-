#!/usr/bin/env python3
"""Build a per-icon, center-aligned size comparison for P14-N07."""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


PROJECT = Path(__file__).resolve().parents[1]
SESSION = PROJECT / "outputs/design-review/2026-10-23/麦奇说验收-安卓/01-分享页完成弹窗-逐项对位"
DESIGN_PATH = SESSION / "inputs/design-screen.png"
DEVICE_PATH = SESSION / "inputs/device-original.png"
OUTPUT_PATH = SESSION / "evidence/P14-N07.png"
FIGMA_PREVIEW_PATH = PROJECT / "work/figma-icon-size-evidence.jpg"


def measure(image: Image.Image, region: tuple[int, int, int, int], kind: str) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = region
    pixels = np.asarray(image.crop(region).convert("RGB"))
    red, green, blue = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]
    if kind == "yellow":
        mask = (red > 190) & (green > 125) & (blue < 100)
    elif kind == "blue":
        mask = (blue > 145) & (green > 100) & (red < 145)
    else:
        mask = (red > 160) & (blue > 115) & (green < 155)
    yy, xx = np.where(mask)
    if not len(xx):
        raise ValueError(f"No icon pixels found for {kind} in {region}")
    return (
        int(xx.min() + x0),
        int(yy.min() + y0),
        int(xx.max() + x0 + 1),
        int(yy.max() + y0 + 1),
    )


def icon_tile(image: Image.Image, bbox: tuple[int, int, int, int], size: int = 120, padding: int = 8) -> Image.Image:
    left, top, right, bottom = bbox
    crop_box = (left - padding, top - padding, right + padding, bottom + padding)
    crop = image.crop(crop_box)
    background = image.getpixel((max(0, left - padding - 1), max(0, top - padding - 1)))
    tile = Image.new("RGB", (size, size), background)
    tile.paste(crop, ((size - crop.width) // 2, (size - crop.height) // 2))
    return tile


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def format_measurement(bbox: tuple[int, int, int, int]) -> str:
    return f"x={bbox[0]}, y={bbox[1]}, w={bbox[2] - bbox[0]}, h={bbox[3] - bbox[1]}"


def main() -> None:
    design = Image.open(DESIGN_PATH).convert("RGB")
    device = Image.open(DEVICE_PATH).convert("RGB")
    icons = [
        {
            "label": "总经验 / 闪电",
            "kind": "yellow",
            "design_region": (270, 640, 330, 710),
            "device_region": (240, 640, 330, 740),
            "node": "6:1874",
        },
        {
            "label": "练习时长 / 时钟",
            "kind": "blue",
            "design_region": (270, 785, 330, 850),
            "device_region": (520, 640, 610, 740),
            "node": "6:1897",
        },
        {
            "label": "新学单词 / 靶标",
            "kind": "pink",
            "design_region": (550, 790, 615, 855),
            "device_region": (235, 810, 325, 900),
            "node": "6:1908",
        },
    ]

    canvas = Image.new("RGB", (1600, 630), "#F1F4F6")
    draw = ImageDraw.Draw(canvas)
    title_font = load_font(28)
    subtitle_font = load_font(18)
    row_font = load_font(22)
    body_font = load_font(17)
    small_font = load_font(15)

    draw.rectangle((0, 0, 1599, 72), fill="#263746")
    draw.text((24, 9), "P14-N07 统计区内 3 枚现存图标均偏大", font=title_font, fill="white")
    draw.text((24, 44), "Figma 设计节点 6:1859；对应图标节点各为 48×48px；设备原图 720px @2x，保持原比例", font=subtitle_font, fill="#D8E1E8")

    draw.text((400, 80), "设计稿可见图形", font=body_font, fill="#34495A")
    draw.text((590, 80), "设备原图裁片", font=body_font, fill="#34495A")
    draw.text((780, 80), "红色 50% 裁片移到设计中心", font=body_font, fill="#34495A")
    draw.text((960, 80), "逐枚尺寸与原图坐标（@2x px）", font=body_font, fill="#34495A")

    results = []
    for index, item in enumerate(icons):
        design_bbox = measure(design, item["design_region"], item["kind"])
        device_bbox = measure(device, item["device_region"], item["kind"])
        design_width = design_bbox[2] - design_bbox[0]
        design_height = design_bbox[3] - design_bbox[1]
        device_width = device_bbox[2] - device_bbox[0]
        device_height = device_bbox[3] - device_bbox[1]
        dx = round((design_bbox[0] + design_bbox[2] - device_bbox[0] - device_bbox[2]) / 2)
        dy = round((design_bbox[1] + design_bbox[3] - device_bbox[1] - device_bbox[3]) / 2)
        ratio = (device_width / design_width + device_height / design_height) / 2
        result = {
            "label": item["label"],
            "design_node": item["node"],
            "design_bbox": {"x": design_bbox[0], "y": design_bbox[1], "width": design_width, "height": design_height},
            "device_bbox": {"x": device_bbox[0], "y": device_bbox[1], "width": device_width, "height": device_height},
            "difference": {"width": device_width - design_width, "height": device_height - design_height},
            "ratio": round(ratio, 2),
            "alignment_offset": {"x": dx, "y": dy},
        }
        results.append(result)

        top = 106 + index * 160
        bottom = top + 150
        draw.rounded_rectangle((12, top, 1588, bottom), radius=6, fill="white", outline="#D2DCE3", width=2)
        draw.text((28, top + 15), item["label"], font=row_font, fill="#192631")
        draw.text((28, top + 49), f"Figma {item['node']} 可见 {design_width}×{design_height}px", font=small_font, fill="#425565")
        draw.text((28, top + 73), f"设备 {device_width}×{device_height}px，约 {ratio:.2f}×", font=small_font, fill="#425565")

        design_tile = icon_tile(design, design_bbox)
        device_tile = icon_tile(device, device_bbox)
        overlay_base = design_tile.convert("RGBA")
        red_crop = device_tile.convert("RGBA")
        red_overlay = Image.new("RGBA", red_crop.size, (255, 0, 0, 128))
        tinted_device = Image.alpha_composite(red_crop, red_overlay)
        overlay_base.alpha_composite(tinted_device)

        for x, tile in [(400, design_tile), (590, device_tile), (780, overlay_base.convert("RGB"))]:
            canvas.paste(tile, (x, top + 14))
            draw.rectangle((x, top + 14, x + 120, top + 134), outline="#AEBBC5", width=1)

        difference_width = device_width - design_width
        difference_height = device_height - design_height
        detail_lines = [
            f"设计可见 bbox：{format_measurement(design_bbox)}",
            f"设备原图 bbox：{format_measurement(device_bbox)}",
            f"尺寸差：宽 +{difference_width}px，高 +{difference_height}px",
            f"中心对位偏移：x {dx}px，y {dy}px；裁片未缩放",
        ]
        for line_index, line in enumerate(detail_lines):
            draw.text((960, top + 20 + line_index * 27), line, font=body_font, fill="#263746")

    draw.text((24, 594), "尺寸按同一 720px 设计稿与设备原图的彩色图形可见像素边界测量；设计容器为 48×48px。缺少的钻石项仍单列在 P14-N02。", font=small_font, fill="#536574")

    canvas.save(OUTPUT_PATH, optimize=True)
    preview = canvas.resize((720, 284), Image.Resampling.LANCZOS)
    preview.save(FIGMA_PREVIEW_PATH, "JPEG", quality=70, optimize=True)
    for item in results:
        print(item)
    print(f"evidence={OUTPUT_PATH}")
    print(f"figma_preview={FIGMA_PREVIEW_PATH} bytes={FIGMA_PREVIEW_PATH.stat().st_size}")


if __name__ == "__main__":
    main()
