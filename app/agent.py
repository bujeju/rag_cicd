"""간단한 도구 사용 에이전트.

도구 2개:
  - search_docs : 사내 문서 검색 (RAG)
  - get_today   : 오늘 날짜

LLM_PROVIDER=openai  → LLM이 어떤 도구를 쓸지 스스로 고른다 (function calling)
LLM_PROVIDER=fake    → 규칙 기반으로 흉내만 낸다 (API 키 없이 실습/CI 가능)
"""
import json
from datetime import datetime, timedelta, timezone

from app import config
from app.rag import Retriever

KST = timezone(timedelta(hours=9))
retriever = Retriever()


# ---------- 도구 ----------
def search_docs(query: str) -> list[dict]:
    return retriever.search(query)


def get_today() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d (%a)")


TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "search_docs",
            "description": "회사 정책/FAQ 문서에서 질문과 관련된 내용을 검색한다.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "검색어"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_today",
            "description": "오늘 날짜(한국 시간)를 알려준다.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def _call_tool(name: str, args: dict):
    if name == "search_docs":
        return search_docs(args.get("query", ""))
    if name == "get_today":
        return get_today()
    return f"알 수 없는 도구: {name}"


# ---------- 에이전트 실행 ----------
def run_agent(question: str) -> dict:
    if config.LLM_PROVIDER == "openai":
        return _run_openai(question)
    return _run_fake(question)


def _run_fake(question: str) -> dict:
    """LLM 없이 동작하는 가짜 에이전트. 검색 결과를 그대로 보여준다."""
    tool_calls, sources, parts = [], [], []

    if any(k in question for k in ["오늘", "날짜", "요일"]):
        tool_calls.append("get_today")
        parts.append(f"오늘은 {get_today()} 입니다.")

    tool_calls.append("search_docs")
    hits = search_docs(question)
    sources = [h["source"] for h in hits]
    parts.append(hits[0]["text"] if hits else "관련 문서를 찾지 못했습니다.")

    return {
        "answer": "[FAKE] " + "\n".join(parts),
        "sources": sources,
        "tool_calls": tool_calls,
        "top_score": hits[0]["score"] if hits else None,
        "usage": {"prompt_tokens": 0, "completion_tokens": 0},
    }


def _run_openai(question: str, max_steps: int = 3) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=config.OPENAI_API_KEY, base_url=config.OPENAI_BASE_URL)
    messages = [
        {"role": "system", "content": config.load_system_prompt()},
        {"role": "user", "content": question},
    ]
    tool_calls, sources, top_score = [], [], None
    usage = {"prompt_tokens": 0, "completion_tokens": 0}

    for _ in range(max_steps):
        resp = client.chat.completions.create(
            model=config.LLM_MODEL, messages=messages, tools=TOOLS_SPEC
        )
        if resp.usage:
            usage["prompt_tokens"] += resp.usage.prompt_tokens
            usage["completion_tokens"] += resp.usage.completion_tokens

        msg = resp.choices[0].message
        if not msg.tool_calls:                       # 도구 호출 없음 → 최종 답변
            return {"answer": msg.content, "sources": sources, "tool_calls": tool_calls,
                    "top_score": top_score, "usage": usage}

        messages.append(msg)
        for tc in msg.tool_calls:                     # 요청한 도구 실행 후 결과 전달
            args = json.loads(tc.function.arguments or "{}")
            result = _call_tool(tc.function.name, args)
            tool_calls.append(tc.function.name)
            if tc.function.name == "search_docs":
                sources += [r["source"] for r in result]
                if result:
                    top_score = max(top_score or 0, result[0]["score"])
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result, ensure_ascii=False)})

    return {"answer": "단계 제한에 도달했습니다.", "sources": sources, "tool_calls": tool_calls,
            "top_score": top_score, "usage": usage}
