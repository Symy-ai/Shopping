# Case 20 alignment evidence

- Generated: 2026-09-03T20:22:41.679783+08:00
- Execution status: **PASS**
- Semantic alignment: **EQUIVALENT**
- Old stack: orchestrator/search APIs on localhost:8009/8010, authenticated read-only calls only
- New stack: MCP API on 127.0.0.1:8910 (service stopped after evidence collection)
- Raw environment/exit/timestamp evidence: `raw/`

## Commands and artifacts

The execution driver used Python HTTP/SSE requests with proxy variables unset and `NO_PROXY=localhost,127.0.0.1`. Each request records method, host, path, full request body, status, raw stdout/body, timestamps, and transport errors.

- Legacy raw: `raw/case-20.legacy.json`
- New raw: `raw/case-20.new.json`

## Legacy request and raw response

See `raw/case-20.legacy.json`. The `body` field contains the complete unmodified JSON or SSE stream; `meta` contains the full request and start/finish timestamps.

## New request and raw response

See `raw/case-20.new.json`. The `body` field contains the complete MCP SSE envelope; `parsed_tool_result` contains the complete parsed tool JSON payload.

## Field-level semantic comparison

Both refuse resale hoarding. Legacy refuses in prose as out-of-scope; new returns SAFETY_BLOCKED with no actions. Refusal semantics match; structure differs.

## Consistent items

- Both systems were actually invoked over their real HTTP APIs.
- Both returned successful transport/status 200 responses for the case calls.
- Alcohol/adult-consumption context and image fields are retained where present in raw evidence.

## Differences

- None beyond response schema/wording differences.
