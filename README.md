# LLMOps 실습: RAG 에이전트를 Git → CI/CD → 쿠버네티스(가비아)로

목표는 어려운 AI가 아니라 **"수정 → 검증 → 배포 → 롤백" 한 바퀴**를 직접 돌려 보는 것입니다.
혼자서 컨테이너 클러스터 1개를 사용해 진행합니다.

```
[로컬 수정] → git push (feature 브랜치) → PR → 셀프 리뷰 + CI(테스트·RAG 평가)
   → main 병합 → CD: 이미지 빌드(태그=커밋해시) → GHCR push
   → dev 네임스페이스 자동 배포 → 본인 승인 → prod 배포
   → Grafana 대시보드로 버전·지연시간·검색 품질 관찰
   → 문제 시 kubectl rollout undo
```

## 구성

| 경로 | 내용 |
|---|---|
| `app/main.py` | FastAPI: `/health`, `/version`, `/chat`, `/metrics` + 요청별 JSON 로그 |
| `app/metrics.py` | Prometheus 지표 (요청 수, 응답시간, 토큰, 도구 호출, 검색 유사도, 버전 정보) |
| `app/agent.py` | 도구 2개(`search_docs`, `get_today`)를 쓰는 에이전트. `fake` / `openai` 모드 |
| `app/rag.py` | 문서 → chunk → TF-IDF 검색 (가장 단순한 RAG) |
| `prompts/system_v1.txt` | 시스템 프롬프트 (Git으로 버전 관리) |
| `data/docs/*.md` | 가상의 '하늘전자' 고객센터 문서 4개 |
| `eval/` | 평가셋 10문항 + 평가 스크립트 (기준 미달 시 배포 중단) |
| `Dockerfile` | 빌드할 때 인덱스까지 생성해 이미지에 포함 |
| `k8s/` | ConfigMap, Deployment, Service, Ingress |
| `scripts/deploy.sh` | 사람과 CD가 함께 쓰는 배포 스크립트 |
| `monitoring/` | 로컬용 docker compose(앱+Prometheus+Grafana), Grafana 대시보드 JSON |
| `k8s/monitoring/` | 클러스터용 Prometheus, Grafana (`scripts/deploy-monitoring.sh`로 설치) |
| `scripts/load_test.py` | 그래프를 움직이기 위한 간단한 부하 발생기 |
| `.github/workflows/` | `ci.yml`(PR 검사), `cd.yml`(빌드·배포) |

## 진행 방식 (혼자 실습)

한 사람이 두 관점을 모두 다룹니다.

- **앱 관점**: RAG, 에이전트, 프롬프트, 평가셋
- **운영 관점**: Dockerfile, K8s, GitHub Actions, Secret, 로그·롤백
- PR은 직접 열고 Files changed를 셀프 리뷰합니다. 병합 조건은 **CI(`test-and-eval`) 통과**이고, 승인 인원은 0명입니다.

---

## 실습 0. 로컬 실행 (API 키 없이)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   /  Mac·Linux: source .venv/bin/activate
pip install -r requirements.txt
python scripts/build_index.py
pytest -q
python eval/run_eval.py
uvicorn app.main:app --reload
```

브라우저에서 http://localhost:8000/docs 를 열어 `/chat`에 질문해 봅니다.
터미널에 찍히는 JSON 로그(버전, 사용한 도구, 출처 문서, 지연시간)를 확인합니다. **이 로그가 LLMOps의 출발점**입니다.

> OpenAI 키가 있으면 `.env.example`을 참고해 `LLM_PROVIDER=openai`, `OPENAI_API_KEY=...`를 환경변수로 설정합니다.

## 실습 1. Docker로 실행

```bash
docker build -t rag-app:local --build-arg APP_VERSION=local .
docker run --rm -p 8000:8000 rag-app:local
curl http://localhost:8000/version
```

## 실습 1-1. 로컬 모니터링 (docker compose)

```bash
cd monitoring
docker compose up -d --build
cd ..
python scripts/load_test.py http://localhost:8000 120
```

- Prometheus http://localhost:9090 → Status → Targets 에서 `rag-app`이 **UP**인지 확인
- Grafana http://localhost:3000 (admin / admin) → **LLMOps → RAG LLMOps** 대시보드
- `load_test.py`에는 문서에 없는 질문("회사 주차장 있나요?")이 섞여 있습니다. **검색 품질 패널**의 유사도가 어떻게 나오는지 봅니다.
- 끝나면 `cd monitoring && docker compose down`

| 패널 | 무엇을 보나 |
|---|---|
| 실행 중인 버전 | 파드별 `app_version`(커밋 해시), 프롬프트 버전, 모델 |
| 버전별 요청 수 | 배포·롤백할 때 선이 바뀌는 순간 |
| 응답시간 p50/p95 | 모델·프롬프트 변경이 속도에 주는 영향 |
| 검색 품질 | 1위 문서 유사도. 떨어지면 문서 보강이 필요하다는 신호 |
| 토큰 사용량 | 비용 추적 (fake 모드는 0) |
| 에러율 / 상태별 요청 | LLM API 장애 감지 |

## 실습 2. GitHub 저장소와 클러스터 연결

1. GitHub에 저장소를 만들고 push
2. **Settings → Branches**: `main` 보호(PR 필수, 필수 승인 0명, CI `test-and-eval` 통과 필수)
3. **Settings → Environments**: `dev`, `production` 생성 → `production`의 Required reviewers에 **본인 계정** 지정 (Prevent self-review는 끈 상태)
4. **Settings → Secrets and variables → Actions**
   - Secret `KUBE_CONFIG`: 가비아에서 받은 kubeconfig를 base64로 인코딩한 값
     - Mac·Linux: `base64 -w0 kubeconfig.yaml`
     - Windows PowerShell: `[Convert]::ToBase64String([IO.File]::ReadAllBytes("kubeconfig.yaml"))`
   - Secret `OPENAI_API_KEY`: (선택)
   - Variable `DEV_HOST`, `PROD_HOST`: (선택) Ingress 도메인
5. 클러스터 확인
   ```bash
   kubectl get nodes
   kubectl get ingressclass     # 없으면 k8s/ingress.yaml 대신 Service type: LoadBalancer
   ```

> **이미지 pull 권한**: GHCR에 처음 올라간 이미지는 private입니다. 실습에서는 GitHub → Packages → 패키지 설정에서 **Public**으로 바꾸는 것이 가장 간단합니다.
> private으로 유지하려면 네임스페이스마다 아래 명령을 실행하고 `k8s/deployment.yaml`의 `imagePullSecrets` 주석을 해제합니다.
> ```bash
> kubectl create secret docker-registry ghcr-pull -n dev \
>   --docker-server=ghcr.io --docker-username=<GitHub ID> --docker-password=<read:packages 권한 PAT>
> ```

## 실습 3. 첫 배포 (v1)

`main`에 push하면 Actions의 **CD**가 실행됩니다. dev 배포가 끝나면 `production` 단계에서 본인이 **Review deployments → Approve** 를 누릅니다.

```bash
kubectl get pods -n dev
kubectl port-forward svc/rag-app 8000:80 -n dev     # Ingress 없을 때
curl http://localhost:8000/version                   # app_version = 커밋 해시
kubectl logs -l app=rag-app -n dev --tail=20         # JSON 로그
```

## 실습 3-1. 클러스터 모니터링 설치

```bash
GRAFANA_PASSWORD='원하는비번' bash scripts/deploy-monitoring.sh
kubectl port-forward svc/grafana 3000:3000 -n monitoring      # http://localhost:3000
kubectl port-forward svc/prometheus 9090:9090 -n monitoring   # Targets 확인용
kubectl port-forward svc/rag-app 8000:80 -n dev               # 다른 터미널
python scripts/load_test.py http://localhost:8000 300
```

대시보드 위쪽 `namespace` 선택으로 dev / prod를 나눠 봅니다.
Prometheus는 디스크 없이 메모리에만 저장하므로 재시작하면 데이터가 초기화됩니다(실습용).

## 실습 4. 수정 → 재배포 시나리오

모든 수정은 **feature 브랜치 → PR → 셀프 리뷰 + CI 통과 → 병합** 순서로 합니다.

| # | 수정 내용 | 관찰 포인트 |
|---|---|---|
| 4-1 | `data/docs/`에 새 문서(예: `event.md`) 추가 + 평가셋에 문항 추가 | 데이터 변경도 이미지 재빌드 → 배포 대상 |
| 4-2 | `prompts/system_v2.txt` 작성 후 `k8s/configmap.yaml`의 `PROMPT_VERSION`을 `v2`로 | `/version`과 로그에서 프롬프트 버전 확인 |
| 4-3 | **일부러 품질 저하**: `data/docs/refund.md` 삭제 후 PR | CI 평가가 실패해 병합이 막히는 것 확인 (retrieval 0.7 < 0.8) |
| 4-4 | ConfigMap에서 `LLM_MODEL` 변경 (openai 모드일 때) | Grafana에서 응답시간·토큰 패널 비교 |

> 4-1, 4-2를 배포하는 동안 `load_test.py`를 계속 돌려 두면, Grafana **버전별 요청 수**에서 이전 버전 선이 내려가고 새 버전 선이 올라가는 **롤링 업데이트**를 볼 수 있습니다.

## 실습 5. 장애와 롤백

문제가 있는 버전이 prod에 나갔다고 가정합니다.

```bash
kubectl rollout history deployment/rag-app -n prod
kubectl rollout undo deployment/rag-app -n prod                 # 직전 버전으로
kubectl rollout undo deployment/rag-app -n prod --to-revision=2 # 특정 버전으로
curl .../version     # 커밋 해시가 되돌아갔는지 확인
```

Grafana **실행 중인 버전** 표와 **버전별 요청 수** 그래프에서도 롤백 순간을 확인합니다. 교안 캡처 포인트입니다.

토론: 롤백한 뒤 Git은 어떻게 정리해야 할까? (`git revert` → PR → 다시 배포)

## 실습 6. (선택) 심화

- TF-IDF 대신 임베딩 API + Chroma로 교체하고 평가 점수 비교
- 평가를 `LLM_PROVIDER=openai`로 돌려 답변 품질(answer_hit)까지 게이트에 포함
- Langfuse 등으로 트레이싱 연결
- Loki를 붙여 JSON 로그도 Grafana에서 검색
- Grafana 알림: p95 > 3초 또는 에러율 > 5%일 때 알림
- ArgoCD로 GitOps(pull 방식) 배포 전환

---

## 자주 막히는 곳

| 증상 | 확인할 것 |
|---|---|
| CD의 kubectl이 `localhost:8080 refused` | `KUBE_CONFIG` Secret 미등록 또는 base64 값 오류 (kubeconfig가 비면 kubectl은 localhost:8080에 접속한다) |
| CD의 `kubectl cluster-info` 실패 | GitHub Actions에서 클러스터 API 서버에 접근 가능한지 (공인 엔드포인트, IP 허용 목록) |
| 파드가 `ImagePullBackOff` | GHCR 패키지 Public 여부 또는 `ghcr-pull` Secret |
| 파드가 `CrashLoopBackOff` | `kubectl logs <pod> -n dev`, ConfigMap 값 오타 |
| 파드가 Running인데 Ready 0/1 | `/health` readinessProbe 실패 → 포트 8000 확인 |
| Grafana 패널이 "No data" | Prometheus Targets에서 rag-app이 UP인지, 파드에 `prometheus.io/scrape` 어노테이션이 있는지, 요청을 보냈는지 |
| Prometheus 파드가 pods 목록을 못 가져옴 | ClusterRole 생성 권한 (`kubectl auth can-i create clusterrole`) |
| 평가가 로컬에선 통과, CI에선 실패 | 인덱스를 다시 만들었는지 (`python scripts/build_index.py`) |
