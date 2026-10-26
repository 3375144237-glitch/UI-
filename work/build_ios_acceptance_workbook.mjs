import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve("outputs/design-review/2026-10-26/麦奇说验收-IOS");
const evidenceDir = path.join(root, "01-首页-单词快拼1", "evidence");
const outputPath = path.join(root, "问题验收汇总.xlsx");
const previewPath = path.resolve("work/ui-review-quality-checks/workbook-preview-ios.png");

const records = [
  {
    image: "P01-01-position.png",
    description: "日历卡、单词快拼主卡和活动卡内容区均比设计稿下移约12px；活动卡后工具区起点比设计稿下移约24px。",
    priority: "P0",
    status: "待修复",
  },
  {
    image: "P01-02-test-overlay.png",
    description: "活动卡片上多出黑色“测试”悬浮控件，遮挡“打卡进度”文案并盖住进度条末端。",
    priority: "P0",
    status: "待修复",
  },
  {
    image: "待确认-吉祥物状态.png",
    description: "吉祥物姿势、表情和装饰与设计稿不同；可能是动画帧或业务状态素材，需要设计/产品确认。",
    priority: "P0",
    status: "待确认",
  },
];

const workbook = Workbook.create();
const sheet = workbook.worksheets.add("验收记录");
sheet.showGridLines = false;
sheet.getRange("A1").values = [["首页-单词快拼1｜IOS验收记录"]];
sheet.mergeCells("A2:F2");
sheet.getRange("A2").values = [["设备截图828×1792，原生2倍图未缩放；设计稿720×2156；状态与字体待确认项见页面问题汇总。"]];
sheet.getRange("A3:F3").values = [["设备", "截图", "问题描述", "优先级", "修复状态", "备注"]];
sheet.getRange(`A4:F${records.length + 3}`).values = records.map((record) => [
  "IOS",
  null,
  record.description,
  record.priority,
  record.status,
  "",
]);

sheet.getRange("A1:F1").format = {
  font: { name: "Arial", size: 14, bold: true, color: "#203544" },
};
sheet.getRange("A2:F2").format = {
  font: { name: "Arial", size: 9, color: "#56616B", italic: true },
  wrapText: true,
  verticalAlignment: "center",
};
sheet.getRange("A3:F3").format = {
  fill: "#314B59",
  font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
sheet.getRange(`A4:F${records.length + 3}`).format = {
  font: { name: "Arial", size: 10, color: "#26343D" },
  verticalAlignment: "center",
  wrapText: true,
};
sheet.getRange("D4:D5").format = {
  fill: "#FCE7DC",
  font: { name: "Arial", size: 10, bold: true, color: "#9A3412" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
sheet.getRange("D6").format = {
  fill: "#F6F0D8",
  font: { name: "Arial", size: 10, bold: true, color: "#785A08" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
sheet.getRange("E4:E6").format.horizontalAlignment = "center";
sheet.getRange("F4:F6").format.fill = "#FFFFFF";
sheet.getRange("A1:F1").format.rowHeight = 28;
sheet.getRange("A2:F2").format.rowHeight = 24;
sheet.getRange("A3:F3").format.rowHeight = 24;
sheet.getRange("A4:F6").format.rowHeight = 112;

for (const [column, width] of Object.entries({ A: 12, B: 28, C: 66, D: 12, E: 14, F: 18 })) {
  sheet.getRange(`${column}1:${column}100`).format.columnWidth = width;
}

sheet.getRange("D4:D100").dataValidation = {
  rule: { type: "list", values: ["待评估", "P0", "P1", "P2", "P3"] },
};
sheet.getRange("E4:E100").dataValidation = {
  rule: { type: "list", values: ["待确认", "待修复", "修复中", "已修复", "不修复"] },
};
const table = sheet.tables.add("A3:F6", true, "IOSAcceptanceRecords");
table.style = "TableStyleLight1";
sheet.freezePanes.freezeRows(3);

for (let index = 0; index < records.length; index += 1) {
  const record = records[index];
  const imagePath = path.join(evidenceDir, record.image);
  const bytes = await fs.readFile(imagePath);
  const dataUrl = `data:image/png;base64,${bytes.toString("base64")}`;
  const imageWidth = bytes.readUInt32BE(16);
  const imageHeight = bytes.readUInt32BE(20);
  const scale = Math.min(190 / imageWidth, 142 / imageHeight, 1);
  sheet.images.add({
    dataUrl,
    anchor: {
      from: { row: index + 3, col: 1 },
      extent: { widthPx: Math.round(imageWidth * scale), heightPx: Math.round(imageHeight * scale) },
    },
  });
}

workbook.recalculate();
const inspection = await workbook.inspect({
  kind: "table",
  range: "验收记录!A1:F6",
  include: "values",
  tableMaxRows: 10,
  tableMaxCols: 6,
  maxChars: 4000,
});
console.log(inspection.ndjson);

const preview = await workbook.render({ sheetName: "验收记录", range: "A1:F6", scale: 1, format: "png" });
await fs.mkdir(path.dirname(previewPath), { recursive: true });
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));

const exported = await SpreadsheetFile.exportXlsx(workbook);
await fs.mkdir(root, { recursive: true });
await exported.save(outputPath);
console.log(`saved ${outputPath}`);
