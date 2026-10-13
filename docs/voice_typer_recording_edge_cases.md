# Voice Typer: Recording and Escape-Key Edge Cases

## Purpose and scope

This document is a forward-looking inventory of possible edge cases for
two areas of Voice Typer:

1.  **Escape-key cancellation** --- what should happen when the user
    presses Escape during recording, transcription, or any intermediate
    processing stage.
2.  **Recording hotkey behavior** --- what should happen when the user
    presses the recording hotkey repeatedly, especially while the model
    is loading, and how to distinguish valid speech from accidental,
    empty, or extremely short recordings.

This is an edge-case checklist, not an audit of the current
implementation. It intentionally includes cases that may already be
handled, partially handled, or unresolved. The project can assess each
item separately later.

## 1. Escape-key cancellation

### 1.1 Escape during recording

-   [ ] The user presses Escape during a normal recording. The current
    recording is discarded and is not sent for transcription.
-   [ ] The user presses Escape immediately after starting recording,
    before meaningful audio has been captured.
-   [ ] The user presses Escape after speaking but before pressing the
    recording hotkey again to finish.
-   [ ] The user presses Escape repeatedly during the same recording.
-   [ ] Escape and the recording hotkey are pressed nearly
    simultaneously.
-   [ ] Escape is pressed just as the recording hotkey would normally
    stop recording and submit the audio.
-   [ ] The user presses Escape while the microphone is disconnected,
    unavailable, muted, or failing.
-   [ ] The user presses Escape while the microphone is connected but
    captures only silence or background noise.
-   [ ] Escape is pressed while the app is still initializing
    recording-related UI.
-   [ ] Escape is pressed while the recording indicator or recording
    modal is opening, closing, or animating.
-   [ ] The user starts a recording, changes focus to another window,
    and presses Escape. The intended behavior should be clear:
    cancellation should not depend accidentally on which window has
    focus.
-   [ ] Escape is pressed when no recording or transcription operation
    exists. It should not cancel an unrelated action or affect the next
    recording.
-   [ ] Escape is pressed after the recording has already been
    discarded. Repeated cancellation should be harmless.
-   [ ] Escape is pressed after the user has already stopped recording
    and the audio has been submitted. The app should not accidentally
    treat the submitted audio as a still-active recording.

### 1.2 Escape while the modal or recording UI is loading

-   [ ] The user presses the recording hotkey while the modal is still
    loading in the background.
-   [ ] The user starts recording before the modal finishes loading,
    then presses Escape while recording is active.
-   [ ] Escape discards the audio, while modal initialization continues
    safely in the background.
-   [ ] The modal finishes loading after the recording was discarded.
    The discarded audio must not be submitted later.
-   [ ] The modal finishes loading at almost the same moment that Escape
    is pressed.
-   [ ] Escape is pressed while the modal is loading and the recording
    hotkey is also pressed again.
-   [ ] The modal fails to load after the user has started and discarded
    a recording.
-   [ ] The modal is closed or hidden while loading, then finishes
    loading. It must not unexpectedly reopen or submit a discarded
    recording.
-   [ ] Multiple recording attempts occur while the modal is still
    loading. The app should not accidentally queue recordings that the
    user intended to cancel.
-   [ ] A loading indicator remains visible after cancellation even
    though no recording is active.
-   [ ] The UI says recording is active when the audio capture has
    already been cancelled, or says it is cancelled while capture
    continues in the background.

### 1.3 Escape during transcription and post-processing

The submitted audio may pass through several stages. Depending on the
implementation, these can include waiting for the model, audio
preparation, transcription, text cleanup or polishing,
vocabulary/dictionary processing, formatting, and delivery of the final
text.

-   [ ] The user presses Escape while the audio is waiting for the model
    to finish loading.
-   [ ] The user presses Escape while the audio is queued for
    transcription.
-   [ ] The user presses Escape while audio is being prepared or
    transformed before transcription.
-   [ ] The user presses Escape while the ASR model is actively
    transcribing.
-   [ ] The user presses Escape after transcription finishes but before
    text processing begins.
-   [ ] The user presses Escape during text polishing or rewriting.
-   [ ] The user presses Escape while custom vocabulary or dictionary
    substitutions are being applied.
-   [ ] The user presses Escape during formatting, punctuation, or other
    post-processing.
-   [ ] The user presses Escape after processing finishes but before the
    final text is delivered.
-   [ ] The user presses Escape at the exact moment the final text is
    being inserted into the target application.
-   [ ] The user presses Escape after some text has already been
    inserted. The app needs a clear rule for whether inserted text can
    be reverted or whether cancellation only prevents further output.
-   [ ] The user presses Escape after the final result has already been
    delivered. It should not remove or corrupt text unexpectedly.
-   [ ] Escape is pressed between two consecutive processing stages.
-   [ ] Escape is pressed while a stage is completing, creating a race
    between cancellation and the next stage starting.
-   [ ] A stage ignores or cannot immediately stop a cancellation
    request. Later stages must still avoid processing or delivering the
    cancelled result where possible.
-   [ ] A background task finishes after cancellation. Its late result
    must not overwrite the UI or be delivered as if it belonged to a
    newer recording.
-   [ ] The user starts a new recording after cancelling an earlier
    transcription. Results from the old operation must not be confused
    with the new operation.
-   [ ] The user presses Escape more than once while a transcription is
    already being cancelled.
-   [ ] Cancellation occurs while a remote cloud model is processing the
    audio. The local app may be able to stop waiting or discard the
    result even if it cannot stop work already running on the provider's
    server.
-   [ ] Cancellation occurs while a local model is processing. Determine
    whether the operation can be interrupted, must finish in the
    background, or can only have its result discarded.
-   [ ] Cancellation occurs during a network timeout, retry, or
    automatic re-submission.
-   [ ] Cancellation occurs while a processing error is being reported.
    The app should not show contradictory cancelled and failed states.
-   [ ] Cancellation occurs when transcription returns no text or an
    error.
-   [ ] Cancellation occurs while the app is showing a progress
    indicator, toast, or other notification related to the operation.
-   [ ] The UI indicates cancellation succeeded even though a later
    processing stage still delivers text.
-   [ ] The UI continues showing a transcription-in-progress state after
    the operation has been cancelled.

### 1.4 Choosing and defining cancellation behavior

These are policy decisions to make explicit rather than leaving them to
incidental implementation details.

-   [ ] **Recording-only cancellation:** Escape cancels only while audio
    capture is active; after submission, Escape does nothing to that
    operation.
-   [ ] **Cancellation throughout the pipeline:** Escape can cancel or
    discard the operation during waiting, transcription,
    post-processing, and delivery.
-   [ ] **Best-effort cancellation:** the app stops work when possible
    and always prevents a cancelled result from being delivered, even if
    some underlying computation cannot be interrupted.
-   [ ] The app communicates clearly when Escape is no longer able to
    stop a stage, rather than silently ignoring the key or implying that
    cancellation occurred.
-   [ ] The same Escape press cannot both cancel one operation and
    accidentally affect another operation that starts immediately
    afterward.
-   [ ] Escape does not close an unrelated modal, dismiss an unrelated
    notification, or trigger another default UI action when it is
    intended to cancel a recording.
-   [ ] Escape behavior is consistent when the main window, bubble,
    recording modal, or another application has focus.
-   [ ] Escape behavior is defined when the user has changed the
    configured hotkey or has assigned Escape to another action.
-   [ ] The app distinguishes cancelling the audio capture from
    cancelling the whole transcription job.
-   [ ] The app defines whether a cancelled recording is retained in
    history, deleted entirely, or recorded as a discarded item.
-   [ ] The app defines whether cancellation produces a notification, a
    silent dismissal, or a temporary status message.
-   [ ] A cancellation request is idempotent: repeating it does not
    create duplicate cleanup, duplicate notifications, or state
    corruption.
-   [ ] Cancellation cleans up audio buffers, temporary files, queue
    entries, and task state without deleting resources still used by
    another operation.
-   [ ] Cancellation does not leave the microphone open, a hotkey
    locked, a spinner running, or a recording state stuck.
-   [ ] Cancellation does not leave the application believing that an
    operation is active when it is no longer active.

### 1.5 Escape key delivery and input-level cases

These cases are about the key press itself reaching (or not reaching)
the app, before any cancellation logic runs.

-   [ ] The user holds Escape down instead of tapping it, so the
    operating system sends repeated Escape events. Repeats must not
    cause double cleanup, duplicate notifications, or errors.
-   [ ] Escape is pressed while the user is typing in Settings or
    another text field. The app needs a rule for whether that press
    cancels an active recording or only affects the focused field.
-   [ ] Escape is pressed while a microphone-permission prompt is open.
-   [ ] Escape is pressed while the screen is locked or the screensaver
    is active.
-   [ ] The user has assigned Escape itself as (or as part of) the
    recording hotkey. Pressing it must not both start and cancel a
    recording at once.
-   [ ] The Escape press is delivered to the focused application and
    never reaches the global listener, so nothing happens while the
    user believes cancellation failed.
-   [ ] Sticky Keys or another accessibility feature changes how the
    Escape press is delivered.
-   [ ] Escape is pressed on a keyboard layout, virtual keyboard, or
    remote-desktop session where the key code differs.
-   [ ] Escape is pressed during onboarding or the first-run flow,
    before normal recording exists.

### 1.6 More transcription-pipeline cancellation points

Finer cut points inside the pipeline, in addition to the stages in
1.3.

-   [ ] Escape is pressed after recording stopped but before the audio
    has been handed to the transcription queue.
-   [ ] Escape is pressed while the audio is being uploaded to a cloud
    provider. The upload may not be recallable even if the eventual
    result is discarded locally.
-   [ ] Escape is pressed while partial or streaming text is already
    displayed. The rule must cover whether shown text is removed.
-   [ ] Escape is pressed during a retry wait (backoff delay) after a
    failed transcription attempt.
-   [ ] Escape is pressed while the app is falling back from a failed
    local model to another engine or provider.
-   [ ] Escape is pressed while a cloud language model is polishing the
    transcribed text (a second network call after transcription).
-   [ ] Escape is pressed while the final text is being written to
    history.
-   [ ] Escape is pressed while the app is restoring the clipboard after
    pasting the result.
-   [ ] Escape is pressed while an error dialog for the same operation
    is open. Dismissing the dialog and cancelling the job must not
    conflict.
-   [ ] Escape is pressed after the user already copied the result
    manually. Cancellation must not delete text the user already took.

## 2. Recording hotkey, repeated presses, and spam

### 2.1 Repeated hotkey presses and timing

-   [ ] The user presses the hotkey once to start recording and
    immediately presses it again to stop and submit.
-   [ ] The user presses the hotkey twice almost simultaneously.
-   [ ] The user presses the hotkey repeatedly in rapid succession:
    start, stop, start, stop.
-   [ ] The user presses the hotkey, waits about one second, and presses
    it again without saying anything.
-   [ ] The user holds the hotkey down instead of tapping it, if the
    keyboard or operating system reports repeated key events.
-   [ ] A single physical press generates duplicate key events due to
    keyboard repeat, driver behavior, or event handling.
-   [ ] The user presses the hotkey while the previous recording is
    still being finalized.
-   [ ] The user presses the hotkey while the previous recording is
    waiting for the model.
-   [ ] The user presses the hotkey while transcription is in progress.
-   [ ] The user presses the hotkey while post-processing or text
    delivery is in progress.
-   [ ] The user presses the hotkey while a cancellation is in progress.
-   [ ] The user presses the hotkey at the same time as Escape.
-   [ ] The user presses the hotkey just as the model becomes ready.
-   [ ] The user presses the hotkey just as the model becomes
    unavailable or crashes.
-   [ ] The user presses the hotkey while the app is changing models or
    switching between local and cloud models.
-   [ ] The user presses the hotkey while the app is starting, shutting
    down, or restarting its audio subsystem.
-   [ ] The user presses the hotkey while another recording UI or modal
    is already open.
-   [ ] The user presses the hotkey while the bubble is hidden,
    minimized, repositioning, or still loading.
-   [ ] The user presses the hotkey while the app is not focused, or
    while another app is receiving keyboard input.
-   [ ] The user presses the hotkey while the configured key is also
    used by the operating system or another application.
-   [ ] The user changes the hotkey while a recording is active.
-   [ ] A hotkey press is missed, delayed, or processed out of order.
-   [ ] The UI briefly shows recording as active even though the audio
    capture did not start.
-   [ ] The UI shows recording as inactive while the audio capture is
    still running.
-   [ ] A stop event is processed before the corresponding start event
    because of asynchronous timing.
-   [ ] Rapid toggling creates multiple active capture sessions or
    leaves one session orphaned.
-   [ ] Rapid toggling creates multiple submissions from the same audio
    segment.
-   [ ] Rapid toggling creates overlapping transcription jobs when the
    intended behavior is one active job.
-   [ ] The app's behavior remains deterministic even when key events
    arrive faster than UI updates.

### 2.2 Model loading and queued recordings

The model may still be loading in the background when the user finishes
a recording. In that case, the recording may wait until the model is
ready before transcription can begin.

-   [ ] The user completes one valid recording while the model is
    loading. It waits and is processed once the model is ready.
-   [ ] The user creates several recordings while the model is loading.
    The app must have an explicit queue policy instead of accumulating
    unlimited work.
-   [ ] The user repeatedly toggles recording while the model is
    loading, creating many very short segments.
-   [ ] The user creates a recording, then cancels it before the model
    is ready. It must never be processed after loading completes.
-   [ ] The user creates several recordings and cancels some but not
    others. Only valid, non-cancelled recordings should be eligible for
    processing.
-   [ ] The model finishes loading while several recordings are queued.
-   [ ] The model loading process fails after recordings have been
    queued.
-   [ ] The model loading process is retried or restarted while
    recordings are queued.
-   [ ] The user switches to another model while recordings are queued
    for the original model.
-   [ ] The user switches from a local model to a cloud model, or vice
    versa, while audio is waiting to be processed.
-   [ ] The model becomes unavailable after the recording finishes but
    before it can process the audio.
-   [ ] The user closes the app while recordings are queued.
-   [ ] The app crashes or the operating system shuts down while
    recordings are queued.
-   [ ] Queued recordings persist across an app restart unintentionally,
    causing old audio to be transcribed later.
-   [ ] A queued recording is processed more than once because of a
    retry or queue-state bug.
-   [ ] Queue order changes unexpectedly, so a later recording is
    processed before an earlier one.
-   [ ] A slow first transcription causes the queue to grow while the
    user keeps recording.
-   [ ] Queue limits are reached. The app should handle this predictably
    rather than consuming unbounded memory or silently losing audio.
-   [ ] The user receives clear feedback when a recording is waiting for
    model loading, rather than assuming transcription has started.
-   [ ] The UI accurately distinguishes model loading, queued audio,
    active recording, transcription, and completed processing.
-   [ ] A recording is still shown as queued after it has been
    discarded.
-   [ ] The model becomes ready after the user has stopped interacting.
    The app must not unexpectedly deliver stale or unwanted results.

### 2.3 Distinguishing valid recordings from accidental toggles

A short segment is not necessarily spam, and a long segment is not
necessarily valid speech. Duration alone may not be sufficient to
determine whether to submit audio.

-   [ ] The user presses the hotkey to start recording and immediately
    presses it again without speaking.
-   [ ] The user records less than one second of audio.
-   [ ] The user records about one second of audio.
-   [ ] The user records about two seconds of audio.
-   [ ] The user speaks a legitimate short command, such as a single
    word or brief phrase.
-   [ ] The user makes a short utterance with a long pause before or
    after the spoken word.
-   [ ] The user speaks quietly or at a low volume, making valid speech
    resemble silence.
-   [ ] The user speaks from far away from the microphone.
-   [ ] The user speaks while the microphone gain is low.
-   [ ] The microphone captures only room tone, fan noise, keyboard
    clicks, traffic, or other background noise.
-   [ ] The microphone captures a brief click or transient that looks
    like audio activity but contains no speech.
-   [ ] The microphone captures silence with a very low noise floor.
-   [ ] The microphone captures background noise that an ASR model may
    interpret as speech.
-   [ ] The user begins speaking immediately after starting recording,
    but the initial phoneme is clipped.
-   [ ] The user begins speaking just as recording stops, so the final
    word is clipped.
-   [ ] The user pauses briefly while speaking and the system mistakenly
    treats the pause as the end of the message.
-   [ ] The user says a short word that the model commonly hallucinates
    from silence or noise, such as "thank you."
-   [ ] The ASR model returns text for an empty or nearly empty
    recording.
-   [ ] The ASR model returns a plausible phrase even though the user
    did not speak.
-   [ ] The ASR model returns an empty result for valid but very quiet
    or short speech.
-   [ ] The user intentionally wants to dictate punctuation, a short
    command, or a single-word response.
-   [ ] A duration threshold rejects legitimate speech because the
    recording is too short.
-   [ ] A duration threshold accepts an empty recording because it is
    just above the minimum.
-   [ ] An audio-level threshold rejects quiet speech or accepts steady
    background noise.
-   [ ] Speech detection starts late or ends early because of noise
    suppression, voice activity detection, or microphone startup
    latency.
-   [ ] The audio contains speech mixed with silence or noise. The app
    must not classify the whole recording as empty solely because most
    of it is silent.
-   [ ] The audio is clipped, corrupted, or has an unexpected sample
    rate or channel layout.
-   [ ] The microphone becomes disconnected during a short recording,
    resulting in an empty or truncated segment.
-   [ ] The operating system or audio driver provides a buffer of zeros,
    stale samples, or duplicated samples.
-   [ ] The user tests the hotkey repeatedly to check whether recording
    starts, generating empty segments unintentionally.
-   [ ] A legitimate short recording is mistakenly classified as spam
    because it follows another recording quickly.
-   [ ] A series of valid short phrases is mistakenly merged, dropped,
    or rejected as spam.
-   [ ] Several empty segments are produced in quick succession. The app
    avoids submitting every one to the ASR model.
-   [ ] The app detects a likely empty recording before model submission
    and skips transcription where appropriate.
-   [ ] The app detects that the ASR result is likely a hallucination
    from silence or noise and handles it without inserting fabricated
    text.
-   [ ] The app does not silently alter or discard legitimate user
    speech merely because it is short.

### 2.4 Spam, burst handling, and resource limits

-   [ ] The user repeatedly starts and stops recording for several
    seconds.
-   [ ] Each short segment is queued while the model loads, creating a
    large backlog.
-   [ ] Each segment is submitted immediately when the model is ready,
    causing a burst of transcription requests.
-   [ ] Many short cloud requests are created, potentially increasing
    latency, API usage, or cost.
-   [ ] Many short local inference jobs are created, consuming CPU, GPU,
    memory, or power.
-   [ ] Audio buffers and temporary files accumulate because short
    segments are not cleaned up.
-   [ ] The queue grows faster than transcription can process it.
-   [ ] The app reaches a maximum queue size while the user continues
    pressing the hotkey.
-   [ ] The app is under heavy CPU or memory pressure and cannot process
    rapid hotkey events in time.
-   [ ] The user spams the hotkey while the app is unresponsive or the
    UI is frozen.
-   [ ] A burst of events produces duplicate notifications, progress
    indicators, or history entries.
-   [ ] A burst of events causes the wrong recording to be paired with
    the wrong transcription result.
-   [ ] A stale result from an earlier short recording arrives after a
    newer recording and overwrites or follows it unexpectedly.
-   [ ] The app applies rate limiting or a cooldown, but the user
    performs a legitimate rapid sequence of recordings.
-   [ ] The app rejects a new recording because another operation is
    active, but the UI fails to explain why.
-   [ ] The app drops a recording because of queue limits but does not
    notify the user.
-   [ ] The app attempts to process all queued recordings after loading
    finishes, even though most were accidental empty segments.
-   [ ] The app's queue policy is consistent across local and cloud
    models.
-   [ ] The app's queue policy is predictable after model errors,
    cancellation, retries, and app restarts.

### 2.5 Hotkey press shape and timing subtleties

These cases are about what a single press looks like physically,
before any toggle logic runs.

-   [ ] The user holds the hotkey down (push-to-talk style) instead of
    tapping to toggle. The app needs a defined meaning for hold
    versus tap.
-   [ ] A tap is so short that key-down and key-up arrive almost
    together. The app must not treat it as zero recordings or as two.
-   [ ] A debounce or cooldown window swallows a legitimate quick second
    recording (for example, dictating two short sentences in a row).
-   [ ] The user starts speaking at the exact moment recording starts,
    and the first fraction of a second is cut off while the audio
    device wakes up.
-   [ ] The user presses the hotkey while the audio device is still
    initializing from the previous session, so the first chunk is
    silence or garbage.
-   [ ] The microphone device or sample rate changes between two rapid
    recordings, so segments have mismatched audio formats.
-   [ ] An accessibility tool, macro, gaming overlay, or stuck key
    generates hotkey presses the user did not intend.
-   [ ] The hotkey is pressed while the screen is locked, while an
    admin-permission prompt is open, or while the app is not allowed
    to listen globally.

### 2.6 Burst aftermath: ordering, delivery target, and side effects

These cases are about what happens after a burst was accepted,
while results come back.

-   [ ] Several burst recordings finish transcription out of order, so
    an earlier sentence appears after a later one.
-   [ ] The user switches windows while a backlog is being processed,
    and text is inserted into the wrong application.
-   [ ] Text insertion for one segment is still in progress
    (typing or pasting) when the next segment's result arrives.
-   [ ] The clipboard is in use by the user at the exact moment a
    result is pasted through clipboard restore.
-   [ ] Burst segments each create their own history entry, flooding
    history; or they are merged and the user cannot find one of them.
-   [ ] Undo removes the wrong segment's text because several
    insertions happened in quick succession.
-   [ ] Rapid cloud requests hit a provider rate limit, so some
    segments fail while others succeed.
-   [ ] A burst arrives while the device is on battery or thermally
    throttled, local inference slows down, and the backlog grows
    further because of it.
-   [ ] Temporary audio files take significant disk space during a long
    spam burst before cleanup runs.
-   [ ] Language auto-detection runs per segment and guesses different
    languages for pieces of one utterance.
-   [ ] The user alternates real short phrases with empty taps. The app
    must keep the phrases and drop the taps without mixing them up.

## 3. Cross-cutting state and race-condition cases

These cases can occur across both Escape cancellation and hotkey
handling.

-   [ ] Escape and the hotkey are pressed at nearly the same time.
-   [ ] A recording is stopped at the same moment that Escape is
    pressed.
-   [ ] A queued recording is cancelled at the same moment that the
    model becomes ready.
-   [ ] The user starts a new recording before the previous operation
    has fully cleaned up.
-   [ ] The user cancels an old operation while a new operation is
    starting.
-   [ ] A previous operation completes after a newer operation has
    become active.
-   [ ] An asynchronous callback updates the UI using stale state.
-   [ ] The recording state, queue state, model state, and UI state
    disagree.
-   [ ] The app believes recording has stopped while the microphone
    capture thread or process is still active.
-   [ ] The app believes a job was cancelled while it remains in a queue
    or continues to deliver a result.
-   [ ] An error occurs during cleanup after cancellation.
-   [ ] A retry starts a second copy of a job that was already cancelled
    or completed.
-   [ ] A modal closes while a background recording or transcription
    operation continues.
-   [ ] The app loses focus or the bubble is hidden while an operation
    is active.
-   [ ] The app shuts down while recording, cancelling, waiting for the
    model, or transcribing.
-   [ ] The app resumes after sleep or hibernation while audio capture
    or model loading was in progress.
-   [ ] The microphone device changes while recording or while a
    recording is waiting in the queue.
-   [ ] The selected model or provider changes while a job is queued or
    running.
-   [ ] A local model fails and the app attempts a fallback, while the
    user has already cancelled the operation.
-   [ ] Network loss occurs during cloud transcription, and the user
    presses Escape before a retry.
-   [ ] A late notification or toast appears for an operation that has
    already been cancelled.
-   [ ] A cancelled or rejected recording is added to history as if it
    were successfully transcribed.
-   [ ] The app inserts text into the target application after the user
    believes the operation was cancelled.
-   [ ] The user rapidly switches between recording, cancellation, and
    model changes, and the app remains in a recoverable state.

## 4. User feedback and interaction expectations

-   [ ] The user can tell whether the app is recording, waiting for the
    model, transcribing, post-processing, cancelled, or finished.
-   [ ] The app clearly indicates when Escape successfully discards a
    recording.
-   [ ] The app does not imply that Escape cancelled transcription if it
    only stopped UI waiting or discarded the eventual result.
-   [ ] The app gives understandable feedback when a recording is too
    short, empty, or rejected.
-   [ ] Feedback for an accidental empty recording does not create
    excessive toast notifications during hotkey spam.
-   [ ] The app makes it clear when a recording is queued because the
    model is still loading.
-   [ ] The app makes it clear when a new recording cannot start because
    another operation or resource limit prevents it.
-   [ ] The app does not show contradictory statuses, such as
    "Recording" and "Transcribing" for the same operation.
-   [ ] A cancelled operation does not leave stale progress indicators
    or enabled/disabled controls in the wrong state.
-   [ ] Keyboard behavior remains predictable when the user interacts
    with other windows or applications.
-   [ ] Error messages distinguish microphone failures, model-loading
    failures, transcription failures, and cancellation where useful.
-   [ ] Notifications and status indicators remain accurate when events
    happen rapidly.

## 5. Data integrity, privacy, and cleanup

-   [ ] Discarded audio is not sent to the transcription model later
    from a queue.
-   [ ] Discarded audio is not accidentally saved to history or retained
    in temporary storage longer than intended.
-   [ ] Empty or rejected recordings do not produce fabricated text in
    the target application.
-   [ ] Each valid recording is processed at most once unless an
    explicitly defined retry is taking place.
-   [ ] A retry does not duplicate final text insertion or history
    entries.
-   [ ] A cancelled job's late result cannot be mistaken for the result
    of a newer recording.
-   [ ] Temporary audio data is cleaned up after success, cancellation,
    rejection, and failure.
-   [ ] Cleanup for one recording does not delete the audio or state of
    another recording.
-   [ ] Queue limits prevent unbounded accumulation of audio, tasks, or
    temporary files.
-   [ ] Cloud requests that have already been sent are handled honestly:
    the app should not claim that remote processing was stopped unless
    that is actually supported.
-   [ ] Logs and diagnostics do not expose dictated content
    unnecessarily.
-   [ ] Restart and crash recovery do not silently resubmit discarded or
    stale recordings.

## 6. Suggested policy questions to resolve later

This list does not prescribe one implementation. It identifies decisions
that should be made explicitly.

1.  **What does Escape mean?** Does it cancel only active recording, or
    does it also cancel queued transcription, active transcription,
    post-processing, and final delivery?
2.  **What is the cancellation cutoff?** If a stage cannot be
    interrupted, should the app discard its eventual result, or should
    Escape be ignored after a defined point?
3.  **What happens while the modal or model is loading?** Should
    recording remain available, should it be blocked, or should it be
    allowed with a bounded queue?
4.  **What is the queue policy?** Should the app queue multiple
    recordings, keep only the latest, or permit only one pending
    recording?
5.  **How should repeated hotkey presses be interpreted?** Should they
    always toggle recording, be ignored while processing, or follow
    another clearly defined state machine?
6.  **How should empty audio be detected?** Which combination of minimum
    duration, audio energy, voice activity detection, and ASR output
    checks is appropriate without rejecting quiet or short legitimate
    speech?
7.  **What is the minimum acceptable recording duration?** The threshold
    must account for legitimate single words and short commands rather
    than assuming all short recordings are accidental.
8.  **What happens when a model is unavailable?** Should recordings
    wait, fail with clear feedback, or be discarded after a limit?
9.  **What happens when queue or resource limits are reached?** The app
    needs predictable behavior and clear feedback.
10. **How are operations identified?** Each recording and transcription
    job should be distinguishable so late results, retries, and
    cancellations cannot affect a newer operation.
11. **What should history contain?** Decide whether cancelled, empty,
    rejected, and failed recordings appear in history.
12. **How should local and cloud models behave consistently?** Account
    for differences in interruption support, request cost, latency,
    retries, and remote processing.
13. **What should the user see during each state?** Define the status
    and feedback for recording, queued, loading, transcribing,
    post-processing, cancellation, rejection, failure, and completion.
14. **What is the shutdown policy?** Decide what happens to active and
    queued recordings when the application closes, crashes, or resumes
    after sleep.
15. **What does holding Escape do versus tapping it?** Are key repeats
    safe, and what happens when Escape never reaches the app?
16. **What does the recording hotkey mean physically?** Toggle on tap,
    push-to-talk on hold, or both, and what is the debounce rule so a
    cooldown never eats a legitimate second recording?
17. **When burst results complete out of order, what order is
    delivered?** And where does text go if the user changed windows
    while the backlog was processing?
18. **What is kept versus deleted for burst spam?** Per-segment history
    entries, merged entries, or nothing, and which segment does undo
    apply to?

## 7. High-value scenarios for later manual testing

-   [ ] Start recording and press Escape immediately.
-   [ ] Start recording, speak a sentence, and press Escape before
    stopping.
-   [ ] Start recording, stop with the hotkey, then press Escape during
    each visible processing stage.
-   [ ] Start recording while the modal is loading, cancel it, and wait
    until loading completes.
-   [ ] Start and stop recording repeatedly while the model is loading.
-   [ ] Create multiple queued recordings, cancel some, and verify that
    only the intended recordings are processed.
-   [ ] Press the hotkey twice very quickly and verify that only the
    intended state transitions occur.
-   [ ] Record nothing for less than one second and verify that no
    hallucinated text is inserted.
-   [ ] Record only background noise and verify that it is not converted
    into fabricated text.
-   [ ] Dictate a legitimate single word or short command and verify
    that it is not rejected solely because it is short.
-   [ ] Record a quiet sentence and verify that silence detection does
    not reject it.
-   [ ] Cancel one operation and immediately start another; verify that
    the old result cannot appear in the new operation.
-   [ ] Switch models while audio is queued and verify that queue
    ownership and processing behavior are well defined.
-   [ ] Simulate a model-loading failure with queued recordings.
-   [ ] Simulate a transcription error, retry, and cancellation
    happening close together.
-   [ ] Close the application while audio is queued and verify that
    discarded or stale audio is not submitted after restart.
-   [ ] Verify that every accepted recording is processed at most once
    and every discarded recording is never delivered.
-   [ ] Hold Escape during recording, then hold Escape during
    transcription, and compare the two behaviors.
-   [ ] Press Escape while a cloud upload is in progress and verify the
    result is never delivered even if the provider finishes.
-   [ ] Hold the hotkey down instead of tapping and verify the behavior
    matches the documented hold rule.
-   [ ] Dictate two single words a few seconds apart and verify both
    survive (no debounce swallowing, no spam rejection).
-   [ ] Spam the hotkey ten times with silence and verify no
    hallucinated text appears anywhere.
-   [ ] Start a recording, switch windows mid-transcription, and verify
    where the text lands.
-   [ ] Unplug the microphone mid-recording, then press Escape, and
    verify the app returns to a clean idle state.
-   [ ] Start a recording while the device is still waking from sleep
    and verify the start of speech is not silently lost.
