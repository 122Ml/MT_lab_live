param(
  [switch]$UseReact,
  [int]$BackendPort = 8000
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$backendPath = Join-Path $projectRoot 'backend'
$frontendVuePath = Join-Path $projectRoot 'frontend-vue'
$frontendReactPath = Join-Path $projectRoot 'frontend-react'

function Test-PortAvailable {
  param([int]$Port)

  try {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse('127.0.0.1'), $Port)
    $listener.Start()
    $listener.Stop()
    return $true
  }
  catch {
    return $false
  }
}

function Resolve-BackendPort {
  param([int]$PreferredPort)

  $candidates = @($PreferredPort, 8010, 18000, 28000) | Select-Object -Unique
  foreach ($port in $candidates) {
    if (Test-PortAvailable -Port $port) {
      return $port
    }
  }

  throw "No available backend port in candidates: $($candidates -join ', ')"
}

function Set-Or-AppendEnvValue {
  param(
    [string]$Path,
    [string]$Key,
    [string]$Value
  )

  $content = ''
  if (Test-Path $Path) {
    $content = Get-Content -Path $Path -Raw -Encoding UTF8
  }

  $pattern = "(?m)^$([regex]::Escape($Key))=.*$"
  if ([regex]::IsMatch($content, $pattern)) {
    $content = [regex]::Replace($content, $pattern, "$Key=$Value")
  }
  else {
    if ($content -and -not $content.EndsWith("`n")) {
      $content += "`r`n"
    }
    $content += "$Key=$Value`r`n"
  }

  Set-Content -Path $Path -Value $content -Encoding UTF8
}

$backendPort = Resolve-BackendPort -PreferredPort $BackendPort
$apiBaseUrl = "http://127.0.0.1:$backendPort"

$backendEnvPath = Join-Path $backendPath '.env'
if (-not (Test-Path $backendEnvPath)) {
  Copy-Item (Join-Path $backendPath '.env.example') $backendEnvPath
}
Set-Or-AppendEnvValue -Path $backendEnvPath -Key 'APP_PORT' -Value $backendPort

$frontendPath = if ($UseReact) { $frontendReactPath } else { $frontendVuePath }
$frontendEnvPath = Join-Path $frontendPath '.env'
if (-not (Test-Path $frontendEnvPath)) {
  if (Test-Path (Join-Path $frontendPath '.env.example')) {
    Copy-Item (Join-Path $frontendPath '.env.example') $frontendEnvPath
  }
  else {
    New-Item -Path $frontendEnvPath -ItemType File -Force | Out-Null
  }
}
Set-Or-AppendEnvValue -Path $frontendEnvPath -Key 'VITE_API_BASE_URL' -Value $apiBaseUrl

$pythonCandidates = @(
  'C:\Users\23396\AppData\Roaming\uv\python\cpython-3.12.12-windows-x86_64-none\python.exe',
  'python'
)

$pythonCommand = $pythonCandidates[0]
if (-not (Test-Path $pythonCommand)) {
  $pythonCommand = 'python'
}

$backendBoot = @"
Set-Location '$backendPath'

if (Test-Path '.venv312') {
  `$venvName = '.venv312'
} else {
  `$venvName = '.venv'
}

if (-not (Test-Path `$venvName)) {
  & '$pythonCommand' -m venv `$venvName
}

& (Join-Path `$venvName 'Scripts\Activate.ps1')
pip install -r requirements.txt

if (-not (Test-Path '.env')) {
  Copy-Item '.env.example' '.env'
}

uvicorn app.main:app --host 127.0.0.1 --port $backendPort --reload
"@

Write-Host "[MT-Lab Live] selected backend port: $backendPort"
Write-Host "[MT-Lab Live] starting backend..."
Start-Process powershell -ArgumentList '-NoExit', '-Command', $backendBoot

if ($UseReact) {
  Write-Host "[MT-Lab Live] starting React frontend..."
  Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$frontendReactPath'; npm install; npm run dev"
} else {
  Write-Host "[MT-Lab Live] starting Vue frontend..."
  Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$frontendVuePath'; npm install; npm run dev"
}

Write-Host "Done. backend: $apiBaseUrl, frontend: http://127.0.0.1:5173 (or 5174)"
