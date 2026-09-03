# Shopping-AI — Stateless MCP Service (Symy "hands")

Symy is a two-part AI shopping companion. The **brain** (Letta, outside this
repo) owns conversation, user memory, and tool selection. This repo is the
**hands**: a stateless Model Context Protocol (MCP) service the brain calls.
Every call receives a complete `Context` and returns structured data — no
session store, no Redis, no process-level request state. The file-backed cart
stub is the only cross-request storage and exists for local demos; production
cart persistence uses Supabase (`src/db/cart_lines.sql`).

> 2026-09-03: the legacy five-agent stack that previously lived in this
> repository (orchestrator/, search/, memory/, safety/, web/, crawler/,
> platform/, tools/, ops/, legacy tests) was removed per the strangler-fig
> Phase D plan. History is preserved — everything remains recoverable from
> git history and the pre-deletion mirror backup. Its behavior served as the
> golden baseline for this rewrite (see `src/docs/alignment-evidence/`).

## MCP Tools

| Tool | Behavior |
|---|---|
| `symy_search` | Search goods / local services / tickets with filters and budget. Never adds to cart. |
| `symy_compare` | Compare two products by normalized unit price; delta, verdict, notes. Read-only. |
| `symy_cart` | Explicit add / remove / list / checkout. Over-budget add succeeds with `BUDGET_EXCEEDED_WARNING`; unknown item → `CART_ITEM_NOT_FOUND`; empty checkout → `CART_EMPTY`. |
| `symy_chat` | Full conversation turn: safety pre-check → one structured LLM triage → capability execution → LLM composition → deterministic post-check. Purchase *intent* never auto-adds; only explicit add directives mutate the cart. |

All tools return `{ trace_id, ok, data?, error?: { code, message, retryable } }`
with machine-readable error codes (`INVALID_INPUT`, `PROVIDER_TIMEOUT`,
`PROVIDER_UNAVAILABLE`, `SAFETY_BLOCKED`, `CART_*`, `INTERNAL_ERROR`).

## Architecture

```
用户 ⇄ Letta brain (memory + conversation)
              │ MCP client (Letta side)
              ▼
      this service (stateless hands)
              │
              ├── catalog provider   (stub | legacy-search-compatible remote)
              ├── cart provider      (file stub | Supabase)
              ├── llm provider       (OpenAI-compatible; used only inside symy_chat)
              └── safety provider    (rule-based)
```

Seven constitutional rules (statelessness, budget discipline, no auto-add,
category routing, image-proxy for hotlinks, controlled-category compliance,
language-following) are enforced in `src/app/constitution/rules.py` and each
has unit tests including counterexamples.

## Local Development

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[llm,cart]' pytest
.venv/bin/uvicorn src.app.main:app --port 8903
# health: curl localhost:8903/health  → {"status":"ok"}
.venv/bin/pytest src/tests
.venv/bin/python src/demo/e2e_client.py --base-url http://localhost:8903/mcp/
```

Configuration via environment variables (all optional; see `src/app/config.py`
for defaults and `SYMY_*` variables: catalog provider, cart provider, Supabase
URL/key, LLM base/key/model, image-proxy base, cart-memory file).

## Testing & Alignment

- `src/tests/` — 69 tests: units, constitution (7 rules + counterexamples),
  statelessness (same input twice differs only by trace_id), alignment matrix.
- `src/docs/alignment-evidence/` — 20-case behavioral alignment against the
  legacy stack, including live dual-stack captures for the starred cases.
- Deployment: Dockerfile in `src/` (uvicorn src.app.main:app on :8080).
