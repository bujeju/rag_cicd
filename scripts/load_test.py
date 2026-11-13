"""Grafana 그래프를 움직이기 위한 간단한 부하 발생기.

사용법:
  python scripts/load_test.py                         # http://localhost:8000, 60초
  python scripts/load_test.py http://localhost:8000 120
"""
import random
import sys
import time

import httpx

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
SECONDS = int(sys.argv[2]) if len(sys.argv) > 2 else 60

QUESTIONS = [
    "반품은 며칠 안에 해야 하나요?", "무료배송 기준이 얼마예요?", "A/S 접수 방법 알려줘",
    "골드 등급 적립률은?", "오늘 날짜 알려줘", "제주도 배송 며칠 걸려요?",
    "회사 주차장 있나요?",            # 문서에 없는 질문 → 검색 유사도가 낮게 나온다
]

end = time.time() + SECONDS
n = 0
with httpx.Client(timeout=30) as client:
    while time.time() < end:
        q = random.choice(QUESTIONS)
        r = client.post(f"{URL}/chat", json={"question": q})
        n += 1
        print(f"[{n}] {r.status_code} {r.json().get('latency_ms')}ms  {q}")
        time.sleep(random.uniform(0.2, 1.0))
print(f"완료: {n}건")
