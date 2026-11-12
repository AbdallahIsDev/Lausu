<#
.SYNOPSIS
  Turns off Chrome's window-occlusion and background-timer throttling for the
  current Windows user, so a covered Chrome window keeps its page active.

.DESCRIPTION
  Claude's dictation capture stops when Chrome decides the tab/window is
  hidden. These per-user policies keep that decision from firing when the
  dictation window is covered by another app. They apply to EVERY Chrome
  profile of this Windows user, not just the dictation profile, and Chrome
  must be fully restarted afterwards.

  Run once:
    powershell -File setup\occlusion.ps1

  Undo exactly these values:
    powershell -File setup\occlusion.ps1 -Revert

  The script is idempotent: values already at 0 are left alone.
#>
[CmdletBinding()]
param(
    [switch]$Revert
)

$ErrorActionPreference = "Stop"
$key = "HKCU:\Software\Policies\Google\Chrome"
$values = @(
    @{ Name = "WindowOcclusionEnabled";           Value = 0 },
    @{ Name = "NativeWindowOcclusionEnabled";     Value = 0 },
    @{ Name = "IntensiveWakeUpThrottlingEnabled"; Value = 0 }
)

if ($Revert) {
    foreach ($entry in $values) {
        if (-not (Test-Path $key)) { continue }
        $present = $null
        try { $present = (Get-ItemProperty -Path $key -Name $entry.Name -ErrorAction Stop).$($entry.Name) } catch { $present = $null }
        if ($null -ne $present) {
            Remove-ItemProperty -Path $key -Name $entry.Name -ErrorAction SilentlyContinue
            Write-Host "removed $($entry.Name)"
        } else {
            Write-Host "$($entry.Name) was not set"
        }
    }
    Write-Host "Chrome policy values removed. Restart Chrome (close every window) for it to take effect."
    return
}

if (-not (Test-Path $key)) {
    New-Item -Path $key -Force | Out-Null
}
foreach ($entry in $values) {
    $current = $null
    try { $current = (Get-ItemProperty -Path $key -Name $entry.Name -ErrorAction Stop).$($entry.Name) } catch { $current = $null }
    if ($current -eq $entry.Value) {
        Write-Host "$($entry.Name) already 0"
    } else {
        Set-ItemProperty -Path $key -Name $entry.Name -Value $entry.Value -Type DWord
        Write-Host "$($entry.Name) = 0"
    }
}
Write-Host "Done. Restart Chrome (close every window) for the policy to take effect."
