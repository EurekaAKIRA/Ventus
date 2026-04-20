# 导出 PNG 供 WPS / 旧版 Office 插入（推荐）
#
# 原因：mermaid-cli 生成的 SVG 使用 <foreignObject>+HTML 排版文字，WPS 对这类 SVG
# 常显示为空白或只有线框。PNG 由 Chromium 整页截图生成，文字与图形一致。
#
# 用法（PowerShell）: .\export-png-for-wps.ps1
# 依赖：Node.js；首次会下载 @mermaid-js/mermaid-cli（内含 Puppeteer）

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$mmdc = "npx"
$argsBase = @("--yes", "@mermaid-js/mermaid-cli@latest")

Get-ChildItem -Filter "*.mmd" | ForEach-Object {
    $in = $_.FullName
    $out = [System.IO.Path]::ChangeExtension($in, ".png")
    Write-Host "Exporting PNG: $($_.Name) -> $(Split-Path -Leaf $out)"
    # 白底避免部分环境下透明 PNG 发灰；scale 提高清晰度
    & $mmdc @argsBase -i $in -o $out -e png -b white -s 2
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Done. Insert the .png files into WPS; keep .svg for Inkscape / 浏览器 / 支持 foreignObject 的编辑器。"
