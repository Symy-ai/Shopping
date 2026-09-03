# Alignment Case 01 — Legacy Search Evidence

- Collected: 2026-09-01T16:58:32+08:00
- Legacy endpoint: `POST http://localhost:8010/query/text`
- Required semantic input: “贵州酱香白酒”, CNY price 200–500
- Health immediately before request: `{"status":"healthy","timestamp":1788253086.69295,"version":"1.0.0"}`

## Request

```http
POST /query/text HTTP/1.1
Host: localhost:8010
Content-Type: application/json

{"text":["贵州酱香白酒"],"categories":[],"filters":{"min_price":200,"max_price":500,"currency":"CNY"},"k":10}
```

## Raw Response

```http
HTTP/1.1 500 Internal Server Error
date: Tue, 01 Sep 2026 08:58:32 GMT
server: uvicorn
content-length: 21
content-type: text/plain; charset=utf-8

Internal Server Error
```

## Notes

The live legacy process was healthy but returned HTTP 500 for this and several probe inputs. Restarting, killing, or inspecting its private process logs was prohibited by the task brief. The equivalent Chinese/English probes also returned 500. No legacy successful result was available for this run.

## src Semantic Outcome

`src` returns `ok: true`, two price-conforming baijiu cards, title, price, unit price/label, proxy image URL, source, marketplace URL, in-stock flag, and alcohol compliance marker. Filters 20000–50000 cents are reported in `applied_filters`.

Semantic equivalence conclusion: not field-equivalent because the live legacy result was unavailable due to its HTTP 500. Against the specified behavior, `src` correctly preserves the query intent, price bounds, card fields, image proxying, marketplace link, and structured envelope.
