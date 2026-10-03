; Lausu. NSIS installer-time hooks (slim-core / runtime-pack split).
;
; Companion to ``scripts/windows/uninstaller.nsh`` (which defines the
; ``customUnInstall`` macro for post-uninstall cleanup). This file defines
; the INSTALL-time hooks the slim-core NSIS installer runs.
;
; Tauri v2 contract (verified against crates/tauri-bundler installer.nsi +
; tauri-utils config.rs ``installer_hooks`` docs):
;   * The generated installer.nsi ``!include``s this file BEFORE the MUI
;     page declarations.
;   * Tauri invokes ONLY the ``NSIS_HOOK_PREINSTALL`` /
;     ``NSIS_HOOK_POSTINSTALL`` / ``NSIS_HOOK_PREUNINSTALL`` /
;     ``NSIS_HOOK_POSTUNINSTALL`` macros. A bare ``customInstall`` /
;     ``customUnInstall`` macro is NEVER called — those names are kept as
;     thin aliases so older references and focused tests keep resolving.
;   * Tauri's wizard has NO ``MUI_PAGE_COMPONENTS`` page. Inserting one
;     would expose Tauri's own ``EarlyChecks`` / ``WebView2`` / ``Install``
;     sections as optional checkboxes (a user could untick Install). The
;     pack choice is therefore a dedicated ``Page custom`` with an
;     nsDialogs checkbox, NOT a Components-page Section.
;
; The pack itself is NEVER bundled into the slim-core installer (it would
; bloat the installer from ~35 MB to ~215 MB: see
; plan-runtime-pack-split.md §5.3). The checkbox state is persisted to
; ``installer-state.json`` and the slim-core app reads it on first launch
; to decide whether to start the silent background pack download
; (plan §4.8).
;
; JSON schema (pinned by tests in ``tests/tauri/test_installer_naming.py``):
;
;     {
;       "include_offline_engine_pack": <bool>,
;       "installer_version": "<VERSION>",
;       "pack_bundled": false
;     }
;
; ``pack_bundled`` is false for the slim-core installer; the full-offline
; installer template (``scripts/windows/full-offline-installer.nsi``) sets
; it true when it bundles the pack zip in-tree.
;
; Page order produced by this include (insertion order = wizard order):
;   Terms of Service → Offline engine pack option → (Tauri) Welcome →
;   Directory → Install → Finish.
;
; VALIDATE ON WINDOWS HOST:
;   1. Build the slim-core installer:
;         cd src-tauri && cargo tauri build --config tauri.windows-x86_64.conf.json
;   2. Run the resulting ``lausu-<version>-x64-setup.exe``.
;   3. Confirm the "Include offline engine pack" checkbox appears (default
;      ticked) on the pack-option page.
;   4. Untick it, finish the install.
;   5. Verify the state file was written with the consent value false:
;         type "%LOCALAPPDATA%\lausu\installer-state.json"
;         (Expected: {"include_offline_engine_pack": false, ...})
;   6. Repeat with the checkbox ticked, confirm the value is true.

!include nsDialogs.nsh

; ─── Terms of Service page (installer consent) ───────────────────────────
; Mandatory ToS page BEFORE the pack option and Tauri's own pages.
; ``MUI_LICENSEPAGE_CHECKBOX`` turns the page's "I agree" button into a
; mandatory checkbox, making the installer acceptance the single up-front
; legal contract for the app's third-party network features (cloud/model
; downloads still use consent; the offline engine pack downloads
; silently/always-on — see installer-license.txt).
!ifndef MUI_PAGE_LICENSE_INSERTED
  !define MUI_LICENSEPAGE_CHECKBOX
  !define MUI_LICENSEPAGE_CHECKBOX_TEXT "I agree to the Terms of Service and consent terms"
  !insertmacro MUI_PAGE_LICENSE "${__FILEDIR__}\installer-license.txt"
  !define MUI_PAGE_LICENSE_INSERTED
!endif

; ─── Pack-option state ───────────────────────────────────────────────────
; "1" = user wants the pack (default). Silent/passive installs keep "1"
; (always-on product decision; the checkbox is an opt-OUT).
Var IncludeOfflineEnginePack
Var IncludeOfflineEnginePackCheckbox

; ─── Custom pack-option page ─────────────────────────────────────────────
; Inserted here so it lands after the ToS page and before Tauri's Welcome.
; The PRE function aborts the page under /S or /P (default stays "1").
!ifndef LAUSU_PACK_OPTION_PAGE_INSERTED
  !define MUI_PAGE_CUSTOMFUNCTION_PRE LausuPackOptionPre
  Page custom LausuPackOptionCreate LausuPackOptionLeave
  !define LAUSU_PACK_OPTION_PAGE_INSERTED
!endif

Function LausuPackOptionPre
  StrCpy $IncludeOfflineEnginePack "1"
  ${If} ${Silent}
    Abort
  ${EndIf}
  ; Tauri passive mode (/P): skip interactive pages, keep the default.
  ${GetOptions} $CMDLINE "/P" $0
  ${IfNot} ${Errors}
    Abort
  ${EndIf}
FunctionEnd

Function LausuPackOptionCreate
  !insertmacro MUI_HEADER_TEXT "Optional components" "Choose which optional components to install"
  nsDialogs::Create 1018
  Pop $0
  ${If} $0 == error
    Abort
  ${EndIf}

  ${NSD_CreateLabel} 0 0 100% 24u "Offline engine pack (~180 MB). Downloads automatically in the background on first launch when needed. Cloud transcription works without it."
  Pop $0

  ${NSD_CreateCheckBox} 0 40u 100% 12u "Include offline engine pack"
  Pop $IncludeOfflineEnginePackCheckbox
  ${NSD_SetState} $IncludeOfflineEnginePackCheckbox ${BST_CHECKED}

  nsDialogs::Show
FunctionEnd

Function LausuPackOptionLeave
  ${NSD_GetState} $IncludeOfflineEnginePackCheckbox $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $IncludeOfflineEnginePack "1"
  ${Else}
    StrCpy $IncludeOfflineEnginePack "0"
  ${EndIf}
FunctionEnd

; ─── State writer (Tauri NSIS_HOOK_POSTINSTALL) ──────────────────────────
; Tauri invokes ``NSIS_HOOK_POSTINSTALL`` after the main app files are
; written and before the installer exits. ``customInstall`` is a thin
; alias kept for older references.
;
; The state file lives at ``%LOCALAPPDATA%\lausu\installer-state.json``,
; the SAME per-user data root the Python backend uses for the runtime
; pack (plan §4.7). JSON shape pinned by
; ``tests/tauri/test_installer_naming.py``. Keep the field names EXACT.
!macro LausuWriteInstallerState
  CreateDirectory "$LOCALAPPDATA\lausu"
  ClearErrors
  FileOpen $0 "$LOCALAPPDATA\lausu\installer-state.json" w
  IfErrors installer_state_done
  ${If} $IncludeOfflineEnginePack == "1"
    FileWrite $0 `{"include_offline_engine_pack": true, "installer_version": "${VERSION}", "pack_bundled": false}`$\r$\n`
  ${Else}
    FileWrite $0 `{"include_offline_engine_pack": false, "installer_version": "${VERSION}", "pack_bundled": false}`$\r$\n`
  ${EndIf}
  FileClose $0
  DetailPrint "[lausu-installer] Wrote installer-state.json (include_offline_engine_pack=$IncludeOfflineEnginePack)."
  installer_state_done:
!macroend

!macro NSIS_HOOK_POSTINSTALL
  ; Belt-and-suspenders: silent/page-skipped paths leave the default "1"
  ; (LausuPackOptionPre sets it); re-assert so a missing Var never writes
  ; an empty selection.
  ${If} $IncludeOfflineEnginePack == ""
    StrCpy $IncludeOfflineEnginePack "1"
  ${EndIf}
  !insertmacro LausuWriteInstallerState
!macroend

; Alias: older call sites / focused tests look for this name. Tauri does
; NOT invoke it directly — NSIS_HOOK_POSTINSTALL is the real hook.
!macro customInstall
  !insertmacro NSIS_HOOK_POSTINSTALL
!macroend
