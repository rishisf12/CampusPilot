"""House-built MCPs (see `docs/MCP_MIGRATION_PLAN.md`, bundle rule 7).

Every MCP lives in its own subpackage — `monitoring`, `alerting`, `security`,
`analyst` — sharing exactly one thin core (`mcp.core`). Swapping or debugging
one MCP must never touch another.
"""
