"""CareOps Intelligence backend package.

Configures CrewAI's telemetry and local storage environment variables before any module imports
``crewai`` so that sandboxed test runners and read-only containers never fail on ``LOCALAPPDATA``.
"""

import os
import tempfile
from pathlib import Path

os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
_local = os.environ.get("LOCALAPPDATA")
if _local:
    try:
        (Path(_local) / "crewai" / "credentials").mkdir(parents=True, exist_ok=True)
    except OSError:
        os.environ["LOCALAPPDATA"] = tempfile.gettempdir()
else:
    os.environ.setdefault("XDG_DATA_HOME", tempfile.gettempdir())
