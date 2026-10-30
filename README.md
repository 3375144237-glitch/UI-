# Figma / App 视觉验收

本项目用 Figma 设计稿和设备截图做静态 UI 验收。完整流程与判定规则见 [`ui-design-review` Skill](.agents/skills/ui-design-review/SKILL.md)，文案分类见 [`COPY-CLASSIFICATION.md`](.agents/skills/ui-design-review/COPY-CLASSIFICATION.md)。创建新文件或验收目录前，先读 workspace 根目录的《问题与报错日志.md》。

## 输入与输出

- 设计图可放 `screenshots/design/`，设备图可放 `screenshots/device/`，也可向命令传入其他本机路径；原图保持不变。
- 每轮输出放 `outputs/design-review/<日期>/<页面-设备>/`，包含输入副本、归一图、叠图、`review.json` 和报告。`work/` 存临时分析与草稿。
- 本项目设计稿以 720px 宽为 @2x 基准。REM 等比缩放设备图到 720px；PX 使用用户确认的设备 @2x 目标宽度和截图倍率。缺少这些信息时按 Skill 记录未验收范围。

## 使用命令

安装依赖：`.venv/bin/python -m pip install -r requirements.txt`。

```bash
.venv/bin/python scripts/ui_review.py compare --design screenshots/design/page.png --device screenshots/device/page.png --mode rem --device-name "设备名" --page "首页/默认态" --out outputs/design-review/YYYY-MM-DD/首页-设备
.venv/bin/python scripts/ui_review.py compare --design screenshots/design/page.png --device screenshots/device/page.png --mode px --target-width 720 --already-2x --device-name "设备名" --page "首页/默认态" --out outputs/design-review/YYYY-MM-DD/首页-设备
.venv/bin/python scripts/ui_review.py align --session outputs/design-review/YYYY-MM-DD/首页-设备 --alignment left --offset-y 0
.venv/bin/python scripts/ui_review.py report --session outputs/design-review/YYYY-MM-DD/首页-设备
.venv/bin/python scripts/ui_review.py batch-report --root outputs/design-review/YYYY-MM-DD/批次名称
```

PX 截图不是设备自身 @2x 时，以用户确认的倍率替换 `--already-2x` 为 `--screenshot-scale <倍率>`。长设计稿可给 `compare` 增加 `--design-y <设计稿@2x纵坐标>`。`compare` 每次只处理一组已配对图片；像素差异和整屏叠图仅作定位线索，结论须按 Skill 逐元素复核。

## 可选辅助脚本

`label_evidence_header.py` 给证据图添加上方标题条；`add_review_note.py` 在现有工作簿副本中添加备注或设计依据截图。两者都需显式输出新文件，不覆盖来源。

```bash
.venv/bin/python scripts/label_evidence_header.py --input evidence/problem.png --output evidence/problem-labeled.png --label "问题说明"
.venv/bin/python scripts/add_review_note.py --workbook report.xlsx --sheet 验收记录 --cell F6 --note "设计依据见附图" --image evidence/design-spacing.png --image-cell F7 --output report-with-note.xlsx
```

运行测试：`.venv/bin/python -m unittest discover -s tests -v`。
