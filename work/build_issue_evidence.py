#!/usr/bin/env python3
"""Generate local, annotated screenshot evidence and the final comparison preview."""

import json
import sys
from pathlib import Path

from PIL import Image, ImageOps

PROJECT = Path(__file__).resolve().parents[1]
SESSION = PROJECT / "outputs/design-review/2026-10-21/麦奇说验收-安卓/01-分享页完成弹窗"
sys.path.insert(0, str(PROJECT / "scripts"))
import ui_review


def main() -> None:
    review_path = SESSION / "review.json"
    review = json.loads(review_path.read_text(encoding="utf-8"))
    design = ui_review.open_rgb(SESSION / review["design"]["prepared"])
    device = ui_review.open_rgb(SESSION / review["device_image"]["prepared"])

    review["overlay"] = ui_review.save_overlay_previews(
        SESSION, design, device, alignment="left", offset_y=-8
    )
    ui_review._side_by_side(design, device).save(SESSION / "side-by-side.png")

    crops = SESSION / "evidence" / "crops"
    for finding in review["findings"]:
        issue_id = finding["id"]
        destination = crops / f"{issue_id}.jpg"
        ui_review.crop_annotated(device, finding["bbox"], issue_id, destination)
        with Image.open(destination) as image:
            contained = ImageOps.contain(image.convert("RGB"), (320, 200))
            canvas = Image.new("RGB", (320, 200), "white")
            canvas.paste(contained, ((320 - contained.width) // 2, (200 - contained.height) // 2))
            canvas.save(destination, quality=92)
        finding["evidence"] = destination.relative_to(SESSION).as_posix()

    review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"生成 {len(review['findings'])} 张局部证据图")


if __name__ == "__main__":
    main()
