# Figma / App 视觉验收

本项目根据 Figma 设计稿和设备截图做静态 UI 验收，输出逐项问题证据、Markdown 汇总和可编辑表格。像素差异只提供线索，必须人工逐项确认。

## 验收前

- 先阅读工作区 `问题与报错日志.md` 和 `.agents/skills/ui-design-review/SKILL.md`。
- 收集 Figma 链接/设计图、设备截图、设备分类、REM/PX 方式；PX 还要用户确认设备自身 @2x 宽度和截图倍率，不按机型猜倍率。
- Figma 画板以 720px 作为项目 @2x 基准。保留原图，不覆盖；每轮结果放 `outputs/design-review/<日期>/<页面-设备>/`。
- 在 Figma 新建“<项目名>验收”页，原设计页保留。图片过多时分批导入，完成当前批对位、记录和证据后再导入下一批。

## 处理方式

- REM：设备图等比缩放至设计稿宽度。
- PX：按用户确认的 @2x 宽度和截图倍率处理；截图已是 @2x 时不缩放。
- 红色 50% 叠图只作定位。先左对齐、再右对齐，居中元素用中心锚点；然后把设备图裁成模块/元素，逐个移到设计稿对应位置，尽量无缝重合。不能重合时区分元素尺寸、周围间距和位置。
- 弹窗从设备图独立裁出，只对齐弹窗顶部和内部内容，不使用整屏顶部作为锚点。
- 设计稿数字属于可配置值时只核对字体样式和字号，不核对具体数字。动态内容仍检查字段、占位、换行、对齐、图片比例和裁切。

## 固定检查顺序

1. P0：大的模块、入口、核心状态或内容是否缺失。
2. P0：每个模块的尺寸、布局、样式、圆角、边框、阴影和间距。
3. P0：模块内部文案、图片、控件、数量、顺序和状态是否一致。
4. P0：图片容器、图片可见边界、icon 节点框和 icon 可见轮廓的尺寸、位置、比例和裁切。
5. P0：固定文案的内容、字体、字号、字重、行高、换行和对齐。
6. P0：设备适配；间距差超过 4px 且明显破坏布局。
7. P1：间距有差异但在 4px 内且影响较低。

瀑布流、列表、统计卡等重复模块逐实例核对，用序号、标题、图标、图片特征和行列定位；模块缺项、icon 尺寸、位置和间距分开登记。同一页面多个问题共享页面组编号但各自有独立 ID、bbox 和证据。

## 字体规则

接口能返回文字样式时记录字体家族、字重、字号、行高和文字节点。接口只返回名称或图片时，不猜字体；请提供可编辑文字图层链接或右侧 Typography 截图。文字转曲、栅格化或图片只能记“字体待确认”，仍检查字形粗细、视觉字号、行高、换行和对齐，并把估算值标明。

## 命令

```bash
.venv/bin/python scripts/ui_review.py compare --design screenshots/design/page.png --device screenshots/device/page.png --mode rem --device-name "设备名" --page "首页/默认态" --out outputs/design-review/2026-10-21/home-rem
.venv/bin/python scripts/ui_review.py compare --design screenshots/design/page.png --device screenshots/device/page.png --mode px --target-width 720 --already-2x --device-name "安卓" --page "首页/默认态" --out outputs/design-review/2026-10-21/home-px
.venv/bin/python scripts/ui_review.py align --session outputs/design-review/2026-10-21/home-px --alignment left --offset-y 0
.venv/bin/python scripts/ui_review.py report --session outputs/design-review/2026-10-21/home-px
.venv/bin/python scripts/ui_review.py batch-report --root outputs/design-review/2026-10-21/批次名称
```

每条问题在 `review.json` 中填写稳定 ID、原始设备截图 @2x `bbox`、类别、描述、设计依据、预期、实际、测量和建议。问题证据必须同时包含设计区域、同源设备原图裁片和移动后的红色 50% 对位图。

表格记录使用设备分类 `IOS`、`安卓`、`鸿蒙`、`PAD`、`PC`；问题ID列按用户要求不展示，备注未要求时留空。Excel、JSON 和 Markdown 的问题数量、来源截图、bbox 和状态必须一致。无明确差异、待确认和未处理截图都要单独记录。

## 验证

```bash
.venv/bin/python -m unittest discover -s tests -v
```
