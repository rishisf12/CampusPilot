# Demo scan - A_W_HEALTH

- scan id: `demo-a_w_health-1792518430`
- recorded: 2026-10-20T17:47:13+00:00
- provider: `nvidia_nim`
- model call: **stubbed** (no provider key in this environment; the tool output, the redaction and the audit trail below are real)

## Verdict

- status: **healthy**
- summary: Demo scan: the measured signals in this window are inside their thresholds, and every number below came from a tool call.
- finding: Measured signal within budget (info)
  - `telemetry_health_7d_web` = 3764.0 count (source: telemetry_health)
  - `p95_latency_window_6h_web` = 0.0 count (source: p95_latency_window)

## The trail it left (`telemetry.tool_call_audit`)

| tool | metric_key | ok | bytes_out | redactions | sent_to |
|---|---|---|---|---|---|
| `telemetry_health` | `telemetry_health_7d_web` | True | 0 | 0 | - |
| `p95_latency_window` | `p95_latency_window_6h_web` | True | 0 | 0 | - |
| `health_uptime_pct` | `web_uptime_pct` | True | 0 | 0 | - |
| `__egress_canary` | `canary` | True | 0 | 0 | - |
| `llm.request` | `` | True | 2481 | 0 | nvidia_nim |

Every tool call is redacted before it is returned, the run has one salt so pseudonyms line up across rows, and an outbound request names the provider it went to and the size of the payload that left.
