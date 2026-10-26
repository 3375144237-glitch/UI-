import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const project = path.resolve(import.meta.dirname, "..");
const session = path.join(project, "outputs/design-review/2026-10-23/麦奇说验收-安卓/01-分享页完成弹窗-逐项对位");
const inputPath = path.join(session, "麦奇说安卓UI验收.xlsx");
const outputPath = path.join(project, "work/ui-review-quality-checks/麦奇说安卓UI验收-P14-N07.xlsx");
const previewDir = path.join(project, "work/ui-review-quality-checks");
const review = JSON.parse(await fs.readFile(path.join(session, "review.json"), "utf8"));
const finding = review.findings.find((item) => item.id === "P14-N07");

if (!finding || review.findings.length !== 7 || review.findings.filter((item) => item.id === finding.id).length !== 1) {
  throw new Error("review.json 中 P14-N07 缺失或编号重复；停止更新工作簿。");
}

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const records = workbook.worksheets.getItem("验收记录");
const details = workbook.worksheets.getItem("问题详情");
const info = workbook.worksheets.getItem("验收信息");
if (!records || !details || !info || records.getUsedRange()?.address !== "A1:F7" || details.getUsedRange()?.address !== "A1:K7") {
  throw new Error("现有工作簿结构与预期不同；没有写入任何问题行。");
}
if (records.getRange("A2:A7").values.flat().some((value) => value === "P14-N07")) {
  throw new Error("工作簿已经包含 P14-N07；为避免重复，停止更新。");
}

records.getRange("A8:F8").copyFrom(records.getRange("A7:F7"), "all");
records.getRange("A8:F8").values = [[
  finding.id,
  "",
  finding.description,
  finding.priority,
  finding.status,
  `${finding.source_screenshot}；${finding.remarks}`,
]];
records.getRange("D8").dataValidation = {
  rule: { type: "list", values: ["待评估", "P0", "P1", "P2", "P3"] },
};
records.getRange("E8").dataValidation = {
  rule: { type: "list", values: ["待确认", "待修复", "修复中", "已修复", "不修复"] },
};
records.getRange("8:8").format.rowHeightPx = 120;

const deviceBoxes = finding.icon_instances.map((item) => item.device_bbox);
const deviceUnion = finding.device_bbox;
const detailRow = [
  finding.id,
  finding.source_screenshot,
  finding.category,
  finding.design_basis,
  finding.expected,
  finding.actual,
  finding.measurement,
  finding.recommendation,
  [deviceUnion.x, deviceUnion.y, deviceUnion.width, deviceUnion.height].join(", "),
  `${finding.design_bbox.x}, ${finding.design_bbox.y}, ${finding.design_bbox.width}, ${finding.design_bbox.height}（design-screen.png）`,
  "",
];
details.getRange("A8:K8").copyFrom(details.getRange("A7:K7"), "all");
details.getRange("A8:K8").values = [detailRow];
details.getRange("8:8").format.rowHeightPx = 188;

const evidence = await fs.readFile(path.join(session, finding.evidence));
const dataUrl = `data:image/png;base64,${evidence.toString("base64")}`;
records.images.add({
  dataUrl,
  anchor: { from: { row: 7, col: 1 }, extent: { widthPx: 260, heightPx: 102 } },
});
details.images.add({
  dataUrl,
  anchor: { from: { row: 7, col: 10 }, extent: { widthPx: 260, heightPx: 102 } },
});

info.getRange("B8").values = [["徽章、吉祥物、标题、统计项和身份条分别用设备裁片对位；统计区4个图标节点逐个核对，3枚现存图标分别测量并移动到设计中心；红色50%只覆盖当前对应裁片，不缩放、不改原图"]];
info.getRange("B10").values = [["共7项；待修复4项；待确认3项"]];
info.getRange("B11").values = [["P14-N02：确认设备与设计是否为同一业务状态；P14-N03、P14-N06：由设计方在目标字体环境确认字形"]];

if (deviceBoxes.length !== 3) throw new Error("P14-N07 应包含3个独立图标 bbox。");
workbook.recalculate();
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
await fs.mkdir(previewDir, { recursive: true });

for (const [sheetName, range, fileName] of [
  ["验收记录", "A1:F8", "records-after-P14-N07.png"],
  ["问题详情", "A1:K8", "details-after-P14-N07.png"],
  ["验收信息", "A1:B13", "info-after-P14-N07.png"],
]) {
  const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}

const reopened = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const verification = await reopened.inspect({ kind: "workbook,sheet,table,drawing", maxChars: 15000, tableMaxRows: 9, tableMaxCols: 12 });
const drawingReport = await reopened.inspect({ kind: "drawing", maxChars: 12000 });
const imageCount = (drawingReport.ndjson.match(/"drawingType":"image"/g) ?? []).length;
const recordIds = reopened.worksheets.getItem("验收记录").getRange("A2:A8").values.flat();
const detailIds = reopened.worksheets.getItem("问题详情").getRange("A2:A8").values.flat();
if (recordIds.at(-1) !== "P14-N07" || detailIds.at(-1) !== "P14-N07" || imageCount !== 14) {
  throw new Error(`导出复核失败：record=${recordIds.at(-1)} detail=${detailIds.at(-1)} images=${imageCount}`);
}
console.log(JSON.stringify({ outputPath, issueId: finding.id, recordRows: recordIds.length, detailRows: detailIds.length, embeddedEvidenceImages: imageCount, verification: verification.ndjson }, null, 2));
