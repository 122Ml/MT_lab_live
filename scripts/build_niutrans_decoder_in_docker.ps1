param(
  [string]$NiuTransRoot = './tools/NiuTrans.SMT',
  [string]$BaseImage = 'ubuntu:22.04'
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$niutransPath = Resolve-Path (Join-Path $projectRoot $NiuTransRoot)
$srcPath = Join-Path $niutransPath 'src'

if (-not (Test-Path (Join-Path $srcPath 'Makefile'))) {
  throw "NiuTrans source not found: $srcPath"
}

Write-Host "[NiuTrans] source root: $niutransPath"
Write-Host "[NiuTrans] checking docker daemon..."
try {
  docker version *> $null
} catch {
  throw "Docker daemon is not ready. Please start Docker Desktop first, then rerun this script."
}

$linuxPath = $niutransPath.Path -replace '\\', '/'
$buildCmd = @(
  'apt-get update',
  'apt-get install -y --no-install-recommends build-essential make perl',
  'cd /workspace/src',
  'make -j2',
  'ls -al /workspace/bin'
) -join ' && '

Write-Host "[NiuTrans] building decoder inside docker..."
docker run --rm `
  -v "${linuxPath}:/workspace" `
  -w /workspace/src `
  $BaseImage `
  bash -lc $buildCmd

$decoderCandidates = @(
  (Join-Path $niutransPath 'bin/NiuTrans.Decoder'),
  (Join-Path $niutransPath 'bin/NiuTrans.Decoder.exe')
)

$decoder = $decoderCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $decoder) {
  throw "Build finished but decoder binary not found under $niutransPath/bin"
}

Write-Host "[NiuTrans] ready: $decoder"
Write-Host "Set in backend/.env:"
Write-Host "SMT_MODE=niutrans"
Write-Host "SMT_NIUTRANS_ROOT=../tools/NiuTrans.SMT"
Write-Host "SMT_NIUTRANS_BIN="
Write-Host "SMT_NIUTRANS_CONFIG=../tools/NiuTrans.SMT/config/NiuTrans.phrase.config"
