# 将本目录下所有 .mmd 导出为矢量图 SVG（Inkscape / 浏览器 / 支持 foreignObject 的编辑器）
# WPS 插入 SVG 常空白：文字在 <foreignObject> 内，请改用同目录脚本 export-png-for-wps.ps1 生成 PNG。
# 用法（PowerShell）: .\export-vector.ps1
# 需已安装 Node.js；首次会下载 @mermaid-js/mermaid-cli

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$mmdc = "npx"
$argsBase = @("--yes", "@mermaid-js/mermaid-cli@latest")

Get-ChildItem -Filter "*.mmd" | ForEach-Object {
    $in = $_.FullName
    $out = [System.IO.Path]::ChangeExtension($in, ".svg")
    Write-Host "Exporting: $($_.Name) -> $(Split-Path -Leaf $out)"
    & $mmdc @argsBase -i $in -o $out -b transparent
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Done. SVG files are vector graphics; use PNG only if the tool cannot import SVG."
