#!/usr/bin/env python3
"""Build image evidence for one manually reviewed Figma/App screenshot pair."""

import json
import shutil
import sys
from pathlib import Path

from PIL import Image

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))
import ui_review


DEVICE = Path("/Users/jiujiu/Downloads/image 50.png")
DESIGN = PROJECT / "work/figma-share-page.png"
SESSION = PROJECT / "outputs/design-review/2026-10-21/麦奇说验收-安卓/01-分享页完成弹窗"


def main() -> None:
    SESSION.mkdir(parents=True, exist_ok=True)
    inputs = SESSION / "inputs"
    inputs.mkdir(exist_ok=True)
    shutil.copy2(DEVICE, inputs / "device-original.png")
    shutil.copy2(DESIGN, inputs / "design-original.png")

    design = ui_review.open_rgb(DESIGN)
    source = ui_review.open_rgb(DEVICE)
    device, normalization = ui_review.normalize_device(source, "px", 720, None, True)
    if design.size != device.size:
        raise ValueError(f"设计与设备图尺寸不同：{design.size} / {device.size}")

    design.save(SESSION / "design-prepared.png")
    device.save(SESSION / "device-prepared.png")
    _, candidates = ui_review._save_preview(SESSION, design, device)
    Image.blend(design, device, 0.5).save(SESSION / "overlay-neutral.png")

    review = {
        "schema_version": 1,
        "page": "分享页/完成弹窗",
        "page_group": "P14",
        "device": "安卓",
        "mode": "PX",
        "review_status": "已验收，发现差异",
        "coordinate_unit": "处理后设备截图 @2x 像素坐标",
        "design": {
            "original": "inputs/design-original.png",
            "source_name": "麦奇说（UI测试验收）/ 分享页 (6:1859)",
            "prepared": "design-prepared.png",
            "source_size": list(design.size),
            "size": list(design.size),
            "reference_region": {"x": 0, "y": 0, "width": design.width, "height": design.height},
            "figma_node": "6:1859",
        },
        "device_image": {
            "original": "inputs/device-original.png",
            "source_name": DEVICE.name,
            "prepared": "device-prepared.png",
            "size": list(device.size),
        },
        "normalization": normalization,
        "overlay": {
            "alignment": "left",
            "offset_y": 0,
            "offset_unit": "处理后设备截图 @2x 像素",
            "opacity": ui_review.OVERLAY_OPACITY,
            "red_layer": "device-red-layer.png",
            "current_preview": "overlay.png",
            "variants": {key: f"overlay-{key}.png" for key in ui_review.OVERLAY_ALIGNMENTS},
            "x_offsets": {key: 0 for key in ui_review.OVERLAY_ALIGNMENTS},
            "canvas_size": list(design.size),
        },
        "automatic_pixel_comparison": True,
        "comparison_note": "像素差异候选只辅助定位；已按同尺寸 PX 红色 50% 叠图人工逐项检查。",
        "candidate_count": len(candidates),
        "findings": [],
    }
    (SESSION / "review.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(SESSION)
    print(f"尺寸：{design.width}x{design.height}，差异像素候选：{len(candidates)}")


if __name__ == "__main__":
    main()
