; Lausu. Full-offline NSIS installer template (slim core + pack bundled).
;
; This is a STANDALONE NSIS script (NOT a Tauri-generated installer.nsi).
; It produces a SECOND installer artifact alongside the slim-core installer
; (plan-runtime-pack-split.md §4.1 / §11.9 / open-decision §14.5: "always
; publish both"). The slim-core installer is the default download; this
; full-offline installer exists for offline-install scenarios (air-gapped
; corp networks, slow links, pre-staged SCCM deploys, etc.).
;
; Build: see ``scripts/build/build_full_offline_installer_windows.sh``.
; The build script invokes ``makensis`` on this file with these !defines:
;
;   SLIM_CORE_EXE   = absolute path to the slim-core installer .exe
;                     produced by ``cargo tauri build --config
;                     tauri.windows-x86_64.conf.json`` (or aarch64 sibling).
;   PACK_ZIP        = absolute path to the runtime-pack zip
;                     (``lausu-runtime-pack-<ver>-<triple>.zip``)
;                     produced by Sub-agent 5's worker build script.
;   PACK_VERSION    = pack version string (e.g. "3").
;   APP_VERSION     = slim-core app version (matches tauri.conf.json).
;   PRODUCT_TRIPLE = target triple (e.g. "x86_64-pc-windows-msvc").
;
; Output: ``lausu-full-offline-<APP_VERSION>-<PRODUCT_TRIPLE>.exe``
; (a NEW artifact name per §11.9; the existing slim-core
; ``lausu-<version>-<triple>.exe`` name is left UNCHANGED, C-CI-13
; forbids renaming existing artifacts).
;
; What this installer does at install time:
;   1. Extracts the bundled pack zip to
;      ``%LOCALAPPDATA%\lausu\runtime-pack\<PACK_VERSION>\``.
;      This is the SAME per-user path the slim-core app's runtime-pack
;      resolver looks at (plan §4.7, ``src-tauri/src/platform/worker_path.rs``).
;   2. Writes ``%LOCALAPPDATA%\lausu\installer-state.json`` with
;      ``pack_bundled: true`` so the slim-core app's first-launch
;      consent gate (plan §4.8) SKIPS the silent background download —
;      the pack is already on disk.
;   3. Runs the bundled slim-core installer .exe with the same NSIS args
;      the user passed to this wrapper (so silent installs propagate:
;      ``/S`` runs the slim-core installer silently).
;
; The wrapper itself has NO Components-page checkbox, the pack IS
; bundled, so the "Include offline engine pack" choice the slim-core
; installer exposes is moot here. We always install the pack to disk.
; The slim-core installer's own Components page still appears (we run
; it after unpacking the pack); the user can untick the checkbox there
; but the pack is already extracted, the checkbox only governs the
; silent *download*, which is skipped because ``pack_bundled: true``.

!ifndef SLIM_CORE_EXE
  !error "SLIM_CORE_EXE must be defined (path to slim-core installer .exe). Build via scripts/build/build_full_offline_installer_windows.sh."
!endif
!ifndef PACK_ZIP
  !error "PACK_ZIP must be defined (path to lausu-runtime-pack-<ver>-<triple>.zip). Build via Sub-agent 5's worker build script."
!endif
!ifndef PACK_VERSION
  !error "PACK_VERSION must be defined (e.g. '3')."
!endif
!ifndef APP_VERSION
  !error "APP_VERSION must be defined (slim-core app version, matches tauri.conf.json)."
!endif
!ifndef PRODUCT_TRIPLE
  !error "PRODUCT_TRIPLE must be defined (e.g. 'x86_64-pc-windows-msvc')."
!endif

Unicode true
ManifestDPIAware true
SetCompressor /SOLID lzma
; ${GetParameters} (used in the slim-core launch section) lives in FileFunc.nsh.
!include FileFunc.nsh

Name "Lausu ${APP_VERSION} (full offline)"
OutFile "lausu-full-offline-${APP_VERSION}-${PRODUCT_TRIPLE}.exe"
InstallDir "$LOCALAPPDATA\lausu"
RequestExecutionLevel user
ShowInstDetails show

; ─── Version metadata (shown in installer .exe Properties → Details) ─────
VIProductVersion "${APP_VERSION}.0"
VIAddVersionKey "ProductName" "Lausu (full offline installer)"
VIAddVersionKey "FileDescription" "Slim core + offline engine pack bundled"
VIAddVersionKey "CompanyName" "Lausu"
VIAddVersionKey "LegalCopyright" "(c) Lausu contributors"
VIAddVersionKey "FileVersion" "${APP_VERSION}"
VIAddVersionKey "ProductVersion" "${APP_VERSION}"

; ─── Pack extraction section ─────────────────────────────────────────────
; The pack is extracted to a versioned subdirectory of the per-user
; data root (plan §4.7: %LOCALAPPDATA%\lausu\runtime-pack\<version>\).
; The slim-core app's runtime-pack resolver discovers the latest version
; by scanning this directory.
Section "Offline engine pack (bundled)" SecPack
  SectionIn RO  ; always installed, pack is the entire point of this artifact
  SetOutPath "$LOCALAPPDATA\lausu\runtime-pack\${PACK_VERSION}"
  DetailPrint "[lausu-full-offline] Extracting pack v${PACK_VERSION} to $LOCALAPPDATA\lausu\runtime-pack\${PACK_VERSION}\..."
  File "${PACK_ZIP}"
  ; Unzip via the bundled Python interpreter? No, we don't have one yet
  ; at install time (the slim-core installer hasn't run). Use NSIS's
  ; native unzip via the ``unzip`` plugin OR shell out to PowerShell's
  ; ``Expand-Archive`` (built-in on Windows 10+). PowerShell is the
  ; zero-dependency choice.
  ; -ErrorAction Stop + $ErrorActionPreference (written $$ in NSIS so a literal
  ; $ reaches PowerShell) make a corrupt zip a nonzero exit, not a silent
  ; non-terminating warning.
  nsExec::ExecToLog 'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "$$ErrorActionPreference = $\'Stop$\'; Expand-Archive -LiteralPath $\'$LOCALAPPDATA\lausu\runtime-pack\${PACK_VERSION}\lausu-runtime-pack-${PACK_VERSION}-${PRODUCT_TRIPLE}.zip$\' -DestinationPath $\'$LOCALAPPDATA\lausu\runtime-pack\${PACK_VERSION}$\' -Force -ErrorAction Stop"'
  Pop $0
  ${If} $0 != 0
    DetailPrint "[lausu-full-offline] ERROR: Expand-Archive failed with exit code $0."
    Abort "[lausu-full-offline] Pack extraction failed; the downloaded archive is kept for retry."
  ${EndIf}
  ; Prove the pack extracted before deleting the archive: the version dir must
  ; contain at least one non-archive file (file assertion).
  nsExec::ExecToLog 'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "$$ErrorActionPreference = $\'Stop$\'; $$files = @(Get-ChildItem -LiteralPath $\'$LOCALAPPDATA\lausu\runtime-pack\${PACK_VERSION}$\' -File -Recurse | Where-Object { $$_.Extension -ne $\'.zip$\' }); if ($$files.Count -eq 0) { Write-Error $\'extracted pack is empty$\'; exit 1 }"'
  Pop $0
  ${If} $0 != 0
    DetailPrint "[lausu-full-offline] ERROR: extracted pack failed verification (exit code $0)."
    Abort "[lausu-full-offline] Pack extraction verification failed; the downloaded archive is kept for retry."
  ${EndIf}
  ; Remove the zip only after extraction is proven good (saves ~180 MB on disk).
  Delete "$LOCALAPPDATA\lausu\runtime-pack\${PACK_VERSION}\lausu-runtime-pack-${PACK_VERSION}-${PRODUCT_TRIPLE}.zip"
SectionEnd

; ─── Slim-core installer launch section ─────────────────────────────────
; Run the bundled slim-core installer .exe. Only the INSTALLER PARAMETERS
; passed to THIS wrapper are forwarded (via ``${GetParameters}``), so
; ``/S`` silent installs propagate. Raw ``$CMDLINE`` is deliberately NOT
; used: it contains this wrapper's own executable path and omits
; ``/D=path``. ``/D=path`` cannot be forwarded through a parameter string
; (NSIS consumes it as the wrapper's own install dir), so set the slim-core
; install dir through its own installer UI/config instead.
; The slim-core installer is invoked with ``ExecWait`` so this wrapper
; does NOT exit until the slim-core install completes (otherwise the user
; sees the wrapper finish before the actual app install, confusing UX).
Section "Install slim core" SecSlimCore
  SectionIn RO
  SetOutPath "$PLUGINSDIR"
  ; ``File /oname=`` extracts the source file under a fixed name so the
  ; ExecWait line below doesn't have to know the source filename.
  File /oname=slim-core-setup.exe "${SLIM_CORE_EXE}"
  DetailPrint "[lausu-full-offline] Launching slim-core installer..."
  ; ${GetParameters} extracts ONLY the installer params (no wrapper exe path).
  ${GetParameters} $R0
  ExecWait '"$PLUGINSDIR\slim-core-setup.exe" $R0' $0
  ${If} $0 != 0
    DetailPrint "[lausu-full-offline] ERROR: slim-core installer exit code $0."
    Abort "[lausu-full-offline] Slim-core installation failed; the full-offline install did not complete."
  ${EndIf}
SectionEnd

; ─── installer-state.json write section ─────────────────────────────────
; Runs LAST (after extraction and slim-core succeeded) so pack_bundled=true
; is never written for a failed install.
; Signals to the slim-core app (read at first launch via
; ``voice_typer/server/installer_state.py``) that:
;   - The pack was bundled into this installer (``pack_bundled: true``).
;   - The user's "Include offline engine pack" checkbox choice from the
;     slim-core installer governs the silent download, but since the pack
;     is already on disk, the slim-core app's pack resolver finds it and
;     skips the download regardless.
; We still write ``include_offline_engine_pack: true`` because the user
; chose to install the full-offline variant (consent is implicit).
Section "Write installer state" SecState
  SectionIn RO
  CreateDirectory "$LOCALAPPDATA\lausu"
  ClearErrors
  FileOpen $0 "$LOCALAPPDATA\lausu\installer-state.json" w
  IfErrors state_done
  FileWrite $0 `{"include_offline_engine_pack": true, "installer_version": "${APP_VERSION}", "pack_bundled": true, "pack_version": "${PACK_VERSION}"}`$\r$\n`
  FileClose $0
  DetailPrint "[lausu-full-offline] Wrote installer-state.json (pack_bundled=true, pack_version=${PACK_VERSION})."
  state_done:
SectionEnd

; ─── customInstall: no-op (handled by the sections above) ───────────────
; This macro is invoked by Tauri v2's installer.nsi; we never run that
; template here (this IS a custom template), but defining the macro
; keeps the file syntactically valid if it's ever ``!include``d by
; another script.
!macro customInstall
!macroend
