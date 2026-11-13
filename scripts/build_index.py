"""문서 → 검색 인덱스 생성. Docker 빌드 단계에서 실행되어 이미지 안에 인덱스가 들어간다."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.rag import build_index  # noqa: E402

if __name__ == "__main__":
    n = build_index()
    print(f"인덱스 생성 완료: chunk {n}개 → {config.INDEX_PATH}")
