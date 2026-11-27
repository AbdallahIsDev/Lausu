# CI Errors

> Generated: 2026-11-27T15:33:03Z
> Data branch commit: `12d8ff6`

## Currently failing

### 1. Client CI — failure

- Run: [46011108033](https://github.com/AbdallahIsDev/Lausu/actions/runs/46011108033) (attempt 1)
- Event: push · Branch: main
- Commit: `d941c88` — fix(lifecycle): resolve POSIX sysconf dynamically and tidy edge-case pins
- Job: Typecheck + Lint + Test · Leg: ubuntu-22.04
- Step: Test (Vitest + coverage)
- Category: eslint/vitest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 2. Build Linux — failure

- Run: [46011107426](https://github.com/AbdallahIsDev/Lausu/actions/runs/46011107426) (attempt 1)
- Event: push · Branch: main
- Commit: `d941c88` — fix(lifecycle): resolve POSIX sysconf dynamically and tidy edge-case pins
- Job: smoke-cargo-check · Leg: ubuntu-22.04
- Step: cargo fmt --check (Tauri Rust host formatting gate)
- Category: gate

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 3. Build installer — failure

- Run: [46011107404](https://github.com/AbdallahIsDev/Lausu/actions/runs/46011107404) (attempt 1)
- Event: push · Branch: main
- Commit: `d941c88` — fix(lifecycle): resolve POSIX sysconf dynamically and tidy edge-case pins
- Job: test (ubuntu-22.04, 3.13) · Leg: ubuntu-22.04, 3.13
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 4. Build installer — failure

- Run: [46011107404](https://github.com/AbdallahIsDev/Lausu/actions/runs/46011107404) (attempt 1)
- Event: push · Branch: main
- Commit: `d941c88` — fix(lifecycle): resolve POSIX sysconf dynamically and tidy edge-case pins
- Job: slow-tests · Leg: ubuntu-22.04
- Step: Run slow manual-script wrappers
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 5. Build installer — failure

- Run: [46011107404](https://github.com/AbdallahIsDev/Lausu/actions/runs/46011107404) (attempt 1)
- Event: push · Branch: main
- Commit: `d941c88` — fix(lifecycle): resolve POSIX sysconf dynamically and tidy edge-case pins
- Job: test (windows-2022, 3.12) · Leg: windows-2022, 3.12
- Step: mypy (ratchet compare against baseline)
- Category: mypy ratchet

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 6. Build installer — failure

- Run: [46011107404](https://github.com/AbdallahIsDev/Lausu/actions/runs/46011107404) (attempt 1)
- Event: push · Branch: main
- Commit: `d941c88` — fix(lifecycle): resolve POSIX sysconf dynamically and tidy edge-case pins
- Job: test (ubuntu-22.04, 3.11) · Leg: ubuntu-22.04, 3.11
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 7. Build installer — failure

- Run: [46011107404](https://github.com/AbdallahIsDev/Lausu/actions/runs/46011107404) (attempt 1)
- Event: push · Branch: main
- Commit: `d941c88` — fix(lifecycle): resolve POSIX sysconf dynamically and tidy edge-case pins
- Job: test (windows-2022, 3.11) · Leg: windows-2022, 3.11
- Step: mypy (ratchet compare against baseline)
- Category: mypy ratchet

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 8. Build installer — failure

- Run: [46011107404](https://github.com/AbdallahIsDev/Lausu/actions/runs/46011107404) (attempt 1)
- Event: push · Branch: main
- Commit: `d941c88` — fix(lifecycle): resolve POSIX sysconf dynamically and tidy edge-case pins
- Job: test (ubuntu-22.04, 3.12) · Leg: ubuntu-22.04, 3.12
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 9. Build installer — failure

- Run: [46011107404](https://github.com/AbdallahIsDev/Lausu/actions/runs/46011107404) (attempt 1)
- Event: push · Branch: main
- Commit: `d941c88` — fix(lifecycle): resolve POSIX sysconf dynamically and tidy edge-case pins
- Job: Rust clippy + cargo audit · Leg: ubuntu-22.04
- Step: Run rustsec/audit-check@v2
- Category: cargo test/clippy/audit

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 10. Build installer — failure

- Run: [46011107404](https://github.com/AbdallahIsDev/Lausu/actions/runs/46011107404) (attempt 1)
- Event: push · Branch: main
- Commit: `d941c88` — fix(lifecycle): resolve POSIX sysconf dynamically and tidy edge-case pins
- Job: test (macos-15, 3.12) · Leg: macos-15, 3.12
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

## Recent failures

### 1. CI error collector — failure

- Run: [46013645462](https://github.com/AbdallahIsDev/Lausu/actions/runs/46013645462) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `d941c88` — fix(lifecycle): resolve POSIX sysconf dynamically and tidy edge-case pins
- Job: Collect CI failures into ci-reports · Leg: ubuntu-22.04
- Step: Generate report from main sources
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 2. CI error collector — failure

- Run: [46013027422](https://github.com/AbdallahIsDev/Lausu/actions/runs/46013027422) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `d941c88` — fix(lifecycle): resolve POSIX sysconf dynamically and tidy edge-case pins
- Job: Collect CI failures into ci-reports · Leg: ubuntu-22.04
- Step: Generate report from main sources
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 3. CI error collector — failure

- Run: [46011961734](https://github.com/AbdallahIsDev/Lausu/actions/runs/46011961734) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `d941c88` — fix(lifecycle): resolve POSIX sysconf dynamically and tidy edge-case pins
- Job: Collect CI failures into ci-reports · Leg: ubuntu-22.04
- Step: Generate report from main sources
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 4. CI error collector — failure

- Run: [46011406606](https://github.com/AbdallahIsDev/Lausu/actions/runs/46011406606) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `d941c88` — fix(lifecycle): resolve POSIX sysconf dynamically and tidy edge-case pins
- Job: Collect CI failures into ci-reports · Leg: ubuntu-22.04
- Step: Generate report from main sources
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 5. Client CI — failure

- Run: [46011108033](https://github.com/AbdallahIsDev/Lausu/actions/runs/46011108033) (attempt 1)
- Event: push · Branch: main
- Commit: `d941c88` — fix(lifecycle): resolve POSIX sysconf dynamically and tidy edge-case pins
- Job: Typecheck + Lint + Test · Leg: ubuntu-22.04
- Step: Test (Vitest + coverage)
- Category: eslint/vitest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 6. Build Linux — failure

- Run: [46011107426](https://github.com/AbdallahIsDev/Lausu/actions/runs/46011107426) (attempt 1)
- Event: push · Branch: main
- Commit: `d941c88` — fix(lifecycle): resolve POSIX sysconf dynamically and tidy edge-case pins
- Job: smoke-cargo-check · Leg: ubuntu-22.04
- Step: cargo fmt --check (Tauri Rust host formatting gate)
- Category: gate

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 7. Build installer — failure

- Run: [46011107404](https://github.com/AbdallahIsDev/Lausu/actions/runs/46011107404) (attempt 1)
- Event: push · Branch: main
- Commit: `d941c88` — fix(lifecycle): resolve POSIX sysconf dynamically and tidy edge-case pins
- Job: test (ubuntu-22.04, 3.13) · Leg: ubuntu-22.04, 3.13
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 8. Build installer — failure

- Run: [46011107404](https://github.com/AbdallahIsDev/Lausu/actions/runs/46011107404) (attempt 1)
- Event: push · Branch: main
- Commit: `d941c88` — fix(lifecycle): resolve POSIX sysconf dynamically and tidy edge-case pins
- Job: slow-tests · Leg: ubuntu-22.04
- Step: Run slow manual-script wrappers
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 9. Build installer — failure

- Run: [46011107404](https://github.com/AbdallahIsDev/Lausu/actions/runs/46011107404) (attempt 1)
- Event: push · Branch: main
- Commit: `d941c88` — fix(lifecycle): resolve POSIX sysconf dynamically and tidy edge-case pins
- Job: test (windows-2022, 3.12) · Leg: windows-2022, 3.12
- Step: mypy (ratchet compare against baseline)
- Category: mypy ratchet

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 10. Build installer — failure

- Run: [46011107404](https://github.com/AbdallahIsDev/Lausu/actions/runs/46011107404) (attempt 1)
- Event: push · Branch: main
- Commit: `d941c88` — fix(lifecycle): resolve POSIX sysconf dynamically and tidy edge-case pins
- Job: test (ubuntu-22.04, 3.11) · Leg: ubuntu-22.04, 3.11
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 11. Build installer — failure

- Run: [46011107404](https://github.com/AbdallahIsDev/Lausu/actions/runs/46011107404) (attempt 1)
- Event: push · Branch: main
- Commit: `d941c88` — fix(lifecycle): resolve POSIX sysconf dynamically and tidy edge-case pins
- Job: test (windows-2022, 3.11) · Leg: windows-2022, 3.11
- Step: mypy (ratchet compare against baseline)
- Category: mypy ratchet

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 12. Build installer — failure

- Run: [46011107404](https://github.com/AbdallahIsDev/Lausu/actions/runs/46011107404) (attempt 1)
- Event: push · Branch: main
- Commit: `d941c88` — fix(lifecycle): resolve POSIX sysconf dynamically and tidy edge-case pins
- Job: test (ubuntu-22.04, 3.12) · Leg: ubuntu-22.04, 3.12
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 13. Build installer — failure

- Run: [46011107404](https://github.com/AbdallahIsDev/Lausu/actions/runs/46011107404) (attempt 1)
- Event: push · Branch: main
- Commit: `d941c88` — fix(lifecycle): resolve POSIX sysconf dynamically and tidy edge-case pins
- Job: Rust clippy + cargo audit · Leg: ubuntu-22.04
- Step: Run rustsec/audit-check@v2
- Category: cargo test/clippy/audit

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 14. Build installer — failure

- Run: [46011107404](https://github.com/AbdallahIsDev/Lausu/actions/runs/46011107404) (attempt 1)
- Event: push · Branch: main
- Commit: `d941c88` — fix(lifecycle): resolve POSIX sysconf dynamically and tidy edge-case pins
- Job: test (macos-15, 3.12) · Leg: macos-15, 3.12
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 15. CI error collector — failure

- Run: [45919343404](https://github.com/AbdallahIsDev/Lausu/actions/runs/45919343404) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `ac9fd08` — docs(plugins): record live-text captures, verdicts and start-origin incident
- Job: Collect CI failures into ci-reports · Leg: ubuntu-22.04
- Step: Generate report from main sources
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 16. CI error collector — failure

- Run: [45919256901](https://github.com/AbdallahIsDev/Lausu/actions/runs/45919256901) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `ac9fd08` — docs(plugins): record live-text captures, verdicts and start-origin incident
- Job: Collect CI failures into ci-reports · Leg: ubuntu-22.04
- Step: Generate report from main sources
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 17. CI error collector — failure

- Run: [45918579927](https://github.com/AbdallahIsDev/Lausu/actions/runs/45918579927) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `ac9fd08` — docs(plugins): record live-text captures, verdicts and start-origin incident
- Job: Collect CI failures into ci-reports · Leg: ubuntu-22.04
- Step: Generate report from main sources
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 18. CI error collector — failure

- Run: [45918289148](https://github.com/AbdallahIsDev/Lausu/actions/runs/45918289148) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `ac9fd08` — docs(plugins): record live-text captures, verdicts and start-origin incident
- Job: Collect CI failures into ci-reports · Leg: ubuntu-22.04
- Step: Generate report from main sources
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 19. Build installer — failure

- Run: [45918142637](https://github.com/AbdallahIsDev/Lausu/actions/runs/45918142637) (attempt 1)
- Event: push · Branch: main
- Commit: `ac9fd08` — docs(plugins): record live-text captures, verdicts and start-origin incident
- Job: slow-tests · Leg: ubuntu-22.04
- Step: Run slow manual-script wrappers
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 20. Build installer — failure

- Run: [45918142637](https://github.com/AbdallahIsDev/Lausu/actions/runs/45918142637) (attempt 1)
- Event: push · Branch: main
- Commit: `ac9fd08` — docs(plugins): record live-text captures, verdicts and start-origin incident
- Job: test (macos-15, 3.11) · Leg: macos-15, 3.11
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 21. Build installer — failure

- Run: [45918142637](https://github.com/AbdallahIsDev/Lausu/actions/runs/45918142637) (attempt 1)
- Event: push · Branch: main
- Commit: `ac9fd08` — docs(plugins): record live-text captures, verdicts and start-origin incident
- Job: Rust clippy + cargo audit · Leg: ubuntu-22.04
- Step: Run rustsec/audit-check@v2
- Category: cargo test/clippy/audit

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 22. Build installer — failure

- Run: [45918142637](https://github.com/AbdallahIsDev/Lausu/actions/runs/45918142637) (attempt 1)
- Event: push · Branch: main
- Commit: `ac9fd08` — docs(plugins): record live-text captures, verdicts and start-origin incident
- Job: test (ubuntu-22.04, 3.13) · Leg: ubuntu-22.04, 3.13
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 23. Build installer — failure

- Run: [45918142637](https://github.com/AbdallahIsDev/Lausu/actions/runs/45918142637) (attempt 1)
- Event: push · Branch: main
- Commit: `ac9fd08` — docs(plugins): record live-text captures, verdicts and start-origin incident
- Job: test (ubuntu-22.04, 3.12) · Leg: ubuntu-22.04, 3.12
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 24. Build installer — failure

- Run: [45918142637](https://github.com/AbdallahIsDev/Lausu/actions/runs/45918142637) (attempt 1)
- Event: push · Branch: main
- Commit: `ac9fd08` — docs(plugins): record live-text captures, verdicts and start-origin incident
- Job: test (ubuntu-22.04, 3.11) · Leg: ubuntu-22.04, 3.11
- Step: Run tests with coverage
- Category: pytest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 25. Build installer — failure

- Run: [45918142637](https://github.com/AbdallahIsDev/Lausu/actions/runs/45918142637) (attempt 1)
- Event: push · Branch: main
- Commit: `ac9fd08` — docs(plugins): record live-text captures, verdicts and start-origin incident
- Job: test (windows-2022, 3.13) · Leg: windows-2022, 3.13
- Step: mypy (ratchet compare against baseline)
- Category: mypy ratchet

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 26. Build installer — failure

- Run: [45918142637](https://github.com/AbdallahIsDev/Lausu/actions/runs/45918142637) (attempt 1)
- Event: push · Branch: main
- Commit: `ac9fd08` — docs(plugins): record live-text captures, verdicts and start-origin incident
- Job: test (windows-2022, 3.11) · Leg: windows-2022, 3.11
- Step: mypy (ratchet compare against baseline)
- Category: mypy ratchet

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 27. Client CI — failure

- Run: [45918142622](https://github.com/AbdallahIsDev/Lausu/actions/runs/45918142622) (attempt 1)
- Event: push · Branch: main
- Commit: `ac9fd08` — docs(plugins): record live-text captures, verdicts and start-origin incident
- Job: Typecheck + Lint + Test · Leg: ubuntu-22.04
- Step: Test (Vitest + coverage)
- Category: eslint/vitest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 28. Client CI — failure

- Run: [45918142622](https://github.com/AbdallahIsDev/Lausu/actions/runs/45918142622) (attempt 1)
- Event: push · Branch: main
- Commit: `ac9fd08` — docs(plugins): record live-text captures, verdicts and start-origin incident
- Job: Security audit · Leg: n/a
- Step: (job-level failure)
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 29. Client CI — failure

- Run: [45918142622](https://github.com/AbdallahIsDev/Lausu/actions/runs/45918142622) (attempt 1)
- Event: push · Branch: main
- Commit: `ac9fd08` — docs(plugins): record live-text captures, verdicts and start-origin incident
- Job: Test results · Leg: n/a
- Step: (job-level failure)
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 30. CI error collector — failure

- Run: [45915307255](https://github.com/AbdallahIsDev/Lausu/actions/runs/45915307255) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `9c3966f` — docs(translation): record Round 4 decisions, measured CPU/GPU evidence and next gates
- Job: Collect CI failures into ci-reports · Leg: ubuntu-22.04
- Step: Generate report from main sources
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 31. CI error collector — failure

- Run: [45915112940](https://github.com/AbdallahIsDev/Lausu/actions/runs/45915112940) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `9c3966f` — docs(translation): record Round 4 decisions, measured CPU/GPU evidence and next gates
- Job: Collect CI failures into ci-reports · Leg: ubuntu-22.04
- Step: Generate report from main sources
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 32. CI error collector — failure

- Run: [45915094638](https://github.com/AbdallahIsDev/Lausu/actions/runs/45915094638) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `9c3966f` — docs(translation): record Round 4 decisions, measured CPU/GPU evidence and next gates
- Job: Collect CI failures into ci-reports · Leg: ubuntu-22.04
- Step: Generate report from main sources
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 33. Build installer — failure

- Run: [45914965538](https://github.com/AbdallahIsDev/Lausu/actions/runs/45914965538) (attempt 1)
- Event: push · Branch: main
- Commit: `9c3966f` — docs(translation): record Round 4 decisions, measured CPU/GPU evidence and next gates
- Job: slow-tests · Leg: ubuntu-22.04
- Step: Run slow manual-script wrappers
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 34. Build installer — failure

- Run: [45914965538](https://github.com/AbdallahIsDev/Lausu/actions/runs/45914965538) (attempt 1)
- Event: push · Branch: main
- Commit: `9c3966f` — docs(translation): record Round 4 decisions, measured CPU/GPU evidence and next gates
- Job: Rust clippy + cargo audit · Leg: ubuntu-22.04
- Step: Run rustsec/audit-check@v2
- Category: cargo test/clippy/audit

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 35. Build installer — failure

- Run: [45914965538](https://github.com/AbdallahIsDev/Lausu/actions/runs/45914965538) (attempt 1)
- Event: push · Branch: main
- Commit: `9c3966f` — docs(translation): record Round 4 decisions, measured CPU/GPU evidence and next gates
- Job: test (macos-15, 3.11) · Leg: macos-15, 3.11
- Step: Ruff (ratchet compare against baseline)
- Category: ruff

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 36. Build installer — failure

- Run: [45914965538](https://github.com/AbdallahIsDev/Lausu/actions/runs/45914965538) (attempt 1)
- Event: push · Branch: main
- Commit: `9c3966f` — docs(translation): record Round 4 decisions, measured CPU/GPU evidence and next gates
- Job: test (macos-15, 3.13) · Leg: macos-15, 3.13
- Step: Ruff (ratchet compare against baseline)
- Category: ruff

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 37. Build installer — failure

- Run: [45914965538](https://github.com/AbdallahIsDev/Lausu/actions/runs/45914965538) (attempt 1)
- Event: push · Branch: main
- Commit: `9c3966f` — docs(translation): record Round 4 decisions, measured CPU/GPU evidence and next gates
- Job: test (ubuntu-22.04, 3.12) · Leg: ubuntu-22.04, 3.12
- Step: Ruff (ratchet compare against baseline)
- Category: ruff

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 38. Build installer — failure

- Run: [45914965538](https://github.com/AbdallahIsDev/Lausu/actions/runs/45914965538) (attempt 1)
- Event: push · Branch: main
- Commit: `9c3966f` — docs(translation): record Round 4 decisions, measured CPU/GPU evidence and next gates
- Job: test (windows-2022, 3.13) · Leg: windows-2022, 3.13
- Step: Ruff (ratchet compare against baseline)
- Category: ruff

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 39. Build installer — failure

- Run: [45914965538](https://github.com/AbdallahIsDev/Lausu/actions/runs/45914965538) (attempt 1)
- Event: push · Branch: main
- Commit: `9c3966f` — docs(translation): record Round 4 decisions, measured CPU/GPU evidence and next gates
- Job: test (windows-2022, 3.12) · Leg: windows-2022, 3.12
- Step: Ruff (ratchet compare against baseline)
- Category: ruff

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 40. Build installer — failure

- Run: [45914965538](https://github.com/AbdallahIsDev/Lausu/actions/runs/45914965538) (attempt 1)
- Event: push · Branch: main
- Commit: `9c3966f` — docs(translation): record Round 4 decisions, measured CPU/GPU evidence and next gates
- Job: test (macos-15, 3.12) · Leg: macos-15, 3.12
- Step: Ruff (ratchet compare against baseline)
- Category: ruff

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 41. Client CI — failure

- Run: [45914965534](https://github.com/AbdallahIsDev/Lausu/actions/runs/45914965534) (attempt 1)
- Event: push · Branch: main
- Commit: `9c3966f` — docs(translation): record Round 4 decisions, measured CPU/GPU evidence and next gates
- Job: Typecheck + Lint + Test · Leg: ubuntu-22.04
- Step: Test (Vitest + coverage)
- Category: eslint/vitest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 42. Client CI — failure

- Run: [45914965534](https://github.com/AbdallahIsDev/Lausu/actions/runs/45914965534) (attempt 1)
- Event: push · Branch: main
- Commit: `9c3966f` — docs(translation): record Round 4 decisions, measured CPU/GPU evidence and next gates
- Job: Security audit · Leg: n/a
- Step: (job-level failure)
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 43. CI error collector — failure

- Run: [45901994665](https://github.com/AbdallahIsDev/Lausu/actions/runs/45901994665) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `da6665d` — feat(translation): consent-gated download row with progress, cancel and disk check; missing model keeps text with one notice
- Job: Collect CI failures into ci-reports · Leg: ubuntu-22.04
- Step: Generate report from main sources
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 44. CI error collector — failure

- Run: [45900525361](https://github.com/AbdallahIsDev/Lausu/actions/runs/45900525361) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `da6665d` — feat(translation): consent-gated download row with progress, cancel and disk check; missing model keeps text with one notice
- Job: Collect CI failures into ci-reports · Leg: ubuntu-22.04
- Step: Generate report from main sources
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 45. CI error collector — failure

- Run: [45900376791](https://github.com/AbdallahIsDev/Lausu/actions/runs/45900376791) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `da6665d` — feat(translation): consent-gated download row with progress, cancel and disk check; missing model keeps text with one notice
- Job: Collect CI failures into ci-reports · Leg: ubuntu-22.04
- Step: Generate report from main sources
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 46. CI error collector — failure

- Run: [45900302469](https://github.com/AbdallahIsDev/Lausu/actions/runs/45900302469) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `da6665d` — feat(translation): consent-gated download row with progress, cancel and disk check; missing model keeps text with one notice
- Job: Collect CI failures into ci-reports · Leg: ubuntu-22.04
- Step: Generate report from main sources
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 47. CI error collector — failure

- Run: [45900285221](https://github.com/AbdallahIsDev/Lausu/actions/runs/45900285221) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `da6665d` — feat(translation): consent-gated download row with progress, cancel and disk check; missing model keeps text with one notice
- Job: Collect CI failures into ci-reports · Leg: ubuntu-22.04
- Step: Generate report from main sources
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 48. Client CI — failure

- Run: [45900138344](https://github.com/AbdallahIsDev/Lausu/actions/runs/45900138344) (attempt 1)
- Event: push · Branch: main
- Commit: `da6665d` — feat(translation): consent-gated download row with progress, cancel and disk check; missing model keeps text with one notice
- Job: Typecheck + Lint + Test · Leg: ubuntu-22.04
- Step: Test (Vitest + coverage)
- Category: eslint/vitest

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 49. Build Linux — failure

- Run: [45900137816](https://github.com/AbdallahIsDev/Lausu/actions/runs/45900137816) (attempt 1)
- Event: push · Branch: main
- Commit: `da6665d` — feat(translation): consent-gated download row with progress, cancel and disk check; missing model keeps text with one notice
- Job: smoke-cargo-check · Leg: ubuntu-22.04
- Step: cargo fmt --check (Tauri Rust host formatting gate)
- Category: gate

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 50. Build installer — failure

- Run: [45900137806](https://github.com/AbdallahIsDev/Lausu/actions/runs/45900137806) (attempt 1)
- Event: push · Branch: main
- Commit: `da6665d` — feat(translation): consent-gated download row with progress, cancel and disk check; missing model keeps text with one notice
- Job: test (windows-2022, 3.12) · Leg: windows-2022, 3.12
- Step: Ruff (ratchet compare against baseline)
- Category: ruff

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 51. Build installer — failure

- Run: [45900137806](https://github.com/AbdallahIsDev/Lausu/actions/runs/45900137806) (attempt 1)
- Event: push · Branch: main
- Commit: `da6665d` — feat(translation): consent-gated download row with progress, cancel and disk check; missing model keeps text with one notice
- Job: Rust clippy + cargo audit · Leg: ubuntu-22.04
- Step: Run rustsec/audit-check@v2
- Category: cargo test/clippy/audit

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 52. Build installer — failure

- Run: [45900137806](https://github.com/AbdallahIsDev/Lausu/actions/runs/45900137806) (attempt 1)
- Event: push · Branch: main
- Commit: `da6665d` — feat(translation): consent-gated download row with progress, cancel and disk check; missing model keeps text with one notice
- Job: slow-tests · Leg: ubuntu-22.04
- Step: Run slow manual-script wrappers
- Category: other

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 53. Build installer — failure

- Run: [45900137806](https://github.com/AbdallahIsDev/Lausu/actions/runs/45900137806) (attempt 1)
- Event: push · Branch: main
- Commit: `da6665d` — feat(translation): consent-gated download row with progress, cancel and disk check; missing model keeps text with one notice
- Job: test (macos-15, 3.11) · Leg: macos-15, 3.11
- Step: Ruff (ratchet compare against baseline)
- Category: ruff

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 54. Build installer — failure

- Run: [45900137806](https://github.com/AbdallahIsDev/Lausu/actions/runs/45900137806) (attempt 1)
- Event: push · Branch: main
- Commit: `da6665d` — feat(translation): consent-gated download row with progress, cancel and disk check; missing model keeps text with one notice
- Job: test (macos-15, 3.13) · Leg: macos-15, 3.13
- Step: Ruff (ratchet compare against baseline)
- Category: ruff

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 55. Build installer — failure

- Run: [45900137806](https://github.com/AbdallahIsDev/Lausu/actions/runs/45900137806) (attempt 1)
- Event: push · Branch: main
- Commit: `da6665d` — feat(translation): consent-gated download row with progress, cancel and disk check; missing model keeps text with one notice
- Job: test (windows-2022, 3.11) · Leg: windows-2022, 3.11
- Step: Ruff (ratchet compare against baseline)
- Category: ruff

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 56. Build installer — failure

- Run: [45900137806](https://github.com/AbdallahIsDev/Lausu/actions/runs/45900137806) (attempt 1)
- Event: push · Branch: main
- Commit: `da6665d` — feat(translation): consent-gated download row with progress, cancel and disk check; missing model keeps text with one notice
- Job: test (windows-2022, 3.13) · Leg: windows-2022, 3.13
- Step: Ruff (ratchet compare against baseline)
- Category: ruff

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 57. Build installer — failure

- Run: [45900137806](https://github.com/AbdallahIsDev/Lausu/actions/runs/45900137806) (attempt 1)
- Event: push · Branch: main
- Commit: `da6665d` — feat(translation): consent-gated download row with progress, cancel and disk check; missing model keeps text with one notice
- Job: test (ubuntu-22.04, 3.11) · Leg: ubuntu-22.04, 3.11
- Step: Ruff (ratchet compare against baseline)
- Category: ruff

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 58. CI error collector — failure

- Run: [45897279304](https://github.com/AbdallahIsDev/Lausu/actions/runs/45897279304) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `428685a` — docs(research): fake-audio and real-path evidence for partial recovery
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 59. CI error collector — failure

- Run: [45897148493](https://github.com/AbdallahIsDev/Lausu/actions/runs/45897148493) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `428685a` — docs(research): fake-audio and real-path evidence for partial recovery
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 60. CI error collector — failure

- Run: [45896563643](https://github.com/AbdallahIsDev/Lausu/actions/runs/45896563643) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `428685a` — docs(research): fake-audio and real-path evidence for partial recovery
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 61. CI error collector — failure

- Run: [45896010049](https://github.com/AbdallahIsDev/Lausu/actions/runs/45896010049) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `428685a` — docs(research): fake-audio and real-path evidence for partial recovery
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 62. Build installer — failure

- Run: [45895830737](https://github.com/AbdallahIsDev/Lausu/actions/runs/45895830737) (attempt 1)
- Event: push · Branch: main
- Commit: `428685a` — docs(research): fake-audio and real-path evidence for partial recovery
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 63. Client CI — failure

- Run: [45895830587](https://github.com/AbdallahIsDev/Lausu/actions/runs/45895830587) (attempt 1)
- Event: push · Branch: main
- Commit: `428685a` — docs(research): fake-audio and real-path evidence for partial recovery
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 64. CI error collector — failure

- Run: [45890684313](https://github.com/AbdallahIsDev/Lausu/actions/runs/45890684313) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `ff210f6` — docs(research): partial dictation recovery feasibility
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 65. Client CI — failure

- Run: [45890148837](https://github.com/AbdallahIsDev/Lausu/actions/runs/45890148837) (attempt 1)
- Event: push · Branch: main
- Commit: `ff210f6` — docs(research): partial dictation recovery feasibility
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 66. Build installer — failure

- Run: [45890148821](https://github.com/AbdallahIsDev/Lausu/actions/runs/45890148821) (attempt 1)
- Event: push · Branch: main
- Commit: `ff210f6` — docs(research): partial dictation recovery feasibility
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 67. CI error collector — failure

- Run: [45883158906](https://github.com/AbdallahIsDev/Lausu/actions/runs/45883158906) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `a049b33` — fix(plugins): skip stop POST into a missing tab and drop expected traceback
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 68. CI error collector — failure

- Run: [45870119710](https://github.com/AbdallahIsDev/Lausu/actions/runs/45870119710) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `a049b33` — fix(plugins): skip stop POST into a missing tab and drop expected traceback
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 69. Client CI — failure

- Run: [45868604297](https://github.com/AbdallahIsDev/Lausu/actions/runs/45868604297) (attempt 1)
- Event: push · Branch: main
- Commit: `a049b33` — fix(plugins): skip stop POST into a missing tab and drop expected traceback
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 70. Build installer — failure

- Run: [45868604239](https://github.com/AbdallahIsDev/Lausu/actions/runs/45868604239) (attempt 1)
- Event: push · Branch: main
- Commit: `a049b33` — fix(plugins): skip stop POST into a missing tab and drop expected traceback
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 71. CI error collector — failure

- Run: [45865840634](https://github.com/AbdallahIsDev/Lausu/actions/runs/45865840634) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `58e973c` — fix(imports): break the security/registry cycle with a legacy-id constants module
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 72. Client CI — failure

- Run: [45863293307](https://github.com/AbdallahIsDev/Lausu/actions/runs/45863293307) (attempt 1)
- Event: push · Branch: main
- Commit: `58e973c` — fix(imports): break the security/registry cycle with a legacy-id constants module
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 73. Build installer — failure

- Run: [45863293201](https://github.com/AbdallahIsDev/Lausu/actions/runs/45863293201) (attempt 1)
- Event: push · Branch: main
- Commit: `58e973c` — fix(imports): break the security/registry cycle with a legacy-id constants module
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 74. CI error collector — failure

- Run: [45861147074](https://github.com/AbdallahIsDev/Lausu/actions/runs/45861147074) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `f989c88` — test(client): pin worker-backed ASR hidden imports in the spec
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 75. CI error collector — failure

- Run: [45860910924](https://github.com/AbdallahIsDev/Lausu/actions/runs/45860910924) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `f989c88` — test(client): pin worker-backed ASR hidden imports in the spec
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 76. CI error collector — failure

- Run: [45859088557](https://github.com/AbdallahIsDev/Lausu/actions/runs/45859088557) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `f989c88` — test(client): pin worker-backed ASR hidden imports in the spec
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 77. Build installer — failure

- Run: [45858394834](https://github.com/AbdallahIsDev/Lausu/actions/runs/45858394834) (attempt 1)
- Event: push · Branch: main
- Commit: `f989c88` — test(client): pin worker-backed ASR hidden imports in the spec
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 78. Build Linux — failure

- Run: [45858393735](https://github.com/AbdallahIsDev/Lausu/actions/runs/45858393735) (attempt 1)
- Event: push · Branch: main
- Commit: `f989c88` — test(client): pin worker-backed ASR hidden imports in the spec
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 79. Client CI — failure

- Run: [45858393511](https://github.com/AbdallahIsDev/Lausu/actions/runs/45858393511) (attempt 1)
- Event: push · Branch: main
- Commit: `f989c88` — test(client): pin worker-backed ASR hidden imports in the spec
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 80. CI error collector — failure

- Run: [45858329686](https://github.com/AbdallahIsDev/Lausu/actions/runs/45858329686) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `d70a14e` — docs(plugins): record live evidence and honest edge-case statuses
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 81. Build Linux — failure

- Run: [45848520453](https://github.com/AbdallahIsDev/Lausu/actions/runs/45848520453) (attempt 1)
- Event: push · Branch: main
- Commit: `d70a14e` — docs(plugins): record live evidence and honest edge-case statuses
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 82. Build installer — failure

- Run: [45848520451](https://github.com/AbdallahIsDev/Lausu/actions/runs/45848520451) (attempt 1)
- Event: push · Branch: main
- Commit: `d70a14e` — docs(plugins): record live evidence and honest edge-case statuses
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 83. Build installer — failure

- Run: [45741472226](https://github.com/AbdallahIsDev/Lausu/actions/runs/45741472226) (attempt 1)
- Event: push · Branch: main
- Commit: `fd574b0` — docs(plugins): reclassify edge cases with live evidence
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 84. Build Linux — failure

- Run: [45730000324](https://github.com/AbdallahIsDev/Lausu/actions/runs/45730000324) (attempt 1)
- Event: push · Branch: main
- Commit: `94b4311` — fix(permissions): dev-only tabs permission and staged-bundle pins
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 85. Build installer — failure

- Run: [45730000314](https://github.com/AbdallahIsDev/Lausu/actions/runs/45730000314) (attempt 1)
- Event: push · Branch: main
- Commit: `94b4311` — fix(permissions): dev-only tabs permission and staged-bundle pins
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other

- Error excerpt:

```text
(no job log available)
```

### 86. Build installer — failure

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

### 87. Build Linux — failure

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

### 88. Build installer — failure

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

### 89. Build installer — failure

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

### 90. Build Linux — failure

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

### 91. Build Linux — failure

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

## Resolved recently

### 1. CI error collector — failure

- Run: [45919343404](https://github.com/AbdallahIsDev/Lausu/actions/runs/45919343404) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `ac9fd08` — docs(plugins): record live-text captures, verdicts and start-origin incident
- Job: Collect CI failures into ci-reports · Leg: ubuntu-22.04
- Step: Generate report from main sources
- Category: other
- Fixed by: [46011338697](https://github.com/AbdallahIsDev/Lausu/actions/runs/46011338697) (success)

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 2. CI error collector — failure

- Run: [45915307255](https://github.com/AbdallahIsDev/Lausu/actions/runs/45915307255) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `9c3966f` — docs(translation): record Round 4 decisions, measured CPU/GPU evidence and next gates
- Job: Collect CI failures into ci-reports · Leg: ubuntu-22.04
- Step: Generate report from main sources
- Category: other
- Fixed by: [45916623927](https://github.com/AbdallahIsDev/Lausu/actions/runs/45916623927) (success)

- Error excerpt:

```text
(job log unavailable: HTTP 403)
```

### 3. CI error collector — failure

- Run: [45897148493](https://github.com/AbdallahIsDev/Lausu/actions/runs/45897148493) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `428685a` — docs(research): fake-audio and real-path evidence for partial recovery
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other
- Fixed by: [45897162803](https://github.com/AbdallahIsDev/Lausu/actions/runs/45897162803) (success)

- Error excerpt:

```text
(no job log available)
```

### 4. CI error collector — failure

- Run: [45890684313](https://github.com/AbdallahIsDev/Lausu/actions/runs/45890684313) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `ff210f6` — docs(research): partial dictation recovery feasibility
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other
- Fixed by: [45892158798](https://github.com/AbdallahIsDev/Lausu/actions/runs/45892158798) (success)

- Error excerpt:

```text
(no job log available)
```

### 5. CI error collector — failure

- Run: [45870119710](https://github.com/AbdallahIsDev/Lausu/actions/runs/45870119710) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `a049b33` — fix(plugins): skip stop POST into a missing tab and drop expected traceback
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other
- Fixed by: [45875702162](https://github.com/AbdallahIsDev/Lausu/actions/runs/45875702162) (success)

- Error excerpt:

```text
(no job log available)
```

### 6. CI error collector — failure

- Run: [45865840634](https://github.com/AbdallahIsDev/Lausu/actions/runs/45865840634) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `58e973c` — fix(imports): break the security/registry cycle with a legacy-id constants module
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other
- Fixed by: [45867530583](https://github.com/AbdallahIsDev/Lausu/actions/runs/45867530583) (success)

- Error excerpt:

```text
(no job log available)
```

### 7. CI error collector — failure

- Run: [45861147074](https://github.com/AbdallahIsDev/Lausu/actions/runs/45861147074) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `f989c88` — test(client): pin worker-backed ASR hidden imports in the spec
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other
- Fixed by: [45862493012](https://github.com/AbdallahIsDev/Lausu/actions/runs/45862493012) (success)

- Error excerpt:

```text
(no job log available)
```

### 8. CI error collector — failure

- Run: [45858329686](https://github.com/AbdallahIsDev/Lausu/actions/runs/45858329686) (attempt 1)
- Event: workflow_run · Branch: main
- Commit: `d70a14e` — docs(plugins): record live evidence and honest edge-case statuses
- Job: (job details unavailable) · Leg: n/a
- Step: 
- Category: other
- Fixed by: [45858621575](https://github.com/AbdallahIsDev/Lausu/actions/runs/45858621575) (success)

- Error excerpt:

```text
(no job log available)
```

### 9. CI error collector — failure

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

### 10. CI error collector — failure

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

### 11. Client CI — failure

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
