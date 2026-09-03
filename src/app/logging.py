"""JSON-lines-only logging contract for new src code."""

from __future__ import annotations

import json
import sys
import time
from typing import Any

from .context import new_trace_id


def emit_log(
    *,
    trace_id: str | None = None,
    tool: str,
    error_code: str | None = None,
    latency_ms: float | None = None,
    **values: Any,
) -> None:
    record = {
        "ts": time.time(),
        "trace_id": trace_id or new_trace_id(),
        "tool": tool,
        "error_code": error_code,
        "latency_ms": latency_ms,
        **values,
    }
    sys.stdout.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()
