"""Host resource metrics, read inside the API process.

Replaces the node-exporter and cAdvisor containers (`docs/MCP_MIGRATION_PLAN.md`
parity row 7): psutil reads the same `/proc` counters those daemons exported,
without a second scrape target to deploy, secure, or keep alive.

Honesty rules, the same discipline as `infrastructure/health.py`:

- A value this process cannot measure stays `None`. The network counters are
  cumulative since boot, so `network_rx_bytes` / `network_tx_bytes` are deltas
  against the previous sample - and the first sample after a restart reports
  `None` rather than an arbitrary lifetime total.
- `psutil.cpu_percent(interval=None)` returns 0.0 on the process's first call
  because it has no window to measure over. That first sample's CPU is a
  floor, not a lie; every later call measures exactly the gap between two
  samples, which is the "current window" the panel asks for.
- `disk_pct` is the filesystem the API actually writes to. In the compose
  deployment that is the container's overlay - which is the disk that fills
  up in practice - not some host partition nothing here can free.

Any psutil failure is caught per-metric: a monitoring probe that can take the
sampler down is worse than one that reports nothing for that metric.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Optional

try:
    import psutil
except ImportError:  # pragma: no cover - declared in requirements.txt
    psutil = None

logger = logging.getLogger(__name__)

#: Cumulative network readings at the previous sample. Process-local on
#: purpose, for the same reason `health._PREV` is: a restart resets the
#: counters and this cache together, and a backwards counter (host reboot)
#: is reported as 0 rather than a negative delta.
_PREV_NET_LOCK = threading.Lock()
_PREV_NET: dict[str, int] = {}


def _disk_path() -> str:
    """The filesystem this deployment writes to: C:\\ on Windows, / elsewhere."""
    return "C:\\" if os.name == "nt" else "/"


def _reset_host_state() -> None:
    """Forget the network baseline. Used by tests and after a reset."""
    with _PREV_NET_LOCK:
        _PREV_NET.clear()


def sample_host() -> dict[str, Optional[float]]:
    """Read all host metrics this process can measure. Never raises."""
    out: dict[str, Optional[float]] = {
        "cpu_pct": None,
        "ram_pct": None,
        "disk_pct": None,
        "network_rx_bytes": None,
        "network_tx_bytes": None,
    }
    if psutil is None:
        # Missing on an install that skipped requirements.txt: report nothing
        # rather than crash the sampler.
        logger.warning("psutil is unavailable; host metrics will stay empty")
        return out

    try:
        out["cpu_pct"] = round(psutil.cpu_percent(interval=None), 1)
    except Exception:
        logger.exception("cpu sample failed")

    try:
        out["ram_pct"] = round(psutil.virtual_memory().percent, 1)
    except Exception:
        logger.exception("ram sample failed")

    try:
        out["disk_pct"] = round(psutil.disk_usage(_disk_path()).percent, 1)
    except Exception:
        logger.exception("disk sample failed")

    try:
        io = psutil.net_io_counters()
        with _PREV_NET_LOCK:
            prev_rx = _PREV_NET.get("rx")
            prev_tx = _PREV_NET.get("tx")
            _PREV_NET["rx"] = io.bytes_recv
            _PREV_NET["tx"] = io.bytes_sent
        if prev_rx is not None:
            out["network_rx_bytes"] = max(0, io.bytes_recv - prev_rx)
        if prev_tx is not None:
            out["network_tx_bytes"] = max(0, io.bytes_sent - prev_tx)
    except Exception:
        logger.exception("network sample failed")

    return out
