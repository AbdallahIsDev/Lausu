"""Backward-compat re-exports for the platform fix regressions.

The tests now live in domain modules under ``tests/clipboard/``,
``tests/platform/``, ``tests/tray/`` and ``tests/packaging/``. ``__test__ =
False`` keeps this shim from collecting the re-exported tests a second time.
"""

from __future__ import annotations

from tests.clipboard.test_platform_clipboard_fixes import (
    TestClipboardSaveRestore,
    TestClipboardSequenceNumber,
    TestClipboardVerification,
    TestContentEditableComment,
    TestElevatedTarget,
    TestEmptyClipboard,
    TestPasswordField,
    TestPynputFallbackDocumentation,
    TestSafeKeyRelease,
    TestWin32ClipboardAbstraction,
)
from tests.packaging.test_platform_manifest import TestManifestIn
from tests.platform.test_platform_autostart_session import (
    TestMutexHandleClose,
    TestMutexPathHash,
    TestRDPSession,
    TestVenvDetection,
)
from tests.platform.test_platform_env_validation import TestEnvVarValidation
from tests.platform.test_platform_hotkey_detection import (
    TestAltGrDetection,
    TestIMEDetection,
    TestMacOSAccessibilityGuide,
    TestVKMapFallback,
)
from tests.tray.test_platform_tray_icon import TestICOFormatSupport, TestTrayIconShapes

__all__ = [
    "TestAltGrDetection",
    "TestClipboardSaveRestore",
    "TestClipboardSequenceNumber",
    "TestClipboardVerification",
    "TestContentEditableComment",
    "TestEmptyClipboard",
    "TestEnvVarValidation",
    "TestElevatedTarget",
    "TestICOFormatSupport",
    "TestIMEDetection",
    "TestMacOSAccessibilityGuide",
    "TestManifestIn",
    "TestMutexHandleClose",
    "TestMutexPathHash",
    "TestPasswordField",
    "TestPynputFallbackDocumentation",
    "TestRDPSession",
    "TestSafeKeyRelease",
    "TestTrayIconShapes",
    "TestVenvDetection",
    "TestVKMapFallback",
    "TestWin32ClipboardAbstraction",
]

__test__ = False
