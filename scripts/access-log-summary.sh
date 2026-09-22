#!/usr/bin/env bash
# 최근 요청 요약: 시간대×상태군 count/avg/max, 5xx 상위 경로, 최근 5xx 20줄(request_id 포함 - trace-request 의 입구).
# docker logs + jq. 계획: docs/superpowers/plans/2026-09-22-caddy-service-status-log.md
#
#   scripts/access-log-summary.sh                # 최근 24시간
#   scripts/access-log-summary.sh --since 2h
set -euo pipefail

SINCE=24h
CONTAINER=${TRACE_CONTAINER:-travel-hunter-onprem-backend-1}
while [ $# -gt 0 ]; do
  case $1 in
    --since) SINCE=$2; shift 2 ;;
    --container) CONTAINER=$2; shift 2 ;;
    *) echo "usage: $0 [--since 24h] [--container NAME]" >&2; exit 1 ;;
  esac
done
command -v jq >/dev/null || { echo "jq 가 필요하다" >&2; exit 2; }

docker logs --since "$SINCE" "$CONTAINER" 2>&1 | grep '^{' | jq -rs '
  map(select(.kind == "access" and .status != null)) as $rows
  | if ($rows | length) == 0 then "접근 줄 없음 (--since \(env.SINCE // "24h") 안에 기록된 요청이 없다)" else
    "== 시간대 × 상태군 (count / avg ms / max ms) ==",
    ( $rows
      | group_by(.ts[0:13], (.status / 100 | floor))
      | map({ hour: .[0].ts[0:13], cls: "\(.[0].status / 100 | floor)xx", n: length,
              avg: ((map(.duration_ms) | add) / length | floor), max: (map(.duration_ms) | max) })
      | .[] | "\(.hour)  \(.cls)  \(.n | tostring | . + "      " | .[0:6]) avg \(.avg)ms  max \(.max)ms" ),
    "",
    "== 5xx 상위 경로 ==",
    ( $rows | map(select(.status >= 500)) | group_by(.path) | map({path: .[0].path, n: length})
      | sort_by(-.n) | .[0:10] | .[] | "\(.n | tostring | . + "    " | .[0:5]) \(.path)" ),
    "",
    "== 최근 5xx (request_id 로 trace-request.sh) ==",
    ( $rows | map(select(.status >= 500)) | .[-20:] | .[]
      | "\(.ts | sub("T"; " ") | .[0:19])  \(.method) \(.path) \(.status)  user=\(.user_id // "-")  rid=\(.request_id)" )
  end
'
