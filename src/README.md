# Shopping-AI Stateless MCP

This package is the stateless “hands” service for the Symy brain. Letta owns conversation and memory; each MCP call receives a complete `Context` and returns structured data. There is no session store, Redis cache, or process-level request state. The explicit file cart stub is the only cross-request storage and is intended for local demos; Supabase uses `src/db/cart_lines.sql`.

## Tools

- `symy_search`: searches goods, local services, and tickets; filters and budget are server-side, and it never adds to cart.
- `symy_compare`: resolves each side from exactly one of `query` or `product_ref`, sorts by normalized unit price, and returns delta, verdict, and comparison notes.
- `symy_cart`: explicit add/remove/list/checkout operations only. Over-budget adds succeed with `BUDGET_EXCEEDED_WARNING`; missing items return `CART_ITEM_NOT_FOUND`; checkout on an empty cart returns `CART_EMPTY`.
- `symy_chat`: full shopping-conversation turn (Round 3 scope).

## Local development

```bash
.venv/bin/pip install -e '.[llm,cart]' pytest
SYMY_IMAGE_PROXY_BASE=http://localhost:8009 .venv/bin/uvicorn src.app.main:app --port 8903
.venv/bin/pytest src/tests
.venv/bin/python src/demo/e2e_client.py --base-url http://localhost:8903/mcp/
```

Set `SYMY_CATALOG_PROVIDER=remote` and `SYMY_CATALOG_BASE_URL=http://localhost:8010` to use the legacy search service. Set `SYMY_CART_PROVIDER=supabase` plus `SYMY_SUPABASE_URL` and `SYMY_SUPABASE_KEY` for durable carts. `SYMY_CART_MEMORY` controls the stub file.

## Alignment

Behavior is compared against the live legacy stack where available. Raw required-run evidence is stored under `src/docs/alignment-evidence`; non-live cases use deterministic code-walkthrough projections. Known differences: the stateless interface returns machine-readable cards/error envelopes instead of legacy prose, and its demo catalog exposes explicit per-unit prices and ticket fields that legacy text retrieval does not return.

## Chat flow

`symy_chat` runs a complete one-turn flow: one structured LLM triage call (`search` / `compare` / `cart_add` / `other` plus entity fields), deterministic capability execution, an OpenAI-compatible compose call, and rule-based safety post-check. The optional `chat_history` parameter is forwarded to compose and supports recent-turn reference resolution. With no `SYMY_LLM_KEY` or `SYMY_LLM_MODEL`, both LLM stages fall back to deterministic rule replies while preserving the same structured cards, actions, and warnings. LLM calls exist only inside this capability; MCP routing itself remains deterministic.

## Round 3 validation

- Full suite: `.venv/bin/pytest src/tests -q` → `67 passed`.
- End-to-end: start on port 8906 and run `.venv/bin/python src/demo/e2e_client.py --base-url http://localhost:8906/mcp/`; the script exercises search, compare, cart add/list/checkout, and chat.
- Alignment: Round 3 live evidence, authorization blockers, and conclusions are under `src/docs/alignment-evidence/round3/`; the semantic 20-case assertions live in `src/tests/test_alignment.py`.
- Legacy data/config walkthroughs use the original production behavior from `orchestrator/`, `safety/`, and `platform/configs/safety`; `src/` never imports those packages.

## Known behavior differences

- The stateless service returns structured envelopes/cards/actions rather than legacy streaming prose.
- Stub catalog products differ from the live Milvus catalog; remote provider mode can point to the legacy search service.
- Safety rules implement the Round 3 domain policy (resale bulk block and tight-budget/high-value cooldown) rather than calling the legacy NeMo Guardrails service.
- Chat pronoun resolution is deterministic for the demo catalog in fallback mode; LLM triage resolves arbitrary entities when configured.
