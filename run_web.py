"""
Launcher for the web dashboard that avoids Python venv activation entirely.

The Claude Code preview tool's sandbox denies read access to any pyvenv.cfg
file, which breaks normal venv activation (`.venv/bin/uvicorn`, `source
.venv/bin/activate`, etc. all fail with PermissionError on pyvenv.cfg).
Dependencies here live in a plain `pylibs/` directory (installed via
`pip install --target=pylibs ...`, which creates no pyvenv.cfg) and are
added to sys.path manually, then run with the base system interpreter.
"""
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "pylibs"))
sys.path.insert(0, ROOT)
os.environ.setdefault("POSTGRES_HOST", "localhost")

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("web.main:app", host="0.0.0.0", port=8000)
