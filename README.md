# Figma / App 视觉验收

本项目根据 Figma 设计稿和设备截图做静态 UI 验收，输出逐项问题证据、Markdown 汇总和可编辑表格。像素差异只提供线索，必须人工逐项确认。

核心 Skill：[`ui-design-review`](.agents/skills/ui-design-review/SKILL.md)

## 验收前

- 先阅读工作区根目录的 `问题与报错日志.md` 和 `.agents/skills/ui-design-review/SKILL.md`。可复用的问题、原因和解决方法记入这份 workspace 中心日志，与每轮变化的钉钉链接分开保存；不自动复制到线上验收文档。
- 收集 Figma 链接/设计图、设备截图、设备分类、REM/PX 方式；PX 还要用户确认设备自身 @2x 宽度和截图倍率，不按机型猜倍率。
- Figma 画板以 720px 作为项目 @2x 基准。保留原图，不覆盖；每轮结果放 `outputs/design-review/<日期>/<页面-设备>/`。
- 忽略截图中的“测试 ▶”“调试”“LiveHybrid”悬浮标记；若其遮挡界面，找同设备、同页面、同状态的补充截图核对并记录来源。无可靠补图的遮挡区域记为未验收，不当作缺陷。
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

多设备出现经确认的同一问题时，汇总表只保留一行，设备列列出所有受影响设备。各设备证据仍保留在“问题详情”和“截图清单”；在相应 `review.json` 条目中填写相同的 `shared_issue_id` 后，`batch-report` 才会合并，不按相同文案自动去重。

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

## 证据辅助脚本

脚本只使用仓库已声明的 Pillow、openpyxl 依赖，不需要 `@oai/artifact-tool`。先运行 `python -m pip install -r requirements.txt`，再用当前 Python 环境运行：

```bash
python scripts/label_evidence_header.py --input evidence/P15-04.png --output evidence/P15-04-labeled.png --label "P15-04 正文至按钮组间距，设计稿40px、设备截图约94px，相差约54px"
python scripts/add_review_note.py --workbook report.xlsx --sheet 验收记录 --cell F6 --note "设计稿正确间距见附图。" --image evidence/design-devmode-spacing.png --image-cell F7 --max-width-px 280 --output report-with-note.xlsx
```

标题脚本会在证据图上方新增标题条，不覆盖原图内容；工作簿脚本只写入新 `.xlsx` 副本，备注文字和图片位置都可按本轮表格调整。两个脚本都接受本机路径，不依赖本项目的 `outputs/` 或某台设备的文件名；中文字体可通过 `--font` 指定。

表格列名固定为「设备、截图、问题描述、优先级、验收状态、备注」，不使用近义替代标题；问题行状态统一为「待修复」。按设备图红框数量写问题描述，文案差异明确写“文案内容”，不使用笼统话术。设备分类使用 `IOS`、`安卓`、`鸿蒙`、`PAD`、`PC`；问题 ID 列不展示，备注未要求时留空。同次归档的 Excel、JSON 和 Markdown 数量、截图、bbox 与状态必须一致；钉钉后续人工修改不反向覆盖到旧快照。无明确差异或未处理的截图单独记录覆盖情况。

## 钉钉协作与人工编辑保护

钉钉表格作为用户指定验收项目的协作主表；本地原图和测量证据仍保存在项目目录。Excel、Markdown 是带导出时间的归档快照，导出后可能与主表不同，不反向用旧快照覆盖主表。

- 人工修改过的单元格永久停止自动更新，只有用户明确解除保护后才可恢复；人工清空、修改格式或改回旧值也不自动解除。
- 保护以稳定问题 ID 和字段跟踪，排序或插行不改变归属；首次接入的已有单元格默认保护，不整表替换或清空重建。
- 后续更新前须有可靠编辑历史、自动写入基线和并发校验，逐单元格回读验证；仅对比当前值不能识别“改过又改回”。无法确认时跳过已有单元格，仅在确认空闲的表尾追加新问题。
- 单元格保护是接入程序的写入规则，不会禁止团队继续编辑。未验证实际读写、人工保护与回读结果前，不宣称钉钉自动同步已接通。
- 访问范围仅限用户明确提供的验收文档，不读取其他文档、聊天或通讯录；实际文档链接保存在项目本地配置，不写入公共仓库。

## 验证

```bash
.venv/bin/python -m unittest discover -s tests -v
```
