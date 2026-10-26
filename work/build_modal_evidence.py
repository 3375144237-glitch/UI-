from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path("/Users/jiujiu/Documents/Codex/workspace/project-015-ui-repo-cleanup")
OUT = ROOT / "outputs/design-review/2026-10-26/麦奇说验收-IOS/12-今日计划已学完弹窗"
DESIGN = OUT / "inputs/design-original.png"
DEVICE = OUT / "inputs/device-original.png"
FONT_PATHS = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]


def font(size: int):
    for path in FONT_PATHS:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                pass
    return ImageFont.load_default()


def label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str) -> None:
    draw.text(xy, text, fill=(32, 39, 46), font=font(18))


def wrap_text(draw: ImageDraw.ImageDraw, text: str, text_font: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [text]:
        line = ""
        for char in paragraph:
            candidate = line + char
            if line and draw.textlength(candidate, font=text_font) > max_width:
                lines.append(line)
                line = char
            else:
                line = candidate
        lines.append(line)
    return lines


def red_layer(image: Image.Image) -> Image.Image:
    layer = ImageOps.colorize(ImageOps.grayscale(image), black=(0, 0, 0), white=(255, 0, 0)).convert("RGBA")
    layer.putalpha(128)
    return layer


def evidence(
    name: str,
    title: str,
    notes: list[str],
    design_crop: Image.Image,
    device_crop: Image.Image,
    design_box: tuple[int, int, int, int],
    device_box: tuple[int, int, int, int],
    issue_color: tuple[int, int, int],
) -> None:
    margin, panel_header, gap = 20, 30, 18
    panel_w = max(design_crop.width, device_crop.width)
    image_h = max(design_crop.height, device_crop.height)
    note_font = font(18)
    measure_draw = ImageDraw.Draw(Image.new("RGB", (panel_w, panel_w)))
    note_lines = [line for note in notes for line in wrap_text(measure_draw, note, note_font, panel_w - 24)]
    note_line_h = 32
    lower_body_h = max(image_h, 14 + note_line_h * len(note_lines))
    top_panel_h = panel_header + image_h
    canvas_h = margin * 2 + 36 + top_panel_h + gap + panel_header + lower_body_h
    canvas = Image.new("RGB", (margin * 2 + panel_w * 2 + gap, canvas_h), (239, 241, 244))
    draw = ImageDraw.Draw(canvas)
    label(draw, (margin, 7), title)
    x1, x2 = margin, margin + panel_w + gap
    y1, y2 = margin + 36, margin + 36 + top_panel_h + gap
    label(draw, (x1, y1 + 6), "設計稿裁片")
    label(draw, (x2, y1 + 6), "設備原圖裁片")
    label(draw, (x1, y2 + 6), "設備紅色 50% 疊圖，彈窗頂部對齊")
    label(draw, (x2, y2 + 6), "檢查記錄")
    content_y1, content_y2 = y1 + panel_header, y2 + panel_header
    marked_design, marked_device = design_crop.copy(), device_crop.copy()
    ImageDraw.Draw(marked_design).rectangle(design_box, outline=(43, 106, 171), width=3)
    ImageDraw.Draw(marked_device).rectangle(device_box, outline=issue_color, width=3)
    canvas.paste(marked_design, (x1, content_y1))
    canvas.paste(marked_device, (x2, content_y1))
    overlay_w = max(design_crop.width, device_crop.width)
    overlay_h = max(design_crop.height, device_crop.height)
    base = Image.new("RGBA", (overlay_w, overlay_h), (77, 77, 77, 255))
    base.alpha_composite(design_crop.convert("RGBA"), ((overlay_w - design_crop.width) // 2, 0))
    base.alpha_composite(red_layer(device_crop), ((overlay_w - device_crop.width) // 2, 0))
    canvas.paste(base.convert("RGB"), (x1, content_y2))
    note_draw = ImageDraw.Draw(canvas)
    note_y = content_y2 + 14
    for line in note_lines:
        note_draw.text((x2 + 12, note_y), line, fill=(40, 48, 56), font=note_font)
        note_y += note_line_h
    canvas.save(OUT / "evidence" / name)


OUT.mkdir(parents=True, exist_ok=True)
(OUT / "evidence").mkdir(exist_ok=True)
design = Image.open(DESIGN).convert("RGB")
device = Image.open(DEVICE).convert("RGB")

# The popup is compared independently; screen chrome and vertical screen placement are excluded.
design_dialog = design.crop((80, 569, 640, 991))
device_dialog = device.crop((134, 667, 694, 1125))
design_dialog.save(OUT / "design-dialog.png")
device_dialog.save(OUT / "device-dialog.png")

side = Image.new("RGB", (20 + design_dialog.width + 20 + device_dialog.width + 20, 60 + max(design_dialog.height, device_dialog.height)), (239, 241, 244))
label(ImageDraw.Draw(side), (20, 8), "設計稿彈窗 560×422px")
label(ImageDraw.Draw(side), (20 + design_dialog.width + 20, 8), "設備彈窗 560×458px")
side.paste(design_dialog, (20, 38))
side.paste(device_dialog, (20 + design_dialog.width + 20, 38))
side.save(OUT / "dialog-side-by-side.png")

overlay = Image.new("RGBA", (560, 458), (77, 77, 77, 255))
overlay.alpha_composite(design_dialog.convert("RGBA"), (0, 0))
overlay.alpha_composite(red_layer(device_dialog), (0, 0))
overlay.convert("RGB").save(OUT / "dialog-overlay-top-aligned.png")

body_design_box = (40, 126, 520, 242)
body_device_box = (58, 141, 504, 232)
evidence(
    "P12-01-copy.png",
    "P12-01 固定正文与设计稿内容不同",
    ["设计：今日新词任务已完成。你还可以回顾历史单词巩固记忆，或进入单元学查看教材中的更多内容。", "设备：你今天的新学单词都已完成，可回顾历史单词巩固记忆，或前往单元学查看更多内容。"],
    design_dialog,
    device_dialog,
    body_design_box,
    body_device_box,
    (210, 36, 47),
)
evidence(
    "P12-02-dialog-height.png",
    "P12-02 弹窗高度与内部纵向布局不同",
    ["设计导出图可见弹窗：560×422px。", "设备可见弹窗：560×458px，高约36px；宽度一致。", "Figma子层 Frame 80 属性为560×380px、圆角32px。", "顶部对齐后，设备标题和按钮整体更靠下。"],
    design_dialog,
    device_dialog,
    (0, 0, 559, 421),
    (0, 0, 559, 457),
    (210, 36, 47),
)
evidence(
    "P12-03-body-color.png",
    "P12-03 正文颜色明显偏浅",
    ["设计正文主要实色像素约 RGB(98,100,102)。", "设备正文主要实色像素约 RGB(158,161,164)。", "字体家族与源字号仍需 Figma Typography 属性核实。"],
    design_dialog,
    device_dialog,
    body_design_box,
    body_device_box,
    (210, 36, 47),
)
evidence(
    "P12-04-vertical-layout.png",
    "P12-04 弹窗内部纵向排布与间距不同",
    ["顶部对齐后，设备标题约下移27px，正文首行约下移15px。", "正文行距较设计稿更紧；正文末行约上移9px。", "按钮组约下移37px，正文至按钮的间距增加约46px。"],
    design_dialog,
    device_dialog,
    (20, 34, 540, 374),
    (21, 60, 539, 410),
    (210, 36, 47),
)
