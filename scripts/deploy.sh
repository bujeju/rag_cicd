#!/usr/bin/env bash
# 사용법: ./scripts/deploy.sh <namespace> <image> [host]
#   예)   ./scripts/deploy.sh dev ghcr.io/myteam/rag_cicd:3f2a1bc dev.example.com
# CD 워크플로와 사람이 같은 스크립트를 쓴다 → "수동으로 되는 건 자동으로도 된다"
set -euo pipefail

NS="$1"
IMAGE="$2"
HOST="${3:-}"

kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -

# API 키가 환경변수에 있으면 Secret 생성/갱신 (없으면 fake 모드로 동작)
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  kubectl create secret generic rag-secret -n "$NS" \
    --from-literal=OPENAI_API_KEY="$OPENAI_API_KEY" \
    --dry-run=client -o yaml | kubectl apply -f -
fi

kubectl apply -n "$NS" -f k8s/configmap.yaml -f k8s/service.yaml
sed "s|IMAGE_PLACEHOLDER|$IMAGE|" k8s/deployment.yaml | kubectl apply -n "$NS" -f -

if [[ -n "$HOST" ]]; then
  sed "s|HOST_PLACEHOLDER|$HOST|" k8s/ingress.yaml | kubectl apply -n "$NS" -f -
fi

# 배포 이력에 사유 기록 → kubectl rollout history 에서 보인다
kubectl annotate deployment/rag-app -n "$NS" \
  kubernetes.io/change-cause="deploy $IMAGE" --overwrite

kubectl rollout status deployment/rag-app -n "$NS" --timeout=180s
kubectl get pods -n "$NS" -l app=rag-app -o wide
