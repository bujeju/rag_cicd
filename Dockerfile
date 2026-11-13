FROM python:3.12-slim

WORKDIR /app

# 1) 의존성 먼저 설치 (코드만 바뀌면 이 레이어는 캐시 재사용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) 코드 + 문서 복사
COPY app ./app
COPY prompts ./prompts
COPY data ./data
COPY scripts ./scripts

# 3) 빌드 시점에 검색 인덱스 생성 → 이미지 안에 포함 (볼륨 불필요)
RUN python scripts/build_index.py

# 4) 이미지 버전 (CI에서 --build-arg APP_VERSION=<커밋해시>)
ARG APP_VERSION=local
ENV APP_VERSION=${APP_VERSION} \
    PYTHONUNBUFFERED=1

# 5) root 아닌 사용자로 실행
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
