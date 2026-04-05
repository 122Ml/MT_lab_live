param(
  [switch]$SkipFrontendBuild
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$backendPath = Join-Path $projectRoot 'backend'
$frontendVuePath = Join-Path $projectRoot 'frontend-vue'
$frontendReactPath = Join-Path $projectRoot 'frontend-react'

function Resolve-Python {
  param([string]$BackendPath)

  $venv312 = Join-Path $BackendPath '.venv312\Scripts\python.exe'
  if (Test-Path $venv312) { return $venv312 }

  $venv = Join-Path $BackendPath '.venv\Scripts\python.exe'
  if (Test-Path $venv) { return $venv }

  return 'python'
}

$pythonExe = Resolve-Python -BackendPath $backendPath

Write-Host "[1/5] Backend compile check"
& $pythonExe -m compileall (Join-Path $backendPath 'app') (Join-Path $backendPath 'scripts')

Write-Host "[2/5] Local model readiness check"
Push-Location $backendPath
try {
  & $pythonExe scripts/check_model_ready.py

  Write-Host "[3/5] API smoke test"
  & $pythonExe scripts/smoke_test_api.py
}
finally {
  Pop-Location
}

if (-not $SkipFrontendBuild) {
  Write-Host "[4/5] Vue frontend build"
  Push-Location $frontendVuePath
  try {
    npm run build
  }
  finally {
    Pop-Location
  }

  Write-Host "[5/5] React frontend build"
  Push-Location $frontendReactPath
  try {
    npm run build
  }
  finally {
    Pop-Location
  }
} else {
  Write-Host "[4/5] Vue frontend build (skipped)"
  Write-Host "[5/5] React frontend build (skipped)"
}

Write-Host "Done. Verification completed."

