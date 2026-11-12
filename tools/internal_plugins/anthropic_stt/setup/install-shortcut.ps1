<#
.SYNOPSIS
  Puts "Claude Dictation" in the Start menu so the profile opens from a search.

.DESCRIPTION
  Creates a shortcut that runs Chrome with exactly the flags
  launch-claude-profile.ps1 uses: --user-data-dir, --profile-directory and the
  Claude URL. No automation or debugging switch is ever written.

  Run once:
    powershell -File setup\install-shortcut.ps1
    powershell -File setup\install-shortcut.ps1 -Desktop   # also on the desktop

  Remove:
    powershell -File setup\install-shortcut.ps1 -Remove
#>
[CmdletBinding()]
param(
    [string]$Name = "Claude Dictation",
    [string]$ProfileDir = "",
    [string]$Url = "",
    [string]$ChromePath = "",
    [switch]$Desktop,
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$pluginRoot = Split-Path -Parent $PSScriptRoot

function Read-PluginConfig {
    foreach ($file in @("config.json", "config.example.json")) {
        $path = Join-Path $pluginRoot $file
        if (-not (Test-Path $path)) { continue }
        try { return Get-Content -LiteralPath $path -Raw | ConvertFrom-Json } catch { }
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

$folders = @([Environment]::GetFolderPath("Programs"))
if ($Desktop) { $folders += [Environment]::GetFolderPath("Desktop") }

foreach ($folder in $folders) {
    $link = Join-Path $folder "$Name.lnk"
    if ($Remove) {
        if (Test-Path $link) {
            Remove-Item -LiteralPath $link
            Write-Host "removed $link"
        }
        continue
    }
    if (-not $ChromePath) {
        throw "chrome.exe was not found in the standard install paths. Pass -ChromePath."
    }
    $shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($link)
    $shortcut.TargetPath = $ChromePath
    # Keep this argument shape identical to launch-claude-profile.ps1.
    $shortcut.Arguments = '--user-data-dir="{0}" --profile-directory=Default "{1}"' -f $ProfileDir, $Url
    $shortcut.WorkingDirectory = Split-Path -Parent $ChromePath
    $shortcut.IconLocation = "$ChromePath,0"
    $shortcut.Description = "Opens the dictation Chrome profile on Claude"
    $shortcut.Save()
    Write-Host "created $link"
}
