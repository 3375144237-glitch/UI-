import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const project = path.resolve(import.meta.dirname, "..");
const batch = path.join(project, "outputs/design-review/2026-10-21/麦奇说验收-安卓");
const session = path.join(batch, "01-分享页完成弹窗");
const review = JSON.parse(await fs.readFile(path.join(session, "review.json"), "utf8"));
const outputPath = path.join(batch, "问题验收汇总.xlsx");
const qualityDir = path.join(project, "work/ui-review-quality-checks");
const fontName = "Arial";

const workbook = Workbook.create();
const records = workbook.worksheets.add("验收记录");
const details = workbook.worksheets.add("问题详情");
const info = workbook.worksheets.add("验收信息");

for (const sheet of [records, details, info]) sheet.showGridLines = false;

const recordHeaders = ["设备", "截图证据", "问题描述", "优先级", "修复状态", "备注"];
records.getRange("A1:F1").values = [recordHeaders];
records.getRange(`A2:F${review.findings.length + 1}`).values = review.findings.map((finding) => [
  finding.device,
  "",
  `[${finding.id}] ${finding.description}`,
  finding.priority,
  finding.status,
  finding.remarks ?? "",
]);
records.getRange(`A1:F${review.findings.length + 1}`).format.font = { name: fontName, size: 10, color: "#24313A" };
records.getRange("A1:F1").format = {
  fill: "#263746",
  font: { name: fontName, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
};
records.getRange(`A2:F${review.findings.length + 1}`).format = {
  verticalAlignment: "center",
  wrapText: true,
  borders: { insideHorizontal: { style: "thin", color: "#D5DCE2" } },
};
records.getRange("A:A").format.columnWidthPx = 74;
records.getRange("B:B").format.columnWidthPx = 170;
records.getRange("C:C").format.columnWidthPx = 300;
records.getRange("D:D").format.columnWidthPx = 82;
records.getRange("E:E").format.columnWidthPx = 92;
records.getRange("F:F").format.columnWidthPx = 230;
records.getRange("1:1").format.rowHeightPx = 30;
records.getRange(`2:${review.findings.length + 1}`).format.rowHeightPx = 110;
records.freezePanes.freezeRows(1);
records.getRange(`D2:D${review.findings.length + 1}`).dataValidation = {
  rule: { type: "list", values: ["待评估", "P0", "P1", "P2", "P3"] },
};
records.getRange(`E2:E${review.findings.length + 1}`).dataValidation = {
  rule: { type: "list", values: ["待确认", "待修复", "修复中", "已修复", "不修复"] },
};

for (let i = 0; i < review.findings.length; i += 1) {
  const finding = review.findings[i];
  const evidencePath = path.join(session, finding.evidence);
  const bytes = await fs.readFile(evidencePath);
  const dataUrl = `data:image/jpeg;base64,${bytes.toString("base64")}`;
  records.images.add({
    dataUrl,
    anchor: { from: { row: i + 1, col: 1 }, extent: { widthPx: 160, heightPx: 100 } },
  });
}

const detailHeaders = ["问题ID", "类别", "设计依据", "预期", "实际", "测量/差异", "修复建议", "设备截图@2x坐标", "截图证据"];
details.getRange("A1:I1").values = [detailHeaders];
details.getRange(`A2:I${review.findings.length + 1}`).values = review.findings.map((finding) => [
  finding.id,
  finding.category,
  finding.design_basis,
  finding.expected,
  finding.actual,
  finding.measurement,
  finding.recommendation,
  [finding.bbox.x, finding.bbox.y, finding.bbox.width, finding.bbox.height].join(", "),
  "",
]);
details.getRange(`A1:I${review.findings.length + 1}`).format.font = { name: fontName, size: 10, color: "#24313A" };
details.getRange("A1:I1").format = {
  fill: "#263746",
  font: { name: fontName, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
};
details.getRange(`A2:I${review.findings.length + 1}`).format = {
  verticalAlignment: "top",
  wrapText: true,
  borders: { insideHorizontal: { style: "thin", color: "#D5DCE2" } },
};
const detailWidths = [88, 130, 220, 220, 230, 180, 235, 145, 130];
for (let i = 0; i < detailWidths.length; i += 1) {
  details.getRangeByIndexes(0, i, review.findings.length + 1, 1).format.columnWidthPx = detailWidths[i];
}
details.getRange("1:1").format.rowHeightPx = 34;
details.getRange(`2:${review.findings.length + 1}`).format.rowHeightPx = 170;
details.freezePanes.freezeRows(1);

for (let i = 0; i < review.findings.length; i += 1) {
  const bytes = await fs.readFile(path.join(session, review.findings[i].evidence));
  details.images.add({
    dataUrl: `data:image/jpeg;base64,${bytes.toString("base64")}`,
    anchor: { from: { row: i + 1, col: 8 }, extent: { widthPx: 120, heightPx: 75 } },
  });
}

const counts = review.findings.reduce((result, finding) => {
  result[finding.status] = (result[finding.status] ?? 0) + 1;
  return result;
}, {});
const infoRows = [
  ["项目", "麦奇说 UI 验收"],
  ["页面组", review.page_group],
  ["页面/状态", review.page],
  ["设备", review.device],
  ["设备截图", review.device_image.source_name],
  ["设计稿画板", review.design.source_name],
  ["Figma 节点", review.design.figma_node],
  ["设计稿定位", "麦奇说（UI测试验收）/ 分享页完成弹窗 / Figma 节点 6:1859"],
  ["实现方式", "PX；设备截图已是自身 @2x，按 720px 原尺寸比对"],
  ["画布尺寸", `${review.design.size[0]} × ${review.design.size[1]} px`],
  ["叠图方式", "设备图红色调，透明度 50%；弹窗顶边上移 8px 对齐"],
  ["问题总数", review.findings.length],
  ["待修复", counts["待修复"] ?? 0],
  ["待确认", counts["待确认"] ?? 0],
  ["判定范围", "仅覆盖本张截图的可见静态界面；Android 状态栏不计为 App 问题"],
  ["并排对照图", "01-分享页完成弹窗/side-by-side.png"],
  ["红色叠图", "01-分享页完成弹窗/overlay.png"],
];
info.getRange(`A1:B${infoRows.length}`).values = infoRows;
info.getRange(`A1:B${infoRows.length}`).format = {
  font: { name: fontName, size: 10, color: "#24313A" },
  verticalAlignment: "center",
  wrapText: true,
};
info.getRange(`A1:A${infoRows.length}`).format = {
  fill: "#EDF1F4",
  font: { name: fontName, size: 10, bold: true, color: "#24313A" },
  verticalAlignment: "center",
  wrapText: true,
};
info.getRange("A:A").format.columnWidthPx = 140;
info.getRange("B:B").format.columnWidthPx = 520;
info.getRange(`1:${infoRows.length}`).format.rowHeightPx = 30;
info.freezePanes.freezeRows(1);

workbook.recalculate();
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
await fs.mkdir(qualityDir, { recursive: true });

for (const [sheetName, range] of [
  ["验收记录", `A1:F${review.findings.length + 1}`],
  ["问题详情", `A1:I${review.findings.length + 1}`],
  ["验收信息", `A1:B${infoRows.length}`],
]) {
  const rendered = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(path.join(qualityDir, `workbook-preview-${sheetName}.png`), new Uint8Array(await rendered.arrayBuffer()));
}

console.log(JSON.stringify({ outputPath, findings: review.findings.length, pageGroup: review.page_group, sheets: [records.name, details.name, info.name] }));
