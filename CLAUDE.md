# CLAUDE.md — rag_cicd 작업 지시서

이 저장소는 **LLMOps 교안용 실습 저장소**다. 목표는 RAG 에이전트를
"로컬 → Docker → Git/GitHub → CI/CD → 가비아 쿠버네티스 클러스터 → Grafana 관찰"까지 한 바퀴 돌리는 것.
코드는 일부러 단순하게 유지한다. 기능을 늘리지 말고, **돌아가게 만들고 검증하는 것**이 목적이다.

## 환경
- Windows PC. 셸 명령은 PowerShell 기준. `scripts/deploy.sh`는 **Git Bash**로 실행한다.
- 기본 `LLM_PROVIDER=fake` (API 키 없이 동작). 키를 요구하지 말 것.
- 구조와 실습 순서는 `README.md` 참고.

## 규칙
1. **비밀값 금지**: API 키, kubeconfig, PAT를 파일에 쓰거나 커밋하지 않는다. `.env`, `kubeconfig*`는 Git에 올리지 않는다.
2. **사용자 확인 후 진행**: GitHub 저장소 생성(공개 여부), `git push`, 클러스터에 `kubectl apply`, GHCR 패키지 공개 전환, 파일 삭제.
3. 코드 구조나 실습 시나리오를 바꿔야 하면 먼저 이유를 설명하고 묻는다. 버그 수정은 바로 해도 된다.
4. 단계마다 실행한 명령과 핵심 출력을 `docs/run-log.md`에 남긴다 (교안 캡처·설명용). 실패와 해결 과정도 적는다.
5. 한 단계가 끝나면 짧게 보고하고 다음 단계로 넘어간다.

## 작업 순서

### 단계 0. 정리 및 환경 점검
- 루트의 `rag_cicd.tar.gz` 삭제 (전송용 임시 파일).
- 버전 확인: `python --version`, `git --version`, `docker version`, `kubectl version --client`, `gh --version`.
- 없는 도구는 설치 방법을 안내하고(winget 등) 설치 여부를 묻는다. Docker Desktop은 실행 중이어야 한다.

### 단계 1. 로컬 실행 (README 실습 0)
- `.venv` 생성 → `pip install -r requirements.txt` → `python scripts/build_index.py` → `pytest -q` → `python eval/run_eval.py`
- `uvicorn app.main:app --port 8000`을 띄우고 `/health`, `/version`, `/chat`(질문 2개 이상) 호출 → 응답과 JSON 로그 기록 → 서버 종료.
- Windows에서 한글 출력이 깨지면 `$env:PYTHONUTF8=1`로 해결.

### 단계 2. Docker (README 실습 1)
- `docker build -t rag-app:local --build-arg APP_VERSION=local .`
- `docker run -d --name rag-local -p 8000:8000 rag-app:local` → 엔드포인트 3개 확인 → `docker logs rag-local`에서 JSON 로그 확인.
- 이미지 크기 기록. 컨테이너 정리 (`docker rm -f rag-local`).
- 빌드가 실패하면 원인을 고치고 `requirements.txt`/`Dockerfile` 수정 내용을 run-log에 적는다.

### 단계 2-1. 로컬 모니터링 (README 실습 1-1)
- `cd monitoring; docker compose up -d --build`
- Prometheus http://localhost:9090/targets 에서 rag-app이 UP인지 확인 (API: `/api/v1/targets`)
- `python scripts/load_test.py http://localhost:8000 120` 실행
- Grafana http://localhost:3000 (admin/admin)의 "LLMOps / RAG LLMOps" 대시보드가 프로비저닝되었는지 API로 확인:
  `curl -u admin:admin "http://localhost:3000/api/search?query=RAG"`
- 패널별 쿼리가 값을 돌려주는지 Prometheus API로 확인하고 run-log에 기록 (No data 패널이 있으면 원인 수정)
- 사용자에게 브라우저로 대시보드를 열어 확인하라고 안내 → 확인되면 `docker compose down`

### 단계 3. Git / GitHub (README 실습 2의 1~3)
- `git init -b main` → 첫 커밋 ("init: LLMOps RAG lab skeleton").
- `gh auth status` 확인 → 사용자에게 **저장소 이름과 공개 여부를 물은 뒤** `gh repo create`로 생성하고 push.
- `gh`로 할 수 있으면 설정:
  - environments: `dev`, `production` (production의 required reviewer는 사용자에게 짝의 GitHub ID를 물어 설정)
  - main 브랜치 보호: PR 필수, 승인 1, status check `test-and-eval` 필수
- `gh`로 안 되는 항목은 웹에서 할 순서를 정리해서 알려준다.

### 단계 4. CI 동작 확인 (README 실습 4-3 축소판)
- 브랜치 `test/ci-check`에서 README에 한 줄을 추가 → PR → CI 통과 확인.
- 브랜치 `test/break-eval`에서 `data/docs/refund.md` 삭제 → PR → **CI가 평가에서 실패하는지 확인** → PR 닫고 브랜치 삭제.
- 결과(Actions 로그의 평가 점수)를 run-log에 기록.

### 단계 5. 클러스터 연결 — 사용자가 kubeconfig 경로를 알려준 뒤에만
- `$env:KUBECONFIG=<경로>` → `kubectl get nodes`, `kubectl get ingressclass`, `kubectl get storageclass`, `kubectl auth can-i create deployments -n dev`
- 결과에 맞춰 수정: Ingress Controller가 있으면 `k8s/ingress.yaml`의 `ingressClassName`, 없으면 `k8s/service.yaml`을 `type: LoadBalancer`로 (또는 port-forward 사용).
- GitHub Secret 등록: kubeconfig를 base64로 바꿔 `gh secret set KUBE_CONFIG` (값을 화면/파일에 남기지 말 것).
- **API 서버 접근성 확인**: GitHub Actions(외부)에서 클러스터에 접속 가능한지 사용자에게 가비아 설정(공인 엔드포인트/IP 허용)을 확인하도록 요청. 막혀 있으면 대안(클러스터 내 self-hosted runner, ArgoCD)을 정리해 보고만 하고 진행은 묻는다.

### 단계 6. 첫 배포 (README 실습 3)
- main에 push된 상태에서 CD 실행 확인 (`gh run watch`).
- `ImagePullBackOff`면 GHCR 패키지 공개 전환을 사용자에게 묻거나 `ghcr-pull` Secret 방식 안내.
- `kubectl get pods -n dev`, `kubectl port-forward svc/rag-app 8000:80 -n dev`, `/version`의 커밋 해시 확인.
- production 승인 후 prod 확인.

### 단계 6-1. 클러스터 모니터링 (README 실습 3-1)
- 먼저 `kubectl auth can-i create clusterrole` 확인 (Prometheus가 ClusterRole 필요). 안 되면 보고하고 대안을 묻는다.
- Grafana 비밀번호를 사용자에게 묻거나 무작위로 만들어 **화면에만 한 번** 보여준다 (파일에 저장 금지).
- `GRAFANA_PASSWORD=... bash scripts/deploy-monitoring.sh` (Git Bash)
- port-forward로 Prometheus Targets에서 dev/prod 파드가 UP인지, Grafana 대시보드가 보이는지 확인.

### 단계 7. 수정 → 재배포 → 롤백 (README 실습 4-1, 4-2, 5)
- 4-1: `data/docs/event.md` 추가 + 평가셋 1문항 추가 → PR → 병합 → 배포 → 새 질문에 답하는지 확인.
- 4-2: `prompts/system_v2.txt` 추가 + ConfigMap `PROMPT_VERSION: "v2"` → 배포 → `/version` 확인.
- 5: `kubectl rollout history` → `kubectl rollout undo -n prod` → `/version`이 이전 해시인지 확인 → `git revert`로 Git도 맞추는 흐름까지.
- 배포·롤백하는 동안 `scripts/load_test.py`를 계속 돌려서, Grafana "버전별 요청 수"와 "실행 중인 버전"에서 버전이 바뀌는 시각을 run-log에 기록 (교안 캡처 포인트).

## 완료 기준
- `docs/run-log.md`에 단계 0~7의 명령/결과/문제 해결이 정리되어 있다.
- Grafana에서 배포와 롤백 순간이 보이는 것을 확인했다.
- 교안에 넣을 캡처 포인트(어느 화면을 캡처하면 좋은지) 목록이 run-log 끝에 있다.
- 실습생이 막힐 만한 지점이 README의 "자주 막히는 곳" 표에 추가되어 있다.
