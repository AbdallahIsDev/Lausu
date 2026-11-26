# Critical plugin notices

One named mechanism (`PluginSession._critical_notify`) emits exactly one OS
toast and one in-app toast for a failure whose cause the user cannot see, even
when the plugin `notify` preference is off or the browser window is hidden.
A per-cycle dedupe key prevents a tab-close and a bridge-disconnect from
emitting two notices for one failure.

In the category:
- browser/tab/profile closed during recording or at stop (`browser-not-open`,
  `browser-closed`), including a bridge disconnect in that window;
- page unresponsive at stop (`page-not-ready`, `bridge-timeout`) when the
  recorded audio cannot be saved;
- start gave up after the bounded Chrome relaunches;
- a recording that ended with lost text (`verdict=investigate`), once that
  path is distinguished from ordinary no-speech.

Not in the category (still obey `notify`): activation done, no-speech,
owner-initiated Esc cancel, bridge status transitions, routine start hints.
