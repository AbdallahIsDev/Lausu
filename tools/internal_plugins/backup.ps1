<#
.SYNOPSIS
  Backup / attach / detach for the internal Google STT plugin (tools/internal_plugins).

.DESCRIPTION
  This folder is deliberately its OWN git repository (nested, ignored by
  the parent repo) so the plugin's code history lives somewhere else —
  a PRIVATE remote — and can never be pushed to the public app repo.

  Attach the private remote (repo is already initialized locally):
    .\backup.ps1 -RemoteUrl https://github.com/<you>/voice-typer-internal-plugins.git

  Fresh folder (creates the repo + pushes in one go):
    .\backup.ps1 -Init -RemoteUrl https://github.com/<you>/voice-typer-internal-plugins.git

  Everyday backup after editing plugin code (remote already attached):
    .\backup.ps1 -Message "selectors: fix mic label after redesign"

  State at a glance:
    .\backup.ps1 -Status

  Attach (fresh machine / after deletion):
    git clone https://github.com/<you>/voice-typer-internal-plugins.git tools/internal_plugins
    New-Item tools/internal_plugins/PLUGINS_ENABLED          # enable in-app
    setx VOICE_TYPER_INTERNAL_PLUGINS 1              # once per machine

  Detach (app instantly returns to stock):
    Remove-Item tools/internal_plugins/PLUGINS_ENABLED

.NEVER
  The Chrome profile (session cookies) lives in %LOCALAPPDATA%, never here.
  debug/, config.json, PLUGINS_ENABLED are gitignored inside this repo.
#>
[CmdletBinding()]
param(
    [switch]$Init,
    [switch]$Status,
    [string]$RemoteUrl = "",
    [string]$Message = ""
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Test-Origin {
    # `git remote get-url` writes to stderr when origin is absent, and under
    # $ErrorActionPreference=Stop a redirected native stderr becomes a
    # terminating error. `git remote` itself always exits 0.
    return ((git remote) -contains "origin")
}

function Get-OriginUrl {
    if (Test-Origin) { return (git remote get-url origin) }
    return $null
}

function Assert-Clean {
    # Never let a backup swallow local secrets/artifacts.
    $blocked = @("google-stt-profile", "debug/last", "config.json", "PLUGINS_ENABLED", "extension/generated", "STOP")
    $raw = git status --porcelain
    foreach ($b in $blocked) {
        if ($raw -match [regex]::Escape($b)) {
            throw "Refusing to commit: '$b' appeared in git status. Check tools/internal_plugins/.gitignore."
        }
    }
}

if ($Init) {
    if (Test-Path ".git") { throw "tools/internal_plugins is already a git repo (use plain -Message backup)." }
    git init
    Assert-Clean
    git add -A
    # Commit BEFORE -M: `git branch -M` on an unborn HEAD exits non-zero
    # on some git versions and silently aborted the first run.
    git commit -m "plugin: initial import of the Google STT plugin"
    git branch -M main
    if ($RemoteUrl) {
        git remote add origin $RemoteUrl
        git push -u origin main
        Write-Host "Pushed to PRIVATE remote: $RemoteUrl"
        Write-Host "Verify it is private: gh repo view $RemoteUrl --json visibility"
    } else {
        Write-Host "Local repo created. Re-run with -Init -RemoteUrl <private repo URL> to push."
    }
    return
}

if ($Status) {
    if (-not (Test-Path ".git")) { Write-Host "No local repo yet. Run: .\backup.ps1 -Init -RemoteUrl <private URL>"; return }
    git status -sb
    git log --oneline -5
    $shown = Get-OriginUrl
    if ($shown) { Write-Host "origin: $shown" }
    else { Write-Host "origin: NONE - run .\backup.ps1 -RemoteUrl <private URL>" }
    return
}

if (-not (Test-Path ".git")) { throw "No local repo. Run: .\backup.ps1 -Init -RemoteUrl <private repo URL>" }

if ($RemoteUrl) {
    # Attach (or repoint) the private remote on an already-initialized repo.
    $origin = Get-OriginUrl
    if (-not $origin) { git remote add origin $RemoteUrl }
    elseif ($origin.Trim() -ne $RemoteUrl.Trim()) { git remote set-url origin $RemoteUrl }
    Write-Host "origin -> $RemoteUrl"
    Write-Host "Verify it is PRIVATE: gh repo view $RemoteUrl --json visibility"
}
if (-not (Test-Origin)) {
    throw "No 'origin' remote yet. Run: .\backup.ps1 -RemoteUrl <private repo URL>"
}
Assert-Clean
$hasChanges = (git status --porcelain)
if (-not $hasChanges) {
    Write-Host "No changes to back up; pushing any unpushed commits."
    git push -u origin HEAD
    return
}
$msg = if ($Message) { $Message } else { "plugin: backup " + (Get-Date -Format "yyyy-MM-dd HH:mm") }
git add -A
git commit -m $msg
git push -u origin HEAD
Write-Host "Backed up: $msg"
