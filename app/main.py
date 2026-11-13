"""API 서버.

GET  /health   → K8s readiness/liveness probe 용
GET  /version  → 지금 떠 있는 버전 확인 (배포/롤백 확인용)
GET  /metrics  → Prometheus 지표 (Grafana 대시보드용)
POST /chat     → {"question": "..."} 에 답한다
"""
import json
import logging
import time
import uuid

from fastapi import FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel

from app import config, metrics
from app.agent import run_agent

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("llmops")

app = FastAPI(title="LLMOps RAG Lab")
metrics.init_info()


class ChatRequest(BaseModel):
    question: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def prometheus_metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/version")
def version():
    return {
        "app_version": config.APP_VERSION,
        "prompt_version": config.PROMPT_VERSION,
        "llm_provider": config.LLM_PROVIDER,
        "llm_model": config.LLM_MODEL,
    }


@app.post("/chat")
def chat(req: ChatRequest):
    request_id = uuid.uuid4().hex[:8]
    model = metrics.model_name()
    start = time.perf_counter()

    try:
        result = run_agent(req.question)
    except Exception as e:  # LLM API 장애 등 → 에러 지표로 남긴다
        metrics.REQUESTS.labels(config.APP_VERSION, config.PROMPT_VERSION, model, "error").inc()
        log.error(json.dumps({"event": "chat_error", "request_id": request_id,
                              "app_version": config.APP_VERSION, "error": str(e)}, ensure_ascii=False))
        raise HTTPException(status_code=502, detail="LLM 호출 실패") from e

    elapsed = time.perf_counter() - start
    latency_ms = round(elapsed * 1000)

    # --- Prometheus 지표 (Grafana) ---
    metrics.REQUESTS.labels(config.APP_VERSION, config.PROMPT_VERSION, model, "ok").inc()
    metrics.LATENCY.labels(config.APP_VERSION).observe(elapsed)
    metrics.TOKENS.labels(model, "prompt").inc(result["usage"]["prompt_tokens"])
    metrics.TOKENS.labels(model, "completion").inc(result["usage"]["completion_tokens"])
    for tool in result["tool_calls"]:
        metrics.TOOL_CALLS.labels(tool).inc()
    if result.get("top_score") is not None:
        metrics.RETRIEVAL_TOP_SCORE.observe(result["top_score"])

    # --- 요청별 JSON 로그 (무엇을, 어떤 버전으로, 얼마나 걸려, 얼마나 썼는지) ---
    log.info(json.dumps({
        "event": "chat",
        "request_id": request_id,
        "app_version": config.APP_VERSION,
        "prompt_version": config.PROMPT_VERSION,
        "model": model,
        "question": req.question,
        "tool_calls": result["tool_calls"],
        "sources": result["sources"],
        "top_score": result.get("top_score"),
        "latency_ms": latency_ms,
        **result["usage"],
    }, ensure_ascii=False))

    return {"request_id": request_id, **result, "latency_ms": latency_ms}
