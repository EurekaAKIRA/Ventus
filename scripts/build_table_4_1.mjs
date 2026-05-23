import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = "E:/ending/LaVague-main/outputs";
const outputPath = `${outputDir}/表4-1_Restful_Booker接口测试链路示例.xlsx`;
const previewPath = `${outputDir}/表4-1_Restful_Booker接口测试链路示例.png`;

await fs.mkdir(outputDir, { recursive: true });

const workbook = Workbook.create();
const sheet = workbook.worksheets.add("表4-1");
sheet.showGridLines = false;

sheet.getRange("A1:D1").merge();
sheet.getRange("A1").values = [["表4-1 Restful Booker 接口测试链路示例"]];

sheet.getRange("A3:D7").values = [
  ["步骤", "接口", "作用", "上下文变量"],
  [1, "POST /auth", "获取鉴权 token", "保存 token"],
  [2, "POST /booking", "创建 booking 资源", "保存 booking_id"],
  [3, "GET /booking/{{booking_id}}", "查询创建结果", "引用 booking_id"],
  [4, "DELETE /booking/{{booking_id}}", "删除测试资源", "引用 token 与 booking_id"],
];

sheet.getRange("A1:D1").format = {
  font: { bold: true, size: 14, color: "#1F2937" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
sheet.getRange("A3:D3").format = {
  fill: "#E5E7EB",
  font: { bold: true, color: "#111827" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
};
sheet.getRange("A4:A7").format = {
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
sheet.getRange("B4:D7").format = {
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
};
sheet.getRange("A3:D7").format = {
  borders: { preset: "all", style: "thin", color: "#6B7280" },
  font: { name: "Microsoft YaHei", size: 11 },
  wrapText: true,
};
sheet.getRange("A1:D7").format = {
  font: { name: "Microsoft YaHei" },
};

sheet.getRange("A1:A7").format.columnWidthPx = 64;
sheet.getRange("B1:B7").format.columnWidthPx = 220;
sheet.getRange("C1:C7").format.columnWidthPx = 180;
sheet.getRange("D1:D7").format.columnWidthPx = 210;
sheet.getRange("A1:D1").format.rowHeightPx = 34;
sheet.getRange("A3:D7").format.rowHeightPx = 32;

sheet.freezePanes.freezeRows(3);

const inspect = await workbook.inspect({
  kind: "table",
  range: "表4-1!A1:D7",
  include: "values",
  tableMaxRows: 10,
  tableMaxCols: 6,
});
console.log(inspect.ndjson);

const preview = await workbook.render({
  sheetName: "表4-1",
  autoCrop: "all",
  scale: 1,
  format: "png",
});
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(outputPath);
