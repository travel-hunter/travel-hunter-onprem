#!/usr/bin/env bash
# 역추적: 한 요청(request_id) 또는 한 사용자(user:<id>)의 모든 로그 줄을 시간순으로 보여 준다.
# docker logs + jq. 계획: docs/superpowers/plans/2026-09-22-caddy-service-status-log.md
#
#   scripts/trace-request.sh a1b2c3d4e5f6a7b8
#   scripts/trace-request.sh user:42 --since 48h
#   scripts/trace-request.sh a1b2c3d4e5f6a7b8 --sensitive     # kind=debug 줄까지 (출력 편의일 뿐 접근 통제가 아니다)
#
# AWS 이전 후에는 같은 조건을 CloudWatch Logs Insights 로: filter request_id = "..." / filter user_id = 42
set -euo pipefail

usage() {
  echo "usage: $0 <request_id | user:<id>> [--since 48h] [--container NAME] [--sensitive]" >&2
  exit 1
}
[ $# -ge 1 ] || usage
KEY=$1; shift
SINCE=48h
CONTAINER=${TRACE_CONTAINER:-travel-hunter-onprem-backend-1}
SENSITIVE=0
while [ $# -gt 0 ]; do
  case $1 in
    --since) SINCE=$2; shift 2 ;;
    --container) CONTAINER=$2; shift 2 ;;
    --sensitive) SENSITIVE=1; shift ;;
    *) usage ;;
  esac
done
command -v jq >/dev/null || { echo "jq 가 필요하다" >&2; exit 2; }

if [[ $KEY == user:* ]]; then
  SELECT=".user_id == ${KEY#user:}"
else
  SELECT=".request_id == \"$KEY\""
fi
[ "$SENSITIVE" = 1 ] || SELECT="($SELECT) and .kind != \"debug\""

# JSON 줄만 고른다 - 기동 배너 등 비 JSON 줄은 건너뛴다
docker logs --since "$SINCE" "$CONTAINER" 2>&1 | grep '^{' | jq -r --arg select "$SELECT" '
  select('"$SELECT"')
  | (.ts | sub("T"; " ") | .[0:23]) as $t
  | if .kind == "access" then
      "\($t)  ACCESS \(.method) \(.path) \(.status // .outcome)  \(.duration_ms // "-")ms  user=\(.user_id // "-")  rid=\(.request_id)"
      + (if .body_shape then "\n           body_shape=\(.body_shape | tojson)" else "" end)
    elif .kind == "debug" then
      "\($t)  DEBUG  \(.method) \(.path)  body=\(.debug_body | tojson)"
    else
      "\($t)  \(.level | .[0:5] | . + "     " | .[0:6]) \(.logger)  \(.msg)"
      + (if .exc_type then "\n           ↳ \(.exc_type): \(.exc_message)" else "" end)
      + (if .frames then "\n" + (.frames | map("             " + .) | join("\n")) else "" end)
      + (if .causes then "\n" + (.causes | map("           ↳ cause \(.exc_type): \(.exc_message)") | join("\n")) else "" end)
    end
'
