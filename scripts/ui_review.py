#!/usr/bin/env python3
"""Prepare paired mobile screenshots and build an editable visual review workbook."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from openpyxl import Workbook, load_workbook
from openpyxl.drawing.image import Image as SheetImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation


VISIBLE_HEADERS = ["设备", "截图", "问题描述", "优先级", "修复状态", "备注"]
PRIORITIES = ["待评估", "P0", "P1", "P2", "P3"]
STATUSES = ["待确认", "待修复", "修复中", "已修复", "不修复"]
OVERLAY_ALIGNMENTS = ("left", "right", "center")
OVERLAY_OPACITY = 0.5
RED = (210, 36, 47)
ANNOTATION_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]


def open_rgb(path: Path) -> Image.Image:
    with Image.open(path) as source:
        return ImageOps.exif_transpose(source).convert("RGB")


def annotation_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for font_path in ANNOTATION_FONTS:
        if Path(font_path).is_file():
            try:
                return ImageFont.truetype(font_path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def normalize_device(
    image: Image.Image,
    mode: str,
    target_width: int | None,
    screenshot_scale: float | None,
    already_2x: bool,
) -> tuple[Image.Image, dict[str, Any]]:
    source_width, source_height = image.size
    if mode == "rem":
        target_width = 720
        target_height = max(1, round(source_height * target_width / source_width))
        normalized = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        return normalized, {
            "mode": "REM",
            "source_size": [source_width, source_height],
            "prepared_size": list(normalized.size),
            "scale": round(target_width / source_width, 8),
            "rule": "按宽度等比缩放至720px",
        }

    if target_width is None or target_width <= 0:
        raise ValueError("PX 模式必须提供用户确认的 --target-width（设备自身@2x宽度）。")
    if already_2x:
        if source_width != target_width:
            raise ValueError(
                f"截图标记为已是@2x，但宽度为{source_width}px，与目标{target_width}px不符；请核对元数据。"
            )
        return image.copy(), {
            "mode": "PX",
            "source_size": [source_width, source_height],
            "prepared_size": list(image.size),
            "scale": 1.0,
            "rule": "输入已是设备自身@2x，保持原尺寸",
        }

    if screenshot_scale is None or screenshot_scale <= 0:
        raise ValueError("PX 模式且截图不是@2x时，必须提供用户确认的 --screenshot-scale。")
    expected_width = source_width * 2.0 / screenshot_scale
    if not math.isclose(expected_width, target_width, rel_tol=0, abs_tol=1.1):
        raise ValueError(
            f"倍率推算的@2x宽度约为{expected_width:.1f}px，与提供的目标宽度{target_width}px不一致；请先核实。"
        )
    target_height = max(1, round(source_height * target_width / source_width))
    normalized = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
    return normalized, {
        "mode": "PX",
        "source_size": [source_width, source_height],
        "prepared_size": list(normalized.size),
        "scale": round(target_width / source_width, 8),
        "screenshot_scale": screenshot_scale,
        "rule": "按用户提供的截图倍率等比换算到设备自身@2x",
    }


def difference_candidates(
    design: Image.Image,
    device: Image.Image,
    threshold: int = 28,
    min_area: int = 36,
    max_candidates: int = 80,
) -> tuple[Image.Image, Image.Image, list[dict[str, Any]]]:
    raw_diff = ImageChops.difference(design, device)
    channels = raw_diff.split()
    strongest = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
    mask = strongest.point(lambda value: 255 if value >= threshold else 0)
    if min(mask.size) >= 5:
        mask = mask.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
    boxes = _connected_boxes(mask, min_area)
    boxes.sort(key=lambda box: (box[1], box[0], box[3] * box[2]))
    boxes = boxes[:max_candidates]

    heat = ImageEnhance.Contrast(raw_diff).enhance(4.0)
    candidates = []
    for index, (x, y, width, height) in enumerate(boxes, 1):
        issue_id = f"差异-{x}-{y}-{width}-{height}"
        candidates.append(
            {
                "id": issue_id,
                "device": "",
                "description": "像素差异候选，待人工确认；差异本身不等于缺陷。",
                "priority": "待评估",
                "status": "待确认",
                "remarks": "",
                "bbox": {"x": x, "y": y, "width": width, "height": height},
                "expected": "",
                "actual": "",
                "measurement": "",
                "recommendation": "",
                "design_basis": "",
                "kind": "像素差异候选",
            }
        )
    return Image.merge("RGB", raw_diff.split()), Image.merge("RGB", heat.split()), candidates


def _connected_boxes(mask: Image.Image, min_area: int) -> list[tuple[int, int, int, int]]:
    """Find 8-connected components using row runs to avoid a heavyweight CV dependency."""
    width, height = mask.size
    pixels = mask.load()
    parents: list[int] = []
    components: list[dict[str, int]] = []
    previous: list[tuple[int, int, int]] = []
    next_label = 0

    def root(label: int) -> int:
        while parents[label] != label:
            parents[label] = parents[parents[label]]
            label = parents[label]
        return label

    def union(left: int, right: int) -> None:
        left_root, right_root = root(left), root(right)
        if left_root != right_root:
            parents[right_root] = left_root

    for y in range(height):
        runs: list[tuple[int, int, int]] = []
        x = 0
        while x < width:
            while x < width and pixels[x, y] == 0:
                x += 1
            if x >= width:
                break
            start = x
            while x < width and pixels[x, y] != 0:
                x += 1
            end = x - 1
            overlaps = [label for p_start, p_end, label in previous if p_end >= start - 1 and p_start <= end + 1]
            if overlaps:
                label = overlaps[0]
                for other in overlaps[1:]:
                    union(label, other)
            else:
                label = next_label
                parents.append(label)
                components.append({"x0": start, "y0": y, "x1": end, "y1": y, "area": 0})
                next_label += 1
            runs.append((start, end, label))
        for start, end, label in runs:
            component = components[root(label)]
            component["x0"] = min(component["x0"], start)
            component["x1"] = max(component["x1"], end)
            component["y1"] = y
            component["area"] += end - start + 1
        previous = runs

    merged: dict[int, dict[str, int]] = {}
    for index, component in enumerate(components):
        resolved = root(index)
        if resolved not in merged:
            merged[resolved] = dict(component)
        else:
            target = merged[resolved]
            target["x0"] = min(target["x0"], component["x0"])
            target["y0"] = min(target["y0"], component["y0"])
            target["x1"] = max(target["x1"], component["x1"])
            target["y1"] = max(target["y1"], component["y1"])
            target["area"] += component["area"]
    return [
        (item["x0"], item["y0"], item["x1"] - item["x0"] + 1, item["y1"] - item["y0"] + 1)
        for item in merged.values()
        if item["area"] >= min_area
    ]


def _side_by_side(design: Image.Image, device: Image.Image) -> Image.Image:
    gap, header = 24, 36
    canvas = Image.new("RGB", (design.width + device.width + gap * 3, max(design.height, device.height) + header), (238, 240, 243))
    draw = ImageDraw.Draw(canvas)
    draw.text((gap, 10), f"Design {design.width}x{design.height}", fill=(40, 45, 52))
    draw.text((design.width + gap * 2, 10), f"App {device.width}x{device.height}", fill=(40, 45, 52))
    canvas.paste(design, (gap, header))
    canvas.paste(device, (design.width + gap * 2, header))
    return canvas


def _device_offset_x(design_width: int, device_width: int, alignment: str) -> int:
    if alignment == "left":
        return 0
    if alignment == "right":
        return design_width - device_width
    if alignment == "center":
        return (design_width - device_width) // 2
    raise ValueError(f"不支持的叠图对齐方式：{alignment}")


def _red_layer(device: Image.Image, opacity: float = OVERLAY_OPACITY) -> Image.Image:
    if not 0 < opacity <= 1:
        raise ValueError("叠图透明度必须大于0且不超过1。")
    grayscale = ImageOps.grayscale(device)
    layer = ImageOps.colorize(grayscale, black=(0, 0, 0), white=(255, 0, 0)).convert("RGBA")
    layer.putalpha(round(opacity * 255))
    return layer


def _compose_overlay(
    design: Image.Image,
    red_layer: Image.Image,
    alignment: str,
    offset_y: int,
) -> tuple[Image.Image, tuple[int, int]]:
    offset_x = _device_offset_x(design.width, red_layer.width, alignment)
    canvas = design.convert("RGBA")

    target_left = max(0, offset_x)
    target_top = max(0, offset_y)
    source_left = max(0, -offset_x)
    source_top = max(0, -offset_y)
    visible_width = min(red_layer.width - source_left, canvas.width - target_left)
    visible_height = min(red_layer.height - source_top, canvas.height - target_top)
    if visible_width > 0 and visible_height > 0:
        visible_layer = red_layer.crop((
            source_left,
            source_top,
            source_left + visible_width,
            source_top + visible_height,
        ))
        canvas.alpha_composite(visible_layer, (target_left, target_top))
    return canvas.convert("RGB"), (offset_x, offset_y)


def save_overlay_previews(
    session: Path,
    design: Image.Image,
    device: Image.Image,
    alignment: str = "left",
    offset_y: int = 0,
) -> dict[str, Any]:
    if alignment not in OVERLAY_ALIGNMENTS:
        raise ValueError(f"叠图对齐方式须为：{', '.join(OVERLAY_ALIGNMENTS)}。")
    red_layer = _red_layer(device)
    red_layer.save(session / "device-red-layer.png")
    x_offsets: dict[str, int] = {}
    for variant in OVERLAY_ALIGNMENTS:
        preview, (offset_x, _) = _compose_overlay(design, red_layer, variant, offset_y)
        preview.save(session / f"overlay-{variant}.png")
        x_offsets[variant] = offset_x
    selected = Image.open(session / f"overlay-{alignment}.png")
    try:
        selected.save(session / "overlay.png")
    finally:
        selected.close()
    return {
        "alignment": alignment,
        "offset_y": int(offset_y),
        "offset_unit": "处理后设备截图 @2x 像素",
        "opacity": OVERLAY_OPACITY,
        "red_layer": "device-red-layer.png",
        "current_preview": "overlay.png",
        "variants": {variant: f"overlay-{variant}.png" for variant in OVERLAY_ALIGNMENTS},
        "x_offsets": x_offsets,
        "canvas_size": list(design.size),
    }


def _save_preview(session: Path, design: Image.Image, device: Image.Image) -> tuple[bool, list[dict[str, Any]]]:
    save_overlay_previews(session, design, device)
    if design.size != device.size:
        _side_by_side(design, device).save(session / "side-by-side.png")
        return False, []
    _, heat, candidates = difference_candidates(design, device)
    heat.save(session / "difference-candidates.png")
    return True, candidates


def _validate_design_width(design: Image.Image, mode: str) -> None:
    if design.width != 720:
        raise ValueError(f"设计稿应为约定的@2x宽720px，当前为{design.width}px；请先确认设计导出规格。")


def prepare_session(args: argparse.Namespace) -> Path:
    design_path, device_path, session = Path(args.design), Path(args.device), Path(args.out)
    if session.exists() and any(session.iterdir()):
        raise ValueError(f"输出目录非空：{session}。每轮截图请使用新的验收目录，以免覆盖原始证据。")
    session.mkdir(parents=True, exist_ok=True)
    design_source = open_rgb(design_path)
    _validate_design_width(design_source, args.mode)
    device_source = open_rgb(device_path)
    device, scale_info = normalize_device(
        device_source, args.mode, args.target_width, args.screenshot_scale, args.already_2x
    )
    design_y = getattr(args, "design_y", None)
    if design_y is None:
        design = design_source
        design_region = {"x": 0, "y": 0, "width": design.width, "height": design.height}
    else:
        if design_y < 0:
            raise ValueError("--design-y 必须是设计稿@2x坐标中的非负纵坐标。")
        design_bottom = design_y + device.height
        if design_bottom > design_source.height:
            raise ValueError(
                f"设计稿区段 y={design_y}、高度={device.height}px 超出设计稿高度 {design_source.height}px。"
            )
        design = design_source.crop((0, design_y, design_source.width, design_bottom))
        design_region = {"x": 0, "y": design_y, "width": design.width, "height": design.height}

    inputs = session / "inputs"
    inputs.mkdir(exist_ok=True)
    design_copy = inputs / f"design-original{design_path.suffix.lower()}"
    device_copy = inputs / f"device-original{device_path.suffix.lower()}"
    shutil.copy2(design_path, design_copy)
    shutil.copy2(device_path, device_copy)
    design.save(session / "design-prepared.png")
    device.save(session / "device-prepared.png")

    comparable, candidates = _save_preview(session, design, device)
    overlay = {
        "alignment": "left",
        "offset_y": 0,
        "offset_unit": "处理后设备截图 @2x 像素",
        "opacity": OVERLAY_OPACITY,
        "red_layer": "device-red-layer.png",
        "current_preview": "overlay.png",
        "variants": {variant: f"overlay-{variant}.png" for variant in OVERLAY_ALIGNMENTS},
        "x_offsets": {
            variant: _device_offset_x(design.width, device.width, variant)
            for variant in OVERLAY_ALIGNMENTS
        },
        "canvas_size": list(design.size),
    }
    for finding in candidates:
        finding["device"] = args.device_name or "待填写"
    review = {
        "schema_version": 1,
        "page": args.page or "待填写",
        "device": args.device_name or "待填写",
        "mode": args.mode.upper(),
        "review_status": "待人工复核",
        "coordinate_unit": "处理后设备截图 @2x 像素坐标",
        "design": {
            "original": str(design_copy.relative_to(session)),
            "source_name": design_path.name,
            "prepared": "design-prepared.png",
            "source_size": list(design_source.size),
            "size": list(design.size),
            "reference_region": design_region,
        },
        "device_image": {
            "original": str(device_copy.relative_to(session)),
            "source_name": device_path.name,
            "prepared": "device-prepared.png",
            "size": list(device.size),
        },
        "normalization": scale_info,
        "overlay": overlay,
        "automatic_pixel_comparison": comparable,
        "comparison_note": (
            "两图尺寸相同，差异图仅用于定位候选；每项仍需依据设计规则人工确认。"
            if comparable else "图像尺寸不同，未执行自动像素差异比较；已生成左/右/居中红色叠图，设备图保持比例并按设计稿画布边界裁切。"
        ),
        "findings": candidates,
    }
    review_path = session / "review.json"
    review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    generate_report(session, review, args.previous_report)
    return session


def crop_annotated(image: Image.Image, bbox: dict[str, Any] | None, issue_id: str, destination: Path) -> None:
    if not bbox:
        raise ValueError(f"问题 {issue_id} 缺少 bbox；请在 review.json 中填写设备截图@2x坐标。")
    x, y = int(bbox["x"]), int(bbox["y"])
    width, height = int(bbox["width"]), int(bbox["height"])
    if width <= 0 or height <= 0:
        raise ValueError(f"问题 {issue_id} 的 bbox 宽高必须大于0。")
    image_width, image_height = image.size
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(image_width, x + width), min(image_height, y + height)
    if x0 >= x1 or y0 >= y1:
        raise ValueError(f"问题 {issue_id} 的 bbox 超出设备截图范围。")
    margin = 24
    left, top = max(0, x0 - margin), max(0, y0 - margin)
    right, bottom = min(image_width, x1 + margin), min(image_height, y1 + margin)
    crop = image.crop((left, top, right, bottom))
    draw = ImageDraw.Draw(crop)
    font = annotation_font(14)
    line_width = max(2, round(max(image_width, image_height) / 900))
    box = (x0 - left, y0 - top, x1 - left - 1, y1 - top - 1)
    draw.rectangle(box, outline=RED, width=line_width)
    label_y = max(0, box[1] - 20)
    label = issue_id[:28]
    label_bounds = draw.textbbox((0, 0), label, font=font)
    label_width = label_bounds[2] + 12
    label_height = max(18, label_bounds[3] + 6)
    draw.rectangle((box[0], label_y, box[0] + label_width, label_y + label_height), fill=RED)
    draw.text((box[0] + 6, label_y + 2), label, fill=(255, 255, 255), font=font)
    destination.parent.mkdir(parents=True, exist_ok=True)
    crop.save(destination, quality=92)


def _previous_fields(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    workbook = load_workbook(path, data_only=True)
    if "验收记录" not in workbook.sheetnames:
        return {}
    sheet = workbook["验收记录"]
    saved: dict[str, dict[str, Any]] = {}
    for row in range(2, sheet.max_row + 1):
        issue_id = sheet.cell(row, 7).value
        if issue_id:
            saved[str(issue_id)] = {
                "description": sheet.cell(row, 3).value,
                "priority": sheet.cell(row, 4).value,
                "status": sheet.cell(row, 5).value,
                "remarks": sheet.cell(row, 6).value,
            }
    return saved


def generate_report(session: Path, review: dict[str, Any], previous_report: str | None = None) -> Path:
    device_path = session / review["device_image"]["prepared"]
    device_image = open_rgb(device_path)
    existing = session / "report.xlsx"
    state_source = Path(previous_report) if previous_report else (existing if existing.exists() else None)
    saved = _previous_fields(state_source)
    findings = review.get("findings", [])
    crops_dir = session / "evidence" / "crops"

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "验收记录"
    sheet.append(VISIBLE_HEADERS + ["问题ID"])
    for index, finding in enumerate(findings, 1):
        issue_id = str(finding.get("id") or f"M-{index:03d}")
        crop_path = crops_dir / f"{index:03d}-{hashlib.sha1(issue_id.encode('utf-8')).hexdigest()[:8]}.jpg"
        bbox = finding.get("bbox") or finding.get("device_bbox")
        crop_annotated(device_image, bbox, issue_id, crop_path)
        values = {
            "description": finding.get("description") or "待填写问题描述",
            "priority": finding.get("priority") or "待评估",
            "status": finding.get("status") or "待确认",
            "remarks": finding.get("remarks") or "",
        }
        values.update(saved.get(issue_id, {}))
        row = index + 1
        sheet.cell(row, 1, finding.get("device") or review.get("device") or "待填写")
        sheet.cell(row, 3, values["description"])
        sheet.cell(row, 4, values["priority"])
        sheet.cell(row, 5, values["status"])
        sheet.cell(row, 6, values["remarks"])
        sheet.cell(row, 7, issue_id)
        embedded = SheetImage(str(crop_path))
        scale = min(190 / embedded.width, 140 / embedded.height, 1.0)
        embedded.width = max(1, int(embedded.width * scale))
        embedded.height = max(1, int(embedded.height * scale))
        sheet.add_image(embedded, f"B{row}")
        sheet.row_dimensions[row].height = 108

    header_fill = PatternFill("solid", fgColor="263746")
    header_font = Font(color="FFFFFF", bold=True)
    thin_gray = Side(style="thin", color="D5DCE2")
    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = Border(bottom=thin_gray)
    sheet.row_dimensions[1].height = 28
    for row in sheet.iter_rows(min_row=2, max_col=6):
        for cell in row:
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            cell.border = Border(bottom=thin_gray)
    for column, width in {"A": 18, "B": 30, "C": 48, "D": 13, "E": 15, "F": 30}.items():
        sheet.column_dimensions[column].width = width
    sheet.column_dimensions["G"].hidden = True
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:F{max(sheet.max_row, 1)}"
    priority_validation = DataValidation(type="list", formula1='"待评估,P0,P1,P2,P3"', allow_blank=True)
    status_validation = DataValidation(type="list", formula1='"待确认,待修复,修复中,已修复,不修复"', allow_blank=True)
    sheet.add_data_validation(priority_validation)
    sheet.add_data_validation(status_validation)
    if sheet.max_row >= 2:
        priority_validation.add(f"D2:D{sheet.max_row}")
        status_validation.add(f"E2:E{sheet.max_row}")

    detail = workbook.create_sheet("问题详情")
    detail_headers = ["问题ID", "问题类别", "影响页面/状态", "本条证据页面/状态", "设计依据", "预期", "实际", "差异/测量", "修复建议", "证据图"]
    detail.append(detail_headers)
    for index, finding in enumerate(findings, 1):
        issue_id = str(finding.get("id") or f"M-{index:03d}")
        crop_path = crops_dir / f"{index:03d}-{hashlib.sha1(issue_id.encode('utf-8')).hexdigest()[:8]}.jpg"
        detail.append([
            issue_id,
            finding.get("category") or "",
            "、".join(finding.get("affected_pages", [])) if isinstance(finding.get("affected_pages"), list) else (finding.get("affected_pages") or ""),
            finding.get("page_state") or review.get("page") or "",
            finding.get("design_basis") or "",
            finding.get("expected") or "",
            finding.get("actual") or "",
            finding.get("measurement") or "",
            finding.get("recommendation") or "",
            str(crop_path.relative_to(session)),
        ])
    for cell in detail[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for row in detail.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    for column, width in {"A": 25, "B": 20, "C": 30, "D": 30, "E": 34, "F": 34, "G": 34, "H": 24, "I": 34, "J": 32}.items():
        detail.column_dimensions[column].width = width
    detail.freeze_panes = "A2"
    detail.auto_filter.ref = f"A1:J{max(detail.max_row, 1)}"

    info = workbook.create_sheet("验收信息")
    info.append(["项目", "内容"])
    info_rows = [
        ("页面", review.get("page", "")),
        ("设备", review.get("device", "")),
        ("实现方式", review.get("mode", "")),
        ("比较坐标单位", review.get("coordinate_unit", "处理后设备截图 @2x 像素坐标")),
        ("设计稿参考区段（@2x坐标）", str(review.get("design", {}).get("reference_region", ""))),
        ("归一规则", review.get("normalization", {}).get("rule", "")),
        ("设备截图原始尺寸", str(review.get("device_image", {}).get("size", ""))),
        ("叠图对齐方式", review.get("overlay", {}).get("alignment", "left")),
        ("设备图纵向偏移（@2x像素）", review.get("overlay", {}).get("offset_y", 0)),
        ("红色图层透明度", f"{round(review.get('overlay', {}).get('opacity', OVERLAY_OPACITY) * 100)}%"),
        ("各锚点横向偏移（@2x像素）", str(review.get("overlay", {}).get("x_offsets", {}))),
        ("差异比较", review.get("comparison_note", "")),
    ]
    for row in info_rows:
        info.append(list(row))
    for cell in info[1]:
        cell.fill = header_fill
        cell.font = header_font
    info.column_dimensions["A"].width = 24
    info.column_dimensions["B"].width = 88
    for row in info.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    destination = session / "report.xlsx"
    with tempfile.NamedTemporaryFile(prefix="report-", suffix=".xlsx", dir=session, delete=False) as temp:
        temporary_path = Path(temp.name)
    try:
        workbook.save(temporary_path)
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)
    return destination


def generate_batch_report(batch_root: Path, destination: Path | None = None) -> Path:
    """Combine confirmed shared issues while retaining evidence for each screenshot."""
    batch_root = batch_root.resolve()
    if not batch_root.is_dir():
        raise ValueError(f"批次目录不存在：{batch_root}")
    review_paths = sorted(batch_root.rglob("review.json"))
    if not review_paths:
        raise ValueError(f"批次目录中没有 review.json：{batch_root}")
    destination = destination or batch_root / "问题验收汇总.xlsx"
    destination.parent.mkdir(parents=True, exist_ok=True)
    previous = _previous_fields(destination)
    progress_path = batch_root / "配对与进度.md"
    progress_sources: dict[int, tuple[str, str, str, str]] = {}
    if progress_path.is_file():
        for line in progress_path.read_text(encoding="utf-8").splitlines():
            if not line.startswith("|") or line.lstrip().startswith("|---"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) < 5 or not cells[0].isdigit():
                continue
            match = re.search(r"`([^`]+\.(?:png|jpe?g|webp))`", cells[1], re.IGNORECASE)
            if match:
                progress_sources[int(cells[0])] = (match.group(1), cells[2], cells[3], cells[4])

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "验收记录"
    sheet.append(VISIBLE_HEADERS + ["记录键"])
    detail = workbook.create_sheet("问题详情")
    detail.append([
        "页面组", "问题ID", "设备", "页面/状态", "来源设备截图", "来源设计稿", "问题类别",
        "设计依据", "预期", "实际", "差异/测量", "修复建议", "设备截图@2x坐标", "局部证据图", "验收目录",
    ])
    coverage = workbook.create_sheet("截图清单")
    coverage.append(["序号", "设备", "来源设备截图", "页面/可见状态", "对应设计稿", "已登记问题数", "验收状态", "并排对照图", "红色叠图", "验收目录", "备注"])

    row = 2
    shared_rows: dict[str, dict[str, Any]] = {}
    represented_sources: set[int] = set()
    for review_path in review_paths:
        session = review_path.parent.resolve()
        review = load_review(session)
        findings = review.get("findings", [])
        session_key = session.relative_to(batch_root).as_posix()
        session_prefix = session.name.split("-", 1)[0]
        progress_entry = progress_sources.get(int(session_prefix)) if session_prefix.isdigit() else None
        if session_prefix.isdigit() and progress_entry:
            represented_sources.add(int(session_prefix))
        source_file = (review.get("device_image", {}).get("source_name")
                       or (progress_entry[0] if progress_entry else "")
                       or review.get("device_image", {}).get("original", ""))
        design_file = (review.get("design", {}).get("source_name")
                       or (progress_entry[1] if progress_entry else "")
                       or review.get("design", {}).get("original", ""))
        source_name = f"{session_key}/{source_file}" if source_file else session_key
        design_name = f"{session_key}/{design_file}" if design_file and not design_file.startswith("Figma ") else design_file or session_key
        review_status = review.get("review_status") or (progress_entry[2] if progress_entry else "") or (
            f"待人工复核（含{len(findings)}条问题记录）" if findings else "待人工验收确认（当前无问题记录）"
        )
        preview = session / "side-by-side.png"
        overlay_preview = session / "overlay.png"
        coverage.append([
            int(session_prefix) if session_prefix.isdigit() else "",
            review.get("device", ""),
            source_name,
            review.get("page", ""),
            design_name,
            len(findings),
            review_status,
            preview.relative_to(batch_root).as_posix() if preview.is_file() else "未生成并排图",
            overlay_preview.relative_to(batch_root).as_posix() if overlay_preview.is_file() else "未生成红色叠图",
            session_key,
            "",
        ])
        if preview.is_file():
            coverage.cell(coverage.max_row, 8).hyperlink = preview.relative_to(batch_root).as_posix()
        if overlay_preview.is_file():
            coverage.cell(coverage.max_row, 9).hyperlink = overlay_preview.relative_to(batch_root).as_posix()
        if not findings:
            continue
        device_image = open_rgb(session / review["device_image"]["prepared"])
        session_fields = _previous_fields(session / "report.xlsx")
        crops_dir = session / "evidence" / "crops"
        for index, finding in enumerate(findings, 1):
            issue_id = str(finding.get("id") or f"M-{index:03d}")
            shared_issue_id = str(finding.get("shared_issue_id") or "").strip()
            display_id = shared_issue_id or issue_id
            local_record_key = f"{session_key}::{issue_id}"
            record_key = f"shared::{shared_issue_id}" if shared_issue_id else local_record_key
            crop_path = crops_dir / f"{index:03d}-{hashlib.sha1(issue_id.encode('utf-8')).hexdigest()[:8]}.jpg"
            crop_annotated(device_image, finding.get("bbox") or finding.get("device_bbox"), display_id, crop_path)

            page_group = finding.get("page_group") or display_id.split("-", 1)[0]
            page = finding.get("page_state") or review.get("page", "")
            source_description = str(finding.get("description") or "待填写问题描述")
            values = {
                "description": source_description,
                "priority": finding.get("priority") or "待评估",
                "status": finding.get("status") or "待确认",
                "remarks": finding.get("remarks") or "",
            }
            values.update(session_fields.get(issue_id, {}))
            values.update(previous.get(record_key, previous.get(local_record_key, {})))
            description = re.sub(r"\s*· 来源截图：.*$", "", str(values["description"]))
            for labeled_id in (issue_id, display_id):
                prefix_pattern = re.compile(r"^\[" + re.escape(labeled_id) + r"(?: · [^\]]*)?\]\s*")
                while prefix_pattern.match(description):
                    description = prefix_pattern.sub("", description, count=1)
            values["description"] = description
            device_name = finding.get("device") or review.get("device") or "待填写"
            if shared_issue_id and record_key in shared_rows:
                grouped = shared_rows[record_key]
                if grouped["source_description"] != source_description or grouped["values"] != values:
                    raise ValueError(f"共享问题 {shared_issue_id} 的描述、优先级、状态或备注不一致，请先核对。")
                if device_name not in grouped["devices"]:
                    grouped["devices"].append(device_name)
                if source_name not in grouped["sources"]:
                    grouped["sources"].append(source_name)
                sheet.cell(grouped["row"], 1, "、".join(grouped["devices"]))
                sheet.cell(grouped["row"], 3, f"[{display_id}] {description} · 来源截图：{'、'.join(grouped['sources'])}")
            else:
                sheet.cell(row, 1, device_name)
                sheet.cell(row, 3, f"[{display_id}] {description} · 来源截图：{source_name}")
                sheet.cell(row, 4, values["priority"])
                sheet.cell(row, 5, values["status"])
                sheet.cell(row, 6, values["remarks"])
                sheet.cell(row, 7, record_key)
                embedded = SheetImage(str(crop_path))
                scale = min(190 / embedded.width, 140 / embedded.height, 1.0)
                embedded.width = max(1, int(embedded.width * scale))
                embedded.height = max(1, int(embedded.height * scale))
                sheet.add_image(embedded, f"B{row}")
                sheet.row_dimensions[row].height = 108
                if shared_issue_id:
                    shared_rows[record_key] = {
                        "row": row, "devices": [device_name], "sources": [source_name],
                        "source_description": source_description, "values": values,
                    }
                row += 1

            bbox = finding.get("bbox") or finding.get("device_bbox") or {}
            detail.append([
                page_group,
                display_id,
                finding.get("device") or review.get("device") or "待填写",
                page,
                source_name,
                design_name,
                finding.get("category") or "",
                finding.get("design_basis") or "",
                finding.get("expected") or "",
                finding.get("actual") or "",
                finding.get("measurement") or "",
                finding.get("recommendation") or "",
                ", ".join(str(bbox.get(key, "")) for key in ("x", "y", "width", "height")),
                crop_path.relative_to(batch_root).as_posix(),
                session_key,
            ])

    for sequence, (source_file, design_ref, status, note) in sorted(progress_sources.items()):
        if sequence in represented_sources:
            continue
        issue_ids = re.findall(r"\b[A-Z]{1,8}\d{0,3}-\d{1,3}\b", note)
        if issue_ids:
            status = f"待补截图证据（进度记录关联 {', '.join(issue_ids)}）"
            note = f"进度文档记录此图的问题归入 {', '.join(issue_ids)}，但当前批次没有原始设备图和独立对照证据，未生成问题证据行。"
        coverage.append([
            sequence,
            "",
            source_file,
            design_ref,
            design_ref,
            len(issue_ids),
            status,
            "未生成并排图",
            "未生成红色叠图",
            "未建立独立验收目录",
            note,
        ])

    coverage_rows = []
    for row_index in range(2, coverage.max_row + 1):
        values = [coverage.cell(row_index, column).value for column in range(1, 12)]
        links = {
            column: coverage.cell(row_index, column).hyperlink.target
            for column in (8, 9)
            if coverage.cell(row_index, column).hyperlink
        }
        coverage_rows.append((values, links))
    coverage_rows.sort(key=lambda record: (int(record[0][0]) if str(record[0][0]).isdigit() else 10**9))
    if coverage.max_row > 1:
        coverage.delete_rows(2, coverage.max_row - 1)
    for values, links in coverage_rows:
        coverage.append(values)
        for column, link in links.items():
            coverage.cell(coverage.max_row, column).hyperlink = link

    header_fill = PatternFill("solid", fgColor="263746")
    header_font = Font(color="FFFFFF", bold=True)
    thin_gray = Side(style="thin", color="D5DCE2")
    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = Border(bottom=thin_gray)
    for cells in sheet.iter_rows(min_row=2, max_col=6):
        for cell in cells:
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            cell.border = Border(bottom=thin_gray)
    sheet.row_dimensions[1].height = 30
    for column, width in {"A": 16, "B": 32, "C": 54, "D": 13, "E": 15, "F": 42}.items():
        sheet.column_dimensions[column].width = width
    sheet.column_dimensions["G"].hidden = True
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:F{max(sheet.max_row, 1)}"
    priority_validation = DataValidation(type="list", formula1='"待评估,P0,P1,P2,P3"', allow_blank=True)
    status_validation = DataValidation(type="list", formula1='"待确认,待修复,修复中,已修复,不修复"', allow_blank=True)
    sheet.add_data_validation(priority_validation)
    sheet.add_data_validation(status_validation)
    if sheet.max_row >= 2:
        priority_validation.add(f"D2:D{sheet.max_row}")
        status_validation.add(f"E2:E{sheet.max_row}")

    for cell in detail[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for cells in detail.iter_rows(min_row=2):
        for cell in cells:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    detail_widths = [16, 18, 16, 28, 32, 32, 18, 36, 36, 36, 26, 36, 22, 42, 36]
    for index, width in enumerate(detail_widths, 1):
        detail.column_dimensions[chr(64 + index)].width = width
    detail.freeze_panes = "A2"
    detail.auto_filter.ref = f"A1:O{max(detail.max_row, 1)}"

    for cell in coverage[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for cells in coverage.iter_rows(min_row=2):
        for cell in cells:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    for index, width in enumerate([10, 16, 46, 30, 46, 16, 38, 48, 48, 36, 64], 1):
        coverage.column_dimensions[chr(64 + index)].width = width
    coverage.freeze_panes = "A2"
    coverage.auto_filter.ref = f"A1:K{max(coverage.max_row, 1)}"

    with tempfile.NamedTemporaryFile(prefix="batch-report-", suffix=".xlsx", dir=destination.parent, delete=False) as temp:
        temporary_path = Path(temp.name)
    try:
        workbook.save(temporary_path)
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)
    return destination


def load_review(session: Path) -> dict[str, Any]:
    path = session / "review.json"
    if not path.exists():
        raise ValueError(f"找不到 {path}。请先运行 compare。")
    review = json.loads(path.read_text(encoding="utf-8"))
    if review.get("schema_version") != 1:
        raise ValueError("review.json schema_version 不受支持。")
    return review


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="移动端 Figma/App 截图准备、差异定位与可编辑验收报告")
    commands = parser.add_subparsers(dest="command", required=True)
    compare = commands.add_parser("compare", help="归一截图并创建首轮验收目录")
    compare.add_argument("--design", required=True, help="Figma @2x 设计稿图片")
    compare.add_argument("--device", required=True, help="用户手动提供的设备原始截图")
    compare.add_argument("--mode", choices=["rem", "px"], required=True, help="按项目约定指定实现方式")
    compare.add_argument("--out", required=True, help="新的验收目录")
    compare.add_argument("--device-name", default="", help="人工确认的设备名称")
    compare.add_argument("--page", default="", help="可选的页面/可见状态标签，可由Codex识别后填写，无需用户逐页提供")
    compare.add_argument("--design-y", type=int, help="长设计稿中参考区段的起始纵坐标；区段高度自动取处理后设备截图高度")
    compare.add_argument("--target-width", type=int, help="PX模式下设备自身@2x宽度")
    compare.add_argument("--screenshot-scale", type=float, help="PX输入截图的像素/逻辑像素倍率")
    compare.add_argument("--already-2x", action="store_true", help="明确声明PX截图已是设备自身@2x")
    compare.add_argument("--previous-report", help="从旧验收表带入相同问题ID的描述、优先级、状态与备注")

    align = commands.add_parser("align", help="调整验收叠图的水平锚点和纵向偏移")
    align.add_argument("--session", required=True, help="compare 创建的验收目录")
    align.add_argument("--alignment", choices=OVERLAY_ALIGNMENTS, help="left、right 或 center；省略时沿用当前值")
    align.add_argument("--offset-y", type=int, help="设备图相对设计稿的纵向偏移，正数下移、负数上移；省略时沿用当前值")

    report = commands.add_parser("report", help="根据 review.json 重建可编辑 Excel")
    report.add_argument("--session", required=True, help="compare 创建的验收目录")
    report.add_argument("--previous-report", help="从其他验收表带入相同问题ID的手动字段")
    batch_report = commands.add_parser("batch-report", help="将本批次各页面问题合并为一份可编辑 Excel")
    batch_report.add_argument("--root", required=True, help="包含多个页面验收目录的批次目录")
    batch_report.add_argument("--out", help="汇总表输出路径；默认写入批次目录/问题验收汇总.xlsx")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "compare":
            session = prepare_session(args)
            print(f"验收目录：{session}")
            print(f"可编辑报告：{session / 'report.xlsx'}")
            print(f"问题清单：{session / 'review.json'}")
            review = load_review(session)
            if review["automatic_pixel_comparison"]:
                print(f"差异候选：{len(review['findings'])} 项。请人工确认后补充说明。")
            else:
                print("两图尺寸不同，已生成三种红色叠图和并排图；未运行自动像素差异比较，请按适配规则人工复核。")
        elif args.command == "align":
            session = Path(args.session)
            review = load_review(session)
            design = open_rgb(session / review["design"]["prepared"])
            device = open_rgb(session / review["device_image"]["prepared"])
            previous = review.get("overlay", {})
            alignment = args.alignment or previous.get("alignment", "left")
            offset_y = args.offset_y if args.offset_y is not None else int(previous.get("offset_y", 0))
            review["overlay"] = save_overlay_previews(session, design, device, alignment, offset_y)
            (session / "review.json").write_text(
                json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            generate_report(session, review)
            print(f"叠图已更新：{session / 'overlay.png'}（{alignment} 对齐，纵向偏移 {offset_y}px）")
        elif args.command == "report":
            session = Path(args.session)
            review = load_review(session)
            destination = generate_report(session, review, args.previous_report)
            print(f"可编辑报告已更新：{destination}")
        else:
            destination = generate_batch_report(Path(args.root), Path(args.out) if args.out else None)
            print(f"批次问题汇总表已生成：{destination}")
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"错误：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
