# Shell navigation audit

Date: 2026-11-24

## Current structure

- The sidebar has two groups: everyday destinations and a bottom-pinned System group.
- Settings is a hub with ten sections, including Bubble Overview, Dictionary & Snippets, and About & Privacy. Each row opens its own Settings section page.
- Bubble Overview reuses the existing `settingsOverlay` route and bubble config controls; no new config fields or duplicate bubble surface are introduced.
- Dictionary & Snippets owns the existing `templates_enabled` and `vocabulary_automation_enabled` controls and links to the Templates and Vocabulary collection pages. Their persisted config keys and backend behavior are unchanged.
- About & Privacy's product identity and privacy disclosures remain intact. Consent controls remain in Settings → Privacy; the About page explains data handling but does not own consent toggles.
- The former `aboutAndPrivacy` route remains registered for existing deep links and compatibility. It is no longer a separate sidebar destination; Settings navigation uses `settingsAboutPrivacy`.
- Bubble components and the Settings preview are now discoverable through the Bubble Overview section; no parallel bubble window or renderer is introduced.
- Plugins remains developer-gated in the sidebar, renderer routes, and server inventory. The Models integration must retain the same gate and server authority.

## Navigation change

About & Privacy was moved from the System sidebar group into the Settings hub after the owner explicitly chose that placement. The Settings section registry, search labels, Settings route rendering, and sidebar/a11y tests follow the new placement. The legacy route and consent-to-`settingsPrivacy` behavior are preserved.

## Validation

See the 2026-11-24 implementation entry in `worklog.md` for the focused renderer tests, formatting, typecheck, and diff checks.
