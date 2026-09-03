# 任务：8 个★对齐案例补实跑取证（HEAD=main=bf40ef8）

## 背景
工作指令附录 B 的 20 案例中有 8 个★（6/11/12/16/17/18/19/20）当时因旧栈 auth 502 被阻，只留了"受阻记录+走查"。**旧栈现已完全修复**（auth 可注册登录拿 token，四服务+Milvus 健康）。

## 环境（全部就绪，直接用）
- 旧栈 orchestrator: http://localhost:8009
  - 注册：POST /auth/register {"username":"align-r5-x","email":"...","password":"..."} → {"token":...}
  - 登录：POST /auth/login {"username","password"} → {"token":...}
  - 流式对话：POST /query/stream（带 Authorization: Bearer <token>，body 参考 openapi：curl http://localhost:8009/openapi.json 查 schema）
  - 购物车：GET/POST /cart/{user_id}（带 token）
- 旧栈 search: POST http://localhost:8010/query/text {"text":["..."],"categories":[],"filters":{...},"k":10}
- 新栈（被对齐方）：/home/spark/src/github/Symy-ai/Shopping-AI 分支 main（bf40ef8）
  - 起服务（逐字照做）：cd /home/spark/src/github/Symy-ai/Shopping-AI/src && KEY=$(grep -oP 'LLM_API_KEY=\K\S+' /tmp/start-8009.sh) && env -u ALL_PROXY -u all_proxy -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u SOCKS_PROXY -u socks_proxy NO_PROXY=localhost,127.0.0.1,open.bigmodel.cn no_proxy=localhost,127.0.0.1,open.bigmodel.cn SYMY_LLM_BASE_URL=https://open.bigmodel.cn/api/coding/paas/v4 SYMY_LLM_KEY=$KEY SYMY_LLM_MODEL=glm-4-flash PYTHONPATH=. nohup ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8910 >/tmp/qa-r5-svc.log 2>&1 &
  - 5 秒后 curl http://127.0.0.1:8910/health 验证

## 任务：8 个★案例逐一【旧栈实跑 + 新栈实跑】，双栈原始输出存证 + 语义等价判定
每个案例存 src/docs/alignment-evidence/r5/case-NN.md（NN=06/11/12/16/17/18/19/20），含：旧栈请求+原始响应、新栈请求+原始响应、语义等价结论（字段级对比；实现差异允许，语义不允许）

- ★06：旧栈 search "茅台镇酱酒" 相关两酱酒对比（如 /query/stream 文本"帮我对比两款酱酒"或两次 search 后人工对比）↔ 新栈 symy_compare a/b
- ★11：旧栈 POST /cart/{uid} 加购酱酒×1（带 token，用 align-r5-cart 用户）→ 响应含 image 字段 ↔ 新栈 symy_cart add（cart_lines.image_url）
- ★12：旧栈加购高价品+低预算设置（/context/{user_id} 或 config）→ 观察是否拦截/警告 ↔ 新栈 add 超预算 → 成功+BUDGET_EXCEEDED_WARNING（新栈不静默拦截）
- ★16：旧栈 /query/stream "我想买茅台"（预算紧）→ 原始回复流 ↔ 新栈 symy_chat 同句 → 降温草稿+warnings
- ★17：旧栈 "帮我比比A和B"（或两款具体酱酒）↔ 新栈 symy_chat compare
- ★18：旧栈 "把它放进购物车"（显式）↔ 新栈 symy_chat → cart_add action+回执
- ★19：旧栈 "我这个月还能花多少" ↔ 新栈 symy_chat 预算问答草稿
- ★20：旧栈 "帮我囤10箱酒转卖" → 拦截行为 ↔ 新栈 SAFETY_BLOCKED

## 注意
- 旧栈 /query/stream 是 SSE 流：curl -N 收全量后存原始片段；body schema 先查 openapi.json
- 语义等价判定标准：意图处理一致、结构化字段语义一致（价格/商品/动作/警告），文案措辞差异允许（不同 LLM）
- 每个案例都真实调用，不许走查替代；如某案例旧栈仍失败，原样存证+注明 blocker
- 测完：杀 8910；旧栈测试用户购物车清空（DELETE 或 remove 端点，查 openapi）

## 红线：不改任何代码、不碰旧栈服务进程（只调 API）、不 push
## 报告→/home/spark/briefs/qa-report-r5-alignment.md：8 案例结论矩阵 + 等价率 + 发现的行为差异清单
