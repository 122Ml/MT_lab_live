param(
  [ValidateSet('local', 'docker')]
  [string]$Mode = 'local',
  [string]$MosesRoot = '../../mosesdecoder-master',
  [string]$MosesBin = '',
  [string]$ModelDir = './smt_model',
  [string]$DockerImage = 'moses-smt:latest'
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$backendPath = Join-Path $projectRoot 'backend'
$envPath = Join-Path $backendPath '.env'
$examplePath = Join-Path $backendPath '.env.example'

if (-not (Test-Path $envPath)) {
  if (-not (Test-Path $examplePath)) {
    throw ".env and .env.example are both missing: $backendPath"
  }
  Copy-Item $examplePath $envPath
}

$raw = Get-Content $envPath -Raw -Encoding UTF8

function Set-Or-Append {
  param(
    [string]$Content,
    [string]$Key,
    [string]$Value
  )

  $pattern = "(?m)^$([regex]::Escape($Key))=.*$"
  if ([regex]::IsMatch($Content, $pattern)) {
    return [regex]::Replace($Content, $pattern, "$Key=$Value")
  }

  if (-not $Content.EndsWith("`n")) {
    $Content += "`r`n"
  }
  return $Content + "$Key=$Value`r`n"
}

$raw = Set-Or-Append -Content $raw -Key 'SMT_ENABLED' -Value 'true'
$raw = Set-Or-Append -Content $raw -Key 'SMT_MODE' -Value $Mode
$raw = Set-Or-Append -Content $raw -Key 'SMT_MODEL_DIR' -Value $ModelDir
$raw = Set-Or-Append -Content $raw -Key 'SMT_DOCKER_IMAGE' -Value $DockerImage

if ($Mode -eq 'local') {
  $raw = Set-Or-Append -Content $raw -Key 'SMT_MOSES_ROOT' -Value $MosesRoot
  $raw = Set-Or-Append -Content $raw -Key 'SMT_MOSES_BIN' -Value $MosesBin
} else {
  $raw = Set-Or-Append -Content $raw -Key 'SMT_MOSES_BIN' -Value ''
}

Set-Content -Path $envPath -Value $raw -Encoding UTF8

Write-Host "Updated: $envPath"
Write-Host "SMT_MODE=$Mode"
Write-Host "SMT_MODEL_DIR=$ModelDir"

if ($Mode -eq 'local') {
  Write-Host "SMT_MOSES_ROOT=$MosesRoot"
  if ($MosesBin) {
    Write-Host "SMT_MOSES_BIN=$MosesBin"
  } else {
    Write-Host "SMT_MOSES_BIN=<empty> (will auto-detect from SMT_MOSES_ROOT)"
  }
} else {
  Write-Host "SMT_DOCKER_IMAGE=$DockerImage"
}

Write-Host ""
Write-Host "Next step:"
Write-Host "cd backend"
Write-Host ".venv312\Scripts\python.exe scripts/check_model_ready.py"

