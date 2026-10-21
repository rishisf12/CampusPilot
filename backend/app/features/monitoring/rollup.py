"""The monitoring worker: rollups, pruning, and alert evaluation.

The compose `rollup` service runs this:

    python -m features.monitoring.rollup --loop --prune

It is the piece that replaced two of the deleted containers:

- **the hourly rollup** - the raw event table is aggregated into hourly
  buckets and the raw rows are pruned afterwards, so the dashboards read a
  small table instead of an ever-growing one;
- **the alert evaluator** - the rules are evaluated against the in-app
  stores and the incidents are routed to the channels, which is what
  Alertmanager used to do.

Without it the raw event table grows forever and nothing is ever alerted
on, so it runs in the same worker rather than as a second service.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("monitoring.rollup")

#: How often the loop runs. The rollup buckets are hourly, so an hourly
#: pass is right; the alert evaluation is cheap and benefits from running
#: more often, so it runs every pass.
DEFAULT_INTERVAL_MINUTES = 60


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def run_once(*, prune: bool = True, now: Optional[datetime] = None) -> dict[str, Any]:
    """One pass: roll up, evaluate the alert rules, deliver, prune."""
    from core.database import session_scope
    from features.alerts.evaluator import evaluate_rules, incidents_to_deliver
    from features.alerts.delivery import deliver
    from features.monitoring.infrastructure.rollup import prune as prune_events
    from features.monitoring.infrastructure.rollup import rollup

    result: dict[str, Any] = {"at": (now or _now_utc()).isoformat()}
    with session_scope() as session:
        result["rollup"] = rollup(session, now=now)
        opened = evaluate_rules(session, now=now)
        result["alerts_opened"] = len(opened)
        if opened:
            delivered: list[dict[str, Any]] = []
            for incident, rule in incidents_to_deliver(session, opened):
                try:
                    delivered.extend(
                        asyncio.run(deliver(session, incident, rule))
                    )
                except Exception as exc:  # noqa: BLE001 - delivery must not break the pass
                    logger.warning("alert delivery failed: %s", exc)
            result["alerts_delivered"] = delivered
        if prune:
            result["pruned"] = prune_events(session, now=now)
    return result


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--loop", action="store_true", help="run forever instead of once"
    )
    parser.add_argument(
        "--prune", action="store_true", help="delete raw events past the retention window"
    )
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=DEFAULT_INTERVAL_MINUTES,
        help="how long to wait between passes in --loop mode",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    if not args.loop:
        result = run_once(prune=args.prune)
        print(json.dumps(result, indent=2, default=str))
        return 0

    logger.info("monitoring worker started (every %d minutes)", args.interval_minutes)
    while True:
        try:
            result = run_once(prune=args.prune)
            logger.info("pass done: %s", json.dumps(result, default=str)[:400])
        except Exception as exc:  # noqa: BLE001 - a failed pass must not kill the worker
            logger.exception("monitoring pass failed: %s", exc)
        time.sleep(max(1, args.interval_minutes) * 60)
    return 0  # unreachable, but the type checker wants it


if __name__ == "__main__":
    sys.exit(main())
