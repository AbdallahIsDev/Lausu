# Plan: Listen Live feedback + mic-volume guard

## Background

Live monitor (`useLiveListen`, pure frontend: getUserMedia → AudioContext →
GainNode → destination) ships with a fixed `MONITOR_GAIN = 0.8` straight to
the system speakers. On speakers (especially laptop speakers next to the
mic) this builds a speaker→mic→speaker loop: ringing, phantom sounds, meter
slamming to 100%. Separately, Windows/driver auto-gain then slides the OS
mic knob down (100 → 92 → 88…), and the user requires it pinned at 100%.

Prior discussion graded five candidate fixes. Adopted: **S1** (quiet capped
preview), **S2** (subtract our own sound), **S5** (mic guard + one-click
restore). Rejected: auto-stop on howl (user can stop it themselves),
talk-or-listen (room noise alone can ring, so it fixes neither case),
any flow requiring OS settings changes, any headset requirement.

## Goals

- Listen Live on speakers can never build into a sustained loop.
- OS mic knob stays at 100%; any outside move is restored in-app, instantly.
- Zero system-settings diving, zero headset requirement, out of the box.
- Mic knob is never moved by us except the explicit user-pressed restore.

## Non-goals

- No auto-duck of the speakers for Live (verdict below).
- No auto-stop, no talk-or-listen mode.
- No OS settings instructions anywhere in the flow.

## Verdict: auto-duck for Live — NO (as automatic behavior)

Dictation ducking lowers *unrelated background content* so the mic doesn't
hear it. For Live it would lower *the signal under test itself*: users tune
filters by ear, and quieter preview hides the very noise they are hunting.
It is also redundant — S1's preview gain is already the volume control for
this path, and two volume mechanisms on one path fight and confuse. It
additionally inherits restore-on-crash edge cases. Adopted instead: a
one-time offer (S1 step 4).

## Workstream S1 — quiet capped preview (useLiveListen)

1. Replace fixed `MONITOR_GAIN = 0.8` with a user level + hard cap constant
   (`LIVE_LISTEN_MAX`, well below loop gain on adjacent laptop hardware).
2. Insert a ceiling node (DynamicsCompressorNode, fast attack) between gain
   and destination so no spike can pass full-blast, whatever the mic hears.
3. Preview volume slider on the Microphone page (own control, persisted via
   new `live_listen_level` config key 0–1, default ~0.5). It controls ONLY
   the preview tap; mic gain and meter are untouched.
4. One-time offer, not auto-duck: if system output is >90% when Live starts,
   show a sticky note with [Lower to 75%] [Keep as is]; remember per
   session. Never moves speakers unasked.
5. New config key goes through the SEC-002 `set_config` allowlist +
   validator like every other key.

## Workstream S2 — subtract our own sound (browser AEC first)

1. Request the browser's built-in canceller on the capture track:
   `getUserMedia({ audio: { echoCancellation: true, noiseSuppression: false,
   autoGainControl: false } })`. NS/AGC stay OFF so they can't fight the
   user's own filter tuning or touch gain.
2. Verify by ear on speakers (hot mic, laptop). Ship if the loop is gone
   at normal preview levels.
3. Fallback only if insufficient: native canceller (SpeexDSP-class) — NOTE:
   the Live path is frontend-only, so this means moving monitoring through
   the backend. Major surgery; do NOT start here.

## Workstream S5 — mic guard at 100% + one-click restore

1. Backend: new mic-volume surface (get/set/watch), modeled on the existing
   speaker-side `volume_backends/` pattern:
   - Windows: capture-endpoint volume (same pycaw family, pointed at the
     mic instead of the speakers).
   - Linux: source volume via the PulseAudio/PipeWire control path.
   - macOS: best-effort — most built-in mics expose no settable input
     gain. Where the OS allows nothing, show the message without the
     button (never pretend).
2. Watcher: notice an outside move within seconds (not hourly). Anti-flap:
   restore at most ~3 times per few minutes, then notify-only so we never
   tug-of-war a stubborn driver.
3. Renderer: sticky message (stays until X, same persistent-toast pattern
   as the pack toast): "Microphone was lowered to 92%" + single
   [Back to 100%] button. Fixed 100% — NOT restore-previous (previous is
   the broken value) and NOT a slider (a slider becomes a tug toy while a
   driver keeps pulling). The button writes the real device knob.
4. New `mic_guard_enabled` config key (default ON), SEC-002 allowlist.

## Workstream S0 — guidance note (approved with tweaks)

- One short static line under the Live buttons, above Microphone Quality:
  headphones recommended for Listen Live on speakers, laptop or desktop.
- Static on purpose: reliable headphone detection is flaky
  cross-platform, and a static line can't be wrong. Complements (does not
  replace) the existing while-listening hint.
- New i18n key, all 8 locales (C-I18N-1).

## i18n (all 8 locales each)

`liveListen.guideNote`, `liveListen.previewVolume`,
`liveListen.lowerSpeakersOffer` + [Lower to 75%] [Keep as is],
`micGuard.loweredTitle/message` + `micGuard.backTo100`.

## Tests (E6, with the change)

- S1: preview gain/cap unit pins (gain node value, ceiling node present,
  slider→gain wiring); offer shows only >90% + once per session.
- S2: getUserMedia constraint pin; by-ear QA script (below), not unit.
- S5: restore writes device value (mocked backend), anti-flap pin,
  toast action calls the IPC, macOS-no-gain path shows message only.
- Regression: existing `useLiveListen`, mic-interaction, a11y suites stay
  green; `typecheck:ci` + full focused runs per C-TEST-6 on final state.

## Acceptance

- Hot mic + laptop speakers, Live on, slider at max: no sustained loop,
  no phantom growth; meter follows voice only.
- Forced mic-knob drop (or loud-event clamp): sticky message within
  seconds, one click restores real device value to 100%.
- No flow asks for headphones, settings changes, or exclusive-mode
  toggles. Nothing in the flow mentions them.

## Risks

- Browser AEC quality varies by room/driver; S1's cap is the backstop
  that holds even if S2 underperforms.
- Driver that re-clamps continuously: anti-flap + notify-only bounds it.
- macOS no-gain devices: message-only path, no fake button.

## Manual QA script (speakers, hot mic, enhancements ON)

1. Live on, slider max: talk, clap, stay silent 10s — expect clean
   preview, no growth, meter sane.
2. Bang desk near mic: expect knob still 100% (guard), or sticky
   message + one-click restore.
3. Speakers at 100%: expect the one-time offer, never an auto-change.
