import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = "E:/ending/LaVague-main/outputs";
const outputPath = `${outputDir}/表4-1_Restful_Booker接口测试链路示例_扩展版.xlsx`;
const previewPath = `${outputDir}/表4-1_Restful_Booker接口测试链路示例_扩展版.png`;

await fs.mkdir(outputDir, { recursive: true });

const workbook = Workbook.create();
const sheet = workbook.worksheets.add("表4-1扩展版");
sheet.showGridLines = false;

sheet.getRange("A1:F1").merge();
sheet.getRange("A1").values = [["表4-1 Restful Booker 接口测试链路示例"]];

sheet.getRange("A3:F9").values = [
  ["步骤", "接口", "请求方法", "作用", "关键断言", "上下文变量"],
  [1, "/auth", "POST", "获取鉴权 token", "状态码为 200，响应中包含 token 字段", "保存 token"],
  [2, "/booking", "POST", "创建 booking 资源", "状态码为 200，响应中包含 bookingid", "保存 booking_id"],
  [3, "/booking/{{booking_id}}", "GET", "查询创建结果", "状态码为 200，姓名、日期等字段与创建数据一致", "引用 booking_id"],
  [4, "/booking/{{booking_id}}", "PATCH", "更新 booking 部分字段", "状态码为 200，返回结果中更新字段生效", "引用 token 与 booking_id"],
  [5, "/booking/{{booking_id}}", "GET", "验证更新结果", "状态码为 200，更新后的字段保持一致", "引用 booking_id"],
  [6, "/booking/{{booking_id}}", "DELETE", "删除测试资源", "状态码为 201 或 200，资源删除成功", "引用 token 与 booking_id"],
];

sheet.getRange("A1:F1").format = {
  font: { name: "Microsoft YaHei", bold: true, size: 14, color: "#1F2937" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
sheet.getRange("A3:F3").format = {
  fill: "#E5E7EB",
  font: { name: "Microsoft YaHei", bold: true, color: "#111827" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
};
sheet.getRange("A4:C9").format = {
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
};
sheet.getRange("D4:F9").format = {
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
};
sheet.getRange("A3:F9").format = {
  borders: { preset: "all", style: "thin", color: "#6B7280" },
  font: { name: "Microsoft YaHei", size: 11 },
  wrapText: true,
};

sheet.getRange("A1:A9").format.columnWidthPx = 56;
sheet.getRange("B1:B9").format.columnWidthPx = 210;
sheet.getRange("C1:C9").format.columnWidthPx = 86;
sheet.getRange("D1:D9").format.columnWidthPx = 160;
sheet.getRange("E1:E9").format.columnWidthPx = 300;
sheet.getRange("F1:F9").format.columnWidthPx = 210;
sheet.getRange("A1:F1").format.rowHeightPx = 34;
sheet.getRange("A3:F9").format.rowHeightPx = 42;

sheet.freezePanes.freezeRows(3);

const inspect = await workbook.inspect({
  kind: "table",
  range: "表4-1扩展版!A1:F9",
  include: "values",
  tableMaxRows: 12,
  tableMaxCols: 8,
});
console.log(inspect.ndjson);

const preview = await workbook.render({
  sheetName: "表4-1扩展版",
  autoCrop: "all",
  scale: 1,
  format: "png",
});
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(outputPath);
