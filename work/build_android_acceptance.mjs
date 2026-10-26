import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const project = path.resolve(import.meta.dirname, "..");
const session = path.join(project, "outputs/design-review/2026-10-23/麦奇说验收-安卓/01-分享页完成弹窗-逐项对位");
const review = JSON.parse(await fs.readFile(path.join(session, "review.json"), "utf8"));
const outputPath = path.join(session, "麦奇说安卓UI验收.xlsx");
const previewDir = path.join(project, "work/ui-review-quality-checks");
const fontName = "Arial";
const deviceLabel = "安卓";
const deviceCategories = ["IOS", "安卓", "鸿蒙", "PAD", "PC"];
const findings = review.findings;

if (
  !Array.isArray(findings)
  || findings.length === 0
  || findings.some((item) => typeof item?.id !== "string" || !item.id.trim())
  || new Set(findings.map((item) => item.id)).size !== findings.length
) {
  throw new Error("问题清单为空，或问题 ID 缺失/重复；已停止生成验收表。");
}

const workbook = Workbook.create();
const records = workbook.worksheets.add("验收记录");
const details = workbook.worksheets.add("问题详情");
const info = workbook.worksheets.add("验收信息");
for (const sheet of [records, details, info]) sheet.showGridLines = false;

const recordHeaders = ["设备", "设备问题截图 / 叠图", "问题描述", "优先级", "状态", "备注"];
records.getRange("A1:F1").values = [recordHeaders];
records.getRange(`A2:F${findings.length + 1}`).values = findings.map((finding) => [
  deviceLabel,
  "",
  finding.description,
  finding.priority,
  finding.status,
  "",
]);
records.getRange(`A1:F${findings.length + 1}`).format.font = { name: fontName, size: 10, color: "#24313A" };
records.getRange("A1:F1").format = {
  fill: "#263746",
  font: { name: fontName, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
};
records.getRange(`A2:F${findings.length + 1}`).format = {
  verticalAlignment: "center",
  wrapText: true,
  borders: { insideHorizontal: { style: "thin", color: "#D5DCE2" } },
};
for (const [column, width] of Object.entries({ A: 92, B: 280, C: 330, D: 88, E: 92, F: 350 })) {
  records.getRange(`${column}:${column}`).format.columnWidthPx = width;
}
records.getRange("1:1").format.rowHeightPx = 32;
records.getRange(`2:${findings.length + 1}`).format.rowHeightPx = 105;
records.freezePanes.freezeRows(1);
records.getRange(`D2:D${findings.length + 1}`).dataValidation = {
  rule: { type: "list", values: ["待评估", "P0", "P1", "P2", "P3"] },
};
records.getRange(`A2:A${findings.length + 1}`).dataValidation = {
  rule: { type: "list", values: deviceCategories },
};
records.getRange(`E2:E${findings.length + 1}`).dataValidation = {
  rule: { type: "list", values: ["待确认", "待修复", "修复中", "已修复", "不修复"] },
};

for (let index = 0; index < findings.length; index += 1) {
  const finding = findings[index];
  const bytes = await fs.readFile(path.join(session, finding.evidence));
  records.images.add({
    dataUrl: `data:image/png;base64,${bytes.toString("base64")}`,
    anchor: { from: { row: index + 1, col: 1 }, extent: { widthPx: 260, heightPx: 64 } },
  });
}

const detailHeaders = [
  "设备", "来源截图", "问题类别", "设计依据", "设计预期", "设备表现", "测量/差异",
  "建议处理", "设备截图 bbox @2x", "设计稿区域 bbox", "问题截图证据",
];
details.getRange("A1:K1").values = [detailHeaders];
details.getRange(`A2:K${findings.length + 1}`).values = findings.map((finding) => [
  deviceLabel,
  finding.source_screenshot,
  finding.category,
  finding.design_basis,
  finding.expected,
  finding.actual,
  finding.measurement,
  finding.recommendation,
  [finding.bbox.x, finding.bbox.y, finding.bbox.width, finding.bbox.height].join(", "),
  [finding.design_bbox.x, finding.design_bbox.y, finding.design_bbox.width, finding.design_bbox.height].join(", "),
  "",
]);
details.getRange(`A2:A${findings.length + 1}`).dataValidation = {
  rule: { type: "list", values: deviceCategories },
};
details.getRange(`A1:K${findings.length + 1}`).format.font = { name: fontName, size: 10, color: "#24313A" };
details.getRange("A1:K1").format = {
  fill: "#263746",
  font: { name: fontName, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
};
details.getRange(`A2:K${findings.length + 1}`).format = {
  verticalAlignment: "top",
  wrapText: true,
  borders: { insideHorizontal: { style: "thin", color: "#D5DCE2" } },
};
const detailWidths = [88, 120, 145, 260, 250, 280, 210, 260, 150, 150, 280];
for (let index = 0; index < detailWidths.length; index += 1) {
  details.getRangeByIndexes(0, index, findings.length + 1, 1).format.columnWidthPx = detailWidths[index];
}
details.getRange("1:1").format.rowHeightPx = 34;
details.getRange(`2:${findings.length + 1}`).format.rowHeightPx = 188;
details.freezePanes.freezeRows(1);

for (let index = 0; index < findings.length; index += 1) {
  const finding = findings[index];
  const bytes = await fs.readFile(path.join(session, finding.evidence));
  details.images.add({
    dataUrl: `data:image/png;base64,${bytes.toString("base64")}`,
    anchor: { from: { row: index + 1, col: 10 }, extent: { widthPx: 260, heightPx: 64 } },
  });
}

const statusCounts = findings.reduce((counts, finding) => {
  counts[finding.status] = (counts[finding.status] ?? 0) + 1;
  return counts;
}, {});
const infoRows = [
  ["验收项", "本轮信息"],
  ["页面组", "P14｜分享页/完成弹窗"],
  ["设备截图", "image 50.png；安卓设备，截图本身为2倍图"],
  ["处理尺寸", "设备原图720×1560px，按PX模式保持原尺寸，不缩放"],
  ["设计稿", "Figma原设计节点6:1859；设计画板720×1560px"],
  ["验收页面", review.design.figma_url],
  ["弹窗对位", "设备弹窗从原图裁出600×942px；设计弹窗600×910px；两张弹窗裁图顶部对齐，不使用状态栏或屏幕顶边"],
  ["逐项方法", "徽章、吉祥物、标题、统计项和身份条分别用设备裁片对位；红色50%只覆盖当前对应裁片，不缩放、不改原图"],
  ["动态数字", "设计稿标注为可配置的数字只核字体样式，不比较具体数值"],
  ["问题统计", `共${findings.length}项；待修复${statusCounts["待修复"] ?? 0}项；待确认${statusCounts["待确认"] ?? 0}项`],
  ["待确认事项", "确认设备与设计是否为同一业务状态；由设计方在目标字体环境确认标题及统计标签字形"],
  ["覆盖范围", "本轮只检查用户提供的分享页完成弹窗截图，不推断其他页面、隐藏业务条件或未截图状态"],
  ["证据规则", "每条问题都嵌入同一来源设备截图裁片及设计区域叠图；详细 bbox 使用设备原图@2x像素坐标"],
];
info.getRange(`A1:B${infoRows.length}`).values = infoRows;
info.getRange(`A1:B${infoRows.length}`).format = {
  font: { name: fontName, size: 10, color: "#24313A" },
  verticalAlignment: "center",
  wrapText: true,
  borders: { insideHorizontal: { style: "thin", color: "#D5DCE2" } },
};
info.getRange("A1:B1").format = {
  fill: "#263746",
  font: { name: fontName, size: 10, bold: true, color: "#FFFFFF" },
  verticalAlignment: "center",
  horizontalAlignment: "center",
};
info.getRange("A:A").format.columnWidthPx = 160;
info.getRange("B:B").format.columnWidthPx = 950;
info.getRange("1:1").format.rowHeightPx = 32;
info.getRange(`2:${infoRows.length}`).format.rowHeightPx = 48;
info.freezePanes.freezeRows(1);

workbook.recalculate();
const workbookOutput = await SpreadsheetFile.exportXlsx(workbook);
await workbookOutput.save(outputPath);
await fs.mkdir(previewDir, { recursive: true });

for (const [sheetName, range, fileName] of [
  ["验收记录", `A1:F${findings.length + 1}`, "android-popup-验收记录.png"],
  ["问题详情", `A1:K${findings.length + 1}`, "android-popup-问题详情.png"],
  ["验收信息", `A1:B${infoRows.length}`, "android-popup-验收信息.png"],
]) {
  const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}

const outputBytes = await fs.stat(outputPath);
const reopened = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const verification = await reopened.inspect({ kind: "sheet,drawing,region", maxChars: 6500, tableMaxRows: 8, tableMaxCols: 12 });
await fs.writeFile(path.join(previewDir, "麦奇说安卓UI验收-P14-N07.xlsx.inspect.ndjson"), verification.ndjson);
console.log(JSON.stringify({
  outputPath,
  bytes: outputBytes.size,
  issueCount: findings.length,
  statusCounts,
  embeddedEvidenceImages: findings.length * 2,
  sheets: [records.name, details.name, info.name],
  verification: verification.ndjson,
}, null, 2));
