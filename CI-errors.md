# CI Errors

> Generated: 2026-11-26T16:57:57Z
> Data branch commit: `58e973c`

## Currently failing

### 1. Build Linux — failure

- Run: [45858393735](https://github.com/AbdallahIsDev/Lausu/actions/runs/45858393735) (attempt 1)
- Event: push · Branch: main
- Commit: `f989c88` — test(client): pin worker-backed ASR hidden imports in the spec
- Job: smoke-cargo-check · Leg: ubuntu-22.04
- Step: cargo fmt --check (Tauri Rust host formatting gate)
- Category: gate

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 2. Client CI — failure

- Run: [45858393511](https://github.com/AbdallahIsDev/Lausu/actions/runs/45858393511) (attempt 1)
- Event: push · Branch: main
- Commit: `f989c88` — test(client): pin worker-backed ASR hidden imports in the spec
- Job: Typecheck + Lint + Test · Leg: ubuntu-22.04
- Step: Test (Vitest + coverage)
- Category: eslint/vitest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 3. Client CI — failure

- Run: [45858393511](https://github.com/AbdallahIsDev/Lausu/actions/runs/45858393511) (attempt 1)
- Event: push · Branch: main
- Commit: `f989c88` — test(client): pin worker-backed ASR hidden imports in the spec
- Job: Security audit · Leg: n/a
- Step: (job-level failure)
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 4. Client CI — failure

- Run: [45858393511](https://github.com/AbdallahIsDev/Lausu/actions/runs/45858393511) (attempt 1)
- Event: push · Branch: main
- Commit: `f989c88` — test(client): pin worker-backed ASR hidden imports in the spec
- Job: Test results · Leg: n/a
- Step: (job-level failure)
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 5. Build installer — failure

- Run: [45848520451](https://github.com/AbdallahIsDev/Lausu/actions/runs/45848520451) (attempt 1)
- Event: push · Branch: main
- Commit: `d70a14e` — docs(plugins): record live evidence and honest edge-case statuses
- Job: Rust clippy + cargo audit · Leg: ubuntu-22.04
- Step: Run rustsec/audit-check@v2
- Category: cargo test/clippy/audit

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 6. Build installer — failure

- Run: [45848520451](https://github.com/AbdallahIsDev/Lausu/actions/runs/45848520451) (attempt 1)
- Event: push · Branch: main
- Commit: `d70a14e` — docs(plugins): record live evidence and honest edge-case statuses
- Job: slow-tests · Leg: ubuntu-22.04
- Step: Run slow manual-script wrappers
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 7. Build installer — failure

- Run: [45848520451](https://github.com/AbdallahIsDev/Lausu/actions/runs/45848520451) (attempt 1)
- Event: push · Branch: main
- Commit: `d70a14e` — docs(plugins): record live evidence and honest edge-case statuses
- Job: test (windows-2022, 3.13) · Leg: windows-2022, 3.13
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 8. Build installer — failure

- Run: [45848520451](https://github.com/AbdallahIsDev/Lausu/actions/runs/45848520451) (attempt 1)
- Event: push · Branch: main
- Commit: `d70a14e` — docs(plugins): record live evidence and honest edge-case statuses
- Job: test (windows-2022, 3.12) · Leg: windows-2022, 3.12
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 9. Build installer — failure

- Run: [45848520451](https://github.com/AbdallahIsDev/Lausu/actions/runs/45848520451) (attempt 1)
- Event: push · Branch: main
- Commit: `d70a14e` — docs(plugins): record live evidence and honest edge-case statuses
- Job: test (windows-2022, 3.11) · Leg: windows-2022, 3.11
- Step: Run tests with coverage
- Category: infrastructure/cancelled/timeout

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 10. Build installer — failure

- Run: [45848520451](https://github.com/AbdallahIsDev/Lausu/actions/runs/45848520451) (attempt 1)
- Event: push · Branch: main
- Commit: `d70a14e` — docs(plugins): record live evidence and honest edge-case statuses
- Job: test (ubuntu-22.04, 3.12) · Leg: ubuntu-22.04, 3.12
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 11. Build installer — failure

- Run: [45848520451](https://github.com/AbdallahIsDev/Lausu/actions/runs/45848520451) (attempt 1)
- Event: push · Branch: main
- Commit: `d70a14e` — docs(plugins): record live evidence and honest edge-case statuses
- Job: test (macos-15, 3.13) · Leg: macos-15, 3.13
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 12. Build installer — failure

- Run: [45848520451](https://github.com/AbdallahIsDev/Lausu/actions/runs/45848520451) (attempt 1)
- Event: push · Branch: main
- Commit: `d70a14e` — docs(plugins): record live evidence and honest edge-case statuses
- Job: test (ubuntu-22.04, 3.13) · Leg: ubuntu-22.04, 3.13
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

## Recent failures

### 1. CI error collector — failure

- Run: [45861147074](https://github.com/AbdallahIsDev/Lausu/actions/runs/45861147074) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `f989c88` — test(client): pin worker-backed ASR hidden imports in the spec
- Job: Collect CI failures into ci-reports · Leg: ubuntu-22.04
- Step: Generate report from main sources
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 2. CI error collector — failure

- Run: [45860910924](https://github.com/AbdallahIsDev/Lausu/actions/runs/45860910924) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `f989c88` — test(client): pin worker-backed ASR hidden imports in the spec
- Job: Collect CI failures into ci-reports · Leg: ubuntu-22.04
- Step: Generate report from main sources
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 3. CI error collector — failure

- Run: [45859088557](https://github.com/AbdallahIsDev/Lausu/actions/runs/45859088557) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `f989c88` — test(client): pin worker-backed ASR hidden imports in the spec
- Job: Collect CI failures into ci-reports · Leg: ubuntu-22.04
- Step: Generate report from main sources
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 4. Build Linux — failure

- Run: [45858393735](https://github.com/AbdallahIsDev/Lausu/actions/runs/45858393735) (attempt 1)
- Event: push · Branch: main
- Commit: `f989c88` — test(client): pin worker-backed ASR hidden imports in the spec
- Job: smoke-cargo-check · Leg: ubuntu-22.04
- Step: cargo fmt --check (Tauri Rust host formatting gate)
- Category: gate

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 5. Client CI — failure

- Run: [45858393511](https://github.com/AbdallahIsDev/Lausu/actions/runs/45858393511) (attempt 1)
- Event: push · Branch: main
- Commit: `f989c88` — test(client): pin worker-backed ASR hidden imports in the spec
- Job: Typecheck + Lint + Test · Leg: ubuntu-22.04
- Step: Test (Vitest + coverage)
- Category: eslint/vitest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 6. Client CI — failure

- Run: [45858393511](https://github.com/AbdallahIsDev/Lausu/actions/runs/45858393511) (attempt 1)
- Event: push · Branch: main
- Commit: `f989c88` — test(client): pin worker-backed ASR hidden imports in the spec
- Job: Security audit · Leg: n/a
- Step: (job-level failure)
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 7. Client CI — failure

- Run: [45858393511](https://github.com/AbdallahIsDev/Lausu/actions/runs/45858393511) (attempt 1)
- Event: push · Branch: main
- Commit: `f989c88` — test(client): pin worker-backed ASR hidden imports in the spec
- Job: Test results · Leg: n/a
- Step: (job-level failure)
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 8. CI error collector — failure

- Run: [45858329686](https://github.com/AbdallahIsDev/Lausu/actions/runs/45858329686) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `d70a14e` — docs(plugins): record live evidence and honest edge-case statuses
- Job: Collect CI failures into ci-reports · Leg: ubuntu-22.04
- Step: Generate report from main sources
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 9. Build Linux — failure

- Run: [45848520453](https://github.com/AbdallahIsDev/Lausu/actions/runs/45848520453) (attempt 1)
- Event: push · Branch: main
- Commit: `d70a14e` — docs(plugins): record live evidence and honest edge-case statuses
- Job: smoke-cargo-check · Leg: ubuntu-22.04
- Step: cargo test (Tauri Rust host unit tests)
- Category: cargo test/clippy/audit

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 10. Build Linux — failure

- Run: [45848520453](https://github.com/AbdallahIsDev/Lausu/actions/runs/45848520453) (attempt 1)
- Event: push · Branch: main
- Commit: `d70a14e` — docs(plugins): record live evidence and honest edge-case statuses
- Job: Security audit · Leg: n/a
- Step: (job-level failure)
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 11. Build installer — failure

- Run: [45848520451](https://github.com/AbdallahIsDev/Lausu/actions/runs/45848520451) (attempt 1)
- Event: push · Branch: main
- Commit: `d70a14e` — docs(plugins): record live evidence and honest edge-case statuses
- Job: Rust clippy + cargo audit · Leg: ubuntu-22.04
- Step: Run rustsec/audit-check@v2
- Category: cargo test/clippy/audit

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 12. Build installer — failure

- Run: [45848520451](https://github.com/AbdallahIsDev/Lausu/actions/runs/45848520451) (attempt 1)
- Event: push · Branch: main
- Commit: `d70a14e` — docs(plugins): record live evidence and honest edge-case statuses
- Job: slow-tests · Leg: ubuntu-22.04
- Step: Run slow manual-script wrappers
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 13. Build installer — failure

- Run: [45848520451](https://github.com/AbdallahIsDev/Lausu/actions/runs/45848520451) (attempt 1)
- Event: push · Branch: main
- Commit: `d70a14e` — docs(plugins): record live evidence and honest edge-case statuses
- Job: test (windows-2022, 3.13) · Leg: windows-2022, 3.13
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 14. Build installer — failure

- Run: [45848520451](https://github.com/AbdallahIsDev/Lausu/actions/runs/45848520451) (attempt 1)
- Event: push · Branch: main
- Commit: `d70a14e` — docs(plugins): record live evidence and honest edge-case statuses
- Job: test (windows-2022, 3.12) · Leg: windows-2022, 3.12
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 15. Build installer — failure

- Run: [45848520451](https://github.com/AbdallahIsDev/Lausu/actions/runs/45848520451) (attempt 1)
- Event: push · Branch: main
- Commit: `d70a14e` — docs(plugins): record live evidence and honest edge-case statuses
- Job: test (windows-2022, 3.11) · Leg: windows-2022, 3.11
- Step: Run tests with coverage
- Category: infrastructure/cancelled/timeout

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 16. Build installer — failure

- Run: [45848520451](https://github.com/AbdallahIsDev/Lausu/actions/runs/45848520451) (attempt 1)
- Event: push · Branch: main
- Commit: `d70a14e` — docs(plugins): record live evidence and honest edge-case statuses
- Job: test (ubuntu-22.04, 3.12) · Leg: ubuntu-22.04, 3.12
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 17. Build installer — failure

- Run: [45848520451](https://github.com/AbdallahIsDev/Lausu/actions/runs/45848520451) (attempt 1)
- Event: push · Branch: main
- Commit: `d70a14e` — docs(plugins): record live evidence and honest edge-case statuses
- Job: test (macos-15, 3.13) · Leg: macos-15, 3.13
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 18. Build installer — failure

- Run: [45848520451](https://github.com/AbdallahIsDev/Lausu/actions/runs/45848520451) (attempt 1)
- Event: push · Branch: main
- Commit: `d70a14e` — docs(plugins): record live evidence and honest edge-case statuses
- Job: test (ubuntu-22.04, 3.13) · Leg: ubuntu-22.04, 3.13
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 19. Build installer — failure

- Run: [45741472226](https://github.com/AbdallahIsDev/Lausu/actions/runs/45741472226) (attempt 1)
- Event: push · Branch: main
- Commit: `fd574b0` — docs(plugins): reclassify edge cases with live evidence
- Job: slow-tests · Leg: ubuntu-22.04
- Step: Run slow manual-script wrappers
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 20. Build installer — failure

- Run: [45741472226](https://github.com/AbdallahIsDev/Lausu/actions/runs/45741472226) (attempt 1)
- Event: push · Branch: main
- Commit: `fd574b0` — docs(plugins): reclassify edge cases with live evidence
- Job: test (ubuntu-22.04, 3.11) · Leg: ubuntu-22.04, 3.11
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 21. Build installer — failure

- Run: [45741472226](https://github.com/AbdallahIsDev/Lausu/actions/runs/45741472226) (attempt 1)
- Event: push · Branch: main
- Commit: `fd574b0` — docs(plugins): reclassify edge cases with live evidence
- Job: test (ubuntu-22.04, 3.13) · Leg: ubuntu-22.04, 3.13
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 22. Build installer — failure

- Run: [45741472226](https://github.com/AbdallahIsDev/Lausu/actions/runs/45741472226) (attempt 1)
- Event: push · Branch: main
- Commit: `fd574b0` — docs(plugins): reclassify edge cases with live evidence
- Job: test (macos-15, 3.13) · Leg: macos-15, 3.13
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 23. Build installer — failure

- Run: [45741472226](https://github.com/AbdallahIsDev/Lausu/actions/runs/45741472226) (attempt 1)
- Event: push · Branch: main
- Commit: `fd574b0` — docs(plugins): reclassify edge cases with live evidence
- Job: test (macos-15, 3.12) · Leg: macos-15, 3.12
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 24. Build installer — failure

- Run: [45741472226](https://github.com/AbdallahIsDev/Lausu/actions/runs/45741472226) (attempt 1)
- Event: push · Branch: main
- Commit: `fd574b0` — docs(plugins): reclassify edge cases with live evidence
- Job: test (macos-15, 3.11) · Leg: macos-15, 3.11
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 25. Build installer — failure

- Run: [45741472226](https://github.com/AbdallahIsDev/Lausu/actions/runs/45741472226) (attempt 1)
- Event: push · Branch: main
- Commit: `fd574b0` — docs(plugins): reclassify edge cases with live evidence
- Job: test (ubuntu-22.04, 3.12) · Leg: ubuntu-22.04, 3.12
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 26. Build installer — failure

- Run: [45741472226](https://github.com/AbdallahIsDev/Lausu/actions/runs/45741472226) (attempt 1)
- Event: push · Branch: main
- Commit: `fd574b0` — docs(plugins): reclassify edge cases with live evidence
- Job: test (windows-2022, 3.12) · Leg: windows-2022, 3.12
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 27. Build Linux — failure

- Run: [45730000324](https://github.com/AbdallahIsDev/Lausu/actions/runs/45730000324) (attempt 1)
- Event: push · Branch: main
- Commit: `94b4311` — fix(permissions): dev-only tabs permission and staged-bundle pins
- Job: smoke-cargo-check · Leg: ubuntu-22.04
- Step: cargo test (Tauri Rust host unit tests)
- Category: cargo test/clippy/audit

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 28. Build installer — failure

- Run: [45730000314](https://github.com/AbdallahIsDev/Lausu/actions/runs/45730000314) (attempt 1)
- Event: push · Branch: main
- Commit: `94b4311` — fix(permissions): dev-only tabs permission and staged-bundle pins
- Job: test (macos-15, 3.12) · Leg: macos-15, 3.12
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 29. Build installer — failure

- Run: [45730000314](https://github.com/AbdallahIsDev/Lausu/actions/runs/45730000314) (attempt 1)
- Event: push · Branch: main
- Commit: `94b4311` — fix(permissions): dev-only tabs permission and staged-bundle pins
- Job: test (macos-15, 3.11) · Leg: macos-15, 3.11
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 30. Build installer — failure

- Run: [45730000314](https://github.com/AbdallahIsDev/Lausu/actions/runs/45730000314) (attempt 1)
- Event: push · Branch: main
- Commit: `94b4311` — fix(permissions): dev-only tabs permission and staged-bundle pins
- Job: Rust clippy + cargo audit · Leg: ubuntu-22.04
- Step: Run rustsec/audit-check@v2
- Category: cargo test/clippy/audit

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 31. Build installer — failure

- Run: [45730000314](https://github.com/AbdallahIsDev/Lausu/actions/runs/45730000314) (attempt 1)
- Event: push · Branch: main
- Commit: `94b4311` — fix(permissions): dev-only tabs permission and staged-bundle pins
- Job: slow-tests · Leg: ubuntu-22.04
- Step: Run slow manual-script wrappers
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 32. Build installer — failure

- Run: [45730000314](https://github.com/AbdallahIsDev/Lausu/actions/runs/45730000314) (attempt 1)
- Event: push · Branch: main
- Commit: `94b4311` — fix(permissions): dev-only tabs permission and staged-bundle pins
- Job: test (windows-2022, 3.13) · Leg: windows-2022, 3.13
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 33. Build installer — failure

- Run: [45730000314](https://github.com/AbdallahIsDev/Lausu/actions/runs/45730000314) (attempt 1)
- Event: push · Branch: main
- Commit: `94b4311` — fix(permissions): dev-only tabs permission and staged-bundle pins
- Job: test (ubuntu-22.04, 3.12) · Leg: ubuntu-22.04, 3.12
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 34. Build installer — failure

- Run: [45730000314](https://github.com/AbdallahIsDev/Lausu/actions/runs/45730000314) (attempt 1)
- Event: push · Branch: main
- Commit: `94b4311` — fix(permissions): dev-only tabs permission and staged-bundle pins
- Job: test (macos-15, 3.13) · Leg: macos-15, 3.13
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 35. Build installer — failure

- Run: [45730000314](https://github.com/AbdallahIsDev/Lausu/actions/runs/45730000314) (attempt 1)
- Event: push · Branch: main
- Commit: `94b4311` — fix(permissions): dev-only tabs permission and staged-bundle pins
- Job: test (ubuntu-22.04, 3.13) · Leg: ubuntu-22.04, 3.13
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 36. Build installer — failure

- Run: [45720592081](https://github.com/AbdallahIsDev/Lausu/actions/runs/45720592081) (attempt 1)
- Event: push · Branch: main
- Commit: `86a656d` — docs(plugins): record live tab, timing, RAM evidence and decision
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 37. Build Linux — failure

- Run: [45720177190](https://github.com/AbdallahIsDev/Lausu/actions/runs/45720177190) (attempt 1)
- Event: push · Branch: main
- Commit: `ee9ec66` — fix(diagnostics): workspace marker gate, tab URLs and per-request platform
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 38. Build installer — failure

- Run: [45720177056](https://github.com/AbdallahIsDev/Lausu/actions/runs/45720177056) (attempt 1)
- Event: push · Branch: main
- Commit: `ee9ec66` — fix(diagnostics): workspace marker gate, tab URLs and per-request platform
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 39. Build installer — failure

- Run: [45695399373](https://github.com/AbdallahIsDev/Lausu/actions/runs/45695399373) (attempt 1)
- Event: push · Branch: main
- Commit: `e1c3bbe` — fix(plugins): fast activation, pending-url tab reuse, quiet logs and one active engine
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 40. Build Linux — failure

- Run: [45695399355](https://github.com/AbdallahIsDev/Lausu/actions/runs/45695399355) (attempt 1)
- Event: push · Branch: main
- Commit: `e1c3bbe` — fix(plugins): fast activation, pending-url tab reuse, quiet logs and one active engine
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 41. Build Linux — failure

- Run: [45681015836](https://github.com/AbdallahIsDev/Lausu/actions/runs/45681015836) (attempt 1)
- Event: push · Branch: main
- Commit: `0616c77` — fix(plugins): ready platform at activation, single-flight launch, and readiness gate
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 42. Build installer — failure

- Run: [45681015474](https://github.com/AbdallahIsDev/Lausu/actions/runs/45681015474) (attempt 1)
- Event: push · Branch: main
- Commit: `0616c77` — fix(plugins): ready platform at activation, single-flight launch, and readiness gate
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 43. CI error collector — failure

- Run: [45520898834](https://github.com/AbdallahIsDev/Lausu/actions/runs/45520898834) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `0c7989d` — feat: shell cleanup, Models tabs, translation optimizations, GPUI prototype and onboarding UX
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 44. Build installer — failure

- Run: [45512898129](https://github.com/AbdallahIsDev/Lausu/actions/runs/45512898129) (attempt 1)
- Event: push · Branch: main
- Commit: `0c7989d` — feat: shell cleanup, Models tabs, translation optimizations, GPUI prototype and onboarding UX
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 45. Build Linux — failure

- Run: [45512898056](https://github.com/AbdallahIsDev/Lausu/actions/runs/45512898056) (attempt 1)
- Event: push · Branch: main
- Commit: `0c7989d` — feat: shell cleanup, Models tabs, translation optimizations, GPUI prototype and onboarding UX
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 46. Build installer — failure

- Run: [45459252772](https://github.com/AbdallahIsDev/Lausu/actions/runs/45459252772) (attempt 1)
- Event: push · Branch: main
- Commit: `63823a1` — style(gates): format the seven touched Python files for ruff-format
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 47. CI error collector — failure

- Run: [45455690803](https://github.com/AbdallahIsDev/Lausu/actions/runs/45455690803) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `97f834c` — fix(ui): finish removing red error surfaces and retarget moved source pins
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 48. Build installer — failure

- Run: [45454671351](https://github.com/AbdallahIsDev/Lausu/actions/runs/45454671351) (attempt 1)
- Event: push · Branch: main
- Commit: `97f834c` — fix(ui): finish removing red error surfaces and retarget moved source pins
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 49. Build installer — failure

- Run: [45410434581](https://github.com/AbdallahIsDev/Lausu/actions/runs/45410434581) (attempt 1)
- Event: push · Branch: main
- Commit: `2f91e2a` — fix(logs): keep expected GGUF cache misses to one DEBUG line
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 50. Client CI — failure

- Run: [45410434401](https://github.com/AbdallahIsDev/Lausu/actions/runs/45410434401) (attempt 1)
- Event: push · Branch: main
- Commit: `2f91e2a` — fix(logs): keep expected GGUF cache misses to one DEBUG line
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 51. Client CI — failure

- Run: [45409359243](https://github.com/AbdallahIsDev/Lausu/actions/runs/45409359243) (attempt 1)
- Event: push · Branch: main
- Commit: `ea6621b` — fix(build): generate the transcribe.cpp resource stub so Tauri resolves clean checkouts
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 52. Build installer — failure

- Run: [45409359123](https://github.com/AbdallahIsDev/Lausu/actions/runs/45409359123) (attempt 1)
- Event: push · Branch: main
- Commit: `ea6621b` — fix(build): generate the transcribe.cpp resource stub so Tauri resolves clean checkouts
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 53. Client CI — failure

- Run: [45401202326](https://github.com/AbdallahIsDev/Lausu/actions/runs/45401202326) (attempt 1)
- Event: push · Branch: main
- Commit: `5de856b` — docs: drop the last in-scope legacy ASR wording in manual README
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 54. Build installer — failure

- Run: [45401202297](https://github.com/AbdallahIsDev/Lausu/actions/runs/45401202297) (attempt 1)
- Event: push · Branch: main
- Commit: `5de856b` — docs: drop the last in-scope legacy ASR wording in manual README
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 55. Build Linux — failure

- Run: [45399711547](https://github.com/AbdallahIsDev/Lausu/actions/runs/45399711547) (attempt 1)
- Event: push · Branch: main
- Commit: `9117bf8` — docs: record phase 1 final verified state and owner checklist
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 56. CodeQL — failure

- Run: [45399711542](https://github.com/AbdallahIsDev/Lausu/actions/runs/45399711542) (attempt 1)
- Event: push · Branch: main
- Commit: `9117bf8` — docs: record phase 1 final verified state and owner checklist
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 57. Client CI — failure

- Run: [45399711163](https://github.com/AbdallahIsDev/Lausu/actions/runs/45399711163) (attempt 1)
- Event: push · Branch: main
- Commit: `9117bf8` — docs: record phase 1 final verified state and owner checklist
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 58. Build installer — failure

- Run: [45399711111](https://github.com/AbdallahIsDev/Lausu/actions/runs/45399711111) (attempt 1)
- Event: push · Branch: main
- Commit: `9117bf8` — docs: record phase 1 final verified state and owner checklist
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 59. CI error collector — failure

- Run: [45307909855](https://github.com/AbdallahIsDev/Lausu/actions/runs/45307909855) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `32d433d` — style: keep timeout constant import at module top
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 60. CodeQL — failure

- Run: [45306954147](https://github.com/AbdallahIsDev/Lausu/actions/runs/45306954147) (attempt 1)
- Event: push · Branch: main
- Commit: `32d433d` — style: keep timeout constant import at module top
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 61. Build installer — failure

- Run: [45306954077](https://github.com/AbdallahIsDev/Lausu/actions/runs/45306954077) (attempt 1)
- Event: push · Branch: main
- Commit: `32d433d` — style: keep timeout constant import at module top
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 62. Client CI — failure

- Run: [45306954019](https://github.com/AbdallahIsDev/Lausu/actions/runs/45306954019) (attempt 1)
- Event: push · Branch: main
- Commit: `32d433d` — style: keep timeout constant import at module top
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 63. Client CI — failure

- Run: [45305611455](https://github.com/AbdallahIsDev/Lausu/actions/runs/45305611455) (attempt 1)
- Event: push · Branch: main
- Commit: `f977190` — fix(asr): close dev-only leaks, route downloads to GGUF, drop in-process ASR fallbacks
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 64. Build Linux — failure

- Run: [45305611432](https://github.com/AbdallahIsDev/Lausu/actions/runs/45305611432) (attempt 1)
- Event: push · Branch: main
- Commit: `f977190` — fix(asr): close dev-only leaks, route downloads to GGUF, drop in-process ASR fallbacks
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 65. Build installer — failure

- Run: [45305611407](https://github.com/AbdallahIsDev/Lausu/actions/runs/45305611407) (attempt 1)
- Event: push · Branch: main
- Commit: `f977190` — fix(asr): close dev-only leaks, route downloads to GGUF, drop in-process ASR fallbacks
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 66. CodeQL — failure

- Run: [45305611366](https://github.com/AbdallahIsDev/Lausu/actions/runs/45305611366) (attempt 1)
- Event: push · Branch: main
- Commit: `f977190` — fix(asr): close dev-only leaks, route downloads to GGUF, drop in-process ASR fallbacks
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 67. CodeQL — failure

- Run: [45298879220](https://github.com/AbdallahIsDev/Lausu/actions/runs/45298879220) (attempt 1)
- Event: push · Branch: main
- Commit: `e3209bc` — feat(models): real GGUF hashes/sizes, five production models, dev-only tiny
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 68. Client CI — failure

- Run: [45298879055](https://github.com/AbdallahIsDev/Lausu/actions/runs/45298879055) (attempt 1)
- Event: push · Branch: main
- Commit: `e3209bc` — feat(models): real GGUF hashes/sizes, five production models, dev-only tiny
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 69. Build Linux — failure

- Run: [45298879048](https://github.com/AbdallahIsDev/Lausu/actions/runs/45298879048) (attempt 1)
- Event: push · Branch: main
- Commit: `e3209bc` — feat(models): real GGUF hashes/sizes, five production models, dev-only tiny
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 70. Build installer — failure

- Run: [45298879046](https://github.com/AbdallahIsDev/Lausu/actions/runs/45298879046) (attempt 1)
- Event: push · Branch: main
- Commit: `e3209bc` — feat(models): real GGUF hashes/sizes, five production models, dev-only tiny
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

## Resolved recently

### 1. CI error collector — failure

- Run: [45861147074](https://github.com/AbdallahIsDev/Lausu/actions/runs/45861147074) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `f989c88` — test(client): pin worker-backed ASR hidden imports in the spec
- Job: Collect CI failures into ci-reports · Leg: ubuntu-22.04
- Step: Generate report from main sources
- Category: other
- Fixed by: [45862493012](https://github.com/AbdallahIsDev/Lausu/actions/runs/45862493012) (success)

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 2. CI error collector — failure

- Run: [45858329686](https://github.com/AbdallahIsDev/Lausu/actions/runs/45858329686) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `d70a14e` — docs(plugins): record live evidence and honest edge-case statuses
- Job: Collect CI failures into ci-reports · Leg: ubuntu-22.04
- Step: Generate report from main sources
- Category: other
- Fixed by: [45858621575](https://github.com/AbdallahIsDev/Lausu/actions/runs/45858621575) (success)

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 3. CI error collector — failure

- Run: [45520898834](https://github.com/AbdallahIsDev/Lausu/actions/runs/45520898834) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `0c7989d` — feat: shell cleanup, Models tabs, translation optimizations, GPUI prototype and onboarding UX
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other
- Fixed by: [45657220481](https://github.com/AbdallahIsDev/Lausu/actions/runs/45657220481) (success)

- Error excerpt:

```text
(no job log available)
```

### 4. CI error collector — failure

- Run: [45455690803](https://github.com/AbdallahIsDev/Lausu/actions/runs/45455690803) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `97f834c` — fix(ui): finish removing red error surfaces and retarget moved source pins
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other
- Fixed by: [45456258764](https://github.com/AbdallahIsDev/Lausu/actions/runs/45456258764) (success)

- Error excerpt:

```text
(no job log available)
```

### 5. Client CI — failure

- Run: [45410434401](https://github.com/AbdallahIsDev/Lausu/actions/runs/45410434401) (attempt 1)
- Event: push · Branch: main
- Commit: `2f91e2a` — fix(logs): keep expected GGUF cache misses to one DEBUG line
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other
- Fixed by: [45454671237](https://github.com/AbdallahIsDev/Lausu/actions/runs/45454671237) (success)

- Error excerpt:

```text
(no job log available)
```

### 6. CodeQL — failure

- Run: [45399711542](https://github.com/AbdallahIsDev/Lausu/actions/runs/45399711542) (attempt 1)
- Event: push · Branch: main
- Commit: `9117bf8` — docs: record phase 1 final verified state and owner checklist
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other
- Fixed by: [45410434270](https://github.com/AbdallahIsDev/Lausu/actions/runs/45410434270) (success)

- Error excerpt:

```text
(no job log available)
```

### 7. Build Linux — failure

- Run: [45399711547](https://github.com/AbdallahIsDev/Lausu/actions/runs/45399711547) (attempt 1)
- Event: push · Branch: main
- Commit: `9117bf8` — docs: record phase 1 final verified state and owner checklist
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other
- Fixed by: [45409359001](https://github.com/AbdallahIsDev/Lausu/actions/runs/45409359001) (success)

- Error excerpt:

```text
(no job log available)
```

### 8. CI error collector — failure

- Run: [45307909855](https://github.com/AbdallahIsDev/Lausu/actions/runs/45307909855) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `32d433d` — style: keep timeout constant import at module top
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other
- Fixed by: [45399942909](https://github.com/AbdallahIsDev/Lausu/actions/runs/45399942909) (success)

- Error excerpt:

```text
(no job log available)
```
