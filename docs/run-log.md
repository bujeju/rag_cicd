# 실습 실행 기록 (run-log)

교안 캡처·설명용으로 단계별 실행 명령과 핵심 출력, 문제 해결 과정을 남긴다.
환경: Windows 10 Pro, PowerShell 5.1 / Git Bash.

---

## 단계 0. 정리 및 환경 점검 (2026-11-13)

### 정리
```powershell
Remove-Item rag_cicd.tar.gz      # 전송용 임시 파일 삭제
```
- `.gitignore`에 `kubeconfig*`, `*.tar.gz` 추가 (kubeconfig가 실수로 커밋되지 않도록).
- `.env`는 이미 `.gitignore`/`.dockerignore`에 포함되어 있음을 확인.

### 도구 버전
| 도구 | 명령 | 결과 |
|---|---|---|
| Python | `python --version` | 3.14.8 (기본) / `py -0p`로 **3.12**도 설치되어 있음 확인 |
| Git | `git --version` | 2.56.0.windows.3 |
| Docker | `docker version` | Client 29.8.1 / Server 29.8.1 (Docker Desktop 실행 중) |
| kubectl | `kubectl version --client` | v1.36.1 (Kustomize v5.8.1) |
| GitHub CLI | `gh --version` | **없음** → 설치 |

### 문제와 해결
- **gh 미설치**: `winget install --id GitHub.cli -e` → gh 2.104.0 설치.
  설치 직후 열려 있던 터미널에서는 PATH가 갱신되지 않아 `gh`를 못 찾을 수 있다 → **새 터미널을 열거나**
  `"C:\Program Files\GitHub CLI\gh.exe"` 전체 경로로 실행.
- **Python 버전**: 기본 python이 3.14인데 Dockerfile·CI는 3.12를 쓴다.
  `scikit-learn==1.5.*` 등이 3.14용 wheel을 제공하지 않을 수 있으므로 로컬 venv도 **3.12로 맞춘다** (`py -3.12 -m venv .venv`).

---

## 단계 1. 로컬 실행 (README 실습 0)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
$env:PYTHONUTF8=1                 # 한글 출력 깨짐 방지
python scripts/build_index.py
pytest -q
python eval/run_eval.py
```

설치된 주요 패키지: fastapi 0.115.14, uvicorn 0.32.1, scikit-learn 1.5.2, openai 1.109.1, prometheus_client 0.21.1, pytest 8.4.2, httpx 0.27.2

```
인덱스 생성 완료: chunk 8개 → C:\rag_cicd\index\index.pkl
.....  5 passed, 1 warning in 2.04s     # warning: starlette의 anyio DeprecationWarning (무시 가능)

OO  반품은 며칠 안에 신청해야 하나요?  → ['refund.md', 'shipping.md', 'refund.md']
... (10문항 모두 OO)
retrieval_hit_rate = 1.0 (기준 0.8)
answer_hit_rate    = 1.0 (기준 0.7)
✅ 평가 통과
```

### 서버 실행과 엔드포인트 확인
```powershell
uvicorn app.main:app --port 8000
```
PowerShell 5.1에서 한글 JSON을 보낼 때는 **UTF-8 바이트로 변환해서** 보내야 한다
(`Invoke-RestMethod -Body '{"question":"..."}'`는 기본 인코딩 때문에 한글이 깨짐).
```powershell
$body = [Text.Encoding]::UTF8.GetBytes((@{question="반품은 며칠 안에 신청해야 하나요?"} | ConvertTo-Json))
Invoke-RestMethod http://localhost:8000/chat -Method Post -ContentType "application/json; charset=utf-8" -Body $body
```
(또는 브라우저에서 http://localhost:8000/docs 의 Swagger UI 사용 — 교안에서는 이쪽이 더 쉽다)

| 호출 | 응답 (요약) |
|---|---|
| `GET /health` | `{"status":"ok"}` |
| `GET /version` | `{"app_version":"local","prompt_version":"v1","llm_provider":"fake","llm_model":"gpt-4o-mini"}` |
| `POST /chat` "반품은 며칠 안에 신청해야 하나요?" | answer: `[FAKE] # 반품 및 환불 정책 상품 수령 후 14일 이내에…`, sources `refund.md, shipping.md, refund.md`, top_score **0.244** |
| `POST /chat` "골드 등급 적립률은 몇 퍼센트인가요?" | answer: `[FAKE] # 회원 등급 및 적립금 … 골드는 3%…`, sources `membership.md…`, top_score **0.331** |
| `POST /chat` "회사 주차장 있나요?" (문서에 없는 질문) | 엉뚱한 `shipping.md` 내용, top_score **0.105** → 낮은 유사도 = 문서 없음 신호 |

서버 터미널(stderr)에 찍힌 JSON 로그:
```json
{"event": "chat", "request_id": "f3ddcb62", "app_version": "local", "prompt_version": "v1", "model": "fake", "question": "반품은 며칠 안에 신청해야 하나요?", "tool_calls": ["search_docs"], "sources": ["refund.md", "shipping.md", "refund.md"], "top_score": 0.244, "latency_ms": 1, "prompt_tokens": 0, "completion_tokens": 0}
{"event": "chat", "request_id": "135dca33", "app_version": "local", "prompt_version": "v1", "model": "fake", "question": "골드 등급 적립률은 몇 퍼센트인가요?", "tool_calls": ["search_docs"], "sources": ["membership.md", "membership.md", "refund.md"], "top_score": 0.331, "latency_ms": 1, "prompt_tokens": 0, "completion_tokens": 0}
{"event": "chat", "request_id": "a059d344", "app_version": "local", "prompt_version": "v1", "model": "fake", "question": "회사 주차장 있나요?", "tool_calls": ["search_docs"], "sources": ["shipping.md", "membership.md", "refund.md"], "top_score": 0.105, "latency_ms": 1, "prompt_tokens": 0, "completion_tokens": 0}
```
→ 서버 종료 (Ctrl+C).

### 문제와 해결
- 특별한 실패 없음. 단, 기본 Python 3.14로 venv를 만들면 고정된 scikit-learn 1.5 wheel이 없어 소스 빌드를 시도할 수 있으므로 3.12 사용을 권장.

---

## 단계 2. Docker (README 실습 1)

```powershell
docker build -t rag-app:local --build-arg APP_VERSION=local .
```
```
#14 [10/10] RUN useradd -m appuser && chown -R appuser /app
#15 naming to docker.io/library/rag-app:local done
```
- 빌드 성공 (첫 빌드 약 44초). `requirements.txt`/`Dockerfile` 수정 없음.
- 이미지 크기: `docker images rag-app:local` → **649MB**
  (python:3.12-slim + scikit-learn/numpy/scipy + openai SDK. 실습용으로는 허용 범위. 줄이려면 멀티스테이지 빌드 또는 TF-IDF 대신 순수 Python 검색 — 교안 토론 거리)

```powershell
docker run -d --name rag-local -p 8000:8000 rag-app:local
```
| 호출 | 응답 (요약) |
|---|---|
| `GET /health` | `{"status":"ok"}` |
| `GET /version` | `{"app_version":"local","prompt_version":"v1","llm_provider":"fake","llm_model":"gpt-4o-mini"}` |
| `POST /chat` "환불은 언제 처리되나요?" | `[FAKE] 환불은 반품 상품이 물류센터에 도착하여 검수가 끝난 뒤 영업일 기준 3일 이내에…`, top_score 0.235 |
| `POST /chat` "A/S 접수는 어디서 하나요?" | `[FAKE] A/S 접수는 고객센터 1588-0000 또는 홈페이지 [A/S 신청] 메뉴에서…`, top_score 0.451 |

`docker logs rag-local`:
```
INFO:     Started server process [1]
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     172.17.0.1:53536 - "POST /chat HTTP/1.1" 200 OK
{"event": "chat", "request_id": "b6281afc", "app_version": "local", "prompt_version": "v1", "model": "fake", "question": "환불은 언제 처리되나요?", "tool_calls": ["search_docs"], "sources": ["refund.md", "refund.md", "shipping.md"], "top_score": 0.235, "latency_ms": 3, "prompt_tokens": 0, "completion_tokens": 0}
{"event": "chat", "request_id": "3431d2cc", "app_version": "local", "prompt_version": "v1", "model": "fake", "question": "A/S 접수는 어디서 하나요?", "tool_calls": ["search_docs"], "sources": ["warranty.md", "warranty.md", "refund.md"], "top_score": 0.451, "latency_ms": 2, "prompt_tokens": 0, "completion_tokens": 0}
```
- `docker inspect rag-local --format "{{.Config.User}}"` → `appuser` (root 아님 확인)

```powershell
docker rm -f rag-local
```

### 문제와 해결
- 실패 없음.
- 참고: PowerShell 5.1에서 `docker logs ... 2>&1`을 쓰면 uvicorn이 stderr로 쓴 줄이 빨간 `NativeCommandError`로 감싸져 에러처럼 보인다. 실제 에러가 아니다 → `2>&1` 없이 `docker logs rag-local`만 실행하면 된다.

---

## 단계 2-1. 로컬 모니터링 (README 실습 1-1)

```powershell
cd monitoring; docker compose up -d --build
docker compose ps
```
```
SERVICE      STATE     PORTS
grafana      running   0.0.0.0:3000->3000/tcp
prometheus   running   0.0.0.0:9090->9090/tcp
rag-app      running   0.0.0.0:8000->8000/tcp
```

### Prometheus Targets
`curl http://localhost:9090/api/v1/targets` → `{'instance': 'rag-app:8000', 'job': 'rag-app'} up` ✅

### 부하 발생
```powershell
python scripts/load_test.py http://localhost:8000 120
```
```
[1] 200 1ms  골드 등급 적립률은?
[2] 200 2ms  회사 주차장 있나요?
...
완료: 188건
```

### Grafana 대시보드 프로비저닝 확인
`curl -u admin:admin "http://localhost:3000/api/search?query=RAG"`
→ `{"uid":"rag-llmops","title":"RAG LLMOps","url":"/d/rag-llmops/rag-llmops","folderTitle":"LLMOps","tags":["llmops"]}` ✅

### 패널별 쿼리 확인 (Prometheus API, `$namespace` = `local`)
| 패널 | 결과 |
|---|---|
| 요청/초 | 1.47 |
| p95 응답시간 | 0.0095 s |
| 에러율 | 0 |
| 토큰/분 | 0 (fake 모드라 정상. "No data"가 아니라 0으로 나옴) |
| 실행 중인 버전 (파드별) | `app_version=local-compose, prompt_version=v1, llm_provider=fake, model=fake, namespace=local` |
| 버전별 요청 수 | `local-compose` 1.47 req/s |
| 버전별 응답시간 p50 / p95 | 0.005 s / 0.0095 s |
| 검색 품질: 1위 문서 유사도 중앙값 | 0.196 ~ 0.215 |
| 도구 호출 | search_docs 1.47/s, get_today 0.25~0.33/s |
| 토큰 사용량 (모델별) | fake/prompt 0, fake/completion 0 |
| 상태별 요청 | ok 1.47/s |

### 문제와 해결
- **대시보드 `namespace` 드롭다운이 비어 있음**: 대시보드 변수는 `label_values(rag_app_info, namespace)`인데,
  클러스터에서는 Prometheus relabel로 `namespace` 라벨이 붙지만 로컬 compose의 static_config에는 없다
  (`/api/v1/label/namespace/values` → `[]`).
  → `monitoring/prometheus.local.yml`의 static_config에 `labels: {namespace: local}` 추가 →
  `docker compose restart prometheus` → `["local"]` 확인. 로컬에서도 클러스터와 같은 방식으로 드롭다운 사용 가능.
- PowerShell에서 `docker compose ... 2>&1`의 진행 메시지가 빨간 에러처럼 보이지만 정상 출력이다.

### 브라우저 확인과 정리
- 사용자가 http://localhost:3000 → Dashboards → LLMOps → **RAG LLMOps**에서 패널이 정상으로 보이는 것을 확인함 (부하 발생기를 돌리는 동안).
- `docker compose down` → 컨테이너와 네트워크 정리 완료.

---

## 단계 3. Git / GitHub (실습 2의 1~3)

### 첫 커밋
```powershell
git config --local user.name "bujeju"
git config --local user.email "<GitHub noreply 이메일>"   # 공개 저장소라 실제 이메일 대신 noreply 사용
git add docs/screenshots
git commit -m "init: LLMOps RAG lab skeleton"
```
- 결과: `bbed9d5 init: LLMOps RAG lab skeleton` (44 files)
- 막힌 점: 새 PC에서는 `user.name`/`user.email`이 비어 있어 커밋이 안 된다. 공개 저장소는 커밋 이메일이 그대로 공개되므로
  GitHub → Settings → Emails의 `<ID>+<username>@users.noreply.github.com`를 권장.

### 저장소 생성과 push
```powershell
gh auth login --hostname github.com --git-protocol https --web   # 처음엔 "not logged into any GitHub hosts"
gh auth status                                                   # ✓ Logged in ... scopes: repo, workflow, ...
gh repo view bujeju/rag_cicd                                     # 없음 확인 (기존 저장소와 이름 충돌 방지)
gh repo create rag_cicd --public --source . --remote origin
git remote -v                                                    # origin https://github.com/bujeju/rag_cicd.git (push 전 확인)
git push -u origin main
```
- PowerShell에서 `gh api user --jq '"\(.login)"'` 같은 jq 문자열 보간은 따옴표 처리 때문에 실패한다 → `--jq '.login, .id'`처럼 단순하게 쓴다.

### main push로 CD 자동 실행 (run 43365630369)
| job | 결과 |
|---|---|
| test-and-eval | ✓ `5 passed`, `retrieval_hit_rate = 1.0 (기준 0.8)`, `answer_hit_rate = 1.0 (기준 0.7)` |
| build-and-push | ✓ `ghcr.io/bujeju/rag_cicd:bbed9d5` |
| deploy-dev | ✗ `kubeconfig 설정` 단계: `The connection to the server localhost:8080 was refused` |
| deploy-prod | 건너뜀 |

- **원인**: `KUBE_CONFIG` Secret이 아직 없다 (단계 5에서 등록). kubeconfig가 비면 kubectl은 기본값 `localhost:8080`에 접속하려 한다.
  → 이 에러 메시지를 보면 "Secret 미등록/잘못된 base64"를 먼저 의심하면 된다.
- 경고: Actions의 Node.js 20 deprecation 안내가 나오지만 실행에는 영향 없음.

### environments와 main 브랜치 보호 (gh api)
```bash
gh api -X PUT repos/bujeju/rag_cicd/environments/dev
gh api -X PUT repos/bujeju/rag_cicd/environments/production
gh api -X PUT repos/bujeju/rag_cicd/branches/main/protection --input bp.json
# bp.json: required_status_checks.contexts=["test-and-eval"], required_approving_review_count=1, enforce_admins=false
```
- 결과: `dev`, `production` 생성 / `{"approvals":1,"checks":["test-and-eval"],"enforce_admins":false}`
- 주의: PR 작성자는 자기 PR을 승인할 수 없다. 혼자 실습하면 승인 1이 병합을 막으므로 짝이 승인하거나,
  관리자는 `enforce_admins=false`라서 `gh pr merge --admin`으로 우회할 수 있다 (교안에서는 우회하지 않는 흐름을 권장).
- production required reviewer: 짝이 없어 본인 계정(`bujeju`)으로 지정, `prevent_self_review=false` (본인이 배포 승인 가능).

---

## 단계 4. CI 동작 확인 (실습 4-3 축소판)
