param(
  [ValidateSet('auto', 'local', 'niutrans', 'docker', 'lite')]
  [string]$Mode = 'auto',
  [string]$MosesRoot = '../../mosesdecoder-master',
  [string]$MosesBin = '',
  [string]$NiuTransRoot = '../tools/NiuTrans.SMT',
  [string]$NiuTransBin = '',
  [string]$NiuTransConfig = '../tools/NiuTrans.SMT/config/NiuTrans.phrase.config',
  [string]$ModelDir = './smt_model',
  [string]$DockerImage = 'moses-smt:latest',
  [string]$LiteModelPath = './smt_model/lite_phrase_table.json',
  [string]$LiteSeedPath = './data/smt_lite_seed.tsv',
  [int]$LiteMaxCedictEntries = 120000
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
$raw = Set-Or-Append -Content $raw -Key 'SMT_LITE_MODEL_PATH' -Value $LiteModelPath
$raw = Set-Or-Append -Content $raw -Key 'SMT_LITE_SEED_PATH' -Value $LiteSeedPath
$raw = Set-Or-Append -Content $raw -Key 'SMT_LITE_MAX_CEDICT_ENTRIES' -Value "$LiteMaxCedictEntries"
$raw = Set-Or-Append -Content $raw -Key 'SMT_NIUTRANS_ROOT' -Value $NiuTransRoot
$raw = Set-Or-Append -Content $raw -Key 'SMT_NIUTRANS_CONFIG' -Value $NiuTransConfig

if ($Mode -eq 'local' -or $Mode -eq 'auto') {
  $raw = Set-Or-Append -Content $raw -Key 'SMT_MOSES_ROOT' -Value $MosesRoot
  $raw = Set-Or-Append -Content $raw -Key 'SMT_MOSES_BIN' -Value $MosesBin
} else {
  $raw = Set-Or-Append -Content $raw -Key 'SMT_MOSES_BIN' -Value ''
}

if ($Mode -eq 'niutrans' -or $Mode -eq 'auto') {
  $raw = Set-Or-Append -Content $raw -Key 'SMT_NIUTRANS_BIN' -Value $NiuTransBin
} else {
  $raw = Set-Or-Append -Content $raw -Key 'SMT_NIUTRANS_BIN' -Value ''
}

Set-Content -Path $envPath -Value $raw -Encoding UTF8

Write-Host "Updated: $envPath"
Write-Host "SMT_MODE=$Mode"
Write-Host "SMT_MODEL_DIR=$ModelDir"

if ($Mode -eq 'local' -or $Mode -eq 'auto') {
  Write-Host "SMT_MOSES_ROOT=$MosesRoot"
  if ($MosesBin) {
    Write-Host "SMT_MOSES_BIN=$MosesBin"
  } else {
    Write-Host "SMT_MOSES_BIN=<empty> (will auto-detect from SMT_MOSES_ROOT)"
  }
}

if ($Mode -eq 'docker' -or $Mode -eq 'auto') {
  Write-Host "SMT_DOCKER_IMAGE=$DockerImage"
}

if ($Mode -eq 'niutrans' -or $Mode -eq 'auto') {
  Write-Host "SMT_NIUTRANS_ROOT=$NiuTransRoot"
  if ($NiuTransBin) {
    Write-Host "SMT_NIUTRANS_BIN=$NiuTransBin"
  } else {
    Write-Host "SMT_NIUTRANS_BIN=<empty> (will auto-detect from SMT_NIUTRANS_ROOT)"
  }
  Write-Host "SMT_NIUTRANS_CONFIG=$NiuTransConfig"
}

Write-Host "SMT_LITE_MODEL_PATH=$LiteModelPath"
Write-Host "SMT_LITE_SEED_PATH=$LiteSeedPath"
Write-Host "SMT_LITE_MAX_CEDICT_ENTRIES=$LiteMaxCedictEntries"

Write-Host ""
Write-Host "Next step:"
Write-Host "cd backend"
Write-Host ".venv312\Scripts\python.exe scripts/check_model_ready.py"
