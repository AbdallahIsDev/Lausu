"""Onboarding permissions probe mixin.

``check_permissions`` is the canonical entry point behind the
``onboarding_check_permissions`` / ``onboarding_recheck_permission``
IPC handlers. Split from ``voice_typer/server/onboarding.py``
(create-first); ``OnboardingController`` composes it so the historical
import path keeps resolving.
"""

from __future__ import annotations

from voice_typer.server._lazy_import import lazy_module

# Call-time facade access: tests patch ``resolve_host_bundle_id`` on the
# facade, so the probe must re-resolve it there (never by value).
_facade = lazy_module("voice_typer.server.onboarding")


class _OnboardingPermissionsMixin:
    """Onboarding permission-state probe (no host state).

    Split from the facade; composed by OnboardingController.
    """

    def check_permissions(self) -> dict:
        """Probe the OS-level keyboard-monitoring permission state.

        macOS first-run users without Accessibility permission
        complete the wizard, press their hotkey, and nothing happens.
        Linux users not in the ``input`` group (and without
        the udev rule) hit the same silent failure.

        This method is the **canonical entry point** for the
        ``onboarding_check_permissions`` and
        ``onboarding_recheck_permission`` IPC handlers, it is the
        single source of truth that produces the renderer-facing
        permission payload. (A previous ``check_permissions_payload``
        free-function in ``permissions.py`` was dead code with a
        misleading docstring claiming this same role; it has been
        removed.)

        This method delegates to
        :func:`voice_typer.server.permissions.check_keyboard_permission`
        to detect the current state and returns a renderer-friendly
        dict containing:

        - ``platform``: ``"windows"`` / ``"macos"`` / ``"linux"`` /
          ``"unknown"``
        - ``state``: ``"granted"`` / ``"denied"`` / ``"unknown"``
          (matches :class:`PermissionState`)
        - ``needed``: bool. True iff the platform requires a
          permission and the user hasn't granted it yet
        - ``instructions``: ``None`` on Windows / unknown platforms;
          a dict with ``title_key`` (str), ``steps_keys`` (list[str]),
          and ``commands`` (list[str] | None) on macOS / Linux when
          permission is needed. The key strings are dotted i18n keys
          (e.g. ``"onboarding.permissionsInstructionsMacosTitle"``)
          that the renderer resolves via ``t(key)``.

        The renderer uses this in the Permissions step to show a
        platform-specific setup walkthrough.

        the ``instructions`` dict now carries i18n *keys*
        (``title_key`` / ``steps_keys``) instead of literal English
        strings. The renderer resolves them via ``t(key)`` so the
        walkthrough is fully localized. ``commands`` remains literal
        (shell commands are not translatable). On macOS the commands
        carry the ``tccutil reset Accessibility <bundle-id>`` re-grant
        command with the bundle ID resolved at RUNTIME
        (``resolve_host_bundle_id``), never hardcoded, so both the
        predecessor and Tauri builds show the command for the actually
        running host. The renderer supports both the new key-based
        shape and the legacy literal shape (``title`` / ``steps``) for
        backward compatibility with older backends and test mocks.
        """
        # Import the platform helpers from ``permissions`` (which
        from voice_typer.server import permissions as perm_mod
        from voice_typer.server.permissions import (
            LINUX_UDEV_RULE,
            PermissionState,
            check_keyboard_permission,
        )

        state = check_keyboard_permission()

        if perm_mod.is_windows():
            platform_name = "windows"
            instructions = None
            needed = False
        elif perm_mod.is_macos():
            platform_name = "macos"
            needed = state != PermissionState.GRANTED
            if needed:
                # The re-grant command embeds the host app's bundle ID,
                bundle_id = _facade.resolve_host_bundle_id()
                if bundle_id:
                    # The command string comes from the single
                    from voice_typer.server.server_platform.macos_bundle_id import (
                        tccutil_reset_command_str,
                    )

                    commands = [tccutil_reset_command_str("Accessibility", bundle_id)]
                else:
                    commands = None
                instructions = {
                    "title_key": "onboarding.permissionsInstructionsMacosTitle",
                    "steps_keys": [
                        "onboarding.permissionsInstructionsMacosStep1",
                        "onboarding.permissionsInstructionsMacosStep2",
                        "onboarding.permissionsInstructionsMacosStep3",
                    ],
                    "commands": commands,
                }
            else:
                instructions = None
        elif perm_mod.is_linux():
            platform_name = "linux"
            needed = state != PermissionState.GRANTED
            # mirror the macOS step but for the input group +
            instructions = (
                {
                    "title_key": "onboarding.permissionsInstructionsLinuxTitle",
                    "steps_keys": [
                        "onboarding.permissionsInstructionsLinuxStep1",
                        "onboarding.permissionsInstructionsLinuxStep2",
                        "onboarding.permissionsInstructionsLinuxStep3",
                    ],
                    "commands": [
                        "sudo usermod -aG input $USER",
                        "# udev rule (installed by scripts/linux/install_permissions.py):",
                        f"# {LINUX_UDEV_RULE}",
                    ],
                }
                if needed
                else None
            )
        else:
            platform_name = "unknown"
            instructions = None
            needed = False

        return {
            "platform": platform_name,
            "state": state.value,
            "needed": needed,
            "instructions": instructions,
        }
