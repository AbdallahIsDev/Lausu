# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**1 failing/errored tests** across 1 matrix legs.

### 1. `tests.test_shutdown_pool_drain.TestDoCleanupDrainsWsPoolViaProductionPath.test_do_cleanup_drains_ws_pool_via_production_path`

- Legs: ubuntu-22.04-3.13
- Location: `tests/test_shutdown_pool_drain.py:245`

```
+  where 0 = len([])

AssertionError: YJ-20: expected exactly one WARNING log record from voice_typer.server.shutdown_controller for the pool drain timeout; got 0. This assertion catches mutations that remove the daemon-thread+join block (shutdown_controller.py lines 402-410), without that block, no WARNING is emitted. All WARNING records seen: [('voice_typer.server._timeout_utils', '[SHUTDOWN] ws_dispatch_pool.drain did not finish in 5.0s, continuing (worker thread leaked as daemon, registered for best-effort join via join_leaked_workers)')]
assert 0 == 1
 +  where 0 = len([])
tests/test_shutdown_pool_drain.py:245: in test_do_cleanup_drains_ws_pool_via_production_path
    assert len(warning_records) == 1, (
E   AssertionError: YJ-20: expected exactly one WARNING log record from voice_typer.server.shutdown_controller for the pool drain timeout; got 0. This assertion catches mutations that remove the daemon-thread+join block (shutdown_controller.py lines 402-410), without that block, no WARNING is emitted. All WARNING records seen: [('voice_typer.server._timeout_utils', '[SHUTDOWN] ws_dispatch_pool.drain did not finish in 5.0s, continuing (worker thread leaked as daemon, registered for best-effort join via join_leaked_workers)')]
E   assert 0 == 1
E    +  where 0 = len([])
```
