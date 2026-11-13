"""Prometheus 지표. /metrics 로 노출되고 Prometheus가 수집 → Grafana에서 본다.

라벨에 app_version / prompt_version 을 넣었기 때문에
배포·롤백 순간 그래프에서 '버전이 바뀌는 것'이 그대로 보인다.
"""
from prometheus_client import Counter, Gauge, Histogram

from app import config

REQUESTS = Counter(
    "rag_requests_total", "채팅 요청 수",
    ["app_version", "prompt_version", "model", "status"],
)
LATENCY = Histogram(
    "rag_request_latency_seconds", "채팅 응답 시간(초)",
    ["app_version"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20),
)
TOKENS = Counter(
    "rag_tokens_total", "LLM 토큰 사용량",
    ["model", "type"],                       # type = prompt | completion
)
TOOL_CALLS = Counter(
    "rag_tool_calls_total", "에이전트 도구 호출 수",
    ["tool"],
)
RETRIEVAL_TOP_SCORE = Histogram(
    "rag_retrieval_top_score", "검색 1위 문서 유사도 (낮으면 '문서에 없는 질문'일 가능성)",
    buckets=(0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0),
)
APP_INFO = Gauge(
    "rag_app_info", "현재 실행 중인 버전 정보 (값은 항상 1)",
    ["app_version", "prompt_version", "llm_provider", "model"],
)


def model_name() -> str:
    return config.LLM_MODEL if config.LLM_PROVIDER != "fake" else "fake"


def init_info() -> None:
    APP_INFO.labels(config.APP_VERSION, config.PROMPT_VERSION,
                    config.LLM_PROVIDER, model_name()).set(1)
