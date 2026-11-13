"""환경변수로 모든 설정을 주입한다. (K8s에서는 ConfigMap/Secret → 환경변수)"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# LLM 설정: fake 모드는 API 키 없이도 동작 (실습/CI용)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "fake")          # fake | openai
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")          # 사용하는 모델명으로 변경
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") or None     # OpenAI 호환 API를 쓸 때

# 프롬프트 버전: prompts/system_{버전}.txt 파일을 읽는다
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v1")

# RAG 설정
TOP_K = int(os.getenv("TOP_K", "3"))
DOCS_DIR = BASE_DIR / "data" / "docs"
INDEX_PATH = BASE_DIR / "index" / "index.pkl"

# 배포 버전 (CI에서 커밋 해시를 넣어 빌드) → /version 으로 확인
APP_VERSION = os.getenv("APP_VERSION", "local")


def load_system_prompt() -> str:
    path = BASE_DIR / "prompts" / f"system_{PROMPT_VERSION}.txt"
    return path.read_text(encoding="utf-8")
