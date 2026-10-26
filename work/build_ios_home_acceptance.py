from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
import sys

design_path = Path(sys.argv[1])
device_path = Path(sys.argv[2])
out = Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)

design = Image.open(design_path).convert("RGB")
device = Image.open(device_path).convert("RGB")

def red_layer(image):
    gray = ImageOps.grayscale(image).convert("RGB")
    layer = ImageOps.colorize(ImageOps.grayscale(gray), black=(0, 0, 0), white=(255, 0, 0)).convert("RGBA")
    layer.putalpha(127)
    return layer

def overlay(design_crop, device_crop, name):
    base = design_crop.convert("RGBA")
    tint = red_layer(device_crop)
    x = (base.width - tint.width) // 2
    y = (base.height - tint.height) // 2
    base.alpha_composite(tint, (x, y))
    base.convert("RGB").save(out / name)

design.save(out / "design-source.png")
device.save(out / "device-source.png")

# Full-screen comparison uses left/right anchors only; the device image is never resized.
for anchor in ("left", "right", "center"):
    canvas = design.copy().convert("RGBA")
    tint = red_layer(device)
    x = 0 if anchor == "left" else design.width - device.width if anchor == "right" else (design.width - device.width) // 2
    canvas.alpha_composite(tint, (x, 0))
    canvas.convert("RGB").save(out / f"overlay-{anchor}.png")

canvas = Image.new("RGB", (design.width + device.width + 72, max(design.height, device.height) + 48), (238, 240, 243))
canvas.paste(design, (24, 48))
canvas.paste(device, (design.width + 48, 48))
draw = ImageDraw.Draw(canvas)
font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 16)
draw.text((24, 12), f"Figma 720x{design.height} @2x", fill=(40, 45, 52), font=font)
draw.text((design.width + 48, 12), f"iOS 828x{device.height} @2x", fill=(40, 45, 52), font=font)
canvas.save(out / "side-by-side.png")

# Device coordinates are used as anchors. Crop matching cards separately and center-align them
# for inspection; crop content remains at its native pixel size.
regions = {
    "calendar": ((32, 180, 688, 415), (32, 192, 796, 415)),
    "word-card": ((32, 436, 708, 1116), (32, 448, 796, 1116)),
    "activity-card": ((32, 1136, 688, 1468), (32, 1148, 796, 1468)),
    "tools-and-nav": ((32, 1500, 688, 2156), (32, 1500, 796, 1792)),
}

for name, (db, ub) in regions.items():
    d = design.crop(db)
    u = device.crop(ub)
    panel = Image.new("RGB", (max(d.width, u.width) + 40, d.height + u.height + 84), (238, 240, 243))
    panel.paste(d, ((panel.width - d.width) // 2, 48))
    panel.paste(u, ((panel.width - u.width) // 2, d.height + 68))
    draw = ImageDraw.Draw(panel)
    draw.text((20, 12), f"{name}: design / device native pixels", fill=(40, 45, 52), font=font)
    panel.save(out / f"module-{name}-comparison.png")
    overlay(d, u, f"module-{name}-overlay.png")

evidence_dir = out / "evidence"
evidence_dir.mkdir(exist_ok=True)
font = ImageFont.truetype("/System/Library/Fonts/STHeiti Medium.ttc", 15)

def add_label(image, text, x=12, y=8):
    draw = ImageDraw.Draw(image)
    draw.rectangle((x - 4, y - 2, x + 400, y + 22), fill=(255, 255, 255))
    draw.text((x, y), text, fill=(35, 45, 55), font=font)

def board_row(design_crop, device_crop, label, device_y_offset=0, bbox=None, mode="overlay"):
    width = max(design_crop.width, device_crop.width)
    height = max(design_crop.height, device_crop.height)
    canvas = Image.new("RGB", (width, height + 30), (238, 240, 243))
    add_label(canvas, label)
    if mode == "design":
        canvas.paste(design_crop, (0, 30))
    elif mode == "device":
        device_preview = device_crop.copy()
        if bbox:
            ImageDraw.Draw(device_preview).rectangle(bbox, outline=(220, 20, 35), width=4)
        canvas.paste(device_preview, (0, 30))
    else:
        canvas.paste(design_crop, (0, 30))
        base = canvas.convert("RGBA")
        layer = red_layer(device_crop)
        dest_y = 30 + device_y_offset
        source_y = max(0, -dest_y)
        target_y = max(0, dest_y)
        visible = layer.crop((0, source_y, layer.width, min(layer.height, source_y + base.height - target_y)))
        if visible.height > 0:
            base.alpha_composite(visible, (0, target_y))
        canvas = base.convert("RGB")
    return canvas

def evidence_board(name, title, panels):
    width = max(panel.width for panel in panels)
    height = sum(panel.height for panel in panels) + 36
    result = Image.new("RGB", (width, height), (238, 240, 243))
    add_label(result, title, 14, 8)
    y = 36
    for panel in panels:
        result.paste(panel, (0, y))
        y += panel.height
    result.save(evidence_dir / name)

d = design.crop((0, 150, 720, 440))
u = device.crop((0, 162, 828, 452))
evidence_board("P01-01-position.png", "内容区起始位置：设备截图比设计稿下移约12px", [
    board_row(d, d, "设计稿原位置 y=150", mode="design"),
    board_row(d, u, "设备原图位置 y=162", mode="device"),
    board_row(d, u, "设备图上移12px后红色50%对位", device_y_offset=-12, mode="overlay"),
])

db = design.crop((24, 1120, 696, 1475))
ub = device.crop((24, 1132, 820, 1487))
relative_bbox = (640 - 24, 1362 - 1132, 803 - 24, 1437 - 1132)
evidence_board("P01-02-test-overlay.png", "活动进度区：设备多出悬浮测试控件并遮挡文字", [
    board_row(db, db, "设计稿对应活动进度区域 y=1120", mode="design"),
    board_row(db, ub, "设备截图原图，红框为遮挡位置", bbox=relative_bbox, mode="device"),
    board_row(db, ub, "活动卡片顶部锚点对齐后的红色50%叠图", device_y_offset=-12, mode="overlay"),
])

dm = design.crop((120, 480, 590, 760))
um = device.crop((120, 492, 710, 772))
evidence_board("待确认-吉祥物状态.png", "吉祥物姿势不同，需确认是否为动效或状态差异", [
    board_row(dm, dm, "设计稿吉祥物", mode="design"),
    board_row(dm, um, "设备截图吉祥物", mode="device"),
])

print(f"saved {len(list(out.iterdir()))} comparison assets to {out}")
