# Cloud Transcription Setup

End-user + integrator guide for routing Lausu's ASR (and LLM
polishing) through a cloud provider instead of the default on-device
faster-whisper / Qwen / Parakeet engines. Covers supported providers,
API key format, network requirements, and per-OS quirks.

> **Threat model first.** All cloud ASR / LLM traffic is gated by the
> URL allowlist + HTTPS-enforcement policy in
> [`docs/adr/0017-cloud-url-allowlist-https.md`](adr/0017-cloud-url-allowlist-https.md)
> (RELIABILITY-004 / SEC-002 endpoint-swap / SEC-003 in-transit). Read
> that ADR before adding a new provider or a self-hosted endpoint —
> every hostname MUST be on the allowlist (or extended at runtime via
> `add_trusted_endpoint`) or the request is rejected before it leaves
> the process.

> **Batch only.** Every provider below is reached with a *finished* audio
> file. Some models only work inside a live streaming session — OpenAI's
> `gpt-live-transcribe` / `gpt-realtime-whisper`, Gemini's
> `gemini-3.5-transcribe-live`, Deepgram's Flux — and are therefore not in
> the catalogue. The evidence and the options for adding them are in
> [`cloud-asr-batch-vs-realtime.md`](cloud-asr-batch-vs-realtime.md).

## Supported providers

| Provider | ASR | LLM polish | Default hostname | Notes |
|----------|-----|------------|------------------|-------|
| OpenAI | ✅ Whisper-1, gpt-transcribe, and the GPT-4o transcribe tiers (audio/transcriptions) | ✅ GPT-4o-family chat | `api.openai.com` | Default cloud option. Both ASR + LLM use the same API key. Batch only — `gpt-live-transcribe` and `gpt-realtime-whisper` are Realtime-API models (WebSocket / WebRTC sessions) that `POST /v1/audio/transcriptions` does not serve, so they are deliberately not in the catalogue. |
| Groq | ✅ Whisper-large / Distil-whisper (audio/transcriptions) | ✅ Llama-family chat | `api.groq.com` | Lowest-latency cloud ASR (typically <300 ms for a short clip). |
| Deepgram | ✅ Nova-3 + Nova-2, pre-recorded (batch) | ❌ (use OpenAI / Anthropic for LLM polish) | `api.deepgram.com` | Nova-3 is the default; Nova-2 stays selectable for the languages Nova-3 does not cover yet. Batch only — Flux (the streaming voice-agent model) is deliberately not in the catalogue. |
| Google Gemini | ✅ Gemini 3.5 Transcribe (inline audio → `generateContent`) | ✅ Gemini chat | `generativelanguage.googleapis.com` | Same API key for both. The catalogue serves Google's dedicated `gemini-3.5-transcribe` model; the earlier entries were general-purpose Flash models borrowed as an ASR fallback. The ~15–20 s per message recorded for that Flash path has NOT been re-measured against the transcribe model. |
| Anthropic (Claude) | ❌ (no ASR endpoint) | ✅ Claude chat | `api.anthropic.com` | LLM polish only. Pair with a cloud speech recognition provider. |
| Self-hosted (vLLM, llama.cpp server, Whisper HTTP server, etc.) | ✅ (if the server speaks a supported cloud ASR wire format) | ✅ (same) | `localhost`, `127.0.0.1`, `::1` (loopback) or any host added via `add_trusted_endpoint` | HTTPS is NOT enforced on loopback; any non-loopback self-hosted host MUST be added via `add_trusted_endpoint` AND served over HTTPS. See the caveat under "Self-hosted endpoint quickstart". |

> Lausu does not implement provider-specific SDKs, each cloud
> path is a thin HTTP client. As long as the self-hosted endpoint
> speaks the same JSON wire format as one of the supported providers,
> the `CloudEngine` API will treat it as that provider (pass
> `provider="openai"` / `"groq"` / `"deepgram"` / `"gemini"` and point
> `api_url` at the self-hosted URL).

## API key format

| Provider | Env var / config key | Format | Where it's stored |
|----------|---------------------|--------|-------------------|
| OpenAI | `OPENAI_API_KEY` (env) or `cloud_api_key` (config) | `sk-` + 20+ of `[A-Za-z0-9_-]` (`sk-proj-…` matches too) | OS credential store, see [`docs/security/credential-store.md`](security/credential-store.md). Never written to disk in plaintext. |
| Groq | `GROQ_API_KEY` (env) or `cloud_api_key` (config) | `gsk_` + exactly 52 alphanumerics | Same. |
| Deepgram | `DEEPGRAM_API_KEY` (env) or `cloud_api_key` (config) | exactly 40 lowercase alphanumerics, no prefix | Same. |
| Anthropic | `ANTHROPIC_API_KEY` (env) or `llm_api_key` (config) | `sk-ant-...` (100+ ASCII chars) | Same. |
| Google Gemini | `GEMINI_API_KEY` (env) or `llm_api_key` (config) | `AIza` + 35 of `[A-Za-z0-9_-]` (39 chars total) | Same. |
| Self-hosted | `cloud_api_key` / `llm_api_key` (config) | Whatever the server expects (often a bearer token or empty for unauthenticated local servers) | Same: if the key is non-empty. |

The four cloud-ASR shapes above are **enforced in the renderer** before
the key is written: `isValidApiKeyFormat()` in
`client/src/renderer/src/lib/utils/models.ts` carries one regex per
provider, each copied from a published machine-readable detector rather
than invented (OpenAI from RegexVault's audited pattern; Groq from
`secretlint-rule-groq` / trufflehog `pkg/detectors/groq`; Deepgram from
trufflehog `pkg/detectors/deepgram`; Google from Microsoft Purview's
"Google API key" SIT). A value that cannot be a key for the selected
provider is refused with an in-app toast and never reaches the
credential store, the format is NOT re-printed under the input field
(that hint was removed on 2026-10-11), and the only authority on
whether a well-shaped key actually works is Test Connection.

The API key is redacted from all log lines by the `PIIRedactionFilter`
(SEC-009) and from IPC responses via the secret-redaction layer
(SEC-003). The renderer never sees the raw key, only the `cloud_provider`
+ `cloud_api_url` are exposed via `get_config`.

## Network requirements

- **HTTPS-only** (ADR-0017 SEC-003): every non-loopback host MUST be
  reached over `https://`. The URL allowlist enforces this at the HTTP
  client boundary, a `http://api.openai.com/...` URL is rejected with
  `host 'api.openai.com' is not in the trusted allowlist` even though
  the host is on the allowlist, because the scheme check fires first.
- **Loopback exception**: `localhost`, `127.0.0.1`, and `::1` are
  the only hosts where `http://` is permitted (for local development
  servers). Self-hosted endpoints on a LAN IP (e.g. `http://10.0.0.5`)
  are NOT exempt: serve them over HTTPS with a self-signed cert and
  add the hostname via `add_trusted_endpoint`.
- **DNS resolution**: the allowlist's host check resolves the hostname
  via `socket.getaddrinfo()` and rejects any hostname that resolves to
  a non-allowlist IP (defense against DNS rebinding, see the inline
  comment in `voice_typer/server/_secrets.py`).
- **Outbound ports**: 443 (HTTPS) for all cloud providers. Lausu
  does not need any inbound ports open for cloud transcription.
- **Proxy support**: Lausu honors the standard `HTTPS_PROXY` /
  `HTTP_PROXY` env vars. The proxy URL itself is NOT subject to the
  allowlist (it's a transport-layer concern, not an endpoint).
- **Connection timeout**: 30 s connect, 120 s read for ASR (audio
  uploads can be large); 30 s connect, 60 s read for LLM polish.
  Timeouts are configurable via `cloud_connect_timeout_seconds` /
  `cloud_read_timeout_seconds` in `Config`.

## Per-OS quirks

| OS | Quirk | Mitigation |
|----|-------|-----------|
| **Windows** | The system trust store is consulted for TLS verification (via `certifi` + `ssl.create_default_context()`). If a corporate MITM proxy replaces the root CA, TLS verification fails with `SSL: CERTIFICATE_VERIFY_FAILED`. | Set the `SSL_CERT_FILE` env var to the path of the corporate root CA bundle (a `.crt` / `.pem` file exported from the corporate IT portal). Restart Lausu. |
| **Windows** | Windows Firewall prompts on first cloud request if the bundled `pythonw.exe` (or the Nuitka-frozen sidecar exe under Tauri) has not yet been allowlisted. | Accept the prompt once (Private networks only, never Public). Lausu makes only outbound HTTPS connections; no inbound rule is needed. |
| **macOS** | Same TLS-verification path as Windows; the system Keychain root CAs are picked up automatically by `certifi`. | Same `SSL_CERT_FILE` workaround for corporate MITM proxies. |
| **macOS** | iCloud Private Relay can route DNS through Apple's relay, which sometimes causes intermittent `getaddrinfo` failures for non-Apple hostnames. | Disable Private Relay for the Lausu binary in System Settings → Apple ID → iCloud → Private Relay → "Exclude". This is a macOS-level setting; Lausu has no in-app toggle. |
| **Linux (X11 + Wayland)** | The trust store is rooted at `/etc/ssl/certs/ca-certificates.crt` (Debian/Ubuntu) or `/etc/pki/tls/certs/ca-bundle.crt` (Fedora/RHEL). `certifi` ships its own bundle and uses it in preference to the system bundle. | If a corporate root CA is installed in the system trust store but NOT in `certifi`'s bundle, set `SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt` (or the Fedora path) to force the system bundle. |
| **Linux (AppImage)** | The AppImage bundles its own `certifi` CA bundle; the host system's trust store is NOT consulted unless `SSL_CERT_FILE` is set explicitly. | Same `SSL_CERT_FILE` workaround as above. |
| **Linux (Tauri sidecar)** | The Nuitka-frozen sidecar exe does NOT consult the system trust store by default; it uses the `certifi` bundle baked in at freeze time. | If the `certifi` bundle is stale (a CA was added/rotated after the sidecar was built), update Lausu to a newer release, there is no in-app CA bundle refresh. |
| **All OSes (Tauri host)** | The Tauri v2 host does NOT proxy cloud requests through Rust. All cloud ASR / LLM HTTP traffic is initiated by the Python backend (same as the retired predecessor host). The Rust host's `tauri-plugin-http` / `tauri-plugin-reqwest` is NOT used for cloud transcription. | No action needed: this is by design (the allowlist + redaction live in the Python layer). |

## Verifying connectivity

Lausu ships an IPC command specifically for testing cloud
connectivity without recording audio:

```
dispatch({type: "test_cloud_connection", data: {provider: "openai"}})
```

The handler (`voice_typer/server/handlers/cloud_test_handlers.py`) opens
a short-lived HTTPS connection to the configured `cloud_api_url` (or
the provider's default hostname if no URL is set), sends a trivial
`GET /v1/models` (or equivalent) request with the configured API key,
and reports the HTTP status code + round-trip latency back to the
renderer. This is exposed on the Models page's Cloud tab as the "Test
Connection" button inside each provider's setup dialog.

The handler returns a short stable token (`auth_failed`,
`rate_limited`, `server_error`, `http_error`, `network_error`,
`no_api_key`) rather than a sentence. The renderer maps that token to
localized copy via `connectionFailureKey()` and shows the result as an
**in-app toast**, never as inline text next to the button: the token
itself ("400 http_error") communicates nothing, and a transient probe
outcome is not a property of the form. Saving a key for a provider whose
audio-transmission consent is not yet granted raises the shared
point-of-use consent dialog (the same modal every other consent-gated
flow uses) once the key is stored.

The `test_cloud_connection` command is rate-limited to 10 calls per
minute (per-connection ADR-0019 rate limiter) to prevent abuse.

## Activating a provider's model

Configuring a provider and *using* it are two separate steps, and the
Models page's Cloud tab exposes them separately:

1. **Configure** sits on the provider's own header row (provider name on
   the left, the button on the right) and opens the provider-level setup
   dialog: one API key field for the whole provider. A provider's models
   all share one key, so the form is never repeated per model. Saving the
   key raises the shared point-of-use consent dialog the first time (see
   `docs/adr/` consent gate notes and `lib/consentGate.ts`).
2. **Select** sits on each model row inside the group. Activating writes
   three config fields together:

   | Field | Value | Why |
   |-------|-------|-----|
   | `asr_backend` | `"cloud"` | The backend selector. There is exactly ONE of these, which is what makes "one active model at a time" hold across the Local and Cloud tabs: activating a cloud model deactivates whichever local model was active, and selecting a local model writes `"whisper"` / `"qwen"` / `"parakeet"` back. |
   | `cloud_provider` | the provider key | Which provider the `cloud` backend talks to. `""` = none, and the backend then reports itself not-loaded so the registry degrades to whisper. |
   | `cloud_model` | the model id | Always written explicitly. The backend falls back to its per-provider default only when this is empty, and the Cloud tab marks that same default as the active row. |

The backend resolves all of this on every `load()` / `transcribe()`
(`CloudAsrBackend` in `voice_typer/server/cloud_backend.py`), so a key
saved in Settings works without restarting the sidecar. Activating a
model for a provider with no stored key is refused up front with a toast
rather than silently falling back to whisper.

### The onboarding wizard writes the same fields

The wizard's Model step has no Save button of its own, and its
`onboarding_set_model` / `onboarding_set_backend` commands only feed the
wizard's controller — `apply_settings` persists the hotkey, microphone and
`model_size` and nothing else. So the step also issues one `set_config`
when the user leaves it, writing exactly what the Cloud tab writes:

* **Cloud branch** — the same three fields above, with `cloud_model` set to
  the provider's catalogue default (`cloudDefaultModel()` in
  `lib/utils/models.ts`), plus the provider's API-key field when one was
  typed. The provider's audio-transmission consent is requested through the
  shared consent gate at that moment rather than through a checkbox on the
  step, so the user reads what the choice authorises as it takes effect;
  the wizard refuses to advance until the gate is allowed.
* **Local branch** — `asr_backend` (from the entry's own registry
  `backend`, so a Parakeet or Qwen choice no longer leaves the backend
  pointing at Whisper) plus `model_size`.

Without this the wizard's Model step was decorative: a cloud choice left
`asr_backend` at its `"whisper"` default, so dictation kept running locally
with no key involved.

## Self-hosted endpoint quickstart

1. Stand up your self-hosted endpoint (e.g. `vllm serve --model
   whisper-large-v3`, or `llama.cpp server --model qwen2.5-72b`).
   Make sure it speaks a supported cloud ASR provider wire format.
2. Serve it over HTTPS. For a LAN-only deployment, use a self-signed
   cert (e.g. `caddy` / `nginx` with a self-signed CA). Loopback
   (`http://localhost:port`) is exempt from HTTPS but anything on a
   LAN IP is not.
3. Add the hostname to the allowlist at runtime:

   ```
   dispatch({type: "add_trusted_endpoint", data: {host: "asr.lan.example.com"}})
   ```

   The host is added to the per-process URL allowlist (`extend_url_allowlist`
   under the hood). The extension is process-global and applies to all
   HTTP clients in the process; it is NOT persisted across restarts —
   add it from a startup hook or your config wizard if you need it
   permanent.
4. In Settings → Models → Cloud, set:
   - `cloud_provider` = `openai` (or whichever wire format your server
     speaks)
   - `cloud_api_url` = `https://asr.lan.example.com/v1`
   - `cloud_api_key` = the bearer token your server expects (or empty
     for unauthenticated loopback servers)

   > **Caveat (SEC-011).** The registry-backed `cloud` backend — the one
   > the Cloud tab's Select action activates — resolves the endpoint from
   > the provider's own default (`_PROVIDER_DEFAULTS`) and **deliberately
   > ignores `cloud_api_url`**. A stored key must never be posted to a
   > caller-chosen host, so a config-level URL cannot redirect it. Driving
   > a self-hosted endpoint therefore means constructing a `CloudEngine`
   > through the API with an explicit `api_url`
   > (`voice_typer/server/cloud/_engine.py`), not pointing the Cloud tab
   > at it. The fields above remain the integrator-facing config surface.
5. Click "Test connection": you should get a 200 + a latency reading.
   If you get `host 'asr.lan.example.com' is not in the trusted
   allowlist`, the `add_trusted_endpoint` call didn't land (check the
   IPC response envelope for an error).

## See also

- [`docs/adr/0017-cloud-url-allowlist-https.md`](adr/0017-cloud-url-allowlist-https.md) —
  the URL allowlist + HTTPS-enforcement ADR (RELIABILITY-004).
- [`docs/security/credential-store.md`](security/credential-store.md) —
  how API keys are stored per-OS (Keychain / Credential Manager /
  Secret Service).
- [`docs/privacy/encryption-at-rest.md`](privacy/encryption-at-rest.md) —
  what user data (including audio clips + transcriptions) is encrypted
  at rest and how.
- [`docs/ipc-reference.md`](ipc-reference.md), the `test_cloud_connection`
  + `add_trusted_endpoint` IPC command rows.
- [`docs/python-api.md`](python-api.md), the `Config` dataclass fields
  (`cloud_provider`, `cloud_api_url`, `cloud_api_key`, etc.).
