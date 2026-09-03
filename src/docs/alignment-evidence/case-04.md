# Alignment Case 04 — Legacy Search Evidence

- Collected: 2026-09-01T16:58:42+08:00
- Legacy endpoint: `POST http://localhost:8010/query/text`
- Required semantic input: “推荐酱酒”, context budget 20000 cents (CNY 200)
- Health immediately before request: `{"status":"healthy","timestamp":1788253086.7020679,"version":"1.0.0"}`

## Request

```http
POST /query/text HTTP/1.1
Host: localhost:8010
Content-Type: application/json

{"text":["推荐酱酒"],"categories":[],"filters":{"max_price":200,"currency":"CNY"},"k":10}
```

## Raw Response

```http
HTTP/1.1 500 Internal Server Error
date: Tue, 01 Sep 2026 08:58:42 GMT
server: uvicorn
content-length: 21
content-type: text/plain; charset=utf-8

Internal Server Error
```

## Notes

The live legacy process was healthy but returned HTTP 500 for this query. The equivalent Chinese probe with `/query/text` also returned 500. Restarting, killing, or inspecting its private process logs was prohibited by the task brief. No legacy successful result was available for this run. A fresh confirmation request at 2026-09-01T17:49:55+08:00 also returned the same raw HTTP 500 response shown above.

## src Semantic Outcome

With `budget_cents=20000`, `src` applies the budget as a maximum price and returns `ok: true`, `cards: []`, `total_hits: 0`, the friendly degradation message `预算范围内暂无匹配商品，可尝试放宽价格或预算。`, and a search action preserving the original query.

Semantic equivalence conclusion: not field-equivalent because the live legacy result was unavailable due to its HTTP 500. Against the specified behavior, `src` correctly avoids an error envelope, returns an empty structured result, and gives the user actionable refinement guidance.
