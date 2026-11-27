# DEV-ONLY. Never staged into a packaged build; never imported by the product.
# Launches the already-signed-in dictation profile with Chromium's fake mic
# flags so a controlled neutral sentence can be dictated during diagnostics.
# Requires the workspace DEVELOPER_DIAGNOSTICS marker and a non-frozen build.
param(
  [Parameter(Mandatory=$true)][ValidateSet('claude','chatgpt','gemini')][string]$Platform,
  [Parameter(Mandatory=$true)][string]$WavPath,
  [int]$DebugPort = 9223
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if ($env:VOICE_TYPER_FROZEN -eq '1') { throw 'refused: frozen build' }
if (-not (Test-Path (Join-Path $root 'tools\internal_plugins\DEVELOPER_DIAGNOSTICS'))) {
  throw 'refused: DEVELOPER_DIAGNOSTICS marker missing'
}
if (-not (Test-Path -LiteralPath $WavPath)) { throw "WAV not found: $WavPath" }
$wav = (Resolve-Path -LiteralPath $WavPath).Path
if ($wav -match '%') { throw 'refused: % is reserved by the fake-audio flag parser' }

$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw "missing venv: $python" }
$profileDir = & $python -c "from tools.internal_plugins._common.bridge.install_paths import profile_dir; print(profile_dir())"
if (-not $profileDir -or -not (Test-Path $profileDir)) { throw "profile missing: $profileDir" }
$chrome = @(
  'C:\Program Files\Google\Chrome\Application\chrome.exe',
  'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
  "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) { throw 'Chrome not found' }

$profileMatch = ($profileDir -replace '\\', '/').TrimEnd('/')
$profileBackslash = $profileDir.TrimEnd('\')
$running = Get-CimInstance Win32_Process -Filter "name='chrome.exe'" |
  Where-Object { $_.CommandLine -match [regex]::Escape($profileMatch) -or $_.CommandLine -match [regex]::Escape($profileBackslash) }
foreach ($p in $running) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Milliseconds 800

$url = if ($Platform -eq 'claude') { 'https://claude.ai/' } elseif ($Platform -eq 'gemini') { 'https://gemini.google.com/app' } else { 'https://chatgpt.com/' }
$args = @(
  "--user-data-dir=$profileDir",
  '--profile-directory=Default',
  "--remote-debugging-port=$DebugPort",
  '--use-fake-device-for-media-stream',
  "--use-file-for-fake-audio-capture=$wav",
  '--no-first-run',
  $url
)
$proc = Start-Process -FilePath $chrome -ArgumentList $args -PassThru
Write-Output "DEV fake-audio Chrome pid=$($proc.Id) port=$DebugPort platform=$Platform wav=$wav"
Write-Output "CDP endpoint: http://127.0.0.1:$DebugPort/json/version"
