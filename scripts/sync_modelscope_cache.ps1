param(
  [string]$ModelScopeCacheRoot = "C:\Users\23396\.cache\modelscope\hub\models",
  [string]$ProjectModelsDir = ""
)

$projectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($ProjectModelsDir)) {
  $ProjectModelsDir = Join-Path $projectRoot "models"
}

New-Item -ItemType Directory -Force -Path $ProjectModelsDir | Out-Null

$copyList = @(
  @{ Name = "opus-mt-zh-en"; Source = Join-Path $ModelScopeCacheRoot "Helsinki-NLP\opus-mt-zh-en" },
  @{ Name = "opus-mt-en-zh"; Source = Join-Path $ModelScopeCacheRoot "Helsinki-NLP\opus-mt-en-zh" },
  @{ Name = "nllb-200-distilled-600M"; Source = Join-Path $ModelScopeCacheRoot "facebook\nllb-200-distilled-600M" }
)

foreach ($item in $copyList) {
  $target = Join-Path $ProjectModelsDir $item.Name
  New-Item -ItemType Directory -Force -Path $target | Out-Null
  Write-Host "[SYNC] $($item.Name)"
  if (-not (Test-Path $item.Source)) {
    Write-Warning "Source not found: $($item.Source)"
    continue
  }

  robocopy $item.Source $target /E /R:1 /W:1 /NFL /NDL /NP | Out-Null
  Write-Host "[DONE] $target"
}

Write-Host "\nModel sync complete."

