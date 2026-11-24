# Onboarding UX plan

## Plain-English summary

Setup is a four-step wizard: Welcome → Consent → Model → Hotkey. It remembers
your choices, asks for consent before downloading, and has no way to skip.
Three things make it confusing today:

1. **The model list can show a developer-only test model and wrong sizes.**
   The curated list in `server/onboarding_selections.py:86-137` still starts
   with `tiny` and carries hand-written sizes (`~75MB`, `~670MB`) that disagree
   with the real registry (`server/gguf_model_registry.py:43-108`). A frozen
   build filters `tiny` out (`:75-83`), but a source build shows it.
2. **Every local model always says Download.** The wizard never asks
   `get_model_status`, so an already-installed model cannot offer Select, and a
   user can start a second download of the same pack.
3. **There is no safe exit and the checks are thin.** Skip was deliberately
   removed (ONB-3; `pages/Onboarding.tsx:16-18`, `:179-183`, `:360-362`), Back
   exists but is easy to miss (`:204-206`, `:338-348`), the microphone is
   never checked, and the hotkey test is a single optional button
   (`components/HotkeyStep.tsx:66-94`). The two progress bars are hand-rolled
   with `transition-all` (`pages/Onboarding.tsx:126-143`, `:234-249`;
   `components/ModelStep.tsx:482-513`), which breaks the shared bar rule
   (C-UI-12) and the reduced-motion rules (C-ANIM-1/3).

**Plan, in priority order:**

1. Make the five production registry models the only list, with registry sizes.
2. Add installed/Select/Active states from `get_model_status`; keep the
   consent gate before every download.
3. Add a microphone check with recovery, a visible Back, and a confirmed Skip
   that uses the backend's existing `onboarding_skip` completion path.
4. Replace both hand-rolled bars with the shared `LevelBar`, shorten copy, and
   add localized strings in all 8 locales.
5. Prove it with focused tests (states, ordering, navigation, resume, i18n) and
   the repo's axe scans.

## E1 audit (current flow, file:line)

| Area | What happens today | Evidence |
| --- | --- | --- |
| Steps | Backend owns a fixed 4-step controller; Welcome/Consent/Model/Hotkey. Microphone, OS permissions and summary steps were removed. | `server/onboarding.py` controller; `pages/Onboarding.tsx:10-15`, `:202-311`; `pages/onboarding/lib/constants.ts:1-15` |
| Copy | Short one-line headings per step; step progress text is "Step N of M". Progress bar duplicates that text. | `pages/Onboarding.tsx:225-267`; locale `onboarding.*` keys |
| Permissions | Consent is one consolidated step with 7 toggles + Agree to All; toggles persist immediately through `set_config`. Cloud provider consent is a point-of-use gate when leaving the Model step. | `components/ConsentStep.tsx:26-66`, `:94-138`; `hooks/useOnboardingWizard.ts:199-233`, `:545-577` |
| Hotkey | Presets from IPC, default Caps Lock, optional inline test with a 10 s keydown listener. No OS-permission probe. | `components/HotkeyStep.tsx:51-94`; `hooks/usePermissionsProbe.ts:55-82`; `lib/constants.ts:33-34` |
| Microphone | No step and no check. `onboarding_get_microphones` exists but is not called by the wizard. Default mic semantics live in Settings. | `pages/Onboarding.tsx:10-15`; `server/onboarding_selections.py:34-47` |
| Model choice | ToggleGroup local/cloud. Curated model list + full catalog merge; catalog-only entries are appended. | `components/ModelStep.tsx:162-291`, `:384-467`; `hooks/useOnboardingWizard.ts:354-367`, `:773-791` |
| Download | Explicit per-model click; HuggingFace consent gate first; `download_progress` events drive a number and hand-rolled bar. No installed state. | `hooks/useOnboardingWizard.ts:402-467`; `components/ModelStep.tsx:221-248`, `:482-513` |
| Cloud | Provider + API key; key omitted when blank (get_config redacts); consent gate on leave. | `hooks/useOnboardingWizard.ts:43-60`, `:492-530`, `:556-577`; `components/ModelStep.tsx:515-569` |
| Language | App locale picker on Welcome only; dictation language is not chosen here. | `components/WelcomeStep.tsx:20-70` |
| First dictation | Not part of onboarding; apply marks setup complete and returns Home. | `hooks/useOnboardingWizard.ts:596-630` |
| Skip / Back | Skip removed; Back from step 2 onward. | `pages/Onboarding.tsx:16-18`, `:179-183`, `:204-206`, `:338-362`; `hooks/useOnboardingWizard.ts:642-653` |
| Persistence / resume | `onboarding_start` returns server step; `get_config` refills hotkey/model/backend/provider/consents on every start (including resume). Controller persists progress. | `hooks/useOnboardingWizard.ts:245-347`; `server/onboarding.py` progress persistence |
| Error / offline | Fatal init → themed `ErrorState` with Retry/Reload/copy; content fetch failure surfaces as `initError`; apply failure has inline alert. | `pages/Onboarding.tsx:179-198`, `:313-332`; `hooks/useOnboardingWizard.ts:368-387`, `:585-630` |
| First run vs re-run | `onboarding_start` rejects already-complete sessions with `client.onboarding_already_complete`, which redirects Home; re-run uses `{force: true}` elsewhere. | `hooks/useOnboardingWizard.ts:369-377`; `server/handlers/onboarding_handlers.py:41-74` |

### Ruled out

- Adding a real Microphone or Permissions *step*: that changes the backend
  step contract and IPC surface. The check is surfaced inside an existing step
  instead (no new command).
- Reading `gguf_model_registry.py` from the renderer: forbidden. The backend's
  existing `onboarding_get_model_options` / `get_model_catalog` helpers carry
  the registry truth over IPC.
- Inventing hashes or downloading anything in tests/CI: the registry already
  pins SHA-256 + byte size; tests use fakes only.

## Owner visual checklist (plain English)

Open the wizard on a fresh profile (and again with an existing config to check
resume). Confirm, in this order:

1. **Welcome** — the step reads "Step 1 of 4", the text is short, the language
   picker works, and a microphone status line says how many input devices were
   found (or tells the user what to do when none are found).
2. **Consent** — seven rows, each with a `?` explanation; Agree to All and
   individual switches persist; nothing is downloaded here.
3. **Model** — exactly five local models, no `tiny`, sizes match the Models
   page; an installed model offers Select (and Active when chosen), a missing
   one offers Download. Clicking Download opens the consent dialog first; the
   bar fills with the shared blue fill and a percent, and Reduce Motion removes
   its transitions.
4. **Back / Skip** — Back returns to the previous step with selections intact.
   Skip asks for confirmation; accepting completes setup with defaults and
   does not show the wizard again on the next launch.
5. **Hotkey** — preset selector, default-hint, Test hotkey gives clear
   success/failure text and times out honestly after 10 s.
6. **Keyboard / screen reader** — Tab order reaches every control, focus rings
   stay visible, step changes are announced, and every progressbar has a name
   and value.
7. **Resume** — quit mid-wizard, relaunch: same step, saved hotkey/model/
   provider/consents, no clobbering with defaults.

## License / dependency notes

No new dependency or network destination. Sizes, names and quantization come
from the existing GGUF registry; the five production packs keep their existing
publisher licenses (CC-BY-4.0 for Parakeet, Apache-2.0 for Qwen3-ASR, MIT for
Whisper weights — see `server/gguf_model_registry.py:43-108`). `tiny` stays
dev-only and is filtered from every user-facing surface.
