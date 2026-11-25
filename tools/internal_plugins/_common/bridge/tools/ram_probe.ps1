param(
  [string]$BridgeUrl = 'http://127.0.0.1:17875',
  [string]$Label = 'measurement'
)
# Dev-only Windows RAM probe. No dependencies beyond PowerShell. Prints the
# plugin profile's total working set / private bytes together with the REAL
# tab count from the dev-only tabs-dump endpoint. Run once per 1/2/3 tabs.
$tabs = @()
try {
  $resp = Invoke-RestMethod -Uri "$BridgeUrl/diagnostics/tabs-dump" -TimeoutSec 5
  if ($resp -and $resp.tabs) { $tabs = @($resp.tabs) }
} catch {
  Write-Warning "tabs-dump unavailable: $($_.Exception.Message)"
}
$procs = Get-CimInstance Win32_Process -Filter "name='chrome.exe'" |
  Where-Object { $_.CommandLine -match 'voice-typer-internal-plugins[/\\]dictation-profile' }
$ws = ($procs | Measure-Object -Property WorkingSetSize -Sum).Sum
$private = ($procs | Measure-Object -Property PrivatePageCount -Sum).Sum
$platformTabs = @($tabs | Where-Object { $_.url -match 'claude\.ai|chatgpt\.com|gemini\.google\.com' }).Count
[pscustomobject]@{
  label          = $Label
  at             = (Get-Date).ToString('o')
  processes      = @($procs).Count
  tabs_total     = @($tabs).Count
  tabs_platform  = $platformTabs
  working_set_mb = [math]::Round($ws / 1MB, 1)
  private_mb     = [math]::Round($private / 1MB, 1)
} | Format-List
