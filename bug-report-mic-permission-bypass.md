# Bug report + fix task: microphone permission revocation is completely bypassed

**Status:** verified — root-caused to four independent defects, all confirmed in source and in the
attached runtime log.
**Severity:** high. The app silently pretends to record, loads a multi-GB model for nothing, and
leaves the UI stuck forever. The user is told nothing.

---

## 0. Golden Rule (binding, highest priority)

> **Always search online for the solution. Do NOT depend on training data or assumptions.** An answer
> you haven't checked is a `suspected` fact, never a `verified` one; checking is not conditional on
> doubt, and confidence is never a reason to skip the search. Sometimes you might be wrong, and
> sometimes one search saves hours: a problem you are facing has very likely happened to someone else
> who already solved it — do not reinvent the wheel, do not overthink, do not trial-and-error back and
> forth. Start with a web search, use the latest official documentation and current community notes,
> see how people handle it, and do the same. If you don't know the solution, search instead of going
> back and forth. This rule binds before every other rule in this file.

Apply it to every platform-specific claim in this report. In particular, **search for the current,
documented PortAudio / sounddevice / WASAPI / CoreAudio / PipeWire error signatures** that indicate
"microphone blocked by OS privacy settings" on each platform before you pick a discriminator. Do not
assume the codes in this report are complete — they are what *this* machine produced.

---

## 1. The problem

Microphone access was disabled completely in the OS privacy settings, so no application on the device
may use the microphone. The expectation is that the app detects this, refuses to start, and says so.

What actually happened: **the app behaved as if the microphone were fully available.** Pressing the
hotkey produced no in-app toast, no OS notification, no bubble state change, and no indication of any
kind that microphone access was disabled. The bubble showed the *recording* state, the home window
showed "Recording", and the model was loaded into memory — all of it fake, because nothing was being
captured (`recorded_rms=0.0000`).

---

## 2. Reproduction

1. Fresh start of the app, then disable the microphone for all apps in the OS privacy settings
   (Windows: Settings → Privacy & security → Microphone → off, including "Let desktop apps access
   your microphone").
2. Press the dictation hotkey.
3. Observe: no toast, no notification, bubble goes to *recording*, home window shows "Recording".
4. Press the hotkey again to stop.
5. Observe: bubble goes to *transcribing* and **stays there indefinitely**.

### Evidence from the runtime log

```
[HOTKEY FIRED] toggle_dictation called (recording=False, busy=False, model_loaded=True ...)
[DICTATION] Starting recording... (cycle=#1)
WARN  [PERMISSION] Windows mic permission probe itself raised (falling back to GRANTED;
      runtime PortAudio failure will be re-classified by the recorder):
      Error opening InputStream: Unanticipated host error [PaErrorCode -9999]:
      'Undefined external error.' [MME error 1]
WARN  [RECORDING] Failed to open input device [27]: ... Invalid device [PaErrorCode -9996]
INFO  [RECORDING] Configured mic failed on its host API. Trying all available input devices as fallback.
WARN  [RECORDING] Fallback device [1] also failed: ... PaErrorCode -9999 ...
WARN  [RECORDING] Fallback device [11] also failed: ... PaErrorCode -9999 ...
WARN  [RECORDING] Fallback device [25] also failed: ... PaErrorCode -9996 ...
WARN  [RECORDING] Fallback device [26] also failed: ... PaErrorCode -9996 ...
WARN  [RECORDING] Fallback device [0] also failed: ... PaErrorCode -9999 ...
WARN  [RECORDING] Fallback device [2] also failed: ... PaErrorCode -9999 ...
WARN  [RECORDING] Fallback device [3] also failed: ... PaErrorCode -9999 ...
INFO  [RECORDING] Fallback succeeded with device [28] Line In (Realtek HD Audio Line input)
WARN  [RECORDING] Selected microphone [System Default] failed to open (...); using device [28]
      for this session (saved selection unchanged)
INFO  [WAVEFORM] Bubble state -> recording
INFO  [DICTATION] Recording started OK (cycle=#1)
...
INFO  [WAVEFORM] Bubble state -> transcribing
INFO  [DICTATION] Recording stopped 0.0s of audio | recorded_rms=0.0000 | busy=True (cycle=#2)
INFO  [DICTATION] Audio too short, skipping transcription
```

Note the tell in the first warning: **the permission probe fell back to `GRANTED`.** Everything
downstream is a consequence of that single wrong answer.

---

## 3. What happens today — four independent defects

### Defect 1 — the Windows permission probe can never return `DENIED`

`voice_typer/server/permissions/mic.py:14-64` (`_check_windows_microphone`). It opens a 1-frame
`sounddevice.InputStream` and classifies the failure:

```python
    except OSError as exc:
        msg = str(exc).lower()
        if "access denied" in msg or "access is denied" in msg:
            return _p.MicrophonePermissionState.DENIED   # ← the ONLY path to DENIED
        ...
        return _p.MicrophonePermissionState.GRANTED
    except Exception as exc:
        ...
        return _p.MicrophonePermissionState.GRANTED      # ← where every real failure lands
```

`sounddevice.PortAudioError` inherits from `Exception`, **not** `OSError` (verified:
`PortAudioError.__mro__` == `(PortAudioError, Exception, BaseException, object)`). Therefore
**every** PortAudio failure — including a genuine access denial — is caught by `except Exception` and
returns `GRANTED`. The `except OSError` branch, the only one that can ever produce `DENIED`, is
unreachable dead code.

Secondary problem even after fixing the exception type: with mic privacy off, Windows reports
`PaErrorCode -9999 "Unanticipated host error"`, **not** the literal string `"access denied"`. So the
string discriminator is also wrong for the real-world signal. This is where the Golden Rule applies
most directly — search for the documented signatures before choosing a replacement.

### Defect 2 — the pre-flight gate is therefore a no-op

`voice_typer/server/recording/recorder.py:340` calls `verify_microphone_accessible()`, and
`voice_typer/server/permissions/checker.py:185-194` raises `MicrophonePermissionDeniedError` **only**
when the state is exactly `DENIED`. Because Defect 1 guarantees `GRANTED`, nothing is ever raised, and
`recording_lifecycle.start_recording()` runs. `UNKNOWN` is also treated as a pass, which is a second
hole on platforms whose probes commonly return `UNKNOWN`.

### Defect 3 — the fallback sweep converts a permission failure into a fake success

`voice_typer/server/recording/stream_lifecycle.py:317-432`. After the configured microphone fails, the
code sweeps **every** input device. It found `[28] Line In (Realtek HD Audio Line input)` on
WDM-KS — a line-in, which is not gated by the microphone privacy toggle — and reported
`Fallback succeeded`. So `start_recording` returned success, the bubble went to `recording`, the tray
and the home window followed, and the user got a completely convincing fake. The audio was silence:
`recorded_rms=0.0000`, `0.0s of audio`.

This means that even with Defects 1 and 2 fixed, any future path that misses the permission check will
still be masked by this sweep. The sweep must not be allowed to override an explicit permission
denial.

### Defect 4 — the model is loaded before the permission check

`voice_typer/server/recording_lifecycle.py:181-195`, inside the hotkey `toggle()`. When no engine is
loaded, the code kicks `app.models.start_background_load()` at line 189 and only then calls
`app._start_dictation()` at line 205 — which reaches the permission check at `recorder.py:340`. So on a
denied hotkey press the app loads the model into memory first and discovers the denial afterwards, if
at all. Model loading **at startup** is correct and must stay; loading **on hotkey press** must be
gated behind the permission check.

### Defect 5 — the "audio too short" path never resets the bubble

`voice_typer/server/recording_lifecycle.py:701` sets the bubble on the **stop** path, before the
transcription worker even runs:

```python
app._waveform_bubble.set_state("transcribing" if _engine_ready else "loading")
```

Then `voice_typer/server/recording_lifecycle.py:820-826`:

```python
        if duration < 0.5:
            log.info("[DICTATION] Audio too short, skipping transcription")
            controller._cancel_streaming_session()
            app.tray.set_state(AppState.IDLE, i18n.t("state.recording_controller.too_short"))
            app._busyness.set_idle()  # busy = False (coordinator)
            app._schedule_timer(2.0, lambda: app.tray.set_state(AppState.IDLE))
            return
```

The tray is reset to `IDLE` and the busy flag is cleared, but the **bubble is never reset** — so it
stays on `transcribing` forever. That is the "stuck indefinitely" the user observed. Line 701 is
correct for the normal path; the fix belongs in the too-short branch.

### Defect 6 — the `permission_revoked` bubble state has no producer

`BubbleMode` has ten members, but nothing anywhere in Python or Rust ever passes `permission_revoked`
(or `blocked`) to `set_state`. The *event* `microphone_permission_revoked` is fully wired —
`voice_typer/server/recording/device_health.py:304` probes during recording,
`voice_typer/server/recording_controller.py:283` stops the stream and publishes it, and
`voice_typer/client/src/renderer/src/hooks/useMicPermissionRevokedToast.ts` turns it into the in-app
banner. But that path only runs **mid-recording**, and it never touches the bubble. So the bubble
variant the user is asking for cannot currently be reached at all.

---

## 4. What it should be

On a hotkey press with microphone access disabled at the OS level:

1. **The permission check runs first** — before the model load, before any stream is opened, before
   any state is published.
2. **The probe answers correctly.** It must return `DENIED` when the OS has the microphone off, on
   every supported platform. If it genuinely cannot tell, it must return `UNKNOWN` and must not be
   silently converted into `GRANTED`.
3. **Nothing else happens.** No model load, no stream open, no fallback sweep, no `recording` bubble
   state, no tray change, no "Recording" on the home page. The denial must be terminal for that
   hotkey press.
4. **The user is told, three ways, immediately:**
   - an in-app toast using the existing `bubble.permissionRevokedLabel` string,
   - an OS / tray notification using `notify.recording_controller.mic_permission_revoked`,
   - the bubble switched to the **`permission_revoked`** variant (red dot, "Mic permission revoked",
     mic + dismiss buttons) — which requires adding the missing producer from Defect 6.
5. **Pressing the hotkey again repeats the refusal**, cleanly, with no side effects. The app recovers
   automatically once access is re-granted; no restart required.
6. **The bubble is never abandoned in a terminal state.** Any path that skips transcription must reset
   the bubble, exactly as it already resets the tray.

---

## 5. Hard constraints

- **The solution must be cross-platform.** It has to work and be verified on **Windows, macOS and
  Linux** — not just the Windows path this report was reproduced on. Each platform's probe
  (`_check_windows_microphone`, `_check_macos_microphone`, `_check_linux_microphone`) must be audited
  for the same class of bug: an exception handler that swallows the denial and returns a permissive
  state. Note that `_check_macos_microphone` returns `UNKNOWN` on several paths today, which the
  pre-flight gate treats as a pass. Fix the whole family, not the one instance. Search for the
  documented per-platform denial signatures rather than reusing the Windows codes verbatim.
- **Follow the Golden Rule** (section 0) throughout — search before asserting any platform behaviour.
- **Add regression tests.** There must be a test proving the probe returns `DENIED` when the stream
  open raises a PortAudio error, a test proving the pre-flight blocks the start, a test proving the
  fallback sweep cannot override an explicit denial, a test proving no model load is kicked on a
  denied hotkey press, and a test proving the too-short path resets the bubble. Each new guard must be
  proven to **fail on the pre-fix code** before it is accepted.
- **Do not regress the legitimate paths.** Model loading at startup must still happen. The device
  fallback sweep must still rescue a genuinely unplugged/changed device. The too-short path must still
  skip transcription. Mid-recording revocation must still stop the stream and publish its event.
- **Keep the existing user-facing strings.** Reuse `bubble.permissionRevokedLabel`,
  `notify.recording_controller.mic_permission_revoked`,
  `state.recording_controller.recording_failed_permission` and the other catalog entries rather than
  adding duplicates (E7). Any new string must go through the catalog in every locale (C-I18N-1), and
  must use `{appName}`, never a hardcoded brand string (C-BRAND-1).
- **If the change touches a rendered surface, keep the design-system representations in sync in the
  same change** (C-DESIGN-1).

---

## 6. Verification

With microphone access disabled in the OS privacy settings and a fresh app start:

- Press the hotkey → in-app toast + OS notification + bubble in the `permission_revoked` variant,
  all appearing promptly.
- The log shows the probe reporting the denied state, and **no** `Trying all available input devices
  as fallback` sweep.
- The log shows **no** model load was kicked by the hotkey press.
- The home window does **not** show "Recording".
- Press the hotkey again → the same clean refusal, no side effects.
- Re-grant access → the next hotkey press records normally, with no restart.
- Stop a genuinely-too-short recording → the bubble returns to idle instead of hanging on
  `transcribing`.
- Repeat the whole check on macOS and Linux.
