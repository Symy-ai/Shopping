# Round 3 alignment evidence

## Live legacy captures

- `case-01-live-search.json`: legacy `POST /query/text` with `text=["贵州酱香白酒"]`, `filters={"min_price":200,"max_price":500}`, `k=5` returned two 358–398 CNY baijiu cards with image and marketplace URLs. The stateless stub returns two in-range baijiu cards with the same card dimensions; catalog items differ because `symy_search` defaults to its deterministic local catalog rather than live Milvus.
- `case-04-live-search.json`: legacy `POST /query/text` with `text=["推荐酱酒"]`, `filters={"max_price":200}`, `k=5` returned one 30 CNY result. The stateless stub returns zero cards and a friendly budget-relaxation action because its demo catalog has no in-budget baijiu. This is a catalog-data difference, not a semantic filter failure.

## Authorization blockers

- `legacy-auth-register-401.json` and `legacy-auth-login-401.json`: live `POST /auth/register` and `/auth/login` both returned `{"detail":"Failed to reach memory service"}` on 2026-09-02. The orchestrator health endpoint was healthy, but its configured memory dependency was unavailable. Required cases 6, 11, 12, and 16–20 therefore use the permitted fallback: legacy code walkthrough plus stateless semantic assertions in `src/tests/test_alignment.py`.
- No protected service was restarted, stopped, reconfigured, or otherwise modified. No authenticated cart operation was attempted without a token.

## End-to-end

- `e2e-four-tools.json`: all four tools (`symy_search`, `symy_compare`, `symy_cart`, `symy_chat`) returned `ok=true` over MCP HTTP on test port 8906. Cart actions succeeded with warning, checkout returned the snapshot, and chat produced a two-item comparison, compliance warning, and structured compare action.
- `e2e-server.log`: service lifecycle for the isolated test server.

## Code-walkthrough conclusions

Legacy cart confirmation and impulse behavior are in `orchestrator/app/agents/cartops/agent.py` and `orchestrator/app/agents/chatter.py`: successful add is followed by authoritative-cart confirmation; budget pressure gets a gentle cooldown; cart mutation happens only in the cart specialist. Legacy input safety is configured under `platform/configs/safety`. The stateless implementation mirrors those semantics as structured `reply_draft`, `actions`, and `warnings`, while keeping routing outside `symy_chat` LLM-free.
