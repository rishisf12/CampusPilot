"""Print Prometheus's view of the monitoring stack.

Run from ``backend/backend`` while ``docker compose --profile monitoring`` is
up::

    python tools/check_prometheus.py

Or, without publishing Prometheus on the host (which is deliberate - it exposes
internal route names), pipe it into a container already on the compose network::

    docker compose exec -T backend python - < backend/backend/tools/check_prometheus.py

Exists because "the config validated" and "Prometheus is actually collecting"
are different claims, and only the second one tells you whether anyone will be
paged at 3am.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

#: Overridable so the same script works from the host (published port) and from
#: inside the compose network (service name).
PROM = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")

#: Jobs that only exist in the `monitoring-full` profile. Prometheus is
#: configured with their static targets unconditionally, so in a lite
#: deployment they are permanently `down`. That is the intended reading of a
#: `down` target for a service you chose not to run - the alternative,
#: maintaining two Prometheus configs, guarantees they drift.
OPTIONAL_JOBS = {"cadvisor", "blackbox"}


def get(path: str):
    with urllib.request.urlopen(f"{PROM}{path}", timeout=10) as r:
        return json.load(r)


def main() -> int:
    targets = get("/api/v1/targets?state=active")["data"]["activeTargets"]
    print("=== targets ===")
    bad = []
    for t in targets:
        health = t["health"]
        job = t["labels"].get("job", "?")
        optional = job in OPTIONAL_JOBS
        # A `down` target that belongs to a profile you are not running is not a
        # fault. Treating it as one would make the lite deployment permanently
        # red and train people to ignore this script.
        note = " (optional, profile not enabled)" if optional and health != "up" else ""
        if health != "up" and not optional:
            bad.append(job)
        err = (t.get("lastError") or "")[:70]
        print(f"  {job:<16} {health:<8} {t['scrapeUrl']}{note}")
        if err and not (optional and health != "up"):
            print(f"      error: {err}")

    print("\n=== is our own metric actually there? ===")
    # The point of the exercise: a target can be "up" while the metric we care
    # about was never produced. Querying for the specific series proves the
    # instrumentation, not just the scrape, works.
    for metric in ("campuspilot_http_requests_total",
                   "campuspilot_http_request_duration_seconds_count",
                   "campuspilot_http_requests_in_flight",
                   "node_memory_MemTotal_bytes"):
        res = get(f"/api/v1/query?query={metric}")
        series = res["data"]["result"]
        total = sum(float(s["value"][1]) for s in series)
        print(f"  {metric:<48} {len(series)} series, total={total:g}")

    print("\n=== route label cardinality ===")
    res = get('/api/v1/query?query=campuspilot_http_requests_total')
    routes = {}
    for s in res["data"]["result"]:
        route = s["metric"].get("route", "?")
        routes[route] = routes.get(route, 0) + float(s["value"][1])
    for route, value in sorted(routes.items(), key=lambda kv: -kv[1])[:8]:
        print(f"  {route:<28} {value:g}")

    print("\n=== firing alerts ===")
    alerts = get("/api/v1/alerts")["data"]["alerts"]
    firing = [a for a in alerts if a["state"] == "firing"]
    for a in firing:
        print(f"  {a['labels'].get('severity', '?'):<9} {a['labels'].get('alertname')}")
    if not firing:
        print("  none")

    print(f"\n{'PASS' if not bad else 'FAIL'}: {len(targets)} targets, "
          f"{len(bad)} required targets not up")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())