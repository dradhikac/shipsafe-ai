"""ShipSafe AI — Agentic Release & Regression Guardian."""

import os
from pathlib import Path

__version__ = "0.1.0"

# Automatically load .env file if present in workspace root without requiring third-party libraries
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.is_file():
    try:
        with open(_env_path, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if not _line or _line.startswith("#") or "=" not in _line:
                    continue
                _k, _v = _line.split("=", 1)
                _k = _k.strip()
                _v = _v.strip().strip("'\"")
                if _k and _k not in os.environ:
                    os.environ[_k] = _v
    except Exception:
        pass
