"""Package initializer for CrewAI agents.

Disables CrewAI telemetry/tracing and ensures a writable token directory before importing
any ``crewai`` submodule (required in read-only containers and sandboxed test environments).
"""

import os
import tempfile
from pathlib import Path

os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
_local_app_data = os.environ.get("LOCALAPPDATA")
if _local_app_data:
    try:
        (Path(_local_app_data) / "crewai" / "credentials").mkdir(parents=True, exist_ok=True)
    except OSError:
        os.environ["LOCALAPPDATA"] = tempfile.gettempdir()
else:
    os.environ.setdefault("XDG_DATA_HOME", tempfile.gettempdir())
