<#
.SYNOPSIS
  Opens the dictation Chrome profile at Claude, as a normal browser the user owns.

.DESCRIPTION
  Reads profileDir and claudeUrl from the plugin's config.json (falling back to
  config.example.json), resolves chrome.exe from the standard install paths,
  and starts it with only:
      --user-data-dir=<profileDir> --profile-directory=Default <claudeUrl>
  No automation, debugging or window-position switches are added.

  Run:
    powershell -File setup\launch-claude-profile.ps1

  Undo: close that Chrome window. Nothing is persisted by this script.
#>
[CmdletBinding()]
param(
    [string]$ProfileDir = "",
    [string]$Url = "",
    [string]$ChromePath = ""
)

$ErrorActionPreference = "Stop"
$pluginRoot = Split-Path -Parent $PSScriptRoot

function Read-PluginConfig {
    foreach ($name in @("config.json", "config.example.json")) {
        $file = Join-Path $pluginRoot $name
        if (-not (Test-Path $file)) { continue }
        try { return Get-Content -LiteralPath $file -Raw | ConvertFrom-Json } catch { }
    }
    return $null
}

$config = Read-PluginConfig

if (-not $ProfileDir) {
    if ($config -and $config.profileDir) {
        $ProfileDir = [string]$config.profileDir
    } else {
        $ProfileDir = Join-Path $env:LOCALAPPDATA "voice-typer-internal-plugins/google-stt-profile"
    }
}

if (-not $Url) {
    if ($config -and $config.claudeUrl) {
        $Url = [string]$config.claudeUrl
    } else {
        $Url = "https://claude.ai/new"
    }
}

if (-not $ChromePath) {
    $candidates = @(
        $env:LUASU_CHROME_PATH,
        (Join-Path ${env:ProgramFiles} "Google/Chrome/Application/chrome.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Google/Chrome/Application/chrome.exe"),
        (Join-Path $env:LOCALAPPDATA "Google/Chrome/Application/chrome.exe")
    )
    $ChromePath = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}

if (-not $ChromePath) {
    throw "chrome.exe was not found in the standard install paths. Pass -ChromePath."
}

New-Item -ItemType Directory -Force -Path $ProfileDir | Out-Null

Write-Host "Chrome:  $ChromePath"
Write-Host "Profile: $ProfileDir (Default)"
Write-Host "URL:     $Url"
Write-Host "No automation or debugging switches are passed."

Start-Process -FilePath $ChromePath -ArgumentList @(
    "--user-data-dir=$ProfileDir",
    "--profile-directory=Default",
    $Url
)
