#!/usr/bin/env bash
# Prometheus + Grafana 를 monitoring 네임스페이스에 설치/갱신한다.
# 사용법: GRAFANA_PASSWORD='원하는비번' bash scripts/deploy-monitoring.sh
# 접속:   kubectl port-forward svc/grafana 3000:3000 -n monitoring  → http://localhost:3000
set -euo pipefail

NS=monitoring
: "${GRAFANA_PASSWORD:?GRAFANA_PASSWORD 환경변수를 설정하세요}"

kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic grafana-admin -n "$NS" \
  --from-literal=user=admin --from-literal=password="$GRAFANA_PASSWORD" \
  --dry-run=client -o yaml | kubectl apply -f -

# 로컬과 같은 대시보드 JSON 을 ConfigMap 으로
kubectl create configmap grafana-dashboards -n "$NS" \
  --from-file=monitoring/grafana/dashboards/ \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f k8s/monitoring/prometheus.yaml -f k8s/monitoring/grafana.yaml

# ConfigMap 변경(대시보드/설정)이 반영되도록 재시작
kubectl rollout restart deployment/prometheus deployment/grafana -n "$NS"
kubectl rollout status deployment/prometheus -n "$NS" --timeout=180s
kubectl rollout status deployment/grafana -n "$NS" --timeout=180s
kubectl get pods -n "$NS"
