# CI Errors

> Auto-generated from the latest GitHub Actions run via `scripts/ci/write_ci_errors.py`. Do not edit by hand, it is overwritten on every CI run.

**122 failing/errored tests** across 9 matrix legs.

### 1. `tests.handlers.test_handler_signature_conformance`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/handlers/test_handler_signature_conformance.py:13`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/handlers/test_handler_signature_conformance.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/handlers/test_handler_signature_conformance.py:13: in <module>
    import voice_typer.server.handlers as _handlers_pkg
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 2. `tests.handlers.test_privacy_handlers`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/handlers/test_privacy_handlers.py:8`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/handlers/test_privacy_handlers.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/handlers/test_privacy_handlers.py:8: in <module>
    from voice_typer.server.handlers import PrivacyHandlersMixin as ReExportedMixin
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 3. `tests.regressions.test_cli_exit_codes`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/regressions/test_cli_exit_codes.py:19`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/regressions/test_cli_exit_codes.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/regressions/test_cli_exit_codes.py:19: in <module>
    from voice_typer.server import ipc_server
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 4. `tests.server`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/server/conftest.py:8`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
tests/server/conftest.py:8: in <module>
    from voice_typer.server import event_bus, ipc_server  # noqa: E402
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 5. `tests.service.test_status_volume_cache`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/service/test_status_volume_cache.py:8`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/service/test_status_volume_cache.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/service/test_status_volume_cache.py:8: in <module>
    from voice_typer.server.service.status import StatusMixin
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 6. `tests.test_cloud_connection_ipc_wiring`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_cloud_connection_ipc_wiring.py:14`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_cloud_connection_ipc_wiring.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_cloud_connection_ipc_wiring.py:14: in <module>
    from voice_typer.server.ipc_server import IPCServer
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 7. `tests.test_cloud_provider_map_single_source`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_cloud_provider_map_single_source.py:11`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_cloud_provider_map_single_source.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_cloud_provider_map_single_source.py:11: in <module>
    from voice_typer.server.handlers import cloud_test_handlers
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 8. `tests.test_cloud_test_handlers_redirect`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_cloud_test_handlers_redirect.py:16`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_cloud_test_handlers_redirect.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_cloud_test_handlers_redirect.py:16: in <module>
    from voice_typer.server.handlers import cloud_test_handlers
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 9. `tests.test_dead_code_stays_removed`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_dead_code_stays_removed.py:18`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_dead_code_stays_removed.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_dead_code_stays_removed.py:18: in <module>
    from voice_typer.server.ipc_server import IPCServer
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 10. `tests.test_di_providers`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_di_providers.py:10`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_di_providers.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_di_providers.py:10: in <module>
    from voice_typer.server.ipc_server import IPCServer  # noqa: E402
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 11. `tests.test_download_model_dispatcher_structure`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_download_model_dispatcher_structure.py:9`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_download_model_dispatcher_structure.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_download_model_dispatcher_structure.py:9: in <module>
    from voice_typer.server.service._download_helpers import (
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 12. `tests.test_download_model_return_shape`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_download_model_return_shape.py:7`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_download_model_return_shape.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_download_model_return_shape.py:7: in <module>
    from voice_typer.server.service import LausuService
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 13. `tests.test_download_progress_events`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_download_progress_events.py:7`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_download_progress_events.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_download_progress_events.py:7: in <module>
    from voice_typer.server.service import LausuService
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 14. `tests.test_heartbeat`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_heartbeat.py:12`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_heartbeat.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_heartbeat.py:12: in <module>
    from voice_typer.server.ipc_server import (
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 15. `tests.test_heartbeat_force_exit`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_heartbeat_force_exit.py:11`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_heartbeat_force_exit.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_heartbeat_force_exit.py:11: in <module>
    from voice_typer.server.ipc_server import (
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 16. `tests.test_ipc_deadlock_regression`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_ipc_deadlock_regression.py:11`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_ipc_deadlock_regression.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_ipc_deadlock_regression.py:11: in <module>
    from voice_typer.server.ipc_server import IPCServer, _TCPLineIO
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 17. `tests.test_ipc_no_client_log_redaction`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_ipc_no_client_log_redaction.py:11`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_ipc_no_client_log_redaction.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_ipc_no_client_log_redaction.py:11: in <module>
    from voice_typer.server.ipc_server import IPCServer
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 18. `tests.test_ipc_rate_limiter_dual_window`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_ipc_rate_limiter_dual_window.py:5`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_ipc_rate_limiter_dual_window.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_ipc_rate_limiter_dual_window.py:5: in <module>
    from voice_typer.server.ipc_server import (
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 19. `tests.test_ipc_send_shutdown_allowlist`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_ipc_send_shutdown_allowlist.py:11`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_ipc_send_shutdown_allowlist.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_ipc_send_shutdown_allowlist.py:11: in <module>
    from voice_typer.server.ipc_server import _SHUTDOWN_ALLOWLIST, IPCServer
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 20. `tests.test_ipc_sender_select`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_ipc_sender_select.py:12`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_ipc_sender_select.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_ipc_sender_select.py:12: in <module>
    from voice_typer.server.ipc_server import IPCServer
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 21. `tests.test_ipc_server`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_ipc_server.py:34`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_ipc_server.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_ipc_server.py:34: in <module>
    from voice_typer.server.ipc_server import (
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 22. `tests.test_ipc_server_main_diagnostics`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_ipc_server_main_diagnostics.py:15`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_ipc_server_main_diagnostics.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_ipc_server_main_diagnostics.py:15: in <module>
    import voice_typer.server.ipc_server  # noqa: F401
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 23. `tests.test_ipc_shutdown_registry`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_ipc_shutdown_registry.py:11`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_ipc_shutdown_registry.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_ipc_shutdown_registry.py:11: in <module>
    from voice_typer.server.ipc_server import IPCServer
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 24. `tests.test_ipc_tray_click_validation`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_ipc_tray_click_validation.py:9`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_ipc_tray_click_validation.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_ipc_tray_click_validation.py:9: in <module>
    from voice_typer.server.ipc_server import IPCServer
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 25. `tests.test_keyboard_ownership_watchdog`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_keyboard_ownership_watchdog.py:6`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_keyboard_ownership_watchdog.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_keyboard_ownership_watchdog.py:6: in <module>
    from voice_typer.server.ipc_server import IPCServer
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 26. `tests.test_module_constant_hoist`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_module_constant_hoist.py:5`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_module_constant_hoist.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_module_constant_hoist.py:5: in <module>
    from voice_typer.server.ipc_server import (
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 27. `tests.test_pack_atomic_swap`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_pack_atomic_swap.py:11`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_pack_atomic_swap.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_pack_atomic_swap.py:11: in <module>
    from voice_typer.server.service import offline_pack
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 28. `tests.test_pack_checksum_background`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_pack_checksum_background.py:11`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_pack_checksum_background.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_pack_checksum_background.py:11: in <module>
    from voice_typer.server.service import offline_pack
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 29. `tests.test_pack_consent_gate`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_pack_consent_gate.py:7`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_pack_consent_gate.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_pack_consent_gate.py:7: in <module>
    from voice_typer.server.service import offline_pack
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 30. `tests.test_pack_corruption_recovery`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_pack_corruption_recovery.py:10`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_pack_corruption_recovery.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_pack_corruption_recovery.py:10: in <module>
    from voice_typer.server.service import offline_pack
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 31. `tests.test_pack_disk_full_during_download`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_pack_disk_full_during_download.py:9`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_pack_disk_full_during_download.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_pack_disk_full_during_download.py:9: in <module>
    from voice_typer.server.service import offline_pack
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 32. `tests.test_pack_disk_space_check`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_pack_disk_space_check.py:10`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_pack_disk_space_check.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_pack_disk_space_check.py:10: in <module>
    from voice_typer.server.service import offline_pack
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 33. `tests.test_pack_download_resume`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_pack_download_resume.py:9`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_pack_download_resume.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_pack_download_resume.py:9: in <module>
    from voice_typer.server.service import offline_pack
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 34. `tests.test_pack_dual_instance`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_pack_dual_instance.py:12`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_pack_dual_instance.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_pack_dual_instance.py:12: in <module>
    from voice_typer.server.service import offline_pack
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 35. `tests.test_pack_fallback_dir`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_pack_fallback_dir.py:9`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_pack_fallback_dir.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_pack_fallback_dir.py:9: in <module>
    from voice_typer.server.service import offline_pack
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 36. `tests.test_pack_github_rate_limit`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_pack_github_rate_limit.py:10`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_pack_github_rate_limit.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_pack_github_rate_limit.py:10: in <module>
    from voice_typer.server.service import offline_pack
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 37. `tests.test_pack_install`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_pack_install.py:11`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_pack_install.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_pack_install.py:11: in <module>
    from voice_typer.server.service import offline_pack
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 38. `tests.test_pack_manifest_builder`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_pack_manifest_builder.py:25`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_pack_manifest_builder.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_pack_manifest_builder.py:25: in <module>
    import build_pack_manifest as bpm  # noqa: E402
scripts/release/build_pack_manifest.py:34: in <module>
    from voice_typer.server.service.offline_pack import (  # noqa: E402
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 39. `tests.test_pack_manifest_url_fallback`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_pack_manifest_url_fallback.py:7`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_pack_manifest_url_fallback.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_pack_manifest_url_fallback.py:7: in <module>
    from voice_typer.server.service import update_check
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 40. `tests.test_pack_missing_on_launch`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_pack_missing_on_launch.py:13`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_pack_missing_on_launch.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_pack_missing_on_launch.py:13: in <module>
    from voice_typer.server.service import offline_pack, update_check
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 41. `tests.test_pack_proxy`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_pack_proxy.py:6`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_pack_proxy.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_pack_proxy.py:6: in <module>
    from voice_typer.server.service import offline_pack
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 42. `tests.test_pack_schema_caps`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_pack_schema_caps.py:10`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_pack_schema_caps.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_pack_schema_caps.py:10: in <module>
    from voice_typer.server.service import offline_pack
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 43. `tests.test_pack_signing`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_pack_signing.py:11`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_pack_signing.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_pack_signing.py:11: in <module>
    from voice_typer.server.service import offline_pack
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 44. `tests.test_pack_version_change_during_download`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_pack_version_change_during_download.py:9`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_pack_version_change_during_download.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_pack_version_change_during_download.py:9: in <module>
    from voice_typer.server.service import offline_pack
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 45. `tests.test_privacy_helpers`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_privacy_helpers.py:16`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_privacy_helpers.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_privacy_helpers.py:16: in <module>
    from voice_typer.server.service.privacy import PrivacyMixin
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 46. `tests.test_segmented_progress_tracker`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_segmented_progress_tracker.py:6`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_segmented_progress_tracker.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_segmented_progress_tracker.py:6: in <module>
    from voice_typer.server.service._download_helpers import (
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 47. `tests.test_sender_select_timeout`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_sender_select_timeout.py:11`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_sender_select_timeout.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_sender_select_timeout.py:11: in <module>
    from voice_typer.server.ipc_server import IPCServer
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 48. `tests.test_service_download_consent`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_service_download_consent.py:7`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_service_download_consent.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_service_download_consent.py:7: in <module>
    from voice_typer.server.service import LausuService
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 49. `tests.test_service_llm_consent`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_service_llm_consent.py:8`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_service_llm_consent.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_service_llm_consent.py:8: in <module>
    from voice_typer.server.service import LausuService
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 50. `tests.test_sidecar_ready_emitted`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_sidecar_ready_emitted.py:17`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_sidecar_ready_emitted.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_sidecar_ready_emitted.py:17: in <module>
    from voice_typer.server.ipc_server import IPCServer  # noqa: E402
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 51. `tests.test_sidecar_ws_ready_ordering`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_sidecar_ws_ready_ordering.py:13`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_sidecar_ws_ready_ordering.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_sidecar_ws_ready_ordering.py:13: in <module>
    from voice_typer.server.ipc_server import IPCServer  # noqa: E402
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 52. `tests.test_transport_write_raw`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_transport_write_raw.py:6`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_transport_write_raw.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_transport_write_raw.py:6: in <module>
    from voice_typer.server.ipc_server import _TCPLineIO
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 53. `tests.test_trusted_extra_hosts`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_trusted_extra_hosts.py:21`

```
ImportError: cannot import name 'IPCServer' from 'tests.server.conftest' (/Users/runner/work/voice-typer/voice-typer/tests/server/conftest.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_trusted_extra_hosts.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_trusted_extra_hosts.py:21: in <module>
    from tests.server.conftest import IPCServer, MockApp  # noqa: E402
E   ImportError: cannot import name 'IPCServer' from 'tests.server.conftest' (/Users/runner/work/voice-typer/voice-typer/tests/server/conftest.py)
```

### 54. `tests.test_update_check`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_update_check.py:14`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_update_check.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_update_check.py:14: in <module>
    from voice_typer.server.service import update_check
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 55. `tests.test_vocabulary_backend_duplicates`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_vocabulary_backend_duplicates.py:9`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_vocabulary_backend_duplicates.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_vocabulary_backend_duplicates.py:9: in <module>
    from voice_typer.server.service.vocabulary import (
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 56. `tests.test_vocabulary_delete_persistence`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/test_vocabulary_delete_persistence.py:9`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

collection failure
ImportError while importing test module '/Users/runner/work/voice-typer/voice-typer/tests/test_vocabulary_delete_persistence.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/test_vocabulary_delete_persistence.py:9: in <module>
    from voice_typer.server.service.vocabulary import VocabularyMixin
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 57. `tests.test_transcribe_offline_forward.test_pack_missing_returns_degraded_not_queued@ipc_layer_fixes`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `voice_typer/server/service/__init__.py:11`

```
ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

failed on setup with "ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)"
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

The above exception was the direct cause of the following exception:
tests/test_transcribe_offline_forward.py:21: in _isolated
    monkeypatch.setattr(
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:107: in derive_importpath
    target = resolve(module)
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:88: in resolve
    raise ImportError(f"import error in {used}: {ex}") from ex
E   ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 58. `tests.test_transcribe_offline_forward.test_malformed_payload_rejected_without_raise[payload0]@ipc_layer_fixes`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `voice_typer/server/service/__init__.py:11`

```
ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

failed on setup with "ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)"
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

The above exception was the direct cause of the following exception:
tests/test_transcribe_offline_forward.py:21: in _isolated
    monkeypatch.setattr(
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:107: in derive_importpath
    target = resolve(module)
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:88: in resolve
    raise ImportError(f"import error in {used}: {ex}") from ex
E   ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 59. `tests.test_transcribe_offline_forward.test_malformed_payload_rejected_without_raise[None]@ipc_layer_fixes`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `voice_typer/server/service/__init__.py:11`

```
ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

failed on setup with "ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)"
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

The above exception was the direct cause of the following exception:
tests/test_transcribe_offline_forward.py:21: in _isolated
    monkeypatch.setattr(
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:107: in derive_importpath
    target = resolve(module)
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:88: in resolve
    raise ImportError(f"import error in {used}: {ex}") from ex
E   ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 60. `tests.test_transcribe_offline_forward.test_malformed_payload_rejected_without_raise[x.wav]@ipc_layer_fixes`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `voice_typer/server/service/__init__.py:11`

```
ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

failed on setup with "ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)"
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

The above exception was the direct cause of the following exception:
tests/test_transcribe_offline_forward.py:21: in _isolated
    monkeypatch.setattr(
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:107: in derive_importpath
    target = resolve(module)
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:88: in resolve
    raise ImportError(f"import error in {used}: {ex}") from ex
E   ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 61. `tests.test_transcribe_offline_forward.test_malformed_payload_rejected_without_raise[payload3]@ipc_layer_fixes`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `voice_typer/server/service/__init__.py:11`

```
ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

failed on setup with "ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)"
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

The above exception was the direct cause of the following exception:
tests/test_transcribe_offline_forward.py:21: in _isolated
    monkeypatch.setattr(
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:107: in derive_importpath
    target = resolve(module)
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:88: in resolve
    raise ImportError(f"import error in {used}: {ex}") from ex
E   ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 62. `tests.test_transcribe_offline_forward.test_malformed_payload_rejected_without_raise[payload4]@ipc_layer_fixes`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `voice_typer/server/service/__init__.py:11`

```
ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

failed on setup with "ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)"
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

The above exception was the direct cause of the following exception:
tests/test_transcribe_offline_forward.py:21: in _isolated
    monkeypatch.setattr(
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:107: in derive_importpath
    target = resolve(module)
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:88: in resolve
    raise ImportError(f"import error in {used}: {ex}") from ex
E   ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 63. `tests.test_transcribe_offline_forward.test_malformed_payload_rejected_without_raise[payload5]@ipc_layer_fixes`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `voice_typer/server/service/__init__.py:11`

```
ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

failed on setup with "ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)"
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

The above exception was the direct cause of the following exception:
tests/test_transcribe_offline_forward.py:21: in _isolated
    monkeypatch.setattr(
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:107: in derive_importpath
    target = resolve(module)
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:88: in resolve
    raise ImportError(f"import error in {used}: {ex}") from ex
E   ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 64. `tests.test_transcribe_offline_forward.test_malformed_payload_rejected_without_raise[payload6]@ipc_layer_fixes`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `voice_typer/server/service/__init__.py:11`

```
ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

failed on setup with "ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)"
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

The above exception was the direct cause of the following exception:
tests/test_transcribe_offline_forward.py:21: in _isolated
    monkeypatch.setattr(
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:107: in derive_importpath
    target = resolve(module)
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:88: in resolve
    raise ImportError(f"import error in {used}: {ex}") from ex
E   ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 65. `tests.test_transcribe_offline_forward.test_malformed_payload_rejected_without_raise[payload7]@ipc_layer_fixes`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `voice_typer/server/service/__init__.py:11`

```
ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

failed on setup with "ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)"
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

The above exception was the direct cause of the following exception:
tests/test_transcribe_offline_forward.py:21: in _isolated
    monkeypatch.setattr(
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:107: in derive_importpath
    target = resolve(module)
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:88: in resolve
    raise ImportError(f"import error in {used}: {ex}") from ex
E   ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 66. `tests.test_transcribe_offline_forward.test_malformed_payload_rejected_without_raise[payload8]@ipc_layer_fixes`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `voice_typer/server/service/__init__.py:11`

```
ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

failed on setup with "ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)"
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

The above exception was the direct cause of the following exception:
tests/test_transcribe_offline_forward.py:21: in _isolated
    monkeypatch.setattr(
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:107: in derive_importpath
    target = resolve(module)
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:88: in resolve
    raise ImportError(f"import error in {used}: {ex}") from ex
E   ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 67. `tests.test_transcribe_offline_forward.test_malformed_payload_rejected_without_raise[payload9]@ipc_layer_fixes`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `voice_typer/server/service/__init__.py:11`

```
ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

failed on setup with "ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)"
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

The above exception was the direct cause of the following exception:
tests/test_transcribe_offline_forward.py:21: in _isolated
    monkeypatch.setattr(
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:107: in derive_importpath
    target = resolve(module)
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:88: in resolve
    raise ImportError(f"import error in {used}: {ex}") from ex
E   ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 68. `tests.test_transcribe_offline_forward.test_malformed_payload_rejected_without_raise[payload10]@ipc_layer_fixes`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `voice_typer/server/service/__init__.py:11`

```
ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

failed on setup with "ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)"
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

The above exception was the direct cause of the following exception:
tests/test_transcribe_offline_forward.py:21: in _isolated
    monkeypatch.setattr(
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:107: in derive_importpath
    target = resolve(module)
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:88: in resolve
    raise ImportError(f"import error in {used}: {ex}") from ex
E   ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 69. `tests.test_transcribe_offline_forward.test_malformed_payload_rejected_without_raise[payload11]@ipc_layer_fixes`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `voice_typer/server/service/__init__.py:11`

```
ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

failed on setup with "ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)"
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

The above exception was the direct cause of the following exception:
tests/test_transcribe_offline_forward.py:21: in _isolated
    monkeypatch.setattr(
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:107: in derive_importpath
    target = resolve(module)
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:88: in resolve
    raise ImportError(f"import error in {used}: {ex}") from ex
E   ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 70. `tests.test_transcribe_offline_forward.test_malformed_payload_rejected_without_raise[payload12]@ipc_layer_fixes`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `voice_typer/server/service/__init__.py:11`

```
ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

failed on setup with "ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)"
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

The above exception was the direct cause of the following exception:
tests/test_transcribe_offline_forward.py:21: in _isolated
    monkeypatch.setattr(
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:107: in derive_importpath
    target = resolve(module)
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:88: in resolve
    raise ImportError(f"import error in {used}: {ex}") from ex
E   ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 71. `tests.test_transcribe_offline_forward.test_forward_when_worker_ready@ipc_layer_fixes`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `voice_typer/server/service/__init__.py:11`

```
ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

failed on setup with "ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)"
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

The above exception was the direct cause of the following exception:
tests/test_transcribe_offline_forward.py:21: in _isolated
    monkeypatch.setattr(
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:107: in derive_importpath
    target = resolve(module)
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:88: in resolve
    raise ImportError(f"import error in {used}: {ex}") from ex
E   ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 72. `tests.test_transcribe_offline_forward.test_queue_when_worker_not_ready_then_drain@ipc_layer_fixes`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `voice_typer/server/service/__init__.py:11`

```
ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

failed on setup with "ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)"
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

The above exception was the direct cause of the following exception:
tests/test_transcribe_offline_forward.py:21: in _isolated
    monkeypatch.setattr(
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:107: in derive_importpath
    target = resolve(module)
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:88: in resolve
    raise ImportError(f"import error in {used}: {ex}") from ex
E   ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 73. `tests.test_transcribe_offline_forward.test_ready_false_queues_without_send@ipc_layer_fixes`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `voice_typer/server/service/__init__.py:11`

```
ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

failed on setup with "ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)"
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

The above exception was the direct cause of the following exception:
tests/test_transcribe_offline_forward.py:21: in _isolated
    monkeypatch.setattr(
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:107: in derive_importpath
    target = resolve(module)
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:88: in resolve
    raise ImportError(f"import error in {used}: {ex}") from ex
E   ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 74. `tests.test_transcribe_offline_forward.test_send_exception_queues_never_raises@ipc_layer_fixes`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `voice_typer/server/service/__init__.py:11`

```
ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

failed on setup with "ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)"
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

The above exception was the direct cause of the following exception:
tests/test_transcribe_offline_forward.py:21: in _isolated
    monkeypatch.setattr(
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:107: in derive_importpath
    target = resolve(module)
/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/monkeypatch.py:88: in resolve
    raise ImportError(f"import error in {used}: {ex}") from ex
E   ImportError: import error in voice_typer.server.service: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 75. `tests.app.test_lifecycle.TestMainWrapsIpcMain.test_main_logs_and_exits_when_ipc_main_raises`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/app/test_lifecycle.py:1282`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
tests/app/test_lifecycle.py:1282: in test_main_logs_and_exits_when_ipc_main_raises
    import voice_typer.server.ipc_server as ipc_server_module
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 76. `tests.app.test_lifecycle.TestMainWrapsIpcMain.test_main_does_not_swallow_system_exit`

- Legs: macos-14-3.10, ubuntu-22.04-3.10
- Location: `tests/app/test_lifecycle.py:1319`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
tests/app/test_lifecycle.py:1319: in test_main_does_not_swallow_system_exit
    import voice_typer.server.ipc_server as ipc_server_module
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 77. `tests.app.test_lifecycle.TestMainWrapsIpcMain.test_main_logs_warning_when_faulthandler_enable_raises`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `tests/app/test_lifecycle.py:1351`

```
ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)

ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
tests/app/test_lifecycle.py:1351: in test_main_logs_warning_when_faulthandler_enable_raises
    import voice_typer.server.ipc_server as ipc_server_module
voice_typer/server/ipc_server.py:136: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin  # noqa: E402
voice_typer/server/handlers/__init__.py:27: in <module>
    from voice_typer.server.handlers.vocabulary_handlers import VocabularyHandlersMixin
voice_typer/server/handlers/vocabulary_handlers.py:12: in <module>
    from voice_typer.server.service.vocabulary import VocabularyDuplicateError
voice_typer/server/service/__init__.py:11: in <module>
    from voice_typer.server.service.model import _MODEL_STATUS_CACHE_TTL_S, ModelMixin
voice_typer/server/service/model/__init__.py:4: in <module>
    from .mixin import ModelMixin
voice_typer/server/service/model/mixin.py:7: in <module>
    from ._downloads import DownloadsMixin
voice_typer/server/service/model/_downloads.py:12: in <module>
    from voice_typer.server.service._download_helpers import DownloadOutcome
voice_typer/server/service/_download_helpers.py:9: in <module>
    from typing import NotRequired, TypedDict
E   ImportError: cannot import name 'NotRequired' from 'typing' (/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/typing.py)
```

### 78. `pytest.internal`

- Legs: macos-14-3.10, ubuntu-22.04-3.10, windows-2022-3.10
- Location: `(pytest internal error, no test location)`

```
internal error

internal error
def worker_internal_error(
        self, node: WorkerController, formatted_error: str
    ) -> None:
        """
        pytest_internalerror() was called on the worker.
    
        pytest_internalerror() arguments are an excinfo and an excrepr, which can't
        be serialized, so we go with a poor man's solution of raising an exception
        here ourselves using the formatted message.
        """
        self._active_nodes.remove(node)
        try:
>           assert False, formatted_error
E           AssertionError: Traceback (most recent call last):
E               File "/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/main.py", line 330, in wrap_session
E                 session.exitstatus = doit(config, session) or 0
E               File "/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/main.py", line 384, in _main
E                 config.hook.pytest_runtestloop(session=session)
E               File "/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/pluggy/_hooks.py", line 512, in __call__
E                 return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
E               File "/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/pluggy/_manager.py", line 120, in _hookexec
E                 return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
E               File "/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/pluggy/_callers.py", line 167, in _multicall
E                 raise exception
E               File "/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/pluggy/_callers.py", line 139, in _multicall
E                 teardown.throw(exception)
E               File "/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/logging.py", line 816, in pytest_runtestloop
E                 return (yield)  # Run all the tests.
E               File "/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/pluggy/_callers.py", line 139, in _multicall
E                 teardown.throw(exception)
E               File "/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/_pytest/terminal.py", line 708, in pytest_runtestloop
E                 result = yield
E               File "/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/pluggy/_callers.py", line 139, in _multicall
E                 teardown.throw(exception)
E               File "/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/pytest_cov/plugin.py", line 348, in pytest_runtestloop
E                 result = yield
E               File "/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/pluggy/_callers.py", line 121, in _multicall
```

### 79. `tests.tauri.mig17.test_faster_whisper_linux.test_build_script_pre_nuitka_check_validates_ct2_backend_importable@faster_whisper_linux`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/mig17/test_faster_whisper_linux.py:49`

```
assert '"$SITE/faster_whisper"' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_BIN"\n\n# ─── Quick smoke (help text only; no display server required) ───────────────\n# ADR-0020 §4.5 Phase 0 gate: verify --help works (proves the frozen\n# interpreter boots). C7: the slim sidecar must NOT load faster_whisper /\n# ctranslate2 at all — ASR lives in the pack worker, so the old "prove the\n# model loads inside Nuitka" smoke is retired with the includes that fed\n# it. Exclusion is pinned statically by tests/test_nuitka_asr_exclusions.py\n# (flag text in all four invocations) and enforced by the 185 MB size gate.\necho "[build_sidecar_linux] smoke: $OUTPUT_BIN --help"\nif [[ "$CROSS_BUILD" == "true" ]]; then\n    # Use qemu explicitly for the help check (binfmt_misc may not be active).\n    qemu-aarch64-static "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (cross-build --help skipped, verify on aarch64 host)"\nelse\n    "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (—help returned non-zero; check $BUILD_LOG)"\nfi\n\necho "[build_sidecar_linux] DONE: $OUTPUT_BIN"\n'

AssertionError: build script must verify $SITE/faster_whisper exists before invoking Nuitka (the cross-platform CT2 backend importability gate)
assert '"$SITE/faster_whisper"' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_BIN"\n\n# ─── Quick smoke (help text only; no d
… (truncated)
```

### 80. `tests.tauri.mig17.test_faster_whisper_linux.test_build_script_includes_faster_whisper_and_ctranslate2_packages@faster_whisper_linux`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/mig17/test_faster_whisper_linux.py:83`

```
assert '--include-package=faster_whisper' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_BIN"\n\n# ─── Quick smoke (help text only; no display server required) ───────────────\n# ADR-0020 §4.5 Phase 0 gate: verify --help works (proves the frozen\n# interpreter boots). C7: the slim sidecar must NOT load faster_whisper /\n# ctranslate2 at all — ASR lives in the pack worker, so the old "prove the\n# model loads inside Nuitka" smoke is retired with the includes that fed\n# it. Exclusion is pinned statically by tests/test_nuitka_asr_exclusions.py\n# (flag text in all four invocations) and enforced by the 185 MB size gate.\necho "[build_sidecar_linux] smoke: $OUTPUT_BIN --help"\nif [[ "$CROSS_BUILD" == "true" ]]; then\n    # Use qemu explicitly for the help check (binfmt_misc may not be active).\n    qemu-aarch64-static "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (cross-build --help skipped, verify on aarch64 host)"\nelse\n    "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (—help returned non-zero; check $BUILD_LOG)"\nfi\n\necho "[build_sidecar_linux] DONE: $OUTPUT_BIN"\n'

AssertionError: Nuitka must include the faster_whisper Python package
assert '--include-package=faster_whisper' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_BIN"\n\n# ─── Quick smoke (help text only; no display server required) ───────────────\n# ADR-0020 §4
… (truncated)
```

### 81. `tests.tauri.mig17.test_faster_whisper_linux.test_build_script_includes_ct2_native_libs_singular_layout@faster_whisper_linux`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/mig17/test_faster_whisper_linux.py:91`

```
assert ('ctranslate2/lib' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_BIN"\n\n# ─── Quick smoke (help text only; no display server required) ───────────────\n# ADR-0020 §4.5 Phase 0 gate: verify --help works (proves the frozen\n# interpreter boots). C7: the slim sidecar must NOT load faster_whisper /\n# ctranslate2 at all — ASR lives in the pack worker, so the old "prove the\n# model loads inside Nuitka" smoke is retired with the includes that fed\n# it. Exclusion is pinned statically by tests/test_nuitka_asr_exclusions.py\n# (flag text in all four invocations) and enforced by the 185 MB size gate.\necho "[build_sidecar_linux] smoke: $OUTPUT_BIN --help"\nif [[ "$CROSS_BUILD" == "true" ]]; then\n    # Use qemu explicitly for the help check (binfmt_misc may not be active).\n    qemu-aarch64-static "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (cross-build --help skipped, verify on aarch64 host)"\nelse\n    "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (—help returned non-zero; check $BUILD_LOG)"\nfi\n\necho "[build_sidecar_linux] DONE: $OUTPUT_BIN"\n')

AssertionError: build script must include --include-data-dir for ctranslate2/lib (the directory holding libctranslate2.so + libiomp5.so/libgomp.so)
assert ('ctranslate2/lib' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_BIN"\n\n# ─── Quick smoke (help text only; no display
… (truncated)
```

### 82. `tests.tauri.mig17.test_faster_whisper_linux.test_build_script_includes_ct2_libs_plural_layout_guarded@faster_whisper_linux`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/mig17/test_faster_whisper_linux.py:105`

```
assert 'ctranslate2/libs' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_BIN"\n\n# ─── Quick smoke (help text only; no display server required) ───────────────\n# ADR-0020 §4.5 Phase 0 gate: verify --help works (proves the frozen\n# interpreter boots). C7: the slim sidecar must NOT load faster_whisper /\n# ctranslate2 at all — ASR lives in the pack worker, so the old "prove the\n# model loads inside Nuitka" smoke is retired with the includes that fed\n# it. Exclusion is pinned statically by tests/test_nuitka_asr_exclusions.py\n# (flag text in all four invocations) and enforced by the 185 MB size gate.\necho "[build_sidecar_linux] smoke: $OUTPUT_BIN --help"\nif [[ "$CROSS_BUILD" == "true" ]]; then\n    # Use qemu explicitly for the help check (binfmt_misc may not be active).\n    qemu-aarch64-static "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (cross-build --help skipped, verify on aarch64 host)"\nelse\n    "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (—help returned non-zero; check $BUILD_LOG)"\nfi\n\necho "[build_sidecar_linux] DONE: $OUTPUT_BIN"\n'

AssertionError: build script must reference the plural ctranslate2/libs path (some wheel variants ship .so files there instead of ctranslate2/lib)
assert 'ctranslate2/libs' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_BIN"\n\n# ─── Quick smoke (help text only; no display se
… (truncated)
```

### 83. `tests.tauri.mig17.test_faster_whisper_linux.test_build_script_bundles_openmp_runtime_libs@faster_whisper_linux`

- Legs: ubuntu-22.04-3.10, ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/mig17/test_faster_whisper_linux.py:351`

```
assert ('libiomp5.so' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_BIN"\n\n# ─── Quick smoke (help text only; no display server required) ───────────────\n# ADR-0020 §4.5 Phase 0 gate: verify --help works (proves the frozen\n# interpreter boots). C7: the slim sidecar must NOT load faster_whisper /\n# ctranslate2 at all — ASR lives in the pack worker, so the old "prove the\n# model loads inside Nuitka" smoke is retired with the includes that fed\n# it. Exclusion is pinned statically by tests/test_nuitka_asr_exclusions.py\n# (flag text in all four invocations) and enforced by the 185 MB size gate.\necho "[build_sidecar_linux] smoke: $OUTPUT_BIN --help"\nif [[ "$CROSS_BUILD" == "true" ]]; then\n    # Use qemu explicitly for the help check (binfmt_misc may not be active).\n    qemu-aarch64-static "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (cross-build --help skipped, verify on aarch64 host)"\nelse\n    "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (—help returned non-zero; check $BUILD_LOG)"\nfi\n\necho "[build_sidecar_linux] DONE: $OUTPUT_BIN"\n')

AssertionError: build script header must document that the ctranslate2/{lib,libs} include ships libiomp5.so (Intel OpenMP, x86_64) + libgomp.so (GNU OpenMP, aarch64), these are the OpenMP runtime .so files CT2's CPU inference path requires
assert ('libiomp5.so' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verifi
… (truncated)
```

### 84. `tests.model_download.test_segmented_download_helpers.test_resolve_within_rejects_escapes[C:/windows/system32/x.dll]`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/model_download/test_segmented_download_helpers.py:139`

```
Failed: DID NOT RAISE SegmentedDownloadError

Failed: DID NOT RAISE SegmentedDownloadError
tests/model_download/test_segmented_download_helpers.py:139: in test_resolve_within_rejects_escapes
    with pytest.raises(seg.SegmentedDownloadError):
E   Failed: DID NOT RAISE SegmentedDownloadError
```

### 85. `tests.model_download.test_segmented_download_helpers.test_install_blob_places_nested_snapshot_file`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/model_download/test_segmented_download_helpers.py:175`

```
+    where resolve = ((((PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_install_blob_places_neste0/hf-cache') / 'snapshots') / 'abc123') / 'model') / 'weights.bin').resolve

AssertionError: assert PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_install_blob_places_neste0/hf-cache/snapshots/abc123/model/weights.bin') == PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_install_blob_places_neste0/hf-cache/snapshots/blobs/cafebabe')
 +  where PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_install_blob_places_neste0/hf-cache/snapshots/blobs/cafebabe') = resolve()
 +    where resolve = ((((PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_install_blob_places_neste0/hf-cache') / 'snapshots') / 'abc123') / 'model') / 'weights.bin').resolve
tests/model_download/test_segmented_download_helpers.py:175: in test_install_blob_places_nested_snapshot_file
    assert placed == (cache / "snapshots" / "abc123" / "model" / "weights.bin").resolve()
E   AssertionError: assert PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_install_blob_places_neste0/hf-cache/snapshots/abc123/model/weights.bin') == PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_install_blob_places_neste0/hf-cache/snapshots/blobs/cafebabe')
E    +  where PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_install_blob_places_neste0/hf-cache/snapshots/blobs/cafebabe') = resolve()
E    +    where resolve = ((((PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_install_blob_places_neste0/hf-cache') / 'snapshots') / 'abc123') / 'model') / 'weights.bin').resolve
```

### 86. `tests.tauri.mig17.test_externalbin_spawn_linux.test_sidecar_ws_binds_loopback_ephemeral_port`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/mig17/test_externalbin_spawn_linux.py:487`

```
+    where <function search at 0x7fd402e762a0> = re.search

AssertionError: sidecar_ws.py must define _LOOPBACK_HOST = '127.0.0.1' (hard loopback, no 0.0.0.0/:: bind, ADR-0020 §1)
assert None
 +  where None = <function search at 0x7fd402e762a0>('_LOOPBACK_HOST\\s*=\\s*"127\\.0\\.0\\.1"', '"""Tauri sidecar WebSocket transport, server side.\n\nADR-0020 §1 + §2: this module turns the existing :class:`IPCServer`\ndispatch layer into a localhost WebSocket server so the Tauri Rust\nhost can connect to it as a WS client.\n\nArchitecture\n------------\n::\n\n    Tauri host (Rust)\n        │  spawns sidecar via externalBin\n        │  passes VOICE_TYPER_IPC_TOKEN env\n        ▼\n    sidecar_main.py (this module\'s run() entrypoint)\n        │  binds websockets.serve on 127.0.0.1:0\n        │  OS assigns an ephemeral port\n        │  writes ONE structured line to stdout:\n        │     {"event":"server_started","port":<n>}\n        ▼\n    Rust reads stdout, parses the JSON, opens a WS client to\n    ws://127.0.0.1:<n>, sends the bearer-token auth frame, then forwards\n    invoke(\'dispatch\', {cmd, data}) envelopes over the WS.\n\n    Auth model (ADR-0020 §3)\n    -----------------------------------------------\n    The handshake is a **one-shot bearer-token** check, NOT an HMAC\n    scheme. The Rust host generates a 256-bit bearer token via\n    ``secrets.token_bytes(32)`` and the Python sidecar compares it with\n    :func:`hmac.compare_digest` (constant-time *comparison ...d`` module-object read at call\n  ``PROTOCOL_VERSION``.\n"""\n\nfrom __future__ import annotations\n\nimport contextlib\nimport json\nimport sys\n\n\ndef _force_line_buffered_stdout() -> None:\n    """so this is always available, but the guard is defensive)."""\n    try:\n        sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined, union-attr]\n    except (AttributeError, ValueError):\n        # Fallback: reopen stdout with buffering=1 (line-buffered).\n        with contextlib.suppress(Exception):\n            sys.stdout = open(  # noqa: SIM115 - intentional reopen\n                sys.stdout.fileno(),\n                "w",\n                buffering=1,\n                encoding="utf-8",\n                closefd=False,\n            )\n\n\ndef _emit_server_started(port: int, protocol: int | None = None) -> None:\n    """Write the one structured stdout line the host is parsing for."""\n    if protocol is not None:\n        print(\n            json.dumps({"event": "server_started", "port": int(port), "protocol": int(protocol)}),\n            flush=True,\n        )\n    else:\n        print(json.dumps({"event": "server_started", "port": int(port)}), flush=True)\n')
 +    where <function search at 0x7fd402e762a0> = re.search
tests/tauri/mig17/test_externalbin_spawn_linux.py:487: in test_sidecar_ws_binds_loopback_ephemeral_port
    assert re.search(
E   AssertionError: sidecar_ws.py must define _LOOPBACK_HOST = '127.0.0.1' (hard loopback, no 0.0.0.0/:: bind, ADR-0020 §1)
E   assert None
E    +  where None = <function search at 0x7fd402e762a0>('_LOOPBACK_HOST\\s*=\\s*"127\\.0\\.0\\.1"', '"""Tauri sidecar WebSocket transport, server side.\n\nADR-0020 §1 + §2: this module turns the existing :class:`IPCServer`\ndispatch layer into a localhost WebSocket server so the Tauri Rust\nhost can connect to it as a WS client.\n\nArchitecture\n------------\n::\n\n    Tauri host (Rust)\n        │  spawns sidecar via externalBin\n        │  passes VOICE_TYPER_IPC_TOKEN env\n        ▼\n    sidecar_main.py (this module\'s run() entrypoint)\n        │  binds websockets.serve on 127.0.0.1:0\n        │  OS assigns an ephemeral port\n        │  writes ONE structured line to stdout:\n        │     {"event":"server_started","port":<n>}\n        ▼\n    Rust reads stdout, parses the JSON, opens a WS client to\n    ws://127.0.0.1:<n>, sends the bearer-token auth frame, then forwards\n    invoke(\'dispatch\', {cmd, data}) envelopes over the WS.\n\n    Auth model (ADR-0020 §3)\n
… (truncated)
```

### 87. `tests.tauri.mig17.test_nuitka_linux_build.test_sidecar_script_contains_expected_nuitka_flag[--include-package=faster_whisper]`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/mig17/test_nuitka_linux_build.py:124`

```
assert '--include-package=faster_whisper' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_BIN"\n\n# ─── Quick smoke (help text only; no display server required) ───────────────\n# ADR-0020 §4.5 Phase 0 gate: verify --help works (proves the frozen\n# interpreter boots). C7: the slim sidecar must NOT load faster_whisper /\n# ctranslate2 at all — ASR lives in the pack worker, so the old "prove the\n# model loads inside Nuitka" smoke is retired with the includes that fed\n# it. Exclusion is pinned statically by tests/test_nuitka_asr_exclusions.py\n# (flag text in all four invocations) and enforced by the 185 MB size gate.\necho "[build_sidecar_linux] smoke: $OUTPUT_BIN --help"\nif [[ "$CROSS_BUILD" == "true" ]]; then\n    # Use qemu explicitly for the help check (binfmt_misc may not be active).\n    qemu-aarch64-static "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (cross-build --help skipped, verify on aarch64 host)"\nelse\n    "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (—help returned non-zero; check $BUILD_LOG)"\nfi\n\necho "[build_sidecar_linux] DONE: $OUTPUT_BIN"\n'

AssertionError: build_sidecar_linux.sh is missing required Nuitka flag `--include-package=faster_whisper`. ADR-0020 §4.4 mandates this flag for the Linux sidecar freeze.
assert '--include-package=faster_whisper' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_B
… (truncated)
```

### 88. `tests.tauri.mig17.test_nuitka_linux_build.test_sidecar_script_contains_expected_nuitka_flag[--include-package=ctranslate2]`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/mig17/test_nuitka_linux_build.py:124`

```
assert '--include-package=ctranslate2' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_BIN"\n\n# ─── Quick smoke (help text only; no display server required) ───────────────\n# ADR-0020 §4.5 Phase 0 gate: verify --help works (proves the frozen\n# interpreter boots). C7: the slim sidecar must NOT load faster_whisper /\n# ctranslate2 at all — ASR lives in the pack worker, so the old "prove the\n# model loads inside Nuitka" smoke is retired with the includes that fed\n# it. Exclusion is pinned statically by tests/test_nuitka_asr_exclusions.py\n# (flag text in all four invocations) and enforced by the 185 MB size gate.\necho "[build_sidecar_linux] smoke: $OUTPUT_BIN --help"\nif [[ "$CROSS_BUILD" == "true" ]]; then\n    # Use qemu explicitly for the help check (binfmt_misc may not be active).\n    qemu-aarch64-static "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (cross-build --help skipped, verify on aarch64 host)"\nelse\n    "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (—help returned non-zero; check $BUILD_LOG)"\nfi\n\necho "[build_sidecar_linux] DONE: $OUTPUT_BIN"\n'

AssertionError: build_sidecar_linux.sh is missing required Nuitka flag `--include-package=ctranslate2`. ADR-0020 §4.4 mandates this flag for the Linux sidecar freeze.
assert '--include-package=ctranslate2' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_BIN"\n\n#
… (truncated)
```

### 89. `tests.tauri.mig17.test_nuitka_linux_build.test_sidecar_script_includes_ctranslate2_data_dir`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/mig17/test_nuitka_linux_build.py:132`

```
assert '--include-data-dir' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_BIN"\n\n# ─── Quick smoke (help text only; no display server required) ───────────────\n# ADR-0020 §4.5 Phase 0 gate: verify --help works (proves the frozen\n# interpreter boots). C7: the slim sidecar must NOT load faster_whisper /\n# ctranslate2 at all — ASR lives in the pack worker, so the old "prove the\n# model loads inside Nuitka" smoke is retired with the includes that fed\n# it. Exclusion is pinned statically by tests/test_nuitka_asr_exclusions.py\n# (flag text in all four invocations) and enforced by the 185 MB size gate.\necho "[build_sidecar_linux] smoke: $OUTPUT_BIN --help"\nif [[ "$CROSS_BUILD" == "true" ]]; then\n    # Use qemu explicitly for the help check (binfmt_misc may not be active).\n    qemu-aarch64-static "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (cross-build --help skipped, verify on aarch64 host)"\nelse\n    "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (—help returned non-zero; check $BUILD_LOG)"\nfi\n\necho "[build_sidecar_linux] DONE: $OUTPUT_BIN"\n'

assert '--include-data-dir' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_BIN"\n\n# ─── Quick smoke (help text only; no display server required) ───────────────\n# ADR-0020 §4.5 Phase 0 gate: verify --help works (proves the frozen\n# interpreter boots). C7: the slim sideca
… (truncated)
```

### 90. `tests.tauri.mig17.test_nuitka_linux_build.test_sidecar_script_uses_nuitka_args_array`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/mig17/test_nuitka_linux_build.py:174`

```
assert 'NUITKA_ARGS+=' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_BIN"\n\n# ─── Quick smoke (help text only; no display server required) ───────────────\n# ADR-0020 §4.5 Phase 0 gate: verify --help works (proves the frozen\n# interpreter boots). C7: the slim sidecar must NOT load faster_whisper /\n# ctranslate2 at all — ASR lives in the pack worker, so the old "prove the\n# model loads inside Nuitka" smoke is retired with the includes that fed\n# it. Exclusion is pinned statically by tests/test_nuitka_asr_exclusions.py\n# (flag text in all four invocations) and enforced by the 185 MB size gate.\necho "[build_sidecar_linux] smoke: $OUTPUT_BIN --help"\nif [[ "$CROSS_BUILD" == "true" ]]; then\n    # Use qemu explicitly for the help check (binfmt_misc may not be active).\n    qemu-aarch64-static "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (cross-build --help skipped, verify on aarch64 host)"\nelse\n    "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (—help returned non-zero; check $BUILD_LOG)"\nfi\n\necho "[build_sidecar_linux] DONE: $OUTPUT_BIN"\n'

AssertionError: build_sidecar_linux.sh must use `NUITKA_ARGS+=(...)` to conditionally append the XPLAT-3 libs/ flag inside the guard block.
assert 'NUITKA_ARGS+=' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_BIN"\n\n# ─── Quick smoke (help text only; no display server required
… (truncated)
```

### 91. `tests.tauri.mig17.test_nuitka_linux_build.test_sidecar_script_has_xplat3_ctranslate2_libs_guard`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/mig17/test_nuitka_linux_build.py:156`

```
assert 'CT2_LIBS_DIR=' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_BIN"\n\n# ─── Quick smoke (help text only; no display server required) ───────────────\n# ADR-0020 §4.5 Phase 0 gate: verify --help works (proves the frozen\n# interpreter boots). C7: the slim sidecar must NOT load faster_whisper /\n# ctranslate2 at all — ASR lives in the pack worker, so the old "prove the\n# model loads inside Nuitka" smoke is retired with the includes that fed\n# it. Exclusion is pinned statically by tests/test_nuitka_asr_exclusions.py\n# (flag text in all four invocations) and enforced by the 185 MB size gate.\necho "[build_sidecar_linux] smoke: $OUTPUT_BIN --help"\nif [[ "$CROSS_BUILD" == "true" ]]; then\n    # Use qemu explicitly for the help check (binfmt_misc may not be active).\n    qemu-aarch64-static "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (cross-build --help skipped, verify on aarch64 host)"\nelse\n    "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (—help returned non-zero; check $BUILD_LOG)"\nfi\n\necho "[build_sidecar_linux] DONE: $OUTPUT_BIN"\n'

AssertionError: build_sidecar_linux.sh must define CT2_LIBS_DIR (the ctranslate2/libs plural path).
assert 'CT2_LIBS_DIR=' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_BIN"\n\n# ─── Quick smoke (help text only; no display server required) ───────────────\n# ADR-0020 §4.5 Phase
… (truncated)
```

### 92. `tests.tauri.mig17.test_nuitka_linux_build.test_sidecar_script_documents_xplat3_guard_rationale`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/mig17/test_nuitka_linux_build.py:183`

```
assert 'ctranslate2/libs' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_BIN"\n\n# ─── Quick smoke (help text only; no display server required) ───────────────\n# ADR-0020 §4.5 Phase 0 gate: verify --help works (proves the frozen\n# interpreter boots). C7: the slim sidecar must NOT load faster_whisper /\n# ctranslate2 at all — ASR lives in the pack worker, so the old "prove the\n# model loads inside Nuitka" smoke is retired with the includes that fed\n# it. Exclusion is pinned statically by tests/test_nuitka_asr_exclusions.py\n# (flag text in all four invocations) and enforced by the 185 MB size gate.\necho "[build_sidecar_linux] smoke: $OUTPUT_BIN --help"\nif [[ "$CROSS_BUILD" == "true" ]]; then\n    # Use qemu explicitly for the help check (binfmt_misc may not be active).\n    qemu-aarch64-static "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (cross-build --help skipped, verify on aarch64 host)"\nelse\n    "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (—help returned non-zero; check $BUILD_LOG)"\nfi\n\necho "[build_sidecar_linux] DONE: $OUTPUT_BIN"\n'

assert 'ctranslate2/libs' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_BIN"\n\n# ─── Quick smoke (help text only; no display server required) ───────────────\n# ADR-0020 §4.5 Phase 0 gate: verify --help works (proves the frozen\n# interpreter boots). C7: the slim sidecar mu
… (truncated)
```

### 93. `tests.tauri.mig17.test_nuitka_linux_build.test_macos_sibling_has_xplat3_ctranslate2_libs_guard`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/mig17/test_nuitka_linux_build.py:383`

```
assert 'CT2_LIBS_DIR' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not invoke codesign.\n    NUITKA_ARGS+=(--macos-sign-identity="$MAC_SIGNING_IDENTITY")\nfi\n"$PY" -m nuitka "${NUITKA_ARGS[@]}"\n\n# ─── Verify ──────────────────────────────────────────────────────────────────\nif [[ ! -f "$OUTPUT_PATH" ]]; then\n    echo "ERROR: $OUTPUT_PATH not built" >&2\n    exit 1\nfi\nchmod +x "$OUTPUT_PATH"\nSIZE_MB=$(du -m "$OUTPUT_PATH" | cut -f1)\necho "[build_sidecar_macos] OK: $OUTPUT_PATH (${SIZE_MB} MB)"\n\n# S5-CR-56: ad-hoc codesign fallback when no Developer ID identity is set.\n# Mirrors `build_native_listener_macos.sh`. When MAC_SIGNING_IDENTITY is set,\n# Nuitka already signed the binary at build time via --macos-sign-identity\n# (see above), skip the ad-hoc fallback in that case.\nif [[ -z "${MAC_SIGNING_IDENTITY:-}" ]] && command -v codesign >/dev/null; then\n    echo "[build_sidecar_macos] Ad-hoc codesign (parent .app will re-sign --deep)..."\n    codesign --force --sign - "$OUTPUT_PATH" || true\nfi\n\necho "[build_sidecar_macos] NEXT: codesign + notarize (see docs/migration/signing-guide.md §13.2)."\n'

assert 'CT2_LIBS_DIR' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)\n# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-apple-darwin\n#   src-tauri/bin/python-sidecar-aarch64-apple-darwin\n#\n# This script is designed to run on a macOS host. For x86_64 on an Apple\n# Silicon host, the script relies on Rosetta 2 being installed (the CI\n# workflow installs it explicitly).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)\n#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)\n#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain\n#\n# ADR-0020 §4.3 mandates:\n#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir\n#     copies below were deleted in the same ch...entity to Nuitka so it\n    # signs the binary at build time. `--macos-signed-app-name` only sets\n    # the bundle\'s signed name; it does not invoke codesign.\n    NUITKA_ARGS+=(--macos-sign-identity="$MAC_SIGNING_IDENTITY")\nfi\n"$PY" -m nuitka "${NUITKA_ARGS[@]}"\n\n# ─── Verify ───────────────────────────────────────────────────────────────
… (truncated)
```

### 94. `tests.tauri.mig17.test_nuitka_linux_build.test_windows_sibling_known_gap_no_xplat3_ctranslate2_libs_guard`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/mig17/test_nuitka_linux_build.py:395`

```
assert 'CT2_LIB_DIR=' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (Windows x86_64 + aarch64)\n# ADR-0020 §4.2. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>.exe, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-pc-windows-msvc.exe\n#   src-tauri/bin/python-sidecar-aarch64-pc-windows-msvc.exe\n#\n# This script is designed to run on a Windows host under Git Bash / MSYS2 /\n# WSL. From native PowerShell, use the inline Nuitka command in\n# .github/workflows/tauri-windows-build.yml instead (it\'s the same command,\n# just expressed in PowerShell syntax).\n#\n# Usage (Git Bash on Windows):\n#   bash scripts/build/build_sidecar_windows.sh x86_64      # default\n#   bash scripts/build/build_sidecar_windows.sh aarch64     # Windows-on-ARM\n#   bash scripts/build/build_sidecar_windows.sh --check     # verify toolchain\n#\n# ADR-0020 §4.2 mandates:\n#   - python-build-standalone cpython-3.12.x\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR liv...isper\n    --nofollow-import-to=ctranslate2\n    --nofollow-import-to=torch\n    --include-package=voice_typer\n    --include-package=websockets\n    # ADR-0023 packaging: media ingest lazily imports yt_dlp / yt_dlp_ejs /\n    # av (decoder.py, downloader.py, subtitles.py, mini_update.py).\n    # av wheels bundle FFmpeg DLLs.\n    --include-package=yt_dlp\n    --include-package=yt_dlp_ejs\n    --include-package=av\n    --include-package-data=yt_dlp\n    --include-package-data=voice_typer.server\n    --windows-disable-console\n    --onefile-tempdir-spec="{CACHE_DIR}/lausu/onefile-tmp"\n    --output-filename="$OUTPUT_NAME"\n    --output-dir="$SIDECAR_DIR"\n    "$PROJECT_ROOT/voice_typer/server/ipc_server.py"\n)\necho "[build_sidecar_windows] Running Nuitka..."\n"$PY" -m nuitka "${NUITKA_ARGS[@]}"\n\n# ─── Verify ──────────────────────────────────────────────────────────────────\nif [[ ! -f "$OUTPUT_PATH" ]]; then\n    echo "ERROR: $OUTPUT_PATH not built" >&2\n    exit 1\nfi\nSIZE_MB=$(du -m "$OUTPUT_PATH" | cut -f1)\necho "[build_sidecar_windows] OK: $OUTPUT_PATH (${SIZE_MB} MB)"\necho "[build_sidecar_windows] NEXT: sign with signtool (see docs/migration/signing-guide.md §13.1)."\n'

AssertionError: build_sidecar_windows.sh must define CT2_LIB_DIR (singular, the required ctranslate2/lib dir).
assert 'CT2_LIB_DIR=' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka sidecar build (Windows x86_64 + aarch64)\n# ADR-0020 §4.2. Nuitka freeze of voice_typer/server/ipc_server.py into\n# python-sidecar-<triple>.exe, using python-build-standalone as the base\n# interpreter.\n#\n# Output:\n#   src-tauri/bin/python-sidecar-x86_64-pc-windows-msvc.exe\n#   src-tauri/bin/python-sidecar-aarch64-pc-windows-msvc.exe\n#\n# This script is designed to run on a Windows host under Git Bash / MSYS2 /\n# WSL. From native PowerShell, use the inline Nuitka command in\n# .github/workflows/tauri-windows-build.yml instead (it\'s the same command,\n# just expressed in PowerShell syntax).\n#\n# Usage (Git Bash on Windows):\n#   bash scripts/build/build_sidecar_windows.sh x86_64      # default\n#   bash scripts/build/build_sidecar_windows.sh aarch64     # Windows-on-ARM\n#   bash scripts/build/build_sidecar_windows.sh --check     # verify toolchain\n#\n# ADR-0020 §4.2 mandates:\n#   - python-build-standalone cpython-3.12.x\n#   - --standalone --onefile\n#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2\n#     (ADR-0025 C7: ASR liv...isper\n    --nofollow-import-to=ctranslate2\n    --nofollow-import-to=torch\n    --include-package=voice_typer\n    --include-package=websockets\n    # ADR-0023 packaging: media ingest lazily imports yt_dlp / yt_dlp_ejs /\n    # av (dec
… (truncated)
```

### 95. `tests.tauri.mig17.test_nuitka_linux_build.test_known_gap_no_python_import_sanity_check`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/mig17/test_nuitka_linux_build.py:424`

```
assert '! -d "$SITE/faster_whisper"' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_BIN"\n\n# ─── Quick smoke (help text only; no display server required) ───────────────\n# ADR-0020 §4.5 Phase 0 gate: verify --help works (proves the frozen\n# interpreter boots). C7: the slim sidecar must NOT load faster_whisper /\n# ctranslate2 at all — ASR lives in the pack worker, so the old "prove the\n# model loads inside Nuitka" smoke is retired with the includes that fed\n# it. Exclusion is pinned statically by tests/test_nuitka_asr_exclusions.py\n# (flag text in all four invocations) and enforced by the 185 MB size gate.\necho "[build_sidecar_linux] smoke: $OUTPUT_BIN --help"\nif [[ "$CROSS_BUILD" == "true" ]]; then\n    # Use qemu explicitly for the help check (binfmt_misc may not be active).\n    qemu-aarch64-static "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (cross-build --help skipped, verify on aarch64 host)"\nelse\n    "$OUTPUT_BIN" --help 2>&1 | head -20 \\\n        || echo "[build_sidecar_linux] (—help returned non-zero; check $BUILD_LOG)"\nfi\n\necho "[build_sidecar_linux] DONE: $OUTPUT_BIN"\n'

AssertionError: build_sidecar_linux.sh must still check the faster_whisper dir exists (partial mitigation for GAP-2, directory check, not Python import).
assert '! -d "$SITE/faster_whisper"' in '#!/usr/bin/env bash\n# =============================================================================\n# Lausu. Nuitka Linux sidecar build (Phase 0-L, ADR-0020 §4.4)\n#\n# Builds the frozen Python sidecar (`python-sidecar-<triple>`) for Linux,\n# for both x86_64-unknown-linux-gnu and aarch64-unknown-linux-gnu.\n#\n# The resulting binary is dropped at:\n#   src-tauri/bin/python-sidecar-<triple>\n# which is where Tauri\'s `externalBin` mechanism expects it (Tauri v2\n# appends the Rust target triple to the base name `bin/python-sidecar`\n# at runtime; see ADR-0020 §4.1 + §7).\n#\n# Usage:\n#   bash scripts/build/build_sidecar_linux.sh x86_64    # native x86_64 build\n#   bash scripts/build/build_sidecar_linux.sh aarch64   # native aarch64 build\n#                                                       # (requires aarch64 host)\n#                                                       # OR cross-build on x86_64\n#                                                       # via qemu-user-static\n#   bash scripts/build/build_sidecar_linux.sh --check   # verify toolchain (BUILD-1)\n#\n# Required env (override defaults with these):\n#   VOICE_TYPER_PYBS_DIR  Directory containing the extracted...ibc 2.35." >&2\n        exit 1\n    fi\n    echo "[build_sidecar_linux] OK: glibc baseline (≤ 2.35) verified"\n}\nverify_glibc "$OUTPUT_BIN"\n\n# ─── Quick smoke (
… (truncated)
```

### 96. `tests.tauri.mig17.test_toast_linux.TestValidateOnLinuxHostBlock.test_docstring_documents_libnotify_install_step`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/mig17/test_toast_linux.py:459`

```
assert 'sudo apt install libnotify4' in 'toast notification wiring validation (Linux).'

AssertionError: VALIDATE ON LINUX HOST block MUST mention 'sudo apt install libnotify4', without libnotify4, the notify() call silently fails (D-Bus message never sent).
assert 'sudo apt install libnotify4' in 'toast notification wiring validation (Linux).'
tests/tauri/mig17/test_toast_linux.py:459: in test_docstring_documents_libnotify_install_step
    assert "sudo apt install libnotify4" in doc, (
E   AssertionError: VALIDATE ON LINUX HOST block MUST mention 'sudo apt install libnotify4', without libnotify4, the notify() call silently fails (D-Bus message never sent).
E   assert 'sudo apt install libnotify4' in 'toast notification wiring validation (Linux).'
```

### 97. `tests.tauri.mig17.test_toast_linux.TestValidateOnLinuxHostBlock.test_docstring_contains_validate_on_linux_host_header`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/mig17/test_toast_linux.py:451`

```
assert 'VALIDATE ON LINUX HOST:' in 'toast notification wiring validation (Linux).'

AssertionError: Module docstring MUST contain 'VALIDATE ON LINUX HOST:' header, this is the canonical marker the Linux host validator scans for.
assert 'VALIDATE ON LINUX HOST:' in 'toast notification wiring validation (Linux).'
tests/tauri/mig17/test_toast_linux.py:451: in test_docstring_contains_validate_on_linux_host_header
    assert "VALIDATE ON LINUX HOST:" in doc, (
E   AssertionError: Module docstring MUST contain 'VALIDATE ON LINUX HOST:' header, this is the canonical marker the Linux host validator scans for.
E   assert 'VALIDATE ON LINUX HOST:' in 'toast notification wiring validation (Linux).'
```

### 98. `tests.tauri.mig17.test_toast_linux.TestValidateOnLinuxHostBlock.test_docstring_documents_dbus_troubleshooting`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/mig17/test_toast_linux.py:475`

```
assert 'D-Bus' in 'toast notification wiring validation (Linux).'

AssertionError: VALIDATE ON LINUX HOST block MUST mention 'D-Bus', the troubleshooting hint for the no-notification-daemon failure mode.
assert 'D-Bus' in 'toast notification wiring validation (Linux).'
tests/tauri/mig17/test_toast_linux.py:475: in test_docstring_documents_dbus_troubleshooting
    assert "D-Bus" in doc, (
E   AssertionError: VALIDATE ON LINUX HOST block MUST mention 'D-Bus', the troubleshooting hint for the no-notification-daemon failure mode.
E   assert 'D-Bus' in 'toast notification wiring validation (Linux).'
```

### 99. `tests.tauri.mig17.test_toast_linux.TestValidateOnLinuxHostBlock.test_docstring_documents_expected_timing`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/mig17/test_toast_linux.py:497`

```
assert 'within 1s' in 'toast notification wiring validation (Linux).'

AssertionError: VALIDATE ON LINUX HOST block MUST document the expected timing ('within 1s'), the upper bound for how long the validator should wait for the banner before declaring the gate failed.
assert 'within 1s' in 'toast notification wiring validation (Linux).'
tests/tauri/mig17/test_toast_linux.py:497: in test_docstring_documents_expected_timing
    assert "within 1s" in doc, (
E   AssertionError: VALIDATE ON LINUX HOST block MUST document the expected timing ('within 1s'), the upper bound for how long the validator should wait for the banner before declaring the gate failed.
E   assert 'within 1s' in 'toast notification wiring validation (Linux).'
```

### 100. `tests.tauri.mig17.test_toast_linux.TestValidateOnLinuxHostBlock.test_docstring_documents_log_path`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/mig17/test_toast_linux.py:488`

```
assert '~/.local/share/lausu/logs/lausu.log' in 'toast notification wiring validation (Linux).'

AssertionError: VALIDATE ON LINUX HOST block MUST document the Linux log path (~/.local/share/lausu/logs/lausu.log) so the validator can confirm the notification event was emitted.
assert '~/.local/share/lausu/logs/lausu.log' in 'toast notification wiring validation (Linux).'
tests/tauri/mig17/test_toast_linux.py:488: in test_docstring_documents_log_path
    assert "~/.local/share/lausu/logs/lausu.log" in doc, (
E   AssertionError: VALIDATE ON LINUX HOST block MUST document the Linux log path (~/.local/share/lausu/logs/lausu.log) so the validator can confirm the notification event was emitted.
E   assert '~/.local/share/lausu/logs/lausu.log' in 'toast notification wiring validation (Linux).'
```

### 101. `tests.tauri.test_installer_naming.TestFullOfflineBuildScript.test_script_exists_and_is_executable`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/tauri/test_installer_naming.py:462`

```
+  where 64 = stat.S_IXUSR

AssertionError: build_full_offline_installer_windows.sh must be executable (chmod +x), the CI YAML invokes it directly.
assert (33188 & 64)
 +  where 64 = stat.S_IXUSR
tests/tauri/test_installer_naming.py:462: in test_script_exists_and_is_executable
    assert mode & stat.S_IXUSR, (
E   AssertionError: build_full_offline_installer_windows.sh must be executable (chmod +x), the CI YAML invokes it directly.
E   assert (33188 & 64)
E    +  where 64 = stat.S_IXUSR
```

### 102. `tests.tauri.test_internal_plugin_tools_absent.TestInternalPluginToolsAbsentFromPackaging.test_gitignore_covers_plugin_artifacts`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/tauri/test_internal_plugin_tools_absent.py:61`

```
FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/voice-typer/voice-typer/tools/internal_plugins/.gitignore'

FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/voice-typer/voice-typer/tools/internal_plugins/.gitignore'
tests/tauri/test_internal_plugin_tools_absent.py:61: in test_gitignore_covers_plugin_artifacts
    gi = (_PLUGINS_DIR / ".gitignore").read_text(encoding="utf-8")
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.11.16/x64/lib/python3.11/pathlib.py:1058: in read_text
    with self.open(mode='r', encoding=encoding, errors=errors) as f:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.11.16/x64/lib/python3.11/pathlib.py:1044: in open
    return io.open(self, mode, buffering, encoding, errors, newline)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/voice-typer/voice-typer/tools/internal_plugins/.gitignore'
```

### 103. `tests.tauri.test_internal_plugin_tools_absent.TestInternalPluginToolsNotInMainRepo.test_root_gitignore_covers_plugin_tools`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/tauri/test_internal_plugin_tools_absent.py:133`

```
assert 1 == 0

AssertionError: tools/internal_plugins must be listed in the root .gitignore (git check-ignore said: not ignored)
assert 1 == 0
tests/tauri/test_internal_plugin_tools_absent.py:133: in test_root_gitignore_covers_plugin_tools
    assert code == 0, (
E   AssertionError: tools/internal_plugins must be listed in the root .gitignore (git check-ignore said: not ignored)
E   assert 1 == 0
```

### 104. `tests.tauri.test_internal_plugin_tools_absent.test_plugin_js_files_stay_inside_the_plugin_workspace[playwright_runner.js]`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/tauri/test_internal_plugin_tools_absent.py:153`

```
+    where exists = PosixPath('/home/runner/work/voice-typer/voice-typer/tools/internal_plugins/google_stt/playwright_runner.js').exists

AssertionError: playwright_runner.js must live under tools/internal_plugins/google_stt
assert False
 +  where False = exists()
 +    where exists = PosixPath('/home/runner/work/voice-typer/voice-typer/tools/internal_plugins/google_stt/playwright_runner.js').exists
tests/tauri/test_internal_plugin_tools_absent.py:153: in test_plugin_js_files_stay_inside_the_plugin_workspace
    assert target.exists(), f"{js_file} must live under tools/internal_plugins/google_stt"
E   AssertionError: playwright_runner.js must live under tools/internal_plugins/google_stt
E   assert False
E    +  where False = exists()
E    +    where exists = PosixPath('/home/runner/work/voice-typer/voice-typer/tools/internal_plugins/google_stt/playwright_runner.js').exists
```

### 105. `tests.tauri.test_internal_plugin_tools_absent.test_plugin_js_files_stay_inside_the_plugin_workspace[run.js]`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/tauri/test_internal_plugin_tools_absent.py:153`

```
+    where exists = PosixPath('/home/runner/work/voice-typer/voice-typer/tools/internal_plugins/google_stt/run.js').exists

AssertionError: run.js must live under tools/internal_plugins/google_stt
assert False
 +  where False = exists()
 +    where exists = PosixPath('/home/runner/work/voice-typer/voice-typer/tools/internal_plugins/google_stt/run.js').exists
tests/tauri/test_internal_plugin_tools_absent.py:153: in test_plugin_js_files_stay_inside_the_plugin_workspace
    assert target.exists(), f"{js_file} must live under tools/internal_plugins/google_stt"
E   AssertionError: run.js must live under tools/internal_plugins/google_stt
E   assert False
E    +  where False = exists()
E    +    where exists = PosixPath('/home/runner/work/voice-typer/voice-typer/tools/internal_plugins/google_stt/run.js').exists
```

### 106. `tests.tauri.test_window_lifecycle_parity.test_main_runtime_grants_the_window_queries_the_bridge_calls`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/tauri/test_window_lifecycle_parity.py:59`

```
FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/voice-typer/voice-typer/src-tauri/gen/schemas/acl-manifests.json'

FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/voice-typer/voice-typer/src-tauri/gen/schemas/acl-manifests.json'
tests/tauri/test_window_lifecycle_parity.py:59: in test_main_runtime_grants_the_window_queries_the_bridge_calls
    resolved = _capability_permissions("main-runtime")
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/tauri/test_window_lifecycle_parity.py:49: in _capability_permissions
    manifest = json.loads(ACL_MANIFESTS.read_text(encoding="utf-8"))
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.11.16/x64/lib/python3.11/pathlib.py:1058: in read_text
    with self.open(mode='r', encoding=encoding, errors=errors) as f:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.11.16/x64/lib/python3.11/pathlib.py:1044: in open
    return io.open(self, mode, buffering, encoding, errors, newline)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/voice-typer/voice-typer/src-tauri/gen/schemas/acl-manifests.json'
```

### 107. `tests.tauri.test_window_lifecycle_parity.test_main_runtime_grants_on_resized_via_event_listen`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/tauri/test_window_lifecycle_parity.py:88`

```
FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/voice-typer/voice-typer/src-tauri/gen/schemas/acl-manifests.json'

FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/voice-typer/voice-typer/src-tauri/gen/schemas/acl-manifests.json'
tests/tauri/test_window_lifecycle_parity.py:88: in test_main_runtime_grants_on_resized_via_event_listen
    resolved = _capability_permissions("main-runtime")
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/tauri/test_window_lifecycle_parity.py:49: in _capability_permissions
    manifest = json.loads(ACL_MANIFESTS.read_text(encoding="utf-8"))
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.11.16/x64/lib/python3.11/pathlib.py:1058: in read_text
    with self.open(mode='r', encoding=encoding, errors=errors) as f:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.11.16/x64/lib/python3.11/pathlib.py:1044: in open
    return io.open(self, mode, buffering, encoding, errors, newline)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/voice-typer/voice-typer/src-tauri/gen/schemas/acl-manifests.json'
```

### 108. `tests.test_clipboard.TestPaste.test_paste_sends_keystroke`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_clipboard.py:72`

```
assert False is True

assert False is True
tests/test_clipboard.py:72: in test_paste_sends_keystroke
    assert result is True
E   assert False is True
```

### 109. `tests.test_clipboard_coverage.TestIsSafePasteTarget.test_returns_true_on_non_windows`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_clipboard_coverage.py:297`

```
assert False is True

assert False is True
tests/test_clipboard_coverage.py:297: in test_returns_true_on_non_windows
    assert result is True
E   assert False is True
```

### 110. `tests.test_clipboard_security.test_safe_paste_target_non_windows`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_clipboard_security.py:31`

```
+    where <function ClipboardManager._is_safe_paste_target at 0x7f1fc2e884a0> = <voice_typer.server.clipboard.manager.ClipboardManager object at 0x7f1f8c81bb90>._is_safe_paste_target

assert False is True
 +  where False = <function ClipboardManager._is_safe_paste_target at 0x7f1fc2e884a0>()
 +    where <function ClipboardManager._is_safe_paste_target at 0x7f1fc2e884a0> = <voice_typer.server.clipboard.manager.ClipboardManager object at 0x7f1f8c81bb90>._is_safe_paste_target
tests/test_clipboard_security.py:31: in test_safe_paste_target_non_windows
    assert clipboard._is_safe_paste_target() is True
E   assert False is True
E    +  where False = <function ClipboardManager._is_safe_paste_target at 0x7f1fc2e884a0>()
E    +    where <function ClipboardManager._is_safe_paste_target at 0x7f1fc2e884a0> = <voice_typer.server.clipboard.manager.ClipboardManager object at 0x7f1f8c81bb90>._is_safe_paste_target
```

### 111. `tests.test_dev_console_launcher.test_launch_dev_console_windows_spawns_cmd`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_dev_console_launcher.py:15`

```
AttributeError: module 'voice_typer.server.autostart.dev_console' has no attribute 'sys'

AttributeError: module 'voice_typer.server.autostart.dev_console' has no attribute 'sys'
tests/test_dev_console_launcher.py:15: in test_launch_dev_console_windows_spawns_cmd
    monkeypatch.setattr(dev_console.sys, "platform", "win32")
                        ^^^^^^^^^^^^^^^
E   AttributeError: module 'voice_typer.server.autostart.dev_console' has no attribute 'sys'
```

### 112. `tests.test_hotkeys_win32.TestModifierOnlyHotkeys.test_modifier_only_polling_loop_suppresses_on_non_modifier_combo`

- Legs: ubuntu-22.04-3.11, windows-2022-3.11
- Location: `tests/test_hotkeys_win32.py:461`

```
+  where True = wait_for(<function TestModifierOnlyHotkeys.test_modifier_only_polling_loop_suppresses_on_non_modifier_combo.<locals>.<lambda> at 0x7fd3be642a20>, timeout=0.12)

AssertionError: Callback fired 1 times after Alt+C combo, should be suppressed (user was doing Alt+C, not invoking bare Alt hotkey)
assert not True
 +  where True = wait_for(<function TestModifierOnlyHotkeys.test_modifier_only_polling_loop_suppresses_on_non_modifier_combo.<locals>.<lambda> at 0x7fd3be642a20>, timeout=0.12)
tests/test_hotkeys_win32.py:461: in test_modifier_only_polling_loop_suppresses_on_non_modifier_combo
    assert not wait_for(lambda: callback.call_count > 0, timeout=0.12), (
E   AssertionError: Callback fired 1 times after Alt+C combo, should be suppressed (user was doing Alt+C, not invoking bare Alt hotkey)
E   assert not True
E    +  where True = wait_for(<function TestModifierOnlyHotkeys.test_modifier_only_polling_loop_suppresses_on_non_modifier_combo.<locals>.<lambda> at 0x7fd3be642a20>, timeout=0.12)
```

### 113. `tests.test_import_model_security.TestImportModelSymlinkRejection.test_legitimate_model_dir_imports_successfully`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_import_model_security.py:401`

```
+    where exists = PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_legitimate_model_dir_impo0/app_hf/huggingface/hub/models--Systran--faster-whisper-tiny').exists

AssertionError: assert False
 +  where False = exists()
 +    where exists = PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_legitimate_model_dir_impo0/app_hf/huggingface/hub/models--Systran--faster-whisper-tiny').exists
tests/test_import_model_security.py:401: in test_legitimate_model_dir_imports_successfully
    assert dest.exists()
E   AssertionError: assert False
E    +  where False = exists()
E    +    where exists = PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_legitimate_model_dir_impo0/app_hf/huggingface/hub/models--Systran--faster-whisper-tiny').exists
```

### 114. `tests.test_import_model_security.TestImportModelSymlinkRejection.test_mixed_symlink_and_clean_models`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_import_model_security.py:441`

```
+      where 'models--Systran--faster-whisper-tiny' = PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw0/test_mixed_symlink_and_clean_m0/source/models--Systran--faster-whisper-tiny').name

AssertionError: assert False
 +  where False = exists()
 +    where exists = (PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw0/test_mixed_symlink_and_clean_m0/app_hf/huggingface/hub') / 'models--Systran--faster-whisper-tiny').exists
 +      where 'models--Systran--faster-whisper-tiny' = PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw0/test_mixed_symlink_and_clean_m0/source/models--Systran--faster-whisper-tiny').name
tests/test_import_model_security.py:441: in test_mixed_symlink_and_clean_models
    assert (app_hf / clean_dir.name).exists()
E   AssertionError: assert False
E    +  where False = exists()
E    +    where exists = (PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw0/test_mixed_symlink_and_clean_m0/app_hf/huggingface/hub') / 'models--Systran--faster-whisper-tiny').exists
E    +      where 'models--Systran--faster-whisper-tiny' = PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw0/test_mixed_symlink_and_clean_m0/source/models--Systran--faster-whisper-tiny').name
```

### 115. `tests.test_installer_state.test_installer_state_path_respects_localappdata`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_installer_state.py:123`

```
ImportError: import error in voice_typer.server.installer_state.sys: No module named 'voice_typer.server.installer_state.sys'; 'voice_typer.server.installer_state' is not a package

ImportError: import error in voice_typer.server.installer_state.sys: No module named 'voice_typer.server.installer_state.sys'; 'voice_typer.server.installer_state' is not a package
/opt/hostedtoolcache/Python/3.11.16/x64/lib/python3.11/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   ModuleNotFoundError: No module named 'voice_typer.server.installer_state.sys'; 'voice_typer.server.installer_state' is not a package

The above exception was the direct cause of the following exception:
tests/test_installer_state.py:123: in test_installer_state_path_respects_localappdata
    monkeypatch.setattr("voice_typer.server.installer_state.sys.platform", "win32")
/opt/hostedtoolcache/Python/3.11.16/x64/lib/python3.11/site-packages/_pytest/monkeypatch.py:107: in derive_importpath
    target = resolve(module)
             ^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.11.16/x64/lib/python3.11/site-packages/_pytest/monkeypatch.py:88: in resolve
    raise ImportError(f"import error in {used}: {ex}") from ex
E   ImportError: import error in voice_typer.server.installer_state.sys: No module named 'voice_typer.server.installer_state.sys'; 'voice_typer.server.installer_state' is not a package
```

### 116. `tests.test_recording.TestStopAudioPrep.test_start_falls_back_to_same_microphone_on_another_host_api`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.13
- Location: `tests/test_recording.py:237`

```
]

assert [0] == [9, 1]
  
  At index 0 diff: 0 != 9
  Right contains one more item: 1
  
  Full diff:
    [
  -     9,
  ?     ^
  +     0,
  ?     ^
  -     1,
    ]
tests/test_recording.py:237: in test_start_falls_back_to_same_microphone_on_another_host_api
    assert opened_devices == [9, 1]
E   assert [0] == [9, 1]
E     
E     At index 0 diff: 0 != 9
E     Right contains one more item: 1
E     
E     Full diff:
E       [
E     -     9,
E     ?     ^
E     +     0,
E     ?     ^
E     -     1,
E       ]
```

### 117. `tests.test_recovery_startup_notify.TestRecoveryStartupNotify.test_unpasted_entries_notify_through_tray_safety`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_recovery_startup_notify.py:41`

```
AssertionError: Expected 'notify_safety' to have been called once. Called 0 times.

AssertionError: Expected 'notify_safety' to have been called once. Called 0 times.
tests/test_recovery_startup_notify.py:41: in test_unpasted_entries_notify_through_tray_safety
    fake_app.tray.notify_safety.assert_called_once()
/opt/hostedtoolcache/Python/3.11.16/x64/lib/python3.11/unittest/mock.py:918: in assert_called_once
    raise AssertionError(msg)
E   AssertionError: Expected 'notify_safety' to have been called once. Called 0 times.
```

### 118. `tests.test_recovery_startup_notify.TestRecoveryStartupNotify.test_recovery_notice_uses_tauri_notification_event`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13, windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/test_recovery_startup_notify.py:92`

```
assert []

assert []
tests/test_recovery_startup_notify.py:92: in test_recovery_notice_uses_tauri_notification_event
    assert notifications
E   assert []
```

### 119. `tests.test_slice3_log_hygiene.TestResourceProbeSingleDrive.test_three_paths_same_drive_emit_one_disk_info`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_slice3_log_hygiene.py:137`

```
+  where 2 = len([<LogRecord: voice_typer.server.resource_probe, 20, /home/runner/work/voice-typer/voice-typer/voice_typer/server/resource_probe.py, 308, "[RESOURCE] Disk free on %s: %.1f GB">, <LogRecord: voice_typer.server.resource_probe, 20, /home/runner/work/voice-typer/voice-typer/voice_typer/server/resource_probe.py, 308, "[RESOURCE] Disk free on %s: %.1f GB">])

AssertionError: same-drive paths must collapse to one line, got 2
assert 2 == 1
 +  where 2 = len([<LogRecord: voice_typer.server.resource_probe, 20, /home/runner/work/voice-typer/voice-typer/voice_typer/server/resource_probe.py, 308, "[RESOURCE] Disk free on %s: %.1f GB">, <LogRecord: voice_typer.server.resource_probe, 20, /home/runner/work/voice-typer/voice-typer/voice_typer/server/resource_probe.py, 308, "[RESOURCE] Disk free on %s: %.1f GB">])
tests/test_slice3_log_hygiene.py:137: in test_three_paths_same_drive_emit_one_disk_info
    assert len(disk_infos) == 1, f"same-drive paths must collapse to one line, got {len(disk_infos)}"
E   AssertionError: same-drive paths must collapse to one line, got 2
E   assert 2 == 1
E    +  where 2 = len([<LogRecord: voice_typer.server.resource_probe, 20, /home/runner/work/voice-typer/voice-typer/voice_typer/server/resource_probe.py, 308, "[RESOURCE] Disk free on %s: %.1f GB">, <LogRecord: voice_typer.server.resource_probe, 20, /home/runner/work/voice-typer/voice-typer/voice_typer/server/resource_probe.py, 308, "[RESOURCE] Disk free on %s: %.1f GB">])
```

### 120. `tests.test_strip_av_cython_shims.test_removes_only_py_with_compiled_twin`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_strip_av_cython_shims.py:43`

```
+    where <function strip_av_shims at 0x7fd38cdcb600> = <module 'strip_av_cython_shims' from '/home/runner/work/voice-typer/voice-typer/scripts/build/strip_av_cython_shims.py'>.strip_av_shims

AssertionError: assert 0 == 2
 +  where 0 = <function strip_av_shims at 0x7fd38cdcb600>(PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_removes_only_py_with_comp0'))
 +    where <function strip_av_shims at 0x7fd38cdcb600> = <module 'strip_av_cython_shims' from '/home/runner/work/voice-typer/voice-typer/scripts/build/strip_av_cython_shims.py'>.strip_av_shims
tests/test_strip_av_cython_shims.py:43: in test_removes_only_py_with_compiled_twin
    assert mod.strip_av_shims(site) == 2
E   AssertionError: assert 0 == 2
E    +  where 0 = <function strip_av_shims at 0x7fd38cdcb600>(PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw1/test_removes_only_py_with_comp0'))
E    +    where <function strip_av_shims at 0x7fd38cdcb600> = <module 'strip_av_cython_shims' from '/home/runner/work/voice-typer/voice-typer/scripts/build/strip_av_cython_shims.py'>.strip_av_shims
```

### 121. `tests.test_strip_av_cython_shims.test_second_run_is_noop`

- Legs: ubuntu-22.04-3.11, ubuntu-22.04-3.12, ubuntu-22.04-3.13
- Location: `tests/test_strip_av_cython_shims.py:56`

```
+    where <function strip_av_shims at 0x7f1f54915080> = <module 'strip_av_cython_shims' from '/home/runner/work/voice-typer/voice-typer/scripts/build/strip_av_cython_shims.py'>.strip_av_shims

AssertionError: assert 0 == 2
 +  where 0 = <function strip_av_shims at 0x7f1f54915080>(PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw0/test_second_run_is_noop0'))
 +    where <function strip_av_shims at 0x7f1f54915080> = <module 'strip_av_cython_shims' from '/home/runner/work/voice-typer/voice-typer/scripts/build/strip_av_cython_shims.py'>.strip_av_shims
tests/test_strip_av_cython_shims.py:56: in test_second_run_is_noop
    assert mod.strip_av_shims(site) == 2
E   AssertionError: assert 0 == 2
E    +  where 0 = <function strip_av_shims at 0x7f1f54915080>(PosixPath('/tmp/pytest-of-runner/pytest-1/popen-gw0/test_second_run_is_noop0'))
E    +    where <function strip_av_shims at 0x7f1f54915080> = <module 'strip_av_cython_shims' from '/home/runner/work/voice-typer/voice-typer/scripts/build/strip_av_cython_shims.py'>.strip_av_shims
```

### 122. `tests.tauri.test_gnu_linkchain_toolchain.test_bootstrap_check_passes_after_provisioning`

- Legs: windows-2022-3.11, windows-2022-3.12, windows-2022-3.13
- Location: `tests/tauri/test_gnu_linkchain_toolchain.py:103`

```
+    where <function check at 0x000001401A5BE700> = <module 'ensure_gnu_linkchain' from 'D:\\a\\voice-typer\\voice-typer\\scripts\\build\\ensure_gnu_linkchain.py'>.check

AssertionError: shim reported as missing/broken. Run: python scripts/build/ensure_gnu_linkchain.py
assert 1 == 0
 +  where 1 = <function check at 0x000001401A5BE700>()
 +    where <function check at 0x000001401A5BE700> = <module 'ensure_gnu_linkchain' from 'D:\\a\\voice-typer\\voice-typer\\scripts\\build\\ensure_gnu_linkchain.py'>.check
tests\tauri\test_gnu_linkchain_toolchain.py:103: in test_bootstrap_check_passes_after_provisioning
    assert bootstrap.check() == 0, (
E   AssertionError: shim reported as missing/broken. Run: python scripts/build/ensure_gnu_linkchain.py
E   assert 1 == 0
E    +  where 1 = <function check at 0x000001401A5BE700>()
E    +    where <function check at 0x000001401A5BE700> = <module 'ensure_gnu_linkchain' from 'D:\\a\\voice-typer\\voice-typer\\scripts\\build\\ensure_gnu_linkchain.py'>.check
```
