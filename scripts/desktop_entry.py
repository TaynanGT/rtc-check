"""Entrada mínima usada pelo PyInstaller no executável Windows."""

from __future__ import annotations

from rtc_check.webapp import main

if __name__ == "__main__":
    raise SystemExit(main())
