# ADR 0001 — Hosted, free, open-source LLM providers only

**Status:** accepted · **Date:** 2026-10-20 · **Owner:** operator decision

## Context

The monitoring scan agent needs a language model to turn numbers into a
narrative. That model runs against a small VPS, for a college project, with
real student data behind the questions it asks. The constraints were:

- the deployment must be free to run, indefinitely;
- no paid provider may ever be configured by accident;
- no raw row may leave the building;
- the model may read telemetry, but never write to it and never act on it.

## Decision

**Hosted, free, open-source providers only**, from a closed allowlist of two:

| provider | role | why |
|---|---|---|
| `nvidia_nim` | primary | free hosted tier, strong instruction following, the Nemotron models are open-weight |
| `openrouter` | fallback | free `:free` model tier, so a provider outage is not an outage |

`llms/` is the single allowlist surface. A named provider outside it is
refused — at the config validator, at the resolver, at the client factory
and at the job gate — even when a working key for it is sitting in the
environment. The historic `openai-compatible` value was removed for the same
reason: it could point anywhere, and a value that can point anywhere is not
an allowlist.

NVIDIA's credential is accepted under two names (`NVIDIA_API_KEY`, with
`NVIDIA_NIM_API_KEY` as an alias) so one key serves both the discovery agent
and the scan agent.

**There is no local provider.** A self-hosted model was carried for a while
as an optional, unexposed fallback; it has been removed completely — the
allowlist, the env, the compose file, the discovery agent's failover chain
and the documentation. An installation that wants a model on its own
hardware can still point `LLM_BASE_URL` at it for the generic Stage-2
client, but the agent tooling never routes there: the fallback has to work
when the primary is down, and "the fallback needs the internet" is exactly
what a fallback is for.

## Consequences

- **Free forever, or not shipped.** A paid provider cannot be reached by
  configuration, by environment variable, or by a mistake in a deployment
  file. The preflight gate checks it on every CI run.
- **One provider stack.** The agent tooling reuses the discovery agent's
  provider clients rather than writing a second HTTP client per provider.
- **The fallback is a different vendor.** If NVIDIA is unavailable, the
  request goes to OpenRouter's free tier. Both are audited separately: the
  outbound row names the provider that actually served the request.
- **Two providers, two keys, nothing else.** No local model to install, no
  GPU to buy, no container to keep warm, and one less thing that can be
  half-configured on a deployment.
- **The data stays inside the rules.** Whatever the provider, a telemetry job
  passes the egress gate first (see SCAN-AGENT.md §4 rule 8), and a job that
  cannot prove the gate refuses to start rather than sending something raw.

## Alternatives considered

- **A paid provider (OpenAI, Anthropic, Groq).** Rejected: it breaks the
  "free forever" constraint and, more importantly, a paid key in the
  environment is a standing invitation for one deployment to start sending
  student data somewhere.
- **Self-hosted weights on the VPS.** Rejected: the smallest useful
  models need more memory than the target VPS has, and the measured
  CPU-hosted latency (69–509 s per call) made the scan feel broken. It was
  carried for a while as an optional local fallback and has now been removed
  outright, rather than left as a third thing to configure.
- **A local model behind the existing OpenAI-compatible client.** This is
  what the generic `LLM_BASE_URL` plumbing is for, and it stays available —
  but it is plumbing, not a named provider, so it is not on the allowlist
  and not what the agent tooling uses.
