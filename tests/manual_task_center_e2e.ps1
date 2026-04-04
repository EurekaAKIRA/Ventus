param(
    [string]$ApiBase = "http://127.0.0.1:8001",
    [string]$RequirementFile = "E:\ending\LaVague-main\docs\platform_e2e_requirement.md",
    [string]$TaskName = "manual_e2e_check",
    [switch]$UseLlm,
    [switch]$ExecuteTask
)

$ErrorActionPreference = "Stop"

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "==== $Title ====" -ForegroundColor Cyan
}

function Show-Json {
    param(
        [Parameter(ValueFromPipeline = $true)]
        $Value
    )
    $Value | ConvertTo-Json -Depth 30
}

function Check-SuspiciousContent {
    param(
        [string]$JsonText
    )
    $matches = Select-String -InputObject $JsonText -Pattern "/users|/resource|enhance_cand_|repair_cand_" -AllMatches
    if ($matches) {
        Write-Host "发现可疑内容:" -ForegroundColor Yellow
        $matches | ForEach-Object { Write-Host $_.Line }
    } else {
        Write-Host "未发现 /users /resource enhance_cand_ repair_cand_" -ForegroundColor Green
    }
}

if (-not (Test-Path -LiteralPath $RequirementFile)) {
    throw "需求文档不存在: $RequirementFile"
}

Write-Section "Health"
$health = Invoke-RestMethod -Method Get -Uri "$ApiBase/health"
$health | Show-Json | Write-Host

Write-Section "Create Task"
$requirementText = Get-Content -LiteralPath $RequirementFile -Raw
$createBody = @{
    task_name = $TaskName
    source_type = "text"
    requirement_text = $requirementText
    target_system = $ApiBase
    environment = "test"
} | ConvertTo-Json -Depth 20

$create = Invoke-RestMethod -Method Post `
    -Uri "$ApiBase/api/tasks" `
    -ContentType "application/json" `
    -Body $createBody

$taskId = $create.data.task_id
$create | Show-Json | Write-Host
Write-Host "TASK_ID=$taskId" -ForegroundColor Green

Write-Section "Parse"
$parseBody = @{
    use_llm = [bool]$UseLlm
    rag_enabled = $true
    retrieval_top_k = 5
    rerank_enabled = $false
} | ConvertTo-Json -Depth 10

$parse = Invoke-RestMethod -Method Post `
    -Uri "$ApiBase/api/tasks/$taskId/parse" `
    -ContentType "application/json" `
    -Body $parseBody

$parse | Show-Json | Write-Host

Write-Section "Parsed Requirement"
$parsed = Invoke-RestMethod -Method Get `
    -Uri "$ApiBase/api/tasks/$taskId/parsed-requirement"

$parsedJson = $parsed | Show-Json
$parsedJson | Write-Host
Check-SuspiciousContent -JsonText $parsedJson

Write-Section "DSL"
$dsl = Invoke-RestMethod -Method Get `
    -Uri "$ApiBase/api/tasks/$taskId/dsl"

$dslJson = $dsl | Show-Json
$dslJson | Write-Host
Check-SuspiciousContent -JsonText $dslJson

if ($ExecuteTask) {
    Write-Section "Execute"
    $execBody = @{
        execution_mode = "api"
        environment = "test"
    } | ConvertTo-Json -Depth 10

    $execute = Invoke-RestMethod -Method Post `
        -Uri "$ApiBase/api/tasks/$taskId/execute" `
        -ContentType "application/json" `
        -Body $execBody

    $execute | Show-Json | Write-Host

    Write-Section "Execution Result"
    $execution = Invoke-RestMethod -Method Get `
        -Uri "$ApiBase/api/tasks/$taskId/execution"

    $executionJson = $execution | Show-Json
    $executionJson | Write-Host
    Check-SuspiciousContent -JsonText $executionJson
}

Write-Section "Done"
Write-Host "任务已创建: $taskId" -ForegroundColor Green
Write-Host "前端可打开: http://localhost:3000/tasks/$taskId?tab=execution"
