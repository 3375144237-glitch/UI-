import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const projectRoot = "/Users/jiujiu/Documents/Codex/workspace/project-015-ui-repo-cleanup";
const reportPath = `${projectRoot}/outputs/design-review/2026-10-26/麦奇说验收-IOS/问题验收汇总.xlsx`;
const previewPath = `${projectRoot}/work/visual-acceptance/batch-report-after.png`;
const p12Dir = `${projectRoot}/outputs/design-review/2026-10-26/麦奇说验收-IOS/12-今日计划已学完弹窗`;

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(reportPath));
const sheet = workbook.worksheets.getItemAt(0);
const table = sheet.tables.items[0];
const existingValues = sheet.getUsedRange().values;
const hasP12 = existingValues.some((row) => String(row[2] ?? "").includes("【页面 P12"));

if (!hasP12) {
  const rows = [
    ["IOS", "", "【页面 P12 今日计划已学完弹窗】正文固定文案与设计稿不一致：设计稿“今日新词任务已完成。你还可以回顾历史单词巩固记忆，或进入单元学查看教材中的更多内容。”；设备为“你今天的新学单词都已完成，可回顾历史单词巩固记忆，或前往单元学查看更多内容。”", "P0", "待修复", ""],
    ["IOS", "", "【页面 P12 今日计划已学完弹窗】设备弹窗可见高458px，设计导出图可见高422px，高约36px；Figma子层边界与导出图可见边界不一致，需确认准确设计边界。", "P0", "待确认", ""],
    ["IOS", "", "【页面 P12 今日计划已学完弹窗】正文颜色明显偏浅：设计稿主要实色像素约RGB(98,100,102)，设备约RGB(158,161,164)；数值来自扁平PNG。", "P0", "待修复", ""],
    ["IOS", "", "【页面 P12 今日计划已学完弹窗】弹窗顶边对齐后，设备标题约下移27px、正文首行下移15px、正文末行上移9px、按钮组下移37px；正文行距及正文至按钮间距不同。", "P0", "待修复", ""],
  ];
  table.rows.add(null, rows);
  for (let i = 0; i < rows.length; i++) {
    const rowNumber = 7 + i;
    const styleRow = i % 2 === 0 ? 4 : 5;
    sheet.getRange(`A${rowNumber}:F${rowNumber}`).copyFrom(sheet.getRange(`A${styleRow}:F${styleRow}`), "all");
    sheet.getRange(`A${rowNumber}:F${rowNumber}`).values = rows[i];
    sheet.getRange(`A${rowNumber}:F${rowNumber}`).format.rowHeightPx = 168;

    const evidencePath = `${p12Dir}/evidence/P12-0${i + 1}-${["copy", "dialog-height", "body-color", "vertical-layout"][i]}.png`;
    const bytes = await fs.readFile(evidencePath);
    const dataUrl = `data:image/png;base64,${bytes.toString("base64")}`;
    sheet.images.add({
      dataUrl,
      anchor: { from: { row: rowNumber - 1, col: 1 }, extent: { widthPx: 176, heightPx: 160 } },
    });
  }
}

sheet.getRange("A1").values = [["麦奇说｜IOS验收记录"]];
sheet.getRange("A2").values = [["本批次包含首页-单词快拼1及今日计划已学完弹窗；设备截图均为IOS原生2倍图828×1792，未缩放。"]];
workbook.recalculate();

const check = await workbook.inspect({
  kind: "workbook,sheet,table,drawing",
  maxChars: 9000,
  tableMaxRows: 12,
  tableMaxCols: 8,
});
console.log(check.ndjson);
const preview = await workbook.render({ sheetName: sheet.name, autoCrop: "all", scale: 1, format: "png" });
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(reportPath);
