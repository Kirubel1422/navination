"""An OpenAI-compatible HTTP server backed by the ScriptedModel. FOR TESTS AND OFFLINE DEMOS ONLY.

Run:  uv run uvicorn devtools.fake_llm_server:app --port 8002
Then point the API at it: AI_PROVIDER_BASE_URL=http://127.0.0.1:8002/v1, AI_MODEL=scripted-test-model,
AI_API_KEY=test. The real OpenAI-compatible adapter is used end to end; only the "model" is fake.
"""

import time
from typing import Any

from fastapi import FastAPI, Request

from devtools.scripted_model import ScriptedModel

app = FastAPI(title="NaviNation scripted test model (not an AI)")
model = ScriptedModel()


@app.get("/v1/models")
def models() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [{"id": model.name, "object": "model", "owned_by": "navination-tests"}],
    }


@app.post("/v1/chat/completions")
async def chat(request: Request) -> dict[str, Any]:
    body = await request.json()
    turn = model.complete(body["messages"], body.get("tools") or [], body.get("response_format"))
    message: dict[str, Any] = {"role": "assistant", "content": turn.content}
    if turn.tool_calls:
        message["tool_calls"] = [
            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
            for c in turn.tool_calls
        ]
    return {
        "id": f"chatcmpl-{int(time.time() * 1000)}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.get("model", model.name),
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "tool_calls" if turn.tool_calls else "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
