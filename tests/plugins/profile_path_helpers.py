"""Platform-neutral checks for the one shared internal-plugin profile authority.

Example configs carry the path spelling of the machine that authored them, so a
cross-platform test compares the data-root-relative profile identity instead of
a literal host path.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from tools.internal_plugins._common.bridge import chrome_profile, install_paths


def assert_shared_profile(configured: str) -> None:
    """A configured profileDir must name the same profile as the one authority."""
    expected = PurePosixPath(install_paths.PROFILE_RELATIVE_PATH).parts
    actual = PurePosixPath(configured.replace("\\", "/")).parts
    assert configured, "profileDir must not be empty"
    assert actual[-len(expected) :] == expected, (
        f"{configured!r} does not name the shared profile "
        f"{install_paths.PROFILE_RELATIVE_PATH!r}"
    )
    assert Path(chrome_profile.PROFILE_DIR) == install_paths.profile_dir()
