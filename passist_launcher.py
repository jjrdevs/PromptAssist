"""PyInstaller entry point for the one-file `passist` CLI.

PyInstaller's `Analysis` wants a single script to freeze. This module is the
thin shim that imports the real entry point and exits with its return code as
the process exit status. Kept at the repo root so PyInstaller can see it, with
the `passist` package on `pathex`.

    python -m PyInstaller passist.spec

On Windows the output is `dist/passist.exe` — self-contained, no Python needed.
"""
import sys
from passist.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
