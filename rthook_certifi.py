"""PyInstaller runtime hook: fix certifi path for frozen apps.

certifi 2026+ uses importlib.resources.files("certifi").joinpath("cacert.pem")
which does not work correctly inside PyInstaller's frozen environment
because the data files are collected to _internal/certifi/ but the
importlib.resources API expects them within the package directory.

This hook patches certifi.core.where() to find cacert.pem via
sys._MEIPASS (the _internal directory) instead.
"""
import os
import sys


def _install_certifi_fix():
    try:
        import certifi.core
    except ImportError:
        return  # certifi not used, skip

    # If we're not in a frozen app, no fix needed
    if not hasattr(sys, 'frozen') and not hasattr(sys, '_MEIPASS'):
        return

    # Determine the base directory (where _internal lives)
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        base = meipass
    else:
        base = os.path.dirname(sys.executable)

    # Locate cacert.pem
    cert_path = None
    candidates = [
        os.path.join(base, 'certifi', 'cacert.pem'),
        os.path.join(base, '_internal', 'certifi', 'cacert.pem'),
    ]
    for p in candidates:
        if os.path.exists(p):
            cert_path = p
            break

    if cert_path is None:
        return  # can't find the cert file, leave default behavior

    # Patch certifi.core.where() to return the correct path
    original_where = certifi.core.where

    def patched_where():
        return cert_path

    certifi.core.where = patched_where
    # Also patch the public API
    import certifi
    certifi.where = patched_where


_install_certifi_fix()
