"""RAG 품질 평가. CI에서 실행되어 점수가 기준보다 낮으면 배포를 막는다.

지표
  - retrieval_hit : 정답 문서가 검색 결과(TOP_K) 안에 있는가
  - answer_hit    : 답변에 기대 키워드가 들어 있는가

사용법
  python eval/run_eval.py                     # 기준: retrieval 0.8, answer 0.7
  MIN_RETRIEVAL=0.9 python eval/run_eval.py   # 기준 변경
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import config  # noqa: E402
from app.agent import run_agent  # noqa: E402

MIN_RETRIEVAL = float(os.getenv("MIN_RETRIEVAL", "0.8"))
MIN_ANSWER = float(os.getenv("MIN_ANSWER", "0.7"))


def main() -> int:
    cases = [json.loads(line) for line in (ROOT / "eval" / "eval_set.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    rows, r_hits, a_hits = [], 0, 0

    for c in cases:
        out = run_agent(c["question"])
        r_ok = c["expected_source"] in out["sources"]
        a_ok = all(k in (out["answer"] or "") for k in c["expected_keywords"])
        r_hits += r_ok
        a_hits += a_ok
        rows.append({"question": c["question"], "retrieval_hit": r_ok, "answer_hit": a_ok,
                     "sources": out["sources"]})
        print(f"{'O' if r_ok else 'X'}{'O' if a_ok else 'X'}  {c['question']}  → {out['sources']}")

    n = len(cases)
    report = {
        "app_version": config.APP_VERSION,
        "prompt_version": config.PROMPT_VERSION,
        "llm_provider": config.LLM_PROVIDER,
        "top_k": config.TOP_K,
        "retrieval_hit_rate": round(r_hits / n, 2),
        "answer_hit_rate": round(a_hits / n, 2),
        "cases": rows,
    }
    (ROOT / "eval" / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nretrieval_hit_rate = {report['retrieval_hit_rate']} (기준 {MIN_RETRIEVAL})")
    print(f"answer_hit_rate    = {report['answer_hit_rate']} (기준 {MIN_ANSWER})")

    if report["retrieval_hit_rate"] < MIN_RETRIEVAL or report["answer_hit_rate"] < MIN_ANSWER:
        print("❌ 평가 기준 미달 → 배포 중단")
        return 1
    print("✅ 평가 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
