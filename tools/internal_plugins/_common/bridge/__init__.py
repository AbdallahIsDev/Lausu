"""Shared Chrome-extension bridge for the internal STT plugins.

One profile launcher, one loopback relay/control plane, one MV3 extension and
one selector authority per platform live here. The plugin directories own only
their hotkey seam, copy, platform descriptor and settings keys.
"""
