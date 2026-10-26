#!/usr/bin/env python3
"""Build source-linked comparison plates and review.json for the Android popup batch."""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


PROJECT = Path(__file__).resolve().parents[1]
SESSION = PROJECT / "outputs/design-review/2026-10-23/麦奇说验收-安卓/01-分享页完成弹窗-逐项对位"
INPUTS = SESSION / "inputs"
EVIDENCE = SESSION / "evidence"
DEVICE_NAME = "安卓设备（2倍图，720px）"
DEVICE_SOURCE = "image 50.png"
FIGMA_URL = "https://www.figma.com/design/kYoNWHRIkZk9M2XM0gheNH/麦奇说（UI测试验收）?node-id=67-23"


def open_rgb(path: Path) -> Image.Image:
    with Image.open(path) as source:
        return ImageOps.exif_transpose(source).convert("RGB")


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ):
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def red_layer(image: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(image)
    layer = ImageOps.colorize(gray, black=(0, 0, 0), white=(210, 36, 47)).convert("RGBA")
    layer.putalpha(128)
    return layer


def composite_at(base: Image.Image, overlay: Image.Image, xy: tuple[int, int]) -> None:
    x, y = xy
    left, top = max(0, x), max(0, y)
    source_left, source_top = max(0, -x), max(0, -y)
    width = min(overlay.width - source_left, base.width - left)
    height = min(overlay.height - source_top, base.height - top)
    if width <= 0 or height <= 0:
        return
    crop = overlay.crop((source_left, source_top, source_left + width, source_top + height))
    base.alpha_composite(crop, (left, top))


def point_box(x: int, y: int, width: int, height: int) -> dict[str, int]:
    return {"x": x, "y": y, "width": width, "height": height}


def finding(
    issue_id: str,
    description: str,
    category: str,
    status: str,
    priority: str,
    design_basis: str,
    expected: str,
    actual: str,
    measurement: str,
    recommendation: str,
    device_box: tuple[int, int, int, int],
    design_box: tuple[int, int, int, int],
    target_xy: tuple[int, int],
    page_note: str,
    plate_device_box: tuple[int, int, int, int] | None = None,
) -> dict:
    x, y, width, height = device_box
    return {
        "id": issue_id,
        "page_group": "P14",
        "page": "分享页/完成弹窗",
        "device": DEVICE_NAME,
        "source_screenshot": DEVICE_SOURCE,
        "status": status,
        "priority": priority,
        "category": category,
        "description": description,
        "design_basis": design_basis,
        "expected": expected,
        "actual": actual,
        "measurement": measurement,
        "recommendation": recommendation,
        "affected_pages": ["分享页/完成弹窗"],
        "bbox": point_box(x, y, width, height),
        "device_bbox": point_box(x, y, width, height),
        "design_bbox": point_box(*design_box),
        "alignment": {
            "method": "设备原图裁片红色50%叠到设计区域；不缩放，单独移动裁片以对齐对应内容锚点",
            "target_offset_in_design_crop": {"x": target_xy[0], "y": target_xy[1]},
            "device_crop_bbox": point_box(*(plate_device_box or device_box)),
            "note": page_note,
        },
        "evidence": f"evidence/{issue_id}.png",
        "remarks": f"来源设备截图：{DEVICE_SOURCE}；设计稿：Figma 节点 6:1859。",
    }


def paste_box(image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    x, y, width, height = box
    return image.crop((x, y, x + width, y + height))


def plate_for(design: Image.Image, device: Image.Image, issue: dict) -> None:
    spec = issue["_plate"]
    design_crop = paste_box(design, spec["design_crop"])
    source_crop_box = spec["device_crop"]
    device_crop = paste_box(device, source_crop_box)
    device_marked = device_crop.copy()
    draw = ImageDraw.Draw(device_marked)
    issue_box = issue["device_bbox"]
    issue_left = issue_box["x"] - source_crop_box[0]
    issue_top = issue_box["y"] - source_crop_box[1]
    issue_right = issue_left + issue_box["width"] - 1
    issue_bottom = issue_top + issue_box["height"] - 1
    draw.rectangle((issue_left, issue_top, issue_right, issue_bottom), outline=(210, 36, 47), width=3)

    overlap = design_crop.convert("RGBA")
    composite_at(overlap, red_layer(device_crop), tuple(spec["target_xy"]))
    overlap = overlap.convert("RGB")
    overlay_draw = ImageDraw.Draw(overlap)
    target_x, target_y = spec["target_xy"]
    overlay_draw.rectangle(
        (target_x + issue_left, target_y + issue_top, target_x + issue_right, target_y + issue_bottom),
        outline=(45, 58, 66),
        width=2,
    )

    pad = 16
    header_h = 56
    panel_h = 30
    content_h = max(design_crop.height, device_marked.height, overlap.height)
    width = design_crop.width * 3 + pad * 4
    height = header_h + panel_h + content_h + pad
    canvas = Image.new("RGB", (width, height), "#F2F4F5")
    draw = ImageDraw.Draw(canvas)
    title_font = font(20)
    small_font = font(15)
    draw.text((pad, 8), f"{issue['id']}  {issue['description']}", fill="#20323D", font=title_font)
    draw.text((pad, 34), f"来源：{DEVICE_SOURCE}  坐标：{issue['bbox']['x']},{issue['bbox']['y']},{issue['bbox']['width']},{issue['bbox']['height']}", fill="#53616A", font=small_font)

    panels = [
        (design_crop, "设计稿对应区域"),
        (device_marked, "设备原图问题区域（未修改）"),
        (overlap, "设备裁片红色50%移至设计锚点"),
    ]
    for index, (panel, label) in enumerate(panels):
        x = pad + index * (design_crop.width + pad)
        draw.rectangle((x, header_h, x + design_crop.width - 1, header_h + panel_h - 1), fill="#DCE4E8")
        draw.text((x + 8, header_h + 5), label, fill="#20323D", font=small_font)
        y = header_h + panel_h + (content_h - panel.height) // 2
        canvas.paste(panel, (x, y))
        draw.rectangle((x, y, x + panel.width - 1, y + panel.height - 1), outline="#95A3AB", width=1)
    canvas.save(EVIDENCE / f"{issue['id']}.png", optimize=True)


def main() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    device = open_rgb(INPUTS / "device-original.png")
    design_screen = open_rgb(INPUTS / "design-screen.png")
    design = open_rgb(INPUTS / "design-dialog.png")
    if device.size != (720, 1560) or design_screen.size != (720, 1560) or design.size != (600, 910):
        raise ValueError(f"输入尺寸不符：device={device.size}, design-screen={design_screen.size}, dialog={design.size}")

    popup_box = (60, 183, 600, 942)
    device_dialog = paste_box(device, popup_box)
    dialog_canvas = Image.new("RGBA", (600, 942), "white")
    dialog_canvas.alpha_composite(design.convert("RGBA"), (0, 0))
    composite_at(dialog_canvas, red_layer(device_dialog), (0, 0))
    dialog_canvas.convert("RGB").save(EVIDENCE / "dialog-overlap-local.png", optimize=True)
    side_by_side = Image.new("RGB", (600 * 2 + 40, 942), "#E9ECEF")
    side_by_side.paste(design, (0, 0))
    side_by_side.paste(device_dialog, (640, 0))
    labels = ImageDraw.Draw(side_by_side)
    labels.rectangle((0, 0, 599, 30), fill="#DCE4E8")
    labels.rectangle((640, 0, 1239, 30), fill="#DCE4E8")
    labels.text((10, 6), "Figma设计弹窗 600×910", fill="#20323D", font=font(15))
    labels.text((650, 6), "设备弹窗裁图 600×942", fill="#20323D", font=font(15))
    side_by_side.save(EVIDENCE / "dialog-side-by-side.png", optimize=True)

    issues = [
        finding(
            "P14-N01",
            "统计项容器的浅紫色底色与R24圆角未实现",
            "容器样式",
            "待修复",
            "P2",
            "Figma 节点 6:1859：统计区 2×2 卡片，每项 256×126px，浅紫色底、R24圆角；卡片间距24px。",
            "四项统计分别位于设计稿卡片内，容器背景和圆角与设计保持一致。",
            "设备截图对应区域无卡片底色和可见圆角边界，统计文字与图标直接显示在白色主体上。",
            "设备区域 bbox=(92,646,536,276)；裁片按统计区整体边界对齐后仍看不到设备侧容器。",
            "恢复四个统计项卡片容器的浅紫底色与R24圆角，保留内部文字和图标相对位置。",
            (92, 646, 536, 276), (32, 432, 536, 276), (0, 0),
            "统计区整体裁片从弹窗局部 y=463 移至设计 y=432，向上31px；未缩放。",
        ),
        finding(
            "P14-N02",
            "统计字段数量与组成不同，需先确认业务状态",
            "字段/业务状态待确认",
            "待确认",
            "待评估",
            "Figma 节点 6:1859 显示总经验、本次钻石、练习时长、新学单词四项，按2×2排列。",
            "若为同一完成状态，应显示设计稿对应字段；动态数字只核对字体样式，不要求具体数值相等。",
            "设备画面有本次经验、练习时长、新学单词三项；缺少本次钻石项，且经验字段文案为本次经验。",
            "设备统计区 bbox=(92,646,536,276)；字段数量为3对4，未比较数字值。",
            "先确认截图是否与设计稿属于同一奖励/完成状态；状态一致后再按字段清单处理。",
            (92, 646, 536, 276), (32, 432, 536, 276), (0, 0),
            "Figma 中三项设备模块已分别移动到对应文字/图标锚点；对应钻石项仍无设备裁片。",
        ),
        finding(
            "P14-N03",
            "标题垂直位置与标题至统计区留白偏大，字体待复核",
            "位置/间距/字体待确认",
            "待确认",
            "P2",
            "设计弹窗标题位于弹窗局部 y=356，设计区域高36px；数字内容可变，仅比较字体样式。",
            "弹窗顶部局部对齐后，标题字形、基线及至统计数字的留白应与设计稿接近。",
            "设备标题可见字形约低6px，标题到首项数字的留白约多10px；设备奖励文本和设计稿存在业务内容差异。",
            "截图像素估算：标题低约6px、间距多约10px；当前 Figma 缺少设计稿指定字体，字体结论待确认。",
            "按相同标题文字锚点复核垂直位置和间距；由设计方用目标字体确认字形差异。",
            (92, 542, 536, 60), (0, 344, 600, 360), (0, 0),
            "先将弹窗裁图顶部对齐，再比较标题与首行统计的相对距离；不使用屏幕顶部位置。",
            plate_device_box=(60, 527, 600, 360),
        ),
        finding(
            "P14-N04",
            "弹窗主体偏高，身份条分隔线低于设计位置",
            "主体尺寸/垂直间距",
            "待修复",
            "P2",
            "设计弹窗 600×910px，白色主体与身份条分隔线位于弹窗局部 y=732px。",
            "弹窗裁图顶部边缘对齐后，分隔线应落在设计稿 y=732px 附近，整体弹窗高度为910px。",
            "设备弹窗局部高度942px；分隔线约在局部 y=786px，较设计低54px，弹窗底部总高多32px。",
            "弹窗局部对位估算：分隔线 +54px；整体高度 +32px。不是屏幕顶部偏移。",
            "检查白色主体纵向留白与身份条起始位置，使分隔线和弹窗总高分别回到设计值。",
            (60, 940, 600, 100), (0, 700, 600, 210), (0, 0),
            "弹窗独立裁切后两张图顶部直接对齐；设备区域取原图 (60,883) 起的同一弹窗纵向区段。",
            plate_device_box=(60, 883, 600, 210),
        ),
        finding(
            "P14-N05",
            "底部身份条高度比设计稿少22px",
            "容器尺寸",
            "待修复",
            "P2",
            "Figma 节点 6:1859：身份条 600×178px，头像、用户名与日期在容器内排布。",
            "身份条高度178px；头像与文字在条内的位置保持设计关系。",
            "设备身份条高156px；按头像和用户名对齐后，设备条上缘约低22px，底边近似重合。",
            "设计 178px；设备 156px；高度差 -22px。测量对象为截图像素，不推断dp或源码尺寸。",
            "核对身份条容器高度和上沿位置；动态头像、用户名及日期不据此判错。",
            (60, 969, 600, 156), (0, 700, 600, 210), (0, 52),
            "设备身份条裁片上移至设计头像/用户名锚点；不缩放，保留底边与上沿的差异。",
        ),
        finding(
            "P14-N06",
            "“新学单词”标签设备渲染宽高偏小，需确认字体",
            "字体/字号待确认",
            "待确认",
            "P2",
            "Figma 设计稿中“新学单词”标签位于右下统计卡，框约112×28px。",
            "相同标签的字体家族、字号、字重和行高与设计稿一致；数字值不参与比较。",
            "设备端相同标签可见字形约95×22px；Figma 当前缺少设计稿指定字体，视觉差异可能受替代字体影响。",
            "截图像素估算：设备字形约95×22px，设计渲染约109×26px；差约14px宽、4px高。",
            "由设计方确认目标字体及字号，并在字体环境一致后复核；确认前不定为已确认缺陷。",
            (92, 796, 256, 126), (312, 582, 256, 126), (0, 0),
            "设备左下新学单词模块移到设计右下对应卡；文字和图标做内容锚点，不缩放。",
        ),
    ]

    for issue in issues:
        issue["_plate"] = {
            "device_crop": tuple(issue["alignment"]["device_crop_bbox"].values()),
            "design_crop": tuple(issue["design_bbox"].values()),
            "target_xy": tuple(issue["alignment"]["target_offset_in_design_crop"].values()),
        }
        plate_for(design, device, issue)
        del issue["_plate"]

    review = {
        "schema_version": 1,
        "page": "分享页/完成弹窗",
        "page_group": "P14",
        "device": DEVICE_NAME,
        "mode": "PX",
        "review_status": "已完成逐项检查，3项待修复、3项待确认",
        "coordinate_unit": "原始安卓设备截图 @2x 像素坐标（720px宽，保持原尺寸）",
        "design": {
            "figma_url": FIGMA_URL,
            "figma_node": "6:1859",
            "acceptance_page": "麦奇说验收（67:23）",
            "original": "inputs/design-screen.png",
            "prepared": "inputs/design-dialog.png",
            "source_size": [720, 1560],
            "size": [600, 910],
            "reference_region": {"x": 60, "y": 175, "width": 600, "height": 910},
        },
        "device_image": {
            "original": "inputs/device-original.png",
            "source_name": DEVICE_SOURCE,
            "prepared": "inputs/device-original.png",
            "size": [720, 1560],
            "dialog_crop": {"x": 60, "y": 183, "width": 600, "height": 942},
        },
        "normalization": {
            "mode": "PX",
            "source_size": [720, 1560],
            "prepared_size": [720, 1560],
            "scale": 1.0,
            "rule": "用户确认安卓设备截图本身为2倍图、宽720px；直接按设计稿@2x尺寸对位，不缩放。",
        },
        "alignment_method": {
            "full_page": "同尺寸PX基准；整屏红色50%叠图仅作初始参考。",
            "dialog": "设备弹窗单独裁切为600×942px，与设计弹窗600×910px顶部对齐；不比较状态栏或屏幕顶边。",
            "modules": "徽章、吉祥物、标题、统计项、身份条逐个裁切并移动到对应设计锚点；不缩放、不改原图。",
            "evidence": "每条问题图包含设计区域、设备原图裁片和移动到设计位置的红色50%叠图。",
        },
        "overlay": {
            "alignment": "弹窗局部顶部对齐",
            "opacity": 0.5,
            "current_preview": "evidence/dialog-overlap-local.png",
            "side_by_side": "evidence/dialog-side-by-side.png",
        },
        "findings": issues,
    }
    (SESSION / "review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"review": str(SESSION / "review.json"), "findings": len(issues), "evidence": [item["evidence"] for item in issues]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
